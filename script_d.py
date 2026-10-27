"""
script_e.py - damaged-recording tier: Silero VAD + SpeechBrain + Whisper.
"""
import sys
import json
import random
import hashlib
import logging
import csv
import re
from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd
import torch
import torchaudio
import whisper
from sklearn.cluster import AgglomerativeClustering

# =============================================================================
# USER CONFIGURATION
# =============================================================================
NUM_SPEAKERS = 2            # Maximum speakers per recording
DISTANCE_THRESHOLD = 0.65   # Only used inside chunks when NUM_SPEAKERS is None
WHISPER_MODEL = "medium"
INPUT_DIR = "A"
OUTPUT_DIR = "B"
OUTPUT_SUFFIX = "_script_e"
SKIP_EXISTING = False       # Skip recordings that already have an output CSV

SEED = 1234
BEAM_SIZE = None

# --- Voice activity detection (Silero) ---
VAD_THRESHOLD = 0.4         # Lower than Silero's 0.5 default: quiet, hissy tape
VAD_MIN_SPEECH_MS = 250
VAD_MIN_SILENCE_MS = 300
VAD_PAD_MS = 100
MAX_REGION_SEC = 10.0       # Long regions are split (at pauses) so one region ~ one voice
HALLUCINATIONS = "flag"     # "flag" = prefix with [?], "drop" = remove, "keep" = leave as is
MIN_VAD_COVERAGE = 0.2      # Sentences with less of their time inside VAD speech are suspect

CHUNK_SEC = 300
MIN_LAST_CHUNK_SEC = 120
MIN_EMBED_SEC = 0.5
CLUSTER_MIN_SEC = 2.0
CORE_MIN_SEC = 8.0
MIN_SPEAKER_SEC = 10.0
SPARE_CLUSTERS = 2
MERGE_SIM = 0.80

# --- Sentences and turns ---
SENTENCE_PAUSE_SEC = 2.0    # Also end a sentence at a pause this long (punctuation is unreliable)
TURN_BREAK_SEC = 10.0       # Start a new row after this much silence, even for the same speaker
LABEL_INTERVIEWER = True    # Name the most question-heavy voice "Interviewer"
INTERVIEWER_MIN_RATE = 0.20 # ...if at least this share of its sentences are questions
USE_INTERJECTIONS = True
INTERJECTION_GAP = 0.25     # Pause needed before a trailing interjection to move it
INTERJECTIONS = {"yeah", "yes", "sure", "right", "yep", "nope", "no", "uh huh", "uh-huh",
                 "mm-hmm", "hmm", "mhm", "okay", "ok"}

# --- Housekeeping ---
CACHE = True
DEBUG_SEGMENTS = False      # Also write a per-sentence CSV (VAD coverage, question, speaker)
SAMPLE_RATE = 16000
# =============================================================================

if not hasattr(torchaudio, "list_audio_backends"):
    torchaudio.list_audio_backends = lambda: ["ffmpeg"]

try:
    from speechbrain.inference.speaker import EncoderClassifier
    from silero_vad import load_silero_vad, get_speech_timestamps
except ImportError as e:
    print(f"Error: import failed - {e}")
    print("Run: pip install speechbrain==1.0.3 silero-vad")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def norm_word(w):
    return re.sub(r"[^\w\s'-]", "", w.lower()).strip()


class Coverage:
    """Fast 'how much of [a, b] lies inside VAD speech' lookups."""
    def __init__(self, regions):
        self.s = np.array([r[0] for r in regions]) if regions else np.zeros(0)
        self.e = np.array([r[1] for r in regions]) if regions else np.zeros(0)

    def __call__(self, a, b):
        if b <= a or len(self.s) == 0:
            return 0.0
        lo = np.searchsorted(self.e, a)
        hi = np.searchsorted(self.s, b)
        if hi <= lo:
            return 0.0
        ov = np.minimum(self.e[lo:hi], b) - np.maximum(self.s[lo:hi], a)
        return float(np.clip(ov, 0, None).sum() / (b - a))


class DamagedAudioTranscriber:
    def __init__(self, input_dir=INPUT_DIR, output_dir=OUTPUT_DIR,
                 whisper_model=WHISPER_MODEL, num_speakers=NUM_SPEAKERS,
                 distance_threshold=DISTANCE_THRESHOLD):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.cache_dir = self.output_dir / "_cache"
        if CACHE:
            self.cache_dir.mkdir(exist_ok=True)
        self.model_name = whisper_model
        self.num_speakers = num_speakers
        self.distance_threshold = distance_threshold

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing on {self.device.upper()}...")
        logger.info("Loading SpeechBrain biometric model (ECAPA-TDNN)...")
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb", run_opts={"device": self.device})
        logger.info("Loading Silero VAD...")
        self.vad_model = load_silero_vad()
        self.whisper_model = None           # loaded only if a transcript isn't cached

    # ----------------------------------------------------------------- cache
    def cache_key(self, audio_path):
        """Identical to script_a.py so the transcript cache is shared."""
        st = audio_path.stat()
        settings = dict(file=audio_path.name, size=st.st_size, mtime=int(st.st_mtime),
                        model=self.model_name, seed=SEED, beam=BEAM_SIZE,
                        whisper=getattr(whisper, "__version__", "?"))
        digest = hashlib.sha1(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:10]
        return f"{audio_path.stem}.{self.model_name}.{digest}"

    # ------------------------------------------------------------- whisper
    def transcribe(self, audio, key):
        cache_file = self.cache_dir / f"{key}.transcript.json"
        if CACHE and cache_file.exists():
            data = json.loads(cache_file.read_text())
            if isinstance(data, dict) and data.get("format") == 2:
                logger.info(f"Using cached transcript: {cache_file.name}")
                return data["segments"]
            logger.info("Cached transcript has no word timings (older script_a); re-transcribing")

        if self.whisper_model is None:
            logger.info(f"Loading Whisper '{self.model_name}'...")
            self.whisper_model = whisper.load_model(self.model_name, device=self.device)
        set_seed(SEED)
        kwargs = dict(word_timestamps=True, fp16=(self.device == "cuda"))
        if BEAM_SIZE:
            kwargs["beam_size"] = BEAM_SIZE
        result = self.whisper_model.transcribe(audio, **kwargs)
        segments = [
            {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip(),
             "words": [[round(float(w["start"]), 3), round(float(w["end"]), 3), w["word"].strip()]
                       for w in s.get("words", []) if w.get("word", "").strip()]}
            for s in result["segments"] if s.get("text", "").strip()
        ]
        if CACHE:
            cache_file.write_text(json.dumps({"format": 2, "segments": segments}))
        return segments

    # ------------------------------------------------------------------ VAD
    def vad_regions(self, audio, key):
        settings = f"{VAD_THRESHOLD}_{VAD_MIN_SPEECH_MS}_{VAD_MIN_SILENCE_MS}_{VAD_PAD_MS}_{MAX_REGION_SEC}"
        cache_file = self.cache_dir / f"{key}.vad_{settings}.json"
        if CACHE and cache_file.exists():
            return json.loads(cache_file.read_text())
        logger.info("Running Silero VAD...")
        ts = get_speech_timestamps(
            torch.from_numpy(audio), self.vad_model, sampling_rate=SAMPLE_RATE,
            threshold=VAD_THRESHOLD, min_speech_duration_ms=VAD_MIN_SPEECH_MS,
            min_silence_duration_ms=VAD_MIN_SILENCE_MS, speech_pad_ms=VAD_PAD_MS,
            max_speech_duration_s=MAX_REGION_SEC)
        regions = [[t["start"] / SAMPLE_RATE, t["end"] / SAMPLE_RATE] for t in ts]
        if CACHE:
            cache_file.write_text(json.dumps(regions))
        return regions

    # ---------------------------------------------------------- embeddings
    def embed_regions(self, audio, units, key):
        cache_file = self.cache_dir / f"{key}.vademb_{len(units)}_{MIN_EMBED_SEC}.npz"
        if CACHE and cache_file.exists():
            data = np.load(cache_file)
            return data["idx"], data["emb"]
        idx, embs = [], []
        min_len = int(MIN_EMBED_SEC * SAMPLE_RATE)
        with torch.no_grad():
            for i, u in enumerate(units):
                chunk = audio[int(u["start"] * SAMPLE_RATE):int(u["end"] * SAMPLE_RATE)]
                if len(chunk) < min_len:
                    continue
                emb = self.encoder.encode_batch(torch.from_numpy(chunk).unsqueeze(0))
                embs.append(emb.squeeze().cpu().numpy())
                idx.append(i)
        idx = np.array(idx, dtype=int)
        emb = unit(np.array(embs)) if embs else np.empty((0, 192))
        if CACHE:
            np.savez(cache_file, idx=idx, emb=emb)
        return idx, emb

    # ------------------------------------------------- clustering (= _a)
    def local_cluster(self, emb):
        n = len(emb)
        if n < 2:
            return np.zeros(n, dtype=int)
        if self.num_speakers:
            clusterer = AgglomerativeClustering(
                n_clusters=min(self.num_speakers + SPARE_CLUSTERS, n),
                metric="cosine", linkage="average")
        else:
            clusterer = AgglomerativeClustering(
                n_clusters=None, distance_threshold=self.distance_threshold,
                metric="cosine", linkage="average")
        return clusterer.fit_predict(emb)

    @staticmethod
    def assign_chunks(segments, total_sec):
        n_chunks = max(1, int(np.ceil(total_sec / CHUNK_SEC)))
        if n_chunks > 1 and total_sec - (n_chunks - 1) * CHUNK_SEC < MIN_LAST_CHUNK_SEC:
            n_chunks -= 1
        mids = np.array([(s["start"] + s["end"]) / 2 for s in segments])
        return np.minimum((mids // CHUNK_SEC).astype(int), n_chunks - 1), n_chunks

    @staticmethod
    def merge_similar(glab, cents, secs):
        glab = glab.copy()
        while True:
            ids = np.unique(glab)
            if len(ids) < 2:
                return glab
            c = np.stack([unit((cents[glab == g] * secs[glab == g, None]).sum(axis=0)) for g in ids])
            sim = c @ c.T
            np.fill_diagonal(sim, -1)
            a, b = np.unravel_index(np.argmax(sim), sim.shape)
            if sim[a, b] < MERGE_SIM:
                return glab
            glab[glab == ids[b]] = ids[a]

    def diarize(self, segments, emb_idx, emb, total_sec):
        n_seg = len(segments)
        labels = np.full(n_seg, -1, dtype=int)
        if len(emb) == 0:
            return labels
        dur = np.array([segments[i]["end"] - segments[i]["start"] for i in emb_idx])
        seg_chunk, n_chunks = self.assign_chunks(segments, total_sec)
        emb_chunk = seg_chunk[emb_idx]

        items, local_of = [], np.full(len(emb), -1)
        for c in range(n_chunks):
            pos = np.where(emb_chunk == c)[0]
            reliable = pos[dur[pos] >= CLUSTER_MIN_SEC]
            pos = reliable if len(reliable) >= 2 else pos
            if len(pos) == 0:
                continue
            loc = self.local_cluster(emb[pos])
            for lab in np.unique(loc):
                members = pos[loc == lab]
                local_of[members] = len(items)
                items.append({"chunk": c, "centroid": unit(emb[members].mean(axis=0)),
                              "seconds": float(dur[members].sum())})

        core = [k for k, it in enumerate(items) if it["seconds"] >= CORE_MIN_SEC] or list(range(len(items)))
        cents = np.stack([items[k]["centroid"] for k in core])
        secs = np.array([items[k]["seconds"] for k in core])
        k_max = self.num_speakers or len(core)
        n_global = min(k_max + SPARE_CLUSTERS, len(core))
        glab = (AgglomerativeClustering(n_clusters=n_global, metric="cosine", linkage="average")
                .fit_predict(cents) if n_global >= 2 else np.zeros(len(core), dtype=int))
        glab = self.merge_similar(glab, cents, secs)

        g_ids = np.unique(glab)
        g_sec = {g: secs[glab == g].sum() for g in g_ids}
        ranked = sorted(g_ids, key=lambda g: -g_sec[g])
        keep = [g for g in ranked[:k_max] if g_sec[g] >= MIN_SPEAKER_SEC] or ranked[:1]
        spk_cent = np.stack([unit((cents[glab == g] * secs[glab == g, None]).sum(axis=0)) for g in keep])

        item_spk = {}
        for j, k in enumerate(core):
            item_spk[k] = keep.index(glab[j]) if glab[j] in keep else int(np.argmax(spk_cent @ items[k]["centroid"]))
        anchors = {}
        for k in item_spk:
            anchors.setdefault(items[k]["chunk"], []).append(k)
        for p, seg_i in enumerate(emb_idx):
            k = local_of[p]
            if k in item_spk:
                labels[seg_i] = item_spk[k]
                continue
            cands = [(float(items[a]["centroid"] @ emb[p]), item_spk[a]) for a in anchors.get(emb_chunk[p], [])]
            cands += [(float(spk_cent[s] @ emb[p]), s) for s in range(len(keep))]
            labels[seg_i] = max(cands)[1]

        speech = np.bincount(labels[labels >= 0], weights=[segments[i]["end"] - segments[i]["start"]
                                                           for i in np.where(labels >= 0)[0]], minlength=len(keep))
        logger.info(f"{len(emb)} voiced regions embedded, {n_chunks} chunk(s), {len(core)} anchors -> "
                    + ", ".join(f"S{s + 1}={speech[s] / 60:.1f} min" for s in range(len(keep))))
        if len(keep) > 1:
            sim = spk_cent @ spk_cent.T
            logger.info("Speaker voiceprint similarity (0.9+ suggests one voice split): " + ", ".join(
                f"S{a + 1}-S{b + 1}={sim[a, b]:.2f}" for a in range(len(keep)) for b in range(a + 1, len(keep))))
        return labels

    @staticmethod
    def fill_unlabelled(units, labels):
        known = np.where(labels >= 0)[0]
        if len(known) == 0:
            return np.zeros(len(labels), dtype=int)
        out = labels.copy()
        starts = np.array([u["start"] for u in units])
        ends = np.array([u["end"] for u in units])
        for i in np.where(labels < 0)[0]:
            gaps = np.maximum(starts[known] - ends[i], starts[i] - ends[known])
            out[i] = labels[known[np.argmin(np.abs(gaps))]]
        return out

    # ------------------------------------------------------------ sentences
    @staticmethod
    def build_sentences(segments):
        words = [w for s in segments for w in s.get("words", [])]
        if not words:      # no word timings: fall back to Whisper segments
            words = [[s["start"], s["end"], s["text"]] for s in segments]
        sentences, cur = [], []
        for w in words:
            if cur and w[0] - cur[-1][1] > SENTENCE_PAUSE_SEC:
                sentences.append(cur)
                cur = []
            cur.append(w)
            if w[2].endswith((".", "?", "!")):
                sentences.append(cur)
                cur = []
        if cur:
            sentences.append(cur)
        return [{"words": s, "start": s[0][0], "end": s[-1][1],
                 "is_question": s[-1][2].endswith("?")} for s in sentences]

    @staticmethod
    def label_sentences(sentences, units, unit_labels):
        u_s = np.array([u["start"] for u in units])
        u_e = np.array([u["end"] for u in units])
        n_spk = int(unit_labels.max()) + 1 if len(unit_labels) else 1
        for s in sentences:
            lo, hi = np.searchsorted(u_e, s["start"]), np.searchsorted(u_s, s["end"])
            ov = np.clip(np.minimum(u_e[lo:hi], s["end"]) - np.maximum(u_s[lo:hi], s["start"]), 0, None)
            if len(ov) and ov.sum() > 0:
                s["spk"] = int(np.argmax(np.bincount(unit_labels[lo:hi], weights=ov, minlength=n_spk)))
            elif len(units):
                mid = (s["start"] + s["end"]) / 2
                s["spk"] = int(unit_labels[np.argmin(np.abs((u_s + u_e) / 2 - mid))])
            else:
                s["spk"] = 0

    @staticmethod
    def move_interjections(sentences):
        """Trailing 'yeah' etc. after a pause, right before a speaker change, belongs to the next speaker."""
        moved = 0
        for a, b in zip(sentences[:-1], sentences[1:]):
            if a["spk"] == b["spk"] or len(a["words"]) < 2:
                continue
            for n in (2, 1):                        # two-word ones first ("uh huh")
                if len(a["words"]) <= n:
                    continue
                tail = a["words"][-n:]
                if norm_word(" ".join(w[2] for w in tail)) in INTERJECTIONS and \
                        tail[0][0] - a["words"][-n - 1][1] >= INTERJECTION_GAP:
                    a["words"] = a["words"][:-n]
                    b["words"] = tail + b["words"]
                    a["end"], b["start"] = a["words"][-1][1], b["words"][0][0]
                    moved += 1
                    break
        return moved

    def speaker_names(self, sentences):
        order = {}
        for s in sentences:
            order.setdefault(s["spk"], len(order))
        names = {spk: f"Speaker {i + 1}" for spk, i in order.items()}
        if LABEL_INTERVIEWER and len(order) > 1:
            rate = {}
            for spk in order:
                mine = [s for s in sentences if s["spk"] == spk and not s.get("suspect")]
                if len(mine) >= 5:
                    rate[spk] = sum(s["is_question"] for s in mine) / len(mine)
            if rate:
                ranked = sorted(rate, key=lambda k: -rate[k])
                top = ranked[0]
                second = rate[ranked[1]] if len(ranked) > 1 else 0.0
                if rate[top] >= INTERVIEWER_MIN_RATE and rate[top] >= 1.5 * second:
                    names[top] = "Interviewer"
                    others = [k for k in order if k != top]
                    for i, spk in enumerate(sorted(others, key=lambda k: order[k])):
                        names[spk] = f"Speaker {i + 1}"
                    logger.info(f"'Interviewer' = voice with {rate[top]:.0%} questions "
                                f"(next highest {second:.0%})")
        return names

    # --------------------------------------------------------------- output
    @staticmethod
    def format_timestamp(seconds):
        total = int(timedelta(seconds=float(seconds)).total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def process_file(self, audio_path):
        out_file = self.output_dir / f"{audio_path.stem}{OUTPUT_SUFFIX}.csv"
        if SKIP_EXISTING and out_file.exists():
            logger.info(f"Skipping {audio_path.name} (output exists)")
            return
        logger.info(f"--- Processing: {audio_path.name} ---")
        key = self.cache_key(audio_path)
        audio = whisper.load_audio(str(audio_path))
        total = len(audio) / SAMPLE_RATE
        logger.info(f"Duration: {total / 60:.1f} min")

        segments = self.transcribe(audio, key)
        regions = self.vad_regions(audio, key)
        if not segments or not regions:
            logger.warning(f"No speech found in {audio_path.name}")
            return

        units = [{"start": a, "end": b} for a, b in regions]
        emb_idx, emb = self.embed_regions(audio, units, key)
        del audio
        unit_labels = self.fill_unlabelled(units, self.diarize(units, emb_idx, emb, total))

        sentences = self.build_sentences(segments)
        cover = Coverage(regions)
        for s in sentences:
            s["vad"] = cover(s["start"], s["end"]) if s["end"] > s["start"] else 1.0
            s["suspect"] = s["vad"] < MIN_VAD_COVERAGE
        n_suspect = sum(s["suspect"] for s in sentences)
        if n_suspect:
            logger.info(f"{n_suspect} sentence(s) fall outside detected speech "
                        f"({'dropped' if HALLUCINATIONS == 'drop' else HALLUCINATIONS})")
        if HALLUCINATIONS == "drop":
            sentences = [s for s in sentences if not s["suspect"]]
        if not sentences:
            logger.warning("Nothing left after removing suspected hallucinations")
            return

        self.label_sentences(sentences, units, unit_labels)
        if USE_INTERJECTIONS:
            moved = self.move_interjections(sentences)
            if moved:
                logger.info(f"Moved {moved} trailing interjection(s) to the next speaker")
        names = self.speaker_names(sentences)

        def text_of(s):
            t = " ".join(w[2] for w in s["words"])
            return f"[?] {t}" if s["suspect"] and HALLUCINATIONS == "flag" else t

        turns, prev = [], None
        for s in sentences:
            name = names[s["spk"]]
            if turns and turns[-1]["speaker"] == name and s["start"] - prev["end"] <= TURN_BREAK_SEC:
                turns[-1]["words"] += " " + text_of(s)
            else:
                turns.append({"speaker": name, "timestamp": self.format_timestamp(s["start"]),
                              "words": text_of(s)})
            prev = s
        pd.DataFrame(turns, columns=["speaker", "timestamp", "words"]).to_csv(
            out_file, index=False, quoting=csv.QUOTE_MINIMAL)

        if DEBUG_SEGMENTS:
            pd.DataFrame({
                "start": [round(s["start"], 2) for s in sentences],
                "end": [round(s["end"], 2) for s in sentences],
                "speaker": [names[s["spk"]] for s in sentences],
                "vad_coverage": [round(s["vad"], 2) for s in sentences],
                "question": [s["is_question"] for s in sentences],
                "text": [" ".join(w[2] for w in s["words"]) for s in sentences],
            }).to_csv(self.output_dir / f"{audio_path.stem}{OUTPUT_SUFFIX}_sentences.csv", index=False)
        logger.info(f"Done! Saved to {out_file.name}\n")

    def run(self):
        files = []
        for ext in [".mp3", ".MP3", ".wav", ".m4a", ".flac"]:
            files.extend(self.input_dir.glob(f"*{ext}"))
        for f in sorted(set(files)):
            try:
                self.process_file(f)
            except Exception as e:
                logger.exception(f"Failed {f.name}: {e}")


if __name__ == "__main__":
    DamagedAudioTranscriber().run()