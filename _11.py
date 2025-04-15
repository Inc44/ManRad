from _0 import DIRS
import json
import os

DELAY_SUFFIX = "000"
SUM_SUFFIX = "001"
TRANSITION_SUFFIX = "999"


if __name__ == "__main__":
	input_dir = DIRS["merge"]
	output_dir = DIRS["merge"]
	input_path = os.path.join(input_dir, "durations.json")
	output_path = os.path.join(output_dir, "page_durations.json")
	with open(input_path) as input_file:
		durations = json.load(input_file)
	page_durations = {}
	for key in durations.keys():
		value = durations[key]
		prefix = key[:4]
		suffix = key[4:]
		if suffix == DELAY_SUFFIX or suffix == TRANSITION_SUFFIX:
			page_durations[key] = value
		else:
			sum_key = prefix + SUM_SUFFIX
			current_sum = page_durations.get(sum_key, 0.0)
			page_durations[sum_key] = current_sum + value
	with open(output_path, "w") as output_file:
		json.dump(page_durations, output_file, indent="\t", ensure_ascii=False)
