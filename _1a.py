import os
import stat
import zipfile
import shutil
import regex
from pathlib import Path

SOURCE_FILE_OR_DIRECTORY_PATHS = [
	"Kage_no_Jitsuryokusha_ni_Naritakute_.zip",  # Kotatsu ZIP
	"Kage_no_Jitsuryokusha_ni_Naritakute_",  # Kotatsu CBZ/DIR
	"The Eminence in Shadow_001",  # HakuNeko Images (Dir of Dirs)
	"The Eminence in Shadow_002",  # HakuNeko CBZ (Dir of CBZs)
]
SELECTED_SOURCE_INDEX = 3
TARGET_DIRECTORY_NAME = "images_1"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_ARCHIVE_EXTENSIONS = {".zip", ".cbz"}


def get_natural_sort_key(item_name_string):
	item_name_string = str(item_name_string).lower()
	return [
		int(c) if c.isdigit() else c for c in regex.split(r"(\d+)", item_name_string)
	]


def file_is_image(file_path_object):
	return file_path_object.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def file_is_archive(file_path_object):
	return file_path_object.suffix.lower() in ALLOWED_ARCHIVE_EXTENSIONS


def remove_directory_recursive(directory_path_object):
	def handle_remove_error(func, path_str, exc_info):
		path_object = Path(path_str)
		can_write = os.access(path_object, os.W_OK)
		if not can_write:
			os.chmod(path_object, stat.S_IWUSR)
			if path_object.is_file():
				os.remove(path_object)
			elif path_object.is_dir():
				os.rmdir(path_object)

	if directory_path_object.exists():
		shutil.rmtree(
			directory_path_object, ignore_errors=False, onerror=handle_remove_error
		)


def prepare_directory(directory_path_object):
	directory_path_object.mkdir(parents=True, exist_ok=True)
	return directory_path_object.exists()


def extract_archive_members_to_work_area(archive_path, work_area_path, archive_index):
	if not zipfile.is_zipfile(archive_path):
		return False
	all_extracted = True
	zip_object = zipfile.ZipFile(archive_path, "r")
	for member_info in zip_object.infolist():
		is_directory = member_info.is_dir()
		is_system_file = member_info.filename.startswith(("__MACOSX", "."))
		if not is_directory and not is_system_file:
			original_file_name = Path(member_info.filename).name
			if not original_file_name:
				continue
			unique_temp_name = f"{archive_index:04d}_{original_file_name}"
			target_file_path = work_area_path / unique_temp_name
			member_data = zip_object.read(member_info.filename)
			bytes_written = target_file_path.write_bytes(member_data)
			if bytes_written != len(member_data):
				all_extracted = False
	zip_object.close()
	return all_extracted


def copy_directory_images_to_work_area(
	source_subdir_path, work_area_path, subdir_index
):
	all_copied = True
	image_files = []
	for item in source_subdir_path.iterdir():
		is_valid_file = (
			item.is_file() and file_is_image(item) and not item.name.startswith(".")
		)
		if is_valid_file:
			image_files.append(item)
	sorted_image_files = sorted(image_files, key=get_natural_sort_key)
	for img_file in sorted_image_files:
		unique_temp_name = f"{subdir_index:04d}_{img_file.name}"
		target_file_path = work_area_path / unique_temp_name
		result_path = shutil.copy2(img_file, target_file_path)
		if not Path(result_path).exists():
			all_copied = False
	return all_copied


def process_selected_source(source_path_string, target_dir_name_string):
	source_location = Path(source_path_string).resolve()
	target_directory = Path(target_dir_name_string).resolve()
	temporary_work_area = target_directory / "temp_work"
	if not source_location.exists():
		return False
	if not os.access(source_location, os.R_OK):
		return False
	target_parent = target_directory.parent
	if not os.access(target_parent, os.W_OK):
		return False
	remove_directory_recursive(temporary_work_area)
	if not prepare_directory(target_directory):
		return False
	if not prepare_directory(temporary_work_area):
		return False
	collection_success = True
	if source_location.is_file() and file_is_archive(source_location):
		collection_success = extract_archive_members_to_work_area(
			source_location, temporary_work_area, 0
		)
	elif source_location.is_dir():
		all_items = list(source_location.iterdir())
		archive_files = sorted(
			[item for item in all_items if item.is_file() and file_is_archive(item)],
			key=get_natural_sort_key,
		)
		subdirectories = sorted(
			[item for item in all_items if item.is_dir()], key=get_natural_sort_key
		)
		loose_image_files = sorted(
			[
				item
				for item in all_items
				if item.is_file()
				and file_is_image(item)
				and not file_is_archive(item)
				and not item.name.startswith(".")
			],
			key=get_natural_sort_key,
		)
		if archive_files:
			for index, archive_path in enumerate(archive_files):
				if not extract_archive_members_to_work_area(
					archive_path, temporary_work_area, index
				):
					collection_success = False
		elif subdirectories:
			for index, subdir_path in enumerate(subdirectories):
				if not os.access(subdir_path, os.R_OK):
					collection_success = False
					continue
				if not copy_directory_images_to_work_area(
					subdir_path, temporary_work_area, index
				):
					collection_success = False
		elif loose_image_files:
			if not copy_directory_images_to_work_area(
				source_location, temporary_work_area, 0
			):
				collection_success = False
		else:
			collection_success = False
	else:
		collection_success = False
	if not collection_success:
		remove_directory_recursive(temporary_work_area)
		return False
	temp_files = list(temporary_work_area.glob("*"))
	image_files_in_work_area = sorted(
		[f for f in temp_files if f.is_file() and file_is_image(f)],
		key=get_natural_sort_key,
	)
	move_success = True
	image_counter = 1
	for current_temp_path in image_files_in_work_area:
		file_extension = current_temp_path.suffix.lower()
		new_target_name = f"{image_counter:04d}{file_extension}"
		final_target_path = target_directory / new_target_name
		if final_target_path.exists():
			move_success = False
			continue
		shutil.move(str(current_temp_path), str(final_target_path))
		if not final_target_path.exists():
			move_success = False
		else:
			image_counter = image_counter + 1
	remove_directory_recursive(temporary_work_area)
	return collection_success and move_success


selected_source_path = SOURCE_FILE_OR_DIRECTORY_PATHS[SELECTED_SOURCE_INDEX]
processing_result = process_selected_source(selected_source_path, TARGET_DIRECTORY_NAME)
