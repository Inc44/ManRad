from _1 import DIRS
from _2 import split_batches
from _5 import is_valid_audio, parse_text_json
from multiprocessing import Pool, cpu_count
import os
import requests
import time

API_ENDPOINTS = ["https://api.openai.com/v1/audio/speech"]
API_KEYS = [os.environ.get("OPENAI_API_KEY")]
INSTRUCTIONS = [
	"",
	"Speak in an emotive and friendly tone... Read only if the text is in Russian",
	"Speak with intonation and emotions in the given sentences from the intense manga.",
]
MAX_TOKENS = 2000
MIN_SIZE = 78
MODELS = ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]
PAUSE = 10
RETRIES = 3
VOICES = ["sage", "ash", "onyx"]
WORKERS = 6


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
	retries,
	voice,
):
	basename, _ = os.path.splitext(filename)
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
		"response_format": "wav",
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
				API_ENDPOINTS[0],
				API_KEYS[0],
				0,
				batch,
				DIRS["image_text"],
				INSTRUCTIONS[0],
				MAX_TOKENS,
				MIN_SIZE,
				MODELS[0],
				DIRS["image_audio"],
				PAUSE,
				RETRIES,
				VOICES[0],
			)
			for batch in batches
		]
		pool.starmap_async(batch_text_to_audio, args).get()
