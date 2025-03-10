import concurrent.futures
import glob
import json
import os
import re


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


def process_file(make_audio, path, out_dir):
	name = os.path.splitext(os.path.basename(path))[0]
	out = os.path.join(out_dir, f"{name}.wav")
	if is_valid(out):
		return {"file": path, "audio": out, "status": "skipped"}
	text = format(path)
	ok = make_audio(text, out)
	status = "created" if ok else "failed"
	return {"file": path, "audio": out, "status": status}


def process_dir(make_audio, base, workers=10):
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
		futures = [pool.submit(process_file, make_audio, f, wav_dir) for f in files]
		for future in concurrent.futures.as_completed(futures):
			results.append(future.result())
	return results


def format(path):
	return parse_json(path).capitalize().replace("\n", " ")
