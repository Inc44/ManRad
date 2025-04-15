from melo.api import TTS
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
import glob
import json
import multiprocessing
import os
import sys
import threading
import time
import torch

GLOBAL_MODEL = None
GLOBAL_CONVERTER = None
SOURCE_SE = None
TARGET_SE = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MAX_WORKERS = min(multiprocessing.cpu_count(), 12)
GPU_WORKERS = 1 if torch.cuda.is_available() else 0
STOP_PROCESSING = False
TIMEOUT = 999


def read_json(path):
	with open(path, encoding="utf-8") as f:
		data = json.load(f)
	if isinstance(data, list):
		return " ".join(
			item.get("text", "") for item in data if isinstance(item, dict)
		).strip()
	if isinstance(data, dict):
		return data.get("text", "").strip()
	return ""


def clean_text(path):
	return read_json(path).capitalize().replace("\n", " ")


def check_file(path, min_size=256):
	return os.path.exists(path) and os.path.getsize(path) >= min_size


def load_models(language="EN_NEWEST", reference_audio=None):
	global GLOBAL_MODEL, GLOBAL_CONVERTER, SOURCE_SE, TARGET_SE, DEVICE
	GLOBAL_MODEL = TTS(language=language, device=DEVICE)
	if reference_audio:
		GLOBAL_CONVERTER = ToneColorConverter(
			"checkpoints_v2/converter/config.json", device=DEVICE
		)
		GLOBAL_CONVERTER.load_ckpt("checkpoints_v2/converter/checkpoint.pth")
		target_status = se_extractor.get_se(reference_audio, GLOBAL_CONVERTER, vad=True)
		if target_status and target_status[0] is not None:
			TARGET_SE = target_status[0]
		speaker_ids = GLOBAL_MODEL.hps.data.spk2id
		speaker_key = list(speaker_ids.keys())[0].lower().replace("_", "-")
		source_path = f"checkpoints_v2/base_speakers/ses/{speaker_key}.pth"
		if os.path.exists(source_path):
			SOURCE_SE = torch.load(source_path, map_location=DEVICE)


def process_audio(file_queue, result_queue, language, speed, reference_audio, wav_dir):
	global GLOBAL_MODEL, GLOBAL_CONVERTER, SOURCE_SE, TARGET_SE, DEVICE, STOP_PROCESSING
	if GLOBAL_MODEL is None:
		load_models(language, reference_audio)
	speaker_ids = GLOBAL_MODEL.hps.data.spk2id
	speaker_key = list(speaker_ids.keys())[0]
	speaker_id = speaker_ids[speaker_key]
	while not STOP_PROCESSING:
		file_path = None
		file_path = file_queue.get(timeout=2)
		if file_path is None:
			break
		name = os.path.splitext(os.path.basename(file_path))[0]
		out_path = os.path.join(wav_dir, f"{name}.wav")
		if check_file(out_path):
			result_queue.put(
				{"file": file_path, "audio": out_path, "status": "skipped"}
			)
			continue
		text = clean_text(file_path)
		if not text:
			result_queue.put({"file": file_path, "audio": out_path, "status": "failed"})
			continue
		text = text.strip()[:4096]
		if not reference_audio or TARGET_SE is None or SOURCE_SE is None:
			GLOBAL_MODEL.tts_to_file(text, speaker_id, out_path, speed=speed)
			status = "created" if check_file(out_path) else "failed"
			result_queue.put({"file": file_path, "audio": out_path, "status": status})
			continue
		tmp_path = f"{os.path.splitext(out_path)[0]}_tmp.wav"
		GLOBAL_MODEL.tts_to_file(text, speaker_id, tmp_path, speed=speed)
		if not check_file(tmp_path):
			if os.path.exists(tmp_path):
				os.remove(tmp_path)
			result_queue.put({"file": file_path, "audio": out_path, "status": "failed"})
			continue
		encode_message = "@MyShell"
		GLOBAL_CONVERTER.convert(
			audio_src_path=tmp_path,
			src_se=SOURCE_SE,
			tgt_se=TARGET_SE,
			output_path=out_path,
			message=encode_message,
		)
		if os.path.exists(tmp_path):
			os.remove(tmp_path)
		status = "created" if check_file(out_path) else "failed"
		result_queue.put({"file": file_path, "audio": out_path, "status": status})


def gather_results(result_queue, total_files, completion_event):
	processed = 0
	last_report_time = time.time()
	results = []
	while processed < total_files:
		result = None
		result = result_queue.get(timeout=1)
		results.append(result)
		processed += 1
		if completion_event.is_set():
			break
		current_time = time.time()
		if processed % 10 == 0 or current_time - last_report_time > 5:
			last_report_time = current_time
	completion_event.set()
	return results


def process_directory(base_path, reference_audio=None, language="EN_NEWEST", speed=1.0):
	global STOP_PROCESSING
	if not os.path.isdir(base_path):
		return []
	json_dir = os.path.join(base_path, "json")
	wav_dir = os.path.join(base_path, "wav")
	if not os.path.isdir(json_dir):
		return []
	os.makedirs(wav_dir, exist_ok=True)
	files = sorted(glob.glob(os.path.join(json_dir, "*.json")))
	if not files:
		return []
	worker_count = 1 if reference_audio else MAX_WORKERS
	if DEVICE == "cuda":
		worker_count = max(1, GPU_WORKERS)
	file_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	completion_event = multiprocessing.Event()
	for file_path in files:
		file_queue.put(file_path)
	for _ in range(worker_count):
		file_queue.put(None)
	load_models(language, reference_audio)
	workers = []
	for _ in range(worker_count):
		process = multiprocessing.Process(
			target=process_audio,
			args=(file_queue, result_queue, language, speed, reference_audio, wav_dir),
		)
		process.daemon = True
		process.start()
		workers.append(process)

	def timeout_handler():
		global STOP_PROCESSING
		STOP_PROCESSING = True
		completion_event.set()
		for p in workers:
			if p.is_alive():
				p.terminate()

	timeout_timer = threading.Timer(
		TIMEOUT * len(files) // worker_count, timeout_handler
	)
	timeout_timer.daemon = True
	timeout_timer.start()
	collector_thread = threading.Thread(
		target=lambda: gather_results(result_queue, len(files), completion_event)
	)
	collector_thread.daemon = True
	collector_thread.start()
	start_time = time.time()
	while not completion_event.is_set() and time.time() - start_time < TIMEOUT:
		if all(not p.is_alive() for p in workers):
			completion_event.set()
		time.sleep(0.5)
	timeout_timer.cancel()
	for process in workers:
		if process.is_alive():
			process.terminate()
			process.join(1)
	for process in workers:
		process.close()
	if collector_thread.is_alive():
		collector_thread.join(2)
	results = []
	while True:
		item = None
		item = result_queue.get_nowait()
		if item:
			results.append(item)


def run():
	if len(sys.argv) <= 1:
		return
	base_path = sys.argv[1]
	if not os.path.exists(base_path):
		return
	language = sys.argv[3] if len(sys.argv) > 3 else "EN_NEWEST"
	speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
	reference_audio = None
	if len(sys.argv) > 2 and sys.argv[2] not in ["None", ""]:
		reference_audio = sys.argv[2]
		if not os.path.exists(reference_audio):
			reference_audio = None
	process_directory(base_path, reference_audio, language, speed)
	os._exit(0)


if __name__ == "__main__":
	multiprocessing.set_start_method("spawn", force=True)
	run()
