import config
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
	audio_output_extension,
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
	audio_filename = f"{basename}{audio_output_extension}"
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
	for current_attempt in range(attempt, retries):
		try:
			response = requests.post(api_endpoint, headers=headers, json=payload)
			if response.status_code == 200:
				with open(audio_path, "wb") as f:
					f.write(response.content)
				if is_valid_audio(min_size, audio_path):
					return
		except:
			pass
		if current_attempt < retries - 1:
			sleep_time = pause * (2**current_attempt)
			time.sleep(sleep_time)


def batch_text_to_audio(
	api_endpoint,
	api_key,
	attempt,
	audio_output_extension,
	batch,
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
	for filename in batch:
		text_to_audio(
			api_endpoint,
			api_key,
			attempt,
			audio_output_extension,
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
		)


if __name__ == "__main__":
	api_endpoints = config.API_ENDPOINTS
	api_keys = config.API_KEYS
	audio_min_size = config.AUDIO_MIN_SIZE
	audio_output_extension = config.AUDIO_OUTPUT_EXTENSION
	dirs = config.DIRS
	instructions = config.INSTRUCTIONS
	max_tokens = config.MAX_TOKENS
	models = config.MODELS
	pause = config.PAUSE
	response_format = config.RESPONSE_FORMAT
	retries = config.RETRIES
	voices = config.VOICES
	workers_config = config.WORKERS
	texts = sorted(
		[f for f in os.listdir(dirs["image_text"]) if f.lower().endswith(".json")]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(texts, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				api_endpoints[4],
				api_keys[6],
				0,
				audio_output_extension,
				batch,
				dirs["image_text"],
				instructions[0],
				max_tokens,
				audio_min_size,
				models[1],
				dirs["image_audio"],
				pause,
				response_format[1],
				retries,
				voices[3],
			)
			for batch in batches
		]
		pool.starmap_async(batch_text_to_audio, args).get()
