from pathlib import Path
import base64
import json
import os
import regex
import requests
import sys
import time
from concurrent.futures import ThreadPoolExecutor

API_KEY = os.environ.get("DEEPINFRA_API_KEY")
MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
PROMPT = 'Proofread this text in Russian but only fix grammar without any introductory phrases or additional commentary. If no readable text is found, the text content is empty. Return JSON: [{"text": "text content"}, ...]'
API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
RETRIES = 3
WAIT_SEC = 6
MAX_WORKERS = 150
BASE_TEMP = 0.0
TEMP_STEP = 0.1


def parse_json(text):
	clean_text = regex.sub(r"\\u[^0-9a-fA-F]{4}|[\x00-\x1F\x7F]", "", text)
	try:
		return json.loads(clean_text)
	except:
		return [{"text": ""}] if '"text"' in clean_text else []


def get_text(img_path, temp=BASE_TEMP):
	with open(img_path, "rb") as f:
		img_b64 = base64.b64encode(f.read()).decode("utf-8")
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
	payload = {
		"model": MODEL,
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": PROMPT},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
					},
				],
			}
		],
		"temperature": temp,
		"max_tokens": 2000,
	}
	for attempt in range(RETRIES):
		try:
			resp = requests.post(API_URL, headers=headers, json=payload)
			if resp.status_code != 200:
				if attempt < RETRIES - 1:
					time.sleep(WAIT_SEC)
				continue
			data = resp.json()
			if not data.get("choices"):
				continue
			content = data["choices"][0]["message"]["content"]
			start = content.find("[")
			end = content.rfind("]") + 1
			if start < 0 or end <= start:
				continue
			result = parse_json(content[start:end])
			if (
				result
				and isinstance(result, list)
				and all(isinstance(item, dict) for item in result)
			):
				return result
		except:
			pass
		if attempt < RETRIES - 1:
			time.sleep(WAIT_SEC)
	return []


def is_valid(json_path):
	path = Path(json_path)
	if not path.exists() or path.stat().st_size < 26:
		return False
	try:
		with open(path, encoding="utf-8") as f:
			data = json.load(f)
		return isinstance(data, list) and data
	except:
		return False


def process(img_path, img_dir, json_dir):
	rel_path = Path(img_path).relative_to(img_dir)
	json_path = json_dir / f"{rel_path.stem}.json"
	os.makedirs(json_path.parent, exist_ok=True)
	if is_valid(json_path):
		return {"image": str(img_path), "json": str(json_path)}
	for i in range(RETRIES):
		temp = BASE_TEMP + (i * TEMP_STEP)
		data = get_text(img_path, temp)
		if not data:
			continue
		try:
			if data and data[0].get("box_2d"):
				data.sort(key=lambda x: (x["box_2d"][0], -x["box_2d"][1]))
			with open(json_path, "w", encoding="utf-8") as f:
				json.dump(data, f, indent="\t", ensure_ascii=False)
			if is_valid(json_path):
				return {
					"image": str(img_path),
					"json": str(json_path),
					"temperature": temp,
				}
		except:
			pass
	return {
		"image": str(img_path),
		"json": str(json_path),
		"error": "Processing failed",
		"max_temp": BASE_TEMP + ((RETRIES - 1) * TEMP_STEP),
	}


def process_dir(base_dir, workers=MAX_WORKERS):
	base_dir = Path(base_dir)
	img_dir = base_dir / "crops"
	json_dir = base_dir / "json"
	os.makedirs(json_dir, exist_ok=True)
	if not img_dir.is_dir():
		return []
	img_files = list(img_dir.glob("**/*.jpg")) + list(img_dir.glob("**/*.JPG"))
	results = []
	with ThreadPoolExecutor(max_workers=min(workers, len(img_files))) as exe:
		futures = [
			exe.submit(process, str(img), img_dir, json_dir) for img in img_files
		]
		for i, future in enumerate(futures):
			try:
				results.append(future.result())
			except Exception as e:
				results.append({"image": str(img_files[i]), "error": f"Error: {e}"})
	return sorted(results, key=lambda x: x.get("image", ""))


def main(path, workers=MAX_WORKERS):
	results = process_dir(path, workers)
	summary = {
		"total": len(results),
		"successful": sum(1 for r in results if "error" not in r),
		"failed": sum(1 for r in results if "error" in r),
		"results": results,
	}
	with open(Path(path) / "extract_summary.json", "w", encoding="utf-8") as f:
		json.dump(summary, f, indent="\t", ensure_ascii=False)
	return results


if __name__ == "__main__":
	if len(sys.argv) > 1:
		main(sys.argv[1])
