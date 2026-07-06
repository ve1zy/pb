"""
Демо для Лабораторной 26: Локальная LLM
Демонстрация работы TinyLlama-1.1B-Chat локально.
"""

from lab26_local_llm import model

print("=" * 70)
print("Демо: Локальная LLM (TinyLlama-1.1B-Chat)")
print("=" * 70)

def ask(prompt: str, max_tokens: int = 100) -> str:
    """Запрос к локальной LLM."""
    return model(prompt, max_new_tokens=max_tokens, temperature=0.7)

# Интерактивный режим
print("\n🤖 Локальная LLM готова! Введите 'exit' для выхода.")
print("Модель: TinyLlama-1.1B-Chat (1.1B параметров)")
print("Квантизация: Q4_K_M (4-bit)")
print("-" * 70)

while True:
    try:
        user_input = input("\nВы: ").strip()
        if user_input.lower() in ['exit', 'quit', 'выход']:
            print("До свидания!")
            break
        if not user_input:
            continue
        
        print("\n🤖 Ассистент:", end=" ", flush=True)
        response = ask(user_input, max_tokens=150)
        print(response)
        
    except KeyboardInterrupt:
        print("\n\nПрервано. До свидания!")
        break
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
