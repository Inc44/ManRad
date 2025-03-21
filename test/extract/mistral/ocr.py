from mistralai import Mistral
import os

api_key = os.environ["MISTRAL_API_KEY"]
client = Mistral(api_key=api_key)
ocr_response = client.ocr.process(
	model="mistral-ocr-2503",
	document={
		"type": "image_url",
		"image_url": "",
	},
)
print(ocr_response.model_dump_json())
