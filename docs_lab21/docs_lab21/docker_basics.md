# Docker: Основы контейнеризации

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
