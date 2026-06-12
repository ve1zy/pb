import os
import json
import sqlite3
import requests
from typing import List, Dict, Optional

class PersistentAIAgent:
    def __init__(self, api_key: str, model: str = "poolside/laguna-m.1:free", db_path: str = "agent_context.db"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.db_path = db_path
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Persistent Agent"
        }
        
        self._init_db()
        self.messages = self._load_history()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_json TEXT NOT NULL
            )
        ''')
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
        except Exception as e:
            print(f"Ошибка загрузки истории: {e}")
            return []

    def _save_message_to_db(self, message: Dict):

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("INSERT INTO chat_history (message_json) VALUES (?)", 
                           (json.dumps(message),))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Ошибка сохранения сообщения: {e}")

    def clear_history(self):

        self.messages = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history")
            conn.commit()
            conn.close()
            print("История диалога очищена.")
        except Exception as e:
            print(f"Ошибка очистки истории: {e}")

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
            print(f"Ошибка API: {e}")
            return None

    def process_request(self, user_input: str, enable_reasoning: bool = False) -> str:

        user_msg = {"role": "user", "content": user_input}
        

        self.messages.append(user_msg)
        self._save_message_to_db(user_msg)
        

        result = self._call_llm(enable_reasoning=enable_reasoning)
        
        if not result or 'choices' not in result or len(result['choices']) == 0:
            return "Извините, ошибка связи с моделью."
        

        assistant_msg = result['choices'][0]['message']
        self.messages.append(assistant_msg)
        self._save_message_to_db(assistant_msg)
        
        return assistant_msg.get('content', '')



if __name__ == "__main__":
    API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
    
    if API_KEY == "sk-or-v1-...":
        print("Установите OPENROUTER_API_KEY")
        exit()

    print("--- Агент с сохранением контекста (SQLite) ---")
    print("Команды: 'exit' - выход, 'clear' - очистить историю")
    

    agent = PersistentAIAgent(api_key=API_KEY)
    
    while True:
        user_text = input("\nВы: ")
        if user_text.lower() == 'exit':
            break
        if user_text.lower() == 'clear':
            agent.clear_history()
            continue
            
        response = agent.process_request(user_text, enable_reasoning=True)
        print(f"Агент: {response}")