"""
Лабораторная 30: Локальная LLM как приватный сервис
HTTP API сервер на базе FastAPI + TinyLlama
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from ctransformers import AutoModelForCausalLM
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta

# ============================================================================
# 1. Инициализация приложения
# ============================================================================

app = FastAPI(
    title="Local LLM Service",
    description="Приватный AI-сервис на базе локальной LLM",
    version="1.0.0"
)

# CORS для доступа с других доменов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 2. Загрузка модели
# ============================================================================

print("📦 Загрузка модели TinyLlama...")
model = AutoModelForCausalLM.from_pretrained(
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
    model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    model_type="llama"
)
print("✅ Модель загружена!")

# Блокировка для потокобезопасности
model_lock = threading.Lock()

# ============================================================================
# 3. Rate limiting
# ============================================================================

class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, client_id: str) -> bool:
        now = datetime.now()
        with self.lock:
            # Удаляем старые запросы
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if now - req_time < timedelta(seconds=self.window_seconds)
            ]
            
            # Проверяем лимит
            if len(self.requests[client_id]) >= self.max_requests:
                return False
            
            self.requests[client_id].append(now)
            return True
    
    def get_remaining(self, client_id: str) -> int:
        now = datetime.now()
        with self.lock:
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if now - req_time < timedelta(seconds=self.window_seconds)
            ]
            return max(0, self.max_requests - len(self.requests[client_id]))

rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

# ============================================================================
# 4. Модели данных
# ============================================================================

class ChatMessage(BaseModel):
    role: str  # "user" или "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: float = 0.3
    max_tokens: int = 200
    client_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    response: str
    usage: Dict
    model: str
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    model: str
    uptime: float
    requests_count: int

# ============================================================================
# 5. Глобальные переменные
# ============================================================================

start_time = time.time()
requests_count = 0

# ============================================================================
# 6. Эндпоинты
# ============================================================================

@app.get("/")
async def root():
    """Главная страница"""
    return {
        "service": "Local LLM API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "/health": "Проверка статуса",
            "/chat": "Чат с моделью",
            "/models": "Список моделей"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Проверка здоровья сервиса"""
    uptime = time.time() - start_time
    return HealthResponse(
        status="healthy",
        model="TinyLlama-1.1B-Chat",
        uptime=uptime,
        requests_count=requests_count
    )

@app.get("/models")
async def list_models():
    """Список доступных моделей"""
    return {
        "models": [
            {
                "id": "tinyllama-1.1b-chat",
                "name": "TinyLlama 1.1B Chat",
                "quantization": "Q4_K_M",
                "context_length": 512,
                "status": "loaded"
            }
        ]
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Чат с моделью"""
    global requests_count
    
    # Rate limiting
    client_ip = req.client.host if req.client else "unknown"
    client_id = request.client_id or client_ip
    
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "max_requests": rate_limiter.max_requests,
                "window_seconds": rate_limiter.window_seconds,
                "retry_after": rate_limiter.window_seconds
            }
        )
    
    # Проверка max context
    total_tokens = sum(len(msg.content.split()) for msg in request.messages)
    if total_tokens > 400:  # Оставляем место для ответа
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Context too long",
                "max_tokens": 400,
                "current_tokens": total_tokens
            }
        )
    
    # Формируем prompt
    prompt_parts = []
    for msg in request.messages:
        if msg.role == "user":
            prompt_parts.append(f"Пользователь: {msg.content}")
        elif msg.role == "assistant":
            prompt_parts.append(f"Ассистент: {msg.content}")
    
    prompt_parts.append("Ассистент:")
    prompt = "\n".join(prompt_parts)
    
    # Генерация ответа
    try:
        start_gen = time.time()
        
        # Потокобезопасный вызов модели
        with model_lock:
            response_text = model(
                prompt,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature
            )
        
        gen_time = time.time() - start_gen
        
        # Извлекаем только ответ ассистента
        if "Ассистент:" in response_text:
            parts = response_text.split("Ассистент:")
            answer = parts[-1].strip() if len(parts) > 1 else response_text.strip()
        else:
            answer = response_text.strip()
        
        # Ограничиваем длину ответа
        words = answer.split()
        if len(words) > request.max_tokens:
            answer = " ".join(words[:request.max_tokens]) + "..."
        
        requests_count += 1
        
        return ChatResponse(
            response=answer,
            usage={
                "prompt_tokens": total_tokens,
                "completion_tokens": len(answer.split()),
                "total_tokens": total_tokens + len(answer.split()),
                "generation_time": gen_time
            },
            model="tinyllama-1.1b-chat",
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/stats")
async def get_stats():
    """Статистика использования"""
    uptime = time.time() - start_time
    return {
        "uptime_seconds": uptime,
        "total_requests": requests_count,
        "rate_limit": {
            "max_requests": rate_limiter.max_requests,
            "window_seconds": rate_limiter.window_seconds
        },
        "model": {
            "name": "TinyLlama-1.1B-Chat",
            "quantization": "Q4_K_M",
            "context_length": 512
        }
    }

# ============================================================================
# 7. Запуск сервера
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 70)
    print("🚀 Запуск приватного LLM-сервиса")
    print("=" * 70)
    print("\n📡 Эндпоинты:")
    print("   GET  /         - Главная страница")
    print("   GET  /health   - Проверка статуса")
    print("   GET  /models   - Список моделей")
    print("   POST /chat     - Чат с моделью")
    print("   GET  /stats    - Статистика")
    print("\n🔒 Rate limit: 10 запросов в минуту")
    print("📏 Max context: 400 токенов")
    print("\n🌐 Сервер запущен на http://0.0.0.0:8000")
    print("=" * 70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
