from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Protocol


DEFAULT_AI_MODEL = "nex-agi/nex-n2-pro:free"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class MemoryLayer(str, Enum):
    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"


class LongTermCategory(str, Enum):
    PROFILE = "profile"
    DECISION = "decision"
    KNOWLEDGE = "knowledge"


@dataclass(frozen=True)
class MemoryRecord:
    layer: MemoryLayer
    key: str
    value: Any
    reason: str
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer.value,
            "key": self.key,
            "value": self.value,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }


class MemoryStore:
    def __init__(self, short_limit: int = 8) -> None:
        self.short_term: deque[MemoryRecord] = deque(maxlen=short_limit)
        self.short_counter = 0
        self.working: Dict[str, MemoryRecord] = {}
        self.long_term: Dict[str, MemoryRecord] = {}
        self.audit_log: List[MemoryRecord] = []

    def remember_short_term(self, role: str, content: Any, reason: str) -> MemoryRecord:
        self.short_counter += 1
        record = MemoryRecord(
            layer=MemoryLayer.SHORT_TERM,
            key=f"{role}.{self.short_counter}",
            value={"role": role, "content": content},
            reason=reason,
            created_at=_now(),
        )
        self.short_term.append(record)
        self._audit(record)
        return record

    def remember_working(self, key: str, value: Any, reason: str) -> MemoryRecord:
        record = MemoryRecord(
            layer=MemoryLayer.WORKING,
            key=key,
            value=value,
            reason=reason,
            created_at=_now(),
        )
        self.working[key] = record
        self._audit(record)
        return record

    def remember_long_term(
        self,
        category: LongTermCategory,
        key: str,
        value: Any,
        reason: str,
    ) -> MemoryRecord:
        full_key = f"{category.value}.{key}"
        record = MemoryRecord(
            layer=MemoryLayer.LONG_TERM,
            key=full_key,
            value=value,
            reason=reason,
            created_at=_now(),
        )
        self.long_term[full_key] = record
        self._audit(record)
        return record

    def remember(
        self,
        layer: MemoryLayer,
        key: str,
        value: Any,
        reason: str,
        *,
        role: Optional[str] = None,
        category: Optional[LongTermCategory] = None,
    ) -> MemoryRecord:
        if layer == MemoryLayer.SHORT_TERM:
            if role is None:
                raise ValueError("Для краткосрочной памяти нужно указать role")
            return self.remember_short_term(role, value, reason)

        if layer == MemoryLayer.WORKING:
            return self.remember_working(key, value, reason)

        if category is None:
            category = _category_from_key(key)
        return self.remember_long_term(category, key, value, reason)

    def clear_short_term(self) -> None:
        self.short_term.clear()

    def clear_working(self) -> None:
        self.working.clear()

    def clear_long_term(self) -> None:
        self.long_term.clear()

    def forget_working(self, key: str) -> None:
        self.working.pop(key, None)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "short_term": [record.to_dict() for record in self.short_term],
            "working_memory": {
                key: record.to_dict() for key, record in self.working.items()
            },
            "long_term_memory": {
                key: record.to_dict() for key, record in self.long_term.items()
            },
            "audit_log": [record.to_dict() for record in self.audit_log],
        }

    def describe(self) -> str:
        lines = [
            "Слои памяти:",
            _format_layer(
                MemoryLayer.SHORT_TERM,
                "текущий диалог",
                [record.to_dict() for record in self.short_term],
            ),
            _format_layer(
                MemoryLayer.WORKING,
                "данные текущей задачи",
                [record.to_dict() for record in self.working.values()],
            ),
            _format_layer(
                MemoryLayer.LONG_TERM,
                "профиль, решения, знания",
                [record.to_dict() for record in self.long_term.values()],
            ),
        ]
        return "\n".join(lines)

    def last_user_message(self) -> Optional[str]:
        for record in reversed(self.short_term):
            value = record.value
            if isinstance(value, dict) and value.get("role") == "user":
                return str(value.get("content", ""))
        return None

    def _audit(self, record: MemoryRecord) -> None:
        self.audit_log.append(record)


@dataclass
class AIModelConfig:
    model: str = DEFAULT_AI_MODEL
    api_url: str = OPENROUTER_API_URL
    reasoning_enabled: bool = True
    temperature: Optional[float] = 0.2
    timeout: int = 60


@dataclass
class AIModelResponse:
    content: str
    raw: Any
    reasoning_details: Optional[Any] = None


class AIModel(Protocol):
    def complete(self, messages: List[Dict[str, Any]]) -> AIModelResponse:
        ...


class OpenRouterAIModel:
    def __init__(
        self,
        config: Optional[AIModelConfig] = None,
        api_key: Optional[str] = "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",
    ) -> None:
        self.config = config or AIModelConfig()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY не задан. "
                "Задайте его перед запуском: export OPENROUTER_API_KEY=sk-or-v1-..."
            )

    def complete(self, messages: List[Dict[str, Any]]) -> AIModelResponse:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("Для OpenRouter нужен requests: pip install requests") from exc

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "reasoning": {"enabled": self.config.reasoning_enabled},
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            url=self.config.api_url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )
        try:
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"OpenRouter error: {exc}\n{response.text}") from exc

        data = response.json()
        choices = data.get("choices")
        if not choices:
            raise RuntimeError(f"OpenRouter вернул ответ без choices: {data}")

        message = choices[0].get("message", {})
        content = message.get("content") or ""
        reasoning_details = message.get("reasoning_details")

        return AIModelResponse(
            content=content,
            raw=data,
            reasoning_details=reasoning_details,
        )


class MemoryAgent:
    def __init__(self, name: str = "MemoryAgent", short_limit: int = 8) -> None:
        self.name = name
        self.memory = MemoryStore(short_limit=short_limit)
        self.ai_model: Optional[AIModel] = None
        self.ai_messages: List[Dict[str, Any]] = []
        self.default_use_ai = False

    def use_ai_model(self, model: AIModel) -> None:
        self.ai_model = model
        self.default_use_ai = True

    def start_task(self, task_name: str, task_goal: Optional[str] = None) -> None:
        self.memory.remember_working("task.name", task_name, "начало текущей задачи")
        if task_goal:
            self.memory.remember_working("task.goal", task_goal, "цель текущей задачи")

    def remember_short_term(self, role: str, content: Any, reason: str) -> MemoryRecord:
        return self.memory.remember_short_term(role, content, reason)

    def remember_working(self, key: str, value: Any, reason: str) -> MemoryRecord:
        return self.memory.remember_working(key, value, reason)

    def remember_long_term(
        self,
        category: LongTermCategory,
        key: str,
        value: Any,
        reason: str,
    ) -> MemoryRecord:
        return self.memory.remember_long_term(category, key, value, reason)

    def respond(
        self,
        message: str,
        *,
        use_ai: Optional[bool] = None,
        remember_layer: Optional[MemoryLayer] = None,
        remember_key: Optional[str] = None,
        remember_value: Optional[Any] = None,
        remember_reason: Optional[str] = None,
        remember_role: Optional[str] = None,
        remember_category: Optional[LongTermCategory] = None,
    ) -> str:
        previous_user_message = self.memory.last_user_message()

        self.memory.remember_short_term(
            "user",
            message,
            "автоматически: текущий диалог",
        )

        if remember_layer is not None:
            key = remember_key or _make_key(message)
            value = remember_value if remember_value is not None else message
            reason = remember_reason or "явно сохранено пользователем"
            self.memory.remember(
                remember_layer,
                key,
                value,
                reason,
                role=remember_role,
                category=remember_category,
            )

        if use_ai if use_ai is not None else self.default_use_ai:
            if self.ai_model is None:
                raise RuntimeError("AI-модель не подключена к агенту")
            answer = self._answer_with_ai(message, previous_user_message)
        else:
            answer = self._answer(message, previous_user_message)

        self.memory.remember_short_term(
            "assistant",
            answer,
            "автоматически: текущий диалог",
        )
        return answer

    def process_request(self, user_input: str, *, use_ai: Optional[bool] = None) -> str:
        return self.respond(user_input, use_ai=use_ai)

    def clear_history(self) -> None:
        self.memory.clear_short_term()
        self.memory.clear_working()
        self.memory.clear_long_term()
        self.ai_messages.clear()

    def _answer(self, message: str, previous_user_message: Optional[str]) -> str:
        lower = message.lower()

        if "слой" in lower and "памят" in lower:
            return (
                "Я использую три отдельных слоя памяти: краткосрочную для текущего "
                "диалога, рабочую для данных текущей задачи и долговременную для "
                "профиля, решений и знаний."
            )

        if "что ты знаешь обо мне" in lower or "моё имя" in lower or "как меня зовут" in lower:
            name = self._long_term_value("profile.name")
            if name:
                return f"В долговременной памяти я храню ваше имя: {name}."
            return "В долговременной памяти пока нет данных о вашем имени."

        if "текущ" in lower or "рабоч" in lower or "задач" in lower:
            task_name = self._working_value("task.name")
            task_goal = self._working_value("task.goal")
            deadline = self._working_value("deadline")
            parts = []
            if task_name:
                parts.append(f"задача: {task_name}")
            if task_goal:
                parts.append(f"цель: {task_goal}")
            if deadline:
                parts.append(f"дедлайн: {deadline}")
            if parts:
                return "В рабочей памяти: " + "; ".join(parts) + "."
            return "Рабочая память пуста."

        if ("сказал" in lower or "спросил" in lower) and ("последн" in lower or "перед" in lower):
            if previous_user_message:
                return f"В краткосрочной памяти: до этого вы сказали: «{previous_user_message}»."
            return "В краткосрочной памяти пока нет предыдущих сообщений."

        if "что ты помнишь" in lower:
            return self._summary_answer()

        if "решение" in lower:
            decisions = self._values_by_prefix("decision.")
            if decisions:
                return "В долговременной памяти есть решения: " + "; ".join(decisions) + "."
            return "В долговременной памяти пока нет решений."

        if "знание" in lower:
            knowledge = self._values_by_prefix("knowledge.")
            if knowledge:
                return "В долговременной памяти есть знания: " + "; ".join(knowledge) + "."
            return "В долговременной памяти пока нет знаний."

        return "Я обработал сообщение и сохранил его только в краткосрочную память текущего диалога."

    def _answer_with_ai(self, message: str, previous_user_message: Optional[str]) -> str:
        if self.ai_model is None:
            raise RuntimeError("AI-модель не подключена к агенту")

        messages = self._build_ai_messages(message, previous_user_message)
        response = self.ai_model.complete(messages)

        assistant_message: Dict[str, Any] = {
            "role": "assistant",
            "content": response.content,
        }
        if response.reasoning_details is not None:
            assistant_message["reasoning_details"] = response.reasoning_details
        self.ai_messages.append(assistant_message)

        return response.content

    def _build_ai_messages(self, message: str, previous_user_message: Optional[str]) -> List[Dict[str, Any]]:
        user_content = (
            "Ты AI-модель внутри ассистента с явной моделью памяти.\n"
            "Используй переданные слои памяти, но не выдумывай данные, которых там нет.\n"
            "Отвечай кратко на русском.\n\n"
            f"Предыдущее сообщение пользователя: {previous_user_message or 'нет'}\n"
            f"Текущий вопрос пользователя: {message}\n\n"
            "Память агента:\n"
            f"{self._memory_context_for_ai()}"
        )
        return [
            {"role": "system", "content": self._system_prompt()},
            *self.ai_messages,
            {"role": "user", "content": user_content},
        ]

    def _system_prompt(self) -> str:
        return (
            "Ты ассистент с тремя раздельными слоями памяти:\n"
            "1. short_term — текущий диалог.\n"
            "2. working — данные текущей задачи.\n"
            "3. long_term — профиль, решения и знания.\n\n"
            "При ответе явно указывай, какой слой памяти повлиял на ответ. "
            "Если данных нет, так и говори."
        )

    def _memory_context_for_ai(self) -> str:
        short_lines = []
        for record in list(self.memory.short_term)[-6:]:
            value = record.value
            if isinstance(value, dict):
                short_lines.append(
                    f"- {value.get('role')}: {value.get('content')} "
                    f"({record.reason})"
                )

        working_lines = [
            f"- {record.key}: {record.value} ({record.reason})"
            for record in self.memory.working.values()
        ]

        long_lines = [
            f"- {record.key}: {record.value} ({record.reason})"
            for record in self.memory.long_term.values()
        ]

        return (
            "short_term:\n"
            + ("\n".join(short_lines) if short_lines else "- пусто\n")
            + "\nworking:\n"
            + ("\n".join(working_lines) if working_lines else "- пусто\n")
            + "\nlong_term:\n"
            + ("\n".join(long_lines) if long_lines else "- пусто")
        )

    def _summary_answer(self) -> str:
        long_term_items = self._values_by_prefix("")
        working_items = [str(record.value) for record in self.working_records()]
        short_items = [
            str(record.value.get("content"))
            for record in self.short_term_records()
            if isinstance(record.value, dict)
        ]

        parts = []
        if long_term_items:
            parts.append("долговременная: " + "; ".join(long_term_items))
        if working_items:
            parts.append("рабочая: " + "; ".join(working_items))
        if short_items:
            parts.append("краткосрочная: последние реплики — " + "; ".join(short_items[-3:]))
        return "Сейчас я помню: " + " | ".join(parts) + "." if parts else "Пока ничего не помню."

    def short_term_records(self) -> Iterable[MemoryRecord]:
        return self.memory.short_term

    def working_records(self) -> Iterable[MemoryRecord]:
        return self.memory.working.values()

    def long_term_records(self) -> Iterable[MemoryRecord]:
        return self.memory.long_term.values()

    def _working_value(self, key: str) -> Optional[str]:
        record = self.memory.working.get(key)
        return None if record is None else str(record.value)

    def _long_term_value(self, key: str) -> Optional[str]:
        record = self.memory.long_term.get(key)
        return None if record is None else str(record.value)

    def _values_by_prefix(self, prefix: str) -> List[str]:
        return [str(record.value) for key, record in self.memory.long_term.items() if key.startswith(prefix)]


def _now() -> datetime:
    return datetime.now()


def _make_key(text: str) -> str:
    words = "".join(ch for ch in text if ch.isalnum() or ch.isspace()).split()
    return "_".join(words[:4])[:60] or "saved_item"


def _category_from_key(key: str) -> LongTermCategory:
    if key.startswith("profile."):
        return LongTermCategory.PROFILE
    if key.startswith("decision."):
        return LongTermCategory.DECISION
    if key.startswith("knowledge."):
        return LongTermCategory.KNOWLEDGE
    return LongTermCategory.KNOWLEDGE


def _format_layer(layer: MemoryLayer, purpose: str, records: List[Dict[str, Any]]) -> str:
    if not records:
        return f"- {layer.value}: {purpose}; записей: 0"
    lines = [f"- {layer.value}: {purpose}; записей: {len(records)}"]
    for record in records:
        lines.append(
            f"  * {record['key']} = {record['value']!r} "
            f"({record['reason']})"
        )
    return "\n".join(lines)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def create_openrouter_model() -> OpenRouterAIModel:
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_AI_MODEL)
    temperature = _env_float("OPENROUTER_TEMPERATURE", 0.2)
    reasoning_enabled = _env_bool("OPENROUTER_REASONING", True)
    return OpenRouterAIModel(
        AIModelConfig(
            model=model,
            reasoning_enabled=reasoning_enabled,
            temperature=temperature,
        )
    )


def run_checks() -> None:
    store = MemoryStore()

    store.remember_short_term("user", "Привет", "текущий диалог")
    assert len(store.short_term) == 1
    assert not store.working
    assert not store.long_term

    store.remember_working("deadline", "пятница 18:00", "ограничение задачи")
    assert "deadline" in store.working
    assert len(store.short_term) == 1
    assert not store.long_term

    store.remember_long_term(
        LongTermCategory.PROFILE,
        "name",
        "Алексей",
        "пользователь сообщил имя",
    )
    assert "profile.name" in store.long_term
    assert "deadline" in store.working
    assert len(store.short_term) == 1

    agent = MemoryAgent()
    agent.start_task("Подготовка отчёта", "показать модель памяти")
    agent.remember_long_term(
        LongTermCategory.PROFILE,
        "name",
        "Алексей",
        "пользователь сообщил имя",
    )
    agent.remember_working("deadline", "пятница 18:00", "ограничение текущей задачи")

    assert "Алексей" in agent.respond("Как меня зовут?")
    assert "Подготовка отчёта" in agent.respond("Какая текущая задача?")
    assert "пятница 18:00" in agent.respond("Что в рабочей памяти?")
    assert "Алексей" in agent.respond("Что ты знаешь обо мне?")
    assert agent.memory.snapshot()["audit_log"]

    print("Проверки memory layers пройдены.")


def run_demo() -> None:
    agent = MemoryAgent()

    print("=== Модель памяти ассистента ===")
    print(
        "Краткосрочная память хранит текущий диалог. "
        "Рабочая память хранит данные текущей задачи. "
        "Долговременная память хранит профиль, решения и знания."
    )
    print()

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"ИИ-модель подключена: {DEFAULT_AI_MODEL}")
        ai_ready = True
    except RuntimeError as exc:
        print(f"ИИ-модель не подключена: {exc}")
        print("Демо продолжит работу на rule-based ответах.")
        ai_ready = False
    print()

    agent.start_task("Подготовка презентации", "показать работу memory layers")

    print("1. Явно сохраняем имя в долговременную память.")
    agent.respond(
        "Меня зовут Алексей",
        remember_layer=MemoryLayer.LONG_TERM,
        remember_key="name",
        remember_value="Алексей",
        remember_reason="пользователь сообщил имя",
        remember_category=LongTermCategory.PROFILE,
    )
    print("(сохранено в long_term: profile.name)")
    print()

    print("2. Явно сохраняем дедлайн в рабочую память.")
    agent.respond(
        "Дедлайн — пятница 18:00",
        remember_layer=MemoryLayer.WORKING,
        remember_key="deadline",
        remember_value="пятница 18:00",
        remember_reason="ограничение текущей задачи",
    )
    print("(сохранено в working: deadline)")
    print()

    print("3. Явно сохраняем решение в долговременную память.")
    agent.respond(
        "Формат ответов — краткий, с указанием слоя памяти",
        remember_layer=MemoryLayer.LONG_TERM,
        remember_key="default_format",
        remember_value="краткие ответы с явным указанием слоя памяти",
        remember_reason="решение о стиле ответов",
        remember_category=LongTermCategory.DECISION,
    )
    print("(сохранено в long_term: decision.default_format)")
    print()

    print("4. Ответ AI зависит от долговременной памяти.")
    print(agent.respond("Как меня зовут?", use_ai=ai_ready))
    print()

    print("5. Ответ AI зависит от рабочей памяти.")
    print(agent.respond("Что сейчас в рабочей памяти?", use_ai=ai_ready))
    print()

    print("6. Ответ AI зависит от краткосрочной памяти.")
    print(agent.respond("Что я сказал перед этим вопросом?", use_ai=ai_ready))
    print()

    print("7. Проверка раздельного хранения слоёв.")
    print(agent.memory.describe())


def print_help() -> None:
    print(
        "\nКоманды:\n"
        "  /short <текст>                         — сохранить в краткосрочную память\n"
        "  /working <ключ> <значение>             — сохранить в рабочую память\n"
        "  /long <profile|decision|knowledge> <ключ> <значение> — сохранить в долговременную\n"
        "  /ask <вопрос>                          — отправить вопрос агенту\n"
        "  /task <название> [цель]                — начать новую задачу\n"
        "  /memory                                — показать все слои памяти\n"
        "  /ai on|off                             — включить или выключить AI-модель\n"
        "  /clear                                 — очистить память агента\n"
        "  /help                                  — показать команды\n"
        "  exit                                   — выйти\n"
    )


def run_cli() -> None:
    agent = MemoryAgent()

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("AI выключен: OPENROUTER_API_KEY не задан. Можно писать /ai on после настройки ключа.")

    print("--- Агент с memory layers ---")
    print_help()

    while True:
        try:
            user_text = input("\nВы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not user_text:
            continue
        if user_text.lower() in {"exit", "выход"}:
            print("Выход.")
            break

        if user_text.startswith("/"):
            parts = user_text.split(maxsplit=3)
            cmd = parts[0].lower()

            if cmd == "/help":
                print_help()

            elif cmd == "/memory":
                print(agent.memory.describe())

            elif cmd == "/clear":
                agent.clear_history()
                print("Память агента очищена.")

            elif cmd == "/task":
                if len(parts) < 2:
                    print("Использование: /task <название задачи> [цель]")
                else:
                    task_name = parts[1]
                    task_goal = parts[2] if len(parts) > 2 else None
                    agent.start_task(task_name, task_goal)
                    print(f"Задача начата: {task_name}")

            elif cmd == "/short":
                text = user_text[len(cmd):].strip()
                if not text:
                    print("Использование: /short <текст>")
                else:
                    agent.remember_short_term("user", text, "явно сохранено через CLI")
                    print("Сохранено в short_term.")

            elif cmd == "/working":
                if len(parts) < 3:
                    print("Использование: /working <ключ> <значение>")
                else:
                    key = parts[1]
                    value = parts[2]
                    agent.remember_working(key, value, "явно сохранено через CLI")
                    print(f"Сохранено в working: {key} = {value}")

            elif cmd == "/long":
                if len(parts) < 4:
                    print("Использование: /long <profile|decision|knowledge> <ключ> <значение>")
                else:
                    category_name = parts[1].lower()
                    key = parts[2]
                    value = parts[3]
                    category_map = {
                        "profile": LongTermCategory.PROFILE,
                        "decision": LongTermCategory.DECISION,
                        "knowledge": LongTermCategory.KNOWLEDGE,
                    }
                    category = category_map.get(category_name)
                    if category is None:
                        print("Категория должна быть: profile, decision или knowledge")
                    else:
                        agent.remember_long_term(category, key, value, "явно сохранено через CLI")
                        print(f"Сохранено в long_term: {category.value}.{key} = {value}")

            elif cmd == "/ask":
                text = user_text[len(cmd):].strip()
                if not text:
                    print("Использование: /ask <вопрос>")
                else:
                    try:
                        print(f"Агент: {agent.process_request(text)}")
                    except RuntimeError as exc:
                        print(f"Ошибка AI: {exc}")

            elif cmd == "/ai":
                if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
                    print("Использование: /ai on или /ai off")
                elif parts[1].lower() == "on":
                    try:
                        agent.use_ai_model(create_openrouter_model())
                        print(f"AI включён: {DEFAULT_AI_MODEL}")
                    except RuntimeError as exc:
                        print(f"Не удалось включить AI: {exc}")
                else:
                    agent.ai_model = None
                    agent.default_use_ai = False
                    print("AI выключен.")

            else:
                print("Неизвестная команда. Введите /help")
            continue

        try:
            print(f"Агент: {agent.process_request(user_text)}")
        except RuntimeError as exc:
            print(f"Ошибка AI: {exc}")


if __name__ == "__main__":
    run_cli()
