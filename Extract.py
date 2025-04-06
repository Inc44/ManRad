from pathlib import Path
import base64
import json
import os
import random
import regex
import requests
import sys
import time
import threading

KEY = os.environ.get("DEEPINFRA_API_KEY")
MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
LANGUAGE = "Russian"
PROMPT = f'Proofread this text in {LANGUAGE} but only fix grammar without any introductory phrases or additional commentary. If no readable text is found, the text content is empty. Return JSON: [{{"text": "text content"}}, ...]'
ENDPOINT = "https://api.deepinfra.com/v1/openai/chat/completions"
RETRY = 3
WAIT = 6
CONCURRENT = 150
BASE_TEMPERATURE = 0.0
TEMPERATURE_INCREASE = 0.1
file_list_lock = threading.Lock()


def sanitize_json_string(json_str):
	fixed = regex.sub(r"\\u[^0-9a-fA-F]{4}", "", json_str)
	fixed = regex.sub(r"[\x00-\x1F\x7F]", "", fixed)
	return fixed


def safe_json_loads(json_str):
	try:
		return json.loads(json_str)
	except json.JSONDecodeError:
		try:
			sanitized = sanitize_json_string(json_str)
			return json.loads(sanitized)
		except json.JSONDecodeError:
			if '"text"' in json_str:
				return [{"text": ""}]
			return []


def extract_text(img_path, temperature=BASE_TEMPERATURE, retry=RETRY, wait=WAIT):
	with open(img_path, "rb") as f:
		b64 = base64.b64encode(f.read()).decode("utf-8")
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {KEY}",
	}
	payload = {
		"model": MODEL,
		"messages": [
			{
				"role": "user",
				"content": [
					{
						"type": "text",
						"text": PROMPT,
					},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/jpeg;base64,{b64}"},
					},
				],
			}
		],
		"temperature": temperature,
		"max_tokens": 2000,
	}
	for attempt in range(retry):
		try:
			resp = requests.post(
				ENDPOINT,
				headers=headers,
				json=payload,
			)
			if resp.status_code != 200:
				if attempt < retry - 1:
					time.sleep(wait)
				continue
			data = resp.json()
			if "choices" in data and data["choices"]:
				content = data["choices"][0]["message"]["content"]
				start = content.find("[")
				end = content.rfind("]") + 1
				if start >= 0 and end > start:
					json_str = content[start:end]
					result = safe_json_loads(json_str)
					if (
						result
						and isinstance(result, list)
						and all(isinstance(item, dict) for item in result)
					):
						return result
		except Exception:
			if attempt < retry - 1:
				time.sleep(wait)
	return []


def verify_json_file(json_path, min_size=26):
	if not os.path.exists(json_path):
		return False
	file_size = os.path.getsize(json_path)
	if file_size < min_size:
		return False
	try:
		with open(json_path, "r", encoding="utf-8") as f:
			data = json.load(f)
		return isinstance(data, list) and len(data) > 0
	except Exception:
		return False


def get_next_file(pending_files):
	with file_list_lock:
		if not pending_files:
			return None
		file_index = random.randint(0, len(pending_files) - 1)
		file_path = pending_files.pop(file_index)
		return file_path


def worker(img_dir, json_dir, pending_files, results):
	while True:
		img_path = get_next_file(pending_files)
		if img_path is None:
			break
		try:
			result = process_image(img_path, img_dir, json_dir)
			with file_list_lock:
				results.append(result)
		except Exception as e:
			error_result = {
				"image": str(img_path),
				"error": f"Processing error: {str(e)}",
			}
			with file_list_lock:
				results.append(error_result)


def process_image(img_path, img_dir, json_dir):
	rel_path = img_path.relative_to(img_dir)
	json_path = json_dir / f"{rel_path.stem}.json"
	os.makedirs(json_path.parent, exist_ok=True)
	if verify_json_file(str(json_path)):
		return {"image": str(img_path), "json": str(json_path)}
	max_attempts = RETRY
	current_temperature = BASE_TEMPERATURE
	for attempt in range(max_attempts):
		text_data = extract_text(str(img_path), temperature=current_temperature)
		if text_data and isinstance(text_data, list):
			try:
				if text_data and len(text_data) > 0 and text_data[0].get("box_2d"):
					text_data.sort(key=lambda x: (x["box_2d"][0], -x["box_2d"][1]))
				with open(json_path, "w", encoding="utf-8") as f:
					json.dump(text_data, f, indent="\t", ensure_ascii=False)
				if verify_json_file(str(json_path)):
					return {
						"image": str(img_path),
						"json": str(json_path),
						"temperature": current_temperature,
					}
			except Exception:
				pass
		current_temperature += TEMPERATURE_INCREASE
	return {
		"image": str(img_path),
		"json": str(json_path),
		"error": "Processing failed",
		"max_temperature_tried": current_temperature - TEMPERATURE_INCREASE,
	}


def process_dir(base_dir, max_workers=CONCURRENT):
	base_dir = Path(base_dir)
	img_dir = base_dir / "crops"
	json_dir = base_dir / "json"
	os.makedirs(json_dir, exist_ok=True)
	if not img_dir.exists() or not img_dir.is_dir():
		return []
	exts = [".jpg"]
	img_files = []
	for ext in exts:
		img_files.extend(img_dir.glob(f"**/*{ext}"))
		img_files.extend(img_dir.glob(f"**/*{ext.upper()}"))
	pending_files = sorted(img_files)
	results = []
	threads = []
	for _ in range(min(max_workers, len(pending_files))):
		thread = threading.Thread(
			target=worker, args=(img_dir, json_dir, pending_files, results)
		)
		thread.start()
		threads.append(thread)
	for thread in threads:
		thread.join()
	return sorted(results, key=lambda x: x.get("image", ""))


def main(path, max_workers=CONCURRENT):
	results = process_dir(path, max_workers)
	summary_path = os.path.join(path, "extract_summary.json")
	with open(summary_path, "w", encoding="utf-8") as f:
		json.dump(
			{
				"total": len(results),
				"successful": sum(1 for r in results if "error" not in r),
				"failed": sum(1 for r in results if "error" in r),
				"results": results,
			},
			f,
			indent="\t",
			ensure_ascii=False,
		)
	return results


if __name__ == "__main__":
	if len(sys.argv) > 1:
		main(sys.argv[1])
