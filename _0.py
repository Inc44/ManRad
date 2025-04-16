from config import DIRS
import os


if __name__ == "__main__":
	for dir_path in DIRS.values():
		os.makedirs(dir_path, exist_ok=True)
