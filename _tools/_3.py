import config
import json
import os
import sys


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
	mode = "delete"
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


if __name__ == "__main__":
	lists(
		config.ALL_IMAGES_LIST_FILENAME,
		sys.argv,
		config.DELETED_IMAGES_LIST_FILENAME,
		config.DIRS,
		config.KEPT_IMAGES_LIST_FILENAME,
	)
