from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lab23 import EnhancedRAGAgent
from lab22 import BENCHMARK_QUESTIONS, evaluate_answer

API_KEY = os.getenv("OPENROUTER_API_KEY", "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")


async def benchmark_mode(agent: EnhancedRAGAgent, mode: str) -> dict:
    """Бенчмарк одного режима на 10 вопросах."""
    results = []
    for i, q in enumerate(BENCHMARK_QUESTIONS):
        result = agent.ask(q["question"], mode=mode, top_k=5)
        eval_data = evaluate_answer(result["answer"], q)
        results.append({
            "question": q["question"],
            "answer": result["answer"],
            "score": eval_data["score"],
            "found_keywords": eval_data["found_keywords"],
            "sources": result["sources"],
            "top_k_before": result.get("top_k_before", 0),
            "top_k_after": result.get("top_k_after", 0),
            "elapsed": result["elapsed"],
        })
        if i < len(BENCHMARK_QUESTIONS) - 1:
            await asyncio.sleep(5)
    return {"mode": mode, "results": results}


async def main():
    print("=" * 70)
    print("Лабораторная 23: Реранкинг и фильтрация в RAG")
    print("=" * 70)

    # 1 — Загрузка индекса и компонентов
    print("\n1️⃣  Загрузка индекса и компонентов...")
    agent = EnhancedRAGAgent(API_KEY)
    agent.load_index()

    # 2 — Демонстрация одного вопроса во всех режимах
    print("\n2️⃣  Демонстрация: один вопрос во всех режимах")
    print("-" * 70)
    sample_q = "Что такое event loop в asyncio?"
    print(f"Вопрос: {sample_q}\n")

    modes = ["plain", "rag", "rag_filter", "rag_rewrite", "rag_full"]
    for i, mode in enumerate(modes):
        print(f"📝 Режим: {mode}")
        result = agent.ask(sample_q, mode=mode, top_k=5)
        answer_preview = result["answer"][:150].replace("\n", " ")
        print(f"  Ответ: {answer_preview}...")
        if result["sources"]:
            print(f"  Источники: {[s['title'] for s in result['sources']]}")
        print(f"  Топ-K: до={result.get('top_k_before', 0)}, после={result.get('top_k_after', 0)}")
        print(f"  Время: {result['elapsed']}с\n")
        if i < len(modes) - 1:
            await asyncio.sleep(5)

    # 3 — Полный бенчмарк всех режимов
    print("\n3️⃣  Полный бенчмарк: 5 режимов × 10 вопросов")
    print("    (с задержкой 5с между вопросами, 10с между режимами)")
    await asyncio.sleep(10)

    all_benchmarks = {}
    for i, mode in enumerate(modes):
        print(f"\n--- Режим: {mode} ---")
        benchmark = await benchmark_mode(agent, mode)
        all_benchmarks[mode] = benchmark

        scores = [r["score"] for r in benchmark["results"]]
        avg = sum(scores) / len(scores)
        print(f"  Средний score: {avg:.2f}")

        if i < len(modes) - 1:
            await asyncio.sleep(10)

    # 4 — Сравнительная таблица
    print("\n" + "=" * 70)
    print("СРАВНИТЕЛЬНАЯ ТАБЛИЦА РЕЖИМОВ")
    print("=" * 70)
    print(f"{'Режим':<15} {'Avg Score':<12} {'Win/10':<10} {'Avg K_before':<15} {'Avg K_after':<15}")
    print("-" * 70)

    for mode in modes:
        benchmark = all_benchmarks[mode]
        scores = [r["score"] for r in benchmark["results"]]
        avg_score = sum(scores) / len(scores)
        wins = sum(1 for s in scores if s >= 0.75)

        if mode == "plain":
            print(f"{mode:<15} {avg_score:<12.2f} {wins:<10} {'—':<15} {'—':<15}")
        else:
            k_before_list = [r["top_k_before"] for r in benchmark["results"]]
            k_after_list = [r["top_k_after"] for r in benchmark["results"]]
            avg_k_before = sum(k_before_list) / len(k_before_list)
            avg_k_after = sum(k_after_list) / len(k_after_list)
            print(f"{mode:<15} {avg_score:<12.2f} {wins:<10} {avg_k_before:<15.1f} {avg_k_after:<15.1f}")

    # 5 — Детальный отчёт по вопросам
    print("\n" + "=" * 70)
    print("ДЕТАЛЬНЫЙ ОТЧЁТ ПО ВОПРОСАМ")
    print("=" * 70)

    for i, q in enumerate(BENCHMARK_QUESTIONS, 1):
        print(f"\n--- Вопрос {i}: {q['question']} ---")
        print(f"  Ожидание: {q['expectation']}")
        print(f"  Источники: {q['expected_source']}")

        for mode in modes:
            benchmark = all_benchmarks[mode]
            result = benchmark["results"][i - 1]
            score = result["score"]
            keywords = result["found_keywords"]
            print(f"  {mode:<15}: {score:.0%} ({keywords})")

    # 6 — Итоговая статистика
    print("\n" + "=" * 70)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 70)

    baseline = all_benchmarks["rag"]
    baseline_scores = [r["score"] for r in baseline["results"]]
    baseline_avg = sum(baseline_scores) / len(baseline_scores)

    for mode in ["rag_filter", "rag_rewrite", "rag_full"]:
        benchmark = all_benchmarks[mode]
        scores = [r["score"] for r in benchmark["results"]]
        avg = sum(scores) / len(scores)
        delta = avg - baseline_avg
        print(f"  {mode:<15}: {avg:.2f} (Δ {delta:+.2f} vs базовый RAG)")

    # 7 — Сохранение результатов
    with open("benchmark_lab23.json", "w", encoding="utf-8") as f:
        json.dump(all_benchmarks, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Результаты сохранены: benchmark_lab23.json")

    print("\n" + "=" * 70)
    print("✅ Лабораторная 23 завершена")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
