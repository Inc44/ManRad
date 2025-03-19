from paddleocr import PaddleOCR, draw_ocr
from PIL import Image
import os
import json

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
		ocr_result = ocr_results[0]
		"""
		image = Image.open(image_path).convert("RGB")
		annotated_image = draw_ocr(image, ocr_result)
		annotated_image = Image.fromarray(annotated_image)
		annotated_image_path = os.path.join(annotated_directory, filename)
		annotated_image.save(annotated_image_path)
		"""

		def calculate_shape_centers(ocr_results):
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

		shape_centers = calculate_shape_centers(ocr_result)
		shape_centers.sort(key=lambda center: center[1])

		def calculate_y_deltas(centers, image_height):
			deltas = []
			if centers:
				deltas.append(centers[0][1])
				for i in range(1, len(centers)):
					delta_y = centers[i][1] - centers[i - 1][1]
					deltas.append(delta_y)
				deltas.append(image_height - centers[-1][1])
			return deltas

		image = Image.open(image_path)
		image_height = image.height
		y_deltas = calculate_y_deltas(shape_centers, image_height)
		directory, base_name = os.path.split(image_path)
		root, _ = os.path.splitext(base_name)
		output_directory = "delta"
		output_extension = ".json"
		output_file_path = os.path.join(output_directory, root + output_extension)
		os.makedirs(output_directory, exist_ok=True)
		with open(output_file_path, "w") as json_file:
			json.dump(y_deltas, json_file, indent="\t")
