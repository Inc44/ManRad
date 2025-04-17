```bash
docker pull nvidia/cuda:12.6.2-cudnn-devel-ubuntu24.04
docker pull nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04
```

| GPU                        | Driver     | CUDA | Power       |
|----------------------------|------------|------|-------------|
| NVIDIA GeForce RTX 3080    | 570.124.04 | 12.8 | 360W        |
| NVIDIA GeForce RTX 4060 Ti | 570.86.16  | 12.8 | 165W        |
| NVIDIA GeForce RTX 4090    | 560.35.03  | 12.6 | 450W        |
| NVIDIA GeForce RTX 5070 Ti | 570.133.07 | 12.8 | 300W        |
| NVIDIA GeForce RTX 5080    | 570.86.16  | 12.8 | 360W        |
| NVIDIA GeForce RTX 5090    | 570.124.04 | 12.8 | 575W / 600W |

```bash
ssh -i key -p ... root@... -L 8080:localhost:8080
```

```bash
mv /ManRad/Cloud_Environment/ManRadE.zip /workspace
mv /ManRad/Cloud_Environment/ManRadP.zip /workspace
mv /ManRad/Cloud_Environment/ManRadS.zip /workspace
mv /ManRad/Cloud_Environment/ManRadS2.zip /workspace
```

```bash
cd /workspace
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm -rf ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init
exit
```

```bash
cd /workspace
conda create --name test python=3.10 -y
conda activate test
pip install librosa opencv-python pillow
sudo apt install ffmpeg neofetch unzip vim -y
```

```bash
conda install paddlepaddle-gpu==3.0.0b1 paddlepaddle-cuda=12.3 -c paddle -c nvidia -y
pip install opencv-python paddleocr regex tiktoken
```

```bash
unzip ManRadE.zip
unzip ManRadP.zip
unzip ManRadS.zip
unzip ManRadS2.zip
unzip ManRadS3.zip
```

```bash
cd ManRad
```

```bash
nvidia-smi
```

```bash
ffmpeg
```

```bash
neofetch
```

```bash
time prlimit --nofile=4096 python -OO Scroll.py
```

```bash
time prlimit --nofile=4096 python -OO menu.py 15
```

```bash
mv /workspace/ManRad/output/scroll.mkv /ManRad
```