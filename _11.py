from _0 import DIRS
import cv2
import os
import subprocess

TARGET_FPS = 60
TARGET_HEIGHT = 1350
TARGET_WIDTH = 900
WORKERS = 6


def fade_images(
	fps,
	image_path1,
	image_path2,
	lastframe,
	render_dir,
	transition_duration,
):
	image1 = cv2.imread(image_path1)
	image2 = cv2.imread(image_path2)
	if image1 is None or image2 is None:
		return lastframe
	frames = fps * transition_duration
	for i in range(frames):
		alpha = i / (frames - 1)
		blended_image = cv2.addWeighted(image1, 1 - alpha, image2, alpha, 0)
		framename = f"{lastframe:05d}.jpg"
		frame_path = os.path.join(render_dir, framename)
		cv2.imwrite(frame_path, blended_image, [cv2.IMWRITE_JPEG_QUALITY, 100])
		lastframe += 1
	return lastframe + frames


def render_fade_video(input_dir, render_dir):
	input_path = os.path.join(input_dir, "fade_video_list.txt")
	render_path = os.path.join(render_dir, "fade_video.mkv")
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
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
		render_path,
	]
	subprocess.run(cmd)


def render_media(audio_dir, video_dir, render_dir):
	video_path = os.path.join(video_dir, "fade_video.mkv")
	audio_path = os.path.join(audio_dir, "audio.txt")
	render_path = os.path.join(render_dir, "fade_video.mkv")
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
	audios = sorted(
		[
			f
			for f in os.listdir(DIRS["image_audio_resized"])
			if f.lower().endswith(".wav")
		]
	)
