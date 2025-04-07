from glob import glob
import json
import librosa
import multiprocessing
import numpy as np
import os
import soundfile as sf
import subprocess


def create_silence(duration=0.5, sr=24000):
	return np.zeros(int(sr * duration))


def extend_audio_with_silence(audio, sr, target_duration=0.5):
	current_duration = len(audio) / sr
	if current_duration >= target_duration:
		return audio
	silence_duration = target_duration - current_duration
	silence = create_silence(silence_duration, sr)
	extended_audio = np.concatenate((audio, silence))
	return extended_audio


def process_audio_file(jpg_path, wav_dir, target_duration=0.5):
	base_name = os.path.splitext(os.path.basename(jpg_path))[0]
	wav_path = os.path.join(wav_dir, f"{base_name}.wav")
	sr = 24000
	if os.path.exists(wav_path) and not os.path.getsize(wav_path) == 0:
		cmd = [
			"ffprobe",
			"-i",
			wav_path,
			"-show_entries",
			"format=duration",
			"-v",
			"quiet",
			"-of",
			"csv=p=0",
		]
		duration = float(subprocess.check_output(cmd).decode().strip())
		if duration < target_duration:
			audio, sr = librosa.load(wav_path, sr=None)
			extended_audio = extend_audio_with_silence(audio, sr, target_duration)
			sf.write(wav_path, extended_audio, sr)
			duration = target_duration
	else:
		silence = create_silence(target_duration, sr)
		sf.write(wav_path, silence, sr)
		duration = target_duration
	return base_name, duration


def process_audio_file_batch(jpg_files_batch, wav_dir, target_duration=0.5):
	results = {}
	base_names = []
	for jpg_path in jpg_files_batch:
		base_name, duration = process_audio_file(jpg_path, wav_dir, target_duration)
		base_names.append(base_name)
		results[base_name] = duration
	return base_names, results


def distribute_files_to_workers(files, num_workers):
	batches = [[] for _ in range(num_workers)]
	for i, filename in enumerate(files):
		worker_idx = i % num_workers
		batches[worker_idx].append(filename)
	return batches


def process_audio_files(img_dir, wav_dir, target_duration=0.5):
	os.makedirs(wav_dir, exist_ok=True)
	jpg_files = sorted(glob(os.path.join(img_dir, "*.jpg")))
	available_cores = multiprocessing.cpu_count()
	optimal_workers = min(6, available_cores)
	all_base_names = []
	all_audio_durations = {}
	if len(jpg_files) <= optimal_workers:
		base_names, audio_durations = process_audio_file_batch(
			jpg_files, wav_dir, target_duration
		)
		all_base_names.extend(base_names)
		all_audio_durations.update(audio_durations)
	else:
		file_batches = distribute_files_to_workers(jpg_files, optimal_workers)
		with multiprocessing.Pool(processes=optimal_workers) as pool:
			tasks = []
			for batch in file_batches:
				if batch:
					task = pool.apply_async(
						process_audio_file_batch, (batch, wav_dir, target_duration)
					)
					tasks.append(task)
			for task in tasks:
				base_names, audio_durations = task.get()
				all_base_names.extend(base_names)
				all_audio_durations.update(audio_durations)
	all_base_names.sort()
	return all_base_names, all_audio_durations


def create_transition_silence(output_dir, transition_duration=0.5, sr=24000):
	transition_path = os.path.join(output_dir, "transition_silence.wav")
	silence = create_silence(transition_duration, sr)
	sf.write(transition_path, silence, sr)
	return transition_path


def create_audio_list_file(wav_dir, jpg_basenames, output_dir, use_transition=False):
	os.makedirs(output_dir, exist_ok=True)
	list_file_path = os.path.join(output_dir, "audio_list.txt")
	with open(list_file_path, "w") as f:
		for i, base_name in enumerate(jpg_basenames):
			wav_file = os.path.join(wav_dir, f"{base_name}.wav")
			if os.path.exists(wav_file):
				abs_path = os.path.abspath(wav_file)
				f.write(f"file '{abs_path}'\n")
				if use_transition and i < len(jpg_basenames) - 1:
					transition_path = os.path.abspath(
						os.path.join(output_dir, "transition_silence.wav")
					)
					f.write(f"file '{transition_path}'\n")
	return list_file_path


def merge_audio_files(audio_list_file, output_dir):
	final_audio_file = os.path.join(output_dir, "audio.opus")
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
		audio_list_file,
		"-c:a",
		"libopus",
		"-vbr",
		"on",
		"-compression_level",
		"10",
		"-frame_duration",
		"60",
		final_audio_file,
	]
	subprocess.run(cmd, check=True)
	return final_audio_file


def save_audio_durations(jpg_basenames, audio_durations, output_dir):
	json_path = os.path.join(output_dir, "audio_durations.json")
	named_durations = {
		base_name: audio_durations[base_name] for base_name in jpg_basenames
	}
	with open(json_path, "w") as f:
		json.dump(named_durations, f, indent="\t", ensure_ascii=False)
	return json_path


def process_and_merge_audio(
	img_directory,
	wav_directory,
	output_directory,
	target_duration=0.5,
	use_transition=False,
):
	os.makedirs(wav_directory, exist_ok=True)
	os.makedirs(output_directory, exist_ok=True)
	jpg_basenames, audio_durations = process_audio_files(
		img_directory, wav_directory, target_duration
	)
	if use_transition and len(jpg_basenames) > 1:
		create_transition_silence(output_directory)
	audio_list_file = create_audio_list_file(
		wav_directory, jpg_basenames, output_directory, use_transition
	)
	duration_json_path = save_audio_durations(
		jpg_basenames, audio_durations, output_directory
	)
	final_audio_path = merge_audio_files(audio_list_file, output_directory)
	return duration_json_path, final_audio_path


if __name__ == "__main__":
	multiprocessing.freeze_support()
	img_directory = "crops"
	wav_directory = "wav"
	output_directory = "output"
	use_transition = False
	target_duration = 0.5
	process_and_merge_audio(
		img_directory, wav_directory, output_directory, target_duration, use_transition
	)
