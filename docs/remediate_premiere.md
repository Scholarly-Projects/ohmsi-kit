# Remediate Premiere Transcripts

## Remove Millisecond from Timestamps

_Windows:_

```bash
sed -i 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /c/Users/GitHubName/Documents/github/ohmsi-kit/B/example_transcript.csv
```

_Mac:_

```bash
sed -i '' 's/\([0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}\):[0-9]\{2\}/\1/g' /Users/GitHubName/Documents/GitHub/ohmsi-kit/B/example_transcript.csv
```

## Switch Columns C and D for Copy Editing Dialogue

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

## Remove Empty Rows Between Dialogue (occasional Premiere bug)

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

## Capitalize First Letter in a New Row of Dialogue (occasional Premiere and Whisper bug)

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
