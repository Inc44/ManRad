from PIL import Image
import glob
import json
import math
import os
import sys
import tiktoken


def calc_img_tokens(img_path):
	img = Image.open(img_path)
	width, height = img.size
	if width <= 384 and height <= 384:
		return 258
	tile_size = 768
	tiles_x = math.ceil(width / tile_size)
	tiles_y = math.ceil(height / tile_size)
	return tiles_x * tiles_y * 258


def count_img_data(base_path):
	img_exts = ["jpg"]
	img_files = []
	for ext in img_exts:
		img_files.extend(
			glob.glob(os.path.join(base_path, "**", f"*.{ext}"), recursive=True)
		)
	img_count = len(img_files)
	token_sum = sum(calc_img_tokens(img) for img in img_files)
	cost = round((0.10 * token_sum) / 1000000, 2)
	return {"img_count": img_count, "token_count": token_sum, "cost": cost}


def count_txt_data(base_path):
	json_files = glob.glob(os.path.join(base_path, "**", "*.json"), recursive=True)
	file_count = len(json_files)
	texts = []
	for json_path in json_files:
		with open(json_path, "r") as f:
			data = json.load(f)
		for item in data:
			if isinstance(item, dict) and "text" in item and item["text"] is not None:
				texts.append(item["text"])
	combined_text = " ".join(texts)
	encoding = tiktoken.get_encoding("cl100k_base")
	token_count = len(encoding.encode(combined_text))
	cost = round((15.0 * token_count) / 1000000, 2)
	return {
		"file_count": file_count,
		"text_len": len(combined_text),
		"token_count": token_count,
		"cost": cost,
	}


def analyze_dir(dir_path):
	img_path = os.path.join(dir_path, "img")
	txt_path = os.path.join(dir_path, "json")
	return {"gemini": count_img_data(img_path), "openai_tts": count_txt_data(txt_path)}


if __name__ == "__main__":
	if len(sys.argv) > 1:
		result = analyze_dir(sys.argv[1])
		print(json.dumps(result, indent="\t"))
