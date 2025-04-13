from _1 import DIRS
from _2 import split_batches
from multiprocessing import Pool, cpu_count
import base64
import json
import os
import regex
import requests
import time

API_ENDPOINT = "http://127.0.0.1:8080/v1/tts"
MAX_TOKENS = 2000
MIN_SIZE = 78
PAUSE = 10
REFERENCE_AUDIO = "reference/reference_audio.flac"
REFERENCE_TEXT = "reference/reference_text.txt"
RETRIES = 3
TEMPERATURE = 0.1
WORKERS = 6


def parse_text_json(max_tokens, path):
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


def is_valid_audio(min_size, path):
	return os.path.exists(path) and os.stat(path).st_size >= min_size


def text_to_audio(
	api_endpoint,
	attempt,
	filename,
	input_dir,
	max_tokens,
	min_size,
	output_dir,
	pause,
	reference_audio_path,
	reference_text_path,
	retries,
	temperature,
):
	basename = os.path.basename(filename)
	path = os.path.join(input_dir, filename)
	audio_filename = f"{basename}.wav"
	audio_path = os.path.join(output_dir, audio_filename)
	if is_valid_audio(min_size, audio_path):
		return
	text = parse_text_json(max_tokens, path)
	if len(text) == 0:
		return
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
	for attempt in range(attempt, retries):
		try:
			response = requests.post(api_endpoint, headers=headers, json=payload)
			if response.status_code == 200:
				with open(audio_path, "wb") as f:
					f.write(response.content)
				if is_valid_audio(min_size, audio_path):
					return
		except:
			pass
		if attempt < retries - 1:
			sleep_time = pause * (2**attempt)
			time.sleep(sleep_time)


def batch_text_to_audio(
	api_endpoint,
	attempt,
	batch,
	input_dir,
	max_tokens,
	min_size,
	output_dir,
	pause,
	reference_audio_path,
	reference_text_path,
	retries,
	temperature,
):
	for filename in batch:
		text_to_audio(
			api_endpoint,
			attempt,
			filename,
			input_dir,
			max_tokens,
			min_size,
			output_dir,
			pause,
			reference_audio_path,
			reference_text_path,
			retries,
			temperature,
		)


if __name__ == "__main__":
	texts = sorted(
		[f for f in os.listdir(DIRS["image_text"]) if f.lower().endswith(".json")]
	)
	workers = min(WORKERS, cpu_count())
	batches = split_batches(workers, texts)
	with Pool(processes=workers) as pool:
		args = [
			(
				API_ENDPOINT,
				0,
				batch,
				DIRS["image_text"],
				MAX_TOKENS,
				MIN_SIZE,
				DIRS["image_audio"],
				PAUSE,
				REFERENCE_AUDIO,
				REFERENCE_TEXT,
				RETRIES,
				TEMPERATURE,
			)
			for batch in batches
		]
		pool.starmap_async(batch_text_to_audio, args).get()
