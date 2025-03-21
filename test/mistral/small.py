from mistralai import Mistral
import json
import os

api_key = os.environ["MISTRAL_API_KEY"]
model = "mistral-small-2503"
client = Mistral(api_key=api_key)
messages = [
	{
		"role": "user",
		"content": [
			{
				"type": "text",
				"text": 'Return bounding boxes in the correct manga page reading order, from right to left, along with their corresponding text content to be read aloud: [{"box_2d": [y1, x1, y2, x2], "text": "text content"}, ...]',
			},
			{
				"type": "image_url",
				"image_url": "",
			},
		],
	}
]
chat_response = client.chat.complete(model=model, messages=messages, temperature=0)
data = json.loads(chat_response.model_dump_json())
content = data["choices"][0]["message"]["content"]
start = content.find("[")
end = content.rfind("]") + 1
json_substring = content[start:end]
result = json.loads(json_substring)
print(result)
