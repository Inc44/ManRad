from scipy.io.wavfile import write
import cv2
import librosa
import numpy as np
import os
import shutil
import subprocess


def make_dir(p):
	if not os.path.exists(p):
		os.makedirs(p)


def clear_dir(p):
	if os.path.exists(p):
		shutil.rmtree(p)
	os.makedirs(p)


def make_silence(p, s, r=24000):
	samples = int(s * r)
	silence = np.zeros(samples, dtype=np.int16)
	write(p, r, silence)


def ffmpeg(args):
	base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
	subprocess.run(base + args, check=True)


def make_seq(src, dst, gap=0.5, steps=15):
	img_dir = os.path.join(src, "img")
	aud_dir = os.path.join(src, "wav")
	if not os.path.exists(img_dir):
		return
	clear_dir(dst)
	frame_dir = os.path.join(dst, "frames")
	os.makedirs(frame_dir)
	imgs = sorted([f for f in os.listdir(img_dir) if f.lower().endswith(".jpg")])
	if not imgs:
		return
	auds = {}
	if os.path.exists(aud_dir):
		for f in os.listdir(aud_dir):
			if f.lower().endswith(".wav"):
				base = os.path.splitext(f)[0]
				auds[base] = os.path.join(aud_dir, f)
	images = []
	sounds = []
	default_rate = 24000
	rate_found = False
	for img_f in imgs:
		img_p = os.path.join(img_dir, img_f)
		img = cv2.imread(img_p)
		if img is None:
			continue
		img = cv2.resize(img, (900, 1350))
		images.append(img)
		base = os.path.splitext(img_f)[0]
		if base in auds:
			aud_p = auds[base]
			dur = librosa.get_duration(path=aud_p)
			if not rate_found:
				_, rate = librosa.load(aud_p, sr=None)
				rate_found = True
			if dur < 1.0:
				extended_path = os.path.join(dst, f"{base}_extended.wav")
				silence_path = os.path.join(dst, f"{base}_silence.wav")
				make_silence(silence_path, 1.0 - dur, rate)
				concat_list = os.path.join(dst, f"{base}_concat.txt")
				with open(concat_list, "w") as f:
					f.write(f"file '{os.path.abspath(aud_p)}'\n")
					f.write(f"file '{os.path.abspath(silence_path)}'\n")
				ffmpeg(
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
				sounds.append(extended_path)
			else:
				sounds.append(aud_p)
		else:
			silence_path = os.path.join(dst, f"{base}_silence.wav")
			make_silence(silence_path, 1.0, default_rate if not rate_found else rate)
			sounds.append(silence_path)
	if not images:
		return
	sil_path = os.path.join(dst, "silent.wav")
	make_silence(sil_path, gap, default_rate if not rate_found else rate)
	vid_list = []
	aud_list = []
	count = 0
	for i, (img, aud) in enumerate(zip(images, sounds)):
		dur = librosa.get_duration(path=aud)
		fname = os.path.join(frame_dir, f"{count:08d}.jpg")
		cv2.imwrite(fname, img)
		vid_list.append((fname, gap / steps))
		vid_list.append((fname, dur - gap / steps))
		count += 1
		aud_list.append(aud)
		if i < len(images) - 1:
			next_img = images[i + 1]
			aud_list.append(sil_path)
			for j in range(1, steps + 1):
				ratio = j / (steps + 1)
				blend = cv2.addWeighted(img, 1 - ratio, next_img, ratio, 0)
				fname = os.path.join(frame_dir, f"{count:08d}.jpg")
				cv2.imwrite(fname, blend)
				vid_list.append((fname, gap / steps))
				count += 1
	frames_file = os.path.join(dst, "frames.txt")
	with open(frames_file, "w") as f:
		for path, dur in vid_list:
			f.write(f"file '{os.path.abspath(path)}'\n")
			f.write(f"duration {dur:.8f}\n")
	audio_file = os.path.join(dst, "audio.txt")
	with open(audio_file, "w") as a:
		for path in aud_list:
			a.write(f"file '{os.path.abspath(path)}'\n")
	vid_out = os.path.join(dst, "video.mp4")
	ffmpeg(
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
			0,
			vid_out,
		]
	)
	aud_out = os.path.join(dst, "audio.opus")
	ffmpeg(
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
			aud_out,
		]
	)
	final_out = os.path.join(dst, "Man.mp4")
	ffmpeg(["-i", vid_out, "-i", aud_out, "-c", "copy", final_out])
	final_path = os.path.join(src, "Man.mp4")
	shutil.move(final_out, final_path)
	shutil.rmtree(dst)


if __name__ == "__main__":
	import sys

	if len(sys.argv) > 1:
		src = sys.argv[1]
		tmp = "temp"
		make_dir(tmp)
		make_seq(src, tmp)
