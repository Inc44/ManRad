from _0 import DIRS
import json
import os

if __name__ == "__main__":
	with open(os.path.join(DIRS["merge"], "durations.json")) as f:
		durations = json.load(f)
	with open(os.path.join(DIRS["merge"], "gaps.json")) as f:
		gaps = json.load(f)
	transition_gaps = gaps.copy()
	for key in durations:
		if key not in transition_gaps:
			transition_gaps[key] = 0
	with open(os.path.join(DIRS["merge"], "transition_gaps.json"), "w") as f:
		json.dump(transition_gaps, f, indent="\t", ensure_ascii=False, sort_keys=True)
