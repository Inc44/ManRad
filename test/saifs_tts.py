import glob
import os
import requests
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Help import format


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


def process_dir(make_audio, in_dir):
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
		text = format(file)
		make_audio(text, out_path)
		results.append({"json": file, "audio": out_path})
	return results


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		process_dir(make_audio, sys.argv[1])
