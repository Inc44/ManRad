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
	text = parse_json(path).replace("\n", " ")
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
	with open(path, "r", encoding="utf-8") as f:
		data = json.load(f)
	if not isinstance(data, list):
		return parse_json(path)
	sorted_blocks = sorted(
		data,
		key=lambda item: (
			item.get("box_2d", [0, 0, 0, 0])[1]
			if isinstance(item, dict) and "box_2d" in item
			else float("inf")
		),
	)
	formatted_blocks = []
	for item in sorted_blocks:
		if not isinstance(item, dict) or "text" not in item:
			continue
		block_text = item["text"].strip()
		if not block_text:
			continue
		if block_text.isupper():
			sentences = re.split(r"([.!?])\s*", block_text.lower())
			fixed_text = ""
			for i in range(0, len(sentences), 2):
				if i >= len(sentences):
					break
				sentence = sentences[i].strip()
				if not sentence:
					continue
				fixed_text += sentence[0].upper() + sentence[1:]
				if i + 1 < len(sentences):
					fixed_text += sentences[i + 1] + " "
		else:
			fixed_text = block_text
		fixed_text = re.sub(r"\n+", " ", fixed_text)
		fixed_text = re.sub(r"\s+", " ", fixed_text)
		formatted_blocks.append(fixed_text.strip())
	return "\n".join(formatted_blocks)
