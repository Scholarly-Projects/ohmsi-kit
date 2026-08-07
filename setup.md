## setup (mac)

brew install pyenv

pyenv versions          # check if a 3.11.x is already installed

pyenv install 3.11.9    # skip this step if 3.11.x already shows up above

~/.pyenv/versions/3.11.9/bin/python -m venv .venv

source .venv/bin/activate

python --version 

_should print Python 3.11.x (any 3.11 patch version works — wheels for torch==2.1.0 are built per minor version, not patch)_

pip install --upgrade pip

pip install -r requirements.txt

### Run Script(s)

python script_

_Keep device and/or display awake while processing_

caffeinate -s python script_

caffeinate -di python script_

_Or run multiple scripts on the same audio files_

caffeinate -di bash -c '
python script_a.py;
python script_b.py;
python script_c.py;
python script_d.py;
python script_e.py;
python script_f.py
'

_More information on workflow included in the README_
