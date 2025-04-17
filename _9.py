import config
from _2 import split_batches
from multiprocessing import Pool, cpu_count
import json
import os
import subprocess


def create_silence(duration, output_path, sample_rate):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-f",
		"lavfi",
		"-i",
		f"anullsrc=r={sample_rate}:cl=mono",
		"-t",
		str(duration),
		"-c:a",
		"pcm_s16le",
		output_path,
	]
	subprocess.run(cmd)


def extend_silence(duration, input_path, output_path, sample_rate):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		input_path,
		"-ar",
		str(sample_rate),
		"-af",
		f"apad=pad_dur={duration}",
		"-c:a",
		"pcm_s16le",
		output_path,
	]
	subprocess.run(cmd)


def get_audio_duration(input_path):
	cmd = [
		"ffprobe",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		input_path,
		"-show_entries",
		"format=duration",
		"-v",
		"quiet",
		"-of",
		"csv=p=0",
	]
	try:
		result = subprocess.check_output(cmd).decode().strip()
		return float(result) if result else 0.0
	except:
		return 0.0


def save_duration_json(basename, duration, output_dir):
	output_path = os.path.join(output_dir, f"{basename}.json")
	with open(output_path, "w") as f:
		json.dump(
			{basename: duration}, f, indent="\t", ensure_ascii=False, sort_keys=True
		)


def copy_audio(input_path, output_path, sample_rate):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		input_path,
		"-ar",
		str(sample_rate),
		"-ac",
		"1",
		"-c:a",
		"pcm_s16le",
		output_path,
	]
	subprocess.run(cmd)


def set_audio_duration(
	audio_output_extension,
	filename,
	input_dir,
	output_dir,
	resized_dir,
	sample_rate,
	target_duration,
):
	input_path = os.path.join(input_dir, filename)
	basename = os.path.splitext(filename)[0]
	resized_path = os.path.join(resized_dir, f"{basename}{audio_output_extension}")
	duration = get_audio_duration(input_path)
	if 0 < duration < target_duration:
		extend_silence(
			target_duration - duration, input_path, resized_path, sample_rate
		)
		duration = target_duration
	elif duration >= target_duration:
		copy_audio(input_path, resized_path, sample_rate)
	else:
		create_silence(target_duration, resized_path, sample_rate)
		duration = target_duration
	save_duration_json(basename, duration, output_dir)


def batch_set_audio_duration(
	audio_output_extension,
	batch,
	input_dir,
	output_dir,
	resized_dir,
	sample_rate,
	target_duration,
):
	for filename in batch:
		set_audio_duration(
			audio_output_extension,
			filename,
			input_dir,
			output_dir,
			resized_dir,
			sample_rate,
			target_duration,
		)


def create_transition_files(
	audio_output_extension,
	audios,
	duration_dir,
	prefix_length,
	resized_dir,
	sample_rate,
	transition_duration,
	transition_suffix,
):
	if transition_duration == 0:
		return
	previous_prefix = None
	for i, filename in enumerate(audios):
		current_prefix = filename[:prefix_length]
		if i > 0 and current_prefix != previous_prefix:
			basename = f"{previous_prefix}{transition_suffix}"
			output_filename = f"{basename}{audio_output_extension}"
			transition_path = os.path.join(resized_dir, output_filename)
			create_silence(transition_duration, transition_path, sample_rate)
			save_duration_json(basename, transition_duration, duration_dir)
		previous_prefix = current_prefix


def create_delay(
	audio_output_extension,
	audios,
	delay_duration,
	delay_suffix,
	duration_dir,
	prefix_length,
	resized_dir,
	sample_rate,
):
	if delay_duration == 0 or not audios:
		return
	filename = audios[0]
	basename = f"{filename[:prefix_length]}{delay_suffix}"
	output_filename = f"{basename}{audio_output_extension}"
	delay_path = os.path.join(resized_dir, output_filename)
	create_silence(delay_duration, delay_path, sample_rate)
	save_duration_json(basename, delay_duration, duration_dir)


def merge_duration_json(input_dir, merged_durations_filename, output_dir):
	durations = {}
	files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
	for filename in files:
		path = os.path.join(input_dir, filename)
		with open(path) as f:
			duration_data = json.load(f)
			durations.update(duration_data)
	path = os.path.join(output_dir, merged_durations_filename)
	with open(path, "w") as f:
		json.dump(durations, f, indent="\t", ensure_ascii=False, sort_keys=True)


def calculate_total_duration(
	input_dir, merged_durations_filename, total_duration_filename
):
	path = os.path.join(input_dir, merged_durations_filename)
	total = 0.0
	with open(path) as f:
		durations = json.load(f)
		total = sum(durations.values())
	output_path = os.path.join(input_dir, total_duration_filename)
	with open(output_path, "w") as f:
		f.write(str(total))


def create_audio_list(audio_list_filename, audios, input_dir, output_dir):
	output_path = os.path.join(output_dir, audio_list_filename)
	with open(output_path, "w") as f:
		for filename in audios:
			path = os.path.join(input_dir, filename)
			f.write(f"file '{os.path.abspath(path)}'\n")


def render_audio(
	audio_filename, audio_list_filename, input_dir, render_dir, sample_rate
):
	path_input = os.path.join(input_dir, audio_list_filename)
	path_render = os.path.join(render_dir, audio_filename)
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-f",
		"concat",
		"-safe",
		"0",
		"-i",
		path_input,
		"-ar",
		str(sample_rate),
		"-c:a",
		"libopus",
		"-vbr",
		"on",
		"-compression_level",
		"10",
		"-frame_duration",
		"60",
		path_render,
	]
	subprocess.run(cmd)


def audio(
	audio_concat_list_filename,
	audio_delay_duration,
	audio_filename,
	audio_output_extension,
	audio_target_segment_duration,
	audio_transition_duration,
	delay_suffix,
	dirs,
	merged_durations_filename,
	output_image_extension,
	prefix_length,
	sample_rate,
	total_duration_filename,
	transition_suffix,
	workers_config,
):
	initial_audios = sorted(
		[
			f.replace(output_image_extension, audio_output_extension)
			for f in os.listdir(dirs["image_crops"])
			if f.lower().endswith(output_image_extension)
		]
	)
	workers = min(workers_config, cpu_count())
	batches = split_batches(initial_audios, workers)
	with Pool(processes=workers) as pool:
		args = [
			(
				audio_output_extension,
				batch,
				dirs["image_audio"],
				dirs["image_durations"],
				dirs["image_audio_resized"],
				sample_rate,
				audio_target_segment_duration,
			)
			for batch in batches
		]
		pool.starmap_async(batch_set_audio_duration, args).get()
	processed_audios = sorted(
		[
			f
			for f in os.listdir(dirs["image_audio_resized"])
			if f.lower().endswith(audio_output_extension)
		]
	)
	create_transition_files(
		audio_output_extension,
		processed_audios,
		dirs["image_durations"],
		prefix_length,
		dirs["image_audio_resized"],
		sample_rate,
		audio_transition_duration,
		transition_suffix,
	)
	audios_with_transitions = sorted(
		[
			f
			for f in os.listdir(dirs["image_audio_resized"])
			if f.lower().endswith(audio_output_extension)
		]
	)
	create_delay(
		audio_output_extension,
		audios_with_transitions,
		audio_delay_duration,
		delay_suffix,
		dirs["image_durations"],
		prefix_length,
		dirs["image_audio_resized"],
		sample_rate,
	)
	merge_duration_json(
		dirs["image_durations"], merged_durations_filename, dirs["merge"]
	)
	calculate_total_duration(
		dirs["merge"], merged_durations_filename, total_duration_filename
	)
	final_audios = sorted(
		[
			f
			for f in os.listdir(dirs["image_audio_resized"])
			if f.lower().endswith(audio_output_extension)
		]
	)
	create_audio_list(
		audio_concat_list_filename,
		final_audios,
		dirs["image_audio_resized"],
		dirs["merge"],
	)
	render_audio(
		audio_filename,
		audio_concat_list_filename,
		dirs["merge"],
		dirs["render"],
		sample_rate,
	)


if __name__ == "__main__":
	audio(
		config.AUDIO_CONCAT_LIST_FILENAME,
		config.AUDIO_DELAY_DURATION,
		config.AUDIO,
		config.AUDIO_OUTPUT_EXTENSION,
		config.AUDIO_TARGET_SEGMENT_DURATION,
		config.AUDIO_TRANSITION_DURATION,
		config.DELAY_SUFFIX,
		config.DIRS,
		config.MERGED_DURATIONS_FILENAME,
		config.OUTPUT_IMAGE_EXTENSION,
		config.PREFIX_LENGTH,
		config.SAMPLE_RATE,
		config.TOTAL_DURATION_FILENAME,
		config.TRANSITION_SUFFIX,
		config.WORKERS,
	)
