# ohmsi-kit

__Oral History Multi-Speaker Interpretation-Kit__

This kit uses Whisper speech-to-text models and SpeechBrain _diarization_ (identifying _who is speaking when_) to turn oral history recordings into CSV transcripts of timestamped dialogue separated by speaker. Recordings are batch processed with a basic script first, with more advanced scripts for difficult audio, such as crosstalk, poor recording conditions or similar-sounding voices. Each transcript can then be copy edited against its recording in a local workspace that previews it as it will appear on an [Oral History as Data](https://github.com/uidaholib/oral-history-collections-template) site. Keyboard shortcuts for playback, looping, speed and navigation streamline the copyediting process, while supplemental Python workflows batch correct repetitive and time consuming errors.

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

_Andrew Weymouth, Fall 2026._

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
<summary><h2>Transcription (A to B)</h2></summary>

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
<summary><h2>Copyediting Workspace (B to C)</h2></summary>

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

### Further Reference

- [Premiere Transcript Workflows](docs/remediate_premiere.md): fixes for transcripts exported from Adobe Premiere, such as removing frame numbers from timestamps, reordering columns, and removing empty rows.
- [Copy Editing Strategies](docs/copy_editing.md): a suggested order of passes for copy editing a transcript, from spot-checking for reprocessing to listening through in the editing workspace.

</details>

<details>
<summary><h2>Acknowledgments</h2></summary>

The transcript editing workspace is built from the [Oral History as Data collections template](https://github.com/uidaholib/oral-history-collections-template) by the CollectionBuilder contributors and University of Idaho Library Digital Initiatives, used under the MIT License with the contributors' permission; see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Transcription uses [Whisper](https://github.com/openai/whisper) and diarization uses [SpeechBrain](https://speechbrain.github.io/).

</details>

<details>
<summary><h2>Background</h2></summary>

This kit was developed over time to facilitate the transcription of the [Latah County Oral History Collection](https://www.lib.uidaho.edu/digital/lcoh/), an initiative conducted in the 1970's by the Latah County Historical Society and later digitized by the University of Idaho's [Center for Digital Inquiry and Learning](https://cdil.lib.uidaho.edu/) (CDIL) in 2015. The author developed this kit to transcribe the over 550 hour collection during the spring and summer of 2026 to make the material more discoverable for researchers and providing the Latah County community with easier access to its history. This kit was developed for implementation in the CDIL's [Oral History as Data](https://github.com/oralhistoryasdata) framework developed by Devin Becker, as well as the author's oral history transcript mining method outlined in [Distant Listening: Using Python and Apps Scripts to Text Mine and Tag Oral History Collections](https://journal.code4lib.org/articles/18286).

</details>