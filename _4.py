from _0 import DIRS
from _2 import split_batches
from multiprocessing import Pool, cpu_count
import base64
import json
import os
import regex
import requests
import time

API_ENDPOINT = "https://api.deepinfra.com/v1/openai/chat/completions"
API_KEY = os.environ.get("DEEPINFRA_API_KEY")
LANGUAGE = "Russian"
MAX_TOKENS = 2000
MIN_SIZE = 13
MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
PAUSE = 10
PROMPT = f'Proofread this text in {LANGUAGE} but only fix grammar without any introductory phrases or additional commentary. If no readable text is found, the text content is empty. Return JSON: [{{"text": "text content"}}, ...]'
RETRIES = 3
TEMPERATURE = 0.0
TEMPERATURE_STEP = 0.2
WORKERS = 60


def parse_json_text(string):
	string = regex.sub(r"[\x00-\x1F\x7F]", "", string)
	string = regex.sub(r"[^A-Za-z\p{Cyrillic}\p{N}\p{P}\p{Z}]", "", string)
	try:
		return json.loads(string)
	except:
		matches = regex.findall(r'"text"\s*:\s*"([^"]*)"', string)
		if matches:
			return [
				{
					"text": bytes(match, "utf-8").decode("unicode_escape")
					if "\\u" in match
					else match
				}
				for match in matches
			]
		return [{"text": ""}] if '"text"' in string else []


def is_valid_json(min_size, path):
	if not os.path.exists(path) or os.stat(path).st_size < min_size:
		return False
	try:
		with open(path, encoding="utf-8") as f:
			data = json.load(f)
		return isinstance(data, list) and data
	except:
		return False


def image_to_text(
	api_endpoint,
	api_key,
	attempt,
	filename,
	input_dir,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	prompt,
	retries,
	temperature,
	temperature_step,
):
	if attempt >= retries:
		return []
	basename = os.path.splitext(filename)[0]
	path = os.path.join(input_dir, filename)
	text_filename = f"{basename}.json"
	text_path = os.path.join(output_dir, text_filename)
	if is_valid_json(min_size, text_path):
		return
	with open(path, "rb") as f:
		image = base64.b64encode(f.read()).decode()
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
	payload = {
		"max_tokens": max_tokens,
		"model": model,
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": prompt},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/jpeg;base64,{image}"},
					},
				],
			}
		],
		"seed": 42,
		"temperature": temperature,
	}
	for attempt in range(attempt, retries):
		try:
			payload["temperature"] = temperature
			response = requests.post(api_endpoint, headers=headers, json=payload)
			if response.status_code == 200:
				content = response.json()["choices"][0]["message"]["content"]
				start = content.find("[")
				end = content.rfind("]") + 1
				if start >= 0 and end > start:
					parsed = parse_json_text(content[start:end])
					if (
						parsed
						and len(str(parsed)) >= min_size
						and isinstance(parsed, list)
						and all(isinstance(item, dict) for item in parsed)
					):
						with open(text_path, "w", encoding="utf-8") as f:
							json.dump(parsed, f, indent="\t", ensure_ascii=False)
						return
		except:
			pass
		if attempt < retries - 1:
			sleep_time = pause * (2**attempt)
			temperature += temperature_step
			time.sleep(sleep_time)


def batch_image_to_text(
	api_endpoint,
	api_key,
	attempt,
	batch,
	input_dir,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	prompt,
	retries,
	temperature,
	temperature_step,
):
	for filename in batch:
		image_to_text(
			api_endpoint,
			api_key,
			attempt,
			filename,
			input_dir,
			max_tokens,
			min_size,
			model,
			output_dir,
			pause,
			prompt,
			retries,
			temperature,
			temperature_step,
		)


if __name__ == "__main__":
	images = sorted(
		[f for f in os.listdir(DIRS["image_crops"]) if f.lower().endswith(".jpg")]
	)
	workers = min(WORKERS, 10 * cpu_count())
	batches = split_batches(workers, images)
	with Pool(processes=workers) as pool:
		args = [
			(
				API_ENDPOINT,
				API_KEY,
				0,
				batch,
				DIRS["image_crops"],
				MAX_TOKENS,
				MIN_SIZE,
				MODEL,
				DIRS["image_text"],
				PAUSE,
				PROMPT,
				RETRIES,
				TEMPERATURE,
				TEMPERATURE_STEP,
			)
			for batch in batches
		]
		pool.starmap_async(batch_image_to_text, args).get()
