"""
script_c.py - Whisper transcription + SpeechBrain speaker labels,
built to keep 5-minute-sample accuracy on 15-minute to 4-hour recordings.
"""
import sys
import json
import random
import hashlib
import logging
import csv
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
NUM_SPEAKERS = 2            # Maximum speakers per recording (same meaning as before)
DISTANCE_THRESHOLD = 0.65   # Only used inside chunks when NUM_SPEAKERS is None
WHISPER_MODEL = "large-v2"
INPUT_DIR = "A"
OUTPUT_DIR = "B"
OUTPUT_SUFFIX = "_script_c" 

# --- Whisper ---
SEED = 1234                 # Fixed seed: makes Whisper's fallback sampling repeatable
BEAM_SIZE = None            # None = greedy, as in the original. 5 = slower, sometimes cleaner

# --- Chunked diarization ---
CHUNK_SEC = 300             # Cluster speakers within 5-minute chunks
MIN_LAST_CHUNK_SEC = 120    # A shorter final chunk is merged into the previous one
MIN_EMBED_SEC = 0.5         # Segments shorter than this take a neighbour's label (as original)
CLUSTER_MIN_SEC = 2.0       # Only segments this long shape the clusters; shorter ones
                            # ("Uh-huh", "Yes") are matched to the closest voice afterwards
CORE_MIN_SEC = 8.0          # A chunk-level speaker needs this much speech to anchor linking
MIN_SPEAKER_SEC = 10.0      # A recording-level speaker needs this much speech to keep a label
SPARE_CLUSTERS = 2          # Extra clusters that soak up coughs, tape noise and laughter
MERGE_SIM = 0.80            # Speakers whose voiceprints are this similar are one person

# --- Housekeeping ---
CACHE = True                # Reuse transcripts/embeddings from OUTPUT_DIR/_cache
DEBUG_SEGMENTS = False      # Also write a per-segment CSV with chunk/cluster details
SAMPLE_RATE = 16000
# =============================================================================

if not hasattr(torchaudio, "list_audio_backends"):
    torchaudio.list_audio_backends = lambda: ["ffmpeg"]

try:
    from speechbrain.inference.speaker import EncoderClassifier
except ImportError:
    print("Error: speechbrain not found. Run 'pip install speechbrain==1.0.3'")
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


class WhisperBiometricTranscriber:
    def __init__(
        self,
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
        whisper_model=WHISPER_MODEL,
        num_speakers=NUM_SPEAKERS,
        distance_threshold=DISTANCE_THRESHOLD,
    ):
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
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": self.device}
        )

        logger.info(f"Loading Whisper '{whisper_model}'...")
        self.whisper_model = whisper.load_model(whisper_model, device=self.device)

    # ----------------------------------------------------------------- cache
    def cache_key(self, audio_path):
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
            logger.info(f"Using cached transcript: {cache_file.name}")
            return json.loads(cache_file.read_text())

        set_seed(SEED)
        kwargs = dict(word_timestamps=True, fp16=(self.device == "cuda"))
        if BEAM_SIZE:
            kwargs["beam_size"] = BEAM_SIZE
        # Default temperature fallback and condition_on_previous_text=True are kept on
        # purpose: they are what lets Whisper escape repetition loops.
        result = self.whisper_model.transcribe(audio, **kwargs)
        segments = [
            {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
            for s in result["segments"] if s.get("text", "").strip()
        ]
        if CACHE:
            cache_file.write_text(json.dumps(segments))
        return segments

    # ---------------------------------------------------------- embeddings
    def embed_segments(self, audio, segments, key):
        cache_file = self.cache_dir / f"{key}.emb{MIN_EMBED_SEC}.npz"
        if CACHE and cache_file.exists():
            data = np.load(cache_file)
            logger.info(f"Using cached embeddings: {cache_file.name}")
            return data["idx"], data["emb"]

        idx, embs = [], []
        min_len = int(MIN_EMBED_SEC * SAMPLE_RATE)
        with torch.no_grad():
            for i, seg in enumerate(segments):
                chunk = audio[int(seg["start"] * SAMPLE_RATE):int(seg["end"] * SAMPLE_RATE)]
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

    # ---------------------------------------------------------- clustering
    def local_cluster(self, emb):
        """The original script_a clustering on one chunk, plus spare clusters for junk."""
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

    def diarize(self, segments, emb_idx, emb, total_sec):
        """Returns a speaker index per segment (or -1 when nothing can be inferred)."""
        n_seg = len(segments)
        labels = np.full(n_seg, -1, dtype=int)
        info = {"chunk": np.full(n_seg, -1), "local": np.full(n_seg, -1), "core": np.zeros(n_seg, bool)}
        if len(emb) == 0:
            return labels, info

        dur = np.array([segments[i]["end"] - segments[i]["start"] for i in emb_idx])
        seg_chunk, n_chunks = self.assign_chunks(segments, total_sec)
        emb_chunk = seg_chunk[emb_idx]

        # STEP A: original clustering inside each chunk -> chunk-level speakers ("items")
        items = []          # dicts: chunk, members (positions into emb), centroid, seconds
        local_of = np.full(len(emb), -1)
        for c in range(n_chunks):
            pos = np.where(emb_chunk == c)[0]
            reliable = pos[dur[pos] >= CLUSTER_MIN_SEC]
            pos = reliable if len(reliable) >= 2 else pos   # short segments act as bridges
            if len(pos) == 0:                               # between voices, so leave them out
                continue
            loc = self.local_cluster(emb[pos])
            for lab in np.unique(loc):
                members = pos[loc == lab]
                local_of[members] = len(items)
                items.append({"chunk": c, "members": members,
                              "centroid": unit(emb[members].mean(axis=0)),
                              "seconds": float(dur[members].sum())})

        core = [k for k, it in enumerate(items) if it["seconds"] >= CORE_MIN_SEC]
        if not core:                       # very short or very fragmented file
            core = list(range(len(items)))

        # STEP B: link chunk-level speakers across the recording. Spare clusters give
        # odd items (noise, laughter, tape artifacts) somewhere to go instead of forcing
        # two real voices together; then near-identical voiceprints are merged and the
        # largest NUM_SPEAKERS groups become the speakers.
        cents = np.stack([items[k]["centroid"] for k in core])
        secs = np.array([items[k]["seconds"] for k in core])
        k_max = self.num_speakers or len(core)
        n_global = min(k_max + SPARE_CLUSTERS, len(core))
        if n_global >= 2:
            glab = AgglomerativeClustering(
                n_clusters=n_global, metric="cosine", linkage="average").fit_predict(cents)
        else:
            glab = np.zeros(len(core), dtype=int)
        glab = self.merge_similar(glab, cents, secs)

        g_ids = np.unique(glab)
        g_sec = {g: secs[glab == g].sum() for g in g_ids}
        ranked = sorted(g_ids, key=lambda g: -g_sec[g])
        keep = [g for g in ranked[:k_max] if g_sec[g] >= MIN_SPEAKER_SEC] or ranked[:1]

        spk_cent = np.stack([unit((cents[glab == g] * secs[glab == g, None]).sum(axis=0))
                             for g in keep])

        item_spk = {}
        for j, k in enumerate(core):
            if glab[j] in keep:
                item_spk[k] = keep.index(glab[j])
            else:   # dropped cluster -> closest kept speaker
                item_spk[k] = int(np.argmax(spk_cent @ items[k]["centroid"]))

        # STEP C: segments of small chunk-level clusters go to the closest speaker,
        # comparing against that chunk's own anchors first (same recording conditions).
        anchors_by_chunk = {}
        for k in item_spk:
            anchors_by_chunk.setdefault(items[k]["chunk"], []).append(k)

        for p, seg_i in enumerate(emb_idx):
            k = local_of[p]
            info["chunk"][seg_i] = emb_chunk[p]
            info["local"][seg_i] = k
            if k in item_spk:
                labels[seg_i] = item_spk[k]
                info["core"][seg_i] = True
                continue
            cands = [(float(items[a]["centroid"] @ emb[p]), item_spk[a])
                     for a in anchors_by_chunk.get(emb_chunk[p], [])]
            cands += [(float(spk_cent[s] @ emb[p]), s) for s in range(len(keep))]
            labels[seg_i] = max(cands)[1]

        # Diagnostics for tuning
        shares = np.bincount(labels[labels >= 0], weights=[segments[i]["end"] - segments[i]["start"]
                                                           for i in np.where(labels >= 0)[0]],
                             minlength=len(keep))
        logger.info(f"{len(emb)} embedded segments, {n_chunks} chunk(s), "
                    f"{len(items)} chunk-level clusters ({len(core)} anchors)")
        logger.info("Speaker speech (min): " +
                    ", ".join(f"S{s + 1}={shares[s] / 60:.1f}" for s in range(len(keep))))
        if len(keep) > 1:
            sim = spk_cent @ spk_cent.T
            pairs = [f"S{a + 1}-S{b + 1}={sim[a, b]:.2f}"
                     for a in range(len(keep)) for b in range(a + 1, len(keep))]
            logger.info("Speaker centroid similarity (values near 0.9+ suggest one voice split): "
                        + ", ".join(pairs))
        return labels, info

    @staticmethod
    def merge_similar(glab, cents, secs):
        """Repeatedly merge the two most similar groups while similarity >= MERGE_SIM."""
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

    @staticmethod
    def fill_unlabelled(segments, labels):
        """Segments too short to embed take the label of the closest labelled neighbour."""
        known = np.where(labels >= 0)[0]
        if len(known) == 0:
            return np.zeros(len(labels), dtype=int)
        out = labels.copy()
        starts = np.array([s["start"] for s in segments])
        ends = np.array([s["end"] for s in segments])
        for i in np.where(labels < 0)[0]:
            gaps = np.maximum(starts[known] - ends[i], starts[i] - ends[known])
            out[i] = labels[known[np.argmin(np.abs(gaps))]]
        return out

    # --------------------------------------------------------------- output
    @staticmethod
    def format_timestamp(seconds):
        total = int(timedelta(seconds=float(seconds)).total_seconds())
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def build_turns(self, segments, labels):
        order = {}
        for lab in labels:                 # Speaker 1 = whoever talks first
            order.setdefault(lab, len(order))
        turns = []
        for seg, lab in zip(segments, labels):
            name = f"Speaker {order[lab] + 1}"
            if turns and turns[-1]["speaker"] == name:
                turns[-1]["words"] += " " + seg["text"]
            else:
                turns.append({"speaker": name, "timestamp": seg["start"], "words": seg["text"]})
        for t in turns:
            t["timestamp"] = self.format_timestamp(t["timestamp"])
        return turns, order

    def process_file(self, audio_path):
        logger.info(f"--- Processing: {audio_path.name} ---")
        key = self.cache_key(audio_path)

        # STEP 1: decode once (16 kHz mono float32), shared by both models
        audio = whisper.load_audio(str(audio_path))
        total_sec = len(audio) / SAMPLE_RATE
        logger.info(f"Duration: {total_sec / 60:.1f} min")

        # STEP 2: Whisper transcription (seeded, cached)
        segments = self.transcribe(audio, key)
        if not segments:
            logger.warning(f"No speech found in {audio_path.name}")
            return

        # STEP 3: SpeechBrain voiceprints per Whisper segment (cached)
        emb_idx, emb = self.embed_segments(audio, segments, key)
        del audio

        # STEP 4: chunked clustering + cross-chunk linking
        labels, info = self.diarize(segments, emb_idx, emb, total_sec)
        labels = self.fill_unlabelled(segments, labels)

        # STEP 5: collapse consecutive turns and save
        turns, order = self.build_turns(segments, labels)
        output_file = self.output_dir / f"{audio_path.stem}{OUTPUT_SUFFIX}.csv"
        pd.DataFrame(turns, columns=["speaker", "timestamp", "words"]).to_csv(
            output_file, index=False, quoting=csv.QUOTE_MINIMAL)

        if DEBUG_SEGMENTS:
            pd.DataFrame({
                "start": [round(s["start"], 2) for s in segments],
                "end": [round(s["end"], 2) for s in segments],
                "speaker": [f"Speaker {order[l] + 1}" for l in labels],
                "chunk": info["chunk"], "chunk_cluster": info["local"],
                "anchored": info["core"], "text": [s["text"] for s in segments],
            }).to_csv(self.output_dir / f"{audio_path.stem}{OUTPUT_SUFFIX}_segments.csv", index=False)

        logger.info(f"Done! Saved to {output_file.name}\n")

    def run(self):
        files = []
        for ext in [".mp3", ".wav", ".m4a", ".flac"]:
            files.extend(self.input_dir.glob(f"*{ext}"))
        for f in sorted(files):
            try:
                self.process_file(f)
            except Exception as e:
                logger.exception(f"Failed {f.name}: {e}")


if __name__ == "__main__":
    WhisperBiometricTranscriber().run()