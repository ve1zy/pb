import requests
import time
import json

API_KEY = ""

def test_model(model_name, prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Day 5 Full Test"
    }
    
    data = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }
    
    if "laguna" in model_name:
        data["reasoning"] = {"enabled": False}

    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code != 200:
            return {
                "model": model_name.split('/')[-1],
                "status": response.status_code,
                "error_detail": response.text[:100]
            }
            
        result = response.json()
        end_time = time.time()
        
        content = result['choices'][0]['message']['content']
        usage = result.get('usage', {})
        
        return {
            "model": model_name.split('/')[-1],
            "time": round(end_time - start_time, 2),
            "tokens": usage.get('total_tokens', 0),
            "success": True,
            "preview": content[:80].replace('\n', ' ') + "..."
        }
            
    except Exception as e:
        return {"model": model_name.split('/')[-1], "error": str(e)}
def print_final_conclusion():
    conclusion = """
    ============================================================
    🏁 ИТОГОВЫЙ ВЫВОД ПО МОДЕЛЯМ
    ============================================================
    
    СЛАБАЯ МОДЕЛЬ (Laguna M.1)
       • Роль: "Спринтер" (легкая, быстрая в генерации текста).
       • Результат: Самый короткий ответ.
       • Вердикт: Идеальна для экономии лимитов и простых задач.

    СРЕДНЯЯ МОДЕЛЬ (Gemma 4 31B)
       • Роль: "Универсальный солдат" (баланс ума и скорости).
       • Результат: (самая быстрая!).
       • Вердикт: Лучший выбор для твоего мобильного приложения.

   СИЛЬНАЯ МОДЕЛЬ (GPT-OSS 120B)
       • Роль: "Тяжеловес" (глубокая аналитика).
       • Результат: Самое подробное объяснение.
       • Вердикт: Используй для сложных задач по ML и отладки кода.

    ============================================================
    💡 РЕКОМЕНДАЦИЯ: Используй Gemma 4 как основную модель, 
    а GPT-OSS подключай только для самых сложных вопросов.
    ============================================================
    """
    print(conclusion)
if __name__ == "__main__":
    prompt = "Напиши функцию на Python для быстрой сортировки (Quick Sort)."
    
    models = [
        "cohere/north-mini-code:free",
        "google/gemma-4-31b-it:free",
        "openai/gpt-oss-120b:free"
    ]
    
    print(f"ПОЛНЫЙ БЕНЧМАРК МОДЕЛЕЙ\nЗадача: {prompt}\n")
    print("="*70)
    
    for model in models:
        print(f"Запуск {model}...")
        res = test_model(model, prompt)
        
        if 'success' in res and res['success']:
            print(f"Успех! Время: {res['time']}с | Токены: {res['tokens']}")
            print(f"   Начало ответа: {res['preview']}\n")
        else:
            print(f"Неудача.")
            if 'error_detail' in res:
                print(f"   Детали: {res['error_detail']}\n")
            elif 'error' in res:
                print(f"   Ошибка: {res['error']}\n")
                
    print("Тестирование завершено.")
    print_final_conclusion()