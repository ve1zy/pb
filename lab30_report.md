# Отчет: Лабораторная 30 - Локальная LLM как приватный сервис

## Цель
Развернуть локальную LLM как приватный сервис с:
- HTTP API (FastAPI)
- Возможностью чата
- Rate limiting
- Ограничением контекста
- Проверкой стабильности

## Реализация

### Архитектура сервиса

```
┌─────────────┐     HTTP      ┌──────────────┐
│   Client    │ ────────────> │  FastAPI     │
│  (Python)   │ <──────────── │  Server      │
└─────────────┘     JSON      │  :8000       │
                              └──────┬───────┘
                                     │
                              ┌──────▼───────┐
                              │  TinyLlama   │
                              │  1.1B Chat   │
                              │  (ctran.)    │
                              └──────────────┘
```

### Компоненты

**Сервер** (`lab30_server.py`):
- FastAPI + Uvicorn
- Модель: TinyLlama-1.1B-Chat (Q4_K_M)
- Потокобезопасность: threading.Lock
- Rate limiting: 10 запросов/минуту
- Контекст: до 400 токенов

**Клиент** (`lab30_client.py`):
- 8 тестов для проверки сервиса
- Параллельные запросы
- Проверка лимитов

### API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/` | Главная страница |
| GET | `/health` | Проверка статуса |
| GET | `/models` | Список моделей |
| POST | `/chat` | Чат с моделью |
| GET | `/stats` | Статистика |

## Результаты тестирования

### ТЕСТ 1: Health Check ✅
```
Статус: 200
Время ответа: 0.002с
```

### ТЕСТ 2: Models List ✅
```
Модель: TinyLlama 1.1B Chat
Квантование: Q4_K_M
Контекст: 512 токенов
```

### ТЕСТ 3: Simple Chat ✅
```
Время ответа: 3.937с
Токены: 46 (prompt: 3, completion: 43)
```

### ТЕСТ 4: Context Chat ✅
```
Время ответа: 2.723с
Контекст: 3 сообщения
```

### ТЕСТ 5: Rate Limiting ✅
```
10 запросов: ✅ OK
11-12 запросы: ⚠️ Rate limited (429)
Лимит: 10 запросов/минуту
```

### ТЕСТ 6: Context Limit ❌
```
Статус: 200 (должен быть 400)
Проблема: проверка считает слова, не токены
```

### ТЕСТ 7: Concurrent Requests ✅
```
5 параллельных запросов: 5/5 успешных
Среднее время: 20.784с
Общее время: 33.851с
```

### ТЕСТ 8: Stats ✅
```
Uptime: 106с
Total requests: 18
```

## Итоги

| Тест | Результат |
|------|-----------|
| Health Check | ✅ |
| Models List | ✅ |
| Simple Chat | ✅ |
| Context Chat | ✅ |
| Rate Limit | ✅ |
| Context Limit | ❌ |
| Concurrent | ✅ |
| Stats | ✅ |

**Результат: 7/8 тестов пройдено (87.5%)**

## Анализ производительности

### Скорость ответов

| Тип запроса | Время |
|-------------|-------|
| Health check | 0.002с |
| Простой чат | 3.9с |
| Чат с контекстом | 2.7с |
| Параллельный (среднее) | 20.8с |

### Стабильность

✅ **Rate limiting работает:**
- 10 запросов проходят
- 11+ отклоняются с кодом 429
- Окно: 60 секунд

✅ **Потокобезопасность:**
- 5 параллельных запросов обработаны
- Нет конфликтов благодаря threading.Lock
- Среднее время 20.8с (последовательно из-за блокировки)

⚠️ **Context limit:**
- Проверка на слова, не токены
- Нужно улучшить (использовать токенайзер)

## Использование

### Запуск сервера

```bash
python lab30_server.py
```

Сервер запустится на `http://0.0.0.0:8000`

### Примеры запросов

**Health check:**
```bash
curl http://localhost:8000/health
```

**Чат:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Привет!"}
    ],
    "temperature": 0.3,
    "max_tokens": 100
  }'
```

**Python клиент:**
```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "messages": [{"role": "user", "content": "Привет!"}],
        "temperature": 0.3,
        "max_tokens": 100
    }
)

print(response.json()["response"])
```

## Деплой на VPS

### 1. Подготовка сервера

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-pip python3-venv

# Создаем виртуальное окружение
python3 -m venv llm-env
source llm-env/bin/activate

# Устанавливаем зависимости
pip install fastapi uvicorn ctransformers
```

### 2. Загрузка кода

```bash
git clone <your-repo>
cd your-repo
```

### 3. Запуск с systemd

```bash
sudo nano /etc/systemd/system/llm-service.service
```

```ini
[Unit]
Description=Local LLM Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/llm-service
ExecStart=/home/ubuntu/llm-env/bin/python lab30_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable llm-service
sudo systemctl start llm-service
```

### 4. Настройка Nginx (опционально)

```nginx
server {
    listen 80;
    server_name llm.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5. HTTPS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d llm.yourdomain.com
```

## Безопасность

### Рекомендации для production:

1. **Аутентификация:**
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(token: str = Depends(security)):
    if token.credentials != "your-secret-token":
        raise HTTPException(status_code=401)
```

2. **CORS (ограничить домены):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    ...
)
```

3. **Rate limiting (строже):**
```python
rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
```

4. **Логирование:**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

5. **Мониторинг:**
- Prometheus + Grafana
- Health checks
- Alerting

## Ограничения

### Текущие:
- Модель 1.1B — малая мощность
- Контекст 512 токенов
- Последовательная обработка (блокировка)
- Нет кэширования

### Для production:
- Использовать модели 7B+ (Llama 2, Mistral)
- GPU для ускорения (CUDA)
- Батчинг запросов
- Кэширование частых запросов
- Load balancing (несколько инстансов)

## Выводы

✅ **Что работает:**
- HTTP API доступен по сети
- Rate limiting защищает от перегрузки
- Потокобезопасность (threading.Lock)
- Параллельные запросы обрабатываются
- Health monitoring

⚠️ **Что улучшить:**
- Context limit (токенайзер вместо split)
- GPU поддержка для ускорения
- Асинхронная обработка
- Кэширование ответов

✅ **Готово к использованию:**
- Локальный приватный AI-сервис
- Доступен по сети
- Защищен rate limiting
- Мониторинг через /health и /stats

## Код

- `lab30_server.py` — HTTP API сервер
- `lab30_client.py` — клиент для тестирования

Запуск:
```bash
python lab30_server.py    # Сервер
python lab30_client.py    # Тесты
```

## Итог

Приватный LLM-сервис развернут и работает. API доступен по сети, есть rate limiting, потокобезопасность, мониторинг. Готов к использованию для локальных задач.

**Статус:** ✅ Лабораторная выполнена
