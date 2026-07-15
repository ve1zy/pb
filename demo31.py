"""
Demo: Ассистент разработчика с MCP
Показывает работу RAG + MCP без интерактивного ввода
"""

import sys
import asyncio
sys.path.insert(0, ".")

from assistant import load_docs, build_index, start_mcp, stop_mcp, call_mcp


async def main():
    print("=" * 60)
    print("DEMO: Ассистент разработчика (RAG + MCP)")
    print("=" * 60)
    
    # Загружаем документацию
    print("\n📚 Загрузка документации...")
    docs = load_docs()
    print(f"   Загружено: {len(docs)} документов")
    
    # Строим индекс
    print("🔨 Построение RAG-индекса...")
    index = build_index(docs)
    print(f"   Чанков: {len(index['chunks'])}")
    print(f"   Словарь: {len(index['vocab'])} слов")
    
    # Запускаем MCP
    print("\n📡 Запуск MCP-сервера...")
    await start_mcp()
    
    # Тестируем MCP-инструменты
    print("\n--- MCP-инструменты ---")
    
    branch = await call_mcp("git_branch")
    print(f"\n🔧 git_branch:\n{branch}")
    
    files = await call_mcp("list_files", {"extension": ".py"})
    py_count = files.split("Всего: ")[-1] if "Всего:" in files else "?"
    print(f"\n📂 list_files (.py): найдено файлов: {py_count}")
    
    diff = await call_mcp("git_diff", {"commits": 2})
    print(f"\n📝 git_diff (2 коммита):\n{diff[:300]}...")
    
    # Тестируем RAG
    print("\n--- RAG поиск ---")
    from assistant import retrieve
    
    for query in ["Docker", "asyncio", "MCP"]:
        results = retrieve(query, index, top_k=1)
        if results:
            chunk, score = results[0]
            print(f"\n🔍 '{query}' → {chunk['source']} (score: {score:.2f})")
    
    # Останавливаем MCP
    await stop_mcp()
    
    print("\n" + "=" * 60)
    print("✅ Demo завершена (MCP интегрирован)")
    print("=" * 60)
    print("\nДля интерактивного режима:")
    print("  python assistant.py")


if __name__ == "__main__":
    asyncio.run(main())
