from PIL import Image, ImageDraw
from paddleocr import PaddleOCR, draw_ocr
import multiprocessing
import json
import math
import numpy as np
import os

DISTANCE_LIMIT = 32
BOX_PADDING = 16
HEIGHT_LIMIT = 96


def get_box_boundaries(box):
	min_x = min(p[0] for p in box)
	min_y = min(p[1] for p in box)
	max_x = max(p[0] for p in box)
	max_y = max(p[1] for p in box)
	return min_x, min_y, max_x, max_y


def measure_box_distance(box1, box2):
	min_x1, min_y1, max_x1, max_y1 = get_box_boundaries(box1)
	min_x2, min_y2, max_x2, max_y2 = get_box_boundaries(box2)
	if min_x1 <= max_x2 and min_x2 <= max_x1:
		dx = 0
	else:
		dx = max(min_x1 - max_x2, min_x2 - max_x1)
	if min_y1 <= max_y2 and min_y2 <= max_y1:
		dy = 0
	else:
		dy = max(min_y1 - max_y2, min_y2 - max_y1)
	return math.sqrt(dx**2 + dy**2)


def group_adjacent_boxes(boxes, max_distance=DISTANCE_LIMIT):
	box_count = len(boxes)
	if box_count == 0:
		return []
	links = [[] for _ in range(box_count)]
	for i in range(box_count):
		for j in range(i + 1, box_count):
			if measure_box_distance(boxes[i], boxes[j]) <= max_distance:
				links[i].append(j)
				links[j].append(i)
	visited = [False] * box_count
	groups = []

	def collect_connected(node, current_group):
		visited[node] = True
		current_group.append(node)
		for neighbor in links[node]:
			if not visited[neighbor]:
				collect_connected(neighbor, current_group)

	for i in range(box_count):
		if not visited[i]:
			current_group = []
			collect_connected(i, current_group)
			groups.append(current_group)
	return groups


def compute_group_bounds_and_centers(boxes, groups, margin=BOX_PADDING):
	group_bounds = []
	group_centers = []
	for group in groups:
		all_points = []
		for idx in group:
			all_points.extend(boxes[idx])
		min_x = min(point[0] for point in all_points) - margin
		min_y = min(point[1] for point in all_points) - margin
		max_x = max(point[0] for point in all_points) + margin
		max_y = max(point[1] for point in all_points) + margin
		group_bounds.append((min_x, min_y, max_x, max_y))
		center_x = (min_x + max_x) / 2
		center_y = (min_y + max_y) / 2
		group_centers.append((center_x, center_y))
	return group_bounds, group_centers


def order_boxes_by_position(centers, bounds, image_width):
	if not centers:
		return []
	box_metrics = []
	for i, center in enumerate(centers):
		corner_distance = math.sqrt((image_width - center[0]) ** 2 + center[1] ** 2)
		top_position = bounds[i][1]
		box_metrics.append((i, corner_distance, top_position))
	box_metrics.sort(key=lambda x: x[1])
	ordered_indices = [box_metrics[0][0]]
	last_y = bounds[box_metrics[0][0]][1]
	remaining = box_metrics[1:]
	while remaining:
		scores = []
		for idx, dist, y_pos in remaining:
			height_diff = abs(y_pos - last_y)
			combined_score = (height_diff * 3) + dist
			scores.append((idx, combined_score))
		scores.sort(key=lambda x: x[1])
		next_box = scores[0][0]
		ordered_indices.append(next_box)
		last_y = bounds[next_box][1]
		remaining = [(i, d, y) for i, d, y in remaining if i != next_box]
	return ordered_indices


def create_directories(directory_list):
	for directory in directory_list:
		os.makedirs(directory, exist_ok=True)


def draw_numbered_boxes(image, bounds, order, line_width=2):
	result = image.copy()
	draw = ImageDraw.Draw(result)
	for number, box_idx in enumerate(order):
		x_min, y_min, x_max, y_max = bounds[box_idx]
		draw.rectangle(
			[(x_min, y_min), (x_max, y_max)], outline="red", width=line_width
		)
		draw.text((x_min + 5, y_min + 5), str(number + 1), fill="red")
	return result


def extract_and_save_regions(image, bounds, order, output_folder, base_name):
	for i, box_idx in enumerate(order):
		x_min, y_min, x_max, y_max = bounds[box_idx]
		x_min = max(0, int(x_min))
		y_min = max(0, int(y_min))
		x_max = min(image.width, int(x_max))
		y_max = min(image.height, int(y_max))
		crop = image.crop((x_min, y_min, x_max, y_max))
		crop_filename = f"{base_name}{i+1:03d}.jpg"
		crop_path = os.path.join(output_folder, crop_filename)
		crop.save(crop_path, quality=100)


def calculate_vertical_gaps(bounds, order, image_height):
	if not order:
		return [image_height]
	top_positions = [bounds[idx][1] for idx in order]
	count = len(top_positions)
	gaps = [0] * count
	gaps[0] = top_positions[0]
	for i in range(1, count):
		gaps[i] = top_positions[i] - top_positions[i - 1]
	if count > 0:
		gaps[-1] = image_height - top_positions[-1]
	carry = 0
	for i in range(count):
		gaps[i] += carry
		carry = 0
		if gaps[i] < HEIGHT_LIMIT:
			carry = gaps[i]
			gaps[i] = 0
	if carry > 0 and count > 0:
		gaps[-1] += carry
	gaps = [max(0, gap) for gap in gaps]
	total = sum(gaps)
	if total != image_height and count > 0:
		gaps[-1] += image_height - total
	return gaps


def store_gap_data(gaps, output_folder, base_name):
	os.makedirs(output_folder, exist_ok=True)
	json_path = os.path.join(output_folder, f"{base_name}.json")
	data = {}
	for i, gap in enumerate(gaps):
		crop_key = f"{base_name}{i+1:03d}"
		data[crop_key] = gap
	with open(json_path, "w") as json_file:
		json.dump(data, json_file, indent="\t", ensure_ascii=False)


def initialize_ocr_engine():
	return PaddleOCR(
		gpu_id=0,
		gpu_mem=1024,
		lang="en",
		layout=False,
		ocr=False,
		rec=False,
		show_log=False,
		table=False,
		use_angle_cls=True,
		use_gpu=True,
	)


def process_single_image(image_path, base_name, folders, ocr_engine):
	ocr_result = ocr_engine.ocr(image_path, rec=False)
	if not ocr_result or len(ocr_result) == 0 or not ocr_result[0]:
		return False
	text_boxes = ocr_result[0]
	image = Image.open(image_path).convert("RGB")
	small_boxes_image = draw_ocr(np.array(image), text_boxes)
	small_boxes_image = Image.fromarray(small_boxes_image)
	small_boxes_path = os.path.join(
		folders["annotated_small"], os.path.basename(image_path)
	)
	small_boxes_image.save(small_boxes_path)
	box_groups = group_adjacent_boxes(text_boxes)
	group_bounds, group_centers = compute_group_bounds_and_centers(
		text_boxes, box_groups
	)
	box_order = order_boxes_by_position(group_centers, group_bounds, image.width)
	grouped_boxes_image = draw_numbered_boxes(image, group_bounds, box_order)
	grouped_boxes_path = os.path.join(
		folders["annotated_grouped"], os.path.basename(image_path)
	)
	grouped_boxes_image.save(grouped_boxes_path)
	extract_and_save_regions(
		image, group_bounds, box_order, folders["crops"], base_name
	)
	vertical_gaps = calculate_vertical_gaps(group_bounds, box_order, image.height)
	store_gap_data(vertical_gaps, folders["deltas"], base_name)
	return True


def process_image_batch(file_batch, folders):
	ocr_engine = initialize_ocr_engine()
	processed = []
	for filename in file_batch:
		if not filename.lower().endswith(".jpg"):
			continue
		image_path = os.path.join(folders["images"], filename)
		base_name, _ = os.path.splitext(filename)
		success = process_single_image(image_path, base_name, folders, ocr_engine)
		if success:
			processed.append(filename)
	return processed


def distribute_files_to_workers(files, num_workers):
	batches = [[] for _ in range(num_workers)]
	for i, filename in enumerate(files):
		worker_idx = i % num_workers
		batches[worker_idx].append(filename)
	return batches


def merge_delta_json_files(delta_folder, output_folder):
	os.makedirs(output_folder, exist_ok=True)
	merged_data = {}
	total_height = 0
	json_files = [f for f in os.listdir(delta_folder) if f.endswith(".json")]
	for filename in json_files:
		file_path = os.path.join(delta_folder, filename)
		with open(file_path, "r") as json_file:
			file_data = json.load(json_file)
		for key, value in file_data.items():
			merged_data[key] = value
			total_height += value
	output_path = os.path.join(output_folder, "delta_durations.json")
	with open(output_path, "w") as json_file:
		json.dump(merged_data, json_file, indent="\t", ensure_ascii=False)
	return total_height


def run_ocr_processing():
	folders = {
		"images": "img",
		"crops": "crops",
		"annotated_small": "annotated",
		"annotated_grouped": "annotated_grouped",
		"deltas": "delta",
		"output": "output",
	}
	create_directories(
		[
			folders["crops"],
			folders["annotated_small"],
			folders["annotated_grouped"],
			folders["deltas"],
			folders["output"],
		]
	)
	jpg_files = [f for f in os.listdir(folders["images"]) if f.lower().endswith(".jpg")]
	jpg_files.sort()
	available_cores = multiprocessing.cpu_count()
	optimal_workers = min(6, available_cores)
	results = []
	if len(jpg_files) <= optimal_workers:
		results = process_image_batch(jpg_files, folders)
	else:
		file_batches = distribute_files_to_workers(jpg_files, optimal_workers)
		with multiprocessing.Pool(processes=optimal_workers) as pool:
			tasks = []
			for batch in file_batches:
				if batch:
					task = pool.apply_async(process_image_batch, (batch, folders))
					tasks.append(task)
			for task in tasks:
				batch_results = task.get()
				results.extend(batch_results)
	total_height = merge_delta_json_files(folders["deltas"], folders["output"])
	height_file_path = os.path.join(folders["output"], "total_height.txt")
	with open(height_file_path, "w") as height_file:
		height_file.write(str(total_height))
	return len(results)


if __name__ == "__main__":
	multiprocessing.freeze_support()
	run_ocr_processing()
