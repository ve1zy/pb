"""
Demo: Ассистент поддержки
"""

import sys
import asyncio
sys.path.insert(0, ".")

from support_assistant import (
    load_docs, build_index, start_mcp, stop_mcp, call_mcp,
    answer_with_context, CURRENT_USER
)


async def main():
    print("=" * 60)
    print("DEMO: Ассистент поддержки (RAG + MCP)")
    print("=" * 60)
    
    # Загружаем FAQ
    print("\n📚 Загрузка FAQ...")
    docs = load_docs()
    print(f"   Документов: {len(docs)}")
    
    print("🔨 Построение RAG-индекса...")
    index = build_index(docs)
    print(f"   Q&A блоков: {len(index['chunks'])}")
    
    # MCP
    print("\n📡 Подключение к CRM...")
    await start_mcp()
    print("   ✅ MCP подключен")
    
    # Показываем все тикеты
    print("\n--- Все тикеты в CRM ---")
    all_tickets = await call_mcp("list_tickets", {})
    print(all_tickets[:600])
    
    # Тикеты текущего пользователя
    print(f"\n--- Тикеты пользователя {CURRENT_USER} ---")
    user_tickets = await call_mcp("list_tickets", {"user_email": CURRENT_USER})
    print(user_tickets)
    
    # Тестовые вопросы
    print("\n" + "=" * 60)
    print("Тестовые сценарии:")
    print("=" * 60)
    
    questions = [
        "Почему не работает авторизация?",
        "Ошибка 429 Too Many Requests",
        "Как оплатить подписку?",
        "тикет T-001",
    ]
    
    for q in questions:
        print(f"\n{'─' * 60}")
        print(f"❓ {q}")
        print(f"{'─' * 60}")
        result = await answer_with_context(q, index)
        print(result)
    
    await stop_mcp()
    
    print("\n" + "=" * 60)
    print("✅ Demo завершена")
    print("=" * 60)
    print("\nИнтерактивный режим:")
    print("  python support_assistant.py")


if __name__ == "__main__":
    asyncio.run(main())
