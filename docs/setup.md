# Setup

## Mac

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

### Run Script(s)

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

## Windows

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

### Run Script(s)

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
