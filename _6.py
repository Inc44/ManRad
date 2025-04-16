import config
from _7 import parse_text_json
import cv2
import json
import os
import tiktoken


def calculate_gemini_tokens(path):
	image = cv2.imread(path)
	height, width = image.shape[:2]
	if width <= 384 and height <= 384:
		return 258
	tile_size = 768
	tiles_x = -(-width // tile_size)
	tiles_y = -(-height // tile_size)
	return tiles_x * tiles_y * 258


def calculate_openai_tokens(low_resolution, path):
	if low_resolution:
		return 85
	image = cv2.imread(path)
	if image is None:
		return 85
	height, width = image.shape[:2]
	tile_size = 512
	tiles_x = -(-width // tile_size)
	tiles_y = -(-height // tile_size)
	return tiles_x * tiles_y * 170 + 85


if __name__ == "__main__":
	cost_deepinfra = config.COST_DEEPINFRA
	cost_filename = config.COST_FILENAME
	cost_gemini = config.COST_GEMINI
	cost_groq = config.COST_GROQ
	cost_openai = config.COST_OPENAI
	cost_tts = config.COST_TTS
	dirs = config.DIRS
	encoding_name = config.ENCODING_NAME
	max_tokens = config.MAX_TOKENS
	output_image_extension = config.OUTPUT_IMAGE_EXTENSION
	images = sorted(
		[
			f
			for f in os.listdir(dirs["image_crops"])
			if f.lower().endswith(output_image_extension)
		]
	)
	texts = sorted(
		[f for f in os.listdir(dirs["image_text"]) if f.lower().endswith(".json")]
	)
	count = len(images)
	token_count_deepinfra = 48 * count
	token_count_gemini = 48 * count
	token_count_groq = 48 * count
	token_count_openai = 48 * count
	for image in images:
		image_path = os.path.join(dirs["image_crops"], image)
		token_count_deepinfra += 160
		token_count_gemini += calculate_gemini_tokens(image_path)
		token_count_groq += 6400
		token_count_openai += calculate_openai_tokens(False, image_path)
	extracted_text = ""
	for text_file in texts:
		text_path = os.path.join(dirs["image_text"], text_file)
		extracted_text += parse_text_json(max_tokens, text_path)
	character_count = len(extracted_text)
	encoding = tiktoken.get_encoding(encoding_name)
	output_token_count = int(len(encoding.encode(extracted_text)) * 1.5)
	cost_data = {
		"count": count,
		"deepinfra": {
			"input_tokens": token_count_deepinfra,
			"output_tokens": output_token_count,
			"input_cost": round(
				(cost_deepinfra[0] * token_count_deepinfra) / 1000000, 4
			),
			"output_cost": round((cost_deepinfra[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(
					cost_deepinfra[0] * token_count_deepinfra
					+ cost_deepinfra[1] * output_token_count
				)
				/ 1000000,
				4,
			),
		},
		"gemini": {
			"input_tokens": token_count_gemini,
			"output_tokens": output_token_count,
			"input_cost": round((cost_gemini[0] * token_count_gemini) / 1000000, 4),
			"output_cost": round((cost_gemini[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(
					cost_gemini[0] * token_count_gemini
					+ cost_gemini[1] * output_token_count
				)
				/ 1000000,
				4,
			),
		},
		"groq": {
			"input_tokens": token_count_groq,
			"output_tokens": output_token_count,
			"input_cost": round((cost_groq[0] * token_count_groq) / 1000000, 4),
			"output_cost": round((cost_groq[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(cost_groq[0] * token_count_groq + cost_groq[1] * output_token_count)
				/ 1000000,
				4,
			),
		},
		"openai": {
			"input_tokens": token_count_openai,
			"output_tokens": output_token_count,
			"input_cost": round((cost_openai[0] * token_count_openai) / 1000000, 4),
			"output_cost": round((cost_openai[1] * output_token_count) / 1000000, 4),
			"total_cost": round(
				(
					cost_openai[0] * token_count_openai
					+ cost_openai[1] * output_token_count
				)
				/ 1000000,
				4,
			),
		},
		"tts": {
			"input_chars": character_count,
			"input_cost": round(cost_tts * character_count / 1000000, 4),
		},
	}
	print(json.dumps(cost_data, indent="\t", ensure_ascii=False, sort_keys=False))
	output_path = os.path.join(dirs["merge"], cost_filename)
	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(cost_data, f, indent="\t", ensure_ascii=False, sort_keys=False)
