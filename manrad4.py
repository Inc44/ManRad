import json
from manrad0 import DIRS
from manrad1 import batches_distribute
from multiprocessing import Pool, cpu_count
import base64
import os
import requests
import regex
import time

API_ENDPOINT = "http://127.0.0.1:8080/v1/tts"
CORES = 6
MAX_TOKENS = 2000
MIN_SIZE = 78
PAUSE = 10
REFERENCE_AUDIO = "reference/reference_audio.flac"
REFERENCE_TEXT = "reference/reference_text.txt"
RETRIES = 3
TEMPERATURE = 0.1


def parse_json(path, max_tokens):
	with open(path, "r", encoding="utf-8") as f:
		data = json.load(f)
	if isinstance(data, list):
		text = " ".join(item.get("text", "") for item in data if isinstance(item, dict))
	elif isinstance(data, dict):
		text = data.get("text", "")
	else:
		return ""
	text = text.replace("- ", "")
	text = regex.sub(r"\s+", " ", text).strip()
	if text:
		text = text[0].upper() + text[1:]
	return text[: max_tokens * 2]


def img_audio(
	api_endpoint,
	attempt,
	filename,
	input_dir,
	max_tokens,
	min_size,
	output_dir_audio,
	pause,
	reference_audio_path,
	reference_text_path,
	retries,
	temperature,
):
	if attempt >= retries:
		return []
	basename, _ = os.path.splitext(filename)
	path = os.path.join(input_dir, filename)
	audio_filename = f"{basename}.wav"
	audio_path = os.path.join(output_dir_audio, audio_filename)
	if valid_audio(audio_path, min_size):
		return
	text = parse_json(path, max_tokens)
	with open(reference_text_path, "r", encoding="utf-8") as f:
		reference_text = f.read().strip()
	with open(reference_audio_path, "rb") as f:
		reference_audio = base64.b64encode(f.read()).decode()
	references = []
	if reference_text and reference_audio:
		references.append({"audio": reference_audio, "text": reference_text})
	headers = {"Content-Type": "application/json"}
	payload = {
		"chunk_length": max_tokens * 2,
		"format": "wav",
		"max_new_tokens": max_tokens,
		"normalize": True,
		"reference_id": None,
		"references": references,
		"seed": 42,
		"streaming": False,
		"temperature": temperature,
		"text": text,
		"use_memory_cache": "on",
	}
	try:
		response = requests.post(api_endpoint, headers=headers, json=payload)
		if response.status_code == 200:
			with open(audio_path, "wb") as f:
				f.write(response.content)
			if valid_audio(audio_path, min_size):
				return
	except:
		pass
	time.sleep(pause)
	return img_audio(
		api_endpoint,
		attempt + 1,
		filename,
		input_dir,
		max_tokens,
		min_size,
		output_dir_audio,
		pause * 2,
		reference_audio_path,
		reference_text_path,
		retries,
		temperature,
	)


def valid_audio(path, min_size):
	return os.path.exists(path) and os.stat(path).st_size >= min_size


def batch_img_audio(
	api_endpoint,
	attempt,
	batch,
	input_dir,
	max_tokens,
	min_size,
	output_dir_audio,
	pause,
	reference_audio_path,
	reference_text_path,
	retries,
	temperature,
):
	for filename in batch:
		img_audio(
			api_endpoint,
			attempt,
			filename,
			input_dir,
			max_tokens,
			min_size,
			output_dir_audio,
			pause,
			reference_audio_path,
			reference_text_path,
			retries,
			temperature,
		)


if __name__ == "__main__":
	# Audio
	texts = sorted(
		[f for f in os.listdir(DIRS["img_text"]) if f.lower().endswith(".json")]
	)
	cores = min(CORES, cpu_count())
	batches = batches_distribute(cores, texts)
	with Pool(processes=cores) as pool:
		args = [
			(
				API_ENDPOINT,
				0,
				batch,
				DIRS["img_text"],
				MAX_TOKENS,
				MIN_SIZE,
				DIRS["img_audio"],
				PAUSE,
				REFERENCE_AUDIO,
				REFERENCE_TEXT,
				RETRIES,
				TEMPERATURE,
			)
			for batch in batches
		]
		# pool.starmap_async(batch_img_audio, args).get()
		batch_img_audio(*args[0])
