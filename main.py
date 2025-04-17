LAZY_PADDLEOCR = True
LAZY_DRAW_OCR = True
from multiprocessing import Pool, cpu_count
import base64
import bisect
import cv2
import functools
import json
import math
import numpy as np
import os
import regex
import requests
import shutil
import subprocess
import tiktoken
import time
import zipfile


def initialize(dirs):
	for dir_path in dirs.values():
		os.makedirs(dir_path, exist_ok=True)


def natural_sort(text):
	text = str(text).lower()
	return [
		int(part) if part.isdigit() else part for part in regex.split(r"(\d+)", text)
	]


def extract_archive(output_dir, prefix, prefix_length, zip_path):
	if not zipfile.is_zipfile(zip_path):
		return
	with zipfile.ZipFile(zip_path) as z:
		for info in z.infolist():
			basename = os.path.basename(info.filename)
			filename = f"{prefix:0{prefix_length}d}_{basename}"
			output_path = os.path.join(output_dir, filename)
			data = z.read(info.filename)
			with open(output_path, "wb") as f:
				f.write(data)


def move_images(image_extensions, input_dir, output_dir, prefix, prefix_length):
	images = [
		f
		for f in os.listdir(input_dir)
		if os.path.isfile(os.path.join(input_dir, f))
		and os.path.splitext(f)[1].lower() in image_extensions
		and not f.startswith(".")
	]
	for image in sorted(images, key=natural_sort):
		filename = f"{prefix:0{prefix_length}d}_{image}"
		output_path = os.path.join(output_dir, filename)
		shutil.copy(os.path.join(input_dir, image), output_path)


def prepare(
	archive_extensions,
	argv,
	dirs,
	image_extensions,
	output_filename_length,
	prefix_length,
	source_paths,
):
	source_path = source_paths[1]
	if len(argv) > 1:
		source_path = argv[1]
	output_dir = dirs["image"]
	temp_dir = dirs["temp"]
	if (
		os.path.isfile(source_path)
		and os.path.splitext(source_path)[1].lower() in archive_extensions
	):
		extract_archive(temp_dir, 0, prefix_length, source_path)
	elif os.path.isdir(source_path):
		paths = os.listdir(source_path)
		archives = sorted(
			[
				f
				for f in paths
				if os.path.isfile(os.path.join(source_path, f))
				and os.path.splitext(f)[1].lower() in archive_extensions
			],
			key=natural_sort,
		)
		sub_dirs = sorted(
			[f for f in paths if os.path.isdir(os.path.join(source_path, f))],
			key=natural_sort,
		)
		images = sorted(
			[
				f
				for f in paths
				if os.path.isfile(os.path.join(source_path, f))
				and os.path.splitext(f)[1].lower() in image_extensions
				and not f.startswith(".")
			],
			key=natural_sort,
		)
		if archives:
			for i, archive in enumerate(archives):
				extract_archive(
					temp_dir, i, prefix_length, os.path.join(source_path, archive)
				)
		elif sub_dirs:
			for i, sub_dir in enumerate(sub_dirs):
				sub_dir_path = os.path.join(source_path, sub_dir)
				move_images(image_extensions, sub_dir_path, temp_dir, i, prefix_length)
		elif images:
			move_images(image_extensions, source_path, temp_dir, 0, prefix_length)
	temp_images = []
	for f in os.listdir(temp_dir):
		temp_path = os.path.join(temp_dir, f)
		if (
			os.path.isfile(temp_path)
			and os.path.splitext(f)[1].lower() in image_extensions
		):
			temp_images.append(f)
	temp_images = sorted(temp_images, key=natural_sort)
	image_counter = 1
	for temp_image in temp_images:
		temp_image_path = os.path.join(temp_dir, temp_image)
		extension = os.path.splitext(temp_image)[1].lower()
		output_filename = f"{image_counter:0{output_filename_length}d}{extension}"
		output_path = os.path.join(output_dir, output_filename)
		if os.path.exists(output_path):
			continue
		os.rename(temp_image_path, output_path)
		if os.path.exists(output_path):
			image_counter += 1
	if os.path.exists(temp_dir):
		shutil.rmtree(temp_dir)
	os.makedirs(temp_dir, exist_ok=True)


def resize_image(filename, input_dir, output_dir, output_image_extension, target_width):
	path = os.path.join(input_dir, filename)
	image = cv2.imread(path)
	height, width = image.shape[:2]
	basename = os.path.splitext(filename)[0]
	output_path = os.path.join(output_dir, f"{basename}{output_image_extension}")
	if width == target_width and filename.lower().endswith(output_image_extension):
		shutil.copy(path, output_path)
		return
	if width != target_width:
		new_height = int((target_width / width) * height)
		image = cv2.resize(
			image, (target_width, new_height), interpolation=cv2.INTER_AREA
		)
	cv2.imwrite(output_path, image, [cv2.IMWRITE_JPEG_QUALITY, 100])


def split_batches(items, num_workers):
	batches = [[] for _ in range(num_workers)]
	for i, item in enumerate(items):
		batches[i % num_workers].append(item)
	return batches


def batch_resize_images(
	batch, input_dir, output_dir, output_image_extension, target_width
):
	for filename in batch:
		resize_image(
			filename, input_dir, output_dir, output_image_extension, target_width
		)


def resize_to_width(
	dirs, image_extensions, output_image_extension, target_width, workers_config
):
	images = sorted(
		[
			f
			for f in os.listdir(dirs["image"])
			if any(f.lower().endswith(ext) for ext in image_extensions)
		]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(images, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				batch,
				dirs["image"],
				dirs["image_resized"],
				output_image_extension,
				target_width,
			)
			for batch in batches
		]
		pool.starmap_async(batch_resize_images, args).get()


def get_basenames(input_dir):
	basenames = set()
	if os.path.exists(input_dir):
		for filename in os.listdir(input_dir):
			if os.path.isfile(os.path.join(input_dir, filename)):
				basename = os.path.splitext(filename)[0]
				basenames.add(basename)
	return basenames


def get_filename(basename, input_dir):
	if os.path.exists(input_dir):
		for filename in os.listdir(input_dir):
			if (
				os.path.isfile(os.path.join(input_dir, filename))
				and os.path.splitext(filename)[0] == basename
			):
				return filename
	return None


def lists(
	all_images_list_filename,
	argv,
	deleted_images_list_filename,
	dirs,
	kept_images_list_filename,
):
	mode = "save"
	if len(argv) > 1:
		mode = argv[1]
	merge_dir = dirs["merge"]
	images_dir = dirs["image"]
	resized_images_dir = dirs["image_resized"]
	deleted_images_path = os.path.join(merge_dir, deleted_images_list_filename)
	images_path = os.path.join(merge_dir, all_images_list_filename)
	kept_images_path = os.path.join(merge_dir, kept_images_list_filename)
	if mode == "save":
		images_basenames = get_basenames(images_dir)
		resized_images_basenames = get_basenames(resized_images_dir)
		kept_images = sorted(list(resized_images_basenames))
		deleted_images = sorted(list(images_basenames - resized_images_basenames))
		images = sorted(list(images_basenames))
		with open(deleted_images_path, "w") as f:
			json.dump(
				deleted_images, f, indent="\t", ensure_ascii=False, sort_keys=True
			)
		with open(images_path, "w") as f:
			json.dump(images, f, indent="\t", ensure_ascii=False, sort_keys=True)
		with open(kept_images_path, "w") as f:
			json.dump(kept_images, f, indent="\t", ensure_ascii=False, sort_keys=True)
	elif mode == "delete":
		if not os.path.exists(deleted_images_path):
			exit()
		with open(deleted_images_path) as f:
			deleted_images = json.load(f)
		for basename in deleted_images:
			filename = get_filename(basename, resized_images_dir)
			if filename:
				path = os.path.join(resized_images_dir, filename)
				if os.path.exists(path):
					os.remove(path)


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
	if LAZY_PADDLEOCR:
		from paddleocr import PaddleOCR

		LAZY_PADDLEOCR = False
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
	if LAZY_DRAW_OCR:
		from paddleocr import draw_ocr

		LAZY_DRAW_OCR = False
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


def parse_json_text(string):
	string = regex.sub(r"[\x00-\x1F\x7F]", "", string)
	string = regex.sub(r"[^A-Za-z\p{Cyrillic}\p{N}\p{P}\p{Z}]", "", string)
	try:
		return json.loads(string)
	except:
		matches = regex.findall(r'"text"\s*:\s*"([^"]*)"', string)
		if matches:
			return [
				{
					"text": bytes(match, "utf-8").decode("unicode_escape")
					if "\\u" in match
					else match
				}
				for match in matches
			]
		return [{"text": ""}] if '"text"' in string else []


def is_valid_json(min_size, path):
	if not os.path.exists(path) or os.stat(path).st_size < min_size:
		return False
	try:
		with open(path, encoding="utf-8") as f:
			data = json.load(f)
		return isinstance(data, list) and data
	except:
		return False


def image_to_text(
	api_endpoint,
	api_key,
	attempt,
	filename,
	input_dir,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	prompt,
	retries,
	temperature,
	temperature_step,
):
	basename = os.path.splitext(filename)[0]
	path = os.path.join(input_dir, filename)
	text_filename = f"{basename}.json"
	text_path = os.path.join(output_dir, text_filename)
	if is_valid_json(min_size, text_path):
		return
	with open(path, "rb") as f:
		image_base64 = base64.b64encode(f.read()).decode()
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
	payload = {
		"max_tokens": max_tokens,
		"model": model,
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": prompt},
					{
						"type": "image_url",
						"image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
					},
				],
			}
		],
		"seed": 42,
		"temperature": temperature,
	}
	current_temperature = temperature
	for current_attempt in range(attempt, retries):
		try:
			payload["temperature"] = current_temperature
			response = requests.post(api_endpoint, headers=headers, json=payload)
			if response.status_code == 200:
				content = response.json()["choices"][0]["message"]["content"]
				start = content.find("[")
				end = content.rfind("]") + 1
				if start >= 0 and end > start:
					parsed = parse_json_text(content[start:end])
					if (
						parsed
						and len(str(parsed)) >= min_size
						and isinstance(parsed, list)
						and all(isinstance(item, dict) for item in parsed)
					):
						with open(text_path, "w", encoding="utf-8") as f:
							json.dump(
								parsed,
								f,
								indent="\t",
								ensure_ascii=False,
								sort_keys=True,
							)
						return
		except:
			pass
		if current_attempt < retries - 1:
			sleep_time = pause * (2**current_attempt)
			current_temperature += temperature_step
			time.sleep(sleep_time)


def batch_image_to_text(
	api_endpoint,
	api_key,
	attempt,
	batch,
	input_dir,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	prompt,
	retries,
	temperature,
	temperature_step,
):
	for filename in batch:
		image_to_text(
			api_endpoint,
			api_key,
			attempt,
			filename,
			input_dir,
			max_tokens,
			min_size,
			model,
			output_dir,
			pause,
			prompt,
			retries,
			temperature,
			temperature_step,
		)


def texts(
	api_endpoints,
	api_keys,
	concurrent_requests,
	dirs,
	max_tokens,
	model,
	output_image_extension,
	pause,
	prompt,
	retries,
	temperature,
	temperature_step,
	text_min_size,
):
	images = sorted(
		[
			f
			for f in os.listdir(dirs["image_crops"])
			if f.lower().endswith(output_image_extension)
		]
	)
	workers = min(concurrent_requests, 10 * cpu_count())
	batches = split_batches(images, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				api_endpoints[2],
				api_keys[1],
				0,
				batch,
				dirs["image_crops"],
				max_tokens,
				text_min_size,
				model,
				dirs["image_text"],
				pause,
				prompt,
				retries,
				temperature,
				temperature_step,
			)
			for batch in batches
		]
		pool.starmap_async(batch_image_to_text, args).get()


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
	height, width = image.shape[:2]
	tile_size = 512
	tiles_x = -(-width // tile_size)
	tiles_y = -(-height // tile_size)
	return tiles_x * tiles_y * 170 + 85


def costs(
	cost_deepinfra,
	cost_filename,
	cost_gemini,
	cost_groq,
	cost_openai,
	cost_tts,
	dirs,
	encoding_name,
	max_tokens,
	output_image_extension,
):
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


def parse_text_json(max_tokens, path):
	with open(path, encoding="utf-8") as f:
		data = json.load(f)
	if isinstance(data, list):
		text = " ".join(item.get("text", "") for item in data if isinstance(item, dict))
	elif isinstance(data, dict):
		text = data.get("text", "")
	else:
		return ""
	text = text.replace("- ", "")
	text = regex.sub(r"\s+", " ", text).strip()
	if text:
		text = text[0].upper() + text[1:]
	return text[: max_tokens * 2]


def is_valid_audio(min_size, path):
	return os.path.exists(path) and os.stat(path).st_size >= min_size


def text_to_audio(
	api_endpoint,
	attempt,
	audio_output_extension,
	filename,
	input_dir,
	max_tokens,
	min_size,
	output_dir,
	pause,
	reference_audio_path,
	reference_text_path,
	retries,
	temperature,
):
	basename = os.path.splitext(filename)[0]
	path = os.path.join(input_dir, filename)
	audio_filename = f"{basename}{audio_output_extension}"
	audio_path = os.path.join(output_dir, audio_filename)
	if is_valid_audio(min_size, audio_path):
		return
	text = parse_text_json(max_tokens, path)
	if len(text) == 0:
		return
	with open(reference_text_path, encoding="utf-8") as f:
		reference_text = f.read().strip()
	with open(reference_audio_path, "rb") as f:
		reference_audio_base64 = base64.b64encode(f.read()).decode()
	references = []
	if reference_text and reference_audio_base64:
		references.append({"audio": reference_audio_base64, "text": reference_text})
	headers = {"Content-Type": "application/json"}
	payload = {
		"chunk_length": max_tokens * 2,
		"format": "wav",
		"max_new_tokens": max_tokens,
		"normalize": True,
		"reference_id": None,
		"references": references,
		"seed": 42,
		"streaming": False,
		"temperature": temperature,
		"text": text,
		"use_memory_cache": "on",
	}
	for current_attempt in range(attempt, retries):
		try:
			response = requests.post(api_endpoint, headers=headers, json=payload)
			if response.status_code == 200:
				with open(audio_path, "wb") as f:
					f.write(response.content)
				if is_valid_audio(min_size, audio_path):
					return
		except:
			pass
		if current_attempt < retries - 1:
			sleep_time = pause * (2**current_attempt)
			time.sleep(sleep_time)


def batch_text_to_audio(
	api_endpoint,
	attempt,
	audio_output_extension,
	batch,
	input_dir,
	max_tokens,
	min_size,
	output_dir,
	pause,
	reference_audio_path,
	reference_text_path,
	retries,
	temperature,
):
	for filename in batch:
		text_to_audio(
			api_endpoint,
			attempt,
			audio_output_extension,
			filename,
			input_dir,
			max_tokens,
			min_size,
			output_dir,
			pause,
			reference_audio_path,
			reference_text_path,
			retries,
			temperature,
		)


def fish_tts(
	api_endpoints,
	audio_min_size,
	audio_output_extension,
	dirs,
	fish_temperature,
	max_tokens,
	pause,
	reference_audio,
	reference_text,
	retries,
	workers_config,
):
	texts = sorted(
		[f for f in os.listdir(dirs["image_text"]) if f.lower().endswith(".json")]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(texts, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				api_endpoints[0],
				0,
				audio_output_extension,
				batch,
				dirs["image_text"],
				max_tokens,
				audio_min_size,
				dirs["image_audio"],
				pause,
				reference_audio,
				reference_text,
				retries,
				fish_temperature,
			)
			for batch in batches
		]
		pool.starmap_async(batch_text_to_audio, args).get()


def text_to_audio(
	api_endpoint,
	api_key,
	attempt,
	audio_output_extension,
	filename,
	input_dir,
	instructions,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	response_format,
	retries,
	voice,
):
	basename = os.path.splitext(filename)[0]
	path = os.path.join(input_dir, filename)
	audio_filename = f"{basename}{audio_output_extension}"
	audio_path = os.path.join(output_dir, audio_filename)
	if is_valid_audio(min_size, audio_path):
		return
	text = parse_text_json(max_tokens, path)
	if len(text) == 0:
		return
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
	payload = {
		"model": model,
		"input": text,
		"voice": voice,
		"response_format": response_format,
	}
	if instructions:
		payload["instructions"] = instructions
	for current_attempt in range(attempt, retries):
		try:
			response = requests.post(api_endpoint, headers=headers, json=payload)
			if response.status_code == 200:
				with open(audio_path, "wb") as f:
					f.write(response.content)
				if is_valid_audio(min_size, audio_path):
					return
		except:
			pass
		if current_attempt < retries - 1:
			sleep_time = pause * (2**current_attempt)
			time.sleep(sleep_time)


def batch_text_to_audio(
	api_endpoint,
	api_key,
	attempt,
	audio_output_extension,
	batch,
	input_dir,
	instructions,
	max_tokens,
	min_size,
	model,
	output_dir,
	pause,
	response_format,
	retries,
	voice,
):
	for filename in batch:
		text_to_audio(
			api_endpoint,
			api_key,
			attempt,
			audio_output_extension,
			filename,
			input_dir,
			instructions,
			max_tokens,
			min_size,
			model,
			output_dir,
			pause,
			response_format,
			retries,
			voice,
		)


def openai_tts(
	api_endpoints,
	api_keys,
	audio_min_size,
	audio_output_extension,
	dirs,
	instructions,
	max_tokens,
	models,
	pause,
	response_format,
	retries,
	voices,
	workers_config,
):
	texts = sorted(
		[f for f in os.listdir(dirs["image_text"]) if f.lower().endswith(".json")]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(texts, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				api_endpoints[4],
				api_keys[6],
				0,
				audio_output_extension,
				batch,
				dirs["image_text"],
				instructions[0],
				max_tokens,
				audio_min_size,
				models[1],
				dirs["image_audio"],
				pause,
				response_format[1],
				retries,
				voices[3],
			)
			for batch in batches
		]
		pool.starmap_async(batch_text_to_audio, args).get()


def create_silence(duration, output_path, sample_rate):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-f",
		"lavfi",
		"-i",
		f"anullsrc=r={sample_rate}:cl=mono",
		"-t",
		str(duration),
		"-c:a",
		"pcm_s16le",
		output_path,
	]
	subprocess.run(cmd)


def extend_silence(duration, input_path, output_path, sample_rate):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		input_path,
		"-ar",
		str(sample_rate),
		"-af",
		f"apad=pad_dur={duration}",
		"-c:a",
		"pcm_s16le",
		output_path,
	]
	subprocess.run(cmd)


def get_audio_duration(input_path):
	cmd = [
		"ffprobe",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		input_path,
		"-show_entries",
		"format=duration",
		"-v",
		"quiet",
		"-of",
		"csv=p=0",
	]
	try:
		result = subprocess.check_output(cmd).decode().strip()
		return float(result) if result else 0.0
	except:
		return 0.0


def save_duration_json(basename, duration, output_dir):
	output_path = os.path.join(output_dir, f"{basename}.json")
	with open(output_path, "w") as f:
		json.dump(
			{basename: duration}, f, indent="\t", ensure_ascii=False, sort_keys=True
		)


def copy_audio(input_path, output_path, sample_rate):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		input_path,
		"-ar",
		str(sample_rate),
		"-ac",
		"1",
		"-c:a",
		"pcm_s16le",
		output_path,
	]
	subprocess.run(cmd)


def set_audio_duration(
	audio_output_extension,
	filename,
	input_dir,
	output_dir,
	resized_dir,
	sample_rate,
	target_duration,
):
	input_path = os.path.join(input_dir, filename)
	basename = os.path.splitext(filename)[0]
	resized_path = os.path.join(resized_dir, f"{basename}{audio_output_extension}")
	duration = get_audio_duration(input_path)
	if 0 < duration < target_duration:
		extend_silence(
			target_duration - duration, input_path, resized_path, sample_rate
		)
		duration = target_duration
	elif duration >= target_duration:
		copy_audio(input_path, resized_path, sample_rate)
	else:
		create_silence(target_duration, resized_path, sample_rate)
		duration = target_duration
	save_duration_json(basename, duration, output_dir)


def batch_set_audio_duration(
	audio_output_extension,
	batch,
	input_dir,
	output_dir,
	resized_dir,
	sample_rate,
	target_duration,
):
	for filename in batch:
		set_audio_duration(
			audio_output_extension,
			filename,
			input_dir,
			output_dir,
			resized_dir,
			sample_rate,
			target_duration,
		)


def create_transition_files(
	audio_output_extension,
	audios,
	duration_dir,
	prefix_length,
	resized_dir,
	sample_rate,
	transition_duration,
	transition_suffix,
):
	if transition_duration == 0:
		return
	previous_prefix = None
	for i, filename in enumerate(audios):
		current_prefix = filename[:prefix_length]
		if i > 0 and current_prefix != previous_prefix:
			basename = f"{previous_prefix}{transition_suffix}"
			output_filename = f"{basename}{audio_output_extension}"
			transition_path = os.path.join(resized_dir, output_filename)
			create_silence(transition_duration, transition_path, sample_rate)
			save_duration_json(basename, transition_duration, duration_dir)
		previous_prefix = current_prefix


def create_delay(
	audio_output_extension,
	audios,
	delay_duration,
	delay_suffix,
	duration_dir,
	prefix_length,
	resized_dir,
	sample_rate,
):
	if delay_duration == 0 or not audios:
		return
	filename = audios[0]
	basename = f"{filename[:prefix_length]}{delay_suffix}"
	output_filename = f"{basename}{audio_output_extension}"
	delay_path = os.path.join(resized_dir, output_filename)
	create_silence(delay_duration, delay_path, sample_rate)
	save_duration_json(basename, delay_duration, duration_dir)


def merge_duration_json(input_dir, merged_durations_filename, output_dir):
	durations = {}
	files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
	for filename in files:
		path = os.path.join(input_dir, filename)
		with open(path) as f:
			duration_data = json.load(f)
			durations.update(duration_data)
	path = os.path.join(output_dir, merged_durations_filename)
	with open(path, "w") as f:
		json.dump(durations, f, indent="\t", ensure_ascii=False, sort_keys=True)


def calculate_total_duration(
	input_dir, merged_durations_filename, total_duration_filename
):
	path = os.path.join(input_dir, merged_durations_filename)
	total = 0.0
	with open(path) as f:
		durations = json.load(f)
		total = sum(durations.values())
	output_path = os.path.join(input_dir, total_duration_filename)
	with open(output_path, "w") as f:
		f.write(str(total))


def create_audio_list(audio_list_filename, audios, input_dir, output_dir):
	output_path = os.path.join(output_dir, audio_list_filename)
	with open(output_path, "w") as f:
		for filename in audios:
			path = os.path.join(input_dir, filename)
			f.write(f"file '{os.path.abspath(path)}'\n")


def render_audio(
	audio_filename, audio_list_filename, input_dir, render_dir, sample_rate
):
	path_input = os.path.join(input_dir, audio_list_filename)
	path_render = os.path.join(render_dir, audio_filename)
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-f",
		"concat",
		"-safe",
		"0",
		"-i",
		path_input,
		"-ar",
		str(sample_rate),
		"-c:a",
		"libopus",
		"-vbr",
		"on",
		"-compression_level",
		"10",
		"-frame_duration",
		"60",
		path_render,
	]
	subprocess.run(cmd)


def audio(
	audio_concat_list_filename,
	audio_delay_duration,
	audio_filename,
	audio_output_extension,
	audio_target_segment_duration,
	audio_transition_duration,
	delay_suffix,
	dirs,
	merged_durations_filename,
	output_image_extension,
	prefix_length,
	sample_rate,
	total_duration_filename,
	transition_suffix,
	workers_config,
):
	initial_audios = sorted(
		[
			f.replace(output_image_extension, audio_output_extension)
			for f in os.listdir(dirs["image_crops"])
			if f.lower().endswith(output_image_extension)
		]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(initial_audios, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				audio_output_extension,
				batch,
				dirs["image_audio"],
				dirs["image_durations"],
				dirs["image_audio_resized"],
				sample_rate,
				audio_target_segment_duration,
			)
			for batch in batches
		]
		pool.starmap_async(batch_set_audio_duration, args).get()
	processed_audios = sorted(
		[
			f
			for f in os.listdir(dirs["image_audio_resized"])
			if f.lower().endswith(audio_output_extension)
		]
	)
	create_transition_files(
		audio_output_extension,
		processed_audios,
		dirs["image_durations"],
		prefix_length,
		dirs["image_audio_resized"],
		sample_rate,
		audio_transition_duration,
		transition_suffix,
	)
	audios_with_transitions = sorted(
		[
			f
			for f in os.listdir(dirs["image_audio_resized"])
			if f.lower().endswith(audio_output_extension)
		]
	)
	create_delay(
		audio_output_extension,
		audios_with_transitions,
		audio_delay_duration,
		delay_suffix,
		dirs["image_durations"],
		prefix_length,
		dirs["image_audio_resized"],
		sample_rate,
	)
	merge_duration_json(
		dirs["image_durations"], merged_durations_filename, dirs["merge"]
	)
	calculate_total_duration(
		dirs["merge"], merged_durations_filename, total_duration_filename
	)
	final_audios = sorted(
		[
			f
			for f in os.listdir(dirs["image_audio_resized"])
			if f.lower().endswith(audio_output_extension)
		]
	)
	create_audio_list(
		audio_concat_list_filename,
		final_audios,
		dirs["image_audio_resized"],
		dirs["merge"],
	)
	render_audio(
		audio_filename,
		audio_concat_list_filename,
		dirs["merge"],
		dirs["render"],
		sample_rate,
	)


def resize_fit_image(
	filename, input_dir, output_dir, output_image_extension, target_height
):
	path = os.path.join(input_dir, filename)
	image = cv2.imread(path)
	height, width = image.shape[:2]
	basename = os.path.splitext(filename)[0]
	output_path = os.path.join(output_dir, f"{basename}{output_image_extension}")
	if height == target_height and filename.lower().endswith(output_image_extension):
		shutil.copy(path, output_path)
		return
	if height > target_height:
		top_pad = (height - target_height) // 2
		bottom_pad = top_pad + target_height
		image = image[top_pad:bottom_pad, 0:width]
	elif height < target_height:
		top_pad = (target_height - height) // 2
		bottom_pad = target_height - height - top_pad
		image = cv2.copyMakeBorder(
			image, top_pad, bottom_pad, 0, 0, cv2.BORDER_CONSTANT, value=[0, 0, 0]
		)
	cv2.imwrite(output_path, image, [cv2.IMWRITE_JPEG_QUALITY, 100])


def batch_resize_images_to_fit(
	batch, input_dir, output_dir, output_image_extension, target_height
):
	for filename in batch:
		resize_fit_image(
			filename, input_dir, output_dir, output_image_extension, target_height
		)


def resize_to_fit(dirs, output_image_extension, target_height, workers_config):
	input_dir = dirs["image_resized"]
	output_dir = dirs["image_resized_fit"]
	images = sorted(
		[f for f in os.listdir(input_dir) if f.lower().endswith(output_image_extension)]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(images, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				batch,
				input_dir,
				output_dir,
				output_image_extension,
				target_height,
			)
			for batch in batches
		]
		pool.starmap_async(batch_resize_images_to_fit, args).get()


def page_durations(
	delay_suffix,
	dirs,
	merged_durations_filename,
	page_durations_filename,
	prefix_length,
	sum_suffix,
	transition_suffix,
):
	input_dir = dirs["merge"]
	output_dir = dirs["merge"]
	input_path = os.path.join(input_dir, merged_durations_filename)
	output_path = os.path.join(output_dir, page_durations_filename)
	with open(input_path) as f:
		durations = json.load(f)
	page_durations = {}
	for key in durations.keys():
		value = durations[key]
		prefix = key[:prefix_length]
		suffix = key[prefix_length:]
		if suffix == delay_suffix or suffix == transition_suffix:
			page_durations[key] = value
		else:
			sum_key = prefix + sum_suffix
			current_sum = page_durations.get(sum_key, 0.0)
			page_durations[sum_key] = current_sum + value
	with open(output_path, "w") as f:
		json.dump(page_durations, f, indent="\t", ensure_ascii=False, sort_keys=True)


def fade_images(input_path1, input_path2, output_dir, target_fps, transition_duration):
	image1 = cv2.imread(input_path1)
	image2 = cv2.imread(input_path2)
	frames = int(target_fps * transition_duration)
	input_stem1 = os.path.splitext(os.path.basename(input_path1))[0]
	for i in range(frames):
		alpha = i / (frames - 1)
		blended_image = cv2.addWeighted(image1, 1 - alpha, image2, alpha, 0)
		cv2.imwrite(
			os.path.join(output_dir, f"{input_stem1}{i:03d}.jpg"),
			blended_image,
			[cv2.IMWRITE_JPEG_QUALITY, 100],
		)


def render_fade_video(
	fade_video_filename, fade_video_list_filename, input_dir, output_dir
):
	input_path = os.path.join(input_dir, fade_video_list_filename)
	output_path = os.path.join(output_dir, fade_video_filename)
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-f",
		"concat",
		"-safe",
		"0",
		"-i",
		input_path,
		"-fps_mode",
		"vfr",
		"-c:v",
		"libx264",
		"-preset",
		"medium",
		output_path,
	]
	subprocess.run(cmd)


def render_media(audio_filename, media_filename, render_dir, video_filename):
	video_path = os.path.join(render_dir, video_filename)
	audio_path = os.path.join(render_dir, audio_filename)
	render_path = os.path.join(render_dir, media_filename)
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		video_path,
		"-i",
		audio_path,
		"-c",
		"copy",
		render_path,
	]
	subprocess.run(cmd)


def fade(
	audio_filename,
	delay_suffix,
	dirs,
	fade_video_filename,
	fade_video_list_filename,
	frame_suffix_length,
	hold_duration,
	media_filename,
	page_durations_filename,
	prefix_length,
	sum_suffix,
	target_fps,
	transition_suffix,
):
	input_dir = dirs["image_resized_fit"]
	output_dir = dirs["image_resized_fit_fade"]
	merge_dir = dirs["merge"]
	render_dir = dirs["render"]
	path = os.path.join(merge_dir, page_durations_filename)
	with open(path) as f:
		page_durations = json.load(f)
	list_file_path = os.path.join(merge_dir, fade_video_list_filename)
	keys = sorted(page_durations.keys())
	with open(list_file_path, "w") as f:
		for i, key in enumerate(keys):
			duration = page_durations[key]
			prefix = key[:prefix_length]
			suffix = key[prefix_length:]
			input_path1 = os.path.join(input_dir, f"{prefix}.jpg")
			if suffix == delay_suffix or suffix == sum_suffix:
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {1 / target_fps}\n")
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {duration - 1 / target_fps}\n")
			elif suffix == transition_suffix:
				if i + 1 < len(keys):
					next_key = keys[i + 1]
					next_prefix = next_key[:prefix_length]
					input_path2 = os.path.join(input_dir, f"{next_prefix}.jpg")
					fade_images(
						input_path1,
						input_path2,
						output_dir,
						target_fps,
						duration,
					)
					frames = int(target_fps * duration)
					for j in range(frames):
						path_frame = os.path.join(
							output_dir, f"{prefix}{j:0{frame_suffix_length}d}.jpg"
						)
						f.write(f"file '{os.path.abspath(path_frame)}'\n")
						f.write(f"duration {duration / frames}\n")
		last_frame_path = path_frame if "path_frame" in locals() else input_path1
		f.write(f"file '{os.path.abspath(last_frame_path)}'\n")
		f.write(f"duration {1 / target_fps}\n")
		f.write(f"file '{os.path.abspath(last_frame_path)}'\n")
		f.write(f"duration {hold_duration - 1 / target_fps}\n")
		f.write(f"file '{os.path.abspath(last_frame_path)}'\n")
		f.write(f"duration {1 / target_fps}\n")
	render_fade_video(
		fade_video_filename, fade_video_list_filename, merge_dir, render_dir
	)
	render_media(audio_filename, media_filename, render_dir, fade_video_filename)


def map_durations(
	dirs, merged_durations_filename, merged_gaps_filename, transition_gaps_filename
):
	merge_dir = dirs["merge"]
	durations_path = os.path.join(merge_dir, merged_durations_filename)
	gaps_path = os.path.join(merge_dir, merged_gaps_filename)
	output_path = os.path.join(merge_dir, transition_gaps_filename)
	with open(durations_path) as f:
		durations = json.load(f)
	with open(gaps_path) as f:
		gaps = json.load(f)
	duration_keys = sorted(durations.keys())
	gaps_keys = sorted(gaps.keys())
	transition_gaps = {}
	for i in range(len(duration_keys)):
		duration_key = duration_keys[i]
		gap_key = gaps_keys[i]
		transition_gaps[duration_key] = gaps[gap_key]
	with open(output_path, "w") as f:
		json.dump(transition_gaps, f, indent="\t", ensure_ascii=False, sort_keys=True)


@functools.lru_cache(maxsize=2048)
def ease(time_ratio):
	eased_value = 0.0
	if time_ratio < 0.4:
		eased_value = 2.5 * time_ratio * time_ratio
	elif time_ratio < 0.8:
		eased_value = 0.4 + (time_ratio - 0.4) * 1.2
	else:
		normalized_time = (time_ratio - 0.8) / 0.2
		normalized_time = max(0.0, normalized_time)
		eased_value = 0.88 + (1.0 - math.pow(1.0 - normalized_time, 2)) * 0.12
	return max(0.0, min(1.0, eased_value))


def render_scroll_video(height, output_path, target_fps, width):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		# "-loglevel",
		# "error",
		"-f",
		"rawvideo",
		"-c:v",
		"rawvideo",
		"-s",
		f"{width}x{height}",
		"-pix_fmt",
		"bgr24",
		"-r",
		str(target_fps),
		"-i",
		"-",
		# "-vf",
		# "mpdecimate",
		"-c:v",
		"h264_nvenc",  # hevc_nvenc av1_nvenc h264_qsv hevc_qsv av1_qsv libx264 libx265 libsvtav1
		"-preset",
		"p7",  # ultrafast faster 13
		"-rc",
		"constqp",
		# "-profile:v",
		# "high",
		"-g",
		"999999",
		# "-pix_fmt",
		# "yuv420p",
		output_path,
	]
	return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def frames_list(input_dir, output_image_extension):
	images = sorted(
		[f for f in os.listdir(input_dir) if f.lower().endswith(output_image_extension)]
	)
	frames_metadata = []
	total_height = 0
	for filename in images:
		path = os.path.join(input_dir, filename)
		if os.path.exists(path):
			image = cv2.imread(path)
			height = image.shape[0]
			frame_info = {
				"path": path,
				"height": height,
				"vertical_start_position": total_height,
			}
			frames_metadata.append(frame_info)
			total_height += height
	return frames_metadata, total_height


@functools.lru_cache(maxsize=6)
def cached_image(path):
	image = cv2.imread(path)
	return image.copy()


def compose_scroll_frame(
	frames_metadata,
	height,
	total_content_height,
	vertical_start_position_list,
	viewport_top_position,
	width,
):
	max_scroll_pos = max(0, total_content_height - height)
	safe_viewport_top_position = (
		int(round(min(max(0, viewport_top_position), max_scroll_pos)))
		if total_content_height > height
		else 0
	)
	safe_viewport_end_position = safe_viewport_top_position + height
	output_frame = np.zeros((height, width, 3), dtype=np.uint8)
	start_index = (
		bisect.bisect_right(vertical_start_position_list, safe_viewport_top_position)
		- 1
	)
	start_index = max(0, start_index)
	for i in range(start_index, len(frames_metadata)):
		frame_meta = frames_metadata[i]
		frame_v_start = frame_meta["vertical_start_position"]
		frame_v_end = frame_v_start + frame_meta["height"]
		if frame_v_start >= safe_viewport_end_position:
			break
		if max(safe_viewport_top_position, frame_v_start) < min(
			safe_viewport_end_position, frame_v_end
		):
			crop_start_y = max(0, safe_viewport_top_position - frame_v_start)
			crop_end_y = min(
				frame_meta["height"], safe_viewport_end_position - frame_v_start
			)
			paste_start_y = max(0, frame_v_start - safe_viewport_top_position)
			if crop_end_y > crop_start_y:
				image = cached_image(frame_meta["path"])
				image_width = image.shape[1]
				if image_width != width:
					if image_width > width:
						image = image[:, :width]
					else:
						image = cv2.copyMakeBorder(
							image,
							0,
							0,
							0,
							width - image_width,
							cv2.BORDER_CONSTANT,
							value=[0, 0, 0],
						)
				cropped_image_part = image[crop_start_y:crop_end_y, 0:width]
				cropped_height = cropped_image_part.shape[0]
				paste_end_y = paste_start_y + cropped_height
				if paste_end_y > height:
					overhang = paste_end_y - height
					cropped_image_part = cropped_image_part[:-overhang, :]
					paste_end_y = height
				if cropped_image_part.shape[0] > 0 and cropped_image_part.shape[1] > 0:
					output_frame[paste_start_y:paste_end_y, 0:width] = (
						cropped_image_part
					)
	return output_frame


def process_scroll_segment(
	delay_percent,
	duration,
	frames_metadata,
	frames_per_second,
	height,
	scroll_video_render_pipe,
	start_focus_point,
	total_content_height,
	vertical_gap_list,
	vertical_start_position_list,
	width,
):
	num_frames_in_segment = round(duration * frames_per_second)
	if num_frames_in_segment <= 0:
		return (
			start_focus_point + sum(vertical_gap_list)
			if vertical_gap_list
			else start_focus_point
		)
	is_hold_segment = (
		not vertical_gap_list or sum(abs(gap) for gap in vertical_gap_list) < 1e-6
	)
	vertical_offset = height * delay_percent
	final_focus_point = start_focus_point
	if is_hold_segment:
		viewport_top_pos = start_focus_point - vertical_offset
		hold_frame = compose_scroll_frame(
			frames_metadata,
			height,
			total_content_height,
			vertical_start_position_list,
			int(round(viewport_top_pos)),
			width,
		)
		hold_frame_bytes = hold_frame.tobytes()
		for _ in range(num_frames_in_segment):
			scroll_video_render_pipe.stdin.write(hold_frame_bytes)
		final_focus_point = start_focus_point
	else:
		focus_point_stops = [start_focus_point]
		for gap in vertical_gap_list:
			focus_point_stops.append(focus_point_stops[-1] + gap)
		final_focus_point = focus_point_stops[-1]
		total_absolute_gap = sum(abs(gap) for gap in vertical_gap_list)
		total_absolute_gap = max(total_absolute_gap, 1e-9)
		time_stops = [0.0]
		cumulative_time = 0.0
		for gap in vertical_gap_list:
			time_ratio = abs(gap) / total_absolute_gap
			cumulative_time += time_ratio * duration
			time_stops.append(cumulative_time)
		time_stops[-1] = duration
		for frame_idx in range(num_frames_in_segment):
			current_time = (frame_idx / num_frames_in_segment) * duration
			sub_segment_idx = bisect.bisect_right(time_stops, current_time) - 1
			sub_segment_idx = max(0, min(sub_segment_idx, len(vertical_gap_list) - 1))
			sub_start_time = time_stops[sub_segment_idx]
			sub_end_time = time_stops[sub_segment_idx + 1]
			sub_duration = sub_end_time - sub_start_time
			time_progress = 0.0
			if sub_duration > 1e-9:
				time_progress = (current_time - sub_start_time) / sub_duration
				time_progress = max(0.0, min(1.0, time_progress))
			else:
				time_progress = (
					0.0 if abs(current_time - sub_start_time) < 1e-9 else 1.0
				)
			eased_progress = ease(time_progress)
			sub_start_focus = focus_point_stops[sub_segment_idx]
			sub_end_focus = focus_point_stops[sub_segment_idx + 1]
			vertical_gap_sub_segment = sub_end_focus - sub_start_focus
			current_focus_point_pos = (
				sub_start_focus + eased_progress * vertical_gap_sub_segment
			)
			viewport_top_pos = current_focus_point_pos - vertical_offset
			output_frame = compose_scroll_frame(
				frames_metadata,
				height,
				total_content_height,
				vertical_start_position_list,
				int(round(viewport_top_pos)),
				width,
			)
			frame_bytes = output_frame.tobytes()
			scroll_video_render_pipe.stdin.write(frame_bytes)
	return final_focus_point


def scroll(
	audio_filename,
	delay_percent,
	dirs,
	hold_duration,
	media_filename,
	merged_durations_filename,
	output_image_extension,
	scroll_video_filename,
	target_fps,
	target_height,
	target_width,
	transition_gaps_filename,
):
	source_image_directory = dirs["image_resized_fit"]
	render_dir = dirs["render"]
	merge_dir = dirs["merge"]
	output_video_path = os.path.join(render_dir, scroll_video_filename)
	vertical_change_data_path = os.path.join(merge_dir, transition_gaps_filename)
	segment_duration_data_path = os.path.join(merge_dir, merged_durations_filename)
	image_metadata, total_content_height = frames_list(
		source_image_directory, output_image_extension
	)
	vertical_start_positions = [
		meta["vertical_start_position"] for meta in image_metadata
	]
	with open(vertical_change_data_path, "r") as f:
		vertical_change_data = json.load(f)
	with open(segment_duration_data_path, "r") as f:
		segment_duration_data = json.load(f)
	gap_keys = set(vertical_change_data.keys())
	duration_keys = set(segment_duration_data.keys())
	valid_segment_keys = sorted(list(gap_keys.intersection(duration_keys)), key=int)
	cached_image.cache_clear()
	encoder_process = render_scroll_video(
		target_height,
		output_video_path,
		target_fps,
		target_width,
	)
	total_frames_written_count = 0
	current_focus_point = 0.0
	num_intro_frames = round(hold_duration * target_fps)
	if num_intro_frames > 0:
		_ = process_scroll_segment(
			delay_percent=delay_percent,
			duration=hold_duration,
			frames_metadata=image_metadata,
			frames_per_second=target_fps,
			height=target_height,
			scroll_video_render_pipe=encoder_process,
			start_focus_point=current_focus_point,
			total_content_height=total_content_height,
			vertical_gap_list=[],
			vertical_start_position_list=vertical_start_positions,
			width=target_width,
		)
		total_frames_written_count += num_intro_frames
	for i, segment_key in enumerate(valid_segment_keys):
		delta_value = vertical_change_data[segment_key]
		segment_duration = float(segment_duration_data[segment_key])
		if isinstance(delta_value, (int, float)):
			segment_vertical_changes = [float(delta_value)]
		elif isinstance(delta_value, list):
			segment_vertical_changes = [
				float(d) for d in delta_value if isinstance(d, (int, float))
			]
		else:
			continue
		if segment_duration <= 0:
			current_focus_point += sum(segment_vertical_changes)
			continue
		num_segment_frames = round(segment_duration * target_fps)
		if num_segment_frames <= 0:
			current_focus_point += sum(segment_vertical_changes)
			continue
		end_focus_point = process_scroll_segment(
			delay_percent=delay_percent,
			duration=segment_duration,
			frames_metadata=image_metadata,
			frames_per_second=target_fps,
			height=target_height,
			scroll_video_render_pipe=encoder_process,
			start_focus_point=current_focus_point,
			total_content_height=total_content_height,
			vertical_gap_list=segment_vertical_changes,
			vertical_start_position_list=vertical_start_positions,
			width=target_width,
		)
		current_focus_point = end_focus_point
		total_frames_written_count += num_segment_frames
	if encoder_process.stdin:
		encoder_process.stdin.close()
	_ = encoder_process.wait()
	render_media(audio_filename, media_filename, render_dir, scroll_video_filename)
