from Help import process_dir
import base64
import os
import requests
import sys
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
	reference_audio="g:/My Drive/Files/Else/AI/llElevenLabs/Voice Cloning/Source/De.flac",
	reference_text="Der nationalen Regierung auf den Gebieten des wirtschaftlichen Lebens. Hier wird ein Gesetz alles Handeln bestimmen. Das Volk lebt nicht für die Wirtschaft, und die Wirtschaft existiert nicht für das Kapital, sondern das Kapital dient der Wirtschaft und die Wirtschaft dem Volk. So ist es! Und der Bruch der uns in den 14 Punkten Wilsons gemachten Zusicherungen begann für Deutschland, das heißt für das schaffende deutsche Volk, eine Zeit grenzenlosen Unglücks. Er wäre auch ohne Weiteres bereit, seine gesamte militärische Einrichtung überhaupt aufzulösen und den kleinen Rest der ihm verbliebenen Waffen zu zerstören, wenn die anliegenden Nationen ebenso rechnen.",
	url="http://127.0.0.1:8080/v1/tts",
):
	text = text.strip()[:4096]
	references = []
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
	if len(sys.argv) > 1:
		process_dir(make_audio, sys.argv[1])
