from _1 import DIRS
from _6 import parse_text_json
import cv2
import json
import os
import tiktoken

ENCODING_NAME = "cl100k_base"
MAX_TOKENS = 2000
COST_DEEPINFRA = (0.08, 0.30)
COST_GEMINI = (0.10, 0.40)
COST_GROQ = (0.90, 0.90)
COST_OPENAI = (5.00, 15.00)
COST_TTS = 15.0


def calculate_gemini_tokens(path):
	image = cv2.imread(path)
	width, height = image.shape[:2]
	if width <= 384 and height <= 384:
		return 258
	tile_size = 768
	tiles_x = -(-width // tile_size)
	tiles_y = -(-height // tile_size)
	return tiles_x * tiles_y * 258


def calculate_openai_tokens(path, low_resolution=False):
	if low_resolution:
		return 85
	image = cv2.imread(path)
	width, height = image.shape[:2]
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
	token_count_deepinfra = 48 * count
	token_count_gemini = 48 * count
	token_count_groq = 48 * count
	token_count_openai = 48 * count
	for image in images:
		image_path = os.path.join(DIRS["image_crops"], image)
		token_count_deepinfra += 160
		token_count_gemini += calculate_gemini_tokens(image_path)
		token_count_groq += 6400
		token_count_openai += calculate_openai_tokens(image_path)
	extracted_text = ""
	for text_file in texts:
		text_path = os.path.join(DIRS["image_text"], text_file)
		extracted_text += parse_text_json(MAX_TOKENS, text_path)
	character_count = len(extracted_text)
	encoding = tiktoken.get_encoding(ENCODING_NAME)
	output_token_count = int(len(encoding.encode(extracted_text)) * 1.5)
	cost_data = {
		"count": count,
		"deepinfra": {
			"input_tokens": token_count_deepinfra,
			"output_tokens": output_token_count,
			"input_cost": round(
				(COST_DEEPINFRA[0] * token_count_deepinfra) / 1000000, 4
			),
			"output_cost": round((COST_DEEPINFRA[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(
					COST_DEEPINFRA[0] * token_count_deepinfra
					+ COST_DEEPINFRA[1] * output_token_count
				)
				/ 1000000,
				4,
			),
		},
		"gemini": {
			"input_tokens": token_count_gemini,
			"output_tokens": output_token_count,
			"input_cost": round((COST_GEMINI[0] * token_count_gemini) / 1000000, 4),
			"output_cost": round((COST_GEMINI[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(
					COST_GEMINI[0] * token_count_gemini
					+ COST_GEMINI[1] * output_token_count
				)
				/ 1000000,
				4,
			),
		},
		"groq": {
			"input_tokens": token_count_groq,
			"output_tokens": output_token_count,
			"input_cost": round((COST_GROQ[0] * token_count_groq) / 1000000, 4),
			"output_cost": round((COST_GROQ[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(COST_GROQ[0] * token_count_groq + COST_GROQ[1] * output_token_count)
				/ 1000000,
				4,
			),
		},
		"openai": {
			"input_tokens": token_count_openai,
			"output_tokens": output_token_count,
			"input_cost": round((COST_OPENAI[0] * token_count_openai) / 1000000, 4),
			"output_cost": round((COST_OPENAI[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(
					COST_OPENAI[0] * token_count_openai
					+ COST_OPENAI[1] * output_token_count
				)
				/ 1000000,
				4,
			),
		},
		"tts": {
			"input_chars": character_count,
			"input_cost": round(COST_TTS * character_count / 1000000, 4),
		},
	}
	print(json.dumps(cost_data, indent="\t", ensure_ascii=False))
	output_path = os.path.join(DIRS["merge"], "cost.json")
	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(cost_data, f, indent="\t", ensure_ascii=False)
