from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lab22 import RAGAgent, BENCHMARK_QUESTIONS, run_benchmark


API_KEY = os.getenv("OPENROUTER_API_KEY", "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")


async def main():
    print("=" * 70)
    print("Лабораторная 22: RAG-агент (Plain vs RAG)")
    print("=" * 70)

    # 1 — Создание тестовых документов (если нет)
    docs_dir = "docs_lab21"
    if not os.path.exists(docs_dir):
        print("\n1️⃣  Создание тестовых документов...")
        from demo21 import create_test_docs
        create_test_docs()
    else:
        print(f"\n1️⃣  Документы найдены: {docs_dir}/")

    # 2 — Построение индекса
    print("\n2️⃣  Построение индекса...")
    agent = RAGAgent(API_KEY)
    filepaths = [
        f"{docs_dir}/python_async.md",
        f"{docs_dir}/fastapi_guide.md",
        f"{docs_dir}/mcp_protocol.md",
        f"{docs_dir}/sqlite_guide.md",
        f"{docs_dir}/ml_basics.md",
        f"{docs_dir}/docker_basics.md",
        f"{docs_dir}/git_workflow.md",
        f"{docs_dir}/testing_python.md",
    ]
    agent.build_index(filepaths, chunker="fixed")

    # 3 — Загрузка индекса
    print("\n3️⃣  Загрузка индекса...")
    agent.load_index()

    # 4 — Демонстрация: один вопрос plain vs rag
    print("\n4️⃣  Демонстрация: Plain vs RAG на примере одного вопроса")
    print("-" * 70)
    sample_q = "Что такое event loop в asyncio?"
    print(f"Вопрос: {sample_q}\n")

    print("📝 PLAIN (без RAG):")
    plain = agent.ask_plain(sample_q)
    print(f"  Ответ: {plain['answer'][:200]}...")
    print(f"  Время: {plain['elapsed']}с\n")

    print("📝 RAG (с поиском контекста):")
    rag = agent.ask_rag(sample_q)
    print(f"  Ответ: {rag['answer'][:200]}...")
    print(f"  Время: {rag['elapsed']}с")
    print(f"  Источники: {[s['title'] for s in rag['sources']]}")
    print(f"  Контекст: {rag.get('context_length', 0)} символов\n")

    # 5 — Полный бенчмарк
    print("\n5️⃣  Запуск полного бенчмарка (10 вопросов)...")
    print("    (с задержкой 2с между вопросами для избежания rate limit)")
    await asyncio.sleep(3)  # Extra delay before benchmark
    benchmark = await run_benchmark(agent)

    # 6 — Детальный отчёт
    print("\n" + "=" * 70)
    print("ДЕТАЛЬНЫЙ ОТЧЁТ")
    print("=" * 70)

    for i, r in enumerate(benchmark["results"], 1):
        print(f"\n--- {i}. {r['question']} ---")
        print(f"  Ожидание: {r['expectation']}")
        print(f"  Ожидаемый источник: {r['expected_source']}")
        print(f"  Plain score: {r['plain_score']:.0%} ({r['plain_eval']['found_keywords']})")
        print(f"  RAG score:   {r['rag_score']:.0%} ({r['rag_eval']['found_keywords']})")
        print(f"  RAG источники: {r['rag_sources']}")
        delta = r['rag_score'] - r['plain_score']
        if delta > 0:
            print(f"  ✅ RAG лучше: +{delta:.0%}")
        elif delta < 0:
            print(f"  ❌ RAG хуже: {delta:.0%}")
        else:
            print(f"  ⚖️  Равно: 0%")

    # 7 — Итоговая статистика
    print("\n" + "=" * 70)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 70)
    print(f"  Средний Plain score: {benchmark['avg_plain']:.0%}")
    print(f"  Средний RAG score:   {benchmark['avg_rag']:.0%}")
    print(f"  Прирост:             {benchmark['improvement']:+.0%}")

    rag_wins = sum(1 for r in benchmark["results"] if r['rag_score'] > r['plain_score'])
    plain_wins = sum(1 for r in benchmark["results"] if r['plain_score'] > r['rag_score'])
    ties = sum(1 for r in benchmark["results"] if r['rag_score'] == r['plain_score'])

    print(f"\n  RAG лучше: {rag_wins}/10")
    print(f"  Plain лучше: {plain_wins}/10")
    print(f"  Ничья: {ties}/10")
    print("=" * 70)

    # 8 — Сохранение результатов
    import json
    with open("benchmark_lab22.json", "w", encoding="utf-8") as f:
        json.dump(benchmark, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Результаты сохранены: benchmark_lab22.json")


if __name__ == "__main__":
    asyncio.run(main())
