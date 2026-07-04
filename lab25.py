from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from lab24 import CitedRAGAgent


@dataclass
class TaskMemory:
    """Память задачи: цель, уточнения, ограничения, термины."""

    goal: str = ""
    clarifications: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    progress: list[str] = field(default_factory=list)

    def add_clarification(self, text: str):
        self.clarifications.append(text)

    def add_constraint(self, text: str):
        self.constraints.append(text)

    def add_term(self, text: str):
        if text not in self.terms:
            self.terms.append(text)

    def add_progress(self, text: str):
        self.progress.append(text)

    def describe(self) -> str:
        lines = []
        if self.goal:
            lines.append(f"Цель: {self.goal}")
        if self.clarifications:
            lines.append(f"Уточнения: {', '.join(self.clarifications[-3:])}")
        if self.constraints:
            lines.append(f"Ограничения: {', '.join(self.constraints[-3:])}")
        if self.terms:
            lines.append(f"Термины: {', '.join(self.terms[-5:])}")
        if self.progress:
            lines.append(f"Прогресс: {len(self.progress)} шагов")
        return "\n".join(lines) if lines else "(память пуста)"


class RAGChatAgent:
    """Мини-чат с RAG + памятью задачи + историей диалога."""

    def __init__(self, api_key: str, model: str = "cohere/north-mini-code:free"):
        self.rag_agent = CitedRAGAgent(api_key, model)
        self.history: list[dict] = []
        self.task_memory = TaskMemory()

    def load_index(self, path: str = "index_lab21.json"):
        """Загрузка индекса."""
        self.rag_agent.load_index(path)

    def _update_task_memory(self, user_message: str):
        """Обновление памяти задачи на основе сообщения пользователя."""
        msg_lower = user_message.lower()

        # Определение цели
        if not self.task_memory.goal:
            goal_keywords = ["хочу узнать", "расскажи про", "объясни", "помоги с", "нужно"]
            for kw in goal_keywords:
                if kw in msg_lower:
                    self.task_memory.goal = user_message
                    break

        # Определение уточнений
        clarification_keywords = ["уточни", "а что такое", "подробнее", "как именно", "почему"]
        if any(kw in msg_lower for kw in clarification_keywords):
            self.task_memory.add_clarification(user_message)

        # Определение ограничений
        constraint_keywords = ["только", "без", "не используй", "важно", "обязательно"]
        if any(kw in msg_lower for kw in constraint_keywords):
            self.task_memory.add_constraint(user_message)

        # Извлечение терминов (простая эвристика)
        tech_terms = ["asyncio", "fastapi", "docker", "git", "pytest", "sqlite", "mcp", "event loop", "endpoint"]
        for term in tech_terms:
            if term in msg_lower:
                self.task_memory.add_term(term)

    def _build_context_prompt(self, user_message: str, rag_result: dict) -> str:
        """Построение промпта с учётом памяти задачи и RAG."""
        memory_context = self.task_memory.describe()

        # История последних 5 сообщений
        recent_history = self.history[-5:]
        history_text = "\n".join(
            f"{msg['role']}: {msg['content'][:100]}"
            for msg in recent_history
        )

        # RAG контекст
        rag_context = ""
        if rag_result and not rag_result.get("is_unknown"):
            sources = rag_result.get("sources", [])
            quotes = rag_result.get("quotes", [])
            if sources or quotes:
                rag_context = "\nКонтекст из базы знаний:\n"
                if sources:
                    rag_context += f"Источники: {', '.join(sources)}\n"
                if quotes:
                    rag_context += "Цитаты:\n" + "\n".join(f'  - "{q}"' for q in quotes[:3]) + "\n"

        prompt = f"""Ты — эксперт-ассистент. Отвечай на вопрос пользователя.

СОСТОЯНИЕ ЗАДАЧИ:
{memory_context}

ИСТОРИЯ ДИАЛОГА:
{history_text if history_text else "(начало диалога)"}
{rag_context}

ПРАВИЛА:
1. Учитывай состояние задачи и историю диалога
2. Если есть контекст из базы знаний — используй его
3. ОБЯЗАТЕЛЬНО указывай источники в формате [Источник N]
4. Если не знаешь ответа — скажи "не знаю"
5. Отвечай кратко и по делу

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {user_message}

ОТВЕТ:"""
        return prompt

    def chat(self, user_message: str) -> dict:
        """Обработка сообщения пользователя."""
        start = time.time()

        # 1. Обновление памяти задачи
        self._update_task_memory(user_message)

        # 2. Поиск контекста через RAG
        rag_result = self.rag_agent.ask(user_message, top_k=3)

        # 3. Построение промпта с учётом памяти и RAG
        prompt = self._build_context_prompt(user_message, rag_result)

        # 4. Генерация ответа
        messages = [
            {"role": "system", "content": "Ты — эксперт-ассистент с памятью задачи."},
            {"role": "user", "content": prompt},
        ]
        answer = self.rag_agent._call_llm(messages)

        # 5. Добавление в историю
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": answer})
        self.task_memory.add_progress(f"Q: {user_message[:50]}...")

        elapsed = time.time() - start

        return {
            "answer": answer,
            "sources": rag_result.get("sources", []),
            "quotes": rag_result.get("quotes", []),
            "is_unknown": rag_result.get("is_unknown", False),
            "task_memory": self.task_memory.describe(),
            "elapsed": round(elapsed, 2),
        }

    def reset(self):
        """Сброс чата."""
        self.history.clear()
        self.task_memory = TaskMemory()


def run_scenario(agent: RAGChatAgent, scenario: list[str]) -> list[dict]:
    """Запуск сценария диалога."""
    results = []
    for i, message in enumerate(scenario, 1):
        print(f"\n--- Сообщение {i}/{len(scenario)} ---")
        print(f"Пользователь: {message}")
        result = agent.chat(message)
        print(f"Ассистент: {result['answer'][:150]}...")
        if result["sources"]:
            print(f"Источники: {result['sources'][:2]}")
        print(f"Память задачи:\n{result['task_memory']}")
        results.append({
            "user_message": message,
            "assistant_answer": result["answer"],
            "sources": result["sources"],
            "task_memory": result["task_memory"],
        })
        # Задержка между запросами для избежания rate limit
        if i < len(scenario):
            import time
            time.sleep(5)
    return results


# Сценарий 1: Изучение asyncio
SCENARIO_1 = [
    "Хочу узнать про asyncio в Python",
    "Что такое event loop?",
    "А как работают корутины?",
    "Объясни подробнее про await",
    "Какие есть практические примеры использования asyncio?",
    "А чем asyncio отличается от threading?",
    "Как обрабатывать ошибки в asyncio?",
    "Что такое asyncio.gather?",
    "Можно ли использовать asyncio с базами данных?",
    "Какие best practices для asyncio?",
]

# Сценарий 2: Изучение FastAPI
SCENARIO_2 = [
    "Расскажи про FastAPI",
    "Как создать простой GET endpoint?",
    "А что такое Pydantic модели?",
    "Как валидировать входные данные?",
    "Объясни middleware в FastAPI",
    "Что такое dependency injection?",
    "Как подключить базу данных?",
    "Как обрабатывать ошибки?",
    "Можно ли использовать WebSocket?",
    "Какие есть best practices для FastAPI?",
    "Как деплоить FastAPI приложение?",
]
