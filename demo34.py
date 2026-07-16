"""
Demo: Ассистент для работы с файлами (с LLM-агентом)
"""

import sys
import asyncio
sys.path.insert(0, ".")

from file_assistant import (
    start_mcp, stop_mcp, ai_agent,
    scenario_find_usages, scenario_search_code,
    scenario_update_docs, scenario_generate_changelog,
    scenario_check_invariants, call_mcp
)


async def main():
    print("=" * 60)
    print("DEMO: Ассистент для работы с файлами (AI-агент)")
    print("=" * 60)
    
    print("\n📡 Подключение к MCP...")
    await start_mcp()
    print("   ✅ MCP подключен")
    
    # Сценарии через команды
    print("\n" + "─" * 60)
    print("📌 Команда /find ctransformers")
    print("─" * 60)
    result = await scenario_find_usages("ctransformers")
    print(result[:400])
    
    print("\n" + "─" * 60)
    print("📌 Команда /check")
    print("─" * 60)
    result = await scenario_check_invariants()
    print(result[:400])
    
    print("\n" + "─" * 60)
    print("📌 Команда /changelog")
    print("─" * 60)
    result = await scenario_generate_changelog()
    print(result[:400])
    
    # AI-агент на естественном языке
    print("\n" + "─" * 60)
    print("🤖 AI-агент: 'найди где у нас используется ctransformers'")
    print("─" * 60)
    result = await ai_agent("найди где у нас используется ctransformers")
    print(result[:800])
    
    print("\n" + "─" * 60)
    print("🤖 AI-агент: 'проверь все python файлы на наличие docstring'")
    print("─" * 60)
    result = await ai_agent("проверь все python файлы на наличие docstring")
    print(result[:800])
    
    await stop_mcp()
    
    print("\n" + "=" * 60)
    print("✅ Demo завершена")
    print("=" * 60)
    print("\nИнтерактивный режим:")
    print("  python file_assistant.py")


if __name__ == "__main__":
    asyncio.run(main())
