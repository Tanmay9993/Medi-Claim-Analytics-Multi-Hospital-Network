# Quick start — run Python files with the project venv

Minimal steps to create the venv once and then run any file easily.

## One-time setup (run once)
```bash
cd 

# create virtual environment (one-time)
python3 -m venv .venv

# activate it for this terminal session
source .venv/bin/activate

# install dependencies (if you have requirements.txt)
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt 