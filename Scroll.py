from PIL import Image
from functools import lru_cache
import json
import math
import os
import subprocess


def combine_images(image_dir):
	image_files = sorted(
		[f for f in os.listdir(image_dir) if f.lower().endswith(".jpg")]
	)
	if not image_files:
		return None, 0
	with Image.open(os.path.join(image_dir, image_files[0])) as first_image:
		width = first_image.size[0]
	total_height = 0
	images = []
	for image_file in image_files:
		with Image.open(os.path.join(image_dir, image_file)) as img:
			images.append(img.copy())
			total_height += img.size[1]
	combined = Image.new("RGB", (width, total_height))
	y_offset = 0
	for img in images:
		combined.paste(img, (0, y_offset))
		y_offset += img.size[1]
		img.close()
	return combined, width


@lru_cache(maxsize=2048)
def ease(t):
	if t < 0.4:
		return 2.5 * t * t
	elif t < 0.8:
		return 0.4 + (t - 0.4) * 1.2
	else:
		normalized = (t - 0.8) / 0.2
		return 0.88 + (1 - math.pow(1 - normalized, 2)) * 0.12


def start_ffmpeg(output_file, width, height, fps):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		# "-loglevel",
		# "error",
		"-f",
		"rawvideo",
		"-c:v",
		"rawvideo",
		"-s",
		f"{width}x{height}",
		"-pix_fmt",
		"rgb24",
		"-r",
		str(fps),
		"-i",
		"-",
		# "-vf",
		# "mpdecimate",
		"-c:v",
		"h264_nvenc",
		"-preset",
		"p7",
		"-rc",
		"constqp",
		"-profile:v",
		"high",
		"-g",
		"999999",
		output_file,
	]
	return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def process_segment(
	image, width, height, start_y, deltas, duration, process, frame_idx, fps
):
	frame_count = round(duration * fps)
	if not deltas or sum(deltas) == 0:
		viewport = image.crop((0, int(start_y), width, int(start_y + height)))
		for _ in range(frame_count):
			process.stdin.write(viewport.tobytes())
		return frame_idx + frame_count, start_y
	positions = [start_y]
	for delta in deltas:
		positions.append(positions[-1] + delta)
	total_delta = sum(deltas)
	ratios = [delta / total_delta for delta in deltas]
	times = [0]
	for ratio in ratios:
		times.append(times[-1] + ratio * duration)
	for frame in range(frame_count):
		time = frame / frame_count * duration
		idx = 0
		while idx < len(times) - 1 and time > times[idx + 1]:
			idx += 1
		if idx >= len(deltas):
			y_pos = positions[-1]
		else:
			segment_time = times[idx + 1] - times[idx]
			if segment_time == 0:
				progress = 1.0
			else:
				progress = (time - times[idx]) / segment_time
			eased = ease(progress)
			delta_pos = positions[idx + 1] - positions[idx]
			y_pos = positions[idx] + eased * delta_pos
		y_pos = max(0, min(y_pos, image.height - height))
		viewport = image.crop((0, int(y_pos), width, int(y_pos + height)))
		process.stdin.write(viewport.tobytes())
	return frame_idx + frame_count, positions[-1] if positions else start_y


def create_video(img_dir, out_dir, out_file, intro_time=0.0):
	os.makedirs(out_dir, exist_ok=True)
	output_path = os.path.join(out_dir, out_file)
	image_files = sorted([f for f in os.listdir(img_dir) if f.lower().endswith(".jpg")])
	first_image_height = 0
	if image_files:
		with Image.open(os.path.join(img_dir, image_files[0])) as first_img:
			first_image_height = first_img.size[1]
	offset_val = -first_image_height / 2
	image, width = combine_images(img_dir)
	if not image:
		return 0
	with open(os.path.join(out_dir, "delta_durations.json"), "r") as file:
		deltas = json.load(file)
	with open(os.path.join(out_dir, "audio_durations.json"), "r") as file:
		durations = json.load(file)
	audio_files = sorted(deltas.keys())
	fps = 60
	height = 1350
	process = start_ffmpeg(output_path, width, height, fps)
	frame_count = 0
	intro_frames = round(intro_time * fps)
	if intro_frames > 0:
		viewport = image.crop((0, 0, width, height))
		for _ in range(intro_frames):
			process.stdin.write(viewport.tobytes())
		frame_count += intro_frames
	y_pos = 0
	offset_remain = offset_val
	for audio in audio_files:
		delta = deltas[audio]
		duration = durations[audio]
		if offset_remain < 0:
			scroll_speed = delta / max(duration, 0.001)
			hold_time = min(
				duration, abs(offset_remain) / max(abs(scroll_speed), 0.001)
			)
			if hold_time > 0:
				hold_frames = round(hold_time * fps)
				top_view = image.crop((0, 0, width, height))
				for _ in range(hold_frames):
					process.stdin.write(top_view.tobytes())
				frame_count += hold_frames
				remain_time = duration - hold_time
				if remain_time > 0:
					reduced_delta = delta * (remain_time / duration)
					frame_count, y_pos = process_segment(
						image,
						width,
						height,
						y_pos,
						[reduced_delta],
						remain_time,
						process,
						frame_count,
						fps,
					)
				used_offset = delta * (hold_time / duration)
				offset_remain += used_offset
			else:
				frame_count, y_pos = process_segment(
					image,
					width,
					height,
					y_pos,
					[delta],
					duration,
					process,
					frame_count,
					fps,
				)
				offset_remain += delta
		else:
			frame_count, y_pos = process_segment(
				image,
				width,
				height,
				y_pos,
				[delta],
				duration,
				process,
				frame_count,
				fps,
			)
	process.stdin.close()
	process.wait()
	image.close()
	return frame_count


if __name__ == "__main__":
	create_video("img", "output", "scroll.mkv")
