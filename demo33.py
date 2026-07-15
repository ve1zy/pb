"""
Demo: Ассистент поддержки с LLM
"""

import sys
import asyncio
sys.path.insert(0, ".")

from support_assistant import (
    load_docs, build_index, start_mcp, stop_mcp, call_mcp,
    answer_with_context, llm_summarize_ticket, llm_suggest_actions, llm_make_natural,
    CURRENT_USER
)


async def main():
    print("=" * 60)
    print("DEMO: Ассистент поддержки (RAG + MCP + LLM)")
    print("=" * 60)
    
    print("\n📚 Загрузка FAQ...")
    docs = load_docs()
    print(f"   Документов: {len(docs)}")
    
    print("🔨 Построение RAG-индекса...")
    index = build_index(docs)
    print(f"   Q&A блоков: {len(index['chunks'])}")
    
    print("\n📡 Подключение к CRM...")
    await start_mcp()
    print("   ✅ MCP подключен")
    
    # Тестовые сценарии
    print("\n" + "=" * 60)
    print("Тестовые сценарии (RAG + LLM):")
    print("=" * 60)
    
    # Сценарий 1: Вопрос + RAG + LLM
    print(f"\n{'─' * 60}")
    print("❓ Сценарий 1: 'Почему не работает авторизация?'")
    print(f"{'─' * 60}")
    result = await answer_with_context("Почему не работает авторизация?", index)
    print(result)
    
    # Сценарий 2: Тикет + LLM резюме
    print(f"\n{'─' * 60}")
    print("🎫 Сценарий 2: тикет T-001 + LLM резюме")
    print(f"{'─' * 60}")
    ticket = await call_mcp("get_ticket", {"ticket_id": "T-001"})
    print(ticket)
    summary = llm_summarize_ticket(ticket)
    if summary:
        print(f"\n🤖 LLM-резюме:\n{summary}")
    
    # Сценарий 3: Анализ тикета + рекомендации
    print(f"\n{'─' * 60}")
    print("🎯 Сценарий 3: /analyze T-001 — LLM рекомендации")
    print(f"{'─' * 60}")
    # Найдём релевантный FAQ для тикета
    from support_assistant import retrieve
    results = retrieve("авторизация пароль не входит", index, top_k=1)
    faq_context = results[0][0]['answer'] if results else ""
    
    actions = llm_suggest_actions(ticket, faq_context)
    if actions:
        print(f"\n🎯 LLM-рекомендации:\n{actions}")
    
    # Сценарий 4: Другой вопрос
    print(f"\n{'─' * 60}")
    print("❓ Сценарий 4: 'Ошибка 429 Too Many Requests'")
    print(f"{'─' * 60}")
    result = await answer_with_context("Ошибка 429 Too Many Requests", index)
    print(result)
    
    await stop_mcp()
    
    print("\n" + "=" * 60)
    print("✅ Demo завершена (RAG + MCP + LLM)")
    print("=" * 60)
    print("\nИнтерактивный режим:")
    print("  python support_assistant.py")


if __name__ == "__main__":
    asyncio.run(main())
