# Lab 34: Ассистент для работы с файлами (с LLM-агентом)

## Статус: ✅ Полностью реализовано

## Архитектура

```
┌──────────────────┐
│   Пользователь   │
│  "найди где у    │
│   нас ctrans..."  │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────┐     stdio     ┌──────────────────┐
│       file_assistant                 │ ◄──────────► │ mcp_files_server │
│                                      │   JSON-RPC   │                  │
│  ┌────────────────────────────────┐  │              │ 10 инструментов: │
│  │  LLM-агент (TinyLlama)        │  │              │ - read_file      │
│  │  ┌──────────────────────────┐  │  │              │ - list_files     │
│  │  │ 1. plan: какой инструмент│  │  │              │ - search_in_files│
│  │  │ 2. call: вызвать MCP     │──┼──┼──────────────│ - find_usages    │
│  │  │ 3. interpret: ответ LLM  │  │  │              │ - create_file    │
│  │  └──────────────────────────┘  │  │              │ - update_file    │
│  └────────────────────────────────┘  │              │ - check_invariants│
│  ┌────────────────────────────────┐  │              │ - get_file_info  │
│  │  Сценарии (для команд)        │  │              │ - generate_diff  │
│  │  /find /search /check         │  │              │ - git_log        │
│  │  /changelog /update-docs /adr │  │              │                  │
│  └────────────────────────────────┘  │              └──────────────────┘
└──────────────────────────────────────┘
```

## Два режима работы

### 1. Командный режим (быстрый)
```
/find ctransformers
/search def.*llm
/check
/changelog
/update-docs
/adr title|decision
```

### 2. AI-агент режим (по умолчанию)
```
найди где у нас используется ctransformers
проверь все python файлы на наличие docstring
сгенерируй changelog
```

LLM сама:
1. **plan** — выбирает подходящий инструмент (генерирует JSON)
2. **call** — вызывает MCP-инструмент
3. **interpret** — формулирует ответ

## MCP-инструменты (10)

| Инструмент | Назначение |
|------------|------------|
| `read_file` | Прочитать файл |
| `list_files` | Список файлов по расширению |
| `search_in_files` | Поиск regex |
| `find_usages` | Использования имени |
| `create_file` | Создать файл |
| `update_file` | Заменить текст |
| `check_invariants` | Проверить правила |
| `get_file_info` | Метаинформация |
| `generate_diff` | Unified diff |
| `git_log` | История коммитов (GitPython) |

## Результаты тестирования

### Команды

| Команда | Результат |
|---------|-----------|
| `/find ctransformers` | Найдено 21 использование |
| `/search def.*ask` | Найдено 10 функций |
| `/check` | 30 файлов без docstring |
| `/changelog` | Создан CHANGELOG.md |
| `/update-docs` | Создан API.md |

### AI-агент

```
🤖 Задача: 'найди где у нас используется ctransformers'
🤖 План: search_in_files(pattern='ctransformers')
📊 Результат: 21 совпадение
💬 Ответ LLM: "найди где у нас используется ctransformers..."
```

⚠️ **Ограничение:** TinyLlama 1.1B не всегда выбирает оптимальный инструмент. Для production нужна модель 7B+.

## Использование

### Интерактивный режим

```bash
python file_assistant.py

# Вводите задачи на естественном языке
Задача: найди где у нас ctransformers
Задача: проверь файлы на docstring
Задача: сгенерируй changelog

# Или команды
Задача: /find ctransformers
```

### Demo

```bash
python demo34.py
```

## Технические детали

**LLM:** TinyLlama-1.1B-Chat (GGUF Q4_K_M)
- Lazy loading
- Генерирует JSON с инструментом: `{"tool": "...", "args": {...}}`
- Парсится regex `\{[^{}]*"tool"[^{}]*\}`
- Интерпретирует результат через второй вызов

**Fallback:** если LLM не выбрала инструмент или JSON невалидный → `search_in_files`

**MCP:** JSON-RPC через stdio_client + ClientSession

## Файлы

```
mcp_files_server.py    # MCP-сервер (10 инструментов)
file_assistant.py      # Ассистент + LLM-агент + сценарии
demo34.py              # Демо
API.md                 # Сгенерированная документация
CHANGELOG.md           # Сгенерированный changelog
lab34_report.md        # Этот отчёт
```

## Зависимости

```
mcp           # MCP SDK
ctransformers # Локальная LLM
gitpython     # для git_log
```
