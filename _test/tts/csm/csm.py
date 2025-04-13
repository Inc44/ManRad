from generator import load_csm_1b, Segment
import os
import torch
import torchaudio

os.environ["NO_TORCH_COMPILE"] = "1"
SPEAKER_PROMPTS = {
	"en": {
		"text": (
			"I honestly can't remember what catalyzed this desire..."
			"...But for as long as i can remember, there's something i've always admired."
			"Something i've devoted my whole self to becoming-"
			"An eminence in shadow."
		),
		"audio": "Nikolay_EN.mp3",
	},
	"ru": {
		"text": (
			"Честно говоря, я не могу вспомнить, что послужило катализатором этого желания..."
			"...Но сколько себя помню, есть нечто, чем я всегда восхищался."
			"Нечто, чему я посвятил всего себя —"
			"Величие в тени."
		),
		"audio": "Nikolay_RU.mp3",
	},
}


def load_prompt_audio(audio_path: str, target_sample_rate: int) -> torch.Tensor:
	audio_tensor, sample_rate = torchaudio.load(audio_path)
	audio_tensor = audio_tensor.squeeze(0)
	audio_tensor = torchaudio.functional.resample(
		audio_tensor, orig_freq=sample_rate, new_freq=target_sample_rate
	)
	return audio_tensor


def prepare_prompt(
	text: str, speaker: int, audio_path: str, sample_rate: int
) -> Segment:
	audio_tensor = load_prompt_audio(audio_path, sample_rate)
	return Segment(text=text, speaker=speaker, audio=audio_tensor)


def main():
	if torch.cuda.is_available():
		device = "cuda"
	else:
		device = "cpu"
	generator = load_csm_1b(device)
	prompt_a = prepare_prompt(
		SPEAKER_PROMPTS["en"]["text"],
		0,
		SPEAKER_PROMPTS["en"]["audio"],
		generator.sample_rate,
	)
	conversation = [
		{
			"text": "I honestly can't remember what catalyzed this desire... ...But for as long as i can remember, there's something i've always admired. Something i've devoted my whole self to becoming- An eminence in shadow.",
			"speaker_id": 0,
		},
	]
	generated_segments = []
	prompt_segments = [prompt_a]
	for utterance in conversation:
		audio_tensor = generator.generate(
			text=utterance["text"],
			speaker=utterance["speaker_id"],
			context=prompt_segments + generated_segments,
		)
		generated_segments.append(
			Segment(
				text=utterance["text"],
				speaker=utterance["speaker_id"],
				audio=audio_tensor,
			)
		)
	all_audio = torch.cat([seg.audio for seg in generated_segments], dim=0)
	torchaudio.save("csm.wav", all_audio.unsqueeze(0).cpu(), generator.sample_rate)


if __name__ == "__main__":
	main()
