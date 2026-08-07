
# Remediation Workflow

## Copy Editing Overview

- **First**, check to see if there are major errors that warrant running the file through another transcription method.
    - Open the file locally and skip about every 15 minutes
    - If you encounter major diarization problems, such as transcripts not flagging distinct speakers in the middle of a chunk of dialogue, the transcript may take less time to reprocess than to manually correct -- and you will want to find this out before putting any more work into it!
    - If this is the case, note the filename of the corrupted transcript in the notes.md in the `reprocess with new script` section.
- **Second**, if the transcript looks workable, begin formatting the transcript as needed using any of these processed detailed in the **other workflows** section below.
    - Remove millisecond from Premiere transcripts
    - Switch columns C and D (retain but not focus on End Time field if this is a Premiere Transcript)
    - Remove empty line breaks from CSV (occasional Premiere bug)
    - Capitalize the first letter in a new row of dialogue (occasional Premiere and Whisper bug)
    - Change speaker names for specific sections
- **Third**, check the spelling in Visual Studio Code.
    - Look up flagged words. 
    - Check the semantic-list.md file for people and place names that have already been documented.
    - If a proper name feels reoccurring, add it to the semantic-list file and right click the word and select `add to user settings` to expand your dictionary.
    - If you are noticing a fair amount of mis-diarization caused by the interviewee posing questions rhetorically or recounting questions of others, such as "... and then she said, why did you do that?" this is a good time in the workflow to run the **said.py** script on the file.
- **Fourth**, listen through the transcript by tabbing through the timestamp field while running the collection on your device locally.
    - This will give you a chance to correct diarization errors and further spelling refinements.
    - **Note**: the goal is to reflect the audio, not correct the audio. Muffled recordings, mumbled words and ambiguous proper names can either be documented by an ellipses or a best guess (as long as the guess is standardized across that transcript).
    - As you work through note things like incorrect interviewer/interviewee metadata on the items, sensitive material that we may want to flag for researchers and notes about the audio, such as looping or noise issues in the notes.md
- **Fifth**, if the script you are working on is overly parsed, you can run the **cluster.py** on the file, which will condense multiple rows of dialogue from the same speaker into maximum four sentence clusters. 

# Technical Workflows

- If you have a copy of the repo on your local, select the + sign in your terminal to open a new window in bash and select these workflows as needed.

- Copy and Paste these formulas down into a Doc and replace the dummy path for the path of the file you would like to adjust. To find your file's path, right click the transcript file and select `copy path`.

## Python Workflows

- **said.py** fixes a weakness in some of the Whisper scripts where an interviewee is mis-identified as the interviewer is posing questions. This frequently comes up if a speaker is prone to recounting things like "... and then she said, why did you do that?". On running the script, these phrases are identified and the speaker column is replaced with `interviewee`, which you can find and replace with that interviewees name after running the script.

- **cluster.py** consolidates rows of dialogue that are labeled as the same speaker into a maximum of four sentences for material that is over-parsed.

## To run Python Scripts:

- Confirm in the VS Code terminal: 

_Windows:_

python --version

_Mac:_

python3 --version

- If you don't have a version newer than  3.8, visit the uidaho / Microsoft store and install the most recent update.

**In Bash**

_Windows:_

python -m venv .venv
source .venv/Scripts/activate

_Mac:_

python3 -m venv .venv
source .venv/bin/activate

**Replace with the path of the file you want to adjust**

_Windows:_

python said.py /c/Users/mkoepele/Documents/GitHub/oral-history-collections-template/_data/transcripts/demus_gus_3.csv

or

python cluster.py /c/Users/mkoepele/Documents/GitHub/oral-history-collections-template/_data/transcripts/demus_gus_3.csv

_Mac:_

python3 said.py /Users/aweymouth@uidaho.edu/Documents/GitHub/oral-history-collections-template/_data/transcripts/flodin_elmer_2.csv

or

python3 cluster.py /Users/aweymouth@uidaho.edu/Documents/GitHub/oral-history-collections-template/_data/transcripts/flodin_elmer_2.csv

# Other Workflows

## To remove millisecond from Premiere transcripts:

_Windows:_

sed -i 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /c/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/demus_gus_3.csv

_Mac:_

sed -i '' 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /Users/aweymouth@uidaho.edu/Documents/GitHub/oral-history-collections-template/_data/transcripts/flodin_elmer_2.csv 

## To switch columns C and D (retain but not focus on End Time field if this is a Premiere Transcript)

_Windows:_

python -c "
import csv
path = 'C:/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/demus_gus_3.csv'
rows = list(csv.reader(open(path)))
out = [[r[0],r[1],r[3],r[2]]+r[4:] if len(r)>3 else r for r in rows]
csv.writer(open(path,'w',newline='')).writerows(out)
"

_Mac:_

python3 -c "
import csv, sys
rows = list(csv.reader(open('$(echo /Users/aweymouth@uidaho.edu/Documents/GitHub/oral-history-collections-template/_data/transcripts/mckeever_george_1.csv)')))
out = [[r[0],r[1],r[3],r[2]]+r[4:] if len(r)>3 else r for r in rows]
csv.writer(open('$(echo /Users/aweymouth@uidaho.edu/Documents/GitHub/oral-history-collections-template/_data/transcripts/mckeever_george_1.csv)','w',newline='')).writerows(out)
"

## To remove empty line breaks from CSV (occasional Premiere bug)

_Windows:_

python -c "
import csv
path = 'C:/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/demus_gus_3.csv'
rows = list(csv.reader(open(path)))
clean = [r for r in rows if any(field.strip() for field in r)]
csv.writer(open(path,'w',newline='')).writerows(clean)
"

_Mac:_

python3 -c "
import csv
path = '/Users/aweymouth@uidaho.edu/Documents/GitHub/oral-history-collections-template/_data/transcripts/mckeever_george_1.csv'
rows = list(csv.reader(open(path)))
clean = [r for r in rows if any(field.strip() for field in r)]
csv.writer(open(path, 'w', newline='')).writerows(clean)
"

## Capitalize the first letter in a new row of dialogue (occasional Premiere and Whisper bug)

_Windows:_

python -c "
import re
path = 'C:/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/demus_gus_3.csv'
content = open(path, encoding='utf-8').read()
content = re.sub(r'\"([a-z])', lambda m: '\"' + m.group(1).upper(), content)
open(path, 'w', encoding='utf-8', newline='').write(content)
"

_Mac:_

perl -i -pe 's/"([a-z])/\"\u$1/g' /Users/aweymouth@uidaho.edu/Documents/GitHub/oral-history-collections-template/_data/transcripts/platz_ima_1.csv

## Change speaker names for specific sections:

_Windows:_

awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Karen Purtee" {$1="Helena Cartwright Carlson"} 1' \
  "/c/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/demus_gus_3.csv" > \
  "/c/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/tmp.csv" && \
  mv "/c/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/tmp.csv" \
     "/c/Users/mkoepele/Documents/github/oral-history-collections-template/_data/transcripts/demus_gus_3.csv"

_Mac:_

awk 'BEGIN{FS=OFS=","} {gsub(/\r/,"")} NR>=66 && NR<=149 && $1=="Karen Purtee" {$1="Helena Cartwright Carlson"} 1' \
  "/Users/aweymouth/Documents/GitHub/oral-history-collections-template/_data/transcripts/carlson_helena_2.csv" > \
  "/Users/aweymouth/Documents/GitHub/oral-history-collections-template/_data/transcripts/tmp.csv" && \
  mv "/Users/aweymouth/Documents/GitHub/oral-history-collections-template/_data/transcripts/tmp.csv" \
     "/Users/aweymouth/Documents/GitHub/oral-history-collections-template/_data/transcripts/carlson_helena_2.csv"

## Add missing punctuation at the end of a row of dialogue (remove period from header after). Does not work if dialogue is missing punctuation inside of dialogue.

python3 -c "
import csv

path = '/Users/aweymouth/Documents/GitHub/oral-history-collections-template/_data/transcripts/holland_joseph_2.csv'

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
