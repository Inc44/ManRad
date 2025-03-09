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