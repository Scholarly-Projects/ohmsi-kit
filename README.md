# ohmsi-kit

Oral History Multi-Speaker Interpretation-Kit

A tiered workflow for creating oral history transcriptions that implements various Whisper models for speech-to-text recognition and SpeechBrain for speaker diarization. The kit is organized to batch process collections of recordings, outputting a CSV file with timestamps and dialogue separated by speaker. Python scripts are designed to batch process the greatest number of recordings first, then apply more advanced scripts to more difficult recordings. Elements such as low audio fidelity, suboptimal recording environments, crosstalk, and vocal similarity between speakers which may introduce errors into Whisper’s pattern recognition, and result in dialogue clusters being underparsed or punctuation being dropped.

## ohmsi-kit workflow

* Before beginning processing, organize recordings by how many speakers are supposed to be involved in each interview. Unexpected speakers will be given the designation “Unknown Speaker” in CSV output, but designating a `NUM\_SPEAKERS` in the user configuration section at the top of the script will help inform how much variance between speakers will be involved in the recording.   
  * If speaker diarization is not a priority and/or you are dealing with a large volume of recordings, writing `None` after `NUM\_SPEAKERS` will default determination of different speakers to the `distance\_threshold`.  
* Move these organized `mp3`, `wav`, `m4a` or `flac` files into the `A` folder of the repository.
* First, batch process with `script\_a`. This is the most basic, accurate script which requires no customization beyond the speaker number designation.
* Reviewing the output of the processed audio files as CSVs in the B folder, it should be apparent if the recording was processed correctly. Large clusters of dialogue and/or transcripts gradually losing punctuation are indicators that those audio files need more advanced processing.
* `Script\_b` is identical to `a`, but utilizes the [medium.en](http://medium.en) Whisper model and `script\_c` uses `large\_v2`. These may result in higher accuracy of word identification and speaker differentiation but they will take longer to process. Also, there is a vulnerability to hallucination in `large\_v2` which you will need to look out for, but it is not nearly as pronounced as tests using `large-v3-turbo`, the most current Whisper model.
* _If these two scripts also yield unsuccessful transcriptions, the following models implement more manual approaches that may be helpful for unique recordings_.  
* `Script\_d` contains an active `distance\_threshold`, which is engaged even if there is a number provided in the `NUM\_SPEAKER`. If you are finding that speakers are incorrectly being merged, lower from the default `.65`. If the same speaker is being identified as multiple speakers, increase from `.65`.  
  * `Script\_d` also contains an `INTERJECTION` filter that may be helpful with specific interview styles. Some interjections may incorrectly cluster at the end of the previous speaker's dialogue, such as:

| speaker | timestamp | words |
| :---- | ----- | :---- |
| Speaker 3 | 0:00:00 | If you didn't pay up, well, it would cut you off the line. So her father is a secretary there. He climbed the pole and cut her off and the old lady came out and put you down. |
| Speaker 2 | 0:00:12 | This was Mrs. McKean? Yeah. |
| Speaker 3 | 0:00:16 | She was a woman that enjoyed getting out of the scrap, you know, just like old Gabriel Anderson or my dad. |
| Speaker 1 | 0:00:23 | Well, she wouldn't pick anything, but she wouldn't pick anything either. |
| Speaker 3 | 0:00:27 | Well, Anna Marie writes this article about this to you. I'm a darn fool. Instead of putting her dad in that did do it, she says, Mr. Roan, my dad, he called her a man. |
| Speaker 1 | 0:00:43 | He and his dad were batching right across the road from him at that time. |
| Speaker 2 | 0:00:47 | Well, so, but what really happened was Gabriel Anderson went... Her mother is a man. What happened? He climbed up the pole to cut it off? Yeah. |


- _The `INTERJECTION` function in the configuration of `script\_d` allows you to build a custom vocabulary based on these speaking styles, remove them from the ends of dialogue and attach them to the correct speaker, such as:_

| speaker | timestamp | words |
| :---- | ----- | :---- |
| Speaker 1 | 0:00:00 | If you didn't pay up, they'll cut you off the line. So her father is a second-year in there. He climbed the pole to cut her off, and the old lady came out of the butcher knife. |
| Speaker 3 | 0:00:13 | This was Mrs. McKean? |
| Speaker 1 | 0:00:14 | Yeah. She was a woman that enjoyed getting into the scrap, you know, just like old Gabriel Anderson or my dad. |
| Speaker 2 | 0:00:23 | Well, she wouldn't take anything, but she wouldn't take anything either. |
| Speaker 1 | 0:00:27 | Well, Anna Marie writes this article about this deal, and the darn fool, instead of putting her dad in that did do it, she says, Mr. Roan, my dad. |
| Speaker 2 | 0:00:40 | They laid right across the road. He and his dad were batching right across the road from him at that time. |
| Speaker 3 | 0:00:47 | Well, so, but what really happened was Gabriel Anderson went... |
| Speaker 1 | 0:00:51 | Her mother is a man. |
| Speaker 3 | 0:00:52 | What happened? He climbed up the pole to cut it off? |
| Speaker 1 | 0:00:54 | Yeah, and she came out with a butcher knife. |

* `Script\_e` adds another level of manual control. Whisper biometrics for identifying and labeling speakers is supplemented with heuristic rules for finding the interviewer by identifying questions being posed throughout the interview. Additionally, you can force breaks in dialogue manually by adjusting the `PAUSE\_THRESHOLD` number in the configuration. This can be a helpful backup script in circumstances where interviewer and interviewee language is more formal.
    * That said, this interviewer designation is programmatic rather than relying on the nuance of the Whisper and SpeechBrain models and may result in needing to correct certain elements of the transcript in future copy editing processes.  
* `Script\_f` is a last resort to salvage extremely compromised audio. Instead of attempting to identify and label speakers, the script separates clusters of speech by a `PAUSE\_THRESHOLD` that can be adjusted in the configuration section of the script.  
    * This CSV output is ideal if you simply need to have the most likely transcription of the audio with no speaker differentiation. For greater accuracy, run the audio through Adobe Premiere’s transcription model, [using my workshop](https://aweymo-ui.github.io/premiere_transcripts/) for reference. The Premiere transcription will likely have improved diarization but inferior translation than this script. Using the Premiere transcript as a base, update with Whisper’s more accurate translation to salvage and synthesize results.

## Supplemental Workflows

- **said.py**: Fixes a weakness in script_e where an interviewee is mis-identified as the interviewer is posing questions. This frequently comes up if a speaker is prone to recounting things like "... and then she said, why did you do that?". On running the script, these phrases are identified and the speaker column is replaced with `interviewee`, which you can find and replace with that interviewees name after running the script.

- **cluster.py**: Consolidates rows of dialogue that are labeled as the same speaker into a maximum of four sentences for material that is over-parsed.


### To run Python Scripts:

- Confirm in the VS Code terminal: 

_Windows:_

python --version

_Mac:_

python3 --version

_Make sure you are newer than 3.8._

**In Bash**

_Windows:_

python -m venv .venv
source .venv/Scripts/activate

_Mac:_

python3 -m venv .venv
source .venv/bin/activate

**Replace with the path of the file you want to adjust**

_Windows:_

python said.py /c/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv

or

python cluster.py /c/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv

_Mac:_

python3 said.py /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv

or

python3 cluster.py /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv

## Additional Workflows

### Remove millisecond from Premiere transcripts:

_Windows:_

sed -i 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv

_Mac:_

sed -i '' 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv 

### Switch columns C and D (Premiere Stop Time fix)

_Windows:_

python -c "
import csv
path = 'C:/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv'
rows = list(csv.reader(open(path)))
out = [[r[0],r[1],r[3],r[2]]+r[4:] if len(r)>3 else r for r in rows]
csv.writer(open(path,'w',newline='')).writerows(out)
"

_Mac:_

python3 -c "
import csv, sys
rows = list(csv.reader(open('$(echo /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/mckeever_george_1.csv)')))
out = [[r[0],r[1],r[3],r[2]]+r[4:] if len(r)>3 else r for r in rows]
csv.writer(open('$(echo /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/mckeever_george_1.csv)','w',newline='')).writerows(out)
"

## To remove empty line breaks from CSV (occasional Premiere bug)

_Windows:_

python -c "
import csv
path = 'C:/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv'
rows = list(csv.reader(open(path)))
clean = [r for r in rows if any(field.strip() for field in r)]
csv.writer(open(path,'w',newline='')).writerows(clean)
"

_Mac:_

python3 -c "
import csv
path = '/Users/GitHubName/Documents/GitHub/ohmsi-kit/B/mckeever_george_1.csv'
rows = list(csv.reader(open(path)))
clean = [r for r in rows if any(field.strip() for field in r)]
csv.writer(open(path, 'w', newline='')).writerows(clean)
"

## Capitalize the first letter in a new row of dialogue (occasional Premiere and Whisper bug)

_Windows:_

python -c "
import re
path = 'C:/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv'
content = open(path, encoding='utf-8').read()
content = re.sub(r'\"([a-z])', lambda m: '\"' + m.group(1).upper(), content)
open(path, 'w', encoding='utf-8', newline='').write(content)
"

_Mac:_

perl -i -pe 's/"([a-z])/\"\u$1/g' /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/platz_ima_1.csv

## Change speaker names for specific sections:

_Windows:_

awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Karen Purtee" {$1="Helena Cartwright Carlson"} 1' \
  "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv" > \
  "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/tmp.csv" && \
  mv "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/tmp.csv" \
     "/c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv"

_Mac:_

awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Karen Purtee" {$1="Helena Cartwright Carlson"} 1' \
  "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/carlson_helena_2.csv" > \
  "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/tmp.csv" && \
  mv "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/tmp.csv" \
     "/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/carlson_helena_2.csv"

## Add missing punctuation at the end of a row of dialogue (remove period from header after). Does not work if dialogue is missing punctuation inside of dialogue.

python3 -c "
import csv

path = '/Users/aweymouth/Documents/GitHub/ohmsi-kit/B/holland_joseph_2.csv'

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
    if text[-1] == '\"' and len(text) > 1:
        core = text[:-1]
        if core and core[-1] not in '.?!':
            text = core + '.\"'
    elif text[-1] not in '.?!':
        text = text + '.'
    row['words'] = text

with open(path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print('Done.')
"
