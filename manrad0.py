import os

DIRS = {
	"img": "img",
	"img_audio": "img_audio",
	"img_boxed": "img_boxed",
	"img_crops": "img_crops",
	"img_crops_durations": "img_crops_durations",
	"img_deltas": "img_deltas",
	"img_grouped": "img_grouped",
	"img_resized": "img_resized",
	"img_text": "img_text",
	"merges": "merges",
	"render": "render",
}
if __name__ == "__main__":
	# Init
	for dir in DIRS.values():
		os.makedirs(dir, exist_ok=True)
