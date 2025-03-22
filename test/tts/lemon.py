import os
import requests
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Help import process_dir


def make_audio(text, out, retry=10, wait=10.0, min_size=256):
	key = os.environ.get("LEMON_API_KEY")
	headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
	text = text.strip()[:4096]
	data = {
		"model": "tts-1",
		"input": text,
		"voice": "onyx",
		"response_format": "wav",
	}
	for _ in range(retry):
		resp = requests.post(
			"https://api.lemonfox.ai/v1/audio/speech",
			headers=headers,
			json=data,
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
