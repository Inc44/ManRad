# Autodetect target height and width using most common dimensions
from _0 import DIRS
from _2 import split_batches
from multiprocessing import Pool, cpu_count
import cv2
import os
import shutil

TARGET_HEIGHT = 1292
WORKERS = 6


def resize_fit_image(filename, input_dir, output_dir, target_height):
	path = os.path.join(input_dir, filename)
	image = cv2.imread(path)
	if image is None:
		return
	height, width = image.shape[:2]
	basename = os.path.splitext(filename)[0]
	output_path = os.path.join(output_dir, f"{basename}.jpg")
	if height == target_height and filename.lower().endswith((".jpg", ".jpeg")):
		shutil.copy(path, output_path)
		return
	if height > target_height:
		top_pad = (height - target_height) // 2
		bottom_pad = top_pad + target_height
		image = image[top_pad:bottom_pad, 0:width]
	else:
		top_pad = (target_height - height) // 2
		bottom_pad = target_height - height - top_pad
		image = cv2.copyMakeBorder(
			image, top_pad, bottom_pad, 0, 0, cv2.BORDER_CONSTANT, value=[0, 0, 0]
		)
	cv2.imwrite(output_path, image, [cv2.IMWRITE_JPEG_QUALITY, 100])


def batch_resize_images(batch, input_dir, output_dir, target_width):
	for filename in batch:
		resize_fit_image(filename, input_dir, output_dir, target_width)


if __name__ == "__main__":
	images = sorted(
		[f for f in os.listdir(DIRS["image_resized"]) if f.lower().endswith(".jpg")]
	)
	workers = min(WORKERS, cpu_count())
	batches = split_batches(workers, images)
	with Pool(processes=workers) as pool:
		args = [
			(batch, DIRS["image_resized"], DIRS["image_resized_fit"], TARGET_HEIGHT)
			for batch in batches
		]
		pool.starmap_async(batch_resize_images, args).get()
