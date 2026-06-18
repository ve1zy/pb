from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from lab13 import (
    DEFAULT_AI_MODEL,
    LongTermCategory,
    MemoryAgent,
    TaskStateAgent,
    _profile_key,
    create_openrouter_model,
)


class InvariantCategory(str, Enum):
    ARCHITECTURE = "architecture"
    TECHNICAL_DECISION = "technical_decision"
    STACK = "stack"
    BUSINESS_RULE = "business_rule"
    SECURITY = "security"
    QUALITY = "quality"


@dataclass(frozen=True)
class Invariant:
    key: str
    category: InvariantCategory
    statement: str
    rationale: str = "принято командой"

    def memory_key(self) -> str:
        return f"invariant.{self.category.value}.{self.key}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "category": self.category.value,
            "statement": self.statement,
            "rationale": self.rationale,
        }

    def to_prompt(self) -> str:
        return f"[{self.category.value}:{self.key}] {self.statement} Причина: {self.rationale}"

    def conflicts_with(self, request_text: str) -> Optional[str]:
        text = request_text.lower()
        statement = self.statement.lower()
        category = self.category.value
        category_reason: Optional[str] = None

        if category == "architecture":
            if "монолит" in statement and any(term in text for term in ["микросервис", "microservice", "микросервисы"]):
                category_reason = "запрос предлагает микросервисы, хотя выбрана архитектура модульного монолита"
            elif "микросервис" in statement and any(term in text for term in ["монолит", "modular monolith"]):
                category_reason = "запрос предлагает монолит, хотя выбрана микросервисная архитектура"

        if category in {"stack", "technical_decision"}:
            if "python" in statement and any(term in text for term in ["node.js", "nodejs", "java", "php", "ruby", " go ", " golang"]):
                category_reason = "запрос предлагает backend не на Python, хотя стек ограничен Python"
            elif any(db in statement for db in ["postgresql", "postgres"]) and any(
                term in text for term in ["mongodb", "mongo", "mysql", "sqlite", "redis as main db"]
            ):
                category_reason = "запрос предлагает другую основную БД, хотя выбрана PostgreSQL"

        if category == "business_rule":
            if "без" in statement and "соглас" in statement and any(
                term in text for term in ["персональ", "паспорт", "passport", "телефон", "phone", "email", "почт"]
            ):
                category_reason = "запрос предполагает работу с персональными данными без согласия"

        if category_reason:
            return category_reason

        if category != "business_rule" and ("нельзя" in statement or "запрещ" in statement or "must not" in statement or "do not" in statement):
            forbidden_terms = [
                term
                for term in ["микросервис", "node.js", "nodejs", "java", "mongodb", "mongo", "персональ", "паспорт"]
                if term in text
            ]
            if forbidden_terms:
                return "запрос содержит запрещённое решение: " + ", ".join(forbidden_terms)

        return None


@dataclass(frozen=True)
class InvariantConflict:
    invariant: Invariant
    request_text: str
    reason: str

    def explanation(self) -> str:
        return (
            f"Запрос: «{self.request_text}». "
            f"Запрос нарушает инвариант {self.invariant.memory_key()}: "
            f"«{self.invariant.statement}». "
            f"Причина инварианта: {self.invariant.rationale}. "
            f"Конфликт: {self.reason}."
        )


class InvariantStore:
    def __init__(self) -> None:
        self.invariants: Dict[str, Invariant] = {}

    def add(self, invariant: Invariant) -> Invariant:
        self.invariants[invariant.key] = invariant
        return invariant

    def remove(self, key: str) -> bool:
        return self.invariants.pop(key, None) is not None

    def get(self, key: str) -> Optional[Invariant]:
        return self.invariants.get(key)

    def values(self) -> Iterable[Invariant]:
        return self.invariants.values()

    def find_conflicts(self, request_text: str) -> List[InvariantConflict]:
        conflicts = []
        for invariant in self.invariants.values():
            reason = invariant.conflicts_with(request_text)
            if reason:
                conflicts.append(InvariantConflict(invariant, request_text, reason))
        return conflicts

    def to_prompt(self) -> str:
        if not self.invariants:
            return "Инварианты не заданы."
        lines = ["Жёсткие инварианты, которые нельзя нарушать:"]
        for invariant in self.invariants.values():
            lines.append(f"- {invariant.to_prompt()}")
        lines.append("Если запрос конфликтует с любым инвариантом, откажи и объясни конфликт.")
        return "\n".join(lines)

    def describe(self) -> str:
        if not self.invariants:
            return "Инварианты: не заданы."
        lines = ["Инварианты:"]
        for invariant in self.invariants.values():
            lines.append(
                f"- {invariant.memory_key()}: {invariant.statement} "
                f"(причина: {invariant.rationale})"
            )
        return "\n".join(lines)

    def persist_to_memory(self, memory: MemoryAgent) -> None:
        for invariant in self.invariants.values():
            memory.remember_long_term(
                LongTermCategory.KNOWLEDGE,
                invariant.memory_key(),
                invariant.to_dict(),
                "жёсткий инвариант состояния",
            )


class InvariantAgent(TaskStateAgent):
    def __init__(self, name: str = "InvariantAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.invariants = InvariantStore()
        self._add_default_invariants()
        self._persist_invariants()

    def add_invariant(
        self,
        category: InvariantCategory,
        key: str,
        statement: str,
        rationale: str = "принято командой",
    ) -> Invariant:
        invariant = Invariant(key=key, category=category, statement=statement, rationale=rationale)
        self.invariants.add(invariant)
        self._persist_invariants()
        return invariant

    def remove_invariant(self, key: str) -> None:
        if not self.invariants.remove(key):
            raise KeyError(f"Инвариант не найден: {key}")
        self._persist_invariants()

    def process_request(self, user_input: str, *, use_ai: Optional[bool] = None) -> str:
        self._persist_invariants()

        conflicts = self.invariants.find_conflicts(user_input)
        if conflicts:
            return self._refuse(conflicts)

        if self._should_use_ai(use_ai):
            if self.ai_model is None:
                raise RuntimeError("AI-модель не подключена к агенту")
            return super().process_request(user_input, use_ai=True)

        self._persist_task_state()
        return self._rule_answer(user_input)

    def _rule_answer(self, user_input: str) -> str:
        lower = user_input.lower()

        if "инвариант" in lower or "ограничен" in lower or "архитектур" in lower or "стек" in lower or "бизнес-правил" in lower:
            return self.invariants.describe()

        return super()._rule_answer(user_input)

    def _system_prompt(self) -> str:
        base_prompt = super()._system_prompt()
        return (
            f"{base_prompt}\n\n"
            f"{self.invariants.to_prompt()}\n\n"
            "При ответе явно проверяй инварианты. Не предлагай решения, которые их нарушают. "
            "При конфликте откажи и объясни, какой инвариант нарушен и почему."
        )

    def _memory_context_for_ai(self) -> str:
        context = super()._memory_context_for_ai()
        return f"{context}\n\ninvariants:\n{self.invariants.to_prompt()}"

    def _refuse(self, conflicts: List[InvariantConflict]) -> str:
        lines = ["Отказ: запрос нарушает заданные инварианты."]
        for conflict in conflicts:
            lines.append(conflict.explanation())
        lines.append("Я не буду предлагать решение, которое нарушает эти ограничения.")
        return "\n".join(lines)

    def _should_use_ai(self, use_ai: Optional[bool]) -> bool:
        return self.default_use_ai if use_ai is None else use_ai

    def _persist_invariants(self) -> None:
        self.invariants.persist_to_memory(self)

    def _add_default_invariants(self) -> None:
        self.invariants.add(
            Invariant(
                key="modular_monolith",
                category=InvariantCategory.ARCHITECTURE,
                statement="Выбранная архитектура — модульный монолит; микросервисы не использовать без отдельного согласования.",
                rationale="команда выбрала модульный монолит для скорости доставки и простоты эксплуатации",
            )
        )
        self.invariants.add(
            Invariant(
                key="python_stack",
                category=InvariantCategory.STACK,
                statement="Стек сервиса: Python, FastAPI, PostgreSQL; другие backend-языки и основные БД не использовать.",
                rationale="принятое техническое решение команды",
            )
        )
        self.invariants.add(
            Invariant(
                key="no_personal_data_without_consent",
                category=InvariantCategory.BUSINESS_RULE,
                statement="Нельзя хранить персональные данные пользователей без явного согласия.",
                rationale="бизнес-правило и требование приватности",
            )
        )


def _normalize_category(value: str) -> InvariantCategory:
    mapping = {
        "architecture": InvariantCategory.ARCHITECTURE,
        "technical": InvariantCategory.TECHNICAL_DECISION,
        "decision": InvariantCategory.TECHNICAL_DECISION,
        "stack": InvariantCategory.STACK,
        "business": InvariantCategory.BUSINESS_RULE,
        "security": InvariantCategory.SECURITY,
        "quality": InvariantCategory.QUALITY,
    }
    key = value.lower().strip()
    if key not in mapping:
        raise ValueError("Категория должна быть: architecture, technical, stack, business, security или quality")
    return mapping[key]


def print_help() -> None:
    print(
        "\nКоманды lab11/lab12/lab13:\n"
        "  /short <текст>                        — сохранить в краткосрочную память\n"
        "  /working <ключ> <значение>            — сохранить в рабочую память\n"
        "  /long <profile|decision|knowledge> <ключ> <значение>\n"
        "  /task <название> [цель]               — начать задачу\n"
        "  /profiles                             — показать профили\n"
        "  /profile [имя]                        — показать профиль\n"
        "  /new <имя>                            — создать профиль\n"
        "  /switch <имя>                         — переключить профиль\n"
        "  /set <style|format|constraints|goals> <значение>\n"
        "  /start [название]                     — начать задачу FSM\n"
        "  /state                                — показать состояние FSM\n"
        "  /advance [результат]                  — завершить шаг FSM\n"
        "  /pause                                — пауза FSM\n"
        "  /resume                               — продолжить FSM\n"
        "  /step <номер>                         — шаг FSM\n"
        "  /action <ожидаемое действие>          — действие FSM\n"
        "  /stage <planning|execution|validation|done>\n"
        "\nКоманды инвариантов lab14:\n"
        "  /invariants                           — показать инварианты\n"
        "  /add <category> <key> <statement> [rationale]\n"
        "  /remove <key>                       — удалить инвариант\n"
        "  /ask <вопрос>                       — отправить вопрос агенту\n"
        "  /memory                             — показать память\n"
        "  /ai on|off                          — включить или выключить AI-модель\n"
        "  /demo                               — показать конфликт запроса и инварианта\n"
        "  /clear                              — очистить память и инварианты\n"
        "  /help                               — показать команды\n"
        "  exit                                — выйти\n"
    )


def run_invariant_checks() -> None:
    agent = InvariantAgent()

    allowed_answer = agent.process_request("Предложи план развития сервиса на Python, FastAPI и PostgreSQL", use_ai=False)
    stack_conflict = agent.process_request("Давай перепишем backend на Node.js и MongoDB", use_ai=False)
    architecture_conflict = agent.process_request("Разбей сервис на микросервисы", use_ai=False)
    business_conflict = agent.process_request("Сохрани паспортные данные пользователей без согласия", use_ai=False)

    assert "Отказ" in stack_conflict
    assert "python_stack" in stack_conflict
    assert "Node.js" in stack_conflict or "MongoDB" in stack_conflict
    assert "modular_monolith" in architecture_conflict
    assert "микросервис" in architecture_conflict
    assert "no_personal_data_without_consent" in business_conflict
    assert "персональные данные" in business_conflict or "паспортные данные" in business_conflict
    assert "Отказ" not in allowed_answer
    assert any("invariant." in key for key in agent.memory.long_term)

    print("Проверки инвариантов пройдены.")


def run_demo() -> None:
    agent = InvariantAgent()

    print("--- Инварианты и ограничения состояния ---")
    print(agent.invariants.describe())
    print()

    print("Запрос без конфликта:")
    print(agent.process_request("Предложи план развития сервиса на Python, FastAPI и PostgreSQL", use_ai=False))
    print()

    print("Запрос с конфликтом стека:")
    print(agent.process_request("Давай перепишем backend на Node.js и MongoDB", use_ai=False))
    print()

    print("Запрос с конфликтом архитектуры:")
    print(agent.process_request("Разбей сервис на микросервисы", use_ai=False))
    print()

    print(agent.memory.describe())


def run_cli() -> None:
    agent = InvariantAgent()

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("AI выключен: OPENROUTER_API_KEY не задан. Можно писать /ai on после настройки ключа.")

    print("--- Ассистент с инвариантами ---")
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
            parts = user_text.split(maxsplit=4)
            cmd = parts[0].lower()

            if cmd == "/help":
                print_help()

            elif cmd == "/memory":
                print(agent.memory.describe())

            elif cmd == "/short":
                text = user_text[len(cmd):].strip()
                if not text:
                    print("Использование: /short <текст>")
                else:
                    agent.remember_short_term("user", text, "явно сохранено через CLI lab11")
                    print("Сохранено в short_term.")

            elif cmd == "/working":
                if len(parts) < 3:
                    print("Использование: /working <ключ> <значение>")
                else:
                    agent.remember_working(parts[1], parts[2], "явно сохранено через CLI lab11")
                    print(f"Сохранено в working: {parts[1]} = {parts[2]}")

            elif cmd == "/long":
                if len(parts) < 4:
                    print("Использование: /long <profile|decision|knowledge> <ключ> <значение>")
                else:
                    category_map = {
                        "profile": LongTermCategory.PROFILE,
                        "decision": LongTermCategory.DECISION,
                        "knowledge": LongTermCategory.KNOWLEDGE,
                    }
                    category = category_map.get(parts[1].lower())
                    if category is None:
                        print("Категория должна быть: profile, decision или knowledge")
                    else:
                        agent.remember_long_term(category, parts[2], parts[3], "явно сохранено через CLI lab11")
                        print(f"Сохранено в long_term: {category.value}.{parts[2]} = {parts[3]}")

            elif cmd == "/task":
                if len(parts) < 2:
                    print("Использование: /task <название задачи> [цель]")
                else:
                    agent.start_task(parts[1], parts[2] if len(parts) > 2 else None)
                    print(f"Задача начата: {parts[1]}")

            elif cmd == "/profiles":
                for key, profile in agent.profiles.items():
                    marker = " (активный)" if key == agent.active_profile_name else ""
                    print(f"- {profile.name}{marker}: {profile.style}, {profile.response_format}")

            elif cmd == "/profile":
                if len(parts) > 1:
                    key = _profile_key(parts[1])
                    profile = agent.profiles.get(key)
                    if profile is None:
                        print(f"Профиль не найден: {parts[1]}")
                    else:
                        print(profile.to_prompt())
                else:
                    print(agent.active_profile.to_prompt())

            elif cmd == "/new":
                if len(parts) < 2:
                    print("Использование: /new <имя профиля>")
                else:
                    profile = agent.create_profile(UserProfile(name=parts[1]), switch=True)
                    print(f"Создан профиль: {profile.name}")

            elif cmd == "/switch":
                if len(parts) < 2:
                    print("Использование: /switch <имя профиля>")
                else:
                    try:
                        profile = agent.switch_profile(parts[1])
                        print(f"Активный профиль: {profile.name}")
                    except KeyError as exc:
                        print(exc)

            elif cmd == "/set":
                if len(parts) < 3:
                    print("Использование: /set <style|format|constraints|goals|note:key> <значение>")
                else:
                    try:
                        agent.update_profile_field(parts[1], parts[2])
                        print("Профиль обновлён.")
                    except ValueError as exc:
                        print(exc)

            elif cmd == "/start":
                title = user_text[len(cmd):].strip() or "Новая задача"
                print(agent.start_task(title))

            elif cmd == "/state":
                print(agent.task.describe())

            elif cmd == "/advance":
                result = user_text[len(cmd):].strip() or None
                try:
                    agent.task.advance(result)
                    agent._persist_task_state()
                    print(agent.task.describe())
                except RuntimeError as exc:
                    print(exc)

            elif cmd == "/pause":
                agent.task.pause()
                agent._persist_task_state()
                print(f"Пауза на этапе {agent.task.stage.value}.")

            elif cmd == "/resume":
                agent.task.resume()
                agent._persist_task_state()
                print(agent.task.describe())

            elif cmd == "/step":
                if len(parts) < 2:
                    print("Использование: /step <номер шага>")
                else:
                    try:
                        agent.task.set_current_step(int(parts[1]))
                        agent._persist_task_state()
                        print(agent.task.describe())
                    except ValueError as exc:
                        print(exc)

            elif cmd == "/action":
                action = user_text[len(cmd):].strip()
                if not action:
                    print("Использование: /action <ожидаемое действие>")
                else:
                    agent.task.set_expected_action(action)
                    agent._persist_task_state()
                    print(agent.task.describe())

            elif cmd == "/stage":
                if len(parts) < 2:
                    print("Использование: /stage <planning|execution|validation|done>")
                else:
                    try:
                        agent.task.set_stage(parts[1])
                        agent._persist_task_state()
                        print(agent.task.describe())
                    except ValueError as exc:
                        print(exc)

            elif cmd == "/invariants":
                print(agent.invariants.describe())

            elif cmd == "/add":
                if len(parts) < 4:
                    print("Использование: /add <category> <key> <statement> [rationale]")
                else:
                    try:
                        category = _normalize_category(parts[1])
                        rationale = parts[4] if len(parts) > 4 else "принято командой"
                        invariant = agent.add_invariant(category, parts[2], parts[3], rationale)
                        print(f"Инвариант добавлен: {invariant.memory_key()}")
                    except ValueError as exc:
                        print(exc)

            elif cmd == "/remove":
                if len(parts) < 2:
                    print("Использование: /remove <key>")
                else:
                    try:
                        agent.remove_invariant(parts[1])
                        print(f"Инвариант удалён: {parts[1]}")
                    except KeyError as exc:
                        print(exc)

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

            elif cmd == "/demo":
                run_demo()

            elif cmd == "/clear":
                agent.clear_history()
                agent.invariants = InvariantStore()
                agent._add_default_invariants()
                agent._persist_invariants()
                print("Память очищена. Инварианты восстановлены.")

            else:
                print("Неизвестная команда. Введите /help")
            continue

        try:
            print(f"Агент: {agent.process_request(user_text)}")
        except RuntimeError as exc:
            print(f"Ошибка AI: {exc}")


if __name__ == "__main__":
    run_cli()
