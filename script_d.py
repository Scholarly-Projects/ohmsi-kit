import os
import sys
import logging
import torch
import torchaudio
import whisper
import pandas as pd
import numpy as np
import csv
from pathlib import Path
from datetime import timedelta
from sklearn.cluster import AgglomerativeClustering

# =============================================================================
# USER CONFIGURATION
# =============================================================================
NUM_SPEAKERS = 2
DISTANCE_THRESHOLD = 0.65
WHISPER_MODEL = "medium"
SPEECHBRAIN_MODEL = "speechbrain/spkrec-ecapa-voxceleb"
INPUT_DIR = "A"
OUTPUT_DIR = "B"

# Enable or disable the interjection reallocation logic
USE_INTERJECTIONS = True

# Words to strip from the end of a line and move to the beginning of the next line.
# Add or remove words in lowercase as needed (punctuation is automatically ignored).
INTERJECTIONS = {"yeah", "yes", "sure", "right", "yep", "nope", "no", "uh huh", "hmm", "mhm", "okay", "ok"}
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

class WhisperBiometricTranscriber:
    def __init__(
        self,
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
        whisper_model=WHISPER_MODEL,
        sb_model=SPEECHBRAIN_MODEL,
        num_speakers=NUM_SPEAKERS,
        distance_threshold=DISTANCE_THRESHOLD,
        use_interjections=USE_INTERJECTIONS,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.num_speakers = num_speakers
        self.distance_threshold = distance_threshold
        self.use_interjections = use_interjections

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing on {self.device.upper()}...")

        logger.info(f"Loading SpeechBrain biometric model ({sb_model})...")
        self.encoder = EncoderClassifier.from_hparams(
            source=sb_model,
            run_opts={"device": self.device}
        )

        logger.info(f"Loading Whisper '{whisper_model}'...")
        self.whisper_model = whisper.load_model(whisper_model, device=self.device)

    def preprocess_audio(self, audio_path):
        wav, sr = torchaudio.load(audio_path)
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            wav = resampler(wav)
        return wav.squeeze()

    def cluster_speakers(self, embeddings):
        n = len(embeddings)
        cap = min(self.num_speakers + 3, n)

        # First pass: let distance_threshold discover how many distinct
        # voices are naturally present, instead of assuming a fixed count.
        natural_clusterer = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            metric='cosine',
            linkage='average'
        )
        natural_labels = natural_clusterer.fit_predict(embeddings)
        natural_count = len(set(natural_labels))

        # If the recording naturally resolves to within the num_speakers+3
        # buffer, trust that result - it reflects the real audio rather than
        # an assumption. Otherwise, fall back to forcing the capped count so
        # a noisy recording doesn't fragment into dozens of tiny clusters.
        if natural_count <= cap:
            return natural_labels

        capped_clusterer = AgglomerativeClustering(
            n_clusters=cap,
            metric='cosine',
            linkage='average'
        )
        return capped_clusterer.fit_predict(embeddings)

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

        # STEP 1: Whisper Transcription
        transcript = self.whisper_model.transcribe(str(audio_path), word_timestamps=True)
        valid_segments = []
        for seg in transcript['segments']:
            text = seg.get('text', '').strip()
            if text:
                seg['text'] = text
                valid_segments.append(seg)

        if not valid_segments:
            return

        # STEP 2: Biometrics
        audio_16k = self.preprocess_audio(audio_path)
        embeddings, valid_indices = [], []

        for i, seg in enumerate(valid_segments):
            start_sample, end_sample = int(seg['start'] * 16000), int(seg['end'] * 16000)
            chunk = audio_16k[start_sample:end_sample]
            if len(chunk) < 8000: continue
            
            with torch.no_grad():
                emb = self.encoder.encode_batch(chunk.unsqueeze(0))
                embeddings.append(emb.squeeze().cpu().numpy())
                valid_indices.append(i)

        # STEP 3: Clustering & Initial Mapping
        speaker_labels = self.cluster_speakers(np.array(embeddings))
        
        # Map clusters to Speaker names, identifying outliers as Unknown Speaker
        label_counts = {}
        for lbl in speaker_labels:
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
            
        # Sort clusters by frequency (most speaking time = Primary Speakers)
        sorted_labels = sorted(label_counts.keys(), key=lambda x: label_counts[x], reverse=True)
        
        label_map = {}
        for i, lbl in enumerate(sorted_labels):
            if i < self.num_speakers:
                label_map[lbl] = f"Speaker {i + 1}"
            else:
                unknown_idx = i - self.num_speakers
                label_map[lbl] = "Unknown Speaker" if unknown_idx == 0 else f"Unknown Speaker {unknown_idx + 1}"

        idx_to_label = {idx: label_map[label] for idx, label in zip(valid_indices, speaker_labels)}

        # STEP 4: Build Raw List with Inheritance & Interjection Scanning
        raw_list = []
        last_spk, last_end = "Unknown", 0.0
        pending_affirmation = ""  # Holds the stripped word for the next line
        
        for i, seg in enumerate(valid_segments):
            text = seg['text']
            
            # Prepend any pending affirmation from the previous line
            if self.use_interjections and pending_affirmation:
                text = f"{pending_affirmation} {text}"
                pending_affirmation = ""
                
            # Scan the end of the text for trailing interjections (only if enabled)
            if self.use_interjections:
                words = text.split()
                if len(words) > 1 and words[-1].lower().strip(".,!?\"'") in INTERJECTIONS:
                    # Strip it off and save it for the next speaker's line
                    pending_affirmation = words[-1]
                    text = " ".join(words[:-1])
                elif len(words) == 1 and words[0].lower().strip(".,!?\"'") in INTERJECTIONS:
                    # If the segment is ONLY the interjection, just queue it and skip adding this segment
                    pending_affirmation = words[0]
                    continue
            
            if i in idx_to_label:
                spk = idx_to_label[i]
                last_spk = spk
            else:
                spk = last_spk if (seg['start'] - last_end) <= 1.5 else "Unknown"
            
            raw_list.append({"speaker": spk, "timestamp": seg['start'], "words": text})
            last_end = seg['end']

        # If the audio ends on a queued interjection, just tack it onto the final line
        if self.use_interjections and pending_affirmation and raw_list:
            raw_list[-1]['words'] += " " + pending_affirmation

        # STEP 5: COLLAPSE CONSECUTIVE SPEAKERS
        collapsed = []
        if raw_list:
            curr = raw_list[0].copy()
            for next_seg in raw_list[1:]:
                if next_seg['speaker'] == curr['speaker']:
                    curr['words'] += " " + next_seg['words']
                else:
                    curr['timestamp'] = self.format_timestamp(curr['timestamp'])
                    collapsed.append(curr)
                    curr = next_seg.copy()
            curr['timestamp'] = self.format_timestamp(curr['timestamp'])
            collapsed.append(curr)

        # STEP 6: Save Result
        output_df = pd.DataFrame(collapsed)
        output_file = self.output_dir / f"{audio_path.stem}_script_d.csv"
        
        output_df.to_csv(output_file, index=False, quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Done! Saved to {output_file.name}\n")

    def run(self):
        files = []
        for ext in [".mp3", ".wav", ".m4a", ".flac"]:
            files.extend(list(self.input_dir.glob(f"*{ext}")))
        for f in files:
            try: self.process_file(f)
            except Exception as e: logger.error(f"Failed {f.name}: {e}")

if __name__ == "__main__":
    WhisperBiometricTranscriber().run()