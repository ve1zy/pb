from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Optional

import requests

from lab21 import DocumentIndexer, FixedSizeChunker


class RAGAgent:
    """Агент с двумя режимами: plain (без RAG) и rag (с поиском контекста)."""

    def __init__(self, api_key: str, model: str = "cohere/north-mini-code:free"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.indexer: Optional[DocumentIndexer] = None
        self.history: list[dict] = []

    def load_index(self, path: str = "index_lab21.json"):
        """Загрузка индекса из lab21."""
        self.indexer = DocumentIndexer()
        self.indexer.index_path = path
        self.indexer.load_index()
        print(f"  Индекс загружен: {len(self.indexer.chunks)} чанков, словарь: {len(self.indexer.vocabulary)}")

    def build_index(self, filepaths: list[str], chunker: str = "fixed"):
        """Построение индекса с нуля."""
        self.indexer = DocumentIndexer()
        self.indexer.index_files(filepaths, chunker=chunker)
        self.indexer.generate_embeddings()
        self.indexer.save_index()

    def _call_llm(self, messages: list[dict]) -> str:
        """Вызов LLM через OpenRouter с retry."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "RAG Agent Lab22",
        }
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if "laguna" in self.model:
            data["reasoning"] = {"enabled": False}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=60,
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"    Rate limit, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    return f"[Ошибка LLM: {e}]"
            except Exception as e:
                return f"[Ошибка LLM: {e}]"
        return "[Ошибка LLM: max retries exceeded]"

    def ask_plain(self, question: str) -> dict:
        """Вопрос к LLM без RAG."""
        messages = [
            {"role": "system", "content": "Ты — эксперт по программированию. Отвечай кратко и по делу."},
            {"role": "user", "content": question},
        ]
        start = time.time()
        answer = self._call_llm(messages)
        elapsed = time.time() - start

        return {
            "mode": "plain",
            "question": question,
            "answer": answer,
            "sources": [],
            "elapsed": round(elapsed, 2),
            "context_used": False,
        }

    def ask_rag(self, question: str, top_k: int = 3) -> dict:
        """Вопрос к LLM с RAG: поиск чанков → объединение → запрос."""
        if not self.indexer:
            return {"error": "Индекс не загружен. Вызови load_index() или build_index()"}

        start = time.time()

        # 1 — Поиск релевантных чанков
        search_results = self.indexer.search(question, top_k=top_k)

        # 2 — Формирование контекста
        context_parts = []
        sources = []
        for i, r in enumerate(search_results, 1):
            context_parts.append(f"[Источник {i}: {r['title']} / {r['section']}]\n{r['content']}")
            sources.append({
                "rank": i,
                "score": r["score"],
                "title": r["title"],
                "section": r["section"],
                "chunk_id": r["chunk_id"],
            })

        context = "\n\n---\n\n".join(context_parts) if context_parts else "(контекст не найден)"

        # 3 — Объединение с вопросом
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты — эксперт по программированию. "
                    "Отвечай на вопрос пользователя, используя предоставленный контекст. "
                    "Если контекст не содержит ответа, скажи об этом. "
                    "Указывай источники в ответе."
                ),
            },
            {
                "role": "user",
                "content": f"КОНТЕКСТ:\n{context}\n\nВОПРОС: {question}",
            },
        ]

        # 4 — Запрос к LLM
        answer = self._call_llm(messages)
        elapsed = time.time() - start

        return {
            "mode": "rag",
            "question": question,
            "answer": answer,
            "sources": sources,
            "elapsed": round(elapsed, 2),
            "context_used": True,
            "context_length": len(context),
        }

    def compare(self, question: str, top_k: int = 3) -> dict:
        """Сравнение ответов: plain vs rag."""
        plain = self.ask_plain(question)
        rag = self.ask_rag(question, top_k=top_k)

        return {
            "question": question,
            "plain": plain,
            "rag": rag,
        }


# 10 контрольных вопросов
BENCHMARK_QUESTIONS = [
    {
        "id": 1,
        "question": "Что такое event loop в asyncio?",
        "expectation": "Event loop — центральный механизм asyncio, регистрирует и распределяет асинхронные задачи",
        "expected_source": "python_async.md",
        "keywords": ["event loop", "asyncio", "распределяет", "задачи"],
    },
    {
        "id": 2,
        "question": "Как создать GET endpoint в FastAPI?",
        "expectation": "Использовать декоратор @app.get() с async функцией",
        "expected_source": "fastapi_guide.md",
        "keywords": ["@app.get", "endpoint", "FastAPI", "декоратор"],
    },
    {
        "id": 3,
        "question": "Какие транспорты поддерживает MCP?",
        "expectation": "stdio для локальных процессов и HTTP+SSE для удалённых серверов",
        "expected_source": "mcp_protocol.md",
        "keywords": ["stdio", "HTTP+SSE", "транспорт", "локальных", "удалённых"],
    },
    {
        "id": 4,
        "question": "Как использовать транзакции в SQLite?",
        "expectation": "BEGIN TRANSACTION → операции → COMMIT",
        "expected_source": "sqlite_guide.md",
        "keywords": ["BEGIN TRANSACTION", "COMMIT", "транзакции"],
    },
    {
        "id": 5,
        "question": "Какие типы машинного обучения существуют?",
        "expectation": "Supervised learning, Unsupervised learning, Reinforcement learning",
        "expected_source": "ml_basics.md",
        "keywords": ["Supervised", "Unsupervised", "Reinforcement", "обучения"],
    },
    {
        "id": 6,
        "question": "Что такое Dockerfile и для чего он нужен?",
        "expectation": "Dockerfile — шаблон для сборки Docker-образа, описывает шаги установки и запуска",
        "expected_source": "docker_basics.md",
        "keywords": ["Dockerfile", "образ", "image", "сборки"],
    },
    {
        "id": 7,
        "question": "Что такое Git Flow?",
        "expectation": "Ветвление: main, develop, feature/*, release/*, hotfix/*",
        "expected_source": "git_workflow.md",
        "keywords": ["main", "develop", "feature", "release", "hotfix"],
    },
    {
        "id": 8,
        "question": "Как использовать fixtures в pytest?",
        "expectation": "Декоратор @pytest.fixture, передача fixture как параметр в тест",
        "expected_source": "testing_python.md",
        "keywords": ["@pytest.fixture", "fixture", "pytest", "параметр"],
    },
    {
        "id": 9,
        "question": "Как настроить Docker Compose с веб-сервисом и базой данных?",
        "expectation": "version + services: web (build, ports) + db (postgres, environment)",
        "expected_source": "docker_basics.md",
        "keywords": ["Docker Compose", "services", "web", "db", "postgres"],
    },
    {
        "id": 10,
        "question": "Какие метрики используются для оценки классификации?",
        "expectation": "Accuracy, Precision, Recall, F1-score",
        "expected_source": "ml_basics.md",
        "keywords": ["Accuracy", "Precision", "Recall", "F1"],
    },
]


def evaluate_answer(answer: str, question_data: dict) -> dict:
    """Оценка ответа: проверка ключевых слов."""
    keywords = question_data["keywords"]
    answer_lower = answer.lower()
    found = [kw for kw in keywords if kw.lower() in answer_lower]
    score = len(found) / len(keywords) if keywords else 0

    return {
        "question_id": question_data["id"],
        "score": round(score, 2),
        "found_keywords": found,
        "missing_keywords": [kw for kw in keywords if kw.lower() not in answer_lower],
        "total_keywords": len(keywords),
    }


async def run_benchmark(agent: RAGAgent) -> dict:
    """Запуск бенчмарка: 10 вопросов, plain vs rag."""
    results = []
    print("\n" + "=" * 70)
    print("БЕНЧМАРК: 10 контрольных вопросов")
    print("=" * 70)

    for i, q in enumerate(BENCHMARK_QUESTIONS):
        print(f"\n--- Вопрос {i+1}/10: {q['question']} ---")

        # Plain
        plain = agent.ask_plain(q["question"])
        plain_eval = evaluate_answer(plain["answer"], q)
        print(f"  Plain: score={plain_eval['score']} ({plain_eval['found_keywords']})")

        # RAG
        rag = agent.ask_rag(q["question"])
        rag_eval = evaluate_answer(rag["answer"], q)
        rag_sources = [s["title"] for s in rag["sources"]]
        print(f"  RAG:   score={rag_eval['score']} ({rag_eval['found_keywords']})")
        print(f"  Источники: {rag_sources}")

        results.append({
            "question": q["question"],
            "expectation": q["expectation"],
            "expected_source": q["expected_source"],
            "plain_answer": plain["answer"],
            "plain_score": plain_eval["score"],
            "plain_eval": plain_eval,
            "rag_answer": rag["answer"],
            "rag_score": rag_eval["score"],
            "rag_eval": rag_eval,
            "rag_sources": rag_sources,
        })

        # Delay to avoid rate limiting (except after last question)
        if i < len(BENCHMARK_QUESTIONS) - 1:
            await asyncio.sleep(2)

    # Итоги
    plain_scores = [r["plain_score"] for r in results]
    rag_scores = [r["rag_score"] for r in results]
    avg_plain = sum(plain_scores) / len(plain_scores)
    avg_rag = sum(rag_scores) / len(rag_scores)

    print("\n" + "=" * 70)
    print("ИТОГИ БЕНЧМАРКА")
    print("=" * 70)
    print(f"  Plain (без RAG): средний score = {avg_plain:.2f}")
    print(f"  RAG (с поиском): средний score = {avg_rag:.2f}")
    print(f"  Прирост: {avg_rag - avg_plain:+.2f}")
    print("=" * 70)

    return {
        "results": results,
        "avg_plain": round(avg_plain, 2),
        "avg_rag": round(avg_rag, 2),
        "improvement": round(avg_rag - avg_plain, 2),
    }
