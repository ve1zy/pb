from __future__ import annotations

import math
import re
import time
from collections import Counter
from typing import Optional

import requests

from lab21 import DocumentIndexer, Chunk
from lab22 import BENCHMARK_QUESTIONS, evaluate_answer


class BM25Reranker:
    """Реранкер на основе BM25 — более точный метод ранжирования."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.avg_dl = 0.0
        self.doc_freqs: dict[str, int] = {}
        self.n_docs = 0

    def fit(self, chunks: list[Chunk]):
        """Обучение BM25 на корпусе чанков."""
        self.n_docs = len(chunks)
        doc_lengths = []
        self.doc_freqs = {}

        for chunk in chunks:
            tokens = self._tokenize(chunk.content)
            doc_lengths.append(len(tokens))
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avg_dl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return text.split()

    def score(self, query: str, chunk: Chunk) -> float:
        """Вычисление BM25 score для пары query-chunk."""
        tokens = self._tokenize(chunk.content)
        tf = Counter(tokens)
        dl = len(tokens)

        score = 0.0
        query_tokens = self._tokenize(query)

        for token in query_tokens:
            if token in self.doc_freqs:
                df = self.doc_freqs[token]
                idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
                freq = tf.get(token, 0)
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                score += idf * numerator / denominator

        return score

    def rerank(self, query: str, chunks: list[Chunk], scores: list[float]) -> list[tuple[float, int]]:
        """Реранкинг: возвращает (new_score, original_index) отсортированные."""
        new_scores = []
        for i, chunk in enumerate(chunks):
            bm25_score = self.score(query, chunk)
            combined = 0.5 * scores[i] + 0.5 * bm25_score
            new_scores.append((combined, i))

        new_scores.sort(reverse=True)
        return new_scores


class RelevanceFilter:
    """Фильтр релевантности по порогу."""

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold

    def filter(self, ranked: list[tuple[float, int]]) -> list[tuple[float, int]]:
        """Отсечение результатов ниже порога."""
        return [(score, idx) for score, idx in ranked if score >= self.threshold]


class QueryRewriter:
    """Расширение запроса ключевыми словами."""

    def __init__(self, indexer: DocumentIndexer):
        self.indexer = indexer

    def expand(self, query: str, top_k: int = 2) -> str:
        """Расширение запроса через ключевые слова из топ-K документов."""
        results = self.indexer.search(query, top_k=top_k)

        all_text = " ".join(r["content"] for r in results)
        tokens = self.indexer._tokenize(all_text)
        stopwords = {"и", "в", "на", "с", "по", "для", "от", "из", "у", "к", "о", "за", "не", "что", "это", "как"}
        freq = Counter(w for w in tokens if len(w) > 3 and w not in stopwords)
        top_words = [w for w, _ in freq.most_common(5)]

        expanded = f"{query} {' '.join(top_words)}"
        return expanded


class EnhancedRAGAgent:
    """Улучшенный RAG-агент с 4 режимами."""

    def __init__(self, api_key: str, model: str = "cohere/north-mini-code:free"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.indexer: Optional[DocumentIndexer] = None
        self.reranker: Optional[BM25Reranker] = None
        self.filter: Optional[RelevanceFilter] = None
        self.rewriter: Optional[QueryRewriter] = None

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
        print(f"  BM25 reranker: обучен")
        print(f"  Filter: threshold={self.filter.threshold}")
        print(f"  Rewriter: готов")

    def _call_llm(self, messages: list[dict]) -> str:
        """Вызов LLM с retry."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Enhanced RAG Lab23",
        }
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
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
                return f"[Ошибка LLM: {e}]"
        return "[Ошибка LLM: max retries exceeded]"

    def _search_and_rank(self, query: str, top_k: int = 5) -> tuple[list[tuple[float, int]], list[dict]]:
        """Поиск + реранкинг. Возвращает (ranked_indices_in_indexer, search_results)."""
        search_results = self.indexer.search(query, top_k=top_k)

        # Маппинг chunk_id к индексу в self.indexer.chunks
        chunk_id_to_idx = {chunk.chunk_id: i for i, chunk in enumerate(self.indexer.chunks)}
        indices = [chunk_id_to_idx[r["chunk_id"]] for r in search_results]
        
        chunks = [self.indexer.chunks[i] for i in indices]
        scores = [r["score"] for r in search_results]

        # Реранкинг возвращает (score, local_index) где local_index — индекс в chunks
        ranked_local = self.reranker.rerank(query, chunks, scores)
        
        # Маппим локальные индексы обратно к индексам в self.indexer.chunks
        ranked = [(score, indices[local_idx]) for score, local_idx in ranked_local]
        
        return ranked, search_results

    def ask(self, question: str, mode: str = "rag", top_k: int = 5) -> dict:
        """
        Режимы:
        - plain: без RAG
        - rag: базовый RAG (поиск → LLM)
        - rag_filter: RAG + фильтр по порогу
        - rag_rewrite: RAG + расширение запроса
        - rag_full: RAG + фильтр + расширение запроса
        """
        start = time.time()

        if mode == "plain":
            messages = [
                {"role": "system", "content": "Ты — эксперт по программированию. Отвечай кратко и по делу."},
                {"role": "user", "content": question},
            ]
            answer = self._call_llm(messages)
            elapsed = time.time() - start
            return {
                "mode": mode,
                "question": question,
                "answer": answer,
                "sources": [],
                "elapsed": round(elapsed, 2),
                "top_k_before": 0,
                "top_k_after": 0,
            }

        # RAG-режимы
        actual_query = question
        if mode in ("rag_rewrite", "rag_full"):
            actual_query = self.rewriter.expand(question)

        ranked, search_results = self._search_and_rank(actual_query, top_k=top_k)
        top_k_before = len(ranked)

        if mode in ("rag_filter", "rag_full"):
            ranked = self.filter.filter(ranked)

        top_k_after = len(ranked)

        if not ranked:
            return {
                "mode": mode,
                "question": question,
                "answer": "[Нет релевантных источников после фильтрации]",
                "sources": [],
                "elapsed": round(time.time() - start, 2),
                "top_k_before": top_k_before,
                "top_k_after": top_k_after,
            }

        context_parts = []
        sources = []
        for rank, (score, idx) in enumerate(ranked[:3], 1):
            chunk = self.indexer.chunks[idx]
            context_parts.append(f"[Источник {rank}: {chunk.title} / {chunk.section}]\n{chunk.content}")
            sources.append({
                "rank": rank,
                "score": round(score, 4),
                "title": chunk.title,
                "section": chunk.section,
                "chunk_id": chunk.chunk_id,
            })

        context = "\n\n---\n\n".join(context_parts)

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

        answer = self._call_llm(messages)
        elapsed = time.time() - start

        return {
            "mode": mode,
            "question": question,
            "answer": answer,
            "sources": sources,
            "elapsed": round(elapsed, 2),
            "top_k_before": top_k_before,
            "top_k_after": top_k_after,
        }
