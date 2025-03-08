from pathlib import Path
import base64
import json
import os
import requests


def extract_text(img_path):
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
	
	resp = requests.post(
		"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
		headers=headers,
		json=payload,
	)
	
	data = resp.json()
	if "choices" in data and data["choices"]:
		content = data["choices"][0]["message"]["content"]
		start = content.find("[")
		end = content.rfind("]") + 1
		if start >= 0 and end > start:
			return json.loads(content[start:end])
	return []


def process_dir(base_dir):
	base_dir = Path(base_dir)
	img_dir = base_dir / "img"
	json_dir = base_dir / "json"
	
	os.makedirs(json_dir, exist_ok=True)
	
	if not img_dir.exists() or not img_dir.is_dir():
		return []
	
	exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
	img_files = []
	
	for ext in exts:
		img_files.extend(img_dir.glob(f"**/*{ext}"))
		img_files.extend(img_dir.glob(f"**/*{ext.upper()}"))
	
	results = []
	for img_path in sorted(img_files):
		rel_path = img_path.relative_to(img_dir)
		json_path = json_dir / f"{rel_path.stem}.json"
		
		os.makedirs(json_path.parent, exist_ok=True)
		
		text_data = extract_text(img_path)
		
		if text_data and "box_2d" in text_data[0]:
			text_data.sort(key=lambda x: (x["box_2d"][0], -x["box_2d"][1]))
		
		with open(json_path, "w", encoding="utf-8") as f:
			json.dump(text_data, f, indent=2)
		
		results.append({"image": str(img_path), "json": str(json_path)})
	
	return results


def main(path):
	return process_dir(path)


if __name__ == "__main__":
	import sys
	
	if len(sys.argv) > 1:
		main(sys.argv[1])
	else:
		sys.exit(1)
