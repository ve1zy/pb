"""
Demo: Ассистент разработчика
Показывает работу RAG + MCP без интерактивного ввода
"""

import sys
sys.path.insert(0, ".")

from assistant import load_docs, build_index, answer_question, git_branch, find_project_structure

print("=" * 60)
print("DEMO: Ассистент разработчика")
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

# Демо вопросы
test_questions = [
    ("Какая текущая ветка?", "git"),
    ("Какая структура проекта?", "structure"),
    ("Что такое asyncio в Python?", "rag"),
    ("Как использовать Docker?", "rag"),
    ("Что такое MCP протокол?", "rag"),
]

print("\n" + "=" * 60)
print("Тестовые вопросы:")
print("=" * 60)

for i, (question, qtype) in enumerate(test_questions, 1):
    print(f"\n{'─' * 60}")
    print(f"Вопрос {i}: {question}")
    print(f"{'─' * 60}")
    answer = answer_question(question, index)
    print(answer)

print("\n" + "=" * 60)
print("✅ Demo завершена")
print("=" * 60)
print("\nДля интерактивного режима:")
print("  python assistant.py")
