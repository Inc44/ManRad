from scipy.io.wavfile import write
import concurrent.futures
import cv2
import librosa
import numpy as np
import os
import shutil
import subprocess
import sys
import tempfile


def create_folder(folder_path):
	if not os.path.exists(folder_path):
		os.makedirs(folder_path)


def execute_ffmpeg_task(parameters, show_console_output=False):
	base_command = ["ffmpeg", "-y"]
	if not show_console_output:
		base_command.extend(["-hide_banner", "-loglevel", "error"])
	base_command.extend(parameters)
	subprocess.run(base_command, check=True)


def generate_silent_audio(output_file, time_length, frequency=24000):
	total_samples = int(time_length * frequency)
	empty_audio = np.zeros(total_samples, dtype=np.int16)
	write(output_file, frequency, empty_audio)


def find_audio_duration(file_path):
	if os.path.exists(file_path):
		return librosa.get_duration(path=file_path)
	return 0


def adjust_image_size(source_file, target_file, target_width, target_height):
	image_data = cv2.imread(source_file)
	if image_data is None:
		return False
	original_height, original_width = image_data.shape[:2]
	aspect_ratio_target = target_width / target_height
	aspect_ratio_current = original_width / original_height
	if aspect_ratio_current > aspect_ratio_target:
		adjusted_width = target_width
		adjusted_height = int(target_width / aspect_ratio_current)
	else:
		adjusted_height = target_height
		adjusted_width = int(target_height * aspect_ratio_current)
	if adjusted_width <= 0 or adjusted_height <= 0:
		return False
	if adjusted_width > target_width or target_height > target_height:
		return False
	resized_image_data = cv2.resize(
		image_data, (adjusted_width, adjusted_height), interpolation=cv2.INTER_AREA
	)
	width_diff = target_width - adjusted_width
	height_diff = target_height - adjusted_height
	top_pad, bottom_pad = height_diff // 2, height_diff - (height_diff // 2)
	left_pad, right_pad = width_diff // 2, width_diff - (width_diff // 2)
	top_pad = max(0, top_pad)
	bottom_pad = max(0, bottom_pad)
	left_pad = max(0, left_pad)
	right_pad = max(0, right_pad)
	final_image = cv2.copyMakeBorder(
		resized_image_data,
		top_pad,
		bottom_pad,
		left_pad,
		right_pad,
		cv2.BORDER_CONSTANT,
		value=(0, 0, 0),
	)
	if final_image.shape[0] != target_height or final_image.shape[1] != target_width:
		return False
	cv2.imwrite(target_file, final_image, [cv2.IMWRITE_JPEG_QUALITY, 100])
	return True


def combine_images_vertically(
	image_list, output_folder, sequence_number, frame_width, frame_height
):
	output_file = os.path.join(output_folder, f"stacked_{sequence_number}.jpg")
	loaded_images = []
	for image in image_list:
		img = cv2.imread(image)
		if img is None:
			return None
		loaded_images.append(img)
	if not loaded_images:
		return None
	combined = cv2.vconcat(loaded_images)
	cv2.imwrite(output_file, combined, [cv2.IMWRITE_JPEG_QUALITY, 100])
	return output_file


def generate_fade_frames(
	image_path1,
	image_path2,
	output_folder,
	num_frames,
	base_index,
	frame_width,
	frame_height,
):
	img1 = cv2.imread(image_path1)
	img2 = cv2.imread(image_path2)
	if img1 is None or img2 is None:
		return base_index
	if img1.shape[0] != frame_height or img1.shape[1] != frame_width:
		img1 = cv2.resize(img1, (frame_width, frame_height))
	if img2.shape[0] != frame_height or img2.shape[1] != frame_width:
		img2 = cv2.resize(img2, (frame_width, frame_height))
	for i in range(num_frames):
		alpha = i / (num_frames - 1)
		blended_img = cv2.addWeighted(img1, 1 - alpha, img2, alpha, 0)
		frame_name = f"frame_{base_index + i:06d}.jpg"
		frame_path = os.path.join(output_folder, frame_name)
		cv2.imwrite(frame_path, blended_img, [cv2.IMWRITE_JPEG_QUALITY, 100])
	return base_index + num_frames


def preprocess_images_for_scroll(image_files, image_dir, output_width):
	processed_images = []
	for image_file in image_files:
		image_path = os.path.join(image_dir, image_file)
		image = cv2.imread(image_path)
		if image is None:
			continue
		img_height, img_width = image.shape[:2]
		scale_factor = output_width / img_width
		new_height = int(img_height * scale_factor)
		resized_image = cv2.resize(image, (output_width, new_height))
		processed_images.append(resized_image)
	return processed_images


def create_scroll_frames(
	processed_images, audio_durations, output_size, frames_per_second, output_dir
):
	output_width, output_height = output_size
	full_image = np.vstack(processed_images)
	full_height = full_image.shape[0]
	heights = [img.shape[0] for img in processed_images]
	positions = [0]
	for h in heights[:-1]:
		positions.append(positions[-1] + h)
	ease_in_percent = 0.15
	ease_out_percent = 0.15
	pause_percent = 0.2
	frame_files = {}
	video_sequence = []
	for segment_index in range(len(processed_images)):
		segment_duration = audio_durations[segment_index]
		start_pos = positions[segment_index]
		end_pos = (
			positions[segment_index + 1]
			if segment_index < len(positions) - 1
			else full_height - output_height
		)
		pause_duration = segment_duration * pause_percent
		y_start = max(0, start_pos)
		y_end = min(y_start + output_height, full_height)
		if y_end - y_start < output_height:
			y_start = max(0, y_end - output_height)
		frame_hash = f"{y_start}_{y_end}"
		if frame_hash not in frame_files:
			visible = full_image[y_start:y_end, 0:output_width]
			if visible.shape[0] < output_height:
				padding_height = output_height - visible.shape[0]
				visible = cv2.copyMakeBorder(
					visible,
					0,
					padding_height,
					0,
					0,
					cv2.BORDER_CONSTANT,
					value=[0, 0, 0],
				)
			frame_path = os.path.join(output_dir, f"frame_{len(frame_files):06d}.jpg")
			cv2.imwrite(frame_path, visible, [cv2.IMWRITE_JPEG_QUALITY, 100])
			frame_files[frame_hash] = frame_path
		video_sequence.append(
			(frame_files[frame_hash], pause_duration)
		)
		scroll_duration = segment_duration * (
			1 - pause_percent - ease_in_percent - ease_out_percent
		)
		if scroll_duration > 0 and segment_index < len(processed_images) - 1:
			scroll_frames = max(
				5, int(scroll_duration * frames_per_second)
			)
			frame_time = scroll_duration / scroll_frames
			for i in range(1, scroll_frames + 1):
				scroll_progress = i / scroll_frames
				if scroll_progress < 0.5:
					eased_progress = 2 * scroll_progress * scroll_progress
				else:
					eased_progress = (
						1 - (-2 * scroll_progress + 2) * (-2 * scroll_progress + 2) / 2
					)
				y_offset = int(start_pos + eased_progress * (end_pos - start_pos))
				y_start = max(0, y_offset)
				y_end = min(y_start + output_height, full_height)
				if y_end - y_start < output_height:
					y_start = max(0, y_end - output_height)
				frame_hash = f"{y_start}_{y_end}"
				if frame_hash not in frame_files:
					visible = full_image[y_start:y_end, 0:output_width]
					if visible.shape[0] < output_height:
						padding_height = output_height - visible.shape[0]
						visible = cv2.copyMakeBorder(
							visible,
							0,
							padding_height,
							0,
							0,
							cv2.BORDER_CONSTANT,
							value=[0, 0, 0],
						)
					frame_path = os.path.join(
						output_dir, f"frame_{len(frame_files):06d}.jpg"
					)
					cv2.imwrite(frame_path, visible, [cv2.IMWRITE_JPEG_QUALITY, 100])
					frame_files[frame_hash] = frame_path
				video_sequence.append((frame_files[frame_hash], frame_time))
		ease_out_duration = segment_duration * ease_out_percent
		if ease_out_duration > 0 and segment_index < len(processed_images) - 1:
			video_sequence[-1] = (
				video_sequence[-1][0],
				video_sequence[-1][1] + ease_out_duration,
			)
	return video_sequence


def create_video_sequence(
	input_location,
	output_location,
	fade_time=0.5,
	use_scroll=False,
	frame_width=900,
	frame_height=1350,
	frames_per_second=30,
):
	picture_folder = os.path.join(input_location, "img")
	sound_folder = os.path.join(input_location, "wav")
	if not os.path.exists(picture_folder):
		return
	create_folder(output_location)
	processed_image_folder = os.path.join(output_location, "images")
	create_folder(processed_image_folder)
	picture_files = sorted(
		[f for f in os.listdir(picture_folder) if f.lower().endswith(".jpg")]
	)
	if not picture_files:
		return
	image_status = {}
	with concurrent.futures.ThreadPoolExecutor() as executor:
		tasks = {
			executor.submit(
				adjust_image_size,
				os.path.join(picture_folder, f),
				os.path.join(processed_image_folder, f),
				frame_width,
				frame_height,
			): f
			for f in picture_files
		}
		for task in concurrent.futures.as_completed(tasks):
			image_status[tasks[task]] = task.result()
	if not all(image_status.values()):
		return
	sound_files = []
	sound_durations = []
	sound_frequency = 24000
	temp_sound_folder = os.path.join(output_location, "audio")
	create_folder(temp_sound_folder)
	create_folder(os.path.join(temp_sound_folder, "long"))
	create_folder(os.path.join(temp_sound_folder, "silence"))
	create_folder(os.path.join(temp_sound_folder, "concat"))
	for i, picture_file in enumerate(picture_files):
		base_name = os.path.splitext(picture_file)[0]
		sound_path = os.path.join(sound_folder, f"{base_name}.wav")
		if os.path.exists(sound_path):
			duration = find_audio_duration(sound_path)
			if i == 0 and duration > 0:
				_, sound_frequency = librosa.load(sound_path, sr=None)
			if duration < 1.0:
				extended_path = os.path.join(
					temp_sound_folder, "long", f"{base_name}_long.wav"
				)
				silence_path = os.path.join(
					temp_sound_folder, "silence", f"silence_{i}.wav"
				)
				generate_silent_audio(silence_path, 1.0 - duration, sound_frequency)
				list_file_path = os.path.join(
					temp_sound_folder, "concat", f"concat_{i}.txt"
				)
				with open(list_file_path, "w") as f:
					f.write(f"file '{os.path.abspath(sound_path)}'\n")
					f.write(f"file '{os.path.abspath(silence_path)}'\n")
				execute_ffmpeg_task(
					[
						"-f",
						"concat",
						"-safe",
						"0",
						"-i",
						list_file_path,
						"-c",
						"copy",
						extended_path,
					]
				)
				sound_files.append(extended_path)
				duration = 1.0
			else:
				sound_files.append(sound_path)
		else:
			silence_path = os.path.join(
				temp_sound_folder, "silence", f"silence_{i}.wav"
			)
			generate_silent_audio(silence_path, 1.0, sound_frequency)
			sound_files.append(silence_path)
			duration = 1.0
		sound_durations.append(duration)
	temp_frame_folder = os.path.join(output_location, "frames")
	create_folder(temp_frame_folder)
	next_frame_index = 0
	if use_scroll:
		processed_images = preprocess_images_for_scroll(
			picture_files, processed_image_folder, frame_width
		)
		video_sequence = create_scroll_frames(
			processed_images,
			sound_durations,
			(frame_width, frame_height),
			frames_per_second,
			temp_frame_folder,
		)
	else:
		for i, picture_file in enumerate(picture_files):
			if not image_status.get(picture_file):
				continue
			image_path = os.path.join(processed_image_folder, picture_file)
			duration = sound_durations[i]
			frame_duration = 1.0 / frames_per_second
			still_frame_name = f"frame_{next_frame_index:06d}.jpg"
			still_frame_path = os.path.join(temp_frame_folder, still_frame_name)
			shutil.copy2(image_path, still_frame_path)
			next_frame_index += 1
			remaining_duration = duration - frame_duration
			if remaining_duration > 0:
				still_frame_name_rem = f"frame_{next_frame_index:06d}.jpg"
				still_frame_path_rem = os.path.join(
					temp_frame_folder, still_frame_name_rem
				)
				shutil.copy2(image_path, still_frame_path_rem)
				next_frame_index += 1
			if i < len(picture_files) - 1:
				next_picture_file = picture_files[i + 1]
				if not image_status.get(next_picture_file):
					continue
				next_image_path = os.path.join(
					processed_image_folder, next_picture_file
				)
				num_fade_frames = int(round(fade_time * frames_per_second))
				fade_folder = os.path.join(temp_frame_folder, f"fade_{i}")
				create_folder(fade_folder)
				next_frame_index = generate_fade_frames(
					image_path,
					next_image_path,
					fade_folder,
					num_fade_frames,
					next_frame_index,
					frame_width,
					frame_height,
				)
	final_video_list = os.path.join(output_location, "concat.txt")
	frame_duration = 1.0 / frames_per_second
	with open(final_video_list, "w") as f:
		if use_scroll:
			for frame_path, duration in video_sequence:
				f.write(f"file '{frame_path}'\n")
				f.write(f"duration {duration:.6f}\n")
		else:
			frame_files = sorted(
				[
					f
					for f in os.listdir(temp_frame_folder)
					if f.startswith("frame_") and f.endswith(".jpg")
				]
			)
			frame_index = 0
			for i, picture_file in enumerate(picture_files):
				if not image_status.get(picture_file):
					continue
				frame_path = os.path.abspath(
					os.path.join(temp_frame_folder, f"frame_{frame_index:06d}.jpg")
				)
				f.write(f"file '{frame_path}'\n")
				f.write(f"duration {frame_duration}\n")
				frame_index += 1
				remaining_frame_path = os.path.abspath(
					os.path.join(temp_frame_folder, f"frame_{frame_index:06d}.jpg")
				)
				remaining_duration = sound_durations[i] - frame_duration
				if remaining_duration > 0:
					f.write(f"file '{remaining_frame_path}'\n")
					f.write(f"duration {remaining_duration}\n")
					frame_index += 1
				if i < len(picture_files) - 1:
					num_fade_frames = int(round(fade_time * frames_per_second))
					for j in range(num_fade_frames):
						fade_frame_path = os.path.abspath(
							os.path.join(
								temp_frame_folder,
								f"fade_{i}",
								f"frame_{frame_index:06d}.jpg",
							)
						)
						if os.path.exists(fade_frame_path):
							f.write(f"file '{fade_frame_path}'\n")
							f.write(f"duration {frame_duration}\n")
							frame_index += 1
	final_video_file = os.path.join(output_location, "video.mkv")
	execute_ffmpeg_task(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			final_video_list,
			"-fps_mode",
			"vfr",
			"-c:v",
			"libx264",
			"-preset",
			"medium",
			final_video_file,
		]
	)
	final_audio_list = os.path.join(output_location, "audio_concat.txt")
	with open(final_audio_list, "w") as f:
		for i, audio_path in enumerate(sound_files):
			f.write(f"file '{os.path.abspath(audio_path)}'\n")
			if (
				not use_scroll and i < len(sound_files) - 1
			):
				silence_duration = fade_time
				silence_path = os.path.join(
					temp_sound_folder, "silence", f"transition_silence_{i}.wav"
				)
				generate_silent_audio(silence_path, silence_duration, sound_frequency)
				f.write(f"file '{os.path.abspath(silence_path)}'\n")
	final_audio_file = os.path.join(output_location, "audio.opus")
	execute_ffmpeg_task(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			final_audio_list,
			"-c:a",
			"libopus",
			"-vbr",
			"on",
			"-compression_level",
			"10",
			"-frame_duration",
			"60",
			final_audio_file,
		]
	)
	complete_video_file = os.path.join(output_location, "Man.mkv")
	execute_ffmpeg_task(
		[
			"-i",
			final_video_file,
			"-i",
			final_audio_file,
			"-c",
			"copy",
			complete_video_file,
		]
	)
	final_output_location = os.path.join(input_location, "Man.mkv")
	shutil.copy2(complete_video_file, final_output_location)


if __name__ == "__main__":
	frame_width_default = 900
	frame_height_default = 1350
	frames_per_second_default = 30
	use_scroll_default = False
	if "--width" in sys.argv:
		width_position = sys.argv.index("--width") + 1
		if width_position < len(sys.argv):
			frame_width_default = int(sys.argv[width_position])
	if "--height" in sys.argv:
		height_position = sys.argv.index("--height") + 1
		if height_position < len(sys.argv):
			frame_height_default = int(sys.argv[height_position])
	if "--fps" in sys.argv:
		fps_position = sys.argv.index("--fps") + 1
		if fps_position < len(sys.argv):
			frames_per_second_default = int(sys.argv[fps_position])
	if "--scroll" in sys.argv:
		use_scroll_default = True
	if len(sys.argv) > 1:
		input_folder_path = sys.argv[1]
		temp_folder_path = tempfile.mkdtemp()
		create_video_sequence(
			input_folder_path,
			temp_folder_path,
			use_scroll=use_scroll_default,
			frame_width=frame_width_default,
			frame_height=frame_height_default,
			frames_per_second=frames_per_second_default,
		)
		# shutil.rmtree(temp_folder_path, ignore_errors=True)
