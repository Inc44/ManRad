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
	if adjusted_width > target_width or adjusted_height > target_height:
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
	cv2.imwrite(target_file, final_image)
	return True


def combine_images_vertically(
	image_list, output_folder, sequence_number, frame_width, frame_height
):
	output_file = os.path.join(
		output_folder, "stacked", f"stacked_{sequence_number}.jpg"
	)
	loaded_images = []
	for image_location in image_list:
		current_image = cv2.imread(image_location)
		if current_image is None:
			return None
		loaded_images.append(current_image)
	if not loaded_images:
		return None
	combined_image = cv2.vconcat(loaded_images)
	if combined_image is None:
		return None
	cv2.imwrite(output_file, combined_image)
	return output_file


def generate_static_video(
	sequence_number,
	image_name,
	input_folder,
	output_folder,
	durations,
	frame_rate,
):
	frame_source = os.path.join(input_folder, image_name)
	video_target = os.path.join(output_folder, "still", f"still_{sequence_number}.mkv")
	text_file_path = os.path.join(
		output_folder, "stillframe", f"stillframe_{sequence_number}.txt"
	)
	create_folder(os.path.dirname(video_target))
	create_folder(os.path.dirname(text_file_path))
	with open(text_file_path, "w") as text_file:
		frame_duration = 1.0 / frame_rate
		main_duration = durations[sequence_number] - frame_duration
		text_file.write(f"file '{os.path.abspath(frame_source)}'\n")
		text_file.write(f"duration {frame_duration}\n")
		text_file.write(f"file '{os.path.abspath(frame_source)}'\n")
		text_file.write(f"duration {main_duration}\n")
		text_file.write(f"file '{os.path.abspath(frame_source)}'\n")
	execute_ffmpeg_task(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			text_file_path,
			"-c:v",
			"libx264",
			"-preset",
			"medium",
			video_target,
		]
	)
	return video_target, sequence_number


def generate_fade_video(
	sequence_number,
	image_names,
	input_folder,
	output_folder,
	fade_duration,
	frame_rate,
):
	first_image = os.path.join(input_folder, image_names[sequence_number])
	second_image = os.path.join(input_folder, image_names[sequence_number + 1])
	video_target = os.path.join(
		output_folder, "transition", f"transition_{sequence_number}.mkv"
	)
	create_folder(os.path.dirname(video_target))
	execute_ffmpeg_task(
		[
			"-loop",
			"1",
			"-t",
			str(fade_duration),
			"-i",
			first_image,
			"-loop",
			"1",
			"-t",
			str(fade_duration),
			"-i",
			second_image,
			"-filter_complex",
			f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset=0",
			"-c:v",
			"libx264",
			"-preset",
			"medium",
			"-r",
			str(frame_rate),
			video_target,
		]
	)
	return video_target, sequence_number


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
		[file for file in os.listdir(picture_folder) if file.lower().endswith((".jpg"))]
	)
	if not picture_files:
		return
	image_status = {}
	with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
		tasks = {
			executor.submit(
				adjust_image_size,
				os.path.join(picture_folder, picture_file),
				os.path.join(processed_image_folder, picture_file),
				frame_width,
				frame_height,
			): picture_file
			for picture_file in picture_files
		}
		for task in concurrent.futures.as_completed(tasks):
			picture_file = tasks[task]
			image_status[picture_file] = task.result()
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
	for file_index, picture_file in enumerate(picture_files):
		file_base = os.path.splitext(picture_file)[0]
		sound_path = os.path.join(sound_folder, f"{file_base}.wav")
		if os.path.exists(sound_path):
			duration = find_audio_duration(sound_path)
			if file_index == 0 and duration > 0:
				_, sound_frequency = librosa.load(sound_path, sr=None)
			if duration < 1.0:
				extended_sound_path = os.path.join(
					temp_sound_folder, "long", f"{file_base}_long.wav"
				)
				silent_sound_path = os.path.join(
					temp_sound_folder, "silence", f"silence_{file_index}.wav"
				)
				generate_silent_audio(
					silent_sound_path, 1.0 - duration, sound_frequency
				)
				list_file_path = os.path.join(
					temp_sound_folder, "concat", f"concat_{file_index}.txt"
				)
				with open(list_file_path, "w") as list_file:
					list_file.write(f"file '{os.path.abspath(sound_path)}'\n")
					list_file.write(f"file '{os.path.abspath(silent_sound_path)}'\n")
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
						extended_sound_path,
					]
				)
				sound_files.append(extended_sound_path)
				duration = 1.0
			else:
				sound_files.append(sound_path)
		else:
			silent_sound_path = os.path.join(
				temp_sound_folder, "silence", f"silence_{file_index}.wav"
			)
			generate_silent_audio(silent_sound_path, 1.0, sound_frequency)
			sound_files.append(silent_sound_path)
			duration = 1.0
		sound_durations.append(duration)
	video_segments = []
	fade_segments = []
	temp_video_folder = os.path.join(output_location, "video")
	create_folder(temp_video_folder)
	create_folder(os.path.join(temp_video_folder, "stacked"))
	create_folder(os.path.join(temp_video_folder, "still"))
	create_folder(os.path.join(temp_video_folder, "transition"))
	create_folder(os.path.join(temp_video_folder, "stillframe"))
	if use_scroll:
		full_image_path = os.path.join(temp_video_folder, "combined.jpg")
		image_locations = [
			os.path.join(processed_image_folder, image)
			for image in picture_files
			if image_status.get(image, False)
		]
		if not image_locations:
			return
		image_group_size = 5
		temporary_stacked_images = []
		with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
			tasks = [
				executor.submit(
					combine_images_vertically,
					image_locations[index : index + image_group_size],
					temp_video_folder,
					index,
					frame_width,
					frame_height,
				)
				for index in range(0, len(image_locations), image_group_size)
			]
			for task in concurrent.futures.as_completed(tasks):
				stacked_image = task.result()
				if stacked_image:
					temporary_stacked_images.append(stacked_image)
		if len(temporary_stacked_images) > 1:
			final_image = None
			for image_path in temporary_stacked_images:
				img_data = cv2.imread(image_path)
				if img_data is not None:
					if final_image is None:
						final_image = img_data
					else:
						final_image = cv2.vconcat([final_image, img_data])
			if final_image is not None:
				cv2.imwrite(full_image_path, final_image)
			else:
				return
		elif temporary_stacked_images:
			shutil.copy2(temporary_stacked_images[0], full_image_path)
		else:
			return
		total_sound_duration = sum(sound_durations)
		scrolling_video_path = os.path.join(temp_video_folder, "scroll.mkv")
		if os.path.exists(full_image_path):
			frame_count = int(np.ceil(total_sound_duration * frames_per_second))
			filter_configuration = f"scale={frame_width}:-1,crop={frame_width}:{frame_height}:0:'min(ih-{frame_height},(n)*{frames_per_second}/{frame_count}*(ih-{frame_height}))'"
			execute_ffmpeg_task(
				[
					"-loop",
					"1",
					"-i",
					full_image_path,
					"-t",
					str(total_sound_duration),
					"-filter_complex",
					filter_configuration,
					"-c:v",
					"libx264",
					"-preset",
					"medium",
					"-r",
					str(frames_per_second),
					scrolling_video_path,
				]
			)
			video_segments.append(scrolling_video_path)
		else:
			return
	else:
		with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
			tasks = []
			for file_index, picture_file in enumerate(picture_files):
				if not image_status.get(picture_file, False):
					continue
				tasks.append(
					executor.submit(
						generate_static_video,
						file_index,
						picture_file,
						processed_image_folder,
						temp_video_folder,
						sound_durations,
						frames_per_second,
					)
				)
				if file_index < len(picture_files) - 1:
					next_picture_file = picture_files[file_index + 1]
					if not image_status.get(next_picture_file, False):
						continue
					tasks.append(
						executor.submit(
							generate_fade_video,
							file_index,
							picture_files,
							processed_image_folder,
							temp_video_folder,
							fade_time,
							frames_per_second,
						)
					)
			static_videos = {}
			fade_videos = {}
			for task in concurrent.futures.as_completed(tasks):
				video_path, sequence_number = task.result()
				if "still_" in video_path:
					static_videos[sequence_number] = video_path
				elif "transition_" in video_path:
					fade_videos[sequence_number] = video_path
			for index in range(len(picture_files)):
				if index in static_videos:
					video_segments.append(static_videos[index])
				if index in fade_videos:
					video_segments.append(fade_videos[index])
	final_video_list = os.path.join(output_location, "concat.txt")
	with open(final_video_list, "w") as file:
		for video_segment in video_segments:
			file.write(f"file '{os.path.abspath(video_segment)}'\n")
	final_video_file = os.path.join(output_location, "video.mkv")
	execute_ffmpeg_task(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			final_video_list,
			"-c",
			"copy",
			final_video_file,
		]
	)
	final_audio_list = os.path.join(output_location, "audio_concat.txt")
	with open(final_audio_list, "w") as file:
		for index, audio_location in enumerate(sound_files):
			file.write(f"file '{os.path.abspath(audio_location)}'\n")
			if not use_scroll and index < len(sound_files) - 1:
				silent_audio_location = os.path.join(
					temp_sound_folder, "silence", f"transition_silence_{index}.wav"
				)
				generate_silent_audio(silent_audio_location, fade_time, sound_frequency)
				file.write(f"file '{os.path.abspath(silent_audio_location)}'\n")
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
			"-b:a",
			"96k",
			"-vbr",
			"on",
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
		shutil.rmtree(temp_folder_path, ignore_errors=True)
