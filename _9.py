from _0 import DIRS
from _2 import split_batches
from multiprocessing import Pool, cpu_count
import json
import os
import subprocess

SAMPLE_RATE = 48000
TARGET_DURATION = 1
TRANSITION_DURATION = 0.5
WORKERS = 6


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
		return float(subprocess.check_output(cmd).decode().strip())
	except:
		return 0.0


def save_duration_json(basename, duration, output_dir):
	output_path = os.path.join(output_dir, f"{basename}.json")
	with open(output_path, "w") as f:
		json.dump({basename: duration}, f, indent="\t", ensure_ascii=False)


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
	filename, input_dir, resized_dir, output_dir, sample_rate, target_duration
):
	input_path = os.path.join(input_dir, filename)
	basename = os.path.splitext(filename)[0]
	resized_path = os.path.join(resized_dir, filename)
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
	batch, input_dir, resized_dir, output_dir, sample_rate, target_duration
):
	for filename in batch:
		set_audio_duration(
			filename, input_dir, resized_dir, output_dir, sample_rate, target_duration
		)


def create_transition_files(
	audios, resized_dir, duration_dir, transition_duration, sample_rate
):
	if transition_duration == 0:
		return
	previous_prefix = None
	for i, filename in enumerate(audios):
		current_prefix = filename[:4]
		if i > 0 and current_prefix != previous_prefix:
			basename = f"{current_prefix}000"
			filename = f"{basename}.wav"
			transition_path = os.path.join(resized_dir, filename)
			create_silence(transition_duration, transition_path, sample_rate)
			save_duration_json(basename, transition_duration, duration_dir)
		previous_prefix = current_prefix


def merge_duration_json(output_dir, input_dir):
	durations = {}
	files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
	for filename in files:
		path = os.path.join(input_dir, filename)
		with open(path, "r") as f:
			duration = json.load(f)
		for key, value in duration.items():
			durations[key] = value
	path = os.path.join(output_dir, "durations.json")
	with open(path, "w") as f:
		json.dump(durations, f, indent="\t", ensure_ascii=False)


def calculate_total_duration(input_dir):
	path = os.path.join(input_dir, "durations.json")
	with open(path, "r") as f:
		durations = json.load(f)
	total = 0
	for i in durations.values():
		total += i
	path = os.path.join(input_dir, "total_duration.txt")
	with open(path, "w") as f:
		f.write(str(total))


def create_audio_list(audios, input_dir, output_dir):
	output_path = os.path.join(output_dir, "audio_list.txt")
	with open(output_path, "w") as f:
		for i, filename in enumerate(audios):
			abs_path = os.path.abspath(os.path.join(input_dir, filename))
			f.write(f"file '{abs_path}'\n")


def render_audio(input_dir, render_dir, sample_rate):
	path_input = os.path.join(input_dir, "audio_list.txt")
	path_render = os.path.join(render_dir, "audio.opus")
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


if __name__ == "__main__":
	audios = sorted(
		[
			f.replace(".jpg", ".wav")
			for f in os.listdir(DIRS["image_crops"])
			if f.lower().endswith(".jpg")
		]
	)
	workers = min(WORKERS, cpu_count())
	batches = split_batches(workers, audios)
	with Pool(processes=workers) as pool:
		args = [
			(
				batch,
				DIRS["image_audio"],
				DIRS["image_audio_resized"],
				DIRS["image_durations"],
				SAMPLE_RATE,
				TARGET_DURATION,
			)
			for batch in batches
		]
		pool.starmap_async(batch_set_audio_duration, args).get()
	audios = sorted(
		[
			f
			for f in os.listdir(DIRS["image_audio_resized"])
			if f.lower().endswith(".wav")
		]
	)
	create_transition_files(
		audios,
		DIRS["image_audio_resized"],
		DIRS["image_durations"],
		TRANSITION_DURATION,
		SAMPLE_RATE,
	)
	merge_duration_json(DIRS["merge"], DIRS["image_durations"])
	calculate_total_duration(DIRS["merge"])
	audios = sorted(
		[
			f
			for f in os.listdir(DIRS["image_audio_resized"])
			if f.lower().endswith(".wav")
		]
	)
	create_audio_list(
		audios,
		DIRS["image_audio_resized"],
		DIRS["merge"],
	)
	render_audio(DIRS["merge"], DIRS["render"], SAMPLE_RATE)
