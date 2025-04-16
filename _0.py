import config
import os

if __name__ == "__main__":
	dirs = config.DIRS
	for dir_path in dirs.values():
		os.makedirs(dir_path, exist_ok=True)
