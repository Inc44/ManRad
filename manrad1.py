from manrad0 import DIRS
from multiprocessing import Pool, cpu_count
import cv2
import os

CORES = 6
WIDTH = 750


def img_resize(filename, input_dir, output_dir):
	path = os.path.join(input_dir, filename)
	image = cv2.imread(path)
	(h, w) = image.shape[:2]
	height = int((WIDTH / w) * h)
	resized = cv2.resize(image, (WIDTH, height), interpolation=cv2.INTER_AREA)
	img_resized = os.path.join(output_dir, filename)
	cv2.imwrite(img_resized, resized)


def batches_distribute(cores, imgs):
	batches = [[] for _ in range(cores)]
	for i, filename in enumerate(imgs):
		worker = i % cores
		batches[worker].append(filename)
	return batches


def batch_img_resize(args):
	batch, input_dir, output_dir_resized = args
	for filename in batch:
		img_resize(filename, input_dir, output_dir_resized)


if __name__ == "__main__":
	# Resize
	imgs = sorted([f for f in os.listdir(DIRS["img"]) if f.lower().endswith(".jpg")])
	cores = min(CORES, cpu_count())
	batches = batches_distribute(cores, imgs)
	with Pool(processes=cores) as pool:
		args = [(batch, DIRS["img"], DIRS["img_resized"]) for batch in batches]
		pool.map_async(batch_img_resize, args).get()
