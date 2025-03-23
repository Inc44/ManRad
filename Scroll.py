from PIL import Image
from functools import lru_cache
import json
import math
import os
import subprocess


def get_files_with_extension(directory, extension):
	return sorted([f for f in os.listdir(directory) if f.lower().endswith(extension)])


def get_image_paths(directory):
	return get_files_with_extension(directory, ".jpg")


def get_json_paths(directory):
	return get_files_with_extension(directory, ".json")


def combine_images(img_dir):
	image_paths = get_image_paths(img_dir)
	first_image = Image.open(os.path.join(img_dir, image_paths[0]))
	width, _ = first_image.size
	first_image.close()
	images = []
	total_height = 0
	for img_path in image_paths:
		img = Image.open(os.path.join(img_dir, img_path))
		images.append(img)
		total_height += img.size[1]
	combined_image = Image.new("RGB", (width, total_height))
	current_y = 0
	for img in images:
		combined_image.paste(img, (0, current_y))
		current_y += img.size[1]
		img.close()
	return combined_image, width


def load_all_delta_data(delta_dir):
	delta_paths = get_json_paths(delta_dir)
	all_deltas = []
	for delta_path in delta_paths:
		with open(os.path.join(delta_dir, delta_path), "r") as f:
			deltas = json.load(f)
			all_deltas.append(deltas)
	return all_deltas


def load_duration_data(output_dir):
	duration_path = os.path.join(output_dir, "audio_durations.json")
	with open(duration_path, "r") as f:
		return json.load(f)


@lru_cache(maxsize=2048)
def cubic_easing(t):
	if t < 0.5:
		return 4 * t * t * t
	return 1 - pow(-2 * t + 2, 3) / 2


@lru_cache(maxsize=2048)
def acceleration_easing(t):
	if t < 0.4:
		return 2.5 * t * t
	elif t < 0.8:
		return 0.4 + (t - 0.4) * 1.2
	else:
		return 0.88 + (1 - math.pow(1 - (t - 0.8) / 0.2, 2)) * 0.12


def ensure_directory_exists(dir_path):
	os.makedirs(dir_path, exist_ok=True)


def setup_ffmpeg_process(output_file, width, height, fps):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		# "-loglevel",
		# "error",
		"-f",
		"rawvideo",
		"-c:v",
		"rawvideo",
		"-s",
		f"{width}x{height}",
		"-pix_fmt",
		"rgb24",
		"-r",
		str(fps),
		"-i",
		"-",
		# "-vf",
		# "mpdecimate",
		"-c:v",
		"h264_nvenc",
		"-preset",
		"p7",
		"-rc",
		"constqp",
		"-profile:v",
		"high",
		"-g",
		"999999",
		output_file,
	]
	return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def write_frame(image, ffmpeg_process):
	raw_bytes = image.tobytes()
	ffmpeg_process.stdin.write(raw_bytes)


def add_static_frames(image, ffmpeg_process, frame_count):
	for _ in range(frame_count):
		write_frame(image, ffmpeg_process)
	return frame_count


def process_animation_segment(
	combined_image,
	width,
	height,
	start_y,
	deltas,
	duration,
	ffmpeg_process,
	frame_index,
	fps,
):
	segment_frame_count = round(duration * fps)
	if not deltas or sum(deltas) == 0:
		viewport = combined_image.crop((0, int(start_y), width, int(start_y + height)))
		for _ in range(segment_frame_count):
			write_frame(viewport, ffmpeg_process)
		return frame_index + segment_frame_count, start_y
	positions = [start_y]
	for delta in deltas:
		positions.append(positions[-1] + delta)
	total_movement = sum(deltas)
	time_ratios = [delta / total_movement for delta in deltas]
	time_markers = [0]
	for ratio in time_ratios:
		time_markers.append(time_markers[-1] + ratio * duration)
	for frame in range(segment_frame_count):
		current_time = frame / segment_frame_count * duration
		segment_index = 0
		while (
			segment_index < len(time_markers) - 1
			and current_time > time_markers[segment_index + 1]
		):
			segment_index += 1
		if segment_index >= len(deltas):
			y_position = positions[-1]
		else:
			segment_duration = (
				time_markers[segment_index + 1] - time_markers[segment_index]
			)
			if segment_duration == 0:
				progress = 1.0
			else:
				progress = (
					current_time - time_markers[segment_index]
				) / segment_duration
			eased_progress = acceleration_easing(progress)
			position_delta = positions[segment_index + 1] - positions[segment_index]
			y_position = positions[segment_index] + eased_progress * position_delta
		y_position = max(0, min(y_position, combined_image.height - height))
		viewport = combined_image.crop(
			(0, int(y_position), width, int(y_position + height))
		)
		write_frame(viewport, ffmpeg_process)
	return frame_index + segment_frame_count, positions[-1]


def create_animation_video(
	combined_image, width, all_deltas, durations, output_file, static_duration=5.0
):
	fps = 60
	height = 1350
	ffmpeg_process = setup_ffmpeg_process(output_file, width, height, fps)
	intro_frame_count = round(static_duration * fps)
	initial_viewport = combined_image.crop((0, 0, width, height))
	current_frame = add_static_frames(
		initial_viewport, ffmpeg_process, intro_frame_count
	)
	current_y = 0
	for deltas, duration in zip(all_deltas, durations):
		current_frame, current_y = process_animation_segment(
			combined_image,
			width,
			height,
			current_y,
			deltas,
			duration,
			ffmpeg_process,
			current_frame,
			fps,
		)
	ffmpeg_process.stdin.close()
	ffmpeg_process.wait()
	return current_frame


def create_scrolling_video(
	img_dir, delta_dir, output_dir, output_file, intro_duration=6.0
):
	ensure_directory_exists(output_dir)
	output_path = os.path.join(output_dir, output_file)
	combined_image, width = combine_images(img_dir)
	all_deltas = load_all_delta_data(delta_dir)
	durations = load_duration_data(output_dir)
	if len(all_deltas) != len(durations):
		return 0
	total_frames = create_animation_video(
		combined_image, width, all_deltas, durations, output_path, intro_duration
	)
	return total_frames


if __name__ == "__main__":
	img_directory = "img"
	delta_directory = "delta"
	output_directory = "output"
	output_filename = "scroll.mkv"
	create_scrolling_video(
		img_directory,
		delta_directory,
		output_directory,
		output_filename,
		intro_duration=6.0,
	)
