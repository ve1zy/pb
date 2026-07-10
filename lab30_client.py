"""
Лабораторная 30: Клиент для тестирования LLM-сервиса
"""

import requests
import time
import json
from typing import List, Dict

BASE_URL = "http://localhost:8000"

def test_health():
    """Тест 1: Проверка здоровья"""
    print("\n" + "=" * 70)
    print("ТЕСТ 1: Health Check")
    print("=" * 70)
    
    start = time.time()
    response = requests.get(f"{BASE_URL}/health")
    elapsed = time.time() - start
    
    print(f"Статус: {response.status_code}")
    print(f"Время ответа: {elapsed:.3f}с")
    print(f"Данные: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    return response.status_code == 200

def test_models():
    """Тест 2: Список моделей"""
    print("\n" + "=" * 70)
    print("ТЕСТ 2: Список моделей")
    print("=" * 70)
    
    response = requests.get(f"{BASE_URL}/models")
    print(f"Статус: {response.status_code}")
    print(f"Модели: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    return response.status_code == 200

def test_chat_simple():
    """Тест 3: Простой чат"""
    print("\n" + "=" * 70)
    print("ТЕСТ 3: Простой чат")
    print("=" * 70)
    
    payload = {
        "messages": [
            {"role": "user", "content": "Привет! Как дела?"}
        ],
        "temperature": 0.3,
        "max_tokens": 100
    }
    
    start = time.time()
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    elapsed = time.time() - start
    
    print(f"Статус: {response.status_code}")
    print(f"Время ответа: {elapsed:.3f}с")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Ответ: {data['response'][:200]}...")
        print(f"Использование: {data['usage']}")
    
    return response.status_code == 200

def test_chat_context():
    """Тест 4: Чат с контекстом"""
    print("\n" + "=" * 70)
    print("ТЕСТ 4: Чат с контекстом")
    print("=" * 70)
    
    payload = {
        "messages": [
            {"role": "user", "content": "Меня зовут Алексей."},
            {"role": "assistant", "content": "Привет, Алексей! Рад познакомиться."},
            {"role": "user", "content": "Как меня зовут?"}
        ],
        "temperature": 0.3,
        "max_tokens": 50
    }
    
    start = time.time()
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    elapsed = time.time() - start
    
    print(f"Статус: {response.status_code}")
    print(f"Время ответа: {elapsed:.3f}с")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Ответ: {data['response']}")
    
    return response.status_code == 200

def test_rate_limit():
    """Тест 5: Rate limiting"""
    print("\n" + "=" * 70)
    print("ТЕСТ 5: Rate Limiting")
    print("=" * 70)
    
    print("Отправляем 12 запросов подряд...")
    
    success_count = 0
    rate_limited_count = 0
    
    for i in range(12):
        payload = {
            "messages": [{"role": "user", "content": f"Запрос {i+1}"}],
            "client_id": "test_client"
        }
        
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        
        if response.status_code == 200:
            success_count += 1
            print(f"  Запрос {i+1}: ✅ OK")
        elif response.status_code == 429:
            rate_limited_count += 1
            print(f"  Запрос {i+1}: ⚠️  Rate limited")
        else:
            print(f"  Запрос {i+1}: ❌ Error {response.status_code}")
    
    print(f"\nРезультат: {success_count} успешных, {rate_limited_count} отклонено")
    
    return rate_limited_count > 0

def test_context_limit():
    """Тест 6: Ограничение контекста"""
    print("\n" + "=" * 70)
    print("ТЕСТ 6: Context Limit")
    print("=" * 70)
    
    # Создаем очень длинный запрос
    long_text = "Это очень длинный текст. " * 100
    
    payload = {
        "messages": [
            {"role": "user", "content": long_text}
        ]
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    
    print(f"Статус: {response.status_code}")
    
    if response.status_code == 400:
        data = response.json()
        print(f"Ошибка: {data['detail']['error']}")
        print(f"Лимит: {data['detail']['max_tokens']} токенов")
        print(f"Текущий размер: {data['detail']['current_tokens']} токенов")
    
    return response.status_code == 400

def test_concurrent():
    """Тест 7: Параллельные запросы"""
    print("\n" + "=" * 70)
    print("ТЕСТ 7: Параллельные запросы")
    print("=" * 70)
    
    import concurrent.futures
    
    def make_request(i):
        payload = {
            "messages": [{"role": "user", "content": f"Вопрос {i}"}],
            "client_id": f"client_{i}"
        }
        start = time.time()
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        elapsed = time.time() - start
        return response.status_code, elapsed
    
    print("Отправляем 5 параллельных запросов...")
    
    start_total = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request, i) for i in range(5)]
        results = [f.result() for f in futures]
    
    total_time = time.time() - start_total
    
    success = sum(1 for status, _ in results if status == 200)
    avg_time = sum(elapsed for _, elapsed in results) / len(results)
    
    print(f"Успешных: {success}/5")
    print(f"Среднее время: {avg_time:.3f}с")
    print(f"Общее время: {total_time:.3f}с")
    
    return success >= 3

def test_stats():
    """Тест 8: Статистика"""
    print("\n" + "=" * 70)
    print("ТЕСТ 8: Статистика")
    print("=" * 70)
    
    response = requests.get(f"{BASE_URL}/stats")
    
    print(f"Статус: {response.status_code}")
    print(f"Данные: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    return response.status_code == 200

def main():
    """Запуск всех тестов"""
    print("=" * 70)
    print("Лабораторная 30: Тестирование LLM-сервиса")
    print("=" * 70)
    
    # Проверяем доступность сервера
    try:
        requests.get(f"{BASE_URL}/", timeout=2)
        print("✅ Сервер доступен")
    except:
        print("❌ Сервер недоступен!")
        print("Запустите: python lab30_server.py")
        return
    
    # Запускаем тесты
    tests = [
        ("Health Check", test_health),
        ("Models List", test_models),
        ("Simple Chat", test_chat_simple),
        ("Context Chat", test_chat_context),
        ("Rate Limit", test_rate_limit),
        ("Context Limit", test_context_limit),
        ("Concurrent", test_concurrent),
        ("Stats", test_stats)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            results.append((name, False))
    
    # Итоги
    print("\n" + "=" * 70)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    success_count = sum(1 for _, s in results if s)
    total = len(results)
    
    print(f"\nРезультат: {success_count}/{total} тестов пройдено")
    
    if success_count == total:
        print("\n🎉 Все тесты пройдены! Сервис работает стабильно.")
    else:
        print("\n⚠️  Некоторые тесты не пройдены.")

if __name__ == "__main__":
    main()
