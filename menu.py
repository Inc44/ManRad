from main import (
	initialize,
	prepare,
	resize_to_width,
	lists,
	crops,
	texts,
	costs,
	fish_tts,
	openai_tts,
	audio,
	resize_to_fit,
	page_durations,
	fade,
	map_durations,
	scroll,
)
import argparse
import config


def action_1():
	initialize(config.DIRS)


def action_2(program_arguments):
	simulated_argv = []
	if program_arguments.source:
		simulated_argv = [None, program_arguments.source]
	prepare(
		config.ARCHIVE_EXTENSIONS,
		simulated_argv,
		config.DIRS,
		config.IMAGE_EXTENSIONS,
		config.OUTPUT_FILENAME_LENGTH,
		config.PREFIX_LENGTH,
		config.SOURCE_PATHS,
	)


def action_3():
	resize_to_width(
		config.DIRS,
		config.IMAGE_EXTENSIONS,
		config.OUTPUT_IMAGE_EXTENSION,
		config.TARGET_WIDTH,
		config.WORKERS,
	)


def action_4(program_arguments):
	mode = program_arguments.mode if program_arguments.mode else "save"
	simulated_argv = [None, mode]
	lists(
		config.ALL_IMAGES_LIST_FILENAME,
		simulated_argv,
		config.DELETED_IMAGES_LIST_FILENAME,
		config.DIRS,
		config.KEPT_IMAGES_LIST_FILENAME,
	)


def action_5():
	crops(
		config.CROP_SUFFIX_LENGTH,
		config.DIRS,
		config.HEIGHT_RANGE,
		config.MARGIN,
		config.MAX_DISTANCE,
		config.MERGED_GAPS_FILENAME,
		config.OUTPUT_IMAGE_EXTENSION,
		config.TOTAL_GAPS_FILENAME,
		config.WORKERS,
	)


def action_6():
	texts(
		config.API_ENDPOINTS,
		config.API_KEYS,
		config.CONCURRENT_REQUESTS,
		config.DIRS,
		config.MAX_TOKENS,
		config.MODEL,
		config.OUTPUT_IMAGE_EXTENSION,
		config.PAUSE,
		config.PROMPT,
		config.RETRIES,
		config.TEMPERATURE,
		config.TEMPERATURE_STEP,
		config.TEXT_MIN_SIZE,
	)


def action_7():
	costs(
		config.COST_DEEPINFRA,
		config.COST_FILENAME,
		config.COST_GEMINI,
		config.COST_GROQ,
		config.COST_OPENAI,
		config.COST_TTS,
		config.DIRS,
		config.ENCODING_NAME,
		config.MAX_TOKENS,
		config.OUTPUT_IMAGE_EXTENSION,
	)


def action_8():
	fish_tts(
		config.API_ENDPOINTS,
		config.AUDIO_MIN_SIZE,
		config.AUDIO_OUTPUT_EXTENSION,
		config.DIRS,
		config.FISH_TEMPERATURE,
		config.MAX_TOKENS,
		config.PAUSE,
		config.REFERENCE_AUDIO,
		config.REFERENCE_TEXT,
		config.RETRIES,
		config.WORKERS,
	)


def action_9():
	openai_tts(
		config.API_ENDPOINTS,
		config.API_KEYS,
		config.AUDIO_MIN_SIZE,
		config.AUDIO_OUTPUT_EXTENSION,
		config.DIRS,
		config.INSTRUCTIONS,
		config.MAX_TOKENS,
		config.MODELS,
		config.PAUSE,
		config.RESPONSE_FORMAT,
		config.RETRIES,
		config.VOICES,
		config.WORKERS,
	)


def action_10():
	audio(
		config.AUDIO_CONCAT_LIST_FILENAME,
		config.AUDIO_DELAY_DURATION,
		config.AUDIO,
		config.AUDIO_OUTPUT_EXTENSION,
		config.AUDIO_TARGET_SEGMENT_DURATION,
		config.AUDIO_TRANSITION_DURATION,
		config.DELAY_SUFFIX,
		config.DIRS,
		config.MERGED_DURATIONS_FILENAME,
		config.OUTPUT_IMAGE_EXTENSION,
		config.PREFIX_LENGTH,
		config.SAMPLE_RATE,
		config.TOTAL_DURATION_FILENAME,
		config.TRANSITION_SUFFIX,
		config.WORKERS,
	)


def action_11():
	resize_to_fit(
		config.DIRS,
		config.OUTPUT_IMAGE_EXTENSION,
		config.TARGET_HEIGHT,
		config.WORKERS,
	)


def action_12():
	page_durations(
		config.DELAY_SUFFIX,
		config.DIRS,
		config.MERGED_DURATIONS_FILENAME,
		config.PAGE_DURATIONS_FILENAME,
		config.PREFIX_LENGTH,
		config.SUM_SUFFIX,
		config.TRANSITION_SUFFIX,
	)


def action_13():
	fade(
		config.AUDIO,
		config.DELAY_SUFFIX,
		config.DIRS,
		config.FADE_VIDEO,
		config.FADE_VIDEO_LIST_FILENAME,
		config.FRAME_SUFFIX_LENGTH,
		config.VIDEO_HOLD_DURATION,
		config.MEDIA,
		config.PAGE_DURATIONS_FILENAME,
		config.PREFIX_LENGTH,
		config.SUM_SUFFIX,
		config.TARGET_FPS,
		config.TRANSITION_SUFFIX,
	)


def action_14():
	map_durations(
		config.DIRS,
		config.MERGED_DURATIONS_FILENAME,
		config.MERGED_GAPS_FILENAME,
		config.TRANSITION_GAPS_FILENAME,
	)


def action_15():
	scroll(
		config.AUDIO,
		config.DELAY_PERCENT,
		config.DIRS,
		config.VIDEO_HOLD_DURATION,
		config.MEDIA,
		config.MERGED_DURATIONS_FILENAME,
		config.OUTPUT_IMAGE_EXTENSION,
		config.SCROLL_VIDEO,
		config.TARGET_FPS,
		config.TARGET_HEIGHT,
		config.TARGET_WIDTH,
		config.TRANSITION_GAPS_FILENAME,
	)


ACTION_EXECUTORS = {
	1: action_1,
	2: action_2,
	3: action_3,
	4: action_4,
	5: action_5,
	6: action_6,
	7: action_7,
	8: action_8,
	9: action_9,
	10: action_10,
	11: action_11,
	12: action_12,
	13: action_13,
	14: action_14,
	15: action_15,
}
ARGUMENT_REQUIRED_ACTIONS = {2, 4}


def start_processing(program_arguments):
	selected_action = program_arguments.action
	executor = ACTION_EXECUTORS[selected_action]
	if selected_action in ARGUMENT_REQUIRED_ACTIONS:
		if selected_action == 4 and program_arguments.mode is None:
			program_arguments.mode = "save"
		executor(program_arguments)
	else:
		executor()


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Create Manga/Manhwa/Manhua.",
		formatter_class=argparse.RawTextHelpFormatter,
		add_help=False,
	)
	required_group = parser.add_argument_group("Required arguments")
	required_group.add_argument(
		"action",
		type=int,
		choices=range(16),
		help="Specify the action number (0-15). 0 executes all actions.",
		metavar="ACTION",
	)
	optional_group = parser.add_argument_group(
		"Optional arguments for specific actions"
	)
	optional_group.add_argument(
		"--source",
		type=str,
		default=None,
		help="Input source path. Used only by action 2.",
		metavar="PATH",
	)
	optional_group.add_argument(
		"--mode",
		type=str,
		choices=["save", "delete"],
		default="save",
		help="Operation mode ('save' or 'delete'). Used only by action 4. Defaults to 'delete'.",
		metavar="MODE",
	)
	help_group = parser.add_argument_group("Help")
	help_group.add_argument(
		"-h", "--help", action="help", help="There is no help, just read your options."
	)
	parser.epilog = (
		"Action descriptions:\n"
		"  1: Prepare necessary directories.\n"
		"  2: Prepare images from specified source (use --source PATH).\n"
		"  3: Adjust image width.\n"
		"  4: Control image lists (use --mode {save,delete}).\n"
		"  5: Identify image text regions.\n"
		"  6: Get text from images.\n"
		"  7: Calculate approximate costs.\n"
		"  8: Create audio from text using Fish Speech.\n"
		"  9: Create audio from text using OpenAI compatible API.\n"
		" 10: Adjust and combine audio files.\n"
		" 11: Adjust image height.\n"
		" 12: Calculate time duration for each page.\n"
		" 13: Create video with fade transitions.\n"
		" 14: Connect audio durations to vertical gaps.\n"
		" 15: Create video with scroll effect.\n\n"
		"Recommendation: Check 'merge/deleted_images.json' before you use action 4."
	)
	program_arguments = parser.parse_args()
	start_processing(program_arguments)
