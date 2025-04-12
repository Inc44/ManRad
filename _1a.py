from _1 import DIRS
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


def extract_zip(zip_path, output_dir, prefix_index):
	if not zipfile.is_zipfile(zip_path):
		return
	with zipfile.ZipFile(zip_path, "r") as f:
		for file_info in f.infolist():
			original_name = os.path.basename(file_info.filename)
			new_name = f"{prefix_index:04d}_{original_name}"
			output_path = os.path.join(output_dir, new_name)
			file_data = f.read(file_info.filename)
			with open(output_path, "wb") as f:
				f.write(file_data)


def copy_images_from_folder(source_folder, dest_folder, prefix_index):
	images = [
		file
		for file in os.listdir(source_folder)
		if os.path.isfile(os.path.join(source_folder, file))
		and os.path.splitext(file)[1].lower() in IMAGE_EXTS
		and not file.startswith(".")
	]
	for image in sorted(images, key=natural_sort):
		new_name = f"{prefix_index:04d}_{image}"
		new_path = os.path.join(dest_folder, new_name)
		shutil.copy2(os.path.join(source_folder, image), new_path)


if __name__ == "__main__":
	source = SOURCES[0]
	output_folder = DIRS["image"]
	temp_folder = DIRS["temp"]
	if os.path.isfile(source) and os.path.splitext(source)[1].lower() in ARCHIVE_EXTS:
		extract_zip(source, temp_folder, 0)
	elif os.path.isdir(source):
		items = os.listdir(source)
		archive_files = sorted(
			[
				f
				for f in items
				if os.path.isfile(os.path.join(source, f))
				and os.path.splitext(f)[1].lower() in ARCHIVE_EXTS
			],
			key=natural_sort,
		)
		subfolders = sorted(
			[f for f in items if os.path.isdir(os.path.join(source, f))],
			key=natural_sort,
		)
		image_files = sorted(
			[
				f
				for f in items
				if os.path.isfile(os.path.join(source, f))
				and os.path.splitext(f)[1].lower() in IMAGE_EXTS
				and not f.startswith(".")
			],
			key=natural_sort,
		)
		if archive_files:
			for idx, archive in enumerate(archive_files):
				extract_zip(os.path.join(source, archive), temp_folder, idx)
		elif subfolders:
			for idx, folder in enumerate(subfolders):
				folder_path = os.path.join(source, folder)
				if not os.access(folder_path, os.R_OK):
					continue
				copy_images_from_folder(folder_path, temp_folder, idx)
		elif image_files:
			copy_images_from_folder(source, temp_folder, 0)
	temp_images = []
	for file in os.listdir(temp_folder):
		file_path = os.path.join(temp_folder, file)
		if (
			os.path.isfile(file_path)
			and os.path.splitext(file)[1].lower() in IMAGE_EXTS
		):
			temp_images.append(file)
	temp_images = sorted(temp_images, key=natural_sort)
	image_number = 1
	for temp_image in temp_images:
		image_path = os.path.join(temp_folder, temp_image)
		ext = os.path.splitext(temp_image)[1].lower()
		new_filename = f"{image_number:04d}{ext}"
		dest_path = os.path.join(output_folder, new_filename)
		if os.path.exists(dest_path):
			continue
		shutil.move(image_path, dest_path)
		if os.path.exists(dest_path):
			image_number += 1
