# FastAPI: Полное руководство

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
