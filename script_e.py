"""
script_f.py - last-resort tier: pause-based turns, no voice biometrics.
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
import whisper

# =============================================================================
# USER CONFIGURATION
# =============================================================================
WHISPER_MODEL = "medium"
INPUT_DIR = "A"
OUTPUT_DIR = "B"
OUTPUT_SUFFIX = "_script_e"
SKIP_EXISTING = False

# --- Whisper (keep identical to script_a.py to share its transcript cache) ---
SEED = 1234
BEAM_SIZE = None

# --- Turns ---
NUM_SPEAKER_LABELS = 3      
PAUSE_THRESHOLD_SECONDS = 2.0
SWITCH_MODE = "cues"        # "cues" or "every_pause" (original script_f behaviour)
ALWAYS_SWITCH_SEC = None    # In "cues" mode, also flip on pauses at least this long (e.g. 6.0)
QUESTION_BREAK_SEC = 0.4    # In "cues" mode, a "?" followed by this much pause also starts a row
                            # (answers often follow questions faster than PAUSE_THRESHOLD)
ANSWER_OPENERS = {"yes", "yeah", "no", "well", "oh", "uh-huh", "mm-hmm", "um", "uh",
                  "sure", "right"}  # first-word cues
QUESTION_STARTS = {"what", "when", "where", "why", "how", "who", "did", "do", "does",
                   "was", "were", "is", "are", "can", "could", "would", "have", "had"}

# --- Optional hallucination check (needs silero-vad) ---
USE_VAD_CHECK = True
VAD_THRESHOLD = 0.4
MIN_VAD_COVERAGE = 0.2
HALLUCINATIONS = "flag"     # "flag" = prefix with [?], "drop" = remove, "keep"

# --- Housekeeping ---
CACHE = True
SAMPLE_RATE = 16000
# =============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from silero_vad import load_silero_vad, get_speech_timestamps
except ImportError:
    if USE_VAD_CHECK:
        logger.warning("silero-vad not installed; skipping the hallucination check")
    USE_VAD_CHECK = False


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def first_word(text):
    return re.sub(r"[^\w'-]", "", text.split()[0].lower()) if text.split() else ""


class PauseHeuristicTranscriber:
    def __init__(self, input_dir=INPUT_DIR, output_dir=OUTPUT_DIR, whisper_model=WHISPER_MODEL):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.cache_dir = self.output_dir / "_cache"
        if CACHE:
            self.cache_dir.mkdir(exist_ok=True)
        self.model_name = whisper_model
        self.n_labels = max(1, NUM_SPEAKER_LABELS)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.whisper_model = None          # loaded only if a transcript isn't cached
        self.vad_model = load_silero_vad() if USE_VAD_CHECK else None

    # ----------------------------------------------------------------- cache
    def cache_key(self, audio_path):
        """Identical to script_a.py so the transcript cache is shared."""
        st = audio_path.stat()
        settings = dict(file=audio_path.name, size=st.st_size, mtime=int(st.st_mtime),
                        model=self.model_name, seed=SEED, beam=BEAM_SIZE,
                        whisper=getattr(whisper, "__version__", "?"))
        digest = hashlib.sha1(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:10]
        return f"{audio_path.stem}.{self.model_name}.{digest}"

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

    def vad_coverage(self, audio, key):
        cache_file = self.cache_dir / f"{key}.vadf_{VAD_THRESHOLD}.json"
        if CACHE and cache_file.exists():
            regions = json.loads(cache_file.read_text())
        else:
            logger.info("Running Silero VAD (hallucination check)...")
            ts = get_speech_timestamps(torch.from_numpy(audio), self.vad_model,
                                       sampling_rate=SAMPLE_RATE, threshold=VAD_THRESHOLD,
                                       speech_pad_ms=100)
            regions = [[t["start"] / SAMPLE_RATE, t["end"] / SAMPLE_RATE] for t in ts]
            if CACHE:
                cache_file.write_text(json.dumps(regions))
        s = np.array([r[0] for r in regions]) if regions else np.zeros(0)
        e = np.array([r[1] for r in regions]) if regions else np.zeros(0)

        def cover(a, b):
            if b <= a or len(s) == 0:
                return 0.0
            lo, hi = np.searchsorted(e, a), np.searchsorted(s, b)
            ov = np.clip(np.minimum(e[lo:hi], b) - np.maximum(s[lo:hi], a), 0, None)
            return float(ov.sum() / (b - a))
        return cover

    # ----------------------------------------------------------------- turns
    @staticmethod
    def format_timestamp(seconds):
        total = int(timedelta(seconds=float(seconds)).total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def switch_reason(prev_text, text, gap):
        prev_text = prev_text.rstrip()
        if prev_text.endswith("?"):
            return "after question"
        fw = first_word(text)
        if fw in ANSWER_OPENERS and len(prev_text.split()) <= 25 and prev_text.split() \
                and first_word(prev_text) in QUESTION_STARTS:
            return "answer after question-like line"
        if fw in {"yes", "yeah", "no", "uh-huh", "mm-hmm", "oh", "well"}:
            return "answer-like opening"
        if ALWAYS_SWITCH_SEC and gap >= ALWAYS_SWITCH_SEC:
            return f"pause >= {ALWAYS_SWITCH_SEC:g}s"
        return ""

    def process_file(self, audio_path):
        out_file = self.output_dir / f"{audio_path.stem}{OUTPUT_SUFFIX}.csv"
        if SKIP_EXISTING and out_file.exists():
            logger.info(f"Skipping {audio_path.name} (output exists)")
            return
        logger.info(f"--- Processing: {audio_path.name} ---")
        key = self.cache_key(audio_path)
        audio = whisper.load_audio(str(audio_path))

        segments = self.transcribe(audio, key)
        words = [w for s in segments for w in s.get("words", [])]
        if not words:
            logger.warning("No words recognized; skipping file.")
            return
        cover = self.vad_coverage(audio, key) if USE_VAD_CHECK else None
        del audio

        # 1. split into rows at pauses
        rows, cur = [], [words[0]]
        gaps = [0.0]
        for prev, w in zip(words[:-1], words[1:]):
            gap = w[0] - prev[1]
            question_break = (SWITCH_MODE == "cues" and prev[2].endswith("?")
                              and gap >= QUESTION_BREAK_SEC)
            if gap > PAUSE_THRESHOLD_SECONDS or question_break:
                rows.append(cur)
                cur = []
                gaps.append(round(gap, 2))
            cur.append(w)
        rows.append(cur)

        # 2. hallucination check per row
        texts = [" ".join(w[2] for w in r) for r in rows]
        suspect = [False] * len(rows)
        if cover is not None:
            suspect = [cover(r[0][0], r[-1][1]) < MIN_VAD_COVERAGE for r in rows]
            n = sum(suspect)
            if n:
                logger.info(f"{n} row(s) fall outside detected speech ({HALLUCINATIONS})")
        keep = [i for i in range(len(rows)) if not (suspect[i] and HALLUCINATIONS == "drop")]

        # 3. assign labels
        out, label, prev_text = [], 0, None
        for n_kept, i in enumerate(keep):
            reason = ""
            if n_kept > 0:
                if SWITCH_MODE == "every_pause":
                    reason = "pause"
                    label = (label + 1) % self.n_labels
                elif self.n_labels == 2:
                    # Roles, not toggling: the asker is Speaker 1, whoever answers is
                    # Speaker 2. Each question re-anchors the labels, so one missed turn
                    # doesn't leave every later row out of step.
                    new = label
                    if texts[i].rstrip().endswith("?"):
                        new, reason = 0, "asks a question"
                    elif prev_text.rstrip().endswith("?"):
                        new, reason = 1, "after question"
                    else:
                        r = self.switch_reason(prev_text, texts[i], gaps[i])
                        if r:
                            new, reason = 1 - label, r
                    if new == label:
                        reason = ""
                    label = new
                else:
                    reason = self.switch_reason(prev_text, texts[i], gaps[i])
                    if reason:
                        label = (label + 1) % self.n_labels
            elif SWITCH_MODE == "cues" and self.n_labels == 2:
                label = 0 if texts[i].rstrip().endswith("?") else 1
            text = f"[?] {texts[i]}" if suspect[i] and HALLUCINATIONS == "flag" else texts[i]
            out.append({"speaker": f"Speaker {label + 1}",
                        "timestamp": self.format_timestamp(rows[i][0][0]),
                        "words": text, "preceding_pause_sec": gaps[i], "switch_reason": reason})
            prev_text = texts[i]

        pd.DataFrame(out).to_csv(out_file, index=False, quoting=csv.QUOTE_MINIMAL)
        flips = sum(1 for r in out if r["switch_reason"])
        logger.info(f"{len(out)} rows, {flips} label changes ({SWITCH_MODE})")
        logger.info(f"Done! Saved to {out_file.name} (heuristic turns, not verified speakers)\n")

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
    PauseHeuristicTranscriber().run()