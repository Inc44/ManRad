from _0 import DIRS
import os
import regex
import zipfile

SOURCE_PATHS = [
	"Kage_no_Jitsuryokusha_ni_Naritakute_",  # Kotatsu CBZ or DIR
	"Kage_no_Jitsuryokusha_ni_Naritakute_.zip",  # Kotatsu ZIP
	"The Eminence in Shadow_001",  # HakuNeko Images
	"The Eminence in Shadow_002",  # HakuNeko CBZ
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ARCHIVE_EXTENSIONS = {".cbz", ".zip"}


def natural_sort(text):
	text = str(text).lower()
	return [
		int(part) if part.isdigit() else part for part in regex.split(r"(\d+)", text)
	]


def extract_archive(output_dir, prefix, zip_path):
	if not zipfile.is_zipfile(zip_path):
		return
	with zipfile.ZipFile(zip_path, "r") as z:
		for info in z.infolist():
			basename = os.path.basename(info.filename)
			filename = f"{prefix:04d}_{basename}"
			output_path = os.path.join(output_dir, filename)
			data = z.read(info.filename)
			with open(output_path, "wb") as f:
				f.write(data)


def move_images(input_dir, output_dir, prefix):
	images = [
		f
		for f in os.listdir(input_dir)
		if os.path.isfile(os.path.join(input_dir, f))
		and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
		and not f.startswith(".")
	]
	for image in sorted(images, key=natural_sort):
		filename = f"{prefix:04d}_{image}"
		output_path = os.path.join(output_dir, filename)
		os.rename(os.path.join(input_dir, image), output_path)


if __name__ == "__main__":
	source_path = SOURCE_PATHS[1]
	output_dir = DIRS["image"]
	temp_dir = DIRS["temp"]
	if (
		os.path.isfile(source_path)
		and os.path.splitext(source_path)[1].lower() in ARCHIVE_EXTENSIONS
	):
		extract_archive(temp_dir, 0, source_path)
	elif os.path.isdir(source_path):
		paths = os.listdir(source_path)
		archives = sorted(
			[
				f
				for f in paths
				if os.path.isfile(os.path.join(source_path, f))
				and os.path.splitext(f)[1].lower() in ARCHIVE_EXTENSIONS
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
				and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
				and not f.startswith(".")
			],
			key=natural_sort,
		)
		if archives:
			for i, archive in enumerate(archives):
				extract_archive(temp_dir, i, os.path.join(source_path, archive))
		elif sub_dirs:
			for i, sub_dir in enumerate(sub_dirs):
				sub_dir_path = os.path.join(source_path, sub_dir)
				move_images(sub_dir_path, temp_dir, i)
		elif images:
			move_images(source_path, temp_dir, 0)
	temp_images = []
	for f in os.listdir(temp_dir):
		temp_path = os.path.join(temp_dir, f)
		if (
			os.path.isfile(temp_path)
			and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
		):
			temp_images.append(f)
	temp_images = sorted(temp_images, key=natural_sort)
	image_counter = 1
	for temp_image in temp_images:
		temp_image_path = os.path.join(temp_dir, temp_image)
		extension = os.path.splitext(temp_image)[1].lower()
		output_filename = f"{image_counter:04d}{extension}"
		output_path = os.path.join(output_dir, output_filename)
		if os.path.exists(output_path):
			continue
		os.rename(temp_image_path, output_path)
		if os.path.exists(output_path):
			image_counter += 1
