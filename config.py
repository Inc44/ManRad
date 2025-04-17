import os

DIRS = {
	"image": "image",
	"image_audio": "image_audio",
	"image_audio_resized": "image_audio_resized",
	"image_boxed": "image_boxed",
	"image_crops": "image_crops",
	"image_durations": "image_durations",
	"image_gaps": "image_gaps",
	"image_grouped": "image_grouped",
	"image_resized": "image_resized",
	"image_resized_fit": "image_resized_fit",
	"image_resized_fit_fade": "image_resized_fit_fade",
	"image_text": "image_text",
	"merge": "merge",
	"render": "render",
	"temp": "temp",
}
SOURCE_PATHS = [
	"Kage_no_Jitsuryokusha_ni_Naritakute_",  # Kotatsu CBZ or DIR
	"Kage_no_Jitsuryokusha_ni_Naritakute_.zip",  # Kotatsu ZIP
	"The Eminence in Shadow_001",  # HakuNeko Images
	"The Eminence in Shadow_002",  # HakuNeko CBZ
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ARCHIVE_EXTENSIONS = {".cbz", ".zip"}
OUTPUT_IMAGE_EXTENSION = ".jpg"
AUDIO_OUTPUT_EXTENSION = ".wav"
PREFIX_LENGTH = 4
OUTPUT_FILENAME_LENGTH = 4
CROP_SUFFIX_LENGTH = 3
FRAME_SUFFIX_LENGTH = 3
DELAY_SUFFIX = "000"
SUM_SUFFIX = "001"
TRANSITION_SUFFIX = "999"
DELETED_IMAGES_LIST_FILENAME = "deleted_images.json"
ALL_IMAGES_LIST_FILENAME = "images.json"
KEPT_IMAGES_LIST_FILENAME = "kept_images.json"
MERGED_GAPS_FILENAME = "gaps.json"
TOTAL_GAPS_FILENAME = "total_gaps.txt"
MERGED_DURATIONS_FILENAME = "durations.json"
TOTAL_DURATION_FILENAME = "total_duration.txt"
PAGE_DURATIONS_FILENAME = "page_durations.json"
TRANSITION_GAPS_FILENAME = "transition_gaps.json"
AUDIO_CONCAT_LIST_FILENAME = "audio_list.txt"
FADE_VIDEO_LIST_FILENAME = "fade_video_list.txt"
COST_FILENAME = "cost.json"
TARGET_WIDTH = 900
TARGET_HEIGHT = 1280
MARGIN = 16
MAX_DISTANCE = 32
HEIGHT_RANGE = 96
LANGUAGE = "English"
MAX_TOKENS = 2000
TEXT_MIN_SIZE = 13
AUDIO_MIN_SIZE = 78
REFERENCE_AUDIO = "_reference/reference_audio.flac"
REFERENCE_TEXT = "_reference/reference_text.txt"
SAMPLE_RATE = 48000
FISH_TEMPERATURE = 0.1
ENCODING_NAME = "cl100k_base"
MODEL = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
PAUSE = 10
PROMPT = f'Proofread this text in {LANGUAGE} but only fix grammar without any introductory phrases or additional commentary. If no readable text is found, the text content is empty. Return JSON: [{{"text": "text content"}}, ...]'
RETRIES = 3
TEMPERATURE = 0.0
TEMPERATURE_STEP = 0.2
CONCURRENT_REQUESTS = 60
API_ENDPOINTS = [
	"http://localhost:8080/v1/tts",  # Fish
	"http://localhost:8880/v1/audio/speech",  # Kokoro
	"https://api.deepinfra.com/v1/openai/chat/completions",  # DeepInfra
	"https://api.lemonfox.ai/v1/audio/speech",  # Lemon
	"https://api.openai.com/v1/audio/speech",  # OpenAI
]
API_KEYS = [
	"not-needed",  # Kokoro
	os.environ.get("DEEPINFRA_API_KEY"),  # DeepInfra
	os.environ.get("GEMINI_API_KEY"),  # Gemini
	os.environ.get("LEMON_API_KEY"),  # Lemon
	os.environ.get("MELO_API_KEY"),  # Melo
	os.environ.get("MISTRAL_API_KEY"),  # Mistral
	os.environ.get("OPENAI_API_KEY"),  # OpenAI
]
INSTRUCTIONS = [
	"",
	"Speak in an emotive and friendly tone... Read only if the text is in Russian",
	"Speak with intonation and emotions in the given sentences from the intense manga.",
]
MODELS = [
	"gpt-4o-mini-tts",  # OpenAI
	"tts-1",  # Kokoro, Lemon, OpenAI
	"tts-1-hd",  # OpenAI
]
RESPONSE_FORMAT = [
	"mp3",  # OpenAI
	"wav",  # Kokoro, Lemon, OpenAI
]
VOICES = [
	"am_onyx",  # Kokoro
	"ash",  # OpenAI
	"onyx",  # Lemon, OpenAI
	"sage",  # OpenAI
]
COST_DEEPINFRA = (0.08, 0.30)
COST_GEMINI = (0.10, 0.40)
COST_GROQ = (0.90, 0.90)
COST_OPENAI = (5.00, 15.00)
COST_TTS = 15.0
WORKERS = 6
TARGET_FPS = 60
AUDIO_DELAY_DURATION = 1
AUDIO_TARGET_SEGMENT_DURATION = 1
AUDIO_TRANSITION_DURATION = 0.5
VIDEO_HOLD_DURATION = 2
DELAY_PERCENT = 0.42
AUDIO = "audio.opus"
SCROLL_VIDEO = "scroll_video.mkv"
FADE_VIDEO = "fade_video.mkv"
MEDIA = "ManRad.mkv"
