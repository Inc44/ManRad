import config
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


def render_fade_video(
	fade_video_filename, fade_video_list_filename, input_dir, output_dir
):
	input_path = os.path.join(input_dir, fade_video_list_filename)
	output_path = os.path.join(output_dir, fade_video_filename)
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


def render_media(audio_filename, media_filename, render_dir, video_filename):
	video_path = os.path.join(render_dir, video_filename)
	audio_path = os.path.join(render_dir, audio_filename)
	render_path = os.path.join(render_dir, media_filename)
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
	audio_filename = config.AUDIO
	delay_duration = config.DELAY_DURATION
	delay_suffix = config.DELAY_SUFFIX
	dirs = config.DIRS
	fade_video_filename = config.FADE_VIDEO
	fade_video_list_filename = config.FADE_VIDEO_LIST_FILENAME
	frame_suffix_length = config.FRAME_SUFFIX_LENGTH
	media_filename = config.MEDIA
	page_durations_filename = config.PAGE_DURATIONS_FILENAME
	prefix_length = config.PREFIX_LENGTH
	sum_suffix = config.SUM_SUFFIX
	target_fps = config.TARGET_FPS
	transition_suffix = config.TRANSITION_SUFFIX
	input_dir = dirs["image_resized_fit"]
	output_dir = dirs["image_resized_fit_fade"]
	merge_dir = dirs["merge"]
	render_dir = dirs["render"]
	path = os.path.join(merge_dir, page_durations_filename)
	with open(path) as f:
		page_durations = json.load(f)
	path = os.path.join(merge_dir, fade_video_list_filename)
	keys = sorted(page_durations.keys())
	with open(path, "w") as f:
		for i, key in enumerate(keys):
			duration = page_durations[key]
			prefix = key[:prefix_length]
			suffix = key[prefix_length:]
			input_path1 = os.path.join(input_dir, f"{prefix}.jpg")
			if suffix == delay_suffix or suffix == sum_suffix:
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {1 / target_fps}\n")
				f.write(f"file '{os.path.abspath(input_path1)}'\n")
				f.write(f"duration {duration - 1 / target_fps}\n")
			elif suffix == transition_suffix:
				if i + 1 < len(keys):
					next_key = keys[i + 1]
					next_prefix = next_key[:prefix_length]
					input_path2 = os.path.join(input_dir, f"{next_prefix}.jpg")
					fade_images(
						input_path1,
						input_path2,
						output_dir,
						target_fps,
						duration,
					)
					frames = int(target_fps * duration)
					for j in range(frames):
						path_frame = os.path.join(
							output_dir, f"{prefix}{j:0{frame_suffix_length}d}.jpg"
						)
						f.write(f"file '{os.path.abspath(path_frame)}'\n")
						f.write(f"duration {duration / frames}\n")
		last_frame_path = path_frame if "path_frame" in locals() else input_path1
		f.write(f"file '{os.path.abspath(last_frame_path)}'\n")
		f.write(f"duration {1 / target_fps}\n")
		f.write(f"file '{os.path.abspath(last_frame_path)}'\n")
		f.write(f"duration {delay_duration - 1 / target_fps}\n")
		f.write(f"file '{os.path.abspath(last_frame_path)}'\n")
		f.write(f"duration {1 / target_fps}\n")
	render_fade_video(
		fade_video_filename, fade_video_list_filename, merge_dir, render_dir
	)
	render_media(audio_filename, media_filename, render_dir, fade_video_filename)
