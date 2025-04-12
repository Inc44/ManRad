from PIL import Image
import os
import re
import shutil
import sys
import zipfile


def make_dirs(paths):
	for p in paths:
		os.makedirs(p, exist_ok=True)


def unzip(src, dst):
	with zipfile.ZipFile(src, "r") as zip_ref:
		zip_ref.extractall(dst)


def keep_files(path, term):
	for f in os.listdir(path):
		file_path = os.path.join(path, f)
		if os.path.isfile(file_path) and term not in f.lower():
			os.remove(file_path)


def extract_comics(src, dst):
	for f in [f for f in os.listdir(src) if f.endswith(".cbz")]:
		file_path = os.path.join(src, f)
		out_dir = os.path.join(dst, os.path.splitext(f)[0])
		os.makedirs(out_dir, exist_ok=True)
		unzip(file_path, out_dir)


def move_files(src, dst, exts):
	for root, _, files in os.walk(src):
		for f in [f for f in files if any(f.lower().endswith(e) for e in exts)]:
			src_path = os.path.join(root, f)
			name, ext = os.path.splitext(f)
			dst_path = os.path.join(dst, f)
			i = 1
			while os.path.exists(dst_path):
				dst_path = os.path.join(dst, f"{name}_{i}{ext}")
				i += 1
			shutil.move(src_path, dst_path)


def natural_sort_key(s):
	s = s.lower()
	return [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", s)]


def find_source_paths(src):
	if not os.path.isdir(src):
		return [src]
	subdirs = [d for d in os.listdir(src) if os.path.isdir(os.path.join(src, d))]
	if not subdirs:
		return [src]
	sorted_dirs = sorted(subdirs, key=natural_sort_key)
	return [os.path.join(src, d) for d in sorted_dirs]


def collect_image_files(path):
	image_exts = [".jpg", ".jpeg", ".png", ".webp"]
	images = []
	for root, _, files in os.walk(path):
		for f in files:
			if any(f.lower().endswith(ext) for ext in image_exts):
				images.append(os.path.join(root, f))
	images.sort(key=natural_sort_key)
	return images


def process_image(img_file, dst, counter):
	_, ext = os.path.splitext(img_file)
	ext = ext.lower()
	if ext in [".webp", ".png"]:
		img = Image.open(img_file)
		if img.mode not in ["L", "RGB"]:
			img = img.convert("RGB")
		new_ext = ".jpg"
		new_name = f"{counter:04d}{new_ext}"
		new_path = os.path.join(dst, new_name)
		img.save(new_path, "JPEG", quality=100)
		return counter + 1
	new_name = f"{counter:04d}{ext}"
	new_path = os.path.join(dst, new_name)
	shutil.copy2(img_file, new_path)
	return counter + 1


def process_images(src, dst):
	counter = 0
	source_paths = find_source_paths(src)
	for path in source_paths:
		image_files = collect_image_files(path)
		for img_file in image_files:
			counter = process_image(img_file, dst, counter)
	return counter


def run(input_path):
	if os.path.isdir(input_path):
		dirs = ["img"]
		make_dirs(dirs)
		process_images(input_path, "img")
	else:
		dirs = ["cbz", "temp", "img"]
		make_dirs(dirs)
		unzip(input_path, "cbz")
		keep_files("cbz", "volume")
		extract_comics("cbz", "temp")
		move_files("temp", "img", [".jpg"])
		shutil.rmtree("temp")


if __name__ == "__main__":
	if len(sys.argv) > 1:
		run(sys.argv[1])
