from manrad0 import DIRS
from manrad1 import batches_distribute
from multiprocessing import Pool, cpu_count
import base64
import json
import os
import regex
import requests
import time

API_ENDPOINT = "https://api.deepinfra.com/v1/openai/chat/completions"
API_KEY = os.environ.get("DEEPINFRA_API_KEY")
CORES = 6
LANGUAGE = "Russian"
MAX_TOKENS = 2000
MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
PAUSE = 10
PROMPT = f'Proofread this text in {LANGUAGE} but only fix grammar without any introductory phrases or additional commentary. If no readable text is found, the text content is empty. Return JSON: [{{"text": "text content"}}, ...]'
RETRIES = 3
TEMPERATURE = 0.0
TEMPERATURE_INCREASE = 0.2


def sanitized_parse_json(string):
	string = regex.sub(r"[\x00-\x1F\x7F]", "", string)
	string = regex.sub(r"[^\p{Latin}\p{Cyrillic}\p{N}\p{P}\p{Z}]", "", string)
	try:
		return json.loads(string)
	except:
		matches = regex.findall(r'"text"\s*:\s*"([^"]*)"', string)
		if matches:
			return [{"text": match} for match in matches]
		return [{"text": ""}] if '"text"' in string else []


def img_text(
	api_endpoint,
	api_key,
	attempt,
	filename,
	input_dir,
	max_tokens,
	model,
	output_dir_text,
	pause,
	prompt,
	retries,
	temperature,
	temperature_increase,
):
	if attempt >= retries:
		return []
	basename, _ = os.path.splitext(filename)
	path = os.path.join(input_dir, filename)
	text_filename = f"{basename}.json"
	text_path = os.path.join(output_dir_text, text_filename)
	if valid(text_path):
		return
	with open(path, "rb") as f:
		img = base64.b64encode(f.read()).decode()
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
	payload = {
		"model": model,
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": prompt},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/jpeg;base64,{img}"},
					},
				],
			}
		],
		"temperature": temperature,
		"max_tokens": max_tokens,
	}
	try:
		response = requests.post(api_endpoint, headers=headers, json=payload)
		if response.status_code == 200:
			content = response.json()["choices"][0]["message"]["content"]
			start = content.find("[")
			end = content.rfind("]") + 1
			if start >= 0 and end > start:
				sanitized_json = sanitized_parse_json(content[start:end])
				if (
					sanitized_json
					and len(str(sanitized_json)) > 12
					and isinstance(sanitized_json, list)
					and all(isinstance(item, dict) for item in sanitized_json)
				):
					with open(text_path, "w", encoding="utf-8") as f:
						json.dump(sanitized_json, f, indent="\t", ensure_ascii=False)
					return
	except:
		pass
	time.sleep(pause)
	return img_text(
		api_endpoint,
		api_key,
		attempt + 1,
		filename,
		input_dir,
		max_tokens,
		model,
		output_dir_text,
		pause * 2,
		prompt,
		retries,
		temperature + (attempt * temperature_increase),
		temperature_increase,
	)


def valid(path):
	if not os.path.exists(path) or os.stat(path).st_size < 13:
		return False
	try:
		with open(path, encoding="utf-8") as f:
			string = json.load(f)
		return isinstance(string, list) and string
	except:
		return False


def batch_img_text(
	api_endpoint,
	api_key,
	attempt,
	batch,
	input_dir,
	max_tokens,
	model,
	output_dir_text,
	pause,
	prompt,
	retries,
	temperature,
	temperature_increase,
):
	for filename in batch:
		img_text(
			api_endpoint,
			api_key,
			attempt,
			filename,
			input_dir,
			max_tokens,
			model,
			output_dir_text,
			pause,
			prompt,
			retries,
			temperature,
			temperature_increase,
		)


if __name__ == "__main__":
	imgs = sorted(
		[f for f in os.listdir(DIRS["img_crops"]) if f.lower().endswith(".jpg")]
	)
	cores = min(CORES, 10 * cpu_count())
	batches = batches_distribute(cores, imgs)
	with Pool(processes=cores) as pool:
		args = [
			(
				API_ENDPOINT,
				API_KEY,
				0,
				batch,
				DIRS["img_crops"],
				MAX_TOKENS,
				MODEL,
				DIRS["img_text"],
				PAUSE,
				PROMPT,
				RETRIES,
				TEMPERATURE,
				TEMPERATURE_INCREASE,
			)
			for batch in batches
		]
		pool.starmap_async(batch_img_text, args).get()
