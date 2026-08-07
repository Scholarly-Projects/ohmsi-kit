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
from sklearn.cluster import SpectralClustering
from sklearn.metrics.pairwise import cosine_similarity

# =============================================================================
# USER CONFIGURATION
# =============================================================================
NUM_SPEAKERS = 2
WHISPER_MODEL = "medium"
INPUT_DIR = "A"
OUTPUT_DIR = "B"
PAUSE_THRESHOLD = 10  # Seconds of silence to trigger a speaker break
# =============================================================================

# Patch torchaudio for older versions
if not hasattr(torchaudio, "list_audio_backends"):
    torchaudio.list_audio_backends = lambda: ["ffmpeg"]

# =============================================================================
# IMPORTS WITH PROPER ERROR HANDLING
# =============================================================================
try:
    from speechbrain.inference.classifiers import EncoderClassifier
    import soundfile
    import silero_vad
except ImportError as e:
    print(f"Error: Import failed - {e}")
    print("Run: pip install speechbrain==1.0.3 soundfile>=0.12.0 silero-vad")
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
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.num_speakers = num_speakers

        # Device Detection
        if torch.cuda.is_available():
            self.sb_device = "cuda"
            self.whisper_device = "cuda"
        elif torch.backends.mps.is_available():
            self.sb_device = "cpu"
            self.whisper_device = "cpu"
        else:
            self.sb_device = "cpu"
            self.whisper_device = "cpu"
        
        logger.info(f"SpeechBrain on {self.sb_device.upper()}, Whisper on {self.whisper_device.upper()}...")

        # 1. Load Speaker Encoder
        logger.info("Loading SpeechBrain biometric model (ECAPA-TDNN)...")
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": self.sb_device}
        )

        # 2. Load Silero VAD
        logger.info("Loading Silero VAD model...")
        self.silero_model, self.silero_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        (self.get_speech_timestamps, _, _, _, _) = self.silero_utils

        # 3. Load Whisper
        logger.info(f"Loading Whisper '{whisper_model}'...")
        self.whisper_model = whisper.load_model(whisper_model, device=self.whisper_device)

    def preprocess_audio(self, audio_path):
        wav, sr = torchaudio.load(audio_path)
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            wav = resampler(wav)
        return wav.squeeze()

    def get_vad_segments(self, wav):
        speech_timestamps = self.get_speech_timestamps(
            wav,
            self.silero_model,
            sampling_rate=16000,
            min_speech_duration_ms=500,
            min_silence_duration_ms=300,
            speech_pad_ms=100
        )
        
        if not speech_timestamps:
            return np.empty((0, 2))
        
        segments = [[ts['start'] / 16000, ts['end'] / 16000] for ts in speech_timestamps]
        return np.array(segments)

    def cluster_speakers_spectral(self, embeddings):
        if len(embeddings) < 2:
            return [0] * len(embeddings)
        
        sim_matrix = cosine_similarity(embeddings)
        clusterer = SpectralClustering(n_clusters=self.num_speakers, affinity='precomputed', assign_labels='kmeans', random_state=42)
        
        try:
            return clusterer.fit_predict(sim_matrix)
        except Exception as e:
            logger.warning(f"Spectral clustering failed ({e}), falling back to Agglomerative.")
            from sklearn.cluster import AgglomerativeClustering
            clusterer = AgglomerativeClustering(n_clusters=self.num_speakers, metric='cosine', linkage='average')
            return clusterer.fit_predict(embeddings)

    @staticmethod
    def format_timestamp(seconds):
        td = timedelta(seconds=float(seconds))
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def build_heuristic_sentences(self, whisper_segments):
        """Extracts words and groups them into logical sentences based on pauses and punctuation."""
        all_words = []
        for segment in whisper_segments:
            if "words" in segment:
                for w in segment["words"]:
                    all_words.append({"word": w["word"].strip(), "start": w["start"], "end": w["end"]})
            else:
                all_words.append({"word": segment["text"].strip(), "start": segment["start"], "end": segment["end"]})

        sentences = []
        current_sentence_words = []
        sentence_start = None
        last_word_end = None

        for w_info in all_words:
            word_text, word_start, word_end = w_info["word"], w_info["start"], w_info["end"]
            if not word_text:
                continue

            # Pause detection
            if last_word_end is not None and (word_start - last_word_end) > PAUSE_THRESHOLD:
                if current_sentence_words:
                    sentences.append({
                        "text": " ".join(current_sentence_words),
                        "start": sentence_start,
                        "end": last_word_end,
                        "is_question": " ".join(current_sentence_words).endswith('?')
                    })
                    current_sentence_words = []
                    sentence_start = word_start

            if not current_sentence_words:
                sentence_start = word_start
                
            current_sentence_words.append(word_text)
            last_word_end = word_end

            # Punctuation detection
            if word_text.endswith('.') or word_text.endswith('?') or word_text.endswith('!'):
                sentences.append({
                    "text": " ".join(current_sentence_words),
                    "start": sentence_start,
                    "end": word_end,
                    "is_question": " ".join(current_sentence_words).endswith('?')
                })
                current_sentence_words = []
                sentence_start = None

        if current_sentence_words:
            sentences.append({
                "text": " ".join(current_sentence_words),
                "start": sentence_start if sentence_start is not None else last_word_end,
                "end": last_word_end,
                "is_question": " ".join(current_sentence_words).endswith('?')
            })

        return sentences

    def map_sentences_to_speakers(self, sentences, vad_boundaries, speaker_labels):
        """Maps biometric speakers to fine-grained heuristic sentences."""
        vad_map = [{'start': float(b[0]), 'end': float(b[1]), 'speaker': speaker_labels[i]} 
                   for i, b in enumerate(vad_boundaries)]

        assigned_sentences = []
        for s in sentences:
            best_match = None
            max_overlap = 0
            
            # Biometric matching
            for v in vad_map:
                overlap = max(0, min(s['end'], v['end']) - max(s['start'], v['start']))
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_match = v['speaker']
            
            # Combine Biometrics with Heuristics
            if s["is_question"]:
                # Override: Treat direct questions as the interviewer, unless you want pure biometrics
                assigned_speaker = "Interviewer"
            else:
                spk_id = best_match if best_match is not None else 0
                assigned_speaker = f"Speaker {spk_id + 1}"
                
            s['speaker'] = assigned_speaker
            assigned_sentences.append(s)
            
        return assigned_sentences

    def process_file(self, audio_path):
        logger.info(f"--- Processing: {audio_path.name} ---")

        audio_16k = self.preprocess_audio(audio_path)
        
        logger.info("Running VAD to identify speech regions...")
        vad_boundaries = self.get_vad_segments(audio_16k)
        if len(vad_boundaries) == 0: return

        logger.info("Extracting speaker embeddings...")
        embeddings = []
        valid_vad_indices = []

        for i, bounds in enumerate(vad_boundaries):
            chunk = audio_16k[int(bounds[0] * 16000):int(bounds[1] * 16000)]
            if len(chunk) < 16000: continue
            
            with torch.no_grad():
                embeddings.append(self.encoder.encode_batch(chunk.unsqueeze(0)).squeeze().cpu().numpy())
                valid_vad_indices.append(i)

        if not embeddings: return

        logger.info("Clustering speakers...")
        speaker_labels = self.cluster_speakers_spectral(np.array(embeddings))
        
        logger.info("Transcribing with Whisper (Word-level timestamps active)...")
        transcript = self.whisper_model.transcribe(str(audio_path), word_timestamps=True)

        logger.info("Applying heuristic segmentation and biometric mapping...")
        sentences = self.build_heuristic_sentences(transcript['segments'])
        valid_vad_bounds = vad_boundaries[valid_vad_indices]
        mapped_sentences = self.map_sentences_to_speakers(sentences, valid_vad_bounds, speaker_labels)

        # Collapse Consecutive Speakers
        collapsed = []
        if mapped_sentences:
            curr = mapped_sentences[0].copy()
            for next_seg in mapped_sentences[1:]:
                # Force break if the speaker changes OR if there's a long pause
                pause = next_seg['start'] - curr['end']
                
                if next_seg['speaker'] == curr['speaker'] and pause <= PAUSE_THRESHOLD:
                    curr['text'] += " " + next_seg['text']
                    curr['end'] = next_seg['end']
                else:
                    collapsed.append({
                        "speaker": curr['speaker'],
                        "timestamp": self.format_timestamp(curr['start']),
                        "words": curr['text']
                    })
                    curr = next_seg.copy()
            
            collapsed.append({
                "speaker": curr['speaker'],
                "timestamp": self.format_timestamp(curr['start']),
                "words": curr['text']
            })

        output_file = self.output_dir / f"{audio_path.stem}_script_e.csv"
        pd.DataFrame(collapsed).to_csv(output_file, index=False, quoting=csv.QUOTE_MINIMAL)
        logger.info(f"Done! Saved to {output_file.name}\n")

    def run(self):
        files = [
            f for ext in [".mp3", ".MP3", ".wav", ".m4a", ".flac"]
            for f in self.input_dir.glob(f"*{ext}")
        ]
        if not files:
            logger.warning(f"No audio files found in {self.input_dir}")
            return

        pending, skipped = [], []
        for f in files:
            expected_csv = self.output_dir / f"{f.stem}_script_e.csv"
            if expected_csv.exists():
                skipped.append(f.name)
            else:
                pending.append(f)

        if skipped:
            logger.info(
                f"Skipping {len(skipped)} already-transcribed file(s): {', '.join(skipped)}"
            )
        logger.info(f"{len(pending)} file(s) queued for processing.")

        for f in pending:
            try:
                self.process_file(f)
            except Exception as e:
                logger.error(f"Failed {f.name}: {e}", exc_info=True)

if __name__ == "__main__":
    WhisperBiometricTranscriber().run()