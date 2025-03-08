## Usage
```
setx /M OPENAI_API_KEY ""
setx /M GEMINI_API_KEY ""
```

```
echo %OPENAI_API_KEY%
echo %GEMINI_API_KEY%
```

```
conda create --name ManRad python=3.10 -y
conda activate ManRad
pip install librosa tiktoken
```

```
git clone https://github.com/Inc44/ManRad.git
```

```
cd ManRad
python -OO Prepare.py .zip
python -OO Evaluate.py .
python -OO Extract.py .
python -OO TTS.py .
python -OO Video.py .
```
## TODO
- All-in-one script
- Parallel requests
- Result verification via JSON and WAV min size

## Failed
- Camera movement
- Neural network classifier for manga pages
- Scroll manga
- Zoom bouncing