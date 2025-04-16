from config import (
	API_ENDPOINTS,
	API_KEYS,
	AUDIO_MIN_SIZE,
	DIRS,
	INSTRUCTIONS,
	MAX_TOKENS,
	MODELS,
	PAUSE,
	RESPONSE_FORMAT,
	RETRIES,
	VOICES,
	WORKERS,
)
from _2 import split_batches
from _7 import is_valid_audio, parse_text_json
from multiprocessing import Pool, cpu_count
import os
import requests
import time


def text_to_audio(
	api_endpoint,
	api_key,
	attempt,
	filename,
	input_dir,
	instructions,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	response_format,
	retries,
	voice,
):
	basename = os.path.splitext(filename)[0]
	path = os.path.join(input_dir, filename)
	audio_filename = f"{basename}.wav"
	audio_path = os.path.join(output_dir, audio_filename)
	if is_valid_audio(min_size, audio_path):
		return
	text = parse_text_json(max_tokens, path)
	if len(text) == 0:
		return
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
	payload = {
		"model": model,
		"input": text,
		"voice": voice,
		"response_format": response_format,
	}
	if instructions:
		payload["instructions"] = instructions
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
	api_key,
	attempt,
	batch,
	input_dir,
	instructions,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	retries,
	response_format,
	voice,
):
	for filename in batch:
		text_to_audio(
			api_endpoint,
			api_key,
			attempt,
			filename,
			input_dir,
			instructions,
			max_tokens,
			min_size,
			model,
			output_dir,
			pause,
			retries,
			response_format,
			voice,
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
				API_ENDPOINTS[4],
				API_KEYS[6],
				0,
				batch,
				DIRS["image_text"],
				INSTRUCTIONS[0],
				MAX_TOKENS,
				AUDIO_MIN_SIZE,
				MODELS[1],
				DIRS["image_audio"],
				PAUSE,
				RESPONSE_FORMAT[1],
				RETRIES,
				VOICES[3],
			)
			for batch in batches
		]
		pool.starmap_async(batch_text_to_audio, args).get()
