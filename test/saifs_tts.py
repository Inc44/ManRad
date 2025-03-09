import glob
import json
import os
import requests


def make_audio(text, out_path):
	if not text or text.strip() == "":
		with open(out_path, "wb") as f:
			f.write(b"")
		return out_path
	form = {"text": text.strip(), "language_id": "en", "voice_id": "male"}
	resp = requests.post("https://shorts.multiplewords.com/mwvideos/api/text_to_voice", data=form)
	if resp.status_code == 200:
		data = resp.json()
		if data.get("status") == "success" and data.get("access_url"):
			audio = requests.get(data["access_url"])
			if audio.status_code == 200:
				with open(out_path, "wb") as f:
					f.write(audio.content)
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
	mp3_dir = os.path.join(in_dir, "mp3")
	if not os.path.isdir(json_dir):
		return []
	if not os.path.exists(mp3_dir):
		os.makedirs(mp3_dir)
	files = glob.glob(os.path.join(json_dir, "*.json"))
	results = []
	for file in sorted(files):
		name = os.path.splitext(os.path.basename(file))[0]
		out_path = os.path.join(mp3_dir, f"{name}.mp3")
		text = parse_json(file).replace("\n", " ")
		make_audio(text, out_path)
		results.append({"json": file, "audio": out_path})
	return results


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		process_dir(sys.argv[1])
