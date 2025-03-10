from Help import process_dir
import os
import requests
import sys
import time


def make_audio(text, out, retry=10, wait=10.0, min_size=256):
	key = os.environ.get("OPENAI_API_KEY")
	headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
	text = text.strip()[:4096]
	data = {
		"model": "tts-1",
		"input": text,
		"voice": "ash",
		"response_format": "wav",
	}
	for _ in range(retry):
		resp = requests.post(
			"https://api.openai.com/v1/audio/speech",
			headers=headers,
			json=data,
			timeout=30,
		)
		if resp.status_code == 200:
			with open(out, "wb") as f:
				f.write(resp.content)
			if os.path.getsize(out) >= min_size:
				return True
		time.sleep(wait)
	open(out, "wb").close()
	return False


if __name__ == "__main__":
	if len(sys.argv) > 1:
		process_dir(make_audio, sys.argv[1])
