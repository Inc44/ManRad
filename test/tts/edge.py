from Help import process_dir
import edge_tts
import os
import sys


def make_audio(text, out, retry=10, wait=10.0, min_size=256):
	text = text.strip()[:4096]
	TEXT = text
	VOICE = "en-US-AndrewNeural"  # "ru-RU-DmitryNeural"
	OUTPUT_FILE = out
	communicate = edge_tts.Communicate(TEXT, VOICE)
	communicate.save_sync(OUTPUT_FILE)
	if os.path.getsize(out) >= min_size:
		return True
	return False


if __name__ == "__main__":
	if len(sys.argv) > 1:
		process_dir(make_audio, sys.argv[1])
