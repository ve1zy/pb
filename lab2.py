import requests
import json

API_KEY = "" 

def send_request(messages, model="cohere/north-mini-code:free", max_tokens=None, stop=None):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Day 2 Lab"
    }
    
    data = {
        "model": model,
        "messages": messages,
        "reasoning": {"enabled": False}
    }
    
    if max_tokens is not None:
        data["max_tokens"] = max_tokens
    if stop is not None:
        data["stop"] = stop

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        return "Ошибка: пустой ответ от модели"
            
    except Exception as e:
        return f"Ошибка запроса: {e}"

if __name__ == "__main__":
    base_question = "Назови 3 главных преимущества Python для Data Science."

    print("ЗАПУСК СРАВНЕНИЯ ОТВЕТОВ\n")

    print("--- ВАРИАНТ 1: Без ограничений ---")
    messages_free = [{"role": "user", "content": base_question}]
    answer_free = send_request(messages_free)
    
    print(answer_free)
    print(f"Статистика: {len(answer_free)} символов.\n")

    print("--- ВАРИАНТ 2: С жесткими ограничениями ---")
    
    strict_instruction = (
        f"{base_question}\n\n"
        "ИНСТРУКЦИЯ:\n"
        "1. Ответь ТОЛЬКО валидным JSON-массивом строк.\n"
        "2. Не используй markdown (без ```json).\n"
        "3. Максимум 10 слов на каждый пункт.\n"
        "4. Заверши ответ сразу после закрывающей квадратной скобки."
    )
    
    messages_strict = [{"role": "user", "content": strict_instruction}]
    
    answer_strict = send_request(
        messages_strict, 
        max_tokens=150, 
        stop=["\n", "```"] 
    )
    
    print(answer_strict)
    print(f"Статистика: {len(answer_strict)} символов.")
    

    try:
        parsed = json.loads(answer_strict)
        print("Успех: Ответ является валидным JSON!")
    except:
        print("Внимание: Ответ не является валидным JSON.")
    print("Переход от «болтливого» текста к чистым данным JSON. Идеально для интеграции в код.")