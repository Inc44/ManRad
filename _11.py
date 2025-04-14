from _0 import DIRS
import cv2
import json
import os
import subprocess

TARGET_FPS = 60
TARGET_HEIGHT = 1292
TARGET_WIDTH = 900
WORKERS = 6

"""
def fade_images(input_path1, input_path2, output_path, target_fps, transition_duration):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-loop",
		"1",
		"-t",
		str(transition_duration),
		"-i",
		input_path1,
		"-loop",
		"1",
		"-t",
		str(transition_duration),
		"-i",
		input_path2,
		"-filter_complex",
		f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset=0",
		"-r",
		str(target_fps),
		"-frames:v",
		str(target_fps * transition_duration),
		"-c:v",
		"libx264",
		"-preset",
		"medium",
		output_path,
	]
	subprocess.run(cmd)
"""


def fade_images(input_path1, input_path2, output_path, target_fps, transition_duration):
	image1 = cv2.imread(input_path1)
	image2 = cv2.imread(input_path2)
	frames = int(target_fps * transition_duration)
	input_stem1 = os.path.splitext(os.path.basename(input_path1))[0]
	for i in range(frames):
		alpha = i / (frames - 1)
		blended_image = cv2.addWeighted(image1, 1 - alpha, image2, alpha, 0)
		cv2.imwrite(
			os.path.join(output_path, f"{input_stem1}{i:03d}.jpg"),
			blended_image,
			[cv2.IMWRITE_JPEG_QUALITY, 100],
		)


def render_fade_video(input_dir, output_dir):
	input_path = os.path.join(input_dir, "fade_video_list.txt")
	output_path = os.path.join(output_dir, "fade_video.mkv")
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
		input_path,
		"-fps_mode",
		"vfr",
		"-c:v",
		"libx264",
		"-preset",
		"medium",
		output_path,
	]
	subprocess.run(cmd)


def render_media(render_dir):
	video_path = os.path.join(render_dir, "fade_video.mkv")
	audio_path = os.path.join(render_dir, "audio.opus")
	render_path = os.path.join(render_dir, "ManRad.mkv")
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		video_path,
		"-i",
		audio_path,
		"-c",
		"copy",
		render_path,
	]
	subprocess.run(cmd)


if __name__ == "__main__":
	path = os.path.join(DIRS["merge"], "summed_durations.json")
	with open(path) as f:
		durations = json.load(f)
	path = os.path.join(DIRS["merge"], "fade_video_list.txt")
	keys = sorted(durations.keys())
	input_dir = DIRS["image_resized_fit"]
	output_dir = DIRS["image_resized_fit_fade"]
	merge_dir = DIRS["merge"]
	render_dir = DIRS["render"]
	target_fps = TARGET_FPS
	with open(path, "w") as f:
		for key in keys:
			duration = durations[key]
			input_prefix1 = key[:4]
			input_prefix2 = f"{int(input_prefix1) + 1:04d}"
			input_path1 = os.path.join(input_dir, f"{input_prefix1}.jpg")
			input_path2 = os.path.join(input_dir, f"{input_prefix2}.jpg")
			output_path = output_dir  # os.path.join(output_dir, f"{key}.mkv")
			if key[4:7] == "999":
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {1 / target_fps}\n")
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {duration - 1 / target_fps}\n")
			elif key[4:7] == "000" and key != keys[-2]:
				fade_images(
					input_path1,
					input_path2,
					output_path,
					target_fps,
					duration,
				)
				frames = int(target_fps * duration)
				for i in range(frames):
					path = os.path.join(output_path, f"{input_prefix1}{i:03d}.jpg")
					f.write(f"file '{os.path.abspath(path)}'\n")
					f.write(f"duration {duration/frames}\n")
				"""
				f.write(f"file '{os.path.abspath(output_path)}'\n")
				f.write(f"duration {duration}\n")
				"""
	render_fade_video(merge_dir, render_dir)
	render_media(render_dir)
