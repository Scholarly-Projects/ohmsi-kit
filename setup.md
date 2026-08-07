## setup

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip

pip install -r requirements.txt

### Whisper + Legacy Transcript Data (does not function with severely corrupted files like LCOH)

python script.py

### Whisper + Programmatic Speaker Diarization which looks for questions to separate speakers

python script_b.py

### Whisper + Speechbrain Speaker Diarization + programmatic speech clustering

python script_c.py

### Whisper + SpeechBrain and Solera VAD for Speaker Diarization

python script_d.py

### All of the elements, including heuristic question determination from script_b

python script_e.py

### Resolve file naming discrepancies through CSV metadata, replace speaker names and change file name to item level

python script_f.py

### Replace file name only -- no speaker name change attempts

python script_g.py

### Cluster dialogue from same speakers from over-parsed Premiere transcripts

python script_h.py

### Correct "said" heuristic judgement

python script_i.py

### Keep monitor awake for batch processing

caffeinate -s python script

caffeinate -di python script

## Current Workflow

**E > F**

### Whisper model configuration:

- Best balance of speed and accuracy: small.en (if all recordings are in English)
- self.model = whisper.load_model("small.en")

- Higher accuracy with moderate speed: medium.en (if all recordings are in English)
- self.model = whisper.load_model("medium.en")

- Highest accuracy (if resources allow): large-v3
- self.model = whisper.load_model("large-v3")
