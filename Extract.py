from pathlib import Path
import base64
import json
import os
import requests
import time
import concurrent.futures


def extract_text(img_path, max_retries=10, retry_delay=10.0):
	with open(img_path, "rb") as f:
		b64 = base64.b64encode(f.read()).decode("utf-8")
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {os.environ.get('GEMINI_API_KEY')}",
	}
	payload = {
		"model": "gemini-2.0-flash-001",
		"messages": [
			{
				"role": "user",
				"content": [
					{
						"type": "text",
						"text": 'Return bounding boxes in the correct manga page reading order, from right to left, along with their corresponding text content to be read aloud: [{"box_2d": [y1, x1, y2, x2], "text": "text content"}, ...]',
					},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/jpeg;base64,{b64}"},
					},
				],
			}
		],
		"temperature": 0,
		"max_tokens": 2000,
	}
	for attempt in range(max_retries):
		resp = requests.post(
			"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
			headers=headers,
			json=payload,
			timeout=30,
		)
		if resp.status_code != 200:
			if attempt < max_retries - 1:
				time.sleep(retry_delay)
			continue
		data = resp.json()
		if "choices" in data and data["choices"]:
			content = data["choices"][0]["message"]["content"]
			start = content.find("[")
			end = content.rfind("]") + 1
			if start >= 0 and end > start:
				result = json.loads(content[start:end])
				if (
					result
					and isinstance(result, list)
					and all(isinstance(item, dict) for item in result)
				):
					return result
	return []


def verify_json_file(json_path, min_size=32):
	if not os.path.exists(json_path):
		return False
	file_size = os.path.getsize(json_path)
	if file_size < min_size:
		return False
	with open(json_path, "r", encoding="utf-8") as f:
		data = json.load(f)
	return isinstance(data, list) and len(data) > 0


def process_image(img_path, img_dir, json_dir):
	rel_path = img_path.relative_to(img_dir)
	json_path = json_dir / f"{rel_path.stem}.json"
	os.makedirs(json_path.parent, exist_ok=True)
	if verify_json_file(str(json_path)):
		return {"image": str(img_path), "json": str(json_path)}
	max_attempts = 3
	for _ in range(max_attempts):
		text_data = extract_text(str(img_path))
		if text_data and isinstance(text_data, list):
			if text_data and "box_2d" in text_data[0]:
				text_data.sort(key=lambda x: (x["box_2d"][0], -x["box_2d"][1]))
			with open(json_path, "w", encoding="utf-8") as f:
				json.dump(text_data, f, indent="\t")
			if verify_json_file(str(json_path)):
				return {"image": str(img_path), "json": str(json_path)}
	return {
		"image": (img_path),
		"json": (json_path),
		"error": "Processing failed",
	}


def process_dir(base_dir, max_workers=4):
	base_dir = Path(base_dir)
	img_dir = base_dir / "img"
	json_dir = base_dir / "json"
	os.makedirs(json_dir, exist_ok=True)
	if not img_dir.exists() or not img_dir.is_dir():
		return []
	exts = [".jpg"]
	img_files = []
	for ext in exts:
		img_files.extend(img_dir.glob(f"**/*{ext}"))
		img_files.extend(img_dir.glob(f"**/*{ext.upper()}"))
	img_files = sorted(img_files)
	results = []
	with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
		future_to_img = {
			executor.submit(process_image, img_path, img_dir, json_dir): img_path
			for img_path in img_files
		}
		for _, future in enumerate(concurrent.futures.as_completed(future_to_img)):
			result = future.result()
			results.append(result)
	return sorted(results, key=lambda x: x.get("image", ""))


def main(path, max_workers=10):
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
		)
	return results


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		main(sys.argv[1])
