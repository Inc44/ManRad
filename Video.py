from scipy.io.wavfile import write
import librosa
import numpy as np
import os
import shutil
import subprocess
import sys
import tempfile


def make_directory(directory_path):
	if not os.path.exists(directory_path):
		os.makedirs(directory_path)


def do_ffmpeg_command(arguments, show_output=False):
	command = ["ffmpeg", "-y"]
	if not show_output:
		command.extend(["-hide_banner", "-loglevel", "error"])
	command.extend(arguments)
	subprocess.run(command, check=True)


def make_silence_file(file_path, duration, sample_rate=24000):
	samples = int(duration * sample_rate)
	silence = np.zeros(samples, dtype=np.int16)
	write(file_path, sample_rate, silence)


def get_audio_length(audio_path):
	if os.path.exists(audio_path):
		return librosa.get_duration(path=audio_path)
	return 0


def make_video_from_images_and_audio(
	source_directory,
	output_directory,
	transition_time=0.5,
	enable_scrolling=False,
	video_width=900,
	video_height=1350,
	video_fps=30,
):
	image_directory = os.path.join(source_directory, "img")
	audio_directory = os.path.join(source_directory, "wav")
	if not os.path.exists(image_directory):
		return
	make_directory(output_directory)
	resized_image_directory = os.path.join(output_directory, "images", "resized")
	make_directory(resized_image_directory)
	image_files = sorted(
		[
			file
			for file in os.listdir(image_directory)
			if file.lower().endswith((".jpg"))
		]
	)
	if not image_files:
		return
	for image_file in image_files:
		input_image_path = os.path.join(image_directory, image_file)
		output_image_path = os.path.join(resized_image_directory, image_file)
		do_ffmpeg_command(
			[
				"-i",
				input_image_path,
				"-vf",
				f"scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2",
				output_image_path,
			]
		)
	audio_files = []
	audio_lengths = []
	audio_sample_rate = 24000
	temp_audio_directory = os.path.join(output_directory, "audio", "temp")
	make_directory(temp_audio_directory)
	for index, image_file in enumerate(image_files):
		base_name = os.path.splitext(image_file)[0]
		audio_path = os.path.join(audio_directory, f"{base_name}.wav")
		if os.path.exists(audio_path):
			length = get_audio_length(audio_path)
			if index == 0 and length > 0:
				_, audio_sample_rate = librosa.load(audio_path, sr=None)
			if length < 1.0:
				extended_audio_path = os.path.join(
					temp_audio_directory, f"{base_name}_long.wav"
				)
				silence_audio_path = os.path.join(
					temp_audio_directory, f"silence_{index}.wav"
				)
				make_silence_file(silence_audio_path, 1.0 - length, audio_sample_rate)
				concat_list_path = os.path.join(
					temp_audio_directory, f"concat_{index}.txt"
				)
				with open(concat_list_path, "w") as file:
					file.write(f"file '{os.path.abspath(audio_path)}'\n")
					file.write(f"file '{os.path.abspath(silence_audio_path)}'\n")
				do_ffmpeg_command(
					[
						"-f",
						"concat",
						"-safe",
						"0",
						"-i",
						concat_list_path,
						"-c",
						"copy",
						extended_audio_path,
					]
				)
				audio_files.append(extended_audio_path)
				length = 1.0
			else:
				audio_files.append(audio_path)
		else:
			silence_audio_path = os.path.join(
				temp_audio_directory, f"silence_{index}.wav"
			)
			make_silence_file(silence_audio_path, 1.0, audio_sample_rate)
			audio_files.append(silence_audio_path)
			length = 1.0
		audio_lengths.append(length)
	video_parts = []
	transition_parts = []
	temp_video_directory = os.path.join(output_directory, "video", "temp")
	make_directory(temp_video_directory)
	if enable_scrolling:
		combined_image_path = os.path.join(temp_video_directory, "combined.jpg")
		image_paths = [
			os.path.join(resized_image_directory, image) for image in image_files
		]
		group_count = 5
		temp_stacked_images = []
		for index in range(0, len(image_paths), group_count):
			group = image_paths[index : index + group_count]
			stacked_output_path = os.path.join(
				temp_video_directory, f"stacked_{index}.jpg"
			)
			temp_stacked_images.append(stacked_output_path)
			filter_sequence = ""
			input_parameters = []
			for sub_index, image_path in enumerate(group):
				input_parameters.extend(["-i", image_path])
				filter_sequence += f"[{sub_index}:v]"
			filter_sequence += f"vstack=inputs={len(group)}[out]"
			do_ffmpeg_command(
				input_parameters
				+ [
					"-filter_complex",
					filter_sequence,
					"-map",
					"[out]",
					stacked_output_path,
				]
			)
		if len(temp_stacked_images) > 1:
			filter_sequence = ""
			input_parameters = []
			for sub_index, image_path in enumerate(temp_stacked_images):
				input_parameters.extend(["-i", image_path])
				filter_sequence += f"[{sub_index}:v]"
			filter_sequence += f"vstack=inputs={len(temp_stacked_images)}[out]"
			do_ffmpeg_command(
				input_parameters
				+ [
					"-filter_complex",
					filter_sequence,
					"-map",
					"[out]",
					combined_image_path,
				]
			)
		else:
			shutil.copy2(temp_stacked_images[0], combined_image_path)
		total_audio_length = sum(audio_lengths)
		scroll_video_path = os.path.join(temp_video_directory, "scroll.mkv")
		filter_text = f"scale={video_width}:-1,crop={video_width}:{video_height}:0:'min(ih-{video_height},n/(30*{total_audio_length})*(ih-{video_height}))'"
		do_ffmpeg_command(
			[
				"-loop",
				"1",
				"-i",
				combined_image_path,
				"-t",
				str(total_audio_length),
				"-filter_complex",
				filter_text,
				"-c:v",
				"libx264",
				"-preset",
				"medium",
				"-r",
				str(video_fps),
				scroll_video_path,
			]
		)
		video_parts.append(scroll_video_path)
	else:
		for index, image_file in enumerate(image_files):
			still_frame_path = os.path.join(resized_image_directory, image_file)
			still_video_path = os.path.join(temp_video_directory, f"still_{index}.mkv")
			concat_text_path = os.path.join(
				temp_video_directory, f"stillframe_{index}.txt"
			)
			with open(concat_text_path, "w") as file:
				one_frame_length = 1.0 / video_fps
				primary_length = audio_lengths[index] - one_frame_length
				file.write(f"file '{os.path.abspath(still_frame_path)}'\n")
				file.write(f"duration {one_frame_length}\n")
				file.write(f"file '{os.path.abspath(still_frame_path)}'\n")
				file.write(f"duration {primary_length}\n")
				file.write(f"file '{os.path.abspath(still_frame_path)}'\n")
			do_ffmpeg_command(
				[
					"-f",
					"concat",
					"-safe",
					"0",
					"-i",
					concat_text_path,
					"-c:v",
					"libx264",
					"-preset",
					"medium",
					still_video_path,
				]
			)
			video_parts.append(still_video_path)
			if index < len(image_files) - 1:
				next_frame_path = os.path.join(
					resized_image_directory, image_files[index + 1]
				)
				transition_video_path = os.path.join(
					temp_video_directory, f"transition_{index}.mkv"
				)
				do_ffmpeg_command(
					[
						"-loop",
						"1",
						"-t",
						str(transition_time),
						"-i",
						still_frame_path,
						"-loop",
						"1",
						"-t",
						str(transition_time),
						"-i",
						next_frame_path,
						"-filter_complex",
						f"[0:v][1:v]xfade=transition=fade:duration={transition_time}:offset=0",
						"-c:v",
						"libx264",
						"-preset",
						"medium",
						"-r",
						str(video_fps),
						transition_video_path,
					]
				)
				transition_parts.append(transition_video_path)
	final_video_list_path = os.path.join(output_directory, "concat.txt")
	with open(final_video_list_path, "w") as file:
		if enable_scrolling:
			for video_path in video_parts:
				file.write(f"file '{os.path.abspath(video_path)}'\n")
		else:
			for index in range(len(video_parts)):
				file.write(f"file '{os.path.abspath(video_parts[index])}'\n")
				if index < len(transition_parts):
					file.write(f"file '{os.path.abspath(transition_parts[index])}'\n")
	final_video_output_path = os.path.join(output_directory, "video.mkv")
	do_ffmpeg_command(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			final_video_list_path,
			"-c",
			"copy",
			final_video_output_path,
		]
	)
	final_audio_list_path = os.path.join(output_directory, "audio_concat.txt")
	with open(final_audio_list_path, "w") as file:
		for index, audio_file_path in enumerate(audio_files):
			file.write(f"file '{os.path.abspath(audio_file_path)}'\n")
			if not enable_scrolling and index < len(audio_files) - 1:
				silence_audio_path = os.path.join(
					temp_audio_directory, f"transition_silence_{index}.wav"
				)
				make_silence_file(
					silence_audio_path, transition_time, audio_sample_rate
				)
				file.write(f"file '{os.path.abspath(silence_audio_path)}'\n")
	final_audio_output_path = os.path.join(output_directory, "audio.opus")
	do_ffmpeg_command(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			final_audio_list_path,
			"-c:a",
			"libopus",
			"-b:a",
			"96k",
			"-vbr",
			"on",
			final_audio_output_path,
		]
	)
	complete_output_path = os.path.join(output_directory, "Man.mkv")
	do_ffmpeg_command(
		[
			"-i",
			final_video_output_path,
			"-i",
			final_audio_output_path,
			"-c",
			"copy",
			complete_output_path,
		]
	)
	final_output_copy_path = os.path.join(source_directory, "Man.mkv")
	shutil.copy2(complete_output_path, final_output_copy_path)


if __name__ == "__main__":
	video_width = 900
	video_height = 1350
	video_fps = 30
	enable_scrolling = False
	if "--width" in sys.argv:
		width_index = sys.argv.index("--width") + 1
		if width_index < len(sys.argv):
			video_width = int(sys.argv[width_index])
	if "--height" in sys.argv:
		height_index = sys.argv.index("--height") + 1
		if height_index < len(sys.argv):
			video_height = int(sys.argv[height_index])
	if "--fps" in sys.argv:
		fps_index = sys.argv.index("--fps") + 1
		if fps_index < len(sys.argv):
			video_fps = int(sys.argv[fps_index])
	if "--scroll" in sys.argv:
		enable_scrolling = True
	if len(sys.argv) > 1:
		source_directory_path = sys.argv[1]
		temp_directory_path = tempfile.mkdtemp()
		make_video_from_images_and_audio(
			source_directory_path,
			temp_directory_path,
			enable_scrolling=enable_scrolling,
			video_width=video_width,
			video_height=video_height,
			video_fps=video_fps,
		)
		shutil.rmtree(temp_directory_path, ignore_errors=True)
