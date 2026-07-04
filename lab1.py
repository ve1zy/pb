import requests
import json
import os

API_KEY = ""


def get_llm_response(user_message):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost", 
        "X-Title": "Day 1 Test"
    }
    
    data = {
        "model": "cohere/north-mini-code:free",
        "messages": [
            {
                "role": "user",
                "content": user_message
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        

        assistant_message = result['choices'][0]['message']['content']
        return assistant_message
        
    except Exception as e:
        return f"Ошибка при запросе: {e}"

if __name__ == "__main__":
    print("Отправляю запрос к Laguna M.1...")
    

    question = "Привет! Напиши короткую функцию на Python для расчета факториала."
    
    answer = get_llm_response(question)
    
    print("\n--- Ответ модели ---")
    print(answer)
    print("--------------------")
    print("Успешный обмен данными. Получен первый ответ от модели Laguna M.1.")