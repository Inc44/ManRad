# ManRad

ManRad is an experimental AI project that attempts to read aloud manga, manhwa, and manhua from images (or, as I call it, "bullshit spaghetti code that somehow works"). The goal is to determine whether it is possible to replace voice acting and achieve comparable quality. To accomplish this, it leverages OCR tools such as PaddleOCR and Gemini for text detection, LLMs with vision support from DeepInfra, Gemini, OpenAI, and Mistral for text recognition, and TTS models such as Fish Speech, OpenAI, Kokoro, Hyperbolic, and Lemon, while exploring alternatives like CSM, Edge, Melo, OpenVoice, and Saifs (possibly Oute, Orpheus, and XTTS) to find the highest quality and most cost-effective solution. We are also exploring cloud computing opportunities using Hyperbolic and Vast.ai. This code may eventually be rewritten entirely in Python or C++ (possibly Rust or Go).

## Install

Set your API keys as environment variables:
```batch
setx /M DEEPINFRA_API_KEY ""
setx /M GEMINI_API_KEY ""
setx /M LEMON_API_KEY ""
setx /M MELO_API_KEY ""
setx /M MISTRAL_API_KEY ""
setx /M OPENAI_API_KEY ""
```

Verify that your environment variables are set:
```batch
echo %DEEPINFRA_API_KEY%
echo %GEMINI_API_KEY%
echo %LEMON_API_KEY%
echo %MELO_API_KEY%
echo %MISTRAL_API_KEY%
echo %OPENAI_API_KEY%
```

Create and activate a new Conda environment, then install the required packages:
```bash
conda create --name ManRad python=3.10 -y
conda activate ManRad
conda install paddlepaddle-gpu==3.0.0b1 paddlepaddle-cuda=12.3 -c paddle -c nvidia -y
pip install -r requirements.txt
```

Clone the repository:
```bash
git clone https://github.com/Inc44/ManRad.git
```

## Usage

Navigate to the project directory and run the scripts:
```bash
cd ManRad
python -OO menu.py ACTION --source PATH --mode save/delete
```

## Fish Speech

### Install

#### Docker

```
docker run -it --name fish-speech --gpus all -p 8080:8080 fishaudio/fish-speech:v1.5.0 zsh
```

##### Usage

```
python -m tools.api_server --listen 0.0.0.0:8080 --compile
```

#### Conda
```
conda create -n fish-speech python=3.10 -y
conda activate fish-speech
git clone https://github.com/fishaudio/fish-speech.git
cd fish-speech
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
pip install -e .
pip install https://github.com/AnyaCoder/fish-speech/releases/download/v0.1.0/triton_windows-0.1.0-py3-none-any.whl
huggingface-cli download fishaudio/fish-speech-1.5 --local-dir checkpoints/fish-speech-1.5
```

##### Usage

```
conda activate fish-speech
cd fish-speech
python -O tools/api_server.py --listen 0.0.0.0:8080 --compile
```

## Manga Source

1. Use **Kotatsu** or **HakuNeko** (on Android or PC) to download the full manga.
2. Navigate to the Android `data` folder or your PC's `Documents` folder.
3. Locate the `.cbz` or image files.
4. Copy the directory or files into the project directory.

### Kotatsu

```bash
java -jar ./kotatsu-dl.jar mangadex.org --format=cbz|zip|dir --dest ManRad
```

### HakuNeko

- Manga List > Website > ReManga
- Settings:
    - Manga Directory: `ManRad`
    - Chapter File Format: `Comic Book Archive` or `Folder with Images`
    - De-Scrambling Format: `JPEG`
    - De-Scrambling Quality: `100`

## Achievements

- Achieved relatively good, inexpensive text recognition using LLaMA 4 Scout on DeepInfra for just $0.35 for 15,000 images, and it is quite fast.
- Achieved somewhat unstable, local, multilingual audio using Fish Speech 1.5, which takes approximately 5 hours and 30 minutes to generate about 14 hours of audio on an RTX 4060 Ti 16GB, which is a bit too slow.
- Achieved stable but expensive audio using OpenAI TTS-1, costing about $8 for the same task.

| Name        | Price      | Type       | Eng Only | Voice Clone |
|-------------|------------|------------|----------|-------------|
| 11ElevenLabs| $100       | API        | NO       | YES         |
| MINIMAX     | $18.5      | API        | NO       | YES         |
| OpenAI      | $4         | API        | NO       | NO          |
| GPT-4o      | $3         | API        | NO       | NO          |
| Lemonfox    | $1.5       | API        | YES      | NO          |
| Melo        | $1.3/Free  | API/Local  | YES      | NO          |
| Kokoro      | $0.5/Free  | API/Local  | YES      | NO          |
| Bark        | Free       | Local      | NO       | NO          |
| CSM         | Free       | Local      | YES      | YES         |
| E2/F5       | Free       | Local      | YES      | YES         |
| Edge        | Free*      | API        | NO       | NO          |
| OpenVoice   | Free       | Local      | YES      | YES         |
| Parler      | Free       | Local      | YES      | NO          |
| Saifs       | Free*      | API        | NO       | NO          |
| Spark       | Free       | Local      | YES      | YES         |
| XTTS        | Free       | Local      | NO       | YES         |

## Problems

### Bugs

- Image sorting issues need to be resolved, likely using natural sort and image extensions.
- Scrolling depends on fade.

### TODO/Not Implemented

- Ensure transition duration works for scrolling.
- Generate silent audio proportional to the estimated duration of missing audio, calculated based on the image text length.
- Improve performance.
- Provide an option to return full-page text detection instead of cropped sections (regression).
- Specify the index of selected entries in lists.

### Failed Features

- Add translation functionality.
- Automatically detect target height and width using the most common image dimensions.
- Enable camera movement.
- Fix zoom bouncing.
- Implement a neural network classifier for manga pages.
- Improve height and width detection without loading the entire image.

## License

[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg

## Support

![BuyMeACoffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)
![Ko-Fi](https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)
![Patreon](https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white)