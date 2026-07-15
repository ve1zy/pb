# Lab 32: AI Code Review (с LLM)

## Статус: ✅ Полностью реализовано

AI-ревьюер для PR с:
- Статическим анализом (regex на баги, стиль)
- Архитектурными проверками
- RAG по документации
- Локальной LLM (TinyLlama 1.1B) для объяснений
- GitHub Action для автоматического запуска

## Компоненты

### `pr_reviewer.py` (ревьюер)
1. **Парсинг diff** — извлекает изменения по файлам
2. **Статический анализ**:
   - Потенциальные баги (eval, hardcoded secrets, SQL injection)
   - Стиль (type hints, docstrings)
   - Архитектура (тесты, размер файлов)
3. **RAG поиск** — релевантная документация по `docs_lab21/`
4. **LLM анализ** — локальная TinyLlama объясняет критические баги

### `.github/workflows/pr-review.yml` (GitHub Action)
- Триггер: `pull_request` (opened, synchronize, reopened)
- Получает diff
- Запускает `pr_reviewer.py`
- Постит результат как комментарий в PR

## Проверки

### Потенциальные баги
- `except:` без типа
- `print()` в production коде
- Hardcoded пароли/токены
- TODO/FIXME
- SQL injection
- eval()/exec()
- Функции > 50 строк

### Стиль
- Type hints
- Docstrings

### Архитектура
- Наличие тестов
- Размер изменений

## Результат тестирования

```
## 🤖 AI Code Review

**Изменено файлов:** 2
**Строк добавлено:** 33

### 🐛 Потенциальные баги
- **api.py**: 🔴 Hardcoded секрет
  > 💡 LLM: "Возьмите переменные окружения..."
- **api.py**: 🔴 eval() — опасно
  > 💡 LLM: "Пример кода..."

### 💅 Стиль кода
- **api.py**: 💡 Добавь docstrings

### 📚 Релевантная документация
- `docs_lab21/sqlite_guide.md`

### 🎯 Общее резюме (LLM)
_Добавьте в файл api.py строку...
```

## Запуск

### Локально
```bash
# Создать тестовый diff
git diff HEAD~1 HEAD > pr_diff.txt
git diff --name-only HEAD~1 HEAD > changed_files.txt

# Запустить ревью
python pr_reviewer.py
```

### На GitHub
Автоматически при создании/обновлении PR.

## Зависимости

```
ctransformers  # для LLM
```

## Технические детали

- LLM: TinyLlama-1.1B-Chat (GGUF Q4_K_M)
- Lazy loading модели (загружается при первом использовании)
- LLM используется только для критических багов (🔴) и итогового резюме
- Если LLM недоступна — ревью работает без LLM-блоков
