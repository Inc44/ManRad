## Usage
```
setx /M OPENAI_API_KEY ""
setx /M GEMINI_API_KEY ""
setx /M DEEPINFRA_API_KEY ""
```

```
echo %OPENAI_API_KEY%
echo %GEMINI_API_KEY%
echo %DEEPINFRA_API_KEY%
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
python -OO Delete.py .
python -OO Evaluate.py .
python -OO Extract.py .
python -OO TTS.py .
python -OO Video.py .
```
## TODO
- All-in-one script
- Local TTS and LLM
- Parallel requests
- Result verification via JSON and WAV min size

## Failed
- Camera movement
- Neural network classifier for manga pages
- Scroll manga
- Translation
- Zoom bouncing

## Manga Source
1. Use **Kotatsu** on Android to download the full manga.
2. Navigate to the Android data folder.
3. Locate and zip the **CBZ** files.
4. Copy the `.zip` file to the project directory.