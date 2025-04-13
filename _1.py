from _0 import DIRS
import os
import regex
import shutil
import zipfile

SOURCES = [
	"Kage_no_Jitsuryokusha_ni_Naritakute_",  # Kotatsu CBZ or DIR
	"Kage_no_Jitsuryokusha_ni_Naritakute_.zip",  # Kotatsu ZIP
	"The Eminence in Shadow_001",  # HakuNeko Images
	"The Eminence in Shadow_002",  # HakuNeko CBZ
]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ARCHIVE_EXTS = {".cbz", ".zip"}


def natural_sort(text):
	text = str(text).lower()
	return [
		int(part) if part.isdigit() else part for part in regex.split(r"(\d+)", text)
	]


def extract(output_dir, prefix, zip_path):
	if not zipfile.is_zipfile(zip_path):
		return
	with zipfile.ZipFile(zip_path, "r") as f:
		for info in f.infolist():
			basename = os.path.basename(info.filename)
			filename = f"{prefix:04d}_{basename}"
			path = os.path.join(output_dir, filename)
			data = f.read(info.filename)
			with open(path, "wb") as f:
				f.write(data)


def move(input_dir, output_dir, prefix):
	images = [
		f
		for f in os.listdir(input_dir)
		if os.path.isfile(os.path.join(input_dir, f))
		and os.path.splitext(f)[1].lower() in IMAGE_EXTS
		and not f.startswith(".")
	]
	for image in sorted(images, key=natural_sort):
		filename = f"{prefix:04d}_{image}"
		path = os.path.join(output_dir, filename)
		os.rename(os.path.join(input_dir, image), path)


if __name__ == "__main__":
	source = SOURCES[0]
	output_dir = DIRS["image"]
	temp_dir = DIRS["temp"]
	if os.path.isfile(source) and os.path.splitext(source)[1].lower() in ARCHIVE_EXTS:
		extract(source, temp_dir, 0)
	elif os.path.isdir(source):
		items = os.listdir(source)
		archives = sorted(
			[
				f
				for f in items
				if os.path.isfile(os.path.join(source, f))
				and os.path.splitext(f)[1].lower() in ARCHIVE_EXTS
			],
			key=natural_sort,
		)
		sub_dirs = sorted(
			[f for f in items if os.path.isdir(os.path.join(source, f))],
			key=natural_sort,
		)
		images = sorted(
			[
				f
				for f in items
				if os.path.isfile(os.path.join(source, f))
				and os.path.splitext(f)[1].lower() in IMAGE_EXTS
				and not f.startswith(".")
			],
			key=natural_sort,
		)
		if archives:
			for i, archive in enumerate(archives):
				extract(os.path.join(source, archive), temp_dir, i)
		elif sub_dirs:
			for i, sub_dir in enumerate(sub_dirs):
				path = os.path.join(source, sub_dir)
				if not os.access(path, os.R_OK):
					continue
				move(path, temp_dir, i)
		elif images:
			move(source, temp_dir, 0)
	temp_images = []
	for f in os.listdir(temp_dir):
		path = os.path.join(temp_dir, f)
		if os.path.isfile(path) and os.path.splitext(f)[1].lower() in IMAGE_EXTS:
			temp_images.append(f)
	temp_images = sorted(temp_images, key=natural_sort)
	counter = 1
	for temp_image in temp_images:
		temp_path = os.path.join(temp_dir, temp_image)
		ext = os.path.splitext(temp_image)[1].lower()
		filename = f"{counter:04d}{ext}"
		path = os.path.join(output_dir, filename)
		if os.path.exists(path):
			continue
		shutil.move(temp_path, path)
		if os.path.exists(path):
			counter += 1
