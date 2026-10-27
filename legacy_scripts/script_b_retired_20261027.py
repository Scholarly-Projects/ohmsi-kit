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
NUM_SPEAKERS = 3
DISTANCE_THRESHOLD = 0.65
WHISPER_MODEL = "medium.en"
INPUT_DIR = "A"
OUTPUT_DIR = "B"
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
        k = min(self.num_speakers, n) if self.num_speakers else None
        clusterer = AgglomerativeClustering(
            n_clusters=k, 
            distance_threshold=self.distance_threshold if not k else None,
            metric='cosine', 
            linkage='average'
        )
        return clusterer.fit_predict(embeddings)

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
        idx_to_label = {idx: label for idx, label in zip(valid_indices, speaker_labels)}

        # STEP 4: Build Raw List with Inheritance (Lowercase Keys)
        raw_list = []
        last_spk, last_end = "Unknown", 0.0
        
        for i, seg in enumerate(valid_segments):
            if i in idx_to_label:
                spk = f"Speaker {idx_to_label[i] + 1}"
                last_spk = spk
            else:
                spk = last_spk if (seg['start'] - last_end) <= 1.5 else "Unknown"
            
            # Key names here define the CSV headers
            raw_list.append({"speaker": spk, "timestamp": seg['start'], "words": seg['text']})
            last_end = seg['end']

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
        output_file = self.output_dir / f"{audio_path.stem}_script_b.csv"
        
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