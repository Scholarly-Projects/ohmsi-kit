import os
import sys
import logging
import torch
import torchaudio
import whisper
import pandas as pd
import csv
from pathlib import Path
from datetime import timedelta

# =============================================================================
# USER CONFIGURATION
# =============================================================================
WHISPER_MODEL = "medium"
INPUT_DIR = "A"
OUTPUT_DIR = "B"

NUM_SPEAKER_LABELS = 1           # Cycle through this many "Speaker N" labels.
PAUSE_THRESHOLD_SECONDS = 2.0    # A gap at least this long is treated as a
                                  # likely turn change.
# =============================================================================

if not hasattr(torchaudio, "list_audio_backends"):
    torchaudio.list_audio_backends = lambda: ["ffmpeg"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WhisperPauseHeuristicTranscriber:
    """
    Tier-3 / last-resort remediation pipeline.

    No speaker-embedding or diarization model is used here at all -- this tier
    is for recordings where neither a human nor a voice-biometric model could
    reliably tell speakers apart (severe overlap, single mixed-down channel,
    extreme degradation, etc.). Rather than *identifying* speakers, this script
    only detects likely turn boundaries from pauses in Whisper's word-level
    timestamps, and cycles labels across them round-robin.

    IMPORTANT: the "speaker" column is a guess about *when turns changed*, not
    a verified identity. Treat it as "probable turn N", spot-check it, and
    prefer script_c / script_s upstream of this whenever they can produce
    usable output -- this tier trades identity accuracy for the ability to
    recover *any* structure and text at all.
    """

    def __init__(
        self,
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
        whisper_model=WHISPER_MODEL,
        num_speaker_labels=NUM_SPEAKER_LABELS,
        pause_threshold=PAUSE_THRESHOLD_SECONDS,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.num_speaker_labels = max(1, num_speaker_labels)
        self.pause_threshold = pause_threshold

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing on {self.device.upper()}...")

        logger.info(f"Loading Whisper '{whisper_model}'...")
        self.whisper_model = whisper.load_model(whisper_model, device=self.device)

    @staticmethod
    def format_timestamp(seconds):
        """Formats seconds into HH:MM:SS (Removed MS for clarity)."""
        td = timedelta(seconds=float(seconds))
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def process_file(self, audio_path):
        logger.info(f"--- Processing: {audio_path.name} ---")

        # STEP 1: Whisper transcription with word-level timestamps.
        # Word-level (rather than segment-level) granularity catches pauses that
        # fall inside a single Whisper segment -- common on rough audio, where
        # Whisper tends to lump multiple utterances into one segment.
        transcript = self.whisper_model.transcribe(str(audio_path), word_timestamps=True)

        words = []
        for seg in transcript['segments']:
            for w in seg.get('words', []):
                text = w.get('word', '').strip()
                if text:
                    words.append({"start": w['start'], "end": w['end'], "word": text})

        if not words:
            logger.warning("No words recognized; skipping file.")
            return

        # STEP 2: Split into turns wherever the pause exceeds the threshold,
        # cycling through NUM_SPEAKER_LABELS labels round-robin.
        turns = []
        speaker_idx = 0
        curr = {
            "speaker": f"Speaker {speaker_idx + 1}",
            "timestamp": words[0]['start'],
            "words": words[0]['word'],
            "preceding_pause_sec": 0.0,
        }
        last_end = words[0]['end']

        for w in words[1:]:
            gap = w['start'] - last_end
            if gap > self.pause_threshold:
                turns.append(curr)
                speaker_idx = (speaker_idx + 1) % self.num_speaker_labels
                curr = {
                    "speaker": f"Speaker {speaker_idx + 1}",
                    "timestamp": w['start'],
                    "words": w['word'],
                    "preceding_pause_sec": round(gap, 2),
                }
            else:
                curr["words"] += " " + w['word']
            last_end = w['end']
        turns.append(curr)

        # STEP 3: Format timestamps and save
        for t in turns:
            t['timestamp'] = self.format_timestamp(t['timestamp'])

        output_df = pd.DataFrame(turns)
        output_file = self.output_dir / f"{audio_path.stem}_script_f.csv"
        output_df.to_csv(output_file, index=False, quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Done! Saved to {output_file.name} (heuristic pause-based turns only)\n")

    def run(self):
        files = []
        for ext in [".mp3", ".wav", ".m4a", ".flac"]:
            files.extend(list(self.input_dir.glob(f"*{ext}")))
        for f in files:
            try:
                self.process_file(f)
            except Exception as e:
                logger.error(f"Failed {f.name}: {e}")


if __name__ == "__main__":
    WhisperPauseHeuristicTranscriber().run()
    