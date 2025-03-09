import concurrent.futures
import glob
import json
import os
import requests
import time


def make_audio(text, out, retry=10, wait=10.0, min_size=256):
	key = os.environ.get("LEMON_API_KEY")
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
			"https://api.lemonfox.ai/v1/audio/speech",
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


def parse_json(path):
	with open(path, "r", encoding="utf-8") as f:
		data = json.load(f)
	if isinstance(data, list):
		return " ".join(
			item.get("text", "") for item in data if isinstance(item, dict)
		).strip()
	if isinstance(data, dict):
		return data.get("text", "").strip()
	return ""


def is_valid(path, min_size=256):
	return os.path.exists(path) and os.path.getsize(path) >= min_size


def process_file(path, out_dir):
	name = os.path.splitext(os.path.basename(path))[0]
	out = os.path.join(out_dir, f"{name}.wav")
	if is_valid(out):
		return {"file": path, "audio": out, "status": "skipped"}
	text = parse_json(path).replace("\n", " ")
	ok = make_audio(text, out)
	status = "created" if ok else "failed"
	return {"file": path, "audio": out, "status": status}


def process_dir(base, workers=10):
	if not os.path.isdir(base):
		return []
	json_dir = os.path.join(base, "json")
	wav_dir = os.path.join(base, "wav")
	if not os.path.isdir(json_dir):
		return []
	os.makedirs(wav_dir, exist_ok=True)
	files = sorted(glob.glob(os.path.join(json_dir, "*.json")))
	results = []
	with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
		futures = [pool.submit(process_file, f, wav_dir) for f in files]
		for future in concurrent.futures.as_completed(futures):
			results.append(future.result())
	return results


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		process_dir(sys.argv[1])
