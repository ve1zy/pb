from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lab21 import DocumentIndexer, FixedSizeChunker, StructureChunker


def create_test_docs():
    """Создание тестовых документов для индексации."""
    os.makedirs("docs_lab21", exist_ok=True)

    docs = {
        "docs_lab21/python_async.md": """# Asyncio в Python

## Введение
Asyncio — это библиотека Python для написания конкурентного кода с использованием async/await.
Asyncio используется как основа для множества высокопроизводительных сетевых фреймворков.

## Основы
Ключевые концепции asyncio: event loop, coroutines, tasks, futures.
Event loop — центральный исполнительный механизм. Он регистрирует и распределяет асинхронные задачи.
Coroutine — функция, объявленная с помощью async def. Она может приостанавливать своё выполнение.
Task — обёртка над coroutine для параллельного выполнения.

## Примеры

### Простой coroutine
async def hello():
    await asyncio.sleep(1)
    print("Hello!")

### Запуск event loop
asyncio.run(hello())

## Продвинутое использование
gather — запуск нескольких задач параллельно.
wait — ожидание завершения набора задач.
create_task — создание задачи из coroutine.

## Практика
Для I/O-bound задач asyncio значительно эффективнее threading.
Для CPU-bound задач лучше использовать multiprocessing.
""",

        "docs_lab21/fastapi_guide.md": """# FastAPI: Полное руководство

## Что такое FastAPI
FastAPI — современный веб-фреймворк для построения API на Python 3.7+.
Основан на Starlette и Pydantic. Автоматическая документация через OpenAPI.

## Установка
pip install fastapi uvicorn

## Первый endpoint
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

## Path параметры
@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}

## Pydantic модели
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool = False

@app.post("/items/")
async def create_item(item: Item):
    return item

## Middleware
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

## Dependency Injection
from fastapi import Depends

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
""",

        "docs_lab21/mcp_protocol.md": """# Model Context Protocol (MCP)

## Обзор
MCP — открытый протокол для интеграции LLM с внешними инструментами и данными.
Позволяет создавать универсальные интерфейсы для взаимодействия моделей с миром.

## Архитектура
MCP использует клиент-серверную архитектуру:
- MCP Host: программа с LLM (Claude Desktop, IDE)
- MCP Client: поддерживает 1:1 соединение с сервером
- MCP Server: предоставляет инструменты, ресурсы, промпты

## Транспорт
Поддерживаются два транспорта:
- stdio: для локальных процессов
- HTTP+SSE: для удалённых серверов

## Инструменты (Tools)
Инструменты — функции, которые может вызвать модель.
Каждый инструмент имеет JSON Schema для параметров.
Сервер описывает инструменты через list_tools.
Вызов через call_tool с аргументами.

## Ресурсы (Resources)
Ресурсы — данные, которые может прочитать клиент.
Аналогичны GET-запросам в REST API.
Примеры: файлы, записи БД, содержимое экранов.

## Промпты (Prompts)
Шаблоны сообщений для конкретных задач.
Пользователь выбирает промпт из списка.
Сервер возвращает готовое сообщение для LLM.
""",

        "docs_lab21/sqlite_guide.md": """# SQLite: Практическое руководство

## Введение
SQLite — встраиваемая реляционная база данных.
Не требует отдельного серверного процесса. Все данные в одном файле.
Идеальна для мобильных приложений, десктопных программ, прототипирования.

## Создание таблицы
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

## Операции CRUD
INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com');
SELECT * FROM users WHERE name LIKE '%Alice%';
UPDATE users SET email = 'new@example.com' WHERE id = 1;
DELETE FROM users WHERE id = 1;

## Транзакции
BEGIN TRANSACTION;
INSERT INTO accounts (balance) VALUES (100);
INSERT INTO transfers (from_id, to_id, amount) VALUES (1, 2, 50);
COMMIT;

## Индексы
CREATE INDEX idx_users_email ON users(email);
Индексы ускоряют поиск, но замедляют запись.

## Python интеграция
import sqlite3
conn = sqlite3.connect('mydb.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM users')
rows = cursor.fetchall()
conn.close()

## Оптимизация
WAL режим: PRAGMA journal_mode=WAL;
Vacuum: сжатие базы данных.
Backup API для безопасного резервного копирования.
""",

        "docs_lab21/ml_basics.md": """# Основы машинного обучения

## Типы обучения
Supervised learning: обучение на размеченных данных.
Unsupervised learning: поиск паттернов без меток.
Reinforcement learning: обучение через вознаграждение.

## Линейная регрессия
Модель: y = w*x + b
Цель: минимизировать MSE (Mean Squared Error).
Метод оптимизации: градиентный спуск.

## Классификация
Логистическая регрессия: сигмоида + cross-entropy loss.
KNN: классификация по ближайшим соседям.
Decision Tree: дерево решений.

## Нейронные сети
Персептрон: базовый блок нейросети.
Hidden layers: скрытые слои для нелинейных преобразований.
Backpropagation: обратное распространение ошибки.
Activation functions: ReLU, sigmoid, tanh.

## Регуляризация
L1 (Lasso): добавляет |w| к loss.
L2 (Ridge): добавляет w^2 к loss.
Dropout: случайное отключение нейронов.
Batch Normalization: нормализация активаций.

## Метрики
Accuracy: доля правильных предсказаний.
Precision/Recall: для несбалансированных классов.
F1-score: гармоническое среднее precision и recall.
""",

        "docs_lab21/docker_basics.md": """# Docker: Основы контейнеризации

## Что такое Docker
Docker — платформа для разработки, доставки и запуска приложений в контейнерах.
Контейнер — изолированная среда с приложениями и их зависимостями.
Образ (image) — шаблон для создания контейнеров.

## Основные команды
docker build -t myapp . — сборка образа из Dockerfile.
docker run -p 8080:80 myapp — запуск контейнера.
docker ps — список запущенных контейнеров.
docker stop <container_id> — остановка контейнера.

## Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]

## Docker Compose
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:80"
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: secret

## Сети
bridge: изолированная сеть для контейнеров.
host: контейнер использует сеть хоста.
none: без сетевого стека.

## Volumes
docker volume create mydata
docker run -v mydata:/data myapp
Persistent storage для контейнеров.
""",

        "docs_lab21/git_workflow.md": """# Git: Рабочие процессы

## Основные команды
git init — инициализация репозитория.
git add . — добавление файлов в staging.
git commit -m "message" — создание коммита.
git push origin main — отправка на удалённый сервер.
git pull — получение и слияние изменений.

## Ветвление
git branch feature — создание ветки.
git checkout feature — переключение на ветку.
git merge feature — слияние ветки в текущую.
git rebase — перемещение коммитов на другую ветку.

## Git Flow
main: стабильная версия.
develop: интеграционная ветка.
feature/*: новые функции.
release/*: подготовка релиза.
hotfix/*: срочные исправления.

## Conventional Commits
feat: новая функция.
fix: исправление бага.
docs: изменения документации.
style: форматирование, без изменения логики.
refactor: реструктуризация кода.
test: добавление тестов.

## Resolve конфликты
git merge вызывает конфликт при одновременном изменении.
Решение: вручную выбрать изменения из обеих веток.
git mergetool — визуальный инструмент для решения.
""",

        "docs_lab21/testing_python.md": """# Тестирование на Python

## pytest
pip install pytest
pytest — запуск всех тестов.
pytest test_file.py — запуск конкретного файла.
pytest -v — подробный вывод.

## Структура теста
def test_addition():
    assert 1 + 1 == 2

def test_string():
    assert "hello".upper() == "HELLO"

## Fixtures
@pytest.fixture
def sample_data():
    return {"name": "Alice", "age": 30}

def test_user(sample_data):
    assert sample_data["name"] == "Alice"

## Параметризация
@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (5, 5, 10),
    (-1, 1, 0),
])
def test_add(a, b, expected):
    assert a + b == expected

## Mock
from unittest.mock import MagicMock
mock = MagicMock(return_value=42)
assert mock() == 42

## Coverage
pip install pytest-cov
pytest --cov=myproject --cov-report=html
Покрытие показывает процент протестированного кода.
""",
    }

    for path, content in docs.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"✅ Создано {len(docs)} тестовых документов в docs_lab21/")
    return list(docs.keys())


async def main():
    print("=" * 60)
    print("Лабораторная 21: Индексация документов")
    print("=" * 60)

    # 1 — Создание тестовых документов
    print("\n1️⃣  Создание тестовых документов...")
    filepaths = create_test_docs()

    # 2 — Сравнение стратегий chunking
    print("\n2️⃣  Сравнение стратегий chunking...")
    indexer = DocumentIndexer()
    comparison = indexer.compare_strategies(filepaths)

    # 3 — Индексация с фиксированным размером
    print("\n3️⃣  Индексация (fixed size, 300 слов/чанк)...")
    indexer_fixed = DocumentIndexer()
    indexer_fixed.index_files(filepaths, chunker="fixed")
    print(f"   Чанков: {len(indexer_fixed.chunks)}")

    # 4 — Генерация эмбеддингов
    print("\n4️⃣  Генерация эмбеддингов...")
    indexer_fixed.generate_embeddings()

    # 5 — Сохранение индекса
    print("\n5️⃣  Сохранение индекса...")
    indexer_fixed.save_index()

    # 6 — Поиск
    print("\n6️⃣  Поиск по индексу...")
    queries = ["asyncio event loop", "FastAPI endpoint", "Docker контейнеры"]
    for query in queries:
        print(f"\n   🔍 Запрос: '{query}'")
        results = indexer_fixed.search(query, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"   {i}. [{r['score']}] {r['title']} / {r['section']}")
            print(f"      {r['content'][:100]}...")

    # 7 — Статистика
    print("\n" + "=" * 60)
    print("ИТОГ:")
    print(f"  Документов: {len(filepaths)}")
    print(f"  Стратегия fixed: {comparison['fixed']['total_chunks']} чанков")
    print(f"  Стратегия structure: {comparison['structure']['total_chunks']} чанков")
    print(f"  Эмбеддингов: {len(indexer_fixed.embeddings)}")
    print(f"  Индекс: {indexer_fixed.index_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
