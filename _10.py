import os
import subprocess
import cv2
import shutil

TARGET_FPS = 60
TARGET_HEIGHT = 1350
TARGET_WIDTH = 900


def render_fade_video(input_dir, render_dir):
	path_input = os.path.join(input_dir, "fade_video_list.txt")
	path_render = os.path.join(render_dir, "fade_video.mkv")
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-f",
		"concat",
		"-safe",
		"0",
		"-i",
		path_input,
		"-fps_mode",
		"vfr",
		"-c:v",
		"libx264",
		"-preset",
		"medium",
		path_render,
	]
	subprocess.run(cmd)


def resize_image_to_fit(filename, input_dir, output_dir, target_height):
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
