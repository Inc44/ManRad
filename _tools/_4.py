import config
from _2 import split_batches
from multiprocessing import Pool, cpu_count
from paddleocr import PaddleOCR, draw_ocr
import cv2
import json
import math
import os


def get_box_bounds(box):
	min_x = min(p[0] for p in box)
	min_y = min(p[1] for p in box)
	max_x = max(p[0] for p in box)
	max_y = max(p[1] for p in box)
	return min_x, min_y, max_x, max_y


def get_box_distance(box1, box2):
	min_x1, min_y1, max_x1, max_y1 = get_box_bounds(box1)
	min_x2, min_y2, max_x2, max_y2 = get_box_bounds(box2)
	dx = max(min_x1 - max_x2, min_x2 - max_x1, 0)
	dy = max(min_y1 - max_y2, min_y2 - max_y1, 0)
	return math.sqrt(dx**2 + dy**2)


def collect_connected_nodes(adj_list, current, node, visited):
	visited[node] = True
	current.append(node)
	for neighbor in adj_list[node]:
		if not visited[neighbor]:
			collect_connected_nodes(adj_list, current, neighbor, visited)


def group_boxes(boxes, max_distance):
	count = len(boxes)
	if count == 0:
		return []
	adj_list = [[] for _ in range(count)]
	for i in range(count):
		for j in range(i + 1, count):
			if get_box_distance(boxes[i], boxes[j]) <= max_distance:
				adj_list[i].append(j)
				adj_list[j].append(i)
	visited = [False] * count
	groups = []
	for i in range(count):
		if not visited[i]:
			current = []
			collect_connected_nodes(adj_list, current, i, visited)
			groups.append(current)
	return groups


def get_bounds_and_centers(boxes, groups, margin):
	bounds = []
	centers = []
	for group in groups:
		points = []
		for i in group:
			points.extend(boxes[i])
		min_x = min(p[0] for p in points) - margin
		min_y = min(p[1] for p in points) - margin
		max_x = max(p[0] for p in points) + margin
		max_y = max(p[1] for p in points) + margin
		bounds.append((min_x, min_y, max_x, max_y))
		center_x = (min_x + max_x) / 2
		center_y = (min_y + max_y) / 2
		centers.append((center_x, center_y))
	return bounds, centers


def get_priority(corner_dist, y_diff):
	return (y_diff * 3) + corner_dist


def order_boxes(bounds, centers, width):
	if not centers:
		return []
	ranking = []
	for i, center in enumerate(centers):
		corner_dist = math.sqrt((width - center[0]) ** 2 + center[1] ** 2)
		y_pos = bounds[i][1]
		ranking.append((i, corner_dist, y_pos))
	ranking.sort(key=lambda x: x[1])
	order = [ranking[0][0]]
	prev_y = bounds[ranking[0][0]][1]
	unprocessed = ranking[1:]
	while unprocessed:
		scores = []
		for i, corner_dist, y_pos in unprocessed:
			y_diff = abs(y_pos - prev_y)
			score = get_priority(corner_dist, y_diff)
			scores.append((i, score))
		scores.sort(key=lambda x: x[1])
		next_index = scores[0][0]
		order.append(next_index)
		prev_y = bounds[next_index][1]
		unprocessed = [(i, d, y) for i, d, y in unprocessed if i != next_index]
	return order


def draw_boxes(bounds, image, order):
	image_copy = image.copy()
	for i, box_index in enumerate(order):
		x_min, y_min, x_max, y_max = bounds[box_index]
		x_min, y_min, x_max, y_max = int(x_min), int(y_min), int(x_max), int(y_max)
		red = (0, 0, 255)
		cv2.rectangle(image_copy, (x_min, y_min), (x_max, y_max), red, 1)
		cv2.putText(
			image_copy,
			str(i + 1),
			(x_min + 4, y_min + 16),
			cv2.FONT_HERSHEY_PLAIN,
			1,
			red,
			1,
		)
	return image_copy


def crop_images(
	basename,
	bounds,
	crop_suffix_length,
	image,
	order,
	output_dir,
	output_image_extension,
):
	height, width = image.shape[:2]
	for i, box_index in enumerate(order):
		x_min, y_min, x_max, y_max = bounds[box_index]
		x_min = max(0, int(x_min))
		y_min = max(0, int(y_min))
		x_max = min(width, int(x_max))
		y_max = min(height, int(y_max))
		crop = image[y_min:y_max, x_min:x_max]
		filename = f"{basename}{i+1:0{crop_suffix_length}d}{output_image_extension}"
		path = os.path.join(output_dir, filename)
		cv2.imwrite(path, crop, [cv2.IMWRITE_JPEG_QUALITY, 100])


def get_gaps(bounds, height, height_range, order):
	if not order:
		return [height]
	positions = [bounds[i][1] for i in order]
	gaps = [positions[0]]
	for i in range(1, len(positions)):
		gaps.append(positions[i] - positions[i - 1])
	gaps.append(height - positions[-1])
	remaining = 0
	for i in range(len(gaps)):
		gaps[i] += remaining
		remaining = 0
		if gaps[i] < height_range:
			remaining = gaps[i]
			gaps[i] = 0
	if remaining > 0:
		gaps[-1] += remaining
	gaps = [max(0, gap) for gap in gaps]
	total = sum(gaps)
	if total != height:
		gaps[-1] += height - total
	return gaps


def save_gaps_json(basename, crop_suffix_length, gaps, output_dir):
	path = os.path.join(output_dir, f"{basename}.json")
	data = {}
	for i, gap in enumerate(gaps):
		key = f"{basename}{i+1:0{crop_suffix_length}d}"
		data[key] = gap
	with open(path, "w") as f:
		json.dump(data, f, indent="\t", ensure_ascii=False, sort_keys=True)


def init_ocr_engine():
	return PaddleOCR(
		gpu_id=0,
		gpu_mem=1000,
		lang="en",
		layout=False,
		ocr=False,
		rec=False,
		show_log=False,
		table=False,
		use_gpu=True,
	)


def detect_image(
	crop_suffix_length,
	filename,
	height_range,
	input_dir,
	margin,
	max_distance,
	ocr_engine,
	output_dir_box,
	output_dir_crops,
	output_dir_gaps,
	output_dir_group,
	output_image_extension,
):
	basename = os.path.splitext(filename)[0]
	path = os.path.join(input_dir, filename)
	ocrs = ocr_engine.ocr(path)
	if not ocrs or len(ocrs) == 0 or not ocrs[0]:
		return
	boxes = [item[0] for item in ocrs[0]]
	image = cv2.imread(path)
	image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
	image_box = draw_ocr(image_rgb, boxes)
	image_box = cv2.cvtColor(image_box, cv2.COLOR_RGB2BGR)
	path_box = os.path.join(output_dir_box, basename + output_image_extension)
	cv2.imwrite(path_box, image_box, [cv2.IMWRITE_JPEG_QUALITY, 100])
	groups = group_boxes(boxes, max_distance)
	bounds, centers = get_bounds_and_centers(boxes, groups, margin)
	order = order_boxes(bounds, centers, image.shape[1])
	image_group = draw_boxes(bounds, image, order)
	path_group = os.path.join(output_dir_group, basename + output_image_extension)
	cv2.imwrite(path_group, image_group, [cv2.IMWRITE_JPEG_QUALITY, 100])
	crop_images(
		basename,
		bounds,
		crop_suffix_length,
		image,
		order,
		output_dir_crops,
		output_image_extension,
	)
	gaps = get_gaps(bounds, image.shape[0], height_range, order)
	save_gaps_json(basename, crop_suffix_length, gaps, output_dir_gaps)


def batch_detect_images(
	batch,
	crop_suffix_length,
	height_range,
	input_dir,
	margin,
	max_distance,
	output_dir_box,
	output_dir_crops,
	output_dir_gaps,
	output_dir_group,
	output_image_extension,
):
	ocr_engine = init_ocr_engine()
	for filename in batch:
		detect_image(
			crop_suffix_length,
			filename,
			height_range,
			input_dir,
			margin,
			max_distance,
			ocr_engine,
			output_dir_box,
			output_dir_crops,
			output_dir_gaps,
			output_dir_group,
			output_image_extension,
		)


def merge_gaps_json(input_dir, merged_gaps_filename, output_dir, total_gaps_filename):
	data = {}
	total = 0
	files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
	for filename in files:
		path = os.path.join(input_dir, filename)
		with open(path) as f:
			gap_data = json.load(f)
		for key, value in gap_data.items():
			data[key] = value
			total += value
	path = os.path.join(output_dir, merged_gaps_filename)
	with open(path, "w") as f:
		json.dump(data, f, indent="\t", ensure_ascii=False, sort_keys=True)
	path = os.path.join(output_dir, total_gaps_filename)
	with open(path, "w") as f:
		f.write(str(total))


def crops(
	crop_suffix_length,
	dirs,
	height_range,
	margin,
	max_distance,
	merged_gaps_filename,
	output_image_extension,
	total_gaps_filename,
	workers_config,
):
	images = sorted(
		[
			f
			for f in os.listdir(dirs["image_resized"])
			if f.lower().endswith(output_image_extension)
		]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(images, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				batch,
				crop_suffix_length,
				height_range,
				dirs["image_resized"],
				margin,
				max_distance,
				dirs["image_boxed"],
				dirs["image_crops"],
				dirs["image_gaps"],
				dirs["image_grouped"],
				output_image_extension,
			)
			for batch in batches
		]
		pool.starmap_async(batch_detect_images, args).get()
	merge_gaps_json(
		dirs["image_gaps"], merged_gaps_filename, dirs["merge"], total_gaps_filename
	)


if __name__ == "__main__":
	crops(
		config.CROP_SUFFIX_LENGTH,
		config.DIRS,
		config.HEIGHT_RANGE,
		config.MARGIN,
		config.MAX_DISTANCE,
		config.MERGED_GAPS_FILENAME,
		config.OUTPUT_IMAGE_EXTENSION,
		config.TOTAL_GAPS_FILENAME,
		config.WORKERS,
	)
