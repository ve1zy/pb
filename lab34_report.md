# Lab 34: Ассистент для работы с файлами проекта

## Статус: ✅ Реализовано

## Архитектура

```
┌──────────────────┐
│   Пользователь   │
│   "/find foo"     │
│   "/changelog"    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     stdio     ┌──────────────────┐
│  file_assistant  │ ◄──────────► │ mcp_files_server │
│                  │   JSON-RPC   │                  │
│  ┌────────────┐  │              │ 10 инструментов: │
│  │ Сценарии   │  │              │ - read_file      │
│  │ /find      │  │              │ - list_files     │
│  │ /search    │  │              │ - search_in_files│
│  │ /check     │──┼──────────────│ - find_usages    │
│  │ /changelog │  │              │ - create_file    │
│  │ /update-docs│ │              │ - update_file    │
│  │ /adr       │  │              │ - check_invariants│
│  └────────────┘  │              │ - get_file_info  │
│                  │              │ - generate_diff  │
└──────────────────┘              │ - git_log        │
                                    └──────────────────┘
```

## Реализованные сценарии

### 1. `/find <component>` — найти использования
```
🔍 Поиск использований `ctransformers`:
cli_llm.py:3,7,15
demo27.py:4,7,10
lab28.py, lab30_server.py...
```

### 2. `/search <regex>` — поиск по коду
```
🔎 Поиск 'def\s+ask':
cli_llm.py:30
demo26.py:12
demo27.py:21
lab22.py:78,97
lab23.py:195
```

### 3. `/check` — проверка инвариантов
```
⚠️ Найдено проблем: 30
- demo16.py: нет docstring
- lab1.py: нет docstring
- 30 файлов без docstring
```

### 4. `/changelog` — генерация CHANGELOG.md
```
✅ Создан: CHANGELOG.md
92d40ca 2026-07-10 s
c3cf3c2 2026-07-06 s
...
```

### 5. `/update-docs` — обновление API.md
```
✅ Создан: API.md
### `load_docs()` (assistant.py)
Загружает README и docs/
### `build_index()` (assistant.py)
Строит TF-IDF индекс
...
```

### 6. `/adr <title>|<decision>` — генерация ADR
```
✅ Создан: docs_lab34/adr-...md
```

## MCP-инструменты (10)

| Инструмент | Назначение |
|------------|------------|
| `read_file` | Прочитать файл |
| `list_files` | Список файлов по расширению |
| `search_in_files` | Поиск regex в файлах |
| `find_usages` | Найти использования имени |
| `create_file` | Создать новый файл |
| `update_file` | Заменить текст в файле |
| `check_invariants` | Проверить правила (docstring, todo, type_hints) |
| `get_file_info` | Метаинформация (размер, MD5) |
| `generate_diff` | Unified diff между текстами |
| `git_log` | История коммитов (GitPython) |

## Запуск

### Интерактивный режим
```bash
python file_assistant.py
```

### Demo
```bash
python demo34.py
```

## Технические детали

**MCP-сервер** работает без subprocess (использует прямое чтение файлов + GitPython).

**Ассистент** — сценарии как обычные Python-функции, не требуют LLM.

**Создаваемые файлы:**
- `API.md` — автогенерируемая документация функций
- `CHANGELOG.md` — история коммитов
- `docs_lab34/adr-*.md` — Architecture Decision Records

## Файлы

```
mcp_files_server.py    # MCP-сервер (10 инструментов)
file_assistant.py      # Ассистент (6 сценариев)
demo34.py              # Демо
lab34_report.md        # Этот отчёт
```

## Зависимости

```
mcp          # MCP SDK
gitpython    # для git_log
```
