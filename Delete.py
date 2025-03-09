import json
import os
import sys


def del_images(dir):
	img = os.path.join(dir, "img")
	json_path = "test/not_manga.json"
	with open(json_path, "r") as f:
		files = json.load(f)
	for name in files:
		path = os.path.join(img, name)
		if os.path.exists(path):
			os.remove(path)


if __name__ == "__main__":
	if len(sys.argv) > 1:
		del_images(sys.argv[1])
