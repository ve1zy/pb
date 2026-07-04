import requests
import json

API_KEY = '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'

response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    data=json.dumps({
        "model": "cohere/north-mini-code:free",
        "messages": [
            {
                "role": "user",
                "content": "Что такое event loop в asyncio?"
            }
        ]
    })
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(f"Ответ: {result['choices'][0]['message']['content'][:100]}...")
else:
    print(f"Ошибка: {response.text}")
