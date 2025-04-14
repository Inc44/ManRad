from _0 import DIRS
import json
import os

if __name__ == "__main__":
	path = os.path.join(DIRS["merge"], "durations.json")
	with open(path) as f:
		durations = json.load(f)
	summed_durations = {}
	current_sum = 0
	current_prefix = None
	for key in sorted(durations.keys()):
		prefix = key[:4]
		suffix = key[4:]
		if current_prefix != prefix:
			if current_prefix:
				summed_durations[f"{current_prefix}999"] = current_sum
			current_prefix = prefix
			current_sum = 0
		if suffix == "000":
			summed_durations[key] = durations[key]
		else:
			current_sum += durations[key]
	if current_sum:
		summed_durations[f"{current_prefix}999"] = current_sum
	output_path = os.path.join(DIRS["merge"], "summed_durations.json")
	with open(output_path, "w") as f:
		json.dump(summed_durations, f, indent="\t", ensure_ascii=False)
