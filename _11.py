from _0 import DIRS
import json
import os


if __name__ == "__main__":
	input_path = os.path.join(DIRS["merge"], "durations.json")
	output_path = os.path.join(DIRS["merge"], "page_durations.json")
	with open(input_path) as f:
		durations = json.load(f)
	page_durations = {}
	current_page = 0.0
	current_prefix = None
	keys = sorted(durations.keys())
	keys_length = len(keys)
	start = 0
	if keys_length > 0:
		key = keys[0]
		prefix = key[:4]
		suffix = key[4:]
		if suffix == "000":
			delay_key = f"{prefix}d"
			page_durations[delay_key] = float(durations[key])
			start = 1
			current_prefix = prefix
	for i in range(start, keys_length):
		key = keys[i]
		prefix = key[:4]
		suffix = key[4:]
		if prefix != current_prefix:
			if current_prefix is not None:
				if current_page > 0.0:
					static_key = f"{current_prefix}s"
					page_durations[static_key] = current_page
			current_prefix = prefix
			current_page = 0.0
		if suffix == "000":
			transition_key = f"{int(prefix) - 1:04d}t"
			page_durations[transition_key] = float(durations[key])
		else:
			current_page = current_page + float(durations[key])
	if current_prefix is not None:
		if current_page > 0.0:
			last_static_key = f"{current_prefix}s"
			page_durations[last_static_key] = current_page
	with open(output_path, "w") as f:
		json.dump(page_durations, f, indent="\t", ensure_ascii=False)
