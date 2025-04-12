from _1 import DIRS
from _5 import parse_text_json
import cv2
import json
import os
import tiktoken

DEEPINFRA_COST = (0.08, 0.30)
ENCODING = "cl100k_base"
GEMINI_COST = (0.10, 0.40)
GROQ_COST = (0.90, 0.90)
MAX_TOKENS = 2000
OPENAI_COST = (5.00, 15.00)
TTS_COST = 15.0


def get_deepinfra_tokens():
	return 160


def get_gemini_tokens(path):
	img = cv2.imread(path)
	width, height = img.shape[:2]
	if width <= 384 and height <= 384:
		return 258
	tile_size = 768
	tiles_x = -(-width // tile_size)
	tiles_y = -(-height // tile_size)
	return tiles_x * tiles_y * 258


def get_groq_tokens():
	return 6400


def get_openai_tokens(path, low_resolution=False):
	if low_resolution:
		return 85
	img = cv2.imread(path)
	width, height = img.shape[:2]
	tile_size = 512
	tiles_x = -(-width // tile_size)
	tiles_y = -(-height // tile_size)
	return tiles_x * tiles_y * 170 + 85


if __name__ == "__main__":
	images = sorted(
		[f for f in os.listdir(DIRS["image_crops"]) if f.lower().endswith(".jpg")]
	)
	texts = sorted(
		[f for f in os.listdir(DIRS["image_text"]) if f.lower().endswith(".json")]
	)
	count = len(images)
	input_tokens = 50 * count
	for image in images:
		image_path = os.path.join(DIRS["image_crops"], image)
		input_tokens += get_gemini_tokens(image_path)
	combined_text = ""
	for text_file in texts:
		text_path = os.path.join(DIRS["image_text"], text_file)
		combined_text += parse_text_json(MAX_TOKENS, text_path)
	input_chars = len(combined_text)
	encoding = tiktoken.get_encoding(ENCODING)
	output_tokens = int(len(encoding.encode(combined_text)) * 1.5)
	data = {
		"count": count,
		"llm": {
			"input_tokens": input_tokens,
			"output_tokens": output_tokens,
			"input_cost": round((GEMINI_COST[0] * input_tokens) / 1000000, 4),
			"output_cost": round((GEMINI_COST[1] * output_tokens) / 1000000, 4),
		},
		"tts": {
			"input_chars": input_chars,
			"input_cost": round(TTS_COST * input_chars / 1000000, 4),
		},
	}
	print(json.dumps(data, indent="\t", ensure_ascii=False))
	output_path = os.path.join(DIRS["merge"], "cost.json")
	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(data, f, indent="\t", ensure_ascii=False)
