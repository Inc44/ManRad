## Usage
```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install seaborn
```

```
pip install paddlepaddle-gpu==3.0.0rc1 -i https://www.paddlepaddle.org.cn/packages/stable/cu123
pip install paddleocr
```

```
setx /M LEMON_API_KEY ""
echo %LEMON_API_KEY%
```

```
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:v0.2.2
```

```
setx /M MELO_API_KEY ""
echo %MELO_API_KEY%
```

```
git clone https://github.com/myshell-ai/OpenVoice.git ...
cd OpenVoice || cd ManRad/test/tts
```

```
conda create -n openvoice python=3.10 -y
conda activate openvoice
pip install -e .
pip install git+https://github.com/myshell-ai/MeloTTS.git
python -m unidic download
pip install -U torch --index-url https://download.pytorch.org/whl/cu126
```

```
pip install mistralai
```

```
setx /M MISTRAL_API_KEY ""
echo %MISTRAL_API_KEY%
```

```
pip install edge-tts
```

```
conda activate ManRad
python -OO Audio.py
conda activate paddle
python -OO Delta.py
conda activate ManRad
python -OO Scroll.py
ffmpeg -i output/scroll.mkv -i output/audio.wav -c copy output/result.mkv
ffprobe -i output/audio.opus
ffprobe -i output/scroll.mkv
ffprobe -i output/result.mkv
```