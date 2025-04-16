from config import AUDIO, DELAY_DURATION, DIRS, FADE_VIDEO, MEDIA, TARGET_FPS
import cv2
import json
import os
import subprocess


def fade_images(input_path1, input_path2, output_dir, target_fps, transition_duration):
	image1 = cv2.imread(input_path1)
	image2 = cv2.imread(input_path2)
	frames = int(target_fps * transition_duration)
	input_stem1 = os.path.splitext(os.path.basename(input_path1))[0]
	for i in range(frames):
		alpha = i / (frames - 1)
		blended_image = cv2.addWeighted(image1, 1 - alpha, image2, alpha, 0)
		cv2.imwrite(
			os.path.join(output_dir, f"{input_stem1}{i:03d}.jpg"),
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


def render_media(audio, media, render_dir, video):
	video_path = os.path.join(render_dir, video)
	audio_path = os.path.join(render_dir, audio)
	render_path = os.path.join(render_dir, media)
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
	input_dir = DIRS["image_resized_fit"]
	output_dir = DIRS["image_resized_fit_fade"]
	merge_dir = DIRS["merge"]
	render_dir = DIRS["render"]
	target_fps = TARGET_FPS
	path = os.path.join(merge_dir, "page_durations.json")
	with open(path) as f:
		page_durations = json.load(f)
	path = os.path.join(merge_dir, "fade_video_list.txt")
	keys = sorted(page_durations.keys())
	with open(path, "w") as f:
		for i, key in enumerate(keys):
			duration = page_durations[key]
			prefix = key[:4]
			suffix = key[4:]
			input_path1 = os.path.join(input_dir, f"{prefix}.jpg")
			if suffix in ["000", "001"]:
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {1 / target_fps}\n")
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {duration - 1 / target_fps}\n")
			elif suffix == "999":
				if i + 1 < len(keys):
					next_key = keys[i + 1]
					next_prefix = next_key[:4]
					input_path2 = os.path.join(input_dir, f"{next_prefix}.jpg")
					fade_images(
						input_path1,
						input_path2,
						output_dir,
						target_fps,
						duration,
					)
					frames = int(target_fps * duration)
					for i in range(frames):
						path = os.path.join(output_dir, f"{prefix}{i:03d}.jpg")
						f.write(f"file '{os.path.abspath(path)}'\n")
						f.write(f"duration {duration / frames}\n")
		f.write(f"file '{os.path.abspath(path)}'\n")
		f.write(f"duration {1 / target_fps}\n")
		f.write(f"file '{os.path.abspath(path)}'\n")
		f.write(f"duration {DELAY_DURATION - 1 / target_fps}\n")
		f.write(f"file '{os.path.abspath(path)}'\n")
		f.write(f"duration {1 / target_fps}\n")
	render_fade_video(merge_dir, render_dir)
	render_media(AUDIO, MEDIA, render_dir, FADE_VIDEO)
