from manrad0 import DIRS
from manrad1 import batches_distribute
from multiprocessing import Pool, cpu_count
from paddleocr import PaddleOCR, draw_ocr
import cv2
import json
import math
import os

CORES = 6
HEIGHT_RANGE = 96
MARGIN = 16
MAX_DISTANCE = 32


def box_bound(box):
	min_x = min(p[0] for p in box)
	min_y = min(p[1] for p in box)
	max_x = max(p[0] for p in box)
	max_y = max(p[1] for p in box)
	return min_x, min_y, max_x, max_y


def box_distance(box1, box2):
	min_x1, min_y1, max_x1, max_y1 = box_bound(box1)
	min_x2, min_y2, max_x2, max_y2 = box_bound(box2)
	if min_x1 <= max_x2 and min_x2 <= max_x1:
		dx = 0
	else:
		dx = max(min_x1 - max_x2, min_x2 - max_x1)
	if min_y1 <= max_y2 and min_y2 <= max_y1:
		dy = 0
	else:
		dy = max(min_y1 - max_y2, min_y2 - max_y1)
	return math.sqrt(dx**2 + dy**2)


def nodes_collect(adjacency_list, current, node, visited):
	visited[node] = True
	current.append(node)
	for neighbor in adjacency_list[node]:
		if not visited[neighbor]:
			nodes_collect(adjacency_list, current, neighbor, visited)


def box_group(boxes, max_distance):
	box_count = len(boxes)
	if box_count == 0:
		return []
	adjacency_list = [[] for _ in range(box_count)]
	for i in range(box_count):
		for j in range(i + 1, box_count):
			if box_distance(boxes[i], boxes[j]) <= max_distance:
				adjacency_list[i].append(j)
				adjacency_list[j].append(i)
	visited = [False] * box_count
	connected = []
	for i in range(box_count):
		if not visited[i]:
			current = []
			nodes_collect(adjacency_list, current, i, visited)
			connected.append(current)
	return connected


def bounds_and_centers(boxes, groups, margin):
	bounds = []
	centers = []
	for group in groups:
		points = []
		for i in group:
			points.extend(boxes[i])
		min_x = min(point[0] for point in points) - margin
		min_y = min(point[1] for point in points) - margin
		max_x = max(point[0] for point in points) + margin
		max_y = max(point[1] for point in points) + margin
		bounds.append((min_x, min_y, max_x, max_y))
		center_x = (min_x + max_x) / 2
		center_y = (min_y + max_y) / 2
		centers.append((center_x, center_y))
	return bounds, centers


def priority(y_difference, corner_distance):
	return (y_difference * 3) + corner_distance


def boxes_order(bounds, centers, width):
	if not centers:
		return []
	ranking = []
	for i, center in enumerate(centers):
		corner_distance = math.sqrt((width - center[0]) ** 2 + center[1] ** 2)
		y_position = bounds[i][1]
		ranking.append((i, corner_distance, y_position))
	ranking.sort(key=lambda x: x[1])
	order = [ranking[0][0]]
	previous_y = bounds[ranking[0][0]][1]
	unprocessed = ranking[1:]
	while unprocessed:
		priority_scores = []
		for i, corner_distance, y_position in unprocessed:
			y_difference = abs(y_position - previous_y)
			priority_score = priority(y_difference, corner_distance)
			priority_scores.append((i, priority_score))
		priority_scores.sort(key=lambda x: x[1])
		next_score = priority_scores[0][0]
		order.append(next_score)
		previous_y = bounds[next_score][1]
		unprocessed = [(i, d, y) for i, d, y in unprocessed if i != next_score]
	return order


def box_draw(bounds, img, order):
	img_copy = img.copy()
	for i, box in enumerate(order):
		x_min, y_min, x_max, y_max = bounds[box]
		x_min, y_min, x_max, y_max = int(x_min), int(y_min), int(x_max), int(y_max)
		red = (0, 0, 255)
		cv2.rectangle(img_copy, (x_min, y_min), (x_max, y_max), red, 1)
		cv2.putText(
			img_copy,
			str(i + 1),
			(x_min + 4, y_min + 16),
			cv2.FONT_HERSHEY_PLAIN,
			1,
			red,
			1,
		)
	return img_copy


def img_crop(basename, bounds, img, order, output_dir_crops):
	height, width = img.shape[:2]
	for i, box in enumerate(order):
		x_min, y_min, x_max, y_max = bounds[box]
		x_min = max(0, int(x_min))
		y_min = max(0, int(y_min))
		x_max = min(width, int(x_max))
		y_max = min(height, int(y_max))
		crop = img[y_min:y_max, x_min:x_max]
		filename = f"{basename}{i+1:03d}.jpg"
		path = os.path.join(output_dir_crops, filename)
		cv2.imwrite(path, crop, [cv2.IMWRITE_JPEG_QUALITY, 100])


def delta(bounds, height, height_range, order):
	if not order:
		return [height]
	positions = [bounds[i][1] for i in order]
	gaps = []
	gaps.append(positions[0])
	for i in range(1, len(positions)):
		gaps.append(positions[i] - positions[i - 1])
	gaps.append(height - positions[-1])
	remaining_space = 0
	for i in range(len(gaps)):
		gaps[i] += remaining_space
		remaining_space = 0
		if gaps[i] < height_range:
			remaining_space = gaps[i]
			gaps[i] = 0
	if remaining_space > 0:
		gaps[-1] += remaining_space
	gaps = [max(0, gap) for gap in gaps]
	total = sum(gaps)
	if total != height:
		gaps[-1] += height - total
	return gaps


def delta_json(basename, gaps, output_dir_deltas):
	path = os.path.join(output_dir_deltas, f"{basename}.json")
	deltas = {}
	for i, gap in enumerate(gaps):
		key = f"{basename}{i+1:03d}"
		deltas[key] = gap
	with open(path, "w") as f:
		json.dump(deltas, f, indent="\t", ensure_ascii=False)


def ocr_engine_init():
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


def img_detect(
	filename,
	height_range,
	input_dir,
	margin,
	max_distance,
	ocr_engine,
	output_dir_box,
	output_dir_crops,
	output_dir_deltas,
	output_dir_group,
):
	basename, _ = os.path.splitext(filename)
	path = os.path.join(input_dir, filename)
	ocrs = ocr_engine.ocr(path)
	if not ocrs or len(ocrs) == 0 or not ocrs[0]:
		return
	boxes = [item[0] for item in ocrs[0]]
	img = cv2.imread(path)
	img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
	img_box = draw_ocr(img_rgb, boxes)
	img_box = cv2.cvtColor(img_box, cv2.COLOR_RGB2BGR)
	path_box = os.path.join(output_dir_box, os.path.basename(path))
	cv2.imwrite(path_box, img_box)
	connected = box_group(boxes, max_distance)
	bounds, centers = bounds_and_centers(boxes, connected, margin)
	order = boxes_order(bounds, centers, img.shape[1])
	img_group = box_draw(bounds, img, order)
	path_group = os.path.join(output_dir_group, os.path.basename(path))
	cv2.imwrite(path_group, img_group)
	img_crop(basename, bounds, img, order, output_dir_crops)
	gaps = delta(bounds, img.shape[0], height_range, order)
	delta_json(basename, gaps, output_dir_deltas)


def batch_img_detect(
	batch,
	height_range,
	input_dir,
	margin,
	max_distance,
	output_dir_box,
	output_dir_crops,
	output_dir_deltas,
	output_dir_group,
):
	ocr_engine = ocr_engine_init()
	for filename in batch:
		img_detect(
			filename,
			height_range,
			input_dir,
			margin,
			max_distance,
			ocr_engine,
			output_dir_box,
			output_dir_crops,
			output_dir_deltas,
			output_dir_group,
		)


def delta_json_merge(output_dir, output_dir_deltas):
	deltas = {}
	total = 0
	jsons = [f for f in os.listdir(output_dir_deltas) if f.endswith(".json")]
	for filename in jsons:
		path = os.path.join(output_dir_deltas, filename)
		with open(path, "r") as f:
			delta = json.load(f)
		for key, value in delta.items():
			deltas[key] = value
			total += value
	path = os.path.join(output_dir, "deltas.json")
	with open(path, "w") as f:
		json.dump(deltas, f, indent="\t", ensure_ascii=False)
	path = os.path.join(output_dir, "total_delta.txt")
	with open(path, "w") as f:
		f.write(str(total))


if __name__ == "__main__":
	# Box, Crop, Delta, Group
	imgs = sorted(
		[f for f in os.listdir(DIRS["img_resized"]) if f.lower().endswith(".jpg")]
	)
	cores = min(CORES, cpu_count())
	batches = batches_distribute(cores, imgs)
	with Pool(processes=cores) as pool:
		args = [
			(
				batch,
				HEIGHT_RANGE,
				DIRS["img_resized"],
				MARGIN,
				MAX_DISTANCE,
				DIRS["img_boxed"],
				DIRS["img_crops"],
				DIRS["img_deltas"],
				DIRS["img_grouped"],
			)
			for batch in batches
		]
		pool.starmap_async(batch_img_detect, args).get()
	delta_json_merge(DIRS["merges"], DIRS["img_deltas"])
