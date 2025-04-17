import config
from multiprocessing import Pool, cpu_count
import cv2
import os
import shutil


def resize_image(filename, input_dir, output_dir, output_image_extension, target_width):
	path = os.path.join(input_dir, filename)
	image = cv2.imread(path)
	if image is None:
		return
	height, width = image.shape[:2]
	basename = os.path.splitext(filename)[0]
	output_path = os.path.join(output_dir, f"{basename}{output_image_extension}")
	if width == target_width and filename.lower().endswith((".jpg", ".jpeg")):
		shutil.copy(path, output_path)
		return
	if width != target_width:
		new_height = int((target_width / width) * height)
		image = cv2.resize(
			image, (target_width, new_height), interpolation=cv2.INTER_AREA
		)
	cv2.imwrite(output_path, image, [cv2.IMWRITE_JPEG_QUALITY, 100])


def split_batches(items, num_workers):
	batches = [[] for _ in range(num_workers)]
	for i, item in enumerate(items):
		batches[i % num_workers].append(item)
	return batches


def batch_resize_images(
	batch, input_dir, output_dir, output_image_extension, target_width
):
	for filename in batch:
		resize_image(
			filename, input_dir, output_dir, output_image_extension, target_width
		)


def resize_to_width(
	dirs, image_extensions, output_image_extension, target_width, workers_config
):
	images = sorted(
		[
			f
			for f in os.listdir(dirs["image"])
			if any(f.lower().endswith(ext) for ext in image_extensions)
		]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(images, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				batch,
				dirs["image"],
				dirs["image_resized"],
				output_image_extension,
				target_width,
			)
			for batch in batches
		]
		pool.starmap_async(batch_resize_images, args).get()


if __name__ == "__main__":
	resize_to_width(
		config.DIRS,
		config.IMAGE_EXTENSIONS,
		config.OUTPUT_IMAGE_EXTENSION,
		config.TARGET_WIDTH,
		config.WORKERS,
	)
