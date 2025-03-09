from paddleocr import PaddleOCR, draw_ocr
from PIL import Image
import json


def process_ocr(img_path):
	img = Image.open(img_path).convert("RGB")
	ocr_engine = PaddleOCR(lang="en")
	ocr_result = ocr_engine.ocr(img_path, rec=False)
	return img, ocr_result[0]


def process_json(json_path):
	with open(json_path) as f:
		data = json.load(f)
	boxes = []
	for item in data:
		y1, x1, y2, x2 = item["box_2d"]
		box = [x1, y1, x1, y2, x2, y2, x2, y1]
		boxes.append(box)
	return boxes


def save_image(img, boxes, output_path):
	result_img = draw_ocr(img, boxes)
	Image.fromarray(result_img).save(output_path)


def main():
	img_path = "img/2084032266_001001.jpg"
	json_path = "json/2084032266_001001.json"
	img, ocr_boxes = process_ocr(img_path)
	save_image(img, ocr_boxes, "paddle.jpg")
	json_boxes = process_json(json_path)
	save_image(img, json_boxes, "gemini.jpg")


if __name__ == "__main__":
	main()
