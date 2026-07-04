import os
import json
import requests
from typing import List, Dict, Optional

class SimpleAIAgent:
    def __init__(self, api_key: str, model: str = "cohere/north-mini-code:free"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        

        self.messages: List[Dict[str, any]] = []

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost", 
            "X-Title": "Simple Agent"
        }

    def _call_llm(self, enable_reasoning: bool = False) -> Optional[Dict]:

        payload = {
            "model": self.model,
            "messages": self.messages,
        }

        if enable_reasoning:
            payload["reasoning"] = {"enabled": True}

        try:
            response = requests.post(
                url=self.base_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status() 
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к API: {e}")
            return None

    def process_request(self, user_input: str, enable_reasoning: bool = False) -> str:

        self.messages.append({"role": "user", "content": user_input})

        result = self._call_llm(enable_reasoning=enable_reasoning)
        
        if not result or 'choices' not in result or len(result['choices']) == 0:
            return "Извините, не удалось получить ответ от модели."

        assistant_message = result['choices'][0]['message']

        self.messages.append(assistant_message)
        

        return assistant_message.get('content', '')

    def reset_history(self):
        self.messages = []


if __name__ == "__main__":
    API_KEY = os.getenv("OPENROUTER_API_KEY", "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") 
    
    if API_KEY == "sk-or-v1-...":
        print("Пожалуйста, установите переменную окружения OPENROUTER_API_KEY")
        exit()

    agent = SimpleAIAgent(api_key=API_KEY)
    
    print("--- Простой ИИ-Агент (введите 'exit' для выхода) ---")
    
    while True:
        user_text = input("\nВы: ")
        if user_text.lower() in ['exit', 'quit', 'выход']:
            break

        response = agent.process_request(user_text, enable_reasoning=True)
        
        print(f"Агент: {response}")