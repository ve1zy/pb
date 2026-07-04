from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lab24 import CitedRAGAgent, evaluate_citation_quality
from lab22 import BENCHMARK_QUESTIONS

API_KEY = os.getenv("OPENROUTER_API_KEY", "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")


async def benchmark_cited(agent: CitedRAGAgent) -> dict:
    """Бенчмарк цитирования на 10 вопросах."""
    results = []
    for i, q in enumerate(BENCHMARK_QUESTIONS):
        print(f"\n--- Вопрос {i+1}/10: {q['question']} ---")
        result = agent.ask(q["question"], top_k=5)
        eval_data = evaluate_citation_quality(result, q)

        print(f"  Ответ: {result['answer'][:100]}...")
        print(f"  Источники: {len(result['sources'])} ({result['sources'][:2]})")
        print(f"  Цитаты: {len(result['quotes'])}")
        print(f"  Режим 'не знаю': {result['is_unknown']}")
        print(f"  Совпадение смысла: {eval_data['semantic_match']}")
        print(f"  Топ-K: до={result['top_k_before']}, после={result['top_k_after']}")

        results.append({
            "question": q["question"],
            "expectation": q["expectation"],
            "expected_source": q["expected_source"],
            "answer": result["answer"],
            "sources": result["sources"],
            "quotes": result["quotes"],
            "is_unknown": result["is_unknown"],
            "top_k_before": result["top_k_before"],
            "top_k_after": result["top_k_after"],
            "elapsed": result["elapsed"],
            "eval": eval_data,
        })

        if i < len(BENCHMARK_QUESTIONS) - 1:
            await asyncio.sleep(5)

    return {"results": results}


async def main():
    print("=" * 70)
    print("Лабораторная 24: Цитаты, источники и анти-галлюцинации")
    print("=" * 70)

    # 1 — Загрузка индекса
    print("\n1️⃣  Загрузка индекса...")
    agent = CitedRAGAgent(API_KEY)
    agent.load_index()

    # 2 — Демонстрация одного вопроса
    print("\n2️⃣  Демонстрация: один вопрос с цитатами")
    print("-" * 70)
    sample_q = "Что такое event loop в asyncio?"
    print(f"Вопрос: {sample_q}\n")

    result = agent.ask(sample_q, top_k=5)
    print(f"ОТВЕТ:\n{result['answer']}\n")
    print(f"ИСТОЧНИКИ:")
    for src in result["sources"]:
        print(f"  - {src}")
    print(f"\nЦИТАТЫ:")
    for quote in result["quotes"]:
        print(f'  - "{quote}"')
    print(f"\nРежим 'не знаю': {result['is_unknown']}")
    print(f"Топ-K: до={result['top_k_before']}, после={result['top_k_after']}")
    print(f"Время: {result['elapsed']}с")

    await asyncio.sleep(5)

    # 3 — Полный бенчмарк
    print("\n3️⃣  Полный бенчмарк: 10 вопросов")
    print("    (с задержкой 5с между вопросами)")
    await asyncio.sleep(5)

    benchmark = await benchmark_cited(agent)

    # 4 — Статистика качества
    print("\n" + "=" * 70)
    print("СТАТИСТИКА КАЧЕСТВА ЦИТИРОВАНИЯ")
    print("=" * 70)

    total = len(benchmark["results"])
    has_sources_count = sum(1 for r in benchmark["results"] if r["eval"]["has_sources"])
    has_quotes_count = sum(1 for r in benchmark["results"] if r["eval"]["has_quotes"])
    semantic_match_count = sum(1 for r in benchmark["results"] if r["eval"]["semantic_match"])
    unknown_count = sum(1 for r in benchmark["results"] if r["is_unknown"])

    print(f"Всего вопросов: {total}")
    print(f"С источниками: {has_sources_count}/{total} ({has_sources_count/total*100:.0f}%)")
    print(f"С цитатами: {has_quotes_count}/{total} ({has_quotes_count/total*100:.0f}%)")
    print(f"Совпадение смысла: {semantic_match_count}/{total} ({semantic_match_count/total*100:.0f}%)")
    print(f"Режим 'не знаю': {unknown_count}/{total} ({unknown_count/total*100:.0f}%)")

    # 5 — Детальный отчёт
    print("\n" + "=" * 70)
    print("ДЕТАЛЬНЫЙ ОТЧЁТ")
    print("=" * 70)

    for i, r in enumerate(benchmark["results"], 1):
        print(f"\n--- Вопрос {i}: {r['question']} ---")
        print(f"  Ожидание: {r['expectation']}")
        print(f"  Ожидаемый источник: {r['expected_source']}")
        print(f"  Ответ: {r['answer'][:150]}...")
        print(f"  Источники: {r['sources']}")
        print(f"  Цитаты: {r['quotes'][:2]}...")
        print(f"  'Не знаю': {r['is_unknown']}")
        print(f"  Совпадение: {r['eval']['semantic_match']}")
        print(f"  Ключевые в ответе: {r['eval']['keywords_in_answer']}")
        print(f"  Ключевые в цитатах: {r['eval']['keywords_in_quotes']}")

    # 6 — Сохранение результатов
    with open("benchmark_lab24.json", "w", encoding="utf-8") as f:
        json.dump(benchmark, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Результаты сохранены: benchmark_lab24.json")

    print("\n" + "=" * 70)
    print("✅ Лабораторная 24 завершена")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
