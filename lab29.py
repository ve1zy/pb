"""
Лабораторная 29: Оптимизация локальной LLM
Сравнение параметров, квантования и prompt-шаблонов
"""

import json
import time
import numpy as np
from typing import List, Dict, Tuple
from ctransformers import AutoModelForCausalLM

# ============================================================================
# 1. Загрузка RAG-индекса (из lab28)
# ============================================================================

print("=" * 70)
print("Лабораторная 29: Оптимизация локальной LLM")
print("=" * 70)

# Загружаем индекс
with open("index_lab21.json", "r", encoding="utf-8") as f:
    index_data = json.load(f)

vocabulary = index_data["vocabulary"]
chunks = index_data["chunks"]
tfidf_matrix = np.array(index_data["embeddings"])
idf_dict = index_data["idf"]

print(f"\n✅ Загружен индекс: {len(chunks)} чанков, {len(vocabulary)} слов")

# ============================================================================
# 2. Retrieval функция
# ============================================================================

def tokenize(text: str) -> List[str]:
    import re
    return [t for t in re.findall(r'\b\w+\b', text.lower()) if len(t) > 2]

def compute_tfidf_vector(tokens: List[str], vocabulary: Dict[str, int], idf_dict: Dict[str, float]) -> np.ndarray:
    vector = np.zeros(len(vocabulary))
    for token in tokens:
        if token in vocabulary:
            vector[vocabulary[token]] += 1
    if len(tokens) > 0:
        vector = vector / len(tokens)
    for token, idx in vocabulary.items():
        if token in idf_dict:
            vector[idx] *= idf_dict[token]
    return vector

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0

def retrieve(query: str, top_k: int = 2) -> List[Tuple[Dict, float]]:
    query_tokens = tokenize(query)
    query_vector = compute_tfidf_vector(query_tokens, vocabulary, idf_dict)
    similarities = []
    for i, chunk in enumerate(chunks):
        sim = cosine_similarity(query_vector, tfidf_matrix[i])
        similarities.append((chunk, sim))
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]

# ============================================================================
# 3. Тестовые запросы
# ============================================================================

test_queries = [
    "Что такое Docker и как его использовать?",
    "Как работает asyncio в Python?",
    "Что такое MCP протокол?"
]

# ============================================================================
# 4. Базовая конфигурация (до оптимизации)
# ============================================================================

print("\n" + "=" * 70)
print("ТЕСТ 1: Базовая конфигурация (до оптимизации)")
print("=" * 70)

print("\n📦 Загрузка модели TinyLlama Q4_K_M...")
model_base = AutoModelForCausalLM.from_pretrained(
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
    model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    model_type="llama"
)
print("✅ Модель загружена!")

def generate_base(context: str, question: str) -> Tuple[str, float]:
    """Базовая генерация"""
    prompt = f"Контекст:\n{context}\n\nВопрос: {question}\n\nОтвет:"
    start = time.time()
    response = model_base(prompt, max_new_tokens=150, temperature=0.7)
    elapsed = time.time() - start
    return response.strip(), elapsed

# Тестируем базовую конфигурацию
results_base = []
for query in test_queries:
    retrieved = retrieve(query, top_k=2)
    context = "\n\n".join([c['content'][:200] for c, _ in retrieved])
    
    answer, elapsed = generate_base(context, query)
    results_base.append({
        "query": query,
        "answer": answer,
        "time": elapsed,
        "context_len": len(context)
    })
    
    print(f"\nЗапрос: {query}")
    print(f"Время: {elapsed:.2f}с")
    print(f"Ответ: {answer[:100]}...")

avg_time_base = sum(r['time'] for r in results_base) / len(results_base)
print(f"\n⏱️  Среднее время (базовая): {avg_time_base:.2f}с")

# ============================================================================
# 5. Оптимизация 1: Temperature
# ============================================================================

print("\n" + "=" * 70)
print("ТЕСТ 2: Оптимизация temperature")
print("=" * 70)

temperatures = [0.1, 0.3, 0.5, 0.7, 0.9]
results_temp = {}

for temp in temperatures:
    print(f"\n🌡️  Temperature: {temp}")
    temp_results = []
    
    for query in test_queries:
        retrieved = retrieve(query, top_k=2)
        context = "\n\n".join([c['content'][:200] for c, _ in retrieved])
        
        prompt = f"Контекст:\n{context}\n\nВопрос: {query}\n\nОтвет:"
        start = time.time()
        response = model_base(prompt, max_new_tokens=150, temperature=temp)
        elapsed = time.time() - start
        
        temp_results.append({
            "query": query,
            "answer": response.strip(),
            "time": elapsed
        })
    
    avg_time = sum(r['time'] for r in temp_results) / len(temp_results)
    results_temp[temp] = {
        "results": temp_results,
        "avg_time": avg_time
    }
    
    print(f"   Среднее время: {avg_time:.2f}с")
    print(f"   Пример: {temp_results[0]['answer'][:80]}...")

# ============================================================================
# 6. Оптимизация 2: Квантование
# ============================================================================

print("\n" + "=" * 70)
print("ТЕСТ 3: Разные квантования")
print("=" * 70)

quantizations = [
    ("Q2_K", "tinyllama-1.1b-chat-v1.0.Q2_K.gguf"),
    ("Q4_K_M", "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"),
    ("Q5_K_M", "tinyllama-1.1b-chat-v1.0.Q5_K_M.gguf"),
    ("Q8_0", "tinyllama-1.1b-chat-v1.0.Q8_0.gguf")
]

results_quant = {}

for quant_name, quant_file in quantizations:
    print(f"\n📦 Загрузка {quant_name}...")
    try:
        model_quant = AutoModelForCausalLM.from_pretrained(
            "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
            model_file=quant_file,
            model_type="llama"
        )
        print(f"✅ {quant_name} загружена!")
        
        quant_results = []
        for query in test_queries:
            retrieved = retrieve(query, top_k=2)
            context = "\n\n".join([c['content'][:200] for c, _ in retrieved])
            
            prompt = f"Контекст:\n{context}\n\nВопрос: {query}\n\nОтвет:"
            start = time.time()
            response = model_quant(prompt, max_new_tokens=150, temperature=0.3)
            elapsed = time.time() - start
            
            quant_results.append({
                "query": query,
                "answer": response.strip(),
                "time": elapsed
            })
        
        avg_time = sum(r['time'] for r in quant_results) / len(quant_results)
        results_quant[quant_name] = {
            "results": quant_results,
            "avg_time": avg_time
        }
        
        print(f"   Среднее время: {avg_time:.2f}с")
        print(f"   Пример: {quant_results[0]['answer'][:80]}...")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки {quant_name}: {e}")
        results_quant[quant_name] = {"error": str(e)}

# ============================================================================
# 7. Оптимизация 3: Prompt-шаблон
# ============================================================================

print("\n" + "=" * 70)
print("ТЕСТ 4: Оптимизированный prompt-шаблон")
print("=" * 70)

def generate_optimized(context: str, question: str) -> Tuple[str, float]:
    """Оптимизированный prompt для RAG"""
    prompt = f"""Ты - помощник, который отвечает на вопросы на основе предоставленного контекста.

ИНСТРУКЦИИ:
1. Используй ТОЛЬКО информацию из контекста
2. Отвечай кратко и по существу
3. Если в контексте нет ответа, скажи "Не знаю"

КОНТЕКСТ:
{context}

ВОПРОС: {question}

ОТВЕТ (кратко):"""
    
    start = time.time()
    response = model_base(prompt, max_new_tokens=100, temperature=0.3)
    elapsed = time.time() - start
    return response.strip(), elapsed

print("\n📝 Оптимизированный prompt-шаблон:")
print("   - Четкие инструкции")
print("   - Ограничение контекстом")
print("   - Низкая temperature (0.3)")
print("   - Меньше max_tokens (100)")

results_prompt = []
for query in test_queries:
    retrieved = retrieve(query, top_k=2)
    context = "\n\n".join([c['content'][:200] for c, _ in retrieved])
    
    answer, elapsed = generate_optimized(context, query)
    results_prompt.append({
        "query": query,
        "answer": answer,
        "time": elapsed
    })
    
    print(f"\nЗапрос: {query}")
    print(f"Время: {elapsed:.2f}с")
    print(f"Ответ: {answer[:100]}...")

avg_time_prompt = sum(r['time'] for r in results_prompt) / len(results_prompt)
print(f"\n⏱️  Среднее время (оптимизированный prompt): {avg_time_prompt:.2f}с")

# ============================================================================
# 8. Итоговое сравнение
# ============================================================================

print("\n" + "=" * 70)
print("ИТОГОВОЕ СРАВНЕНИЕ")
print("=" * 70)

print("\n📊 Скорость:")
print(f"   Базовая конфигурация: {avg_time_base:.2f}с")
print(f"   Оптимизированный prompt: {avg_time_prompt:.2f}с")
print(f"   Улучшение: {((avg_time_base - avg_time_prompt) / avg_time_base * 100):.1f}%")

print("\n🌡️  Temperature (лучшее качество):")
best_temp = min(results_temp.items(), key=lambda x: x[1]['avg_time'])
print(f"   Лучшая: {best_temp[0]} ({best_temp[1]['avg_time']:.2f}с)")

print("\n📦 Квантование:")
for quant_name, data in results_quant.items():
    if "error" not in data:
        print(f"   {quant_name}: {data['avg_time']:.2f}с")

print("\n✅ Рекомендации:")
print("   1. Temperature: 0.1-0.3 для фактологических ответов")
print("   2. Temperature: 0.5-0.7 для креативных задач")
print("   3. Квантование: Q4_K_M (баланс качество/размер)")
print("   4. Prompt: четкие инструкции + ограничение контекстом")
print("   5. Max tokens: 100-150 для кратких ответов")

print("\n" + "=" * 70)
print("Лабораторная 29 завершена")
print("=" * 70)
