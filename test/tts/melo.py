import os
import requests
import sys
import time
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Help import process_dir


def make_audio(text, out, retry=10, wait=10.0, min_size=256):
	key = os.environ.get("MELO_API_KEY")
	headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
	text = text.strip()[:4096]
	data = {
		"text": text,
	}
	for _ in range(retry):
		resp = requests.post(
			"https://api.hyperbolic.xyz/v1/audio/generation",
			headers=headers,
			json=data,
			timeout=30,
		)
		if resp.status_code == 200:
			with open(out, "wb") as f:
				f.write(base64.b64decode(resp.json()["audio"]))
			if os.path.getsize(out) >= min_size:
				return True
		time.sleep(wait)
	open(out, "wb").close()
	return False


if __name__ == "__main__":
	if len(sys.argv) > 1:
		process_dir(make_audio, sys.argv[1])
