"""
Demo: Ассистент для работы с файлами
"""

import sys
import asyncio
sys.path.insert(0, ".")

from file_assistant import (
    start_mcp, stop_mcp,
    scenario_find_usages, scenario_search_code,
    scenario_update_docs, scenario_generate_changelog,
    scenario_check_invariants, call_mcp
)


async def main():
    print("=" * 60)
    print("DEMO: Ассистент для работы с файлами")
    print("=" * 60)
    
    print("\n📡 Подключение к MCP...")
    await start_mcp()
    print("   ✅ MCP подключен")
    
    # Сценарий 1: Поиск использований
    print("\n" + "─" * 60)
    print("📌 Сценарий 1: /find ctransformers")
    print("─" * 60)
    result = await scenario_find_usages("ctransformers")
    print(result[:500])
    
    # Сценарий 2: Поиск по коду
    print("\n" + "─" * 60)
    print("📌 Сценарий 2: /search 'def.*ask'")
    print("─" * 60)
    result = await scenario_search_code(r"def\s+ask")
    print(result[:500])
    
    # Сценарий 3: Проверка инвариантов
    print("\n" + "─" * 60)
    print("📌 Сценарий 3: /check — проверка инвариантов")
    print("─" * 60)
    result = await scenario_check_invariants()
    print(result[:800])
    
    # Сценарий 4: Генерация CHANGELOG
    print("\n" + "─" * 60)
    print("📌 Сценарий 4: /changelog — генерация CHANGELOG.md")
    print("─" * 60)
    result = await scenario_generate_changelog()
    print(result[:500])
    
    # Сценарий 5: Обновление документации
    print("\n" + "─" * 60)
    print("📌 Сценарий 5: /update-docs — обновление API.md")
    print("─" * 60)
    result = await scenario_update_docs()
    print(result[:600])
    
    await stop_mcp()
    
    print("\n" + "=" * 60)
    print("✅ Demo завершена")
    print("=" * 60)
    print("\nСозданные файлы:")
    print("  API.md      — документация функций")
    print("  CHANGELOG.md — история коммитов")
    print("\nИнтерактивный режим:")
    print("  python file_assistant.py")


if __name__ == "__main__":
    asyncio.run(main())
