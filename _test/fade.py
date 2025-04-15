import subprocess


def fade_images(input_path1, input_path2, output_path, target_fps, transition_duration):
	cmd = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-loop",
		"1",
		"-t",
		str(transition_duration),
		"-i",
		input_path1,
		"-loop",
		"1",
		"-t",
		str(transition_duration),
		"-i",
		input_path2,
		"-filter_complex",
		f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset=0",
		"-r",
		str(target_fps),
		"-frames:v",
		str(target_fps * transition_duration),
		"-c:v",
		"libx264",
		"-preset",
		"medium",
		output_path,
	]
	subprocess.run(cmd)
