#!/usr/bin/env python3
"""
Demo: Локальный LLM CLI
Показывает работу с моделью TinyLlama через ctransformers
"""

from ctransformers import AutoModelForCausalLM

print("=" * 70)
print("DEMO: Локальный LLM CLI (ctransformers)")
print("=" * 70)

print("\n📦 Загрузка модели TinyLlama-1.1B-Chat...")
model = AutoModelForCausalLM.from_pretrained(
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
    model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    model_type="llama"
)
print("✅ Модель загружена!\n")

def ask(prompt: str, max_tokens: int = 150) -> str:
    """Запрос к локальной LLM."""
    return model(prompt, max_new_tokens=max_tokens, temperature=0.7)

# Demo 1: Простой вопрос
print("=" * 70)
print("DEMO 1: Простой вопрос")
print("=" * 70)
prompt = "Привет! Как дела?"
print(f"Вы: {prompt}")
response = ask(prompt, max_tokens=100)
print(f"Ассистент: {response.strip()}\n")

# Demo 2: Объяснение концепции
print("=" * 70)
print("DEMO 2: Объяснение концепции")
print("=" * 70)
prompt = "Что такое рекурсия в программировании?"
print(f"Вы: {prompt}")
response = ask(prompt, max_tokens=150)
print(f"Ассистент: {response.strip()}\n")

# Demo 3: Генерация кода
print("=" * 70)
print("DEMO 3: Генерация кода")
print("=" * 70)
prompt = "Напиши функцию на Python для вычисления факториала:"
print(f"Вы: {prompt}")
response = ask(prompt, max_tokens=200)
print(f"Ассистент: {response.strip()}\n")

print("=" * 70)
print("✅ Demo завершена")
print("=" * 70)
print("\nДля интерактивного режима запустите:")
print("  python cli_llm.py")
