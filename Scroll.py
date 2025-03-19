import os
import json
from PIL import Image


def stitch_images(img_dir):
	image_files = sorted([f for f in os.listdir(img_dir) if f.lower().endswith(".jpg")])
	first_image = Image.open(os.path.join(img_dir, image_files[0]))
	width, height = first_image.size
	total_height = height * len(image_files)
	stitched_image = Image.new("RGB", (width, total_height))
	for i, img_file in enumerate(image_files):
		img = Image.open(os.path.join(img_dir, img_file))
		stitched_image.paste(img, (0, i * height))
	return stitched_image, width


def load_and_combine_deltas(delta_dir):
	delta_files = sorted(
		[f for f in os.listdir(delta_dir) if f.lower().endswith(".json")]
	)
	all_deltas = []
	for delta_file in delta_files:
		with open(os.path.join(delta_dir, delta_file), "r") as f:
			deltas = json.load(f)
			all_deltas.extend(deltas)
	return all_deltas


def merge_small_deltas(deltas, threshold=42):
	merged_deltas = []
	i = 0
	while i < len(deltas):
		current_delta = deltas[i]
		if current_delta < threshold and i < len(deltas) - 1:
			merged_deltas.append(current_delta + deltas[i + 1])
			i += 2
		else:
			merged_deltas.append(current_delta)
			i += 1
	return merged_deltas


def ease_in_out(t):
	if t < 0.5:
		return 4 * t * t * t
	else:
		return 1 - pow(-2 * t + 2, 3) / 2


def generate_frames(stitched_image, width, deltas, total_duration, output_dir):
	os.makedirs(output_dir, exist_ok=True)
	fps = 30
	total_frames = int(total_duration * fps)
	height = 1350
	positions = [0]
	for delta in deltas:
		positions.append(positions[-1] + delta)
	total_distance = sum(deltas)
	time_proportions = [delta / total_distance for delta in deltas]
	time_points = [0]
	for proportion in time_proportions:
		time_points.append(time_points[-1] + proportion * total_duration)
	for frame in range(total_frames):
		current_time = frame / fps
		segment = 0
		while (
			segment < len(time_points) - 1 and current_time > time_points[segment + 1]
		):
			segment += 1
		if segment >= len(deltas):
			y_position = positions[-1]
		else:
			segment_duration = time_points[segment + 1] - time_points[segment]
			if segment_duration == 0:
				progress = 1.0
			else:
				progress = (current_time - time_points[segment]) / segment_duration
			eased_progress = ease_in_out(progress)
			y_position = positions[segment] + eased_progress * (
				positions[segment + 1] - positions[segment]
			)
		y_position = max(0, min(y_position, stitched_image.height - height))
		viewport = stitched_image.crop(
			(0, int(y_position), width, int(y_position + height))
		)
		frame_filename = os.path.join(output_dir, f"frame_{frame:04d}.jpg")
		viewport.save(frame_filename, quality=100)
	return total_frames


def create_scrolling_animation(img_dir, delta_dir, output_dir, total_duration):
	stitched_image, width = stitch_images(img_dir)
	deltas = load_and_combine_deltas(delta_dir)
	merged_deltas = merge_small_deltas(deltas)
	generate_frames(stitched_image, width, merged_deltas, total_duration, output_dir)


img_directory = "img"
delta_directory = "delta"
output_directory = "output"
duration_seconds = 421
create_scrolling_animation(
	img_directory, delta_directory, output_directory, duration_seconds
)
