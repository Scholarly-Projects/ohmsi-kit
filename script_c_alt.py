import sys
import random
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
NUM_SPEAKERS = 3            # Max clusters. Tiny clusters are folded into the
                            # nearest big one (MIN_CLUSTER_SHARE). Use 2 for strict
                            # two-person interviews, or None to use DISTANCE_THRESHOLD.
DISTANCE_THRESHOLD = 0.65   # Only used when NUM_SPEAKERS is None (may need retuning:
                            # window embeddings behave differently from segment ones).
WHISPER_MODEL = "large-v2"
INPUT_DIR = "A"
OUTPUT_DIR = "B"

# --- Reproducibility / diarization settings ---
SEED = 1234                 # Fixed RNG seed, re-applied before every file
WINDOW_SEC = 1.5            # Length of each speaker-embedding window
HOP_SEC = 0.75              # Step between windows (50% overlap)
MIN_SPEECH_FRACTION = 0.5   # Window must be at least this much covered by words
MIN_CLUSTER_SHARE = 0.03    # Clusters smaller than this share of windows get merged
EMBED_BATCH = 32            # Windows per SpeechBrain forward pass
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
        self.num_speakers = num_speakers
        self.distance_threshold = distance_threshold

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing on {self.device.upper()}...")

        logger.info("Loading SpeechBrain biometric model (ECAPA-TDNN)...")
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": self.device}
        )
        self.encoder.eval()

        logger.info(f"Loading Whisper '{whisper_model}'...")
        self.whisper_model = whisper.load_model(whisper_model, device=self.device)

    # ------------------------------------------------------------------ audio
    def preprocess_audio(self, audio_path):
        wav, sr = torchaudio.load(audio_path)
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        if sr != SAMPLE_RATE:
            wav = torchaudio.transforms.Resample(sr, SAMPLE_RATE)(wav)
        return wav.squeeze()

    # ------------------------------------------------------------- whisper
    def transcribe(self, audio_path):
        # Deterministic decoding:
        #  - temperature=0.0 disables Whisper's random-sampling fallback
        #  - condition_on_previous_text=False stops one odd window from
        #    cascading into every later window (and curbs repetition loops)
        set_seed(SEED)
        return self.whisper_model.transcribe(
            str(audio_path),
            word_timestamps=True,
            temperature=0.0,
            condition_on_previous_text=False,
            fp16=(self.device == "cuda"),
        )

    @staticmethod
    def extract_words(transcript):
        """Flatten Whisper output into a list of timed words."""
        words = []
        for seg in transcript["segments"]:
            seg_words = seg.get("words") or []
            if seg_words:
                for w in seg_words:
                    if w["word"].strip():
                        words.append({"start": float(w["start"]),
                                      "end": float(w["end"]),
                                      "text": w["word"]})
            elif seg.get("text", "").strip():
                words.append({"start": float(seg["start"]),
                              "end": float(seg["end"]),
                              "text": " " + seg["text"].strip()})
        return words

    # ---------------------------------------------------------- diarization
    def window_embeddings(self, audio, words):
        """Embed fixed-length windows that contain speech.

        Diarization no longer depends on how Whisper happened to split the
        audio, so a segment holding both voices can't blur an embedding.
        """
        win = int(WINDOW_SEC * SAMPLE_RATE)
        hop = int(HOP_SEC * SAMPLE_RATE)
        n = audio.shape[0]
        if n < win:
            return np.empty(0), np.empty((0, 192))

        fps = 100  # speech mask resolution: 10 ms
        mask = np.zeros(int(np.ceil(n / SAMPLE_RATE * fps)) + 1, dtype=bool)
        for w in words:
            mask[int(w["start"] * fps):int(np.ceil(w["end"] * fps))] = True

        starts = [
            s for s in range(0, n - win + 1, hop)
            if mask[s * fps // SAMPLE_RATE:(s + win) * fps // SAMPLE_RATE].mean() >= MIN_SPEECH_FRACTION
        ]
        if not starts:
            return np.empty(0), np.empty((0, 192))

        chunks = []
        with torch.no_grad():
            for i in range(0, len(starts), EMBED_BATCH):
                batch = torch.stack([audio[s:s + win] for s in starts[i:i + EMBED_BATCH]]).to(self.device)
                chunks.append(self.encoder.encode_batch(batch).squeeze(1).cpu().numpy())
        emb = np.concatenate(chunks)
        emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
        return np.array(starts) / SAMPLE_RATE, emb

    def cluster_speakers(self, emb):
        n = len(emb)
        if n < 2:
            return np.zeros(n, dtype=int)

        if self.num_speakers:
            clusterer = AgglomerativeClustering(
                n_clusters=min(self.num_speakers, n), metric="cosine", linkage="average")
        else:
            clusterer = AgglomerativeClustering(
                n_clusters=None, distance_threshold=self.distance_threshold,
                metric="cosine", linkage="average")
        labels = clusterer.fit_predict(emb)

        # Fold tiny clusters (coughs, tape noise, stray words) into the
        # nearest substantial speaker instead of letting them take a slot.
        counts = np.bincount(labels)
        major = np.where(counts >= MIN_CLUSTER_SHARE * n)[0]
        if len(major) == 0:
            major = np.array([counts.argmax()])
        centroids = np.stack([emb[labels == c].mean(axis=0) for c in major])
        centroids /= np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-9
        minor = ~np.isin(labels, major)
        if minor.any():
            labels[minor] = major[(emb[minor] @ centroids.T).argmax(axis=1)]

        # Number speakers by order of first appearance, so "Speaker 1" is
        # always whoever talks first (usually the interviewer).
        order = {}
        for lab in labels:
            order.setdefault(lab, len(order))
        return np.array([order[lab] for lab in labels])

    @staticmethod
    def assign_words(words, starts, labels):
        """Give each word the speaker of the windows it overlaps most."""
        if len(starts) == 0:
            return [0] * len(words)
        ends = starts + WINDOW_SEC
        centres = starts + WINDOW_SEC / 2
        n_spk = int(labels.max()) + 1
        out = []
        for w in words:
            overlap = np.minimum(ends, w["end"]) - np.maximum(starts, w["start"])
            hit = overlap > 0
            if hit.any():
                votes = np.bincount(labels[hit], weights=overlap[hit], minlength=n_spk)
                out.append(int(votes.argmax()))
            else:
                mid = (w["start"] + w["end"]) / 2
                out.append(int(labels[np.abs(centres - mid).argmin()]))
        return out

    # --------------------------------------------------------------- output
    @staticmethod
    def format_timestamp(seconds):
        total = int(timedelta(seconds=float(seconds)).total_seconds())
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def build_turns(self, words, word_speakers):
        turns = []
        for w, spk in zip(words, word_speakers):
            name = f"Speaker {spk + 1}"
            if turns and turns[-1]["speaker"] == name:
                turns[-1]["words"] += w["text"]
            else:
                turns.append({"speaker": name, "timestamp": w["start"], "words": w["text"]})
        for t in turns:
            t["timestamp"] = self.format_timestamp(t["timestamp"])
            t["words"] = " ".join(t["words"].split())
        return turns

    def process_file(self, audio_path):
        logger.info(f"--- Processing: {audio_path.name} ---")

        # STEP 1: Whisper transcription (deterministic)
        words = self.extract_words(self.transcribe(audio_path))
        if not words:
            logger.warning(f"No speech found in {audio_path.name}")
            return

        # STEP 2: Speaker embeddings on fixed windows
        audio_16k = self.preprocess_audio(audio_path)
        starts, emb = self.window_embeddings(audio_16k, words)

        # STEP 3: Clustering
        labels = self.cluster_speakers(emb) if len(emb) else np.empty(0, dtype=int)
        logger.info(f"Embedded {len(emb)} windows -> {len(set(labels.tolist())) or 1} speaker(s)")

        # STEP 4: Words -> speakers -> turns
        turns = self.build_turns(words, self.assign_words(words, starts, labels))

        # STEP 5: Save
        output_file = self.output_dir / f"{audio_path.stem}_script_c_alt.csv"
        pd.DataFrame(turns, columns=["speaker", "timestamp", "words"]).to_csv(
            output_file, index=False, quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Done! Saved to {output_file.name}\n")

    def run(self):
        files = []
        for ext in [".mp3", ".wav", ".m4a", ".flac"]:
            files.extend(self.input_dir.glob(f"*{ext}"))
        for f in sorted(files):
            try:
                self.process_file(f)
            except Exception as e:
                logger.error(f"Failed {f.name}: {e}")


if __name__ == "__main__":
    WhisperBiometricTranscriber().run()