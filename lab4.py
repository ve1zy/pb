import requests
import json

API_KEY = ""

def send_request(prompt, temperature, model="poolside/laguna-m.1:free"):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Day 4 Temp Test"
    }
    
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "reasoning": {"enabled": False}
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Ошибка: {e}"
def print_comparison_report():
    report = """
    ИТОГОВОЕ СРАВНЕНИЕ ТЕМПЕРАТУРЫ (Temperature)
    ============================================================
    | Temp | Характеристика          | Где лучше использовать       |
    |------|-------------------------|------------------------------|
    |  0.0 | Предсказуемость, точность| Код, факты, математика       |
    |  0.7 | Баланс, живость         | Чат-боты, статьи, диалоги    |
    |  1.2 | Креативность, хаос      | Брейншторм, идеи, стихи      |
    ============================================================
    """
    print(report)
if __name__ == "__main__":
    prompt = "Придумай 3 коротких и запоминающихся названия для мобильного приложения, которое помогает студентам находить команду для дипломного проекта."
    
    print(f"ЗАДАЧА: {prompt}\n")
    print("="*60)

    temps = [0, 0.7, 1.2]
    
    for t in temps:
        print(f"\nTEMPERATURE = {t}")
        print("-" * 30)
        answer = send_request(prompt, t)
        print(answer)
        
    print("\n" + "="*60)
    print("ЭКСПЕРИМЕНТ ЗАВЕРШЕН")
    print_comparison_report()