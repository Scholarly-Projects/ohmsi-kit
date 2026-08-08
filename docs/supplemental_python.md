# Supplemental Python Workflows

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
