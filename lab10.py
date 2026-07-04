import os
import json
import sqlite3
import requests
import tiktoken
from typing import List, Dict, Optional

class MultiStrategyAgent:
    def __init__(self, api_key: str, model: str = "cohere/north-mini-code:free", db_path: str = "agent_strategies.db"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.db_path = db_path
        
        self.window_size = 6
        self.current_strategy = "sliding_window"
        self.current_branch_id = 1
        
        try:
            self.encoding = tiktoken.get_encoding("o200k_base")
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Multi-Strategy Agent"
        }
        
        self._init_db()
        self._load_state()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            branch_id INTEGER DEFAULT 1,
            message_json TEXT NOT NULL
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS facts (
            key TEXT PRIMARY KEY, 
            value TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY, 
            value TEXT
        )''')
        conn.commit()
        conn.close()

    def _load_state(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM state WHERE key = 'strategy'")
        row = cursor.fetchone()
        if row: self.current_strategy = row[0]
        

        cursor.execute("SELECT value FROM state WHERE key = 'branch_id'")
        row = cursor.fetchone()
        if row: self.current_branch_id = int(row[0])
        
        conn.close()
        self.messages = self._load_messages()
        self.facts = self._load_facts()

    def _load_messages(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT message_json FROM messages WHERE branch_id = ? ORDER BY id ASC", (self.current_branch_id,))
        rows = cursor.fetchall()
        conn.close()
        return [json.loads(row[0]) for row in rows]

    def _load_facts(self) -> Dict[str, str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM facts")
        rows = cursor.fetchall()
        conn.close()
        return dict(rows)

    def _save_message(self, msg: Dict):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (branch_id, message_json) VALUES (?, ?)", 
                       (self.current_branch_id, json.dumps(msg)))
        conn.commit()
        conn.close()

    def _update_fact(self, key: str, value: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO facts (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
        self.facts[key] = value

    def set_strategy(self, strategy_name: str):
        if strategy_name in ["sliding_window", "sticky_facts", "branching"]:
            self.current_strategy = strategy_name
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('strategy', ?)", (strategy_name,))
            conn.commit()
            conn.close()
            print(f"Стратегия изменена на: {strategy_name}")
        else:
            print("Неизвестная стратегия")

    def create_branch(self):
        new_branch_id = self.current_branch_id + 1
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        

        cursor.execute("SELECT message_json FROM messages WHERE branch_id = ?", (self.current_branch_id,))
        messages = cursor.fetchall()
        for msg in messages:
            cursor.execute("INSERT INTO messages (branch_id, message_json) VALUES (?, ?)", (new_branch_id, msg[0]))

        cursor.execute("SELECT key, value FROM facts")
        facts = cursor.fetchall()
        
        conn.commit()
        conn.close()
        
        self.current_branch_id = new_branch_id
        self.messages = self._load_messages()
        print(f"Создана новая ветка #{new_branch_id}. История скопирована.")

    def switch_branch(self, branch_id: int):
        self.current_branch_id = branch_id
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('branch_id', ?)", (str(branch_id),))
        conn.commit()
        conn.close()
        self.messages = self._load_messages()
        print(f"Переключено на ветку #{branch_id}")

    def _extract_facts_with_llm(self, user_input: str, last_response: str):
        prompt = f"""
        Проанализируй диалог и извлеки ключевые факты в формате JSON (ключ: значение).
        Интересуют: цели, ограничения, предпочтения, имена, технические детали.
        Если новых фактов нет, верни пустой объект .
        
        Диалог:
        User: {user_input}
        Agent: {last_response}
        """
        try:
            response = requests.post(
                url=self.base_url,
                headers=self.headers,
                data=json.dumps({
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}]
                }),
                timeout=15
            )
            result = response.json()
            content = result['choices'][0]['message']['content']
            content = content.replace("```json", "").replace("```", "").strip()
            new_facts = json.loads(content)
            for k, v in new_facts.items():
                self._update_fact(k, str(v))
        except Exception as e:
            print(f"Ошибка извлечения фактов: {e}")

    def process_request(self, user_input: str) -> str:
        user_msg = {"role": "user", "content": user_input}
        self.messages.append(user_msg)
        self._save_message(user_msg)

        final_messages = []
        
        if self.current_strategy == "sticky_facts":
            
            facts_text = "\n".join([f"- {k}: {v}" for k, v in self.facts.items()])
            if facts_text:
                final_messages.append({
                    "role": "system", 
                    "content": f"ВАЖНАЯ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ И ПРОЕКТЕ (Sticky Facts):\n{facts_text}"
                })
            final_messages.extend(self.messages[-self.window_size:])
            
        elif self.current_strategy == "sliding_window":
            final_messages.extend(self.messages[-self.window_size:])
            
        elif self.current_strategy == "branching":
            final_messages.extend(self.messages[-self.window_size:])

        total_tokens = sum([len(self.encoding.encode(json.dumps(m))) for m in final_messages])
        print(f"\n--- Стратегия: {self.current_strategy} | Ветка: {self.current_branch_id} | Токены: ~{total_tokens} ---")

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
            self._save_message(assistant_msg)
            
            if self.current_strategy == "sticky_facts":
                 self._extract_facts_with_llm(user_input, assistant_msg.get('content', ''))

            return assistant_msg.get('content', '')
        except Exception as e:
            return f"Ошибка: {e}"

    def clear_history(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages")
        cursor.execute("DELETE FROM facts")
        cursor.execute("DELETE FROM state")
        conn.commit()
        conn.close()
        self.messages = []
        self.facts = {}
        self.current_branch_id = 1
        self.current_strategy = "sliding_window"
        print("Все данные очищены.")

if __name__ == "__main__":
    API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
    if API_KEY == "sk-or-v1-...":
        print("Установите OPENROUTER_API_KEY")
        exit()

    print("--- Мульти-стратегический Агент ---")
    print("Команды: /strategy [name], /branch, /switch [id], /clear, exit")
    agent = MultiStrategyAgent(api_key=API_KEY)
    
    while True:
        user_text = input("\nВы: ")
        if user_text.lower() == 'exit': break
        
        if user_text.startswith('/'):
            parts = user_text.split()
            cmd = parts[0]
            if cmd == '/strategy' and len(parts) > 1:
                agent.set_strategy(parts[1])
            elif cmd == '/branch':
                agent.create_branch()
            elif cmd == '/switch' and len(parts) > 1:
                agent.switch_branch(int(parts[1]))
            elif cmd == '/clear':
                agent.clear_history()
            continue
            
        response = agent.process_request(user_text)
        print(f"Агент: {response}")