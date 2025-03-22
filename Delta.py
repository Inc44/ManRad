from paddleocr import PaddleOCR, draw_ocr
from PIL import Image
import os
import json


def calculate_shape_centers(ocr_results):
	if ocr_results is None:
		return []
	centers = []
	for shape in ocr_results:
		sum_x = 0
		sum_y = 0
		for point in shape:
			sum_x += point[0]
			sum_y += point[1]
		center_x = sum_x / len(shape)
		center_y = sum_y / len(shape)
		centers.append([center_x, center_y])
	return centers


def calculate_y_deltas(centers, image_height):
	deltas = []
	if centers:
		deltas.append(centers[0][1])
		for i in range(1, len(centers)):
			delta_y = centers[i][1] - centers[i - 1][1]
			deltas.append(delta_y)
		deltas.append(image_height - centers[-1][1])
	else:
		deltas.append(image_height)
	return deltas


def merge_small_deltas(deltas, threshold=50):
	if not deltas:
		return []
	merged_deltas = []
	current_group = deltas[0]
	for i in range(1, len(deltas)):
		if deltas[i] < threshold:
			current_group += deltas[i]
		else:
			merged_deltas.append(current_group)
			current_group = deltas[i]
	merged_deltas.append(current_group)
	return merged_deltas


ocr_engine = PaddleOCR(lang="en")
image_directory = "img"
annotated_directory = "annotated"
os.makedirs(annotated_directory, exist_ok=True)
for filename in os.listdir(image_directory):
	if filename.lower().endswith(".jpg"):
		image_path = os.path.join(image_directory, filename)
		ocr_results = ocr_engine.ocr(image_path, rec=False)
		"""
		for idx in range(len(ocr_results)):
			ocr_result = ocr_results[idx]
			for line in ocr_result:
				print(line)
		"""
		if ocr_results and len(ocr_results) > 0:
			ocr_result = ocr_results[0]
		else:
			ocr_result = None
		image = Image.open(image_path)
		image_height = image.height
		shape_centers = calculate_shape_centers(ocr_result)
		shape_centers.sort(key=lambda center: center[1]) if shape_centers else []
		y_deltas = calculate_y_deltas(shape_centers, image_height)
		merged_deltas = merge_small_deltas(y_deltas, threshold=50)
		directory, base_name = os.path.split(image_path)
		root, _ = os.path.splitext(base_name)
		output_directory = "delta"
		os.makedirs(output_directory, exist_ok=True)
		output_file_path = os.path.join(output_directory, root + ".json")
		with open(output_file_path, "w") as json_file:
			json.dump(merged_deltas, json_file, indent="\t")
		"""
		image = Image.open(image_path).convert("RGB")
		annotated_image = draw_ocr(image, ocr_result)
		annotated_image = Image.fromarray(annotated_image)
		annotated_image_path = os.path.join(annotated_directory, filename)
		annotated_image.save(annotated_image_path)
		"""
