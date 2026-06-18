import os
import json
import sqlite3
import requests
import tiktoken
from typing import List, Dict, Optional

class SmartCompressedAgent:
    def __init__(self, api_key: str, model: str = "poolside/laguna-m.1:free", db_path: str = "agent_smart.db"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.db_path = db_path
        
        self.window_size = 6
        self.summary_token_limit = 1000 
        
        try:
            self.encoding = tiktoken.get_encoding("o200k_base")
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Smart Agent"
        }
        
        self._init_db()
        self.messages = self._load_history()
        self.summary = self._load_summary()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, message_json TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS agent_state (key TEXT PRIMARY KEY, value TEXT)''')
        conn.commit()
        conn.close()

    def _load_history(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT message_json FROM chat_history ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [json.loads(row[0]) for row in rows]

    def _save_message_to_db(self, message: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (message_json) VALUES (?)", (json.dumps(message),))
        conn.commit()
        conn.close()

    def _load_summary(self) -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM agent_state WHERE key = 'summary'")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ""

    def _save_summary(self, summary: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO agent_state (key, value) VALUES ('summary', ?)", (summary,))
        conn.commit()
        conn.close()
        self.summary = summary

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _compress_history(self):
        if len(self.messages) <= self.window_size:
            return

        messages_to_compress = self.messages[:-self.window_size]

        compress_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages_to_compress])
        
        print("\nЗапуск сжатия истории...")
        
        summary_prompt = [
            {"role": "system", "content": "Ты полезный ассистент. Сделай краткое резюме следующего диалога. Сохрани ключевые факты, имена и договоренности. Игнорируй приветствия и воду."},
            {"role": "user", "content": f"Резюме диалога:\n{compress_text}"}
        ]

        try:
            response = requests.post(
                url=self.base_url,
                headers=self.headers,
                data=json.dumps({
                    "model": self.model,
                    "messages": summary_prompt
                }),
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            new_summary = result['choices'][0]['message']['content']
            
            if self.summary:
                final_summary = f"{self.summary}\n\nПродолжение диалога:\n{new_summary}"
            else:
                final_summary = new_summary
                
            self._save_summary(final_summary)
            
            self.messages = self.messages[-self.window_size:]

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history")
            for msg in self.messages:
                cursor.execute("INSERT INTO chat_history (message_json) VALUES (?)", (json.dumps(msg),))
            conn.commit()
            conn.close()
            
            print(f"История сжата. Новое резюме сохранено.")
            
        except Exception as e:
            print(f" Ошибка при сжатии: {e}")

    def process_request(self, user_input: str) -> str:
        user_msg = {"role": "user", "content": user_input}
        self.messages.append(user_msg)
        self._save_message_to_db(user_msg)

        if len(self.messages) > self.window_size + 2:
             self._compress_history()


        final_messages = []

        if self.summary:
            final_messages.append({
                "role": "system", 
                "content": f"Краткая история предыдущего общения с пользователем:\n{self.summary}"
            })

        final_messages.extend(self.messages)

        total_context_tokens = sum([self.count_tokens(json.dumps(m)) for m in final_messages])
        print(f"\n--- Статистика ---")
        print(f"Сообщений в окне: {len(self.messages)}")
        print(f"Есть резюме: {'Да' if self.summary else 'Нет'}")
        print(f"Примерный размер контекста: {total_context_tokens} токенов")

        payload = {
            "model": self.model,
            "messages": final_messages,
            "reasoning": {"enabled": True}
        }

        try:
            response = requests.post(url=self.base_url, headers=self.headers, data=json.dumps(payload), timeout=30)
            response.raise_for_status()
            result = response.json()
            
            assistant_msg = result['choices'][0]['message']
            self.messages.append(assistant_msg)
            self._save_message_to_db(assistant_msg)
            
            return assistant_msg.get('content', '')
        except Exception as e:
            return f"Ошибка: {e}"

    def clear_history(self):
        self.messages = []
        self.summary = ""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        cursor.execute("DELETE FROM agent_state")
        conn.commit()
        conn.close()
        print("История и резюме полностью очищены.")

if __name__ == "__main__":
    API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
    if API_KEY == "sk-or-v1-...":
        print("Установите OPENROUTER_API_KEY")
        exit()

    print("--- Умный агент со сжатием контекста ---")
    agent = SmartCompressedAgent(api_key=API_KEY)
    
    while True:
        user_text = input("\nВы: ")
        if user_text.lower() == 'exit': break
        if user_text.lower() == 'clear': 
            agent.clear_history()
            continue
            
        response = agent.process_request(user_text)
        print(f"Агент: {response}")