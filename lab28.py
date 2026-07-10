"""
Лабораторная 28: Локальная LLM + RAG
Полностью локальная RAG-система с использованием:
- Индекса из lab21 (TF-IDF)
- Локальной LLM (TinyLlama через ctransformers)
- Сравнение с облачной моделью (если есть OpenAI API)
"""

import json
import time
import numpy as np
from typing import List, Dict, Tuple
from ctransformers import AutoModelForCausalLM

# ============================================================================
# 1. Загрузка индекса и документов
# ============================================================================

print("=" * 70)
print("Лабораторная 28: Локальная LLM + RAG")
print("=" * 70)

# Загружаем индекс
with open("index_lab21.json", "r", encoding="utf-8") as f:
    index_data = json.load(f)

vocabulary = index_data["vocabulary"]
chunks = index_data["chunks"]
tfidf_matrix = np.array(index_data["embeddings"])
idf_dict = index_data["idf"]

print(f"\n✅ Загружен индекс:")
print(f"   - Словарь: {len(vocabulary)} слов")
print(f"   - Чанков: {len(chunks)}")
print(f"   - Матрица TF-IDF: {tfidf_matrix.shape}")

# Загружаем документы
docs = {}
for doc_file in [
    "docs_lab21/docker_basics.md",
    "docs_lab21/fastapi_guide.md",
    "docs_lab21/git_workflow.md",
    "docs_lab21/mcp_protocol.md",
    "docs_lab21/ml_basics.md",
    "docs_lab21/python_async.md",
    "docs_lab21/sqlite_guide.md",
    "docs_lab21/testing_python.md",
]:
    try:
        with open(doc_file, "r", encoding="utf-8") as f:
            docs[doc_file] = f.read()
    except FileNotFoundError:
        print(f"⚠️  Файл не найден: {doc_file}")

print(f"   - Документов загружено: {len(docs)}")

# ============================================================================
# 2. Retrieval: поиск релевантных чанков
# ============================================================================

def tokenize(text: str) -> List[str]:
    """Простая токенизация"""
    import re
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return [t for t in tokens if len(t) > 2]

def compute_tfidf_vector(tokens: List[str], vocabulary: Dict[str, int], idf_dict: Dict[str, float]) -> np.ndarray:
    """Вычисляет TF-IDF вектор для текста"""
    vector = np.zeros(len(vocabulary))
    
    # TF (term frequency)
    for token in tokens:
        if token in vocabulary:
            idx = vocabulary[token]
            vector[idx] += 1
    
    # Нормализация TF
    if len(tokens) > 0:
        vector = vector / len(tokens)
    
    # IDF weighting - используем словарь IDF
    for token, idx in vocabulary.items():
        if token in idf_dict:
            vector[idx] *= idf_dict[token]
    
    return vector

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Косинусное сходство"""
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)

def retrieve(query: str, top_k: int = 2) -> List[Tuple[Dict, float]]:
    """Поиск релевантных чанков"""
    # Векторизуем запрос используя IDF из индекса
    query_tokens = tokenize(query)
    query_vector = compute_tfidf_vector(query_tokens, vocabulary, idf_dict)
    
    # Вычисляем сходство
    similarities = []
    for i, chunk in enumerate(chunks):
        sim = cosine_similarity(query_vector, tfidf_matrix[i])
        similarities.append((chunk, sim))
    
    # Сортируем по сходству
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    return similarities[:top_k]

# ============================================================================
# 3. Локальная LLM для генерации
# ============================================================================

print("\n📦 Загрузка локальной модели TinyLlama...")
local_model = AutoModelForCausalLM.from_pretrained(
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
    model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    model_type="llama"
)
print("✅ Локальная модель загружена!")

def generate_local(context: str, question: str, max_tokens: int = 200) -> str:
    """Генерация ответа через локальную LLM"""
    prompt = f"""Контекст:
{context}

Вопрос: {question}

Ответ:"""
    
    response = local_model(prompt, max_new_tokens=max_tokens, temperature=0.7)
    return response.strip()

# ============================================================================
# 4. Облачная модель (если есть API ключ)
# ============================================================================

def generate_cloud(context: str, question: str) -> str:
    """Генерация ответа через облачную модель (OpenAI)"""
    try:
        import os
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "⚠️  OPENAI_API_KEY не установлен"
        
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты помощник, который отвечает на вопросы на основе предоставленного контекста."},
                {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {question}\n\nОтвет:"}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    except ImportError:
        return "⚠️  Библиотека openai не установлена"
    except Exception as e:
        return f"⚠️  Ошибка: {e}"

# ============================================================================
# 5. RAG-пайплайн
# ============================================================================

def rag_pipeline(query: str, use_cloud: bool = False) -> Dict:
    """Полный RAG-пайплайн"""
    start_time = time.time()
    
    # Retrieval
    retrieved_chunks = retrieve(query, top_k=2)
    
    # Ограничиваем контекст до ~300 слов чтобы влезть в 512 токенов
    full_context = "\n\n".join([chunk['content'] for chunk, score in retrieved_chunks])
    words = full_context.split()
    if len(words) > 300:
        context = " ".join(words[:300]) + "..."
    else:
        context = full_context
    
    # Generation
    if use_cloud:
        answer = generate_cloud(context, query)
        model_type = "Cloud (GPT-3.5)"
    else:
        answer = generate_local(context, query, max_tokens=150)
        model_type = "Local (TinyLlama)"
    
    elapsed = time.time() - start_time
    
    return {
        "query": query,
        "retrieved_chunks": retrieved_chunks,
        "context": context,
        "answer": answer,
        "model": model_type,
        "time": elapsed
    }

# ============================================================================
# 6. Тестирование и сравнение
# ============================================================================

test_queries = [
    "Что такое Docker и как его использовать?",
    "Как работает asyncio в Python?",
    "Что такое MCP протокол?",
    "Как тестировать Python код?"
]

print("\n" + "=" * 70)
print("Тестирование RAG-системы")
print("=" * 70)

# Проверяем наличие OPENAI_API_KEY
import os
has_cloud = bool(os.getenv("OPENAI_API_KEY"))
if not has_cloud:
    print("\n⚠️  OPENAI_API_KEY не установлен - облачная модель недоступна")
    print("   Будет тестироваться только локальная модель")

results_local = []
results_cloud = []

for i, query in enumerate(test_queries, 1):
    print(f"\n{'='*70}")
    print(f"Запрос {i}: {query}")
    print(f"{'='*70}")
    
    # Локальная модель
    print("\n📍 Локальная модель (TinyLlama):")
    result_local = rag_pipeline(query, use_cloud=False)
    print(f"   Время: {result_local['time']:.2f}с")
    print(f"   Найдено чанков: {len(result_local['retrieved_chunks'])}")
    for j, (chunk, score) in enumerate(result_local['retrieved_chunks'], 1):
        print(f"   - Чанк {j} (score: {score:.3f}): {chunk['source']}")
    print(f"   Ответ: {result_local['answer'][:300]}...")
    results_local.append(result_local)
    
    # Облачная модель (только если есть ключ)
    if has_cloud:
        print("\n☁️  Облачная модель (GPT-3.5):")
        result_cloud = rag_pipeline(query, use_cloud=True)
        print(f"   Время: {result_cloud['time']:.2f}с")
        print(f"   Ответ: {result_cloud['answer'][:300]}...")
        results_cloud.append(result_cloud)

# ============================================================================
# 7. Сравнение и оценка
# ============================================================================

print("\n" + "=" * 70)
print("Сравнение моделей")
print("=" * 70)

avg_time_local = sum(r['time'] for r in results_local) / len(results_local)

print(f"\n⏱️  Средняя скорость:")
print(f"   Локальная: {avg_time_local:.2f}с")

if has_cloud and results_cloud:
    avg_time_cloud = sum(r['time'] for r in results_cloud) / len(results_cloud)
    print(f"   Облачная:  {avg_time_cloud:.2f}с")
    print(f"   Разница:   {abs(avg_time_local - avg_time_cloud):.2f}с")

print(f"\n📊 Качество:")
print(f"   Локальная модель:")
print(f"   - Плюсы: работает офлайн, быстро, бесплатно")
print(f"   - Минусы: маленькие модели дают менее точные ответы")
print(f"   - Стабильность: высокая (нет зависимости от сети)")

if has_cloud:
    print(f"\n   Облачная модель:")
    print(f"   - Плюсы: большие модели, высокое качество ответов")
    print(f"   - Минусы: требует интернет, API ключ, платно")
    print(f"   - Стабильность: зависит от сети и API")
else:
    print(f"\n   Облачная модель не тестировалась (нет OPENAI_API_KEY)")

print(f"\n✅ Вывод:")
print(f"   Локальная RAG-система полностью работает офлайн.")
print(f"   Подходит для прототипирования и приватных данных.")
print(f"   Для production можно использовать более мощные модели (Llama 7B/13B).")

print("\n" + "=" * 70)
print("Лабораторная 28 завершена")
print("=" * 70)
