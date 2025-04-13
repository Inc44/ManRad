import os

DIRS = {
	"image": "image",
	"image_audio": "image_audio",
	"image_audio_resized": "image_audio_resized",
	"image_boxed": "image_boxed",
	"image_crops": "image_crops",
	"image_durations": "image_durations",
	"image_gaps": "image_gaps",
	"image_grouped": "image_grouped",
	"image_resized": "image_resized",
	"image_text": "image_text",
	"merge": "merge",
	"render": "render",
	"temp": "temp",
}


def create_directories():
	for dir_path in DIRS.values():
		os.makedirs(dir_path, exist_ok=True)


if __name__ == "__main__":
	create_directories()
