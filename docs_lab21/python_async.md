# Asyncio в Python

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
