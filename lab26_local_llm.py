"""
Лабораторная 26: Запуск локальной LLM через ctransformers
Без зависимости от PyTorch — используем только ctransformers.
"""

from ctransformers import AutoModelForCausalLM

print("=" * 70)
print("Лабораторная 26: Локальная LLM")
print("=" * 70)

print("\nЗагрузка модели TinyLlama-1.1B-Chat...")
model = AutoModelForCausalLM.from_pretrained(
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
    model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    model_type="llama"
)
print("✅ Модель загружена!")

def ask(prompt: str, max_tokens: int = 100) -> str:
    """Запрос к локальной LLM."""
    response = model(prompt, max_new_tokens=max_tokens, temperature=0.7)
    return response

# Запрос 1: Простой
print("\n" + "=" * 70)
print("Запрос 1: Простой")
print("=" * 70)
prompt = "Привет! Как дела?"
print(f"Вопрос: {prompt}")
response = ask(prompt, max_tokens=50)
print(f"Ответ: {response}")

# Запрос 2: Средней сложности
print("\n" + "=" * 70)
print("Запрос 2: Средней сложности")
print("=" * 70)
prompt = "Объясни, что такое рекурсия в программировании."
print(f"Вопрос: {prompt}")
response = ask(prompt, max_tokens=150)
print(f"Ответ: {response}")

# Запрос 3: Сложный (код)
print("\n" + "=" * 70)
print("Запрос 3: Сложный (генерация кода)")
print("=" * 70)
prompt = "Напиши функцию на Python для вычисления чисел Фибоначчи с мемоизацией:"
print(f"Вопрос: {prompt}")
response = ask(prompt, max_tokens=200)
print(f"Ответ: {response}")

print("\n" + "=" * 70)
print("✅ Все 3 запроса выполнены")
print("=" * 70)
