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
		normalized_time = max(0.0, normalized_time)
		eased_value = 0.88 + (1.0 - math.pow(1.0 - normalized_time, 2)) * 0.12
	return max(0.0, min(1.0, eased_value))


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
		"bgr24",
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
	frames_metadata = []
	total_height = 0
	for filename in images:
		path = os.path.join(input_dir, filename)
		if os.path.exists(path):
			image = cv2.imread(path)
			height = image.shape[0]
			frame_info = {
				"path": path,
				"height": height,
				"vertical_start_position": total_height,
			}
			frames_metadata.append(frame_info)
			total_height += height
	return frames_metadata, total_height


@functools.lru_cache(maxsize=6)
def cached_image(path):
	image = cv2.imread(path)
	return image.copy()


def compose_scroll_frame(
	vertical_start_position,
	width,
	height,
	frames_metadata,
	vertical_start_position_list,
	total_content_height,
):
	max_scroll_pos = max(0, total_content_height - height)
	safe_vertical_start_position = (
		int(round(min(max(0, vertical_start_position), max_scroll_pos)))
		if total_content_height > height
		else 0
	)
	safe_vertical_end_position = safe_vertical_start_position + height
	output_frame = np.zeros((height, width, 3), dtype=np.uint8)
	start_index = (
		bisect.bisect_right(vertical_start_position_list, safe_vertical_start_position)
		- 1
	)
	start_index = max(0, start_index)
	for i in range(start_index, len(frames_metadata)):
		frame_meta = frames_metadata[i]
		frame_v_start = frame_meta["vertical_start_position"]
		frame_v_end = frame_v_start + frame_meta["height"]
		if frame_v_start >= safe_vertical_end_position:
			break
		if max(safe_vertical_start_position, frame_v_start) < min(
			safe_vertical_end_position, frame_v_end
		):
			crop_start_y = max(0, safe_vertical_start_position - frame_v_start)
			crop_end_y = min(
				frame_meta["height"], safe_vertical_end_position - frame_v_start
			)
			paste_start_y = max(0, frame_v_start - safe_vertical_start_position)
			if crop_end_y > crop_start_y:
				image = cached_image(frame_meta["path"])
				image_h, image_w, _ = image.shape
				if image_w != width:
					image = (
						image[:, :width]
						if image_w > width
						else cv2.copyMakeBorder(
							image,
							0,
							0,
							0,
							width - image_w,
							cv2.BORDER_CONSTANT,
							value=[0, 0, 0],
						)
					)
				cropped_image_part = image[crop_start_y:crop_end_y, 0:width]
				cropped_height = cropped_image_part.shape[0]
				paste_end_y = paste_start_y + cropped_height
				if paste_end_y > height:
					overhang = paste_end_y - height
					cropped_image_part = cropped_image_part[:-overhang, :]
					paste_end_y = height
				if cropped_image_part.shape[0] > 0 and cropped_image_part.shape[1] > 0:
					output_frame[paste_start_y:paste_end_y, 0:width] = (
						cropped_image_part
					)
	return output_frame


def process_scroll_segment(
	frames_metadata,
	vertical_start_position_list,
	total_content_height,
	width,
	height,
	start_vertical_position,
	vertical_gap_list,
	duration,
	scroll_video_render_pipe,
	frames_per_second,
):
	num_frames_in_segment = round(duration * frames_per_second)
	if num_frames_in_segment <= 0:
		return start_vertical_position
	is_hold_segment = (
		not vertical_gap_list or sum(abs(gap) for gap in vertical_gap_list) < 1e-6
	)
	final_vertical_position = start_vertical_position
	if is_hold_segment:
		hold_frame = compose_scroll_frame(
			int(round(start_vertical_position)),
			width,
			height,
			frames_metadata,
			vertical_start_position_list,
			total_content_height,
		)
		hold_frame_bytes = hold_frame.tobytes()
		for _ in range(num_frames_in_segment):
			scroll_video_render_pipe.stdin.write(hold_frame_bytes)
		final_vertical_position = start_vertical_position
	else:
		vertical_stops = [start_vertical_position]
		for gap in vertical_gap_list:
			vertical_stops.append(vertical_stops[-1] + gap)
		final_vertical_position = vertical_stops[-1]
		total_absolute_gap = sum(abs(gap) for gap in vertical_gap_list)
		total_absolute_gap = max(total_absolute_gap, 1e-9)
		time_stops = [0.0]
		cumulative_time = 0.0
		for gap in vertical_gap_list:
			time_ratio = abs(gap) / total_absolute_gap
			cumulative_time += time_ratio * duration
			time_stops.append(cumulative_time)
		time_stops[-1] = duration
		current_calculated_pos = start_vertical_position
		for frame_idx in range(num_frames_in_segment):
			current_time = (frame_idx / num_frames_in_segment) * duration
			sub_segment_idx = bisect.bisect_right(time_stops, current_time) - 1
			sub_segment_idx = max(0, min(sub_segment_idx, len(vertical_gap_list) - 1))
			sub_start_time = time_stops[sub_segment_idx]
			sub_end_time = time_stops[sub_segment_idx + 1]
			sub_duration = sub_end_time - sub_start_time
			time_progress = 0.0
			if sub_duration > 1e-9:
				time_progress = (current_time - sub_start_time) / sub_duration
				time_progress = max(0.0, min(1.0, time_progress))
			else:
				time_progress = (
					0.0 if abs(current_time - sub_start_time) < 1e-9 else 1.0
				)
			eased_progress = ease(time_progress)
			sub_start_y = vertical_stops[sub_segment_idx]
			sub_end_y = vertical_stops[sub_segment_idx + 1]
			vertical_gap_sub_segment = sub_end_y - sub_start_y
			current_calculated_pos = (
				sub_start_y + eased_progress * vertical_gap_sub_segment
			)
			output_frame = compose_scroll_frame(
				int(round(current_calculated_pos)),
				width,
				height,
				frames_metadata,
				vertical_start_position_list,
				total_content_height,
			)
			frame_bytes = output_frame.tobytes()
			scroll_video_render_pipe.stdin.write(frame_bytes)
	return final_vertical_position


if __name__ == "__main__":
	source_image_directory = DIRS["image_resized_fit"]
	output_directory = DIRS["render"]
	output_video_filename = "scroll_video.mkv"
	intro_hold_duration_seconds = DELAY_DURATION
	output_video_height_pixels = TARGET_HEIGHT
	frames_per_second = TARGET_FPS
	output_video_width_pixels = TARGET_WIDTH
	output_video_path = os.path.join(output_directory, output_video_filename)
	vertical_change_data_path = os.path.join(DIRS["merge"], "transition_gaps.json")
	segment_duration_data_path = os.path.join(DIRS["merge"], "durations.json")
	image_metadata, total_content_height = frames_list(source_image_directory)
	vertical_start_positions = [
		meta["vertical_start_position"] for meta in image_metadata
	]
	with open(vertical_change_data_path, "r") as f:
		vertical_change_data = json.load(f)
	with open(segment_duration_data_path, "r") as f:
		segment_duration_data = json.load(f)
	gap_keys = set(vertical_change_data.keys())
	duration_keys = set(segment_duration_data.keys())
	valid_segment_keys = sorted(list(gap_keys.intersection(duration_keys)))
	cached_image.cache_clear()
	encoder_process = render_scroll_video(
		output_video_height_pixels,
		output_video_path,
		frames_per_second,
		output_video_width_pixels,
	)
	total_frames_written_count = 0
	current_vertical_scroll_position = 0.0
	num_intro_frames = round(intro_hold_duration_seconds * frames_per_second)
	if num_intro_frames > 0:
		_ = process_scroll_segment(
			image_metadata,
			vertical_start_positions,
			total_content_height,
			output_video_width_pixels,
			output_video_height_pixels,
			start_vertical_position=current_vertical_scroll_position,
			vertical_gap_list=[],
			duration=intro_hold_duration_seconds,
			scroll_video_render_pipe=encoder_process,
			frames_per_second=frames_per_second,
		)
		total_frames_written_count += num_intro_frames
	for i, segment_key in enumerate(valid_segment_keys):
		delta_value = vertical_change_data[segment_key]
		segment_duration = float(segment_duration_data[segment_key])
		if isinstance(delta_value, (int, float)):
			segment_vertical_changes = [float(delta_value)]
		elif isinstance(delta_value, list):
			segment_vertical_changes = [
				float(d) for d in delta_value if isinstance(d, (int, float))
			]
		else:
			continue
		if segment_duration <= 0:
			continue
		num_segment_frames = round(segment_duration * frames_per_second)
		if num_segment_frames <= 0:
			current_vertical_scroll_position += sum(segment_vertical_changes)
			continue
		end_position = process_scroll_segment(
			image_metadata,
			vertical_start_positions,
			total_content_height,
			output_video_width_pixels,
			output_video_height_pixels,
			current_vertical_scroll_position,
			segment_vertical_changes,
			segment_duration,
			encoder_process,
			frames_per_second,
		)
		current_vertical_scroll_position = end_position
		total_frames_written_count += num_segment_frames
	if encoder_process.stdin:
		encoder_process.stdin.close()
	encoder_exit_code = encoder_process.wait()
