# Лабораторные работы: Локальные LLM

Коллекция лабораторных работ по интеграции и использованию локальных языковых моделей.

## Лабораторные

### Lab 27: Интеграция локальной LLM в CLI-утилиту

**Файлы:**
- `lab27_cli_llm.py` — интерактивный CLI для работы с локальной LLM
- `demo27.py` — демонстрация работы

**Описание:**
CLI-утилита для работы с локальной языковой моделью через ctransformers. Работает полностью офлайн, без зависимости от Ollama или облачных сервисов.

**Запуск:**
```bash
python lab27_cli_llm.py
```

---

### Lab 28: Локальная LLM + RAG

**Файлы:**
- `lab28.py` — RAG-система с TF-IDF retrieval + локальная генерация
- `lab28_report.md` — отчет с результатами

**Описание:**
Полностью локальная RAG-система:
- Retrieval: TF-IDF индекс из lab21 (8 чанков, 626 слов)
- Генерация: TinyLlama 1.1B через ctransformers
- Сравнение с облачной моделью (если есть OPENAI_API_KEY)

**Результаты:**
- ✅ Retrieval находит правильные чанки
- ⚠️ Качество генерации низкое (маленькая модель)
- ⏱️ Средняя скорость: 14.68с

**Запуск:**
```bash
python lab28.py
```

---

### Lab 29: Оптимизация локальной LLM

**Файлы:**
- `lab29.py` — тестирование параметров (temperature, квантование, prompt)
- `lab29_report.md` — отчет с результатами

**Описание:**
Оптимизация локальной модели под задачу RAG:
- Настройка temperature (0.1-0.9)
- Сравнение квантований (Q2_K, Q4_K_M, Q5_K_M, Q8_0)
- Оптимизация prompt-шаблона

**Результаты:**
| Параметр | До | После | Улучшение |
|----------|-----|-------|-----------|
| Скорость | 7.17с | 6.17с | **-14%** |
| Качество | Среднее | Выше | **+30%** |

**Оптимальная конфигурация:**
```python
temperature = 0.3
max_tokens = 100
context_limit = 300  # слов
quantization = "Q4_K_M"
```

**Запуск:**
```bash
python lab29.py
```

---

### Lab 30: Локальная LLM как приватный сервис

**Файлы:**
- `lab30_server.py` — HTTP API сервер (FastAPI)
- `lab30_client.py` — клиент для тестирования
- `lab30_report.md` — отчет с результатами

**Описание:**
Приватный AI-сервис с HTTP API:
- FastAPI + Uvicorn
- Rate limiting (10 запросов/минуту)
- Потокобезопасность (threading.Lock)
- Мониторинг (/health, /stats)

**API Endpoints:**
```
GET  /         - Главная
GET  /health   - Статус
GET  /models   - Модели
POST /chat     - Чат
GET  /stats    - Статистика
```

**Результаты тестирования: 7/8 (87.5%)**
- ✅ Health Check, Models List, Simple Chat
- ✅ Context Chat, Rate Limit, Concurrent, Stats
- ❌ Context Limit (проверка на слова, не токены)

**Запуск:**
```bash
python lab30_server.py    # Сервер (http://localhost:8000)
python lab30_client.py    # Тесты
```

**Пример запроса:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Привет!"}],
    "temperature": 0.3,
    "max_tokens": 100
  }'
```

---

## Требования

- Python 3.7+
- `ctransformers` — для локальной LLM
- `fastapi`, `uvicorn` — для lab30
- `requests` — для HTTP запросов

**Установка:**
```bash
pip install ctransformers fastapi uvicorn requests
```

## Модели

Все лабораторные используют **TinyLlama 1.1B Chat** (GGUF Q4_K_M):
- Размер: ~700 МБ
- Контекст: 512 токенов
- Работает на CPU
- Полностью офлайн

## Структура

```
.
├── demo27.py              # Demo локальной LLM
├── lab27_cli_llm.py       # CLI утилита
├── lab28.py               # RAG система
├── lab28_report.md        # Отчет RAG
├── lab29.py               # Оптимизация
├── lab29_report.md        # Отчет оптимизации
├── lab30_server.py        # HTTP API сервер
├── lab30_client.py        # Тесты сервиса
├── lab30_report.md        # Отчет сервиса
└── README.md              # Этот файл
```

## Лицензия

MIT
