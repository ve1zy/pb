from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lab25 import RAGChatAgent, run_scenario, SCENARIO_1, SCENARIO_2

API_KEY = os.getenv("OPENROUTER_API_KEY", "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")


async def main():
    print("=" * 70)
    print("Лабораторная 25: Мини-чат с RAG + памятью задачи")
    print("=" * 70)

    # 1. Инициализация агента
    print("\n1️⃣  Инициализация агента...")
    agent = RAGChatAgent(API_KEY)
    agent.load_index()

    # 2. Сценарий 1: asyncio
    print("\n" + "=" * 70)
    print("СЦЕНАРИЙ 1: Изучение asyncio (10 сообщений)")
    print("=" * 70)
    results_1 = run_scenario(agent, SCENARIO_1)

    # 3. Сброс и сценарий 2: FastAPI
    print("\n" + "=" * 70)
    print("СБРОС ЧАТА")
    print("=" * 70)
    agent.reset()
    print("Чат сброшен, память задачи очищена")

    print("\n" + "=" * 70)
    print("СЦЕНАРИЙ 2: Изучение FastAPI (11 сообщений)")
    print("=" * 70)
    results_2 = run_scenario(agent, SCENARIO_2)

    # 4. Анализ результатов
    print("\n" + "=" * 70)
    print("АНАЛИЗ РЕЗУЛЬТАТОВ")
    print("=" * 70)

    def analyze_scenario(name, results):
        print(f"\n{name}:")
        total = len(results)
        with_sources = sum(1 for r in results if r["sources"])
        print(f"  Всего сообщений: {total}")
        print(f"  С источниками: {with_sources}/{total} ({with_sources/total*100:.0f}%)")
        print(f"  Без источников: {total - with_sources}/{total}")

        # Проверка памяти задачи
        last_memory = results[-1]["task_memory"]
        if "Цель:" in last_memory:
            print(f"  ✅ Цель сохранена в памяти")
        if "Уточнения:" in last_memory:
            print(f"  ✅ Уточнения зафиксированы")
        if "Термины:" in last_memory:
            print(f"  ✅ Термины извлечены")

    analyze_scenario("Сценарий 1 (asyncio)", results_1)
    analyze_scenario("Сценарий 2 (FastAPI)", results_2)

    # 5. Финальная проверка
    print("\n" + "=" * 70)
    print("ПРОВЕРКА: Источники в каждом ответе")
    print("=" * 70)

    all_results = results_1 + results_2
    all_with_sources = sum(1 for r in all_results if r["sources"])
    total_messages = len(all_results)

    print(f"Всего сообщений: {total_messages}")
    print(f"С источниками: {all_with_sources}/{total_messages}")
    print(f"Без источников: {total_messages - all_with_sources}/{total_messages}")

    if all_with_sources == total_messages:
        print("✅ Все ответы содержат источники")
    else:
        print(f"⚠️  {total_messages - all_with_sources} ответов без источников")

    print("\n" + "=" * 70)
    print("✅ Лабораторная 25 завершена")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
