import os
import shutil
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


def run(zip_path):
	dirs = ["cbz", "temp", "img"]
	make_dirs(dirs)
	unzip(zip_path, "cbz")
	keep_files("cbz", "volume")
	extract_comics("cbz", "temp")
	move_files("temp", "img", [".jpg"])
	shutil.rmtree("temp")


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		run(sys.argv[1])
