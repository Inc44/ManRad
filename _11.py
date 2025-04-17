import config
import json
import os


def page_durations(
	delay_suffix,
	dirs,
	merged_durations_filename,
	page_durations_filename,
	prefix_length,
	sum_suffix,
	transition_suffix,
):
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


if __name__ == "__main__":
	page_durations(
		config.DELAY_SUFFIX,
		config.DIRS,
		config.MERGED_DURATIONS_FILENAME,
		config.PAGE_DURATIONS_FILENAME,
		config.PREFIX_LENGTH,
		config.SUM_SUFFIX,
		config.TRANSITION_SUFFIX,
	)
