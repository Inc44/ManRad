from manrad0 import DIRS
from multiprocessing import Pool, cpu_count
import cv2
import os

TARGET_WIDTH = 750
WORKERS = 6


def resize_image(filename, input_dir, output_dir, target_width):
	path = os.path.join(input_dir, filename)
	image = cv2.imread(path)
	if image is None:
		return
	height, width = image.shape[:2]
	new_height = int((target_width / width) * height)
	resized = cv2.resize(
		image, (target_width, new_height), interpolation=cv2.INTER_AREA
	)
	output_path = os.path.join(output_dir, filename)
	cv2.imwrite(output_path, resized)


def split_batches(num_workers, items):
	batches = [[] for _ in range(num_workers)]
	for i, item in enumerate(items):
		batches[i % num_workers].append(item)
	return batches


def batch_resize_images(batch, input_dir, output_dir, target_width):
	for filename in batch:
		resize_image(filename, input_dir, output_dir, target_width)


if __name__ == "__main__":
	images = sorted(
		[f for f in os.listdir(DIRS["image"]) if f.lower().endswith(".jpg")]
	)
	workers = min(WORKERS, cpu_count())
	batches = split_batches(workers, images)
	with Pool(processes=workers) as pool:
		args = [
			(batch, DIRS["image"], DIRS["image_resized"], TARGET_WIDTH)
			for batch in batches
		]
		pool.starmap_async(batch_resize_images, args).get()
