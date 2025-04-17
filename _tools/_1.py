import config
import os
import regex
import shutil
import sys
import zipfile


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


if __name__ == "__main__":
	prepare(
		config.ARCHIVE_EXTENSIONS,
		sys.argv,
		config.DIRS,
		config.IMAGE_EXTENSIONS,
		config.OUTPUT_FILENAME_LENGTH,
		config.PREFIX_LENGTH,
		config.SOURCE_PATHS,
	)
