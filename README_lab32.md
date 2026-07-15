# Лабораторная 32: AI Code Review

## Назначение

Автоматический AI-ревьюер для Pull Request, который анализирует diff и выдает:
- Потенциальные баги
- Архитектурные проблемы
- Стилевые рекомендации
- Релевантную документацию

## Компоненты

### 1. GitHub Action
Файл: `.github/workflows/pr-review.yml`

- Триггер: `pull_request` (opened, synchronize, reopened)
- Получает diff и список файлов
- Запускает Python скрипт
- Постит ревью как комментарий в PR

### 2. AI-ревьюер
Файл: `pr_reviewer.py`

- Парсит diff на файлы с изменениями
- Статический анализ (баги, стиль)
- Архитектурные проверки
- RAG по документации проекта
- Генерация отчета в markdown

## Проверки

### Потенциальные баги

| Паттерн | Описание |
|---------|----------|
| `except:` без типа | Скрывает все ошибки |
| `print()` в коде | Нужен logging |
| Hardcoded пароли/токены | Используй env vars |
| `TODO`/`FIXME` | Незавершенные задачи |
| SQL injection | Параметризованные запросы |
| `eval()`/`exec()` | Опасно |
| Функции > 50 строк | Разбей на части |

### Стиль

- Type hints
- Docstrings
- Именование

### Архитектура

- Наличие тестов
- Размер изменений
- Разделение ответственности

## RAG

Использует `docs_lab21/*.md`:
- python_async.md
- docker_basics.md
- fastapi_guide.md
- sqlite_guide.md
- mcp_protocol.md
- и другие

Поиск по ключевым словам из diff.

## Использование

### Локально

```bash
# Создать diff
git diff HEAD~1 HEAD > pr_diff.txt
git diff --name-only HEAD~1 HEAD > changed_files.txt

# Запустить ревью
python pr_reviewer.py
```

### На GitHub

Автоматически при создании/обновлении PR.

## Файлы

- `pr_reviewer.py` — основной скрипт
- `.github/workflows/pr-review.yml` — GitHub Action
- `pr_diff.txt` — тестовый diff
- `changed_files.txt` — список файлов
- `review_output.md` — результат ревью
- `lab32_report.md` — отчет

## Запуск

```bash
python pr_reviewer.py
```

## Пример вывода

```markdown
## 🤖 AI Code Review

**Изменено файлов:** 2
**Строк добавлено:** 33

### 🐛 Потенциальные баги
- **api.py**: 🔴 Hardcoded секрет
- **api.py**: 🔴 eval() — опасно

### 💅 Стиль кода
- **api.py**: 💡 Добавь docstrings

### 📚 Релевантная документация
- `docs_lab21/sqlite_guide.md`
- `docs_lab21/fastapi_guide.md`
```

## Требования

```bash
pip install ctransformers  # для локальной LLM (опционально)
```

Базовый анализ работает без зависимостей.
