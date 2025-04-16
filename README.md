## Usage

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
pip install opencv-python paddleocr regex tiktoken
```

Clone the repository:
```bash
git clone https://github.com/Inc44/ManRad.git
```

Navigate to the project directory and run the scripts:
```bash
cd ManRad
python -OO _0.py
python -OO _1.py
python -OO _2.py
python -OO _3.py
python -OO _4.py
python -OO _5.py
python -OO _6.py
python -OO _7.py
python -OO _8.py
python -OO _9.py
python -OO _10.py
python -OO _11.py
python -OO _12.py
python -OO _13.py
python -OO _14.py
```

## Not Implemented / Failed Features

- Autodetect target height and width using the most common dimensions of images.
- Camera movement.
- Create a CLI menu using argparse to select actions with numbers 1 to 15 for individual actions and 0 for auto mode, with a note that it is recommended to define deleted_images.json in advance.
- Create silent audio proportional to the possible duration of missing audio, calculated using the image text length.
- Define the index of selected entries in lists.
- Make the transition duration work for scrolling.
- Neural network classifier for manga pages.
- Return full-page text detection instead of crops as an option.
- Translation.
- Zoom bouncing.

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

---

Shield: [![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg