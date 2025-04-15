from _0 import DIRS
from _12 import DELAY_DURATION, TARGET_HEIGHT, TARGET_FPS, TARGET_WIDTH
import bisect
import cv2
import functools
import json
import math
import numpy as np
import os
import subprocess


@functools.lru_cache(maxsize=2048)
def ease(time_ratio):
	eased_value = 0.0
	if time_ratio < 0.4:
		eased_value = 2.5 * time_ratio * time_ratio
	elif time_ratio < 0.8:
		eased_value = 0.4 + (time_ratio - 0.4) * 1.2
	else:
		normalized_time = (time_ratio - 0.8) / 0.2
		eased_value = 0.88 + (1.0 - math.pow(1.0 - normalized_time, 2)) * 0.12
	return eased_value


def render_scroll_video(height, output_path, target_fps, width):
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
		str(target_fps),
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
		output_path,
	]
	return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def frames_list(input_dir):
	images = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(".jpg")])
	frames = []
	total_height = 0
	for filename in images:
		path = os.path.join(input_dir, filename)
		if os.path.exists(path):
			image = cv2.imread(path)
			height = image.shape[0]
			frame = {
				"path": path,
				"height": height,
				"vertical_start_position": total_height,
			}
			frames.append(frame)
			total_height += height
	return frames, total_height


@functools.lru_cache(maxsize=6)
def cached_image(path):
	image = cv2.imread(path)
	image_copy = image.copy()
	return image_copy


def compose_scroll_frame(
	vertical_start_position,
	width,
	height,
	frames,
	vertical_start_position_list,
	total_height,
):
	if total_height < height:
		safe_vertical_start_position = int(
			round(min(max(0, vertical_start_position), total_height - height))
		)
	else:
		safe_vertical_start_position = 0
	safe_vertical_end_position = safe_vertical_start_position + height
	scroll_frame = np.zeros((height, width, 3), dtype=np.uint8)
	start_index = (
		bisect.bisect_right(vertical_start_position_list, safe_vertical_start_position)
		- 1
	)
	safe_start_index = max(0, start_index)
	for i in range(safe_start_index, len(frames)):
		frame = frames[i]
		frame_vertical_start_position = frame["vertical_start_position"]
		if frame_vertical_start_position >= safe_vertical_end_position:
			break
		frame_path = frame["path"]
		frame_height = frame["height"]
		frame_vertical_end_position = frame_vertical_start_position + frame_height
		if max(safe_vertical_start_position, frame_vertical_start_position) < min(
			safe_vertical_end_position, frame_vertical_end_position
		):
			crop_vertical_start = max(
				0, safe_vertical_start_position - frame_vertical_start_position
			)
			crop_vertical_end = min(
				frame_height, safe_vertical_end_position - frame_vertical_start_position
			)
			scroll_frame_vertical_start_position = max(
				0, frame_vertical_start_position - safe_vertical_start_position
			)
			if crop_vertical_end > crop_vertical_start:
				image = cached_image(frame_path)
				cropped_image = image[crop_vertical_start:crop_vertical_end, 0:width]
				cropped_height = cropped_image.shape[0]
				paste_y_start = scroll_frame_vertical_start_position
				paste_y_end = scroll_frame_vertical_start_position + cropped_height
				if paste_y_end > height:
					cropped_image = cropped_image[: height - paste_y_start, :]
				scroll_frame[
					paste_y_start : paste_y_start + cropped_image.shape[0], 0:width
				] = cropped_image
	return scroll_frame


def process_scroll_segment(
	frames,
	vertical_start_position_list,
	total_height,
	width,
	height,
	start_vertical_position,
	vertical_gap_list,
	duration,
	scroll_video_render_pipe,
	frames_per_second,
):
	scroll_frames = round(duration * frames_per_second)
	if scroll_frames <= 0 or duration <= 0:
		return start_vertical_position
	current_vertical_position = start_vertical_position
	if not (vertical_gap_list and sum(abs(gap) for gap in vertical_gap_list) >= 1e-6):
		scroll_frame = compose_scroll_frame(
			int(round(start_vertical_position)),
			width,
			height,
			frames,
			vertical_start_position_list,
			total_height,
		)
		if scroll_frame:
			for _ in range(scroll_frames):
				scroll_video_render_pipe.stdin.write(scroll_frame.tobytes())
			return start_vertical_position
		else:
			return start_vertical_position
	else:
		vertical_position_stops = [start_vertical_position]
		for gap in vertical_gap_list:
			vertical_position_stops.append(vertical_position_stops[-1] + gap)
		total_absolute_vertical_gap = sum(abs(gap) for gap in vertical_gap_list)
		if total_absolute_vertical_gap < 1e-6:
			total_absolute_vertical_gap = 1.0
		time_points_seconds = [0.0]
		cumulative_time = 0.0
		for gap in vertical_gap_list:
			time_ratio = abs(gap) / total_absolute_vertical_gap
			cumulative_time += time_ratio * duration
			time_points_seconds.append(cumulative_time)
		if len(time_points_seconds) > 1:
			time_points_seconds[-1] = duration
		for frame_num in range(scroll_frames):
			current_time_in_seconds = (frame_num / scroll_frames) * duration
			sub_index = 0
			while (
				sub_index < len(time_points_seconds) - 1
				and current_time_in_seconds >= time_points_seconds[sub_index + 1]
			):
				sub_index += 1
			sub_index = min(sub_index, len(vertical_gap_list) - 1)
			sub_start_time = time_points_seconds[sub_index]
			sub_end_time = time_points_seconds[sub_index + 1]
			sub_duration = sub_end_time - sub_start_time
			progress_ratio = 0.0
			if sub_duration > 1e-6:
				progress_ratio = (
					current_time_in_seconds - sub_start_time
				) / sub_duration
				progress_ratio = max(0.0, min(1.0, progress_ratio))
			else:
				progress_ratio = 1.0
			eased_progress_ratio = ease(progress_ratio)
			sub_start_y = vertical_position_stops[sub_index]
			sub_end_y = vertical_position_stops[sub_index + 1]
			vertical_gap_for_sub_segment = sub_end_y - sub_start_y
			current_vertical_position = (
				sub_start_y + eased_progress_ratio * vertical_gap_for_sub_segment
			)
			generated_frame = compose_scroll_frame(
				int(round(current_vertical_position)),
				width,
				height,
				frames,
				vertical_start_position_list,
				total_height,
			)
			if generated_frame:
				frame_pixel_data = generated_frame.tobytes()
				scroll_video_render_pipe.stdin.write(frame_pixel_data)
		if vertical_position_stops:
			return vertical_position_stops[-1]
		else:
			return start_vertical_position


if __name__ == "__main__":
	source_image_directory = DIRS["image_resized_fit"]
	output_directory = DIRS["render"]
	output_video_filename = "scroll_video.mkv"
	intro_hold_duration_seconds = DELAY_DURATION
	output_video_height_pixels = TARGET_HEIGHT
	frames_per_second = TARGET_FPS
	output_video_path = os.path.join(output_directory, output_video_filename)
	image_specs, total_height = frames_list(source_image_directory)
	source_width = TARGET_WIDTH
	v_start_list = [meta["vertical_start_position"] for meta in image_specs]
	vertical_change_data_path = os.path.join(DIRS["merge"], "gaps.json")
	segment_duration_data_path = os.path.join(DIRS["merge"], "durations.json")
	vertical_change_data = {}
	segment_duration_data = {}
	with open(vertical_change_data_path) as delta_file:
		vertical_change_data = json.load(delta_file)
	with open(segment_duration_data_path) as duration_file:
		segment_duration_data = json.load(duration_file)
	segment_identifiers = sorted(vertical_change_data.keys())
	duration_keys = set(segment_duration_data.keys())
	change_keys = set(segment_identifiers)
	if change_keys != duration_keys:
		common_keys = change_keys.intersection(duration_keys)
		segment_identifiers = sorted(list(common_keys))
	cached_image.cache_clear()
	encoder_process = render_scroll_video(
		output_video_height_pixels, output_video_path, frames_per_second, source_width
	)
	total_frames_generated_count = 0
	current_vertical_scroll_position = 0.0
	number_of_intro_frames = round(intro_hold_duration_seconds * frames_per_second)
	if number_of_intro_frames > 0:
		intro_frame = compose_scroll_frame(
			0,
			source_width,
			output_video_height_pixels,
			image_specs,
			v_start_list,
			total_height,
		)
		if intro_frame:
			intro_frame_bytes = intro_frame.tobytes()
			for _ in range(number_of_intro_frames):
				encoder_process.stdin.write(intro_frame_bytes)
			total_frames_generated_count += number_of_intro_frames
	for segment_key in segment_identifiers:
		delta_value = vertical_change_data[segment_key]
		segment_vertical_changes = []
		if isinstance(delta_value, list):
			segment_vertical_changes = [float(d) for d in delta_value]
		else:
			segment_vertical_changes = [float(delta_value)]
		segment_duration = float(segment_duration_data[segment_key])
		if segment_duration <= 0:
			continue
		total_frames_generated_count, current_vertical_scroll_position = (
			process_scroll_segment(
				image_specs,
				v_start_list,
				total_height,
				source_width,
				output_video_height_pixels,
				current_vertical_scroll_position,
				segment_vertical_changes,
				segment_duration,
				encoder_process,
				total_frames_generated_count,
				frames_per_second,
			)
		)
	if encoder_process.stdin:
		encoder_process.stdin.close()
	encoder_exit_code = encoder_process.wait()
