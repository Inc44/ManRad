import os

DIRS = {
	"img": "img",
	"img_boxed": "img_boxed",
	"img_crops": "img_crops",
	"img_deltas": "img_deltas",
	"img_grouped": "img_grouped",
	"img_resized": "img_resized",
	"output": "output",
}
if __name__ == "__main__":
	# Init
	for dir in DIRS.values():
		os.makedirs(dir, exist_ok=True)
