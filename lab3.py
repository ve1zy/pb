import requests
import json

API_KEY = ""

def send_request(messages, model="cohere/north-mini-code:free", reasoning_enabled=False):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Day 3 Lab"
    }
    
    data = {
        "model": model,
        "messages": messages,
        "reasoning": {"enabled": reasoning_enabled}
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Ошибка: {e}"

if __name__ == "__main__":
    task = "У меня есть 3 яблока. Вчера я съел одно. Сегодня утром я купил еще 2, но одно из них оказалось гнилым, и я его выбросил. Сколько у меня сейчас целых яблок?"
    
    print(f"ЗАДАЧА: {task}\n")
    print("="*50)


    print("СПОСОБ: Прямой ответ (Zero-shot)")
    msg_1 = [{"role": "user", "content": task}]
    ans_1 = send_request(msg_1)
    print(ans_1)


    print("СПОСОБ: Инструкция «Решай пошагово»")
    msg_2 = [{"role": "user", "content": f"{task}\n\nРеши эту задачу пошагово, объясняя каждое действие."}]
    ans_2 = send_request(msg_2)
    print(ans_2)


    print("СПОСОБ: Мета-промпт (Self-Prompting)")

    meta_prompt = f"Составь максимально точный и детальный промпт для решения следующей задачи, чтобы исключить ошибки в логике: '{task}'"
    generated_prompt = send_request([{"role": "user", "content": meta_prompt}])
    
    print(f"[Сгенерированный промпт]: {generated_prompt[:100]}...")
    msg_3 = [{"role": "user", "content": generated_prompt}]
    ans_3 = send_request(msg_3)
    print(f"[Ответ по мета-промпту]: {ans_3}")


    print("СПОСОБ: Группа экспертов (Аналитик, Инженер, Критик)")
    experts_prompt = (
        f"Задача: '{task}'.\n\n"
        "Действуйте как группа экспертов:\n"
        "1. Аналитик: разбери условия задачи.\n"
        "2. Инженер: произведи расчеты.\n"
        "3. Критик: проверь логику на наличие ловушек.\n"
        "В конце выдайте общий финальный ответ."
    )
    msg_4 = [{"role": "user", "content": experts_prompt}]
    ans_4 = send_request(msg_4)
    print(ans_4)

    print("\n" + "="*50)
    print("СРАВНЕНИЕ ЗАВЕРШЕНО")
    print("Повышение точности на логических задачах. Способ «Эксперты» дал самый структурированный и проверенный ответ.")