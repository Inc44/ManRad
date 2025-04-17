import config
import os


def initialize(dirs):
	for dir_path in dirs.values():
		os.makedirs(dir_path, exist_ok=True)


if __name__ == "__main__":
	initialize(config.DIRS)
