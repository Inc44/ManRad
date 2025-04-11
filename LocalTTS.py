from Help import process_dir
import base64
import os
import requests
import time


def audio_to_base64(audio_path):
	if os.path.exists(audio_path):
		with open(audio_path, "rb") as audio_file:
			audio_bytes = audio_file.read()
			return base64.b64encode(audio_bytes).decode("utf-8")
	return None


def make_audio(
	text,
	out,
	retry=5,
	wait=5.0,
	min_size=256,
	reference_audio="reference/reference_audio.flac",
	reference_text_path="reference/reference_text.txt",
	url="http://127.0.0.1:8080/v1/tts",
):
	text = text.strip()[:4096]
	references = []
	reference_text = None
	if os.path.exists(reference_text_path):
		with open(reference_text_path, "r", encoding="utf-8") as f:
			reference_text = f.read().strip()
	audio_base64 = audio_to_base64(reference_audio)
	if reference_audio and reference_text and audio_base64:
		references.append({"audio": audio_base64, "text": reference_text})
	data = {
		"text": text,
		"chunk_length": 4096,
		"format": "wav",
		"references": references,
		"reference_id": None,
		"seed": 42,
		"use_memory_cache": "on",
		"normalize": True,
		"streaming": False,
		"max_new_tokens": 1024,
		"temperature": 0.1,
	}
	headers = {"Content-Type": "application/json"}
	for attempt in range(retry):
		resp = requests.post(
			url,
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
	process_dir(make_audio)
