import bisect
import functools
import json
import math
import os
import PIL.Image
import subprocess


@functools.lru_cache(maxsize=2048)
def calculate_eased_progress(time_ratio):
	eased_value = 0.0
	if time_ratio < 0.4:
		eased_value = 2.5 * time_ratio * time_ratio
	elif time_ratio < 0.8:
		eased_value = 0.4 + (time_ratio - 0.4) * 1.2
	else:
		normalized_time = (time_ratio - 0.8) / 0.2
		eased_value = 0.88 + (1.0 - math.pow(1.0 - normalized_time, 2)) * 0.12
	return eased_value


def start_video_encoder_process(
	output_file_path, image_width, image_height, frames_per_second
):
	command_arguments = [
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
		f"{image_width}x{image_height}",
		"-pix_fmt",
		"rgb24",
		"-r",
		str(frames_per_second),
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
		output_file_path,
	]
	process_handle = subprocess.Popen(command_arguments, stdin=subprocess.PIPE)
	return process_handle


def get_image_specifications(image_directory_path):
	all_files = os.listdir(image_directory_path)
	image_file_names = []
	for f_name in all_files:
		is_image = f_name.lower().endswith((".jpg"))
		if is_image:
			image_file_names.append(f_name)
	image_file_names.sort()
	if not image_file_names:
		return [], 0, 0
	image_spec_list = []
	total_source_image_height = 0
	first_image_width = 0
	first_image_path = os.path.join(image_directory_path, image_file_names[0])
	if os.path.exists(first_image_path):
		first_image_object = PIL.Image.open(first_image_path)
		first_image_width = first_image_object.width
		first_image_object.close()
	else:
		return [], 0, 0
	if first_image_width == 0:
		return [], 0, 0
	for image_file_name in image_file_names:
		file_path = os.path.join(image_directory_path, image_file_name)
		if os.path.exists(file_path):
			img_object = PIL.Image.open(file_path)
			current_width = img_object.width
			current_height = img_object.height
			img_object.close()
			image_data = {
				"file_path": file_path,
				"image_height": current_height,
				"vertical_start_position": total_source_image_height,
			}
			image_spec_list.append(image_data)
			total_source_image_height += current_height
	return image_spec_list, first_image_width, total_source_image_height


@functools.lru_cache(maxsize=6)
def get_cached_image_object(file_path):
	if not os.path.exists(file_path):
		return None
	img_object = PIL.Image.open(file_path)
	img_copy = img_object.copy()
	img_object.close()
	return img_copy


def compose_video_frame(
	target_vertical_position,
	output_frame_width,
	output_frame_height,
	image_specifications,
	vertical_start_position_list,
	total_source_vertical_pixels,
):
	safe_target_y = max(0, target_vertical_position)
	safe_target_y = min(
		safe_target_y, total_source_vertical_pixels - output_frame_height
	)
	if total_source_vertical_pixels < output_frame_height:
		safe_target_y = 0
	integer_target_y = int(round(safe_target_y))
	new_frame_object = PIL.Image.new("RGB", (output_frame_width, output_frame_height))
	view_area_top_pixel = integer_target_y
	view_area_bottom_pixel = integer_target_y + output_frame_height
	potential_start_index = bisect.bisect_right(
		vertical_start_position_list, view_area_top_pixel
	)
	start_check_index = max(0, potential_start_index - 1)
	for i in range(start_check_index, len(image_specifications)):
		img_data = image_specifications[i]
		img_vertical_start = img_data["vertical_start_position"]
		if img_vertical_start >= view_area_bottom_pixel:
			break
		img_path = img_data["file_path"]
		img_h = img_data["image_height"]
		img_vertical_end = img_vertical_start + img_h
		overlap_exists = max(view_area_top_pixel, img_vertical_start) < min(
			view_area_bottom_pixel, img_vertical_end
		)
		if overlap_exists:
			crop_y_start_in_img = max(0, view_area_top_pixel - img_vertical_start)
			crop_y_end_in_img = min(img_h, view_area_bottom_pixel - img_vertical_start)
			paste_y_in_frame = max(0, img_vertical_start - view_area_top_pixel)
			if crop_y_end_in_img > crop_y_start_in_img:
				source_img_object = get_cached_image_object(img_path)
				if source_img_object is None:
					continue
				crop_box = (
					0,
					crop_y_start_in_img,
					output_frame_width,
					crop_y_end_in_img,
				)
				cropped_part = source_img_object.crop(crop_box)
				paste_coordinates = (0, paste_y_in_frame)
				new_frame_object.paste(cropped_part, paste_coordinates)
				cropped_part.close()
	return new_frame_object


def process_scroll_segment(
	image_specifications,
	vertical_start_position_list,
	total_source_vertical_pixels,
	output_frame_width,
	output_frame_height,
	segment_start_vertical_position,
	vertical_change_list,
	segment_duration_seconds,
	encoder_process_handle,
	current_frame_index,
	frames_per_second,
):
	number_of_frames_in_segment = round(segment_duration_seconds * frames_per_second)
	if number_of_frames_in_segment <= 0 or segment_duration_seconds <= 0:
		return current_frame_index, segment_start_vertical_position
	current_vertical_position = segment_start_vertical_position
	final_vertical_position = segment_start_vertical_position
	is_static_segment = True
	if vertical_change_list:
		total_movement = sum(abs(change) for change in vertical_change_list)
		if total_movement >= 1e-6:
			is_static_segment = False
	if is_static_segment:
		target_y = int(round(segment_start_vertical_position))
		unchanging_frame_object = compose_video_frame(
			target_y,
			output_frame_width,
			output_frame_height,
			image_specifications,
			vertical_start_position_list,
			total_source_vertical_pixels,
		)
		if unchanging_frame_object:
			frame_pixel_data = unchanging_frame_object.tobytes()
			unchanging_frame_object.close()
			for _ in range(number_of_frames_in_segment):
				encoder_process_handle.stdin.write(frame_pixel_data)
			final_vertical_position = segment_start_vertical_position
			new_frame_index = current_frame_index + number_of_frames_in_segment
			return new_frame_index, final_vertical_position
		else:
			return current_frame_index, segment_start_vertical_position
	else:
		vertical_position_stops = [segment_start_vertical_position]
		for change in vertical_change_list:
			vertical_position_stops.append(vertical_position_stops[-1] + change)
		total_absolute_vertical_change = sum(
			abs(change) for change in vertical_change_list
		)
		if total_absolute_vertical_change < 1e-6:
			total_absolute_vertical_change = 1.0
		time_points_seconds = [0.0]
		cumulative_time = 0.0
		for change in vertical_change_list:
			time_ratio = abs(change) / total_absolute_vertical_change
			cumulative_time += time_ratio * segment_duration_seconds
			time_points_seconds.append(cumulative_time)
		if len(time_points_seconds) > 1:
			time_points_seconds[-1] = segment_duration_seconds
		for frame_num in range(number_of_frames_in_segment):
			current_time_in_segment_seconds = (
				frame_num / number_of_frames_in_segment
			) * segment_duration_seconds
			sub_segment_index = 0
			while (
				sub_segment_index < len(time_points_seconds) - 1
				and current_time_in_segment_seconds
				>= time_points_seconds[sub_segment_index + 1]
			):
				sub_segment_index += 1
			sub_segment_index = min(sub_segment_index, len(vertical_change_list) - 1)
			sub_segment_start_time = time_points_seconds[sub_segment_index]
			sub_segment_end_time = time_points_seconds[sub_segment_index + 1]
			sub_segment_duration = sub_segment_end_time - sub_segment_start_time
			segment_progress_ratio = 0.0
			if sub_segment_duration > 1e-6:
				segment_progress_ratio = (
					current_time_in_segment_seconds - sub_segment_start_time
				) / sub_segment_duration
				segment_progress_ratio = max(0.0, min(1.0, segment_progress_ratio))
			else:
				segment_progress_ratio = 1.0
			eased_segment_progress_ratio = calculate_eased_progress(
				segment_progress_ratio
			)
			sub_segment_start_y = vertical_position_stops[sub_segment_index]
			sub_segment_end_y = vertical_position_stops[sub_segment_index + 1]
			vertical_change_for_sub_segment = sub_segment_end_y - sub_segment_start_y
			current_vertical_position = (
				sub_segment_start_y
				+ eased_segment_progress_ratio * vertical_change_for_sub_segment
			)
			target_y = int(round(current_vertical_position))
			generated_frame_object = compose_video_frame(
				target_y,
				output_frame_width,
				output_frame_height,
				image_specifications,
				vertical_start_position_list,
				total_source_vertical_pixels,
			)
			if generated_frame_object:
				frame_pixel_data = generated_frame_object.tobytes()
				encoder_process_handle.stdin.write(frame_pixel_data)
				generated_frame_object.close()
		if vertical_position_stops:
			final_vertical_position = vertical_position_stops[-1]
		else:
			final_vertical_position = segment_start_vertical_position
		new_frame_index = current_frame_index + number_of_frames_in_segment
		return new_frame_index, final_vertical_position


def generate_scrolling_video(
	source_image_directory,
	output_directory,
	output_video_filename,
	intro_hold_duration_seconds=0.0,
	output_video_height_pixels=1000,
	frames_per_second=60,
):
	os.makedirs(output_directory, exist_ok=True)
	output_video_path = os.path.join(output_directory, output_video_filename)
	image_specs, source_width, total_source_height = get_image_specifications(
		source_image_directory
	)
	if not image_specs or source_width <= 0:
		return 0
	v_start_list = [meta["vertical_start_position"] for meta in image_specs]
	vertical_change_data_path = os.path.join(output_directory, "gaps.json")
	segment_duration_data_path = os.path.join(output_directory, "durations.json")
	if not os.path.exists(vertical_change_data_path) or not os.path.exists(
		segment_duration_data_path
	):
		return 0
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
	if not segment_identifiers:
		return 0
	get_cached_image_object.cache_clear()
	encoder_process = start_video_encoder_process(
		output_video_path, source_width, output_video_height_pixels, frames_per_second
	)
	if not encoder_process or not encoder_process.stdin:
		return 0
	total_frames_generated_count = 0
	current_vertical_scroll_position = 0.0
	number_of_intro_frames = round(intro_hold_duration_seconds * frames_per_second)
	if number_of_intro_frames > 0:
		intro_frame_object = compose_video_frame(
			0,
			source_width,
			output_video_height_pixels,
			image_specs,
			v_start_list,
			total_source_height,
		)
		if intro_frame_object:
			intro_frame_bytes = intro_frame_object.tobytes()
			intro_frame_object.close()
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
				total_source_height,
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
	return total_frames_generated_count


if __name__ == "__main__":
	IMAGE_DIRECTORY = "image_resized_fit"
	OUTPUT_DIRECTORY = "render"
	OUTPUT_FILENAME = "scroll_video.mkv"
	OUTPUT_FRAME_HEIGHT = 1292
	VIDEO_FPS = 60
	INTRO_HOLD_TIME = 1
	delta_json_path = os.path.join(OUTPUT_DIRECTORY, "gaps.json")
	duration_json_path = os.path.join(OUTPUT_DIRECTORY, "durations.json")
	generated_frame_count = generate_scrolling_video(
		source_image_directory=IMAGE_DIRECTORY,
		output_directory=OUTPUT_DIRECTORY,
		output_video_filename=OUTPUT_FILENAME,
		intro_hold_duration_seconds=INTRO_HOLD_TIME,
		output_video_height_pixels=OUTPUT_FRAME_HEIGHT,
		frames_per_second=VIDEO_FPS,
	)
