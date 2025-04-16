import config
import json
import os

if __name__ == "__main__":
	delay_suffix = config.DELAY_SUFFIX
	dirs = config.DIRS
	merged_durations_filename = config.MERGED_DURATIONS_FILENAME
	page_durations_filename = config.PAGE_DURATIONS_FILENAME
	prefix_length = config.PREFIX_LENGTH
	sum_suffix = config.SUM_SUFFIX
	transition_suffix = config.TRANSITION_SUFFIX
	input_dir = dirs["merge"]
	output_dir = dirs["merge"]
	input_path = os.path.join(input_dir, merged_durations_filename)
	output_path = os.path.join(output_dir, page_durations_filename)
	with open(input_path) as f:
		durations = json.load(f)
	page_durations = {}
	for key in durations.keys():
		value = durations[key]
		prefix = key[:prefix_length]
		suffix = key[prefix_length:]
		if suffix == delay_suffix or suffix == transition_suffix:
			page_durations[key] = value
		else:
			sum_key = prefix + sum_suffix
			current_sum = page_durations.get(sum_key, 0.0)
			page_durations[sum_key] = current_sum + value
	with open(output_path, "w") as f:
		json.dump(page_durations, f, indent="\t", ensure_ascii=False, sort_keys=True)
