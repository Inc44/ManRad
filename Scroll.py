from PIL import Image
from functools import lru_cache
import json
import os


def get_image_files(directory):
	return sorted([f for f in os.listdir(directory) if f.lower().endswith(".jpg")])


def get_json_files(directory):
	return sorted([f for f in os.listdir(directory) if f.lower().endswith(".json")])


def create_stitched_image(img_dir):
	image_files = get_image_files(img_dir)
	first_image = Image.open(os.path.join(img_dir, image_files[0]))
	width, height = first_image.size
	total_height = height * len(image_files)
	stitched_image = Image.new("RGB", (width, total_height))
	for i, img_file in enumerate(image_files):
		img = Image.open(os.path.join(img_dir, img_file))
		stitched_image.paste(img, (0, i * height))
	return stitched_image, width


def collect_delta_data(delta_dir):
	delta_files = get_json_files(delta_dir)
	all_deltas = []
	for delta_file in delta_files:
		with open(os.path.join(delta_dir, delta_file), "r") as f:
			deltas = json.load(f)
			all_deltas.append(deltas)
	return all_deltas


def read_duration_data(output_dir):
	with open(os.path.join(output_dir, "audio_durations.json"), "r") as f:
		return json.load(f)


@lru_cache(maxsize=1024)
def calculate_easing(t):
	if t < 0.5:
		return 4 * t * t * t
	else:
		return 1 - pow(-2 * t + 2, 3) / 2


def make_directory(dir_path):
	os.makedirs(dir_path, exist_ok=True)


def write_frame(image, path, quality=100):
	image.save(path, quality=quality)


def create_static_frames(image, output_dir, count):
	for frame in range(count):
		frame_filename = os.path.join(output_dir, f"frame_{frame:04d}.jpg")
		write_frame(image, frame_filename)
	return count


def process_segment(
	stitched_image,
	width,
	height,
	start_position,
	deltas,
	duration,
	output_dir,
	start_frame,
	fps,
):
	segment_frames = int(duration * fps)
	if not deltas or sum(deltas) == 0:
		viewport = stitched_image.crop(
			(0, int(start_position), width, int(start_position + height))
		)
		for frame in range(segment_frames):
			frame_filename = os.path.join(
				output_dir, f"frame_{start_frame + frame:04d}.jpg"
			)
			write_frame(viewport, frame_filename)
		return start_frame + segment_frames, start_position
	positions = [start_position]
	for delta in deltas:
		positions.append(positions[-1] + delta)
	total_distance = sum(deltas)
	time_proportions = [delta / total_distance for delta in deltas]
	time_points = [0]
	for proportion in time_proportions:
		time_points.append(time_points[-1] + proportion * duration)
	for frame in range(segment_frames):
		current_time = frame / segment_frames * duration
		sub_segment = 0
		while (
			sub_segment < len(time_points) - 1
			and current_time > time_points[sub_segment + 1]
		):
			sub_segment += 1
		if sub_segment >= len(deltas):
			y_position = positions[-1]
		else:
			sub_segment_duration = (
				time_points[sub_segment + 1] - time_points[sub_segment]
			)
			if sub_segment_duration == 0:
				progress = 1.0
			else:
				progress = (
					current_time - time_points[sub_segment]
				) / sub_segment_duration
			eased_progress = calculate_easing(progress)
			y_position = positions[sub_segment] + eased_progress * (
				positions[sub_segment + 1] - positions[sub_segment]
			)
		y_position = max(0, min(y_position, stitched_image.height - height))
		viewport = stitched_image.crop(
			(0, int(y_position), width, int(y_position + height))
		)
		frame_filename = os.path.join(
			output_dir, f"frame_{start_frame + frame:04d}.jpg"
		)
		write_frame(viewport, frame_filename)
	return start_frame + segment_frames, positions[-1]


def build_animation_frames(
	stitched_image, width, all_deltas, durations, output_dir, static_duration=5.0
):
	make_directory(output_dir)
	fps = 30
	height = 1350
	static_intro_frames = int(static_duration * fps)
	initial_viewport = stitched_image.crop((0, 0, width, height))
	current_frame = create_static_frames(
		initial_viewport, output_dir, static_intro_frames
	)
	current_position = 0
	for segment_idx, (deltas, duration) in enumerate(zip(all_deltas, durations)):
		current_frame, current_position = process_segment(
			stitched_image,
			width,
			height,
			current_position,
			deltas,
			duration,
			output_dir,
			current_frame,
			fps,
		)
	return current_frame


def generate_scrolling_animation(
	img_dir, delta_dir, output_dir, static_intro_duration=6.0
):
	stitched_image, width = create_stitched_image(img_dir)
	all_deltas = collect_delta_data(delta_dir)
	durations = read_duration_data(output_dir)
	if len(all_deltas) != len(durations):
		return 0
	total_frames = build_animation_frames(
		stitched_image, width, all_deltas, durations, output_dir, static_intro_duration
	)
	return total_frames


if __name__ == "__main__":
	img_directory = "img"
	delta_directory = "delta"
	output_directory = "output"
	generate_scrolling_animation(
		img_directory, delta_directory, output_directory, static_intro_duration=5.0
	)
