import os
import json
import sqlite3
import requests
import tiktoken
from typing import List, Dict, Optional

class TokenAwareAgent:
    def __init__(self, api_key: str, model: str = "cohere/north-mini-code:free", db_path: str = "agent_context.db"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.db_path = db_path
        
        try:
            self.encoding = tiktoken.get_encoding("o200k_base")
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Token-Aware Agent"
        }
        
        self._init_db()
        self.messages = self._load_history()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, message_json TEXT NOT NULL)''')
        conn.commit()
        conn.close()

    def _load_history(self) -> List[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT message_json FROM chat_history ORDER BY id ASC")
            rows = cursor.fetchall()
            conn.close()
            return [json.loads(row[0]) for row in rows]
        except:
            return []

    def _save_message_to_db(self, message: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (message_json) VALUES (?)", (json.dumps(message),))
        conn.commit()
        conn.close()

    def count_tokens_for_messages(self, messages: List[Dict]) -> int:
        num_tokens = 0
        for message in messages:
            num_tokens += len(self.encoding.encode(message.get("role", "")))
            num_tokens += len(self.encoding.encode(message.get("content", "")))

            if "reasoning_details" in message and message["reasoning_details"]:

                 reasoning_text = str(message["reasoning_details"])
                 num_tokens += len(self.encoding.encode(reasoning_text))

            num_tokens += 3 
        return num_tokens

    def clear_history(self):
        self.messages = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        print("История и токены очищены.")

    def process_request(self, user_input: str, max_context_tokens: int = 4000) -> str:

        user_msg = {"role": "user", "content": user_input}
        

        temp_messages = self.messages + [user_msg]
        current_tokens = self.count_tokens_for_messages(temp_messages)
        
        print(f"\n--- Статистика токенов ---")
        print(f"Токенов в истории (без нового запроса): {self.count_tokens_for_messages(self.messages)}")
        print(f"Токенов в новом запросе пользователя: {len(self.encoding.encode(user_input))}")
        print(f"Общий размер контекста перед отправкой: {current_tokens}")

        if current_tokens > max_context_tokens:
            warning = f"ВНИМАНИЕ: Превышен лимит контекста ({max_context_tokens})! Текущий размер: {current_tokens}."
            print(warning)
            return warning + "\nПожалуйста, очистите историю командой 'clear'."

        self.messages.append(user_msg)
        self._save_message_to_db(user_msg)

        payload = {
            "model": self.model,
            "messages": self.messages,
            "reasoning": {"enabled": True}
        }

        try:
            response = requests.post(
                url=self.base_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            usage = result.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 'N/A')
            completion_tokens = usage.get('completion_tokens', 'N/A')
            total_tokens = usage.get('total_tokens', 'N/A')
            
            print(f"Ответ получен. Использовано токенов (по данным API):")
            print(f"   Prompt (вход): {prompt_tokens}")
            print(f"   Completion (выход): {completion_tokens}")
            print(f"   Total (всего): {total_tokens}")

            assistant_msg = result['choices'][0]['message']
            self.messages.append(assistant_msg)
            self._save_message_to_db(assistant_msg)
            
            return assistant_msg.get('content', '')

        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                error_detail = response.json().get('error', {}).get('message', 'Unknown error')
                if "context_length_exceeded" in error_detail or "too long" in error_detail.lower():
                    return f" Ошибка 400: Контекст переполнен. API отвергло запрос. Размер: {current_tokens} токенов."
            return f"Ошибка HTTP: {e}"
        except Exception as e:
            return f"Ошибка: {e}"



if __name__ == "__main__":
    API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
    if API_KEY == "sk-or-v1-...":
        print("Установите OPENROUTER_API_KEY")
        exit()


    DEMO_LIMIT = 500 
    
    print(f"--- Агент с мониторингом токенов (Лимит демо: {DEMO_LIMIT}) ---")
    agent = TokenAwareAgent(api_key=API_KEY)
    
    while True:
        user_text = input("\nВы: ")
        if user_text.lower() == 'exit': break
        if user_text.lower() == 'clear': 
            agent.clear_history()
            continue
            
        response = agent.process_request(user_text, max_context_tokens=DEMO_LIMIT)
        print(f"Агент: {response[:200]}...")