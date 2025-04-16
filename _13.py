import config
import json
import os

if __name__ == "__main__":
	dirs = config.DIRS
	merged_durations_filename = config.MERGED_DURATIONS_FILENAME
	merged_gaps_filename = config.MERGED_GAPS_FILENAME
	transition_gaps_filename = config.TRANSITION_GAPS_FILENAME
	merge_dir = dirs["merge"]
	durations_path = os.path.join(merge_dir, merged_durations_filename)
	gaps_path = os.path.join(merge_dir, merged_gaps_filename)
	with open(durations_path) as f:
		durations = json.load(f)
	with open(gaps_path) as f:
		gaps = json.load(f)
	duration_keys = sorted(durations.keys())
	gaps_keys = sorted(gaps.keys())
	transition_gaps = {}
	for i in range(len(duration_keys)):
		duration_key = duration_keys[i]
		gap_key = gaps_keys[i]
		transition_gaps[duration_key] = gaps[gap_key]
	output_path = os.path.join(merge_dir, transition_gaps_filename)
	with open(output_path, "w") as f:
		json.dump(transition_gaps, f, indent="\t", ensure_ascii=False, sort_keys=True)
