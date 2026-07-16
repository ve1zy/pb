# API Reference

Автоматически сгенерировано ассистентом.

## Функции

### `load_docs()` (assistant.py)

Загружает README и docs/

### `build_index()` (assistant.py)

Строит TF-IDF индекс

### `retrieve()` (assistant.py)

Поиск релевантных чанков

### `start_mcp()` (assistant.py)

Запускает MCP-сервер и возвращает сессию

### `stop_mcp()` (assistant.py)

Останавливает MCP-сессию

### `call_mcp()` (assistant.py)

Вызывает MCP-инструмент и возвращает текст результата

### `find_project_structure()` (assistant.py)

Описание структуры проекта

### `answer_question()` (assistant.py)

Отвечает на вопрос используя RAG + MCP

### `ask()` (cli_llm.py)

Запрос к локальной LLM.

### `create_test_docs()` (demo21.py)

Создание тестовых документов для индексации.

### `benchmark_mode()` (demo23.py)

Бенчмарк одного режима на 10 вопросах.

