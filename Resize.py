import os
import json
import shutil
import glob
from PIL import Image

INPUT_IMG_DIR = "img"
OUTPUT_IMG_DIR = "img_same_width"
INPUT_JSON_PATH = "output/delta_durations.json"
OUTPUT_JSON_PATH = "output/delta_durations_same_width.json"
TARGET_WIDTH = 750


def make_directory(path):
	if not os.path.exists(path):
		os.makedirs(path)


def get_image_path(base_name, directory):
	path = os.path.join(directory, base_name + ".jpg")
	if os.path.isfile(path):
		return path
	return None


def calculate_relative_path(source, target):
	return os.path.relpath(source, start=target)


def create_file_link_or_copy(source, destination, relative_path):
	if os.path.exists(destination) or os.path.islink(destination):
		return False
	source_absolute = os.path.abspath(source)
	destination_absolute = os.path.abspath(destination)
	if source_absolute == destination_absolute:
		return False
	if hasattr(os, "symlink"):
		symlink_created = False
		symlink_function = getattr(os, "symlink")
		result = symlink_function(relative_path, destination)
		symlink_created = result is None
		if symlink_created:
			return True
	if os.path.isfile(source) and source_absolute != destination_absolute:
		shutil.copy2(source, destination)
		return True
	return False


def resize_image_file(image, original_width, original_height, new_width, save_path):
	if original_width <= 0:
		return 1.0, 0
	scale = new_width / original_width
	new_height = int(original_height * scale)
	if new_width != original_width or new_height != original_height:
		resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
		resized.save(save_path, quality=95, optimize=True)
	return scale, new_height


def process_single_image(image_path, output_dir, target_width):
	if not image_path or not os.path.isfile(image_path):
		return 1.0, 0
	image_dir = os.path.dirname(os.path.abspath(image_path))
	output_abs = os.path.abspath(output_dir)
	if image_dir == output_abs:
		return 1.0, 0
	filename = os.path.basename(image_path)
	output_path = os.path.join(output_dir, filename)
	image_abs = os.path.abspath(image_path)
	if os.path.exists(output_path) and os.path.getsize(output_path) == os.path.getsize(
		image_path
	):
		with Image.open(output_path) as img:
			return 1.0, img.size[1]
	with Image.open(image_path) as img:
		width, height = img.size
		if width == target_width:
			relative_path = calculate_relative_path(image_abs, output_abs)
			create_file_link_or_copy(image_path, output_path, relative_path)
			return 1.0, height
		elif width > 0:
			return resize_image_file(img, width, height, target_width, output_path)
		else:
			return 1.0, height


def load_json_file(file_path):
	if not os.path.isfile(file_path):
		return {}
	with open(file_path, "r") as file:
		content = file.read()
		if not content:
			return {}
		return json.loads(content)


def save_json_file(data, file_path):
	with open(file_path, "w") as file:
		json.dump(data, file, indent="\t")


def is_valid_image(file_path):
	if not os.path.isfile(file_path):
		return False
	base, ext = os.path.splitext(os.path.basename(file_path))
	return ext.lower() == ".jpg" and len(base) == 4 and base.isdigit()


def adjust_deltas_for_height(delta_values, image_base, target_height):
	keys = [k for k in delta_values if k.startswith(image_base)]
	if not keys:
		return
	deltas = [delta_values[k] for k in keys]
	int_deltas = [int(d) for d in deltas]
	delta_sum = sum(int_deltas)
	diff = target_height - delta_sum
	if diff != 0 and len(int_deltas) > 0:
		indices_by_size = sorted(
			range(len(int_deltas)), key=lambda i: int_deltas[i], reverse=True
		)
		if diff > 0:
			for i in range(diff):
				idx = indices_by_size[i % len(indices_by_size)]
				int_deltas[idx] += 1
		else:
			for i in range(-diff):
				idx = indices_by_size[i % len(indices_by_size)]
				if int_deltas[idx] > 0:
					int_deltas[idx] -= 1
	for i, key in enumerate(keys):
		delta_values[key] = int_deltas[i]


def process_all_files():
	input_abs = os.path.abspath(INPUT_IMG_DIR)
	output_abs = os.path.abspath(OUTPUT_IMG_DIR)
	if input_abs == output_abs:
		if os.path.isfile(INPUT_JSON_PATH) and INPUT_JSON_PATH != OUTPUT_JSON_PATH:
			data = load_json_file(INPUT_JSON_PATH)
			save_json_file(data, OUTPUT_JSON_PATH)
		return
	make_directory(OUTPUT_IMG_DIR)
	delta_data = load_json_file(INPUT_JSON_PATH)
	scaled_deltas = {}
	processed_images = set()
	image_heights = {}
	for key, value in delta_data.items():
		if len(key) >= 4:
			img_base = key[:4]
			processed_images.add(img_base)
			img_path = get_image_path(img_base, INPUT_IMG_DIR)
			if img_path:
				scale, height = process_single_image(
					img_path, OUTPUT_IMG_DIR, TARGET_WIDTH
				)
				if height > 0:
					image_heights[img_base] = height
				scaled_deltas[key] = value * scale
			else:
				scaled_deltas[key] = value
		else:
			scaled_deltas[key] = value
	if os.path.isdir(INPUT_IMG_DIR):
		all_images = glob.glob(os.path.join(INPUT_IMG_DIR, "*.jpg"))
		for img_path in all_images:
			if not is_valid_image(img_path):
				continue
			base = os.path.splitext(os.path.basename(img_path))[0]
			if base not in processed_images:
				_, height = process_single_image(img_path, OUTPUT_IMG_DIR, TARGET_WIDTH)
				if height > 0:
					image_heights[base] = height
	for img_base, height in image_heights.items():
		adjust_deltas_for_height(scaled_deltas, img_base, height)
	save_json_file(scaled_deltas, OUTPUT_JSON_PATH)


if __name__ == "__main__":
	process_all_files()
