from glob import glob
import json
import librosa
import numpy as np
import os
import soundfile as sf
import subprocess


def create_silence(duration=1.0, sr=24000):
	return np.zeros(int(sr * duration))


def extend_audio_with_silence(audio, sr, target_duration=1.0):
	current_duration = len(audio) / sr
	if current_duration >= target_duration:
		return audio
	silence_duration = target_duration - current_duration
	silence = create_silence(silence_duration, sr)
	extended_audio = np.concatenate((audio, silence))
	return extended_audio


def process_audio_file(jpg_path, wav_dir, target_duration=1.0):
	base_name = os.path.splitext(os.path.basename(jpg_path))[0]
	wav_path = os.path.join(wav_dir, f"{base_name}.wav")
	sr = 24000
	if os.path.exists(wav_path):
		audio, sr = librosa.load(wav_path, sr=None)
		duration = len(audio) / sr
		if duration < target_duration:
			extended_audio = extend_audio_with_silence(audio, sr, target_duration)
			sf.write(wav_path, extended_audio, sr)
			duration = target_duration
	else:
		silence = create_silence(target_duration, sr)
		sf.write(wav_path, silence, sr)
		duration = target_duration
	return base_name, duration


def process_audio_files(img_dir, wav_dir, target_duration=1.0):
	os.makedirs(wav_dir, exist_ok=True)
	jpg_files = sorted(glob(os.path.join(img_dir, "*.jpg")))
	jpg_basenames = []
	audio_durations = {}
	for jpg_path in jpg_files:
		base_name, duration = process_audio_file(jpg_path, wav_dir, target_duration)
		jpg_basenames.append(base_name)
		audio_durations[base_name] = duration
	return jpg_basenames, audio_durations


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
	final_audio_file = os.path.join(output_dir, "merged_audio.opus")
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
	durations_list = [audio_durations[base_name] for base_name in jpg_basenames]
	with open(json_path, "w") as f:
		json.dump(durations_list, f, indent="\t")
	return json_path


def process_and_merge_audio(
	img_directory,
	wav_directory,
	output_directory,
	target_duration=1.0,
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
	final_audio_path = merge_audio_files(audio_list_file, output_directory)
	duration_json_path = save_audio_durations(
		jpg_basenames, audio_durations, output_directory
	)
	return final_audio_path, duration_json_path


if __name__ == "__main__":
	img_directory = "img"
	wav_directory = "wav"
	output_directory = "output"
	use_transition = False
	target_duration = 1.0
	process_and_merge_audio(
		img_directory, wav_directory, output_directory, target_duration, use_transition
	)
