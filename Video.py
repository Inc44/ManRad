from scipy.io.wavfile import write
import cv2
import librosa
import numpy as np
import os
import shutil
import subprocess
import sys


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


def preprocess_images(image_files, image_dir, output_width):
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


def create_media_continuous_scroll(
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
	unique_frames = {}
	frame_files = {}
	video_sequence = []
	last_y_center = 0
	for segment_index in range(len(processed_images)):
		segment_duration = audio_durations[segment_index]
		start_pos = positions[segment_index]
		end_pos = (
			positions[segment_index + 1]
			if segment_index < len(positions) - 1
			else full_height - output_height
		)
		pause_duration = segment_duration * pause_percent
		y_center = max(last_y_center, min(start_pos, full_height - output_height // 2))
		last_y_center = y_center
		y_start = max(0, y_center - output_height // 2)
		y_end = min(y_start + output_height, full_height)
		if y_end - y_start < output_height:
			y_start = max(0, y_end - output_height)
		frame_hash = f"{y_start}_{y_end}"
		if frame_hash not in frame_files:
			if frame_hash not in unique_frames:
				unique_frames[frame_hash] = (y_start, y_end)
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
			frame_path = os.path.join(output_dir, f"{len(frame_files):08d}.jpg")
			cv2.imwrite(frame_path, visible)
			frame_files[frame_hash] = frame_path
		video_sequence.append((frame_files[frame_hash], pause_duration))
		scroll_duration = segment_duration * (
			1 - pause_percent - ease_in_percent - ease_out_percent
		)
		if scroll_duration > 0 and segment_index < len(processed_images) - 1:
			scroll_frames = max(5, int(scroll_duration * frames_per_second / 4))
			frame_time = scroll_duration / scroll_frames
			for i in range(1, scroll_frames + 1):
				scroll_progress = i / scroll_frames
				if scroll_progress < 0.5:
					eased_progress = 2 * scroll_progress * scroll_progress
				else:
					eased_progress = (
						1
						- ((-2 * scroll_progress + 2) * (-2 * scroll_progress + 2)) / 2
					)
				y_offset = int(start_pos + eased_progress * (end_pos - start_pos))
				y_center = max(
					last_y_center, min(y_offset, full_height - output_height // 2)
				)
				last_y_center = y_center
				y_start = max(0, y_center - output_height // 2)
				y_end = min(y_start + output_height, full_height)
				if y_end - y_start < output_height:
					y_start = max(0, y_end - output_height)
				frame_hash = f"{y_start}_{y_end}"
				if frame_hash not in frame_files:
					if frame_hash not in unique_frames:
						unique_frames[frame_hash] = (y_start, y_end)
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
					frame_path = os.path.join(output_dir, f"{len(frame_files):08d}.jpg")
					cv2.imwrite(frame_path, visible)
					frame_files[frame_hash] = frame_path
				video_sequence.append((frame_files[frame_hash], frame_time))
		ease_out_duration = segment_duration * ease_out_percent
		if ease_out_duration > 0 and segment_index < len(processed_images) - 1:
			video_sequence[-1] = (
				video_sequence[-1][0],
				video_sequence[-1][1] + ease_out_duration,
			)
	return video_sequence


def create_media_sequence(
	source_dir,
	output_dir,
	transition_gap=0.5,
	transition_steps=15,
	use_scrolling=False,
	output_size=(900, 1350),
	frames_per_second=30,
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
	processed_audio = []
	audio_durations = []
	default_sample_rate = 24000
	sample_rate_determined = False
	for image_file in image_files:
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
				duration = 1.0
			else:
				processed_audio.append(audio_path)
			audio_durations.append(duration)
		else:
			current_rate = (
				default_sample_rate if not sample_rate_determined else sample_rate
			)
			silence_path = os.path.join(output_dir, f"{base_name}_silence.wav")
			create_silence(silence_path, 1.0, current_rate)
			processed_audio.append(silence_path)
			audio_durations.append(1.0)
	if len(processed_audio) == 0:
		return
	current_rate = default_sample_rate if not sample_rate_determined else sample_rate
	video_sequence = []
	audio_sequence = processed_audio
	if use_scrolling:
		processed_images = preprocess_images(image_files, image_dir, output_size[0])
		if not processed_images:
			return
		video_sequence = create_media_continuous_scroll(
			processed_images, audio_durations, output_size, frames_per_second, frame_dir
		)
	else:
		silence_path = os.path.join(output_dir, "silent.wav")
		create_silence(silence_path, transition_gap, current_rate)
		frame_count = 0
		for i, image_file in enumerate(image_files):
			image_path = os.path.join(image_dir, image_file)
			image = cv2.imread(image_path)
			if image is None:
				continue
			duration = audio_durations[i]
			resized_image = cv2.resize(image, (output_size[0], output_size[1]))
			frame_path = os.path.join(frame_dir, f"{frame_count:08d}.jpg")
			cv2.imwrite(frame_path, resized_image)
			step_duration = transition_gap / transition_steps
			video_sequence.append((frame_path, step_duration))
			video_sequence.append((frame_path, duration - step_duration))
			if i < len(image_files) - 1:
				audio_sequence.insert(i * 2 + 1, silence_path)
				next_image_path = os.path.join(image_dir, image_files[i + 1])
				next_image = cv2.imread(next_image_path)
				if next_image is not None:
					next_image_resized = cv2.resize(
						next_image, (output_size[0], output_size[1])
					)
					for step in range(1, transition_steps + 1):
						blend_ratio = step / (transition_steps + 1)
						blended_image = cv2.addWeighted(
							resized_image,
							1 - blend_ratio,
							next_image_resized,
							blend_ratio,
							0,
						)
						frame_path = os.path.join(
							frame_dir, f"{frame_count + step:08d}.jpg"
						)
						cv2.imwrite(frame_path, blended_image)
						video_sequence.append((frame_path, step_duration))
				frame_count += transition_steps
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
	if "--width" in sys.argv:
		width_index = sys.argv.index("--width") + 1
		if width_index < len(sys.argv):
			width = int(sys.argv[width_index])
	if "--height" in sys.argv:
		height_index = sys.argv.index("--height") + 1
		if height_index < len(sys.argv):
			height = int(sys.argv[height_index])
	if "--fps" in sys.argv:
		fps_index = sys.argv.index("--fps") + 1
		if fps_index < len(sys.argv):
			frames_per_second = int(sys.argv[fps_index])
	if len(sys.argv) > 1:
		source_directory = sys.argv[1]
		temp_directory = "temp"
		create_directory(temp_directory)
		use_scrolling = "--scroll" in sys.argv
		width = 900
		height = 1350
		frames_per_second = 30
		create_media_sequence(
			source_directory,
			temp_directory,
			use_scrolling=use_scrolling,
			output_size=(width, height),
			frames_per_second=frames_per_second,
		)
