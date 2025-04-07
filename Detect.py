from PIL import Image, ImageDraw
from paddleocr import PaddleOCR, draw_ocr
import concurrent.futures
import json
import math
import numpy as np
import os
from tqdm import tqdm

DISTANCE = 32
MARGIN = 16
THRESHOLD = 96


def calculate_box_distance(box1, box2):
	min_x1 = min(p[0] for p in box1)
	min_y1 = min(p[1] for p in box1)
	max_x1 = max(p[0] for p in box1)
	max_y1 = max(p[1] for p in box1)
	min_x2 = min(p[0] for p in box2)
	min_y2 = min(p[1] for p in box2)
	max_x2 = max(p[0] for p in box2)
	max_y2 = max(p[1] for p in box2)
	if min_x1 <= max_x2 and min_x2 <= max_x1:
		dx = 0
	else:
		dx = max(min_x1 - max_x2, min_x2 - max_x1)
	if min_y1 <= max_y2 and min_y2 <= max_y1:
		dy = 0
	else:
		dy = max(min_y1 - max_y2, min_y2 - max_y1)
	return math.sqrt(dx**2 + dy**2)


def find_connected_components(boxes, distance=DISTANCE):
	n = len(boxes)
	graph = [[] for _ in range(n)]
	for i in range(n):
		for j in range(i + 1, n):
			if calculate_box_distance(boxes[i], boxes[j]) <= distance:
				graph[i].append(j)
				graph[j].append(i)
	visited = [False] * n
	groups = []

	def depth_first_search(node, component):
		visited[node] = True
		component.append(node)
		for neighbor in graph[node]:
			if not visited[neighbor]:
				depth_first_search(neighbor, component)

	for i in range(n):
		if not visited[i]:
			current_group = []
			depth_first_search(i, current_group)
			groups.append(current_group)
	return groups


def calculate_group_boxes(boxes, groups, margin=MARGIN):
	group_boxes = []
	group_centers = []
	for group in groups:
		all_points = []
		for idx in group:
			all_points.extend(boxes[idx])
		min_x = min(point[0] for point in all_points) - margin
		min_y = min(point[1] for point in all_points) - margin
		max_x = max(point[0] for point in all_points) + margin
		max_y = max(point[1] for point in all_points) + margin
		group_boxes.append((min_x, min_y, max_x, max_y))
		center_x = (min_x + max_x) / 2
		center_y = (min_y + max_y) / 2
		group_centers.append((center_x, center_y))
	return group_boxes, group_centers


def sort_boxes_by_topright_and_height(centers, boxes, image_width, threshold=THRESHOLD):
	box_data = []
	for i, center in enumerate(centers):
		distance = math.sqrt((image_width - center[0]) ** 2 + center[1] ** 2)
		height_value = boxes[i][1]
		box_data.append((i, distance, height_value))
	result = []
	box_data.sort(key=lambda x: x[1])
	first_idx = box_data[0][0]
	result.append(first_idx)
	prev_y = boxes[first_idx][1]
	remaining_boxes = box_data[1:]
	while remaining_boxes:
		height_distance_scores = []
		for idx, dist, y_min in remaining_boxes:
			height_diff = abs(y_min - prev_y)
			combined_score = (height_diff * 3) + dist
			height_distance_scores.append((idx, combined_score))
		height_distance_scores.sort(key=lambda x: x[1])
		next_idx = height_distance_scores[0][0]
		result.append(next_idx)
		prev_y = boxes[next_idx][1]
		remaining_boxes = [(i, d, y) for i, d, y in remaining_boxes if i != next_idx]
	return result


def create_required_directories(dir_list):
	for directory in dir_list:
		os.makedirs(directory, exist_ok=True)


def draw_grouped_boxes(image, boxes, sorted_indices, line_width=2):
	result_image = image.copy()
	draw = ImageDraw.Draw(result_image)
	for i, idx in enumerate(sorted_indices):
		min_x, min_y, max_x, max_y = boxes[idx]
		draw.rectangle(
			[(min_x, min_y), (max_x, max_y)], outline="red", width=line_width
		)
		draw.text((min_x + 5, min_y + 5), str(i + 1), fill="red")
	return result_image


def crop_and_save_boxes(image, boxes, sorted_indices, output_dir, filename_base):
	for i, box_idx in enumerate(sorted_indices):
		min_x, min_y, max_x, max_y = boxes[box_idx]
		min_x = max(0, int(min_x))
		min_y = max(0, int(min_y))
		max_x = min(image.width, int(max_x))
		max_y = min(image.height, int(max_y))
		crop = image.crop((min_x, min_y, max_x, max_y))
		crop_path = os.path.join(output_dir, f"{filename_base}{i+1:03d}.jpg")
		crop.save(crop_path, quality=100)


def calculate_height_deltas(
	group_centers, grouped_boxes, sorted_indices, image_height, threshold=THRESHOLD
):
	sorted_top_heights = [grouped_boxes[idx][1] for idx in sorted_indices]
	if not sorted_top_heights:
		return [image_height]
	num_groups = len(sorted_top_heights)
	deltas = [0] * num_groups
	deltas[0] = sorted_top_heights[0]
	for i in range(1, num_groups - 1):
		deltas[i] = sorted_top_heights[i] - sorted_top_heights[i - 1]
	if num_groups > 1:
		deltas[-1] = image_height - sorted_top_heights[-1]
	remainder = 0
	for i in range(num_groups):
		deltas[i] += remainder
		remainder = 0
		if deltas[i] < threshold:
			remainder = deltas[i]
			deltas[i] = 0
	if remainder > 0 and num_groups > 0:
		deltas[-1] += remainder
	deltas = [max(0, d) for d in deltas]
	current_sum = sum(deltas)
	if current_sum != image_height and num_groups > 0:
		deltas[-1] += image_height - current_sum
	return deltas


def save_deltas_to_json(deltas, output_dir, filename_base):
	os.makedirs(output_dir, exist_ok=True)
	output_file_path = os.path.join(output_dir, f"{filename_base}.json")
	delta_dict = {}
	for i, delta in enumerate(deltas):
		crop_filename = f"{filename_base}{i+1:03d}"
		delta_dict[crop_filename] = delta
	with open(output_file_path, "w") as json_file:
		json.dump(delta_dict, json_file, indent="\t", ensure_ascii=False)


def process_single_image(
	filename,
	ocr_engine,
	image_dir,
	crops_dir,
	annotated_small_dir,
	annotated_grouped_dir,
	delta_dir,
):
	if not filename.lower().endswith((".jpg")):
		return
	image_path = os.path.join(image_dir, filename)
	ocr_results = ocr_engine.ocr(image_path, rec=False)
	if not ocr_results or len(ocr_results) == 0 or not ocr_results[0]:
		return
	ocr_result = ocr_results[0]
	image = Image.open(image_path).convert("RGB")
	small_boxes_image = draw_ocr(np.array(image), ocr_result)
	small_boxes_image = Image.fromarray(small_boxes_image)
	small_annotated_path = os.path.join(annotated_small_dir, filename)
	small_boxes_image.save(small_annotated_path)
	groups = find_connected_components(ocr_result)
	grouped_boxes, group_centers = calculate_group_boxes(ocr_result, groups)
	sorted_indices = sort_boxes_by_topright_and_height(
		group_centers, grouped_boxes, image.width
	)
	grouped_boxes_image = draw_grouped_boxes(image, grouped_boxes, sorted_indices)
	grouped_annotated_path = os.path.join(annotated_grouped_dir, filename)
	grouped_boxes_image.save(grouped_annotated_path)
	root, _ = os.path.splitext(filename)
	crop_and_save_boxes(image, grouped_boxes, sorted_indices, crops_dir, root)
	height_deltas = calculate_height_deltas(
		group_centers, grouped_boxes, sorted_indices, image.height
	)
	save_deltas_to_json(height_deltas, delta_dir, root)
	return filename


def process_images_with_ocr():
	ocr_engine = PaddleOCR(
		gpu_mem=4000,
		lang="en",
		layout=False,
		ocr=False,
		rec=False,
		show_log=False,
		table=False,
		use_angle_cls=True,
		use_gpu=True,
	)
	image_dir = "img"
	crops_dir = "crops"
	annotated_small_dir = "annotated"
	annotated_grouped_dir = "annotated_grouped"
	delta_dir = "delta"
	create_required_directories(
		[crops_dir, annotated_small_dir, annotated_grouped_dir, delta_dir]
	)
	filenames = [f for f in os.listdir(image_dir) if f.lower().endswith(".jpg")]
	for filename in tqdm(filenames, desc="Processing images"):
		process_single_image(
			filename,
			ocr_engine,
			image_dir,
			crops_dir,
			annotated_small_dir,
			annotated_grouped_dir,
			delta_dir,
		)


if __name__ == "__main__":
	process_images_with_ocr()
