## Usage
```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install seaborn
```

```
setx /M API_KEY ""
echo %API_KEY%
```

```
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:v0.2.2
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
pip install edge-tts
```

```
docker run -it --name fish-speech --gpus all -p 8080:8080 fishaudio/fish-speech:latest-dev zsh
python -m tools.api_server --listen 0.0.0.0:8080 --compile
```