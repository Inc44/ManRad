from scipy.io.wavfile import write
import cv2
import librosa
import numpy as np
import os
import shutil
import subprocess


def create_directory(directory_path):
	if not os.path.exists(directory_path):
		os.makedirs(directory_path)


def clear_directory(directory_path):
	if os.path.exists(directory_path):
		shutil.rmtree(directory_path)
	os.makedirs(directory_path)


def create_silence(file_path, duration_seconds, sample_rate=24000):
	samples = int(duration_seconds * sample_rate)
	silence = np.zeros(samples, dtype=np.int16)
	write(file_path, sample_rate, silence)


def run_ffmpeg(command_args):
	base_command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
	subprocess.run(base_command + command_args, check=True)


def create_media_sequence(
	source_dir, output_dir, transition_gap=0.5, transition_steps=15
):
	image_dir = os.path.join(source_dir, "img")
	audio_dir = os.path.join(source_dir, "wav")
	if not os.path.exists(image_dir):
		return
	clear_directory(output_dir)
	frame_dir = os.path.join(output_dir, "frames")
	os.makedirs(frame_dir)
	image_files = sorted(
		[f for f in os.listdir(image_dir) if f.lower().endswith(".jpg")]
	)
	if not image_files:
		return
	audio_files = {}
	if os.path.exists(audio_dir):
		for file in os.listdir(audio_dir):
			if file.lower().endswith(".wav"):
				base_name = os.path.splitext(file)[0]
				audio_files[base_name] = os.path.join(audio_dir, file)
	processed_images = []
	processed_audio = []
	default_sample_rate = 24000
	sample_rate_determined = False
	for image_file in image_files:
		image_path = os.path.join(image_dir, image_file)
		image = cv2.imread(image_path)
		if image is None:
			continue
		image = cv2.resize(image, (900, 1350))
		processed_images.append(image)
		base_name = os.path.splitext(image_file)[0]
		if base_name in audio_files:
			audio_path = audio_files[base_name]
			duration = librosa.get_duration(path=audio_path)
			if not sample_rate_determined:
				_, sample_rate = librosa.load(audio_path, sr=None)
				sample_rate_determined = True
			if duration < 1.0:
				extended_path = os.path.join(output_dir, f"{base_name}_extended.wav")
				silence_path = os.path.join(output_dir, f"{base_name}_silence.wav")
				create_silence(silence_path, 1.0 - duration, sample_rate)
				concat_list = os.path.join(output_dir, f"{base_name}_concat.txt")
				with open(concat_list, "w") as f:
					f.write(f"file '{os.path.abspath(audio_path)}'\n")
					f.write(f"file '{os.path.abspath(silence_path)}'\n")
				run_ffmpeg(
					[
						"-f",
						"concat",
						"-safe",
						"0",
						"-i",
						concat_list,
						"-c",
						"copy",
						extended_path,
					]
				)
				processed_audio.append(extended_path)
			else:
				processed_audio.append(audio_path)
		else:
			current_rate = (
				default_sample_rate if not sample_rate_determined else sample_rate
			)
			silence_path = os.path.join(output_dir, f"{base_name}_silence.wav")
			create_silence(silence_path, 1.0, current_rate)
			processed_audio.append(silence_path)
	if not processed_images:
		return
	current_rate = default_sample_rate if not sample_rate_determined else sample_rate
	silence_path = os.path.join(output_dir, "silent.wav")
	create_silence(silence_path, transition_gap, current_rate)
	video_sequence = []
	audio_sequence = []
	frame_count = 0
	for i, (image, audio) in enumerate(zip(processed_images, processed_audio)):
		duration = librosa.get_duration(path=audio)
		frame_path = os.path.join(frame_dir, f"{frame_count:08d}.jpg")
		cv2.imwrite(frame_path, image)
		step_duration = transition_gap / transition_steps
		video_sequence.append((frame_path, step_duration))
		video_sequence.append((frame_path, duration - step_duration))
		frame_count += 1
		audio_sequence.append(audio)
		if i < len(processed_images) - 1:
			next_image = processed_images[i + 1]
			audio_sequence.append(silence_path)
			for step in range(1, transition_steps + 1):
				blend_ratio = step / (transition_steps + 1)
				blended_image = cv2.addWeighted(
					image, 1 - blend_ratio, next_image, blend_ratio, 0
				)
				frame_path = os.path.join(frame_dir, f"{frame_count:08d}.jpg")
				cv2.imwrite(frame_path, blended_image)
				video_sequence.append((frame_path, step_duration))
				frame_count += 1
	frames_file = os.path.join(output_dir, "frames.txt")
	with open(frames_file, "w") as f:
		for path, duration in video_sequence:
			f.write(f"file '{os.path.abspath(path)}'\n")
			f.write(f"duration {duration:.8f}\n")
	audio_file = os.path.join(output_dir, "audio.txt")
	with open(audio_file, "w") as a:
		for path in audio_sequence:
			a.write(f"file '{os.path.abspath(path)}'\n")
	video_output = os.path.join(output_dir, "video.mp4")
	run_ffmpeg(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			frames_file,
			"-fps_mode",
			"vfr",
			"-c:v",
			"libx264",
			"-preset",
			"medium",
			"-g",
			"0",
			video_output,
		]
	)
	audio_output = os.path.join(output_dir, "audio.opus")
	run_ffmpeg(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			audio_file,
			"-c:a",
			"libopus",
			"-b:a",
			"96k",
			"-vbr",
			"on",
			audio_output,
		]
	)
	final_output = os.path.join(output_dir, "Man.mp4")
	run_ffmpeg(["-i", video_output, "-i", audio_output, "-c", "copy", final_output])
	final_path = os.path.join(source_dir, "Man.mp4")
	shutil.move(final_output, final_path)
	shutil.rmtree(output_dir)


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		source_directory = sys.argv[1]
		temp_directory = "temp"
		create_directory(temp_directory)
		create_media_sequence(source_directory, temp_directory)
