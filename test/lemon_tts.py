import glob
import json
import os
import requests


def make_audio(text, out_path):
	if not text or text.strip() == "":
		with open(out_path, "wb") as f:
			f.write(b"")
		return out_path
	key = 'YTrijnmU56BLmbePlXmo7XxldhHOQTkk'
	if not key:
		with open(out_path, "wb") as f:
			f.write(b"")
		return out_path
	headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
	text = text.strip()[:4096]
	payload = {
		"model": "tts-1",
		"input": text,
		"voice": "ash",
		"response_format": "wav"
	}
	resp = requests.post(
		"https://api.lemonfox.ai/v1/audio/speech", headers=headers, json=payload
	)
	with open(out_path, "wb") as f:
		f.write(resp.content if resp.status_code == 200 else b"")
	return out_path


def parse_json(path):
	with open(path, "r") as f:
		data = json.load(f)
	text = ""
	if isinstance(data, list):
		text = " ".join(item.get("text", "") for item in data if isinstance(item, dict))
	elif isinstance(data, dict):
		text = data.get("text", "")
	return text.strip()


def process_dir(in_dir):
	if not os.path.isdir(in_dir):
		return []
	json_dir = os.path.join(in_dir, "json")
	wav_dir = os.path.join(in_dir, "wav")
	if not os.path.isdir(json_dir):
		return []
	if not os.path.exists(wav_dir):
		os.makedirs(wav_dir)
	files = glob.glob(os.path.join(json_dir, "*.json"))
	results = []
	for file in sorted(files):
		name = os.path.splitext(os.path.basename(file))[0]
		out_path = os.path.join(wav_dir, f"{name}.wav")
		text = parse_json(file).replace("\n", " ")
		make_audio(text, out_path)
		results.append({"json": file, "audio": out_path})
	return results


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		process_dir(sys.argv[1])
