# ohmsi-kit

__Oral History Multi-Speaker Interpretation-Kit__

A tiered workflow for creating oral history transcriptions that implements various Whisper models for speech-to-text recognition and SpeechBrain for _diarization_, or the process of sorting an audio recording into segments that indicate _who is speaking when_. The kit batch processes collections of recordings into CSV files of timestamped dialogue separated by speaker, then provides a local editing workspace for copy editing each transcript against its recording. Whisper and SpeechBrain are open source, require no login or tokens, and **run locally** once their pre-trained models are downloaded.

The Python scripts are designed to batch process the greatest number of recordings first, then apply more advanced scripts to more difficult recordings. Low audio fidelity, suboptimal recording environments, crosstalk and vocal similarity between speakers can introduce errors into Whisper's pattern recognition, resulting in under-parsed dialogue clusters or dropped punctuation, which the kit's more advanced scripts can help mitigate.

The editing workspace previews each transcript as it will appear on an [Oral History as Data](https://github.com/uidaholib/oral-history-collections-template) site, playing the recording alongside the transcript so it can serve as the reference while you correct the CSV.

### Folder Structure

| Folder | Contents | Created by |
| :---- | :---- | :---- |
| `A` | Your original recordings (`.mp3`, `.m4a`, `.wav` or `.flac`; add files here before processing) | You |
| `B` | Generated transcripts: one CSV per recording, with timestamps and dialogue separated by speaker | `script_a.py`–`script_f.py` |
| `C` | The one transcript you're currently copy editing, opened in the editing workspace | You (copy a CSV from `B`) |
| `D` | Finished, copy-edited transcripts | You (move the CSV from `C` when done) |

A recording and its transcript share a filename throughout: `A/interview01.wav` → `B/interview01.csv`. Two more items at the root belong to the editing workspace: `_config.yml` (its settings) and `_local-build/` (everything it runs on; no need to open it).

### Basic Workflow

1. Add recordings to `A`.
2. Run the Python scripts to generate transcripts in `B`, starting with the batch script and using the advanced scripts on recordings that need them.
3. Copy one CSV from `B` into `C` and run `bundle exec jekyll s` to open the editing workspace.
4. Open the CSV in `C` in VS Code, listen and correct, and save; the workspace reloads with each save.
5. Move the finished CSV to `D`, then copy the next transcript into `C`.

_Andrew Weymouth, Summer 2026._

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
<summary><h2>Setup</h2></summary>

The kit needs three things, each installed once per computer: **Python 3.11** for the transcription scripts, **ffmpeg** for reading audio (Whisper uses it, and so do the editing workspace's playback copies), and **Ruby** for the editing workspace.

### Mac

#### Python

```bash
brew install pyenv
pyenv versions          # check if a 3.11.x is already installed
pyenv install 3.11.9    # skip this step if 3.11.x already shows up above
~/.pyenv/versions/3.11.9/bin/python -m venv .venv
source .venv/bin/activate
```
```bash
python --version
```
_should print Python 3.11.x (any 3.11 patch version works — wheels for torch==2.1.0 are built per minor version, not patch)_

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### ffmpeg

```bash
brew install ffmpeg
```

#### Ruby (editing workspace)

Install Ruby 3.1 or newer (Jekyll's [macOS guide](https://jekyllrb.com/docs/installation/macos/) walks through it), then from the toolkit root:

```bash
gem install bundler
bundle install
```

#### Run Script(s)

```bash
python script_a.py
```

_Keep device and/or display awake while processing_

```bash
caffeinate -s python script_a.py
caffeinate -di python script_a.py
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

#### Python

```powershell
choco install pyenv-win
pyenv versions          # check if a 3.11.x is already installed
pyenv install 3.11.9    # skip this step if 3.11.x already shows up above
& "$env:USERPROFILE\.pyenv\pyenv-win\versions\3.11.9\python.exe" -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # only needed if activation is blocked
.venv\Scripts\Activate.ps1
```
```bash
python --version
```
_should print Python 3.11.x (any 3.11 patch version works — wheels for torch==2.1.0 are built per minor version, not patch)_

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

#### ffmpeg

```powershell
choco install ffmpeg
```

#### Ruby (editing workspace)

Install Ruby 3.1 or newer with the DevKit (Jekyll's [Windows guide](https://jekyllrb.com/docs/installation/windows/) walks through it), then from the toolkit root:

```powershell
gem install bundler
bundle install
```

#### Run Script(s)

```powershell
python script_a.py
```

_Keep device and/or display awake while processing_

Windows has no direct `caffeinate` equivalent. Check your current timeout values first (`powercfg /query`), then temporarily set them to 0 and restore your originals after:
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
python script_a.py
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

### Running these scripts

Activate the virtual environment created in **Setup** (`source .venv/bin/activate` on Mac, `.venv\Scripts\Activate.ps1` on Windows), then run the script with the path of the file you want to adjust:

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
awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Speaker 2" {$1="Narrator Name"} 1' \
  "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv" > \
  "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/tmp.csv" && \
  mv "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/tmp.csv" \
     "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv"
```

_Mac:_

```bash
awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Speaker 2" {$1="Narrator Name"} 1' \
  "/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv" > \
  "/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/tmp.csv" && \
  mv "/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/tmp.csv" \
     "/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv"
```

### Add Missing Punctuation at the End of a Row of Dialogue

_Removes the period from the header first; does not work if dialogue is missing punctuation inside of the dialogue itself._

```bash
python3 -c "
import csv
path = '/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv'
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

### Swap the Third and Fourth Columns for Copy Editing Dialogue

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
path = '/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv'
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
perl -i -pe 's/"([a-z])/\"\u$1/g' /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv
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
    - [Swap the third and fourth columns](#swap-the-third-and-fourth-columns-for-copy-editing-dialogue) — retain, but don't prioritize, the End Time field if this is a Premiere transcript
    - [Remove empty line breaks from the CSV](#remove-empty-rows-between-dialogue-occasional-premiere-bug) (occasional Premiere bug)
    - [Capitalize the first letter in a new row of dialogue](#capitalize-first-letter-in-a-new-row-of-dialogue-occasional-premiere-and-whisper-bug) (occasional Premiere and Whisper bug)
    - [Change speaker names for specific sections](#change-speaker-names-for-specific-sections)
- **Third**, check the spelling in Visual Studio Code (or your editor of choice).
    - Look up flagged words.
    - Check your project's reference list (e.g. `semantic-list.md`) for people and place names that have already been documented.
    - If a proper name feels recurring, add it to the reference list, then right-click the word in your editor and select `Add to User Settings` to expand your personal dictionary.
    - If the interviewee is mislabeled as the interviewer when recounting someone else's questions, this is a good point to run **said.py** (see Supplemental Python Workflows).
- **Fourth**, listen through the transcript in the Transcript Editing Workspace (below), correcting the CSV in VS Code as you go.
    - This gives you a chance to correct diarization errors and refine spelling further.
    - **Note**: the goal is to reflect the audio, not correct it. Muffled recordings, mumbled words, and ambiguous proper names can be documented with an ellipsis or a best guess, as long as the guess is standardized across that transcript.
    - As you work through, note things like incorrect interviewer/interviewee metadata, sensitive material that should be flagged for researchers, and notes about the audio itself (looping, noise issues, etc.) in your tracking notes.
- **Fifth**, if the transcript is over-parsed, run **cluster.py** on the file (see Supplemental Python Workflows).

</details>

<details>
<summary><h2>Transcript Editing Workspace</h2></summary>

A local dry run of how a transcript will look and behave on an Oral History as Data (OHD) site, used to copy edit the transcript against its recording. The page is built from the OHD item-level transcript layout and runs with Jekyll on your own computer. Nothing is published. It uses the folders described in [Folder Structure](#folder-structure).

### Opening the workspace

1. Copy **one** CSV from `B/` into `C/`.
2. From the toolkit root, run:

   ```bash
   bundle exec jekyll s
   ```

   When the build finishes, the terminal prints a line like

   ```
   Workspace: http://127.0.0.1:4000/
   ```

   Copy that address into a browser (most terminals also open it with Cmd+click or Ctrl+click). The browser is not opened automatically.
3. Open the CSV in `C/` in VS Code next to the browser. Listen, correct the text, and save. The page rebuilds and reloads by itself, and playback continues from where it was.
4. When you're done, move the corrected CSV to `D/`, then copy the next transcript into `C/`.

The first time a WAV, FLAC or M4A recording is opened, the build pauses while ffmpeg makes a playback copy (see below). This happens once per recording.

### What's on the page

The page header takes its title and description from `title` and `description` in `_config.yml`. Below it, the page uses the OHD transcript includes unchanged: the topic bar with its hover tooltips, the topic filter and search, the sticky filter tab, scrollama, and the transcript lines. A transcript should look the same here as on the live site. Two areas differ:

- **Player**: OHD's own MP3 player (`transcript/item/av.html`), playing the recording from `A/`, with editor-only controls underneath. When you scroll into the transcript it shrinks to the mini player at the lower right, as on the live site (needs `media-scroll: true` in `_local-build/_data/theme.yml`).
- **Metadata area**: workspace status instead of collection metadata, since a transcript in `C/` has no metadata row yet.

#### Editor-only additions

**Player controls.** Under the player and in the scrolling mini player: −5s / +5s, speed − / + with a readout (select it for normal speed), and ⟲ Loop 5s. Controls flash yellow when used, by mouse or keyboard, and a short note beside them confirms a new speed, a loop's range or a copied time.

**Keyboard shortcuts** (the defaults; see [Changing the shortcuts](#changing-the-shortcuts)):

| Key | Setting | Does |
|---|---|---|
| `Space` | `play_pause` | Play / pause, including while a timestamp or line number has focus |
| `←` / `→` | `back` / `forward` | Back / forward 5 seconds |
| `I` / `D` | `faster` / `slower` | Faster / slower, stepping through 0.5×, 0.75×, 1×, 1.25×, 1.5×, 1.75×, 2× |
| `0` | `normal_speed` | Normal speed (1×) |
| `N` / `P` | `next_line` / `previous_line` | Jump playback to the next / previous line (scrolls it into view if needed) |
| `L` | `loop` | Loop the last 5 seconds, from the moment you press it (see below) |
| `C` | `continue` | End a loop and carry on playing from that point |
| `T` | `copy_time` | Copy the current playback time in the CSV's timestamp format (`00:12:03`), to paste into a timestamp you're correcting |
| `Tab` / `Shift`+`Tab` | | Move through the timestamps and line numbers; `Enter` on a timestamp jumps playback there |
| `↑` / `↓` | | Scroll the page, as usual |

A keyboard guide sits at the top right above the player; a smaller one sits under the mini player when you scroll down. Both list the shortcuts as configured. Shortcuts are ignored while you type in the search box, choose from a menu, or use the browser's own player controls. Speed changes are announced to screen readers.

**Looping.** A loop keeps replaying while you correct the passage in VS Code, and changing speed keeps it going. Besides `C`, it ends with `L` again or anything that moves or stops playback: `Space` (pauses), `←` / `→`, `N` / `P`, a timestamp, or the player's own scrubber.

**Line numbers.** The grey **L** number under each timestamp is that line of the CSV. Select it (click, or `Tab` to it and press `Enter`) to open the CSV in VS Code with the cursor on that line. The first time, the browser asks permission to open VS Code; allow it (and tick "always allow" if offered).

**Line being spoken.** Highlighted in yellow with a black left edge. The timestamp or line number you've tabbed to has a black outline.

These additions are marked `no-print` and don't appear in printouts. Filtering, search and Reset Filters come from the OHD filter bar above the transcript.

#### Changing the shortcuts

Each shortcut is set under `editor: keys:` in `_config.yml` at the toolkit root, using the setting names in the table above. Alongside them, `skip_seconds`, `speeds` and `loop_seconds` set the skip length, speed steps and loop length, and `open_in` sets the editor line numbers open (`vscode`, `vscode-insiders`, `cursor`, `vscodium` or `none`). After changing any of them, stop the server and run `bundle exec jekyll s` again.

- Give each action one key, or a list such as `next_line: [n, j]`.
- Use letters and digits as typed (put digits and symbols in quotes: `"0"`, `"]"`), `Space`, or a key name: `ArrowLeft`, `ArrowRight`, `ArrowUp`, `ArrowDown`, `Enter`, `Escape`. Letters work with or without Shift.
- Set an action to `""` to turn its shortcut off; its button still works.
- Avoid `Tab` and `Enter`, which move between and activate timestamps and line numbers.
- The keyboard guides, button labels and tooltips update to match.

### Checks and warnings

On each rebuild the workspace checks the CSV and lists problems in the status area (and in the terminal):

- `C/` empty, or holding more than one CSV (it then shows the most recently saved one)
- no matching recording in `A/`
- a CSV that can't be parsed, usually an unmatched double quote, with the line where parsing failed
- a file not saved as UTF-8
- missing `speaker`, `timestamp` or `words` columns
- lines with no timestamp

Individual lines get a red edge and a note, and are listed under "lines to check", when their timestamp isn't `H:MM:SS`, goes backwards, or the line has no words.

### Playback

The OHD player is an MP3 player, so for WAV, FLAC and M4A recordings the workspace uses ffmpeg to make a constant-bitrate 128 kbps MP3 copy, which plays and seeks accurately in every browser. A one-hour recording becomes about 55 MB.

- Copies are kept in `.jekyll-cache/editor-audio/` and remade only when the recording changes.
- The original in `A/` is never modified.
- Setting `editor: playback_copy:` in `_config.yml` controls this: `auto` (everything except MP3, the default), `always` (every recording) or `never`.
- If ffmpeg isn't installed, the original file is played and the status area says so; see **Setup** above.

While `jekyll serve` runs, the recording is served in short pieces that the browser doesn't cache. This keeps seeking and reloading reliable with long recordings, which Jekyll's built-in server otherwise sends as one long open-ended response.

### Setup

Ruby and ffmpeg are installed in the **Setup** section above.

The page loads Bootstrap and fonts from the web, so you need an internet connection. To work offline, download Bootstrap 5's `bootstrap.min.css` and `bootstrap.bundle.min.js` into `_local-build/assets/lib/` and point the two links in `_local-build/_includes/head/head.html` and `_local-build/_includes/foot.html` at them.

#### Git

`.gitignore` should include:

```
_site/
.jekyll-cache/
.jekyll-metadata
.sass-cache/
A/
B/
C/
D/
```

### How it's put together

Jekyll reads the toolkit root, so it notices saves in `C/`, but `_config.yml` points it at `_local-build/` for its layouts, includes, plugins, styles, theme data and output.

```
_local-build/
├── _data/        theme.yml, filters.csv, config-theme-colors.csv (from OHD)
├── _includes/    OHD includes, plus editor/ (the workspace's own)
├── _layouts/     editor.html, editor-base.html
├── _plugins/     editor_workspace.rb
├── _sass/        OHD styles
├── assets/       css/cb.scss and lib/ (from OHD), published at /assets/
└── _site/        the built page (generated; ignored by git)
```

| Piece | Role |
|---|---|
| `_plugins/editor_workspace.rb` | Finds the CSV in `C/` and the recording in `A/`, makes the playback copy, checks the CSV, generates the page, publishes `assets/`, serves the recording in short pieces, and prints the workspace address |
| `_layouts/editor.html` | The workspace page, following OHD `_layouts/transcript.html` |
| `_layouts/editor-base.html` | Page shell approximating the OHD item page: title banner, breadcrumb, item title, footer, back-to-top button |
| `_includes/editor/` | Player controls, keyboard guides, status panel, back-to-top button, editor script and styles |

#### Files copied from the OHD template, unchanged

All of these live under `_local-build/`:

```
_includes/head/head.html
_includes/foot.html
_includes/transcript/                          (the whole folder), in particular:
    item/av.html
    player/mp3.html
    item/transcript.html
    item/transcript-viz.html
    item/filters.html
    standardized-timestamp.html
    style/filter-style.html
    style/visualization-filter-legend.html
    style/media-scroll-wrapper.html
    js/transcript-js.html
    js/scrollama-js.html
    js/scrollama-base-js.html
_sass/  (all six partials)
assets/css/cb.scss
assets/lib/
_data/theme.yml
_data/config-theme-colors.csv
_data/filters.csv
```

The workspace draws its own back-to-top button and Transcript ↓ arrow, so it doesn't need OHD's `scroll-to-top.html` or the `cb-icons.svg` sprite.

Keep `theme.yml`, `filters.csv` and the SCSS in step with the live site so the dry run matches it. The mini player needs `media-scroll: true` and the filter bar `search-and-filters: true` in `theme.yml`; the keyboard shortcuts work either way.

</details>

<details>
<summary><h2>Background</h2></summary>

This kit was developed over time to facilitate the transcription of the [Latah County Oral History Collection](https://www.lib.uidaho.edu/digital/lcoh/), an initiative conducted in the 1970's by the Latah County Historical Society and later digitized by the University of Idaho's [Center for Digital Inquiry and Learning](https://cdil.lib.uidaho.edu/) (CDIL) in 2015. The author developed this kit to transcribe the over 550 hour collection during the spring and summer of 2026 to make the material more discoverable for researchers and providing the Latah County community with easier access to its history. This kit was developed for implementation in the CDIL's [Oral History as Data](https://github.com/oralhistoryasdata) framework developed by Devin Becker, as well as the author's oral history transcript mining method outlined in [Distant Listening: Using Python and Apps Scripts to Text Mine and Tag Oral History Collections](https://journal.code4lib.org/articles/18286).

</details>