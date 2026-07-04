from __future__ import annotations

import json
import re
import time
from typing import Optional

import requests

from lab21 import DocumentIndexer
from lab22 import BENCHMARK_QUESTIONS, evaluate_answer
from lab23 import BM25Reranker, RelevanceFilter, QueryRewriter


class CitedRAGAgent:
    """RAG-агент с обязательными источниками, цитатами и режимом 'не знаю'."""

    def __init__(self, api_key: str, model: str = "cohere/north-mini-code:free"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.indexer: Optional[DocumentIndexer] = None
        self.reranker: Optional[BM25Reranker] = None
        self.filter: Optional[RelevanceFilter] = None
        self.rewriter: Optional[QueryRewriter] = None
        self.knowledge_threshold = 0.4

    def load_index(self, path: str = "index_lab21.json"):
        """Загрузка индекса."""
        self.indexer = DocumentIndexer()
        self.indexer.index_path = path
        self.indexer.load_index()

        self.reranker = BM25Reranker()
        self.reranker.fit(self.indexer.chunks)

        self.filter = RelevanceFilter(threshold=0.3)
        self.rewriter = QueryRewriter(self.indexer)

        print(f"  Индекс: {len(self.indexer.chunks)} чанков")
        print(f"  Порог знаний: {self.knowledge_threshold}")

    def _call_llm(self, messages: list[dict]) -> str:
        """Вызов LLM с retry."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Cited RAG Lab24",
        }
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if "laguna" in self.model:
            data["reasoning"] = {"enabled": False}

        max_retries = 5
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
                    wait = 5 * (2 ** attempt)
                    print(f"    Rate limit, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    return f"[Ошибка LLM: {e}]"
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 3 * (attempt + 1)
                    print(f"    Connection error, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    return f"[Ошибка LLM: {e}]"
        return "[Ошибка LLM: max retries exceeded]"

    def _search_and_rank(self, query: str, top_k: int = 5) -> tuple[list[tuple[float, int]], list[dict]]:
        """Поиск + реранкинг."""
        search_results = self.indexer.search(query, top_k=top_k)

        chunk_id_to_idx = {chunk.chunk_id: i for i, chunk in enumerate(self.indexer.chunks)}
        indices = [chunk_id_to_idx[r["chunk_id"]] for r in search_results]

        chunks = [self.indexer.chunks[i] for i in indices]
        scores = [r["score"] for r in search_results]

        ranked_local = self.reranker.rerank(query, chunks, scores)
        ranked = [(score, indices[local_idx]) for score, local_idx in ranked_local]

        return ranked, search_results

    def _build_cited_prompt(self, question: str, chunks_with_scores: list[tuple[float, int, 'Chunk']]) -> str:
        """Построение промпта с требованием цитат и источников."""
        context_parts = []
        for i, (score, idx, chunk) in enumerate(chunks_with_scores, 1):
            context_parts.append(
                f"[Источник {i}]\n"
                f"  Файл: {chunk.title}\n"
                f"  Раздел: {chunk.section}\n"
                f"  ID: {chunk.chunk_id}\n"
                f"  Релевантность: {score:.2f}\n"
                f"  Текст: {chunk.content}\n"
            )

        context = "\n".join(context_parts)

        prompt = f"""Ты — эксперт по программированию. Отвечай на вопрос пользователя, используя ТОЛЬКО предоставленный контекст.

ПРАВИЛА:
1. Если контекст НЕ содержит ответа на вопрос, напиши: "Я не знаю. Уточните вопрос или предоставьте больше информации."
2. В ответе ОБЯЗАТЕЛЬНО укажи источники в формате: [Источник N]
3. В ответе ОБЯЗАТЕЛЬНО приведи цитаты (дословные фрагменты) из источников
4. Цитаты должны быть заключены в кавычки "..."
5. Если релевантность источника ниже 0.3, не используй его

КОНТЕКСТ:
{context}

ВОПРОС: {question}

ФОРМАТ ОТВЕТА:
Ответ: <твой ответ>

Источники:
- [Источник 1]: <название файла> / <раздел>
- [Источник 2]: <название файла> / <раздел>

Цитаты:
- "цитата из источника 1"
- "цитата из источника 2"
"""
        return prompt

    def _parse_cited_response(self, response: str) -> dict:
        """Парсинг ответа LLM для извлечения источников и цитат."""
        result = {
            "answer": "",
            "sources": [],
            "quotes": [],
            "is_unknown": False,
        }

        # Проверка на "не знаю"
        unknown_patterns = [
            r"я не знаю",
            r"не могу ответить",
            r"уточните вопрос",
            r"недостаточно информации",
        ]
        response_lower = response.lower()
        for pattern in unknown_patterns:
            if re.search(pattern, response_lower):
                result["is_unknown"] = True
                break

        # Извлечение ответа
        answer_match = re.search(r"Ответ:\s*(.+?)(?=\n\nИсточники:|\nИсточники:|$)", response, re.DOTALL)
        if answer_match:
            result["answer"] = answer_match.group(1).strip()
        else:
            result["answer"] = response.split("Источники:")[0].strip()

        # Извлечение источников
        sources_section = re.search(r"Источники:\s*(.+?)(?=\n\nЦитаты:|\nЦитаты:|$)", response, re.DOTALL)
        if sources_section:
            sources_text = sources_section.group(1)
            source_matches = re.findall(r"\[Источник\s*\d+\]:\s*(.+?)(?=\n-|\n\[|$)", sources_text)
            result["sources"] = [s.strip() for s in source_matches if s.strip()]

        # Извлечение цитат
        quotes_section = re.search(r"Цитаты:\s*(.+?)$", response, re.DOTALL)
        if quotes_section:
            quotes_text = quotes_section.group(1)
            quote_matches = re.findall(r'"([^"]+)"', quotes_text)
            result["quotes"] = [q.strip() for q in quote_matches if q.strip()]

        return result

    def ask(self, question: str, top_k: int = 5) -> dict:
        """Запрос с обязательными источниками и цитатами."""
        start = time.time()

        # Поиск и реранкинг
        ranked, search_results = self._search_and_rank(question, top_k=top_k)

        # Фильтрация по порогу
        filtered_ranked = [(score, idx) for score, idx in ranked if score >= self.filter.threshold]

        if not filtered_ranked:
            return {
                "question": question,
                "answer": "Я не знаю. Уточните вопрос или предоставьте больше информации.",
                "sources": [],
                "quotes": [],
                "is_unknown": True,
                "top_k_before": len(ranked),
                "top_k_after": 0,
                "elapsed": round(time.time() - start, 2),
            }

        # Подготовка чанков для промпта
        chunks_with_scores = [(score, idx, self.indexer.chunks[idx]) for score, idx in filtered_ranked[:3]]

        # Построение промпта
        prompt = self._build_cited_prompt(question, chunks_with_scores)

        messages = [
            {"role": "system", "content": "Ты — эксперт по программированию. Отвечай строго по контексту."},
            {"role": "user", "content": prompt},
        ]

        # Вызов LLM
        response = self._call_llm(messages)

        # Парсинг ответа
        parsed = self._parse_cited_response(response)

        elapsed = time.time() - start

        return {
            "question": question,
            "answer": parsed["answer"],
            "sources": parsed["sources"],
            "quotes": parsed["quotes"],
            "is_unknown": parsed["is_unknown"],
            "top_k_before": len(ranked),
            "top_k_after": len(filtered_ranked),
            "elapsed": round(elapsed, 2),
        }


def evaluate_citation_quality(result: dict, question_data: dict) -> dict:
    """Оценка качества цитирования."""
    has_sources = len(result["sources"]) > 0
    has_quotes = len(result["quotes"]) > 0
    is_unknown = result["is_unknown"]

    # Проверка совпадения смысла (через ключевые слова)
    answer_lower = result["answer"].lower()
    quotes_text = " ".join(result["quotes"]).lower()
    keywords = question_data["keywords"]

    found_in_answer = [kw for kw in keywords if kw.lower() in answer_lower]
    found_in_quotes = [kw for kw in keywords if kw.lower() in quotes_text]

    # Совпадение: если ключевые слова есть и в ответе, и в цитатах
    overlap = set(found_in_answer) & set(found_in_quotes)
    semantic_match = len(overlap) > 0

    return {
        "has_sources": has_sources,
        "has_quotes": has_quotes,
        "is_unknown": is_unknown,
        "semantic_match": semantic_match,
        "keywords_in_answer": found_in_answer,
        "keywords_in_quotes": found_in_quotes,
        "keywords_overlap": list(overlap),
    }
