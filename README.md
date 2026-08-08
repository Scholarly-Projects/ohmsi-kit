# ohmsi-kit

__Oral History Multi-Speaker Interpretation-Kit__

A tiered workflow for creating oral history transcriptions that implements various Whisper models for speech-to-text recognition and SpeechBrain for _diarization_, or the process of sorting an audio recording into segments that indicate _who is speaking when_. The kit is organized to batch process collections of recordings, outputting a CSV file with timestamps and dialogue separated by speaker. Both Whisper and SpeechBrain are open source, do not login or tokens to access and run locally once their pre-trained models are downloaded. 

The Python scripts are designed to batch process the greatest number of recordings first, then apply more advanced scripts to more difficult recordings. Elements such as low audio fidelity, suboptimal recording environments, crosstalk, and vocal similarity between speakers may introduce errors into Whisper's pattern recognition, and result in dialogue clusters being under parsed or punctuation being dropped, which the kit's more advanced scripts can help mediate.

This kit was developed over time to facilitate the transcription of the [Latah County Oral History Collection](https://www.lib.uidaho.edu/digital/lcoh/), an initiative conducted in the 1970's by the Latah County Historical Society and later digitized by the University of Idaho's [Center for Digital Inquiry and Learning](https://cdil.lib.uidaho.edu/) (CDIL) in 2015. The author developed this kit to transcribe the over 550 hour collection during the spring and summer of 2026 to make the material more discoverable for researchers and providing the Latah County community with easier access to its history. This kit was developed for implementation in the CDIL's [Oral History as Data](https://github.com/oralhistoryasdata) framework developed by Devin Becker, as well as the author's oral history transcript mining method outlined in [Distant Listening: Using Python and Apps Scripts to Text Mine and Tag Oral History Collections](https://journal.code4lib.org/articles/18286).

Future iterations of ohmsi-kit will include an editing workspace where users can open processed transcriptions locally to aid and streamline the copyediting process, leveraging Oral History as Data’s playback interface and Visual Studio Code’s user dictionary capabilities. Other advancements may include automated sequential processing of audio files based on a programmatic survey that evaluates transcripts for accurate dialogue clustering.

_Andrew Weymouth, Summer, 2026_

<details>
<summary><h2>ohmsi-kit Workflow</h2></summary>

* Before processing, organize recordings by how many speakers are supposed to be involved in each interview. Unexpected speakers will be given the designation "Unknown Speaker" in CSV output, but designating a `NUM_SPEAKERS` in the user configuration section at the top of the script will help inform how much variance between speakers will be involved in the recording for greater accuracy.
  * If speaker diarization is not a priority and/or you are dealing with a large volume of recordings, writing `None` after `NUM_SPEAKERS` will default determination of different speakers to the `distance_threshold`.
* Move these organized `mp3`, `wav`, `m4a` or `flac` files into the `A` folder of the repository.
* First, batch process with `script_a`. This is the most basic, accurate script which requires no customization beyond the speaker number designation.
* Reviewing the output of the processed audio files as CSVs in the B folder, it should be apparent if the recording was processed correctly. Large clusters of dialogue and/or transcripts gradually losing punctuation are indicators that those audio files need more advanced processing.
* `script_b` is identical to `a`, but utilizes the `medium.en` Whisper model and `script_c` uses `large_v2`. These may result in higher accuracy of word identification and speaker differentiation but they will take longer to process. Also, there is a vulnerability to hallucination in `large_v2` which you will need to look out for, but it is not nearly as pronounced as tests using `large-v3-turbo`, the most current Whisper model.
* _If these two scripts also yield unsuccessful transcriptions, the following models implement more manual approaches that may be helpful for unique recordings_.
* `script_d` contains an active `distance_threshold`, which is engaged even if there is a number provided in the `NUM_SPEAKERS`. If you are finding that speakers are incorrectly being merged, lower from the default `.65`. If the same speaker is being identified as multiple speakers, increase from `.65`.
  * `script_d` also contains an `INTERJECTION` filter that may be helpful with specific interview styles. Some interjections may incorrectly cluster at the end of the previous speaker's dialogue, such as:

| speaker | timestamp | words |
| :---- | ----- | :---- |
| Speaker 3 | 0:00:00 | If you didn't pay up, well, it would cut you off the line. So her father is a secretary there. He climbed the pole and cut her off and the old lady came out and put you down. |
| Speaker 2 | 0:00:12 | This was Mrs. McKean? <mark>Yeah.</mark> |
| Speaker 3 | 0:00:16 | She was a woman that enjoyed getting out of the scrap, you know, just like old Gabriel Anderson or my dad. |
| Speaker 1 | 0:00:23 | Well, she wouldn't pick anything, but she wouldn't pick anything either. |
| Speaker 3 | 0:00:27 | Well, Anna Marie writes this article about this to you. I'm a darn fool. Instead of putting her dad in that did do it, she says, Mr. Roan, my dad, he called her a man. |
| Speaker 1 | 0:00:43 | He and his dad were batching right across the road from him at that time. |
| Speaker 2 | 0:00:47 | Well, so, but what really happened was Gabriel Anderson went... Her mother is a man. What happened? He climbed up the pole to cut it off? <mark>Yeah.</mark> |

- _The `INTERJECTION` function in the configuration of `script_d` allows you to build a custom vocabulary based on these speaking styles, remove them from the ends of dialogue and attach them to the correct speaker, such as:_

| speaker | timestamp | words |
| :---- | ----- | :---- |
| Speaker 1 | 0:00:00 | If you didn't pay up, they'll cut you off the line. So her father is a second-year in there. He climbed the pole to cut her off, and the old lady came out of the butcher knife. |
| Speaker 3 | 0:00:13 | This was Mrs. McKean? |
| Speaker 1 | 0:00:14 | <mark>Yeah.</mark> She was a woman that enjoyed getting into the scrap, you know, just like old Gabriel Anderson or my dad. |
| Speaker 2 | 0:00:23 | Well, she wouldn't take anything, but she wouldn't take anything either. |
| Speaker 1 | 0:00:27 | Well, Anna Marie writes this article about this deal, and the darn fool, instead of putting her dad in that did do it, she says, Mr. Roan, my dad. |
| Speaker 2 | 0:00:40 | They laid right across the road. He and his dad were batching right across the road from him at that time. |
| Speaker 3 | 0:00:47 | Well, so, but what really happened was Gabriel Anderson went... |
| Speaker 1 | 0:00:51 | Her mother is a man. |
| Speaker 3 | 0:00:52 | What happened? He climbed up the pole to cut it off? |
| Speaker 1 | 0:00:54 | <mark>Yeah.</mark> And she came out with a butcher knife. |

* `script_e` adds another level of manual control. Whisper biometrics for identifying and labeling speakers is supplemented with heuristic rules for finding the interviewer by identifying questions being posed throughout the interview. Additionally, you can force breaks in dialogue manually by adjusting the `PAUSE_THRESHOLD` number in the configuration. This can be a helpful backup script in circumstances where interviewer and interviewee language is more formal.
    * That said, this interviewer designation is programmatic rather than relying on the nuance of the Whisper and SpeechBrain models and may result in needing to correct certain elements of the transcript in future copy editing processes.
* `script_f` is a last resort to salvage extremely compromised audio. Instead of attempting to identify and label speakers, the script separates clusters of speech by a `PAUSE_THRESHOLD` that can be adjusted in the configuration section of the script.
    * This CSV output is ideal if you simply need to have accurate transcription of the audio with no speaker diarization. For greater accuracy, run the audio through Adobe Premiere's transcription model, [using my workshop](https://aweymo-ui.github.io/premiere_transcripts/) for reference. The Premiere transcription will likely have improved diarization but inferior translation than this script. Using the Premiere transcript as a base, update with Whisper's more accurate translation to salvage and synthesize results.

</details>

<details>
<summary><h2>Python Tool Setup</h2></summary>

### Mac

```bash
brew install pyenv
pyenv versions          # check if a 3.11.x is already installed
pyenv install 3.11.9    # skip this step if 3.11.x already shows up above
~/.pyenv/versions/3.11.9/bin/python -m venv .venv
source .venv/bin/activate
```
```bash
`python --version`
```
_should print Python 3.11.x (any 3.11 patch version works — wheels for torch==2.1.0 are built per minor version, not patch)_

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Run Script(s)

```bash
python script_
```

_Keep device and/or display awake while processing_

```bash
caffeinate -s python script_
caffeinate -di python script_
```

_Or run multiple scripts on the same audio files_

```bash
caffeinate -di bash -c '
python script_a.py;
python script_b.py;
python script_c.py;
python script_d.py;
python script_e.py;
python script_f.py
'
```

### Windows

```powershell
choco install pyenv-win
pyenv versions          # check if a 3.11.x is already installed
pyenv install 3.11.9    # skip this step if 3.11.x already shows up above
& "$env:USERPROFILE\.pyenv\pyenv-win\versions\3.11.9\python.exe" -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # only needed if activation is blocked
.venv\Scripts\Activate.ps1
```
```bash
`python --version`
```
_should print Python 3.11.x (any 3.11 patch version works — wheels for torch==2.1.0 are built per minor version, not patch)_

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

#### Run Script(s)

```powershell
python script_
```

_Keep device and/or display awake while processing_

Windows has no direct `caffeinate` equivalent. Check your current timeout values first (`powercfg /query`), then temporarily set them to 0 and restore your originals after:
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
python script_
# restore your original values here when done
```

_Or run multiple scripts on the same audio files_

```powershell
python script_a.py; python script_b.py; python script_c.py; python script_d.py; python script_e.py; python script_f.py
```

</details>

<details>
<summary><h2>Supplemental Python Workflows</h2></summary>

- **said.py**: Fixes a weakness in script_e where an interviewee is mis-identified as the interviewer is posing questions. This frequently comes up if a speaker is prone to recounting things like "... and then she said, why did you do that?". On running the script, these phrases are identified and the speaker column is replaced with `interviewee`, which you can find and replace with that interviewee's name after running the script.

- **cluster.py**: Consolidates rows of dialogue that are labeled as the same speaker into a maximum of four sentences for material that is over-parsed.

### To run Python Scripts:

- Confirm in the VS Code terminal:

_Windows:_

```bash
`python --version`
```

_Mac:_

```bash
python3 --version
```

_Make sure you are newer than 3.8._

**In Bash**

_Windows:_

```bash
python -m venv .venv
source .venv/Scripts/activate
```

_Mac:_

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Replace with the path of the file you want to adjust**

_Windows:_

```bash
python said.py /c/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv
```

or

```bash
python cluster.py /c/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv
```

_Mac:_

```bash
python3 said.py /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv
```

or

```bash
python3 cluster.py /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv
```

### Change Speaker Names for Specific Sections

_Windows:_

```bash
awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Karen Purtee" {$1="Helena Cartwright Carlson"} 1' \
  "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv" > \
  "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/tmp.csv" && \
  mv "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/tmp.csv" \
     "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv"
```

_Mac:_

```bash
awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Karen Purtee" {$1="Helena Cartwright Carlson"} 1' \
  "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/carlson_helena_2.csv" > \
  "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/tmp.csv" && \
  mv "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/tmp.csv" \
     "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/carlson_helena_2.csv"
```

### Add Missing Punctuation at the End of a Row of Dialogue

_Removes the period from the header first; does not work if dialogue is missing punctuation inside of the dialogue itself._

```bash
python3 -c "
import csv
path = '/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/example_transcript.csv'
with open(path, newline='', encoding='utf-8') as f:
    rows = list(csv.reader(f))
header = rows[0]
header = [h.rstrip('.?!') for h in header]
rows[0] = header
with open(path, 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(rows)
with open(path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)
for row in rows:
    text = row['words'].rstrip()
    if not text:
        continue
    if text[-1] == '"' and len(text) > 1:
        core = text[:-1]
        if core and core[-1] not in '.?!':
            text = core + '."'
    elif text[-1] not in '.?!':
        text = text + '.'
    row['words'] = text
with open(path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print('Done.')
"
```

</details>

<details>
<summary><h2>Premiere Transcript Remediation Workflows</h2></summary>

### Remove Millisecond from Timestamps

_Windows:_

```bash
sed -i 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv
```

_Mac:_

```bash
sed -i '' 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv
```

### Switch Columns C and D for Copy Editing Dialogue

_Windows:_

```bash
python -c "
import csv
path = 'C:/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv'
rows = list(csv.reader(open(path)))
out = [[r[0],r[1],r[3],r[2]]+r[4:] if len(r)>3 else r for r in rows]
csv.writer(open(path,'w',newline='')).writerows(out)
"
```

_Mac:_

```bash
python3 -c "
import csv, sys
rows = list(csv.reader(open('$(echo /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv)')))
out = [[r[0],r[1],r[3],r[2]]+r[4:] if len(r)>3 else r for r in rows]
csv.writer(open('$(echo /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv)','w',newline='')).writerows(out)
"
```

### Remove Empty Rows Between Dialogue (occasional Premiere bug)

_Windows:_

```bash
python -c "
import csv
path = 'C:/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv'
rows = list(csv.reader(open(path)))
clean = [r for r in rows if any(field.strip() for field in r)]
csv.writer(open(path,'w',newline='')).writerows(clean)
"
```

_Mac:_

```bash
python3 -c "
import csv
path = '/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/example_transcript.csv'
rows = list(csv.reader(open(path)))
clean = [r for r in rows if any(field.strip() for field in r)]
csv.writer(open(path, 'w', newline='')).writerows(clean)
"
```

### Capitalize First Letter in a New Row of Dialogue (occasional Premiere and Whisper bug)

_Windows:_

```bash
python -c "
import re
path = 'C:/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv'
content = open(path, encoding='utf-8').read()
content = re.sub(r'\"([a-z])', lambda m: '\"' + m.group(1).upper(), content)
open(path, 'w', encoding='utf-8', newline='').write(content)
"
```

_Mac:_

```bash
perl -i -pe 's/"([a-z])/\"\u$1/g' /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/platz_ima_1.csv
```

</details>

<details>
<summary><h2>Copy Editing Workflows</h2></summary>

This overview assumes you're keeping basic tracking notes (e.g. a `notes.md` file) and a shared reference list of proper nouns (e.g. a `semantic-list.md` file) alongside your transcripts. These are suggested conventions, not required infrastructure — adapt them to whatever tracking method works for your project.

- **First**, check whether there are major errors serious enough to warrant reprocessing the audio with a different script, rather than manually correcting the transcript.
    - Open the file locally and skip ahead roughly every 15 minutes to spot-check for major issues.
    - If you encounter major diarization problems — such as the transcript failing to flag distinct speakers in the middle of a dialogue exchange — reprocessing the audio may take less time than manually correcting it, so it's worth finding this out before investing more work.
    - If that's the case, log the filename of the affected transcript under a `reprocess with new script` heading in your tracking notes.
- **Second**, if the transcript looks workable, begin formatting it as needed using any of the processes detailed in the [Premiere Transcript Remediation Workflows](#premiere-transcript-remediation-workflows) section above:
    - [Remove millisecond from timestamps](#remove-millisecond-from-timestamps) (Premiere transcripts)
    - [Switch columns C and D](#switch-columns-c-and-d-for-copy-editing-dialogue) — retain, but don't prioritize, the End Time field if this is a Premiere transcript
    - [Remove empty line breaks from the CSV](#remove-empty-rows-between-dialogue-occasional-premiere-bug) (occasional Premiere bug)
    - [Capitalize the first letter in a new row of dialogue](#capitalize-first-letter-in-a-new-row-of-dialogue-occasional-premiere-and-whisper-bug) (occasional Premiere and Whisper bug)
    - [Change speaker names for specific sections](#change-speaker-names-for-specific-sections)
- **Third**, check the spelling in Visual Studio Code (or your editor of choice).
    - Look up flagged words.
    - Check your project's reference list (e.g. `semantic-list.md`) for people and place names that have already been documented.
    - If a proper name feels recurring, add it to the reference list, then right-click the word in your editor and select `Add to User Settings` to expand your personal dictionary.
    - If you're noticing a fair amount of mis-diarization caused by the interviewee posing rhetorical questions or recounting someone else's questions — such as "... and then she said, why did you do that?" — this is a good point in the workflow to run the **said.py** script on the file.
- **Fourth**, listen through the transcript by tabbing through the timestamp field while playing the corresponding audio locally.
    - This gives you a chance to correct diarization errors and refine spelling further.
    - **Note**: the goal is to reflect the audio, not correct it. Muffled recordings, mumbled words, and ambiguous proper names can be documented with an ellipsis or a best guess, as long as the guess is standardized across that transcript.
    - As you work through, note things like incorrect interviewer/interviewee metadata, sensitive material that should be flagged for researchers, and notes about the audio itself (looping, noise issues, etc.) in your tracking notes.
- **Fifth**, if the transcript is over-parsed, run **cluster.py** on the file, which will condense multiple rows of dialogue from the same speaker into clusters of up to four sentences.

</details>