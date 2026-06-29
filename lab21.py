from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Chunk:
    chunk_id: str
    source: str
    title: str
    section: str
    content: str
    metadata: dict


class FixedSizeChunker:
    """Chunking по фиксированному размеру с перекрытием."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, source: str, title: str) -> list[Chunk]:
        chunks = []
        words = text.split()
        i = 0
        chunk_idx = 0

        while i < len(words):
            end = min(i + self.chunk_size, len(words))
            content = " ".join(words[i:end])

            if content.strip():
                chunk = Chunk(
                    chunk_id=f"{source}:{chunk_idx}",
                    source=source,
                    title=title,
                    section="fixed",
                    content=content,
                    metadata={
                        "strategy": "fixed_size",
                        "chunk_size": self.chunk_size,
                        "overlap": self.overlap,
                        "word_count": len(content.split()),
                        "position": f"{i}-{end}",
                    },
                )
                chunks.append(chunk)
                chunk_idx += 1

            i += self.chunk_size - self.overlap

        return chunks


class StructureChunker:
    """Chunking по структуре (заголовки, разделы)."""

    def chunk(self, text: str, source: str, title: str) -> list[Chunk]:
        chunks = []
        sections = re.split(r"\n(?=#{1,3}\s)", text)

        for idx, section in enumerate(sections):
            lines = section.strip().split("\n", 1)
            header = lines[0].strip().lstrip("#").strip() if lines else f"Section {idx}"
            content = lines[1].strip() if len(lines) > 1 else ""

            if content and len(content.split()) > 10:
                chunk = Chunk(
                    chunk_id=f"{source}:struct:{idx}",
                    source=source,
                    title=title,
                    section=header,
                    content=content,
                    metadata={
                        "strategy": "structure",
                        "word_count": len(content.split()),
                        "section_index": idx,
                    },
                )
                chunks.append(chunk)

        return chunks


class DocumentIndexer:
    """Индексатор документов с локальными TF-IDF эмбеддингами."""

    def __init__(self, api_key: str = "", model: str = "tf-idf-local"):
        self.api_key = api_key
        self.model = model
        self.chunks: list[Chunk] = []
        self.embeddings: list[list[float]] = []
        self.index_path = "index_lab21.json"
        self.vocabulary: dict[str, int] = {}
        self.idf: dict[str, float] = {}

    def add_file(self, filepath: str, title: Optional[str] = None):
        if not os.path.exists(filepath):
            print(f"  ❌ Файл не найден: {filepath}")
            return

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        title = title or os.path.basename(filepath)
        print(f"  📄 {filepath} ({len(text)} символов, {len(text.split())} слов)")
        return text, title

    def index_files(self, filepaths: list[str], chunker: str = "fixed"):
        """Индексация файлов."""
        print(f"\n📚 Индексация ({len(filepaths)} файлов, стратегия: {chunker})...")

        if chunker == "fixed":
            chunker_obj = FixedSizeChunker(chunk_size=300, overlap=50)
        else:
            chunker_obj = StructureChunker()

        for filepath in filepaths:
            result = self.add_file(filepath)
            if result:
                text, title = result
                chunks = chunker_obj.chunk(text, filepath, title)
                self.chunks.extend(chunks)
                print(f"     → {len(chunks)} чанков")

        print(f"\n✅ Всего чанков: {len(self.chunks)}")
        return len(self.chunks)

    def _tokenize(self, text: str) -> list[str]:
        """Токенизация текста."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return text.split()

    def generate_embeddings(self):
        """Генерация TF-IDF эмбеддингов локально."""
        print(f"\n🔢 Генерация TF-IDF эмбеддингов ({len(self.chunks)} чанков)...")

        # Построение словаря
        doc_freq = Counter()
        all_tokens = []

        for chunk in self.chunks:
            tokens = self._tokenize(chunk.content)
            unique_tokens = set(tokens)
            all_tokens.append(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1

        # Построение vocabulary
        self.vocabulary = {token: idx for idx, token in enumerate(doc_freq.keys())}
        print(f"   Словарь: {len(self.vocabulary)} уникальных токенов")

        # Вычисление IDF
        n_docs = len(self.chunks)
        self.idf = {
            token: math.log(n_docs / (1 + freq)) + 1
            for token, freq in doc_freq.items()
        }

        # Генерация TF-IDF векторов
        for i, (chunk, tokens) in enumerate(zip(self.chunks, all_tokens)):
            tf = Counter(tokens)
            vector = [0.0] * len(self.vocabulary)

            for token, count in tf.items():
                if token in self.vocabulary:
                    idx = self.vocabulary[token]
                    tfidf = (count / len(tokens)) * self.idf[token]
                    vector[idx] = tfidf

            self.embeddings.append(vector)

            if (i + 1) % 5 == 0:
                print(f"   {i + 1}/{len(self.chunks)}")

        print(f"✅ Эмбеддинги сгенерированы: {len(self.embeddings)} (размерность: {len(self.vocabulary)})")

    def save_index(self):
        """Сохранение индекса в JSON."""
        index_data = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_chunks": len(self.chunks),
            "model": self.model,
            "vocabulary": self.vocabulary,
            "idf": self.idf,
            "chunks": [asdict(c) for c in self.chunks],
            "embeddings": self.embeddings,
        }

        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Индекс сохранён: {self.index_path}")

    def load_index(self):
        """Загрузка индекса из JSON."""
        with open(self.index_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.chunks = [Chunk(**c) for c in data["chunks"]]
        self.embeddings = data["embeddings"]
        self.vocabulary = data.get("vocabulary", {})
        self.idf = data.get("idf", {})
        print(f"✅ Индекс загружен: {len(self.chunks)} чанков, словарь: {len(self.vocabulary)}")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Поиск по косинусному сходству (TF-IDF)."""
        if not self.embeddings:
            print("❌ Индекс пуст")
            return []

        # TF-IDF вектор для запроса
        tokens = self._tokenize(query)
        tf = Counter(tokens)
        query_vector = [0.0] * len(self.vocabulary)

        for token, count in tf.items():
            if token in self.vocabulary:
                idx = self.vocabulary[token]
                tfidf = (count / len(tokens)) * self.idf.get(token, 1.0)
                query_vector[idx] = tfidf

        scores = []
        for i, emb in enumerate(self.embeddings):
            score = self._cosine_similarity(query_vector, emb)
            scores.append((score, i))

        scores.sort(reverse=True)
        results = []

        for score, idx in scores[:top_k]:
            chunk = self.chunks[idx]
            results.append({
                "score": round(score, 4),
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "title": chunk.title,
                "section": chunk.section,
                "content": chunk.content[:200] + "...",
                "metadata": chunk.metadata,
            })

        return results

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0

    def compare_strategies(self, filepaths: list[str]) -> dict:
        """Сравнение стратегий chunking."""
        print("\n" + "=" * 60)
        print("СРАВНЕНИЕ СТРАТЕГИЙ CHUNKING")
        print("=" * 60)

        results = {}

        for strategy in ["fixed", "structure"]:
            indexer = DocumentIndexer()
            indexer.index_files(filepaths, chunker=strategy)

            total_words = sum(len(c.content.split()) for c in indexer.chunks)
            avg_words = total_words / len(indexer.chunks) if indexer.chunks else 0

            results[strategy] = {
                "total_chunks": len(indexer.chunks),
                "total_words": total_words,
                "avg_words_per_chunk": round(avg_words, 1),
                "chunks": indexer.chunks,
            }

            print(f"\n📊 {strategy.upper()}:")
            print(f"   Чанков: {len(indexer.chunks)}")
            print(f"   Всего слов: {total_words}")
            print(f"   Среднее слов/чанк: {avg_words:.1f}")

        print("\n" + "=" * 60)
        print("ВЫВОД:")
        print(f"  Fixed: {results['fixed']['total_chunks']} чанков, {results['fixed']['avg_words_per_chunk']} слов/чанк")
        print(f"  Structure: {results['structure']['total_chunks']} чанков, {results['structure']['avg_words_per_chunk']} слов/чанк")
        print("=" * 60)

        return results
