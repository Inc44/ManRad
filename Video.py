from scipy.io.wavfile import write
import librosa
import numpy as np
import os
import shutil
import subprocess
import sys
import tempfile


def create_directory(directory_path):
	if not os.path.exists(directory_path):
		os.makedirs(directory_path)


def run_ffmpeg(args, quiet=True):
	cmd = ["ffmpeg", "-y"]
	if quiet:
		cmd.extend(["-hide_banner", "-loglevel", "error"])
	cmd.extend(args)
	subprocess.run(cmd, check=True)


def create_silence(file_path, duration, sample_rate=24000):
	samples = int(duration * sample_rate)
	silence = np.zeros(samples, dtype=np.int16)
	write(file_path, sample_rate, silence)


def get_audio_duration(audio_path):
	if os.path.exists(audio_path):
		return librosa.get_duration(path=audio_path)
	return 0


def create_media_sequence(
	source_dir,
	output_dir,
	transition_gap=0.5,
	use_scrolling=False,
	output_size=(900, 1350),
	frames_per_second=30,
):
	width, height = output_size
	image_dir = os.path.join(source_dir, "img")
	audio_dir = os.path.join(source_dir, "wav")
	if not os.path.exists(image_dir):
		return
	os.makedirs(output_dir, exist_ok=True)
	resized_dir = os.path.join(output_dir, "resized")
	os.makedirs(resized_dir, exist_ok=True)
	image_files = sorted(
		[f for f in os.listdir(image_dir) if f.lower().endswith((".jpg"))]
	)
	if not image_files:
		return
	for img_file in image_files:
		input_path = os.path.join(image_dir, img_file)
		output_path = os.path.join(resized_dir, img_file)
		run_ffmpeg(
			[
				"-i",
				input_path,
				"-vf",
				f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
				output_path,
			]
		)
	audio_files = []
	audio_durations = []
	sample_rate = 24000
	for i, img_file in enumerate(image_files):
		base_name = os.path.splitext(img_file)[0]
		audio_path = os.path.join(audio_dir, f"{base_name}.wav")
		if os.path.exists(audio_path):
			duration = get_audio_duration(audio_path)
			if i == 0 and duration > 0:
				_, sample_rate = librosa.load(audio_path, sr=None)
			if duration < 1.0:
				extended_path = os.path.join(output_dir, f"{base_name}_extended.wav")
				silence_path = os.path.join(output_dir, f"silence_{i}.wav")
				create_silence(silence_path, 1.0 - duration, sample_rate)
				concat_list = os.path.join(output_dir, f"concat_{i}.txt")
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
				audio_files.append(extended_path)
				duration = 1.0
			else:
				audio_files.append(audio_path)
		else:
			silence_path = os.path.join(output_dir, f"silence_{i}.wav")
			create_silence(silence_path, 1.0, sample_rate)
			audio_files.append(silence_path)
			duration = 1.0
		audio_durations.append(duration)
	video_segments = []
	transition_segments = []
	if use_scrolling:
		combined_img = os.path.join(output_dir, "combined.jpg")
		img_paths = [os.path.join(resized_dir, img) for img in image_files]
		group_size = 5
		temp_stacked_images = []
		for i in range(0, len(img_paths), group_size):
			group = img_paths[i : i + group_size]
			stacked_output = os.path.join(output_dir, f"stacked_{i}.jpg")
			temp_stacked_images.append(stacked_output)
			filter_complex = ""
			input_args = []
			for j, img_path in enumerate(group):
				input_args.extend(["-i", img_path])
				filter_complex += f"[{j}:v]"
			filter_complex += f"vstack=inputs={len(group)}[out]"
			run_ffmpeg(
				input_args
				+ ["-filter_complex", filter_complex, "-map", "[out]", stacked_output]
			)
		if len(temp_stacked_images) > 1:
			filter_complex = ""
			input_args = []
			for j, img_path in enumerate(temp_stacked_images):
				input_args.extend(["-i", img_path])
				filter_complex += f"[{j}:v]"
			filter_complex += f"vstack=inputs={len(temp_stacked_images)}[out]"
			run_ffmpeg(
				input_args
				+ ["-filter_complex", filter_complex, "-map", "[out]", combined_img]
			)
		else:
			shutil.copy2(temp_stacked_images[0], combined_img)
		total_duration = sum(audio_durations)
		scroll_video = os.path.join(output_dir, "scroll.mkv")
		filter_expr = f"scale={width}:-1,crop={width}:{height}:0:'min(ih-{height},n/(30*{total_duration})*(ih-{height}))'"
		run_ffmpeg(
			[
				"-loop",
				"1",
				"-i",
				combined_img,
				"-t",
				str(total_duration),
				"-filter_complex",
				filter_expr,
				"-c:v",
				"libx264",
				"-preset",
				"medium",
				"-r",
				str(frames_per_second),
				scroll_video,
			]
		)
		video_segments.append(scroll_video)
	else:
		for i, img_file in enumerate(image_files):
			still_frame = os.path.join(resized_dir, img_file)
			still_video = os.path.join(output_dir, f"still_{i}.mkv")
			concat_txt = os.path.join(output_dir, f"stillframe_{i}.txt")
			with open(concat_txt, "w") as f:
				frame_duration = 1.0 / frames_per_second
				main_duration = audio_durations[i] - frame_duration
				f.write(f"file '{os.path.abspath(still_frame)}'\n")
				f.write(f"duration {frame_duration}\n")
				f.write(f"file '{os.path.abspath(still_frame)}'\n")
				f.write(f"duration {main_duration}\n")
				f.write(f"file '{os.path.abspath(still_frame)}'\n")
			run_ffmpeg(
				[
					"-f",
					"concat",
					"-safe",
					"0",
					"-i",
					concat_txt,
					"-c:v",
					"libx264",
					"-preset",
					"medium",
					still_video,
				]
			)
			video_segments.append(still_video)
			if i < len(image_files) - 1:
				next_frame = os.path.join(resized_dir, image_files[i + 1])
				transition_video = os.path.join(output_dir, f"transition_{i}.mkv")
				run_ffmpeg(
					[
						"-loop",
						"1",
						"-t",
						str(transition_gap),
						"-i",
						still_frame,
						"-loop",
						"1",
						"-t",
						str(transition_gap),
						"-i",
						next_frame,
						"-filter_complex",
						f"[0:v][1:v]xfade=transition=fade:duration={transition_gap}:offset=0",
						"-c:v",
						"libx264",
						"-preset",
						"medium",
						"-r",
						str(frames_per_second),
						transition_video,
					]
				)
				transition_segments.append(transition_video)
	concat_file = os.path.join(output_dir, "concat.txt")
	with open(concat_file, "w") as f:
		if use_scrolling:
			for vid in video_segments:
				f.write(f"file '{os.path.abspath(vid)}'\n")
		else:
			for i in range(len(video_segments)):
				f.write(f"file '{os.path.abspath(video_segments[i])}'\n")
				if i < len(transition_segments):
					f.write(f"file '{os.path.abspath(transition_segments[i])}'\n")
	video_output = os.path.join(output_dir, "video.mkv")
	run_ffmpeg(
		["-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", video_output]
	)
	audio_concat = os.path.join(output_dir, "audio_concat.txt")
	with open(audio_concat, "w") as f:
		for i, audio_file in enumerate(audio_files):
			f.write(f"file '{os.path.abspath(audio_file)}'\n")
			if not use_scrolling and i < len(audio_files) - 1:
				silence_path = os.path.join(output_dir, f"transition_silence_{i}.wav")
				create_silence(silence_path, transition_gap, sample_rate)
				f.write(f"file '{os.path.abspath(silence_path)}'\n")
	audio_output = os.path.join(output_dir, "audio.opus")
	run_ffmpeg(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			audio_concat,
			"-c:a",
			"libopus",
			"-b:a",
			"96k",
			"-vbr",
			"on",
			audio_output,
		]
	)
	final_output = os.path.join(output_dir, "Man.mkv")
	run_ffmpeg(["-i", video_output, "-i", audio_output, "-c", "copy", final_output])
	final_path = os.path.join(source_dir, "Man.mkv")
	shutil.copy2(final_output, final_path)


if __name__ == "__main__":
	width = 900
	height = 1350
	frames_per_second = 30
	use_scrolling = False
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
	if "--scroll" in sys.argv:
		use_scrolling = True
	if len(sys.argv) > 1:
		source_directory = sys.argv[1]
		temp_directory = tempfile.mkdtemp()
		try:
			create_media_sequence(
				source_directory,
				temp_directory,
				use_scrolling=use_scrolling,
				output_size=(width, height),
				frames_per_second=frames_per_second,
			)
		finally:
			shutil.rmtree(temp_directory, ignore_errors=True)
