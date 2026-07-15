#!/usr/bin/env python3
"""
CLI-утилита для работы с локальной LLM через ctransformers
Без Ollama — модель загружается напрямую
"""

from ctransformers import AutoModelForCausalLM
import sys

MODEL_PATH = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
MODEL_FILE = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
MODEL_TYPE = "llama"

print("=" * 60)
print("Локальный LLM CLI (ctransformers)")
print("=" * 60)

print("\nЗагрузка модели TinyLlama-1.1B-Chat...")
try:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        model_file=MODEL_FILE,
        model_type=MODEL_TYPE
    )
    print("✅ Модель загружена!")
except Exception as e:
    print(f"❌ Ошибка загрузки модели: {e}")
    sys.exit(1)

def ask(prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> str:
    """Запрос к локальной LLM."""
    return model(prompt, max_new_tokens=max_tokens, temperature=temperature)

print("\n" + "=" * 60)
print("Команды:")
print("  /help    - показать справку")
print("  /clear   - очистить историю")
print("  /exit    - выход")
print("=" * 60)
print("\nВведите ваш вопрос:\n")

history = []

while True:
    try:
        user_input = input("Вы: ").strip()
        
        if not user_input:
            continue
        
        # Команды
        if user_input.startswith("/"):
            cmd = user_input.lower()
            
            if cmd in ["/exit", "/quit"]:
                print("До свидания!")
                break
            
            elif cmd == "/help":
                print("\nКоманды:")
                print("  /help    - показать справку")
                print("  /clear   - очистить историю")
                print("  /exit    - выход")
                print()
                continue
            
            elif cmd == "/clear":
                history = []
                print("История очищена\n")
                continue
            
            else:
                print(f"Неизвестная команда: {cmd}\n")
                continue
        
        # Запрос к LLM
        print("\nАссистент: ", end="", flush=True)
        
        # Формируем промпт с историей
        if history:
            context = "\n".join([f"Вы: {q}\nАссистент: {a}" for q, a in history[-3:]])
            full_prompt = f"{context}\nВы: {user_input}\nАссистент:"
        else:
            full_prompt = user_input
        
        response = ask(full_prompt, max_tokens=200, temperature=0.7)
        
        # Извлекаем только новый ответ
        if "Ассистент:" in response:
            parts = response.split("Ассистент:")
            answer = parts[-1].strip() if len(parts) > 1 else response.strip()
        else:
            answer = response.strip()
        
        print(answer)
        
        # Сохраняем в историю
        history.append((user_input, answer))
        
        # Ограничиваем историю
        if len(history) > 10:
            history = history[-10:]
        
        print()
    
    except KeyboardInterrupt:
        print("\n\nДо свидания!")
        break
    except EOFError:
        print("\n\nДо свидания!")
        break
