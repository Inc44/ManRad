# Modify to make the silence created proportional to the possible duration of missing audio by reading the text length
# Make the transition duration work for scroll
from _0 import DIRS
from _2 import split_batches
from multiprocessing import Pool, cpu_count
import json
import os
import subprocess

TARGET_DURATION = 1
TRANSITION = 0
WORKERS = 6


def create_silence(duration, filename, input_dir):
	path = os.path.join(input_dir, filename)
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-f",
		"lavfi",
		"-i",
		"anullsrc=cl=mono",
		"-t",
		str(duration),
		path,
	]
	subprocess.run(cmd)


def extend_silence(duration, filename, input_dir):
	path = os.path.join(input_dir, filename)
	basename = os.path.splitext(filename)[0]
	extended_filename = f"{basename}_extended.wav"
	extended_path = os.path.join(input_dir, extended_filename)
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		path,
		"-af",
		f"apad=pad_dur={duration}",
		extended_path,
	]
	subprocess.run(cmd)
	os.remove(path)
	os.rename(extended_path, path)


def get_audio_duration(filename, input_dir):
	path = os.path.join(input_dir, filename)
	cmd = [
		"ffprobe",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		path,
		"-show_entries",
		"format=duration",
		"-v",
		"quiet",
		"-of",
		"csv=p=0",
	]
	return float(subprocess.check_output(cmd).decode().strip())


def save_duration_json(basename, duration, output_dir):
	path = os.path.join(output_dir, f"{basename}.json")
	with open(path, "w") as f:
		json.dump({basename: duration}, f, indent="\t", ensure_ascii=False)


def set_audio_duration(filename, input_dir, output_dir, target_duration):
	path = os.path.join(input_dir, filename)
	basename = os.path.splitext(filename)[0]
	if os.path.exists(path) and not os.stat(path).st_size == 0:
		duration = get_audio_duration(filename, input_dir)
		if duration < target_duration:
			extend_silence(target_duration - duration, filename, input_dir)
			duration = target_duration
	else:
		create_silence(target_duration, filename, input_dir)
		duration = target_duration
	save_duration_json(basename, duration, output_dir)


def batch_set_audio_duration(batch, input_dir, output_dir, target_duration):
	for filename in batch:
		set_audio_duration(filename, input_dir, output_dir, target_duration)


def merge_duration_json(output_dir, input_dir):
	durations = {}
	total = 0
	files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
	for filename in files:
		path = os.path.join(input_dir, filename)
		with open(path, "r") as f:
			duration = json.load(f)
		for key, value in duration.items():
			durations[key] = value
			total += value
	path = os.path.join(output_dir, "durations.json")
	with open(path, "w") as f:
		json.dump(durations, f, indent="\t", ensure_ascii=False)
	path = os.path.join(output_dir, "total_duration.txt")
	with open(path, "w") as f:
		f.write(str(total))


def create_audio_list(audios, input_dir, output_dir, transition_duration):
	path = os.path.join(output_dir, "audio_list.txt")
	if transition_duration != 0:
		create_silence(transition_duration, "0000000.wav", input_dir)
	with open(path, "w") as f:
		for i, filename in enumerate(audios):
			abs_path = os.path.abspath(os.path.join(input_dir, filename))
			f.write(f"file '{abs_path}'\n")
			if transition_duration != 0 and i < len(audios) - 1:
				abs_path = os.path.abspath(os.path.join(input_dir, "0000000.wav"))
				f.write(f"file '{abs_path}'\n")


def render_audio(input_dir, render_dir):
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
		[f for f in os.listdir(DIRS["image_audio"]) if f.lower().endswith(".wav")]
	)
	workers = min(WORKERS, cpu_count())
	batches = split_batches(workers, audios)
	with Pool(processes=workers) as pool:
		args = [
			(
				batch,
				DIRS["image_audio"],
				DIRS["image_durations"],
				TARGET_DURATION,
			)
			for batch in batches
		]
		pool.starmap_async(batch_set_audio_duration, args).get()
	merge_duration_json(DIRS["merge"], DIRS["image_durations"])
	create_audio_list(audios, DIRS["image_audio"], DIRS["merge"], TRANSITION)
	render_audio(DIRS["merge"], DIRS["render"])
