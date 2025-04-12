from manrad0 import DIRS
from manrad1 import batches_distribute
from multiprocessing import Pool, cpu_count
import json
import os
import subprocess

CORES = 6
TARGET_DURATION = 1
TRANSITION_DURATION = 0


# Modify to make the silence created proportional to the possible duration of missing audio by reading the text length
# Make the transition duration work for scroll
def silence_create(duration, filename, input_dir):
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
		duration,
		path,
	]
	subprocess.run(cmd)


def silence_extend(duration, filename, input_dir):
	path = os.path.join(input_dir, filename)
	basename, _ = os.path.splitext(filename)
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


def duration_get(filename, input_dir):
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


def audio_json(basename, duration, output_dir_audio):
	path = os.path.join(output_dir_audio, f"{basename}.json")
	audio = {}
	audio[basename] = duration
	with open(path, "w") as f:
		json.dump(audio, f, indent="\t", ensure_ascii=False)


def duration_set(filename, input_dir, output_dir_audio, target_duration):
	path = os.path.join(input_dir, filename)
	basename, _ = os.path.splitext(filename)
	if os.path.exists(path) and not os.stat(path).st_size == 0:
		duration = duration_get(filename, input_dir)
		if duration < target_duration:
			silence_extend(target_duration - duration, filename, input_dir)
			duration = target_duration
	else:
		silence_create(target_duration, filename, input_dir)
		duration = target_duration
	audio_json(basename, duration, output_dir_audio)


def batch_duration(batch, input_dir, output_dir_audio, target_duration):
	for filename in batch:
		duration_set(filename, input_dir, output_dir_audio, target_duration)


def audio_json_merge(output_dir, output_dir_crops_durations):
	audios = {}
	total = 0
	jsons = [f for f in os.listdir(output_dir_crops_durations) if f.endswith(".json")]
	for filename in jsons:
		path = os.path.join(output_dir_crops_durations, filename)
		with open(path, "r") as f:
			audio = json.load(f)
		for key, value in audio.items():
			audios[key] = value
			total += value
	path = os.path.join(output_dir, "audios.json")
	with open(path, "w") as f:
		json.dump(audios, f, indent="\t", ensure_ascii=False)
	path = os.path.join(output_dir, "total_duration.txt")
	with open(path, "w") as f:
		f.write(str(total))


def audio_list(audios, input_dir, output_dir, transition_duration):
	path = os.path.join(output_dir, "audio_list.txt")
	if transition_duration != 0:
		silence_create(transition_duration, "0000000.wav", input_dir)
	with open(path, "w") as f:
		for i, filename in enumerate(audios):
			path = os.path.join(input_dir, filename)
			f.write(f"file '{path}'\n")
			if transition_duration != 0 and i < len(audios) - 1:
				path = os.path.join(input_dir, "0000000.wav")
				f.write(f"file '{path}'\n")


def audio_render(input_dir, render_dir):
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
	# Render Audio
	audios = sorted(
		[f for f in os.listdir(DIRS["img_audio"]) if f.lower().endswith(".wav")]
	)
	cores = min(CORES, cpu_count())
	batches = batches_distribute(cores, audios)
	with Pool(processes=cores) as pool:
		args = [
			(
				batch,
				DIRS["img_audio"],
				DIRS["img_crops_durations"],
				TARGET_DURATION,
			)
			for batch in batches
		]
		pool.starmap_async(batch_duration, args).get()
	audio_json_merge(DIRS["merges"], DIRS["img_crops_durations"])
	audio_list(audios, DIRS["img_audio"], DIRS["merges"], TRANSITION_DURATION)
	audio_render(DIRS["merges"], DIRS["render"])
