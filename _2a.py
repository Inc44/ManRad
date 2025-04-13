from _0 import DIRS
import os
import json


def get_file_basenames(directory):
	basenames = set()
	if os.path.exists(directory):
		for filename in os.listdir(directory):
			if os.path.isfile(os.path.join(directory, filename)):
				basename = os.path.splitext(filename)[0]
				basenames.add(basename)
	return basenames


def compare_directories():
	image_dir = DIRS["image"]
	image_resize_dir = DIRS["image_resized"]
	original_files = get_file_basenames(image_dir)
	resized_files = get_file_basenames(image_resize_dir)
	kept_files = list(resized_files)
	deleted_files = list(original_files - resized_files)
	kept_files.sort()
	deleted_files.sort()
	output_dir = DIRS["merge"]
	os.makedirs(output_dir, exist_ok=True)
	kept_path = os.path.join(output_dir, "kept_files.json")
	with open(kept_path, "w", encoding="utf-8") as f:
		json.dump(kept_files, f, indent="\t")
	deleted_path = os.path.join(output_dir, "deleted_files.json")
	with open(deleted_path, "w", encoding="utf-8") as f:
		json.dump(deleted_files, f, indent="\t")


if __name__ == "__main__":
	compare_directories()
