from _0 import DIRS
import json
import os
import sys

DELETED_IMAGES_PATH = "deleted_images.json"
IMAGES_PATH = "images.json"
KEPT_IMAGES_PATH = "kept_images.json"


def get_basenames(input_dir):
	basenames = set()
	if os.path.exists(input_dir):
		for filename in os.listdir(input_dir):
			if os.path.isfile(os.path.join(input_dir, filename)):
				basename = os.path.splitext(filename)[0]
				basenames.add(basename)
	return basenames


def get_filename(input_dir, basename):
	if os.path.exists(input_dir):
		for filename in os.listdir(input_dir):
			if (
				os.path.isfile(os.path.join(input_dir, filename))
				and os.path.splitext(filename)[0] == basename
			):
				return filename
	return None


if __name__ == "__main__":
	mode = "delete"
	if len(sys.argv) > 1:
		mode = sys.argv[1]
	merge_dir = DIRS["merge"]
	images_dir = DIRS["image"]
	resized_images_dir = DIRS["image_resized"]
	deleted_images_path = os.path.join(merge_dir, DELETED_IMAGES_PATH)
	images_path = os.path.join(merge_dir, IMAGES_PATH)
	kept_images_path = os.path.join(merge_dir, KEPT_IMAGES_PATH)
	if mode == "save":
		images_paths = get_basenames(images_dir)
		resized_images_paths = get_basenames(resized_images_dir)
		kept_images = sorted(list(resized_images_paths))
		deleted_images = sorted(list(images_paths - resized_images_paths))
		images = sorted(list(images_paths))
		with open(deleted_images_path, "w") as f:
			json.dump(deleted_images, f, indent="\t")
		with open(images_path, "w") as f:
			json.dump(images, f, indent="\t")
		with open(kept_images_path, "w") as f:
			json.dump(kept_images, f, indent="\t")
	elif mode == "delete":
		if not os.path.exists(deleted_images_path):
			exit()
		with open(deleted_images_path, "r") as f:
			deleted_images = json.load(f)
		for basename in deleted_images:
			filename = get_filename(resized_images_dir, basename)
			if filename:
				path = os.path.join(resized_images_dir, filename)
				if os.path.exists(path):
					os.remove(path)
