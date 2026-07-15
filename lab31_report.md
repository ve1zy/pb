# Lab 31: Developer Assistant (RAG + MCP)

## Статус: ✅ Полностью реализовано

Ассистент разработчика с:
- RAG по README + docs/ (TF-IDF)
- MCP-сервер для git (GitPython, без subprocess)
- MCP-клиент в ассистенте

## Архитектура

```
┌──────────────────┐
│   Пользователь   │
│      /help       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     stdio     ┌──────────────────┐
│   assistant.py   │ ◄──────────► │ mcp_git_server.py│
│                  │   JSON-RPC    │                  │
│  ┌────────────┐  │               │  ┌────────────┐  │
│  │ RAG        │  │               │  │ GitPython  │  │
│  │ (TF-IDF)   │  │               │  │ (repo.xxx) │  │
│  └────────────┘  │               │  └────────────┘  │
│  ┌────────────┐  │               │  ┌────────────┐  │
│  │ MCP client │──┼───────────────┼─►│ git_branch │  │
│  │            │  │               │  │ list_files │  │
│  └────────────┘  │               │  │ git_diff   │  │
└──────────────────┘               │  └────────────┘  │
         │                          └──────────────────┘
         ▼
┌──────────────────┐
│  README + docs/  │
└──────────────────┘
```

## Компоненты

### `mcp_git_server.py` (MCP-сервер)
- `git_branch` — текущая ветка + все ветки
- `list_files` — список файлов по расширению
- `git_diff` — diff последних N коммитов
- Использует **GitPython** (без subprocess — Windows конфликт)

### `assistant.py` (ассистент)
- RAG по README + docs/ (TF-IDF, 656 слов)
- MCP-клиент: запускает `mcp_git_server.py` как subprocess
- JSON-RPC обмен через stdin/stdout
- Команды: `/help`, `/git`, `/files`, `/diff`, `/exit`

## Запуск

```bash
python assistant.py
```

## Демо

```bash
python demo31.py
```

## Технические детали

**Проблема:** `subprocess.run` внутри MCP-сервера ломает JSON-RPC транспорт на Windows (BrokenResourceError).

**Решение:** Использование GitPython вместо subprocess. GitPython работает через libgit2 (нативная библиотека) и не создает пайпы, которые конфликтуют с MCP транспортом.

**MCP API:** версия 1.28.1. Обработчики возвращают `list[TextContent]`.

## Результаты

```
📚 Загружено: 9 документов
🔨 Чанков: 9, Словарь: 656 слов
📡 MCP-сервер запущен

🔧 git_branch: main
📂 list_files (.py): найдено 65 файлов
📝 git_diff: 2 коммита с diff

🔍 RAG поиск:
  - Docker → docs_lab21/docker_basics.md (score: 0.68)
  - asyncio → docs_lab21/python_async.md (score: 0.54)
  - MCP → docs_lab21/mcp_protocol.md (score: 0.48)
```
