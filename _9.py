# Modify to make the silence created proportional to the possible duration of missing audio by reading the text length
# Make the transition duration work for scroll
# Fix missing audio
from _0 import DIRS
from _2 import split_batches
from multiprocessing import Pool, cpu_count
import json
import os
import shutil
import subprocess

TARGET_DURATION = 1
TRANSITION = 0
WORKERS = 6


def create_silence(duration, output_path):
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
		output_path,
	]
	subprocess.run(cmd)


def extend_silence(duration, input_path, output_path):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-i",
		input_path,
		"-af",
		f"apad=pad_dur={duration}",
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
		return 0


def save_duration_json(basename, duration, output_dir):
	output_path = os.path.join(output_dir, f"{basename}.json")
	with open(output_path, "w") as f:
		json.dump({basename: duration}, f, indent="\t", ensure_ascii=False)


def set_audio_duration(filename, input_dir, resized_dir, output_dir, target_duration):
	input_path = os.path.join(input_dir, filename)
	basename = os.path.splitext(filename)[0]
	resized_path = os.path.join(resized_dir, filename)
	if os.path.exists(input_path) and not os.stat(input_path).st_size == 0:
		duration = get_audio_duration(input_path)
		if duration < target_duration:
			extend_silence(target_duration - duration, input_path, resized_path)
			duration = target_duration
		else:
			shutil.copy(input_path, resized_path)
	else:
		create_silence(target_duration, resized_path)
		duration = target_duration
	save_duration_json(basename, duration, output_dir)


def batch_set_audio_duration(
	batch, input_dir, resized_dir, output_dir, target_duration
):
	for filename in batch:
		set_audio_duration(
			filename, input_dir, resized_dir, output_dir, target_duration
		)


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
	output_path = os.path.join(output_dir, "audio_list.txt")
	if transition_duration != 0:
		create_silence(transition_duration, "0000000.wav", input_dir)
	with open(output_path, "w") as f:
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
				TARGET_DURATION,
			)
			for batch in batches
		]
		pool.starmap_async(batch_set_audio_duration, args).get()
	merge_duration_json(DIRS["merge"], DIRS["image_durations"])
	create_audio_list(audios, DIRS["image_audio_resized"], DIRS["merge"], TRANSITION)
	render_audio(DIRS["merge"], DIRS["render"])
