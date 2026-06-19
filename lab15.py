from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from lab13 import UserProfile, _profile_key
from lab14 import (
    DEFAULT_AI_MODEL,
    Invariant,
    InvariantAgent,
    InvariantCategory,
    InvariantStore,
    LongTermCategory,
    MemoryAgent,
    create_openrouter_model,
)


class ControlledTaskState(str, Enum):
    PLANNING = "planning"
    PLAN_APPROVED = "plan_approved"
    EXECUTION = "execution"
    VALIDATION = "validation"
    DONE = "done"


ALLOWED_TRANSITIONS: Dict[ControlledTaskState, set[ControlledTaskState]] = {
    ControlledTaskState.PLANNING: {ControlledTaskState.PLAN_APPROVED},
    ControlledTaskState.PLAN_APPROVED: {ControlledTaskState.EXECUTION},
    ControlledTaskState.EXECUTION: {ControlledTaskState.VALIDATION},
    ControlledTaskState.VALIDATION: {ControlledTaskState.DONE},
    ControlledTaskState.DONE: set(),
}

STATE_EXPECTED_ACTIONS: Dict[ControlledTaskState, str] = {
    ControlledTaskState.PLANNING: "Сформулировать цель, ограничения и план; реализация запрещена до утверждения плана",
    ControlledTaskState.PLAN_APPROVED: "Начать реализацию только по утверждённому плану",
    ControlledTaskState.EXECUTION: "Выполнить работу по утверждённому плану и подготовить результат",
    ControlledTaskState.VALIDATION: "Проверить результат, закрыть замечания и подтвердить готовность",
    ControlledTaskState.DONE: "Задача завершена; новые переходы запрещены",
}


@dataclass
class ControlledTaskSnapshot:
    title: str
    state: str
    status: str
    current_step: int
    total_steps: int
    expected_action: str
    paused_from: Optional[str]
    history: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "state": self.state,
            "status": self.status,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "expected_action": self.expected_action,
            "paused_from": self.paused_from,
            "history": self.history,
        }


class ControlledTaskStateMachine:
    def __init__(self) -> None:
        self.title = ""
        self.state = ControlledTaskState.PLANNING
        self.status = "paused"
        self.paused_from: Optional[ControlledTaskState] = None
        self.history: List[str] = []

    def start_task(self, title: str) -> None:
        self.title = title
        self.state = ControlledTaskState.PLANNING
        self.status = "active"
        self.paused_from = None
        self.history = ["planning"]

    def can_transition_to(self, target: ControlledTaskState) -> bool:
        return target in ALLOWED_TRANSITIONS.get(self.state, set())

    def transition_to(self, target: ControlledTaskState, reason: str = "переход") -> None:
        if self.status == "paused":
            raise RuntimeError("Задача на паузе. Сначала выполните /resume")
        if self.state == ControlledTaskState.DONE:
            raise RuntimeError("Задача уже завершена")
        if not self.can_transition_to(target):
            allowed = ", ".join(item.value for item in ALLOWED_TRANSITIONS[self.state])
            raise ValueError(
                f"Недопустимый переход {self.state.value} → {target.value}. "
                f"Разрешён только переход в: {allowed}."
            )
        self.state = target
        self.history.append(f"{reason}: {target.value}")

    def approve_plan(self) -> None:
        self.transition_to(ControlledTaskState.PLAN_APPROVED, "план утверждён")

    def start_execution(self) -> None:
        self.transition_to(ControlledTaskState.EXECUTION, "реализация начата")

    def start_validation(self) -> None:
        self.transition_to(ControlledTaskState.VALIDATION, "валидация начата")

    def finish(self) -> None:
        self.transition_to(ControlledTaskState.DONE, "задача завершена")

    def advance(self, result: Optional[str] = None) -> str:
        if self.status == "paused":
            raise RuntimeError("Задача на паузе. Сначала выполните /resume")

        if self.state == ControlledTaskState.PLANNING:
            if result and "утвер" not in result.lower():
                return "План ещё не утверждён. Введите /approve-plan или /advance план утверждён."
            self.approve_plan()
            return "План утверждён. Теперь разрешён переход к реализации."

        if self.state == ControlledTaskState.PLAN_APPROVED:
            self.start_execution()
            return "Реализация начата по утверждённому плану."

        if self.state == ControlledTaskState.EXECUTION:
            self.start_validation()
            return "Реализация завершена. Начата валидация."

        if self.state == ControlledTaskState.VALIDATION:
            self.finish()
            return "Валидация пройдена. Задача завершена."

        return "Задача уже завершена."

    def pause(self) -> None:
        if self.status == "active":
            self.status = "paused"
            self.paused_from = self.state

    def resume(self) -> None:
        if self.status == "paused":
            if self.paused_from is not None:
                self.state = self.paused_from
            self.status = "active"
            self.paused_from = None

    def snapshot(self) -> ControlledTaskSnapshot:
        state_order = list(ControlledTaskState)
        return ControlledTaskSnapshot(
            title=self.title or "Без названия",
            state=self.state.value,
            status=self.status,
            current_step=state_order.index(self.state) + 1,
            total_steps=len(state_order),
            expected_action=STATE_EXPECTED_ACTIONS[self.state],
            paused_from=None if self.paused_from is None else self.paused_from.value,
            history=list(self.history),
        )

    def describe(self) -> str:
        snapshot = self.snapshot()
        paused = f", пауза с состояния {snapshot.paused_from}" if snapshot.paused_from else ""
        return (
            f"Задача: {snapshot.title}\n"
            f"Статус: {snapshot.status}{paused}\n"
            f"Состояние: {snapshot.state}\n"
            f"Шаг жизненного цикла: {snapshot.current_step}/{snapshot.total_steps}\n"
            f"Ожидаемое действие: {snapshot.expected_action}\n"
            f"История переходов: {' -> '.join(snapshot.history)}"
        )


class ControlledInvariantAgent(InvariantAgent):
    def __init__(self, name: str = "ControlledInvariantAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.task = ControlledTaskStateMachine()
        self._persist_task_state()

    def start_task(self, title: str, steps: Optional[Any] = None) -> str:
        self.task.start_task(title)
        self._persist_task_state()
        return self.task.describe()

    def process_request(self, user_input: str, *, use_ai: Optional[bool] = None) -> str:
        self._persist_invariants()
        self._persist_task_state()

        conflicts = self.invariants.find_conflicts(user_input)
        if conflicts:
            return self._refuse(conflicts)

        transition_refusal = self._detect_invalid_transition_request(user_input)
        if transition_refusal:
            return transition_refusal

        if self.task.status == "paused" and not self._is_resume_input(user_input):
            return "Задача на паузе. Введите /resume, чтобы продолжить с текущего состояния без повторных объяснений."

        if self._should_use_ai(use_ai):
            if self.ai_model is None:
                raise RuntimeError("AI-модель не подключена к агенту")
            return super().process_request(user_input, use_ai=True)

        return self._rule_answer(user_input)

    def _rule_answer(self, user_input: str) -> str:
        text = user_input.strip()
        lower = text.lower()

        if lower in {"lifecycle", "/lifecycle", "жизненный цикл", "состояние задачи"}:
            return self.task.describe()

        if lower in {"approve-plan", "/approve-plan", "утвердить план"}:
            try:
                self.task.approve_plan()
                self._persist_task_state()
                return self.task.describe()
            except (RuntimeError, ValueError) as exc:
                return str(exc)

        if lower in {"start-execution", "/start-execution", "начать реализацию"}:
            try:
                self.task.start_execution()
                self._persist_task_state()
                return self.task.describe()
            except (RuntimeError, ValueError) as exc:
                return str(exc)

        if lower in {"start-validation", "/start-validation", "начать валидацию"}:
            try:
                self.task.start_validation()
                self._persist_task_state()
                return self.task.describe()
            except (RuntimeError, ValueError) as exc:
                return str(exc)

        if lower in {"finish", "/finish", "завершить задачу"}:
            try:
                self.task.finish()
                self._persist_task_state()
                return self.task.describe()
            except (RuntimeError, ValueError) as exc:
                return str(exc)

        if lower in {"pause", "/pause", "пауза"}:
            self.task.pause()
            self._persist_task_state()
            return f"Пауза на состоянии {self.task.state.value}."

        if lower in {"resume", "/resume", "продолжить", "continue"}:
            self.task.resume()
            self._persist_task_state()
            return self._current_state_answer("Задача продолжена.")

        if lower in {"state", "/state", "что дальше", "что сейчас"}:
            return self._current_state_answer()

        if lower in {"advance", "/advance", "next", "/next"}:
            result = None
            if text.startswith("/advance "):
                result = text[len("/advance "):].strip() or None
            try:
                answer = self.task.advance(result)
                self._persist_task_state()
                return self._current_state_answer(answer)
            except (RuntimeError, ValueError) as exc:
                return str(exc)

        if text.startswith("/stage"):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                return "Использование: /stage <planning|plan_approved|execution|validation|done>"
            try:
                target = ControlledTaskState(parts[1])
                self.task.transition_to(target, "ручной переход")
                self._persist_task_state()
                return self._current_state_answer("Состояние изменено.")
            except ValueError as exc:
                return str(exc)

        return self._current_state_answer()

    def _system_prompt(self) -> str:
        base_prompt = super()._system_prompt()
        return (
            f"{base_prompt}\n\n"
            "Контролируемый жизненный цикл задачи:\n"
            f"{self.task.describe()}\n\n"
            "Разрешённые переходы: planning → plan_approved → execution → validation → done. "
            "Не предлагай и не выполняй переходы, которых нет в этом списке."
        )

    def _memory_context_for_ai(self) -> str:
        context = super()._memory_context_for_ai()
        return (
            f"{context}\n\n"
            "controlled_task_lifecycle:\n"
            f"{self.task.describe()}\n"
            "Нельзя перепрыгивать состояния. Реализация разрешена только после plan_approved. "
            "Финал разрешён только после validation."
        )

    def _current_state_answer(self, prefix: Optional[str] = None) -> str:
        answer = self.task.describe()
        return f"{prefix}\n{answer}" if prefix else answer

    def _detect_invalid_transition_request(self, user_input: str) -> Optional[str]:
        text = user_input.lower()

        if self.task.state == ControlledTaskState.PLANNING and any(
            term in text for term in ["реализ", "код", "разраб", "внедр", "начинаем делать", "начать делать"]
        ):
            return (
                "Отказ: нельзя начинать реализацию в состоянии planning. "
                "Сначала утвердите план через /approve-plan."
            )

        if self.task.state in {
            ControlledTaskState.PLANNING,
            ControlledTaskState.PLAN_APPROVED,
            ControlledTaskState.EXECUTION,
        } and any(term in text for term in ["финал", "заверш", "done", "релиз", "выпуск"]):
            return (
                "Отказ: нельзя завершать задачу до состояния validation. "
                "Сначала выполните работу и пройдите валидацию."
            )

        return None

    def _is_resume_input(self, user_input: str) -> bool:
        return user_input.strip().lower() in {"resume", "/resume", "продолжить", "continue"}

    def _persist_task_state(self) -> None:
        self.remember_working(
            "controlled_task.state",
            self.task.snapshot().to_dict(),
            "контролируемое состояние жизненного цикла задачи",
        )


def print_help() -> None:
    print(
        "\nКоманды lab11/lab12/lab13/lab14:\n"
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
        "  /advance [результат]                  — контролируемый переход FSM\n"
        "  /pause                                — пауза FSM\n"
        "  /resume                               — продолжить FSM\n"
        "  /invariants                           — показать инварианты\n"
        "  /add <category> <key> <statement> [rationale]\n"
        "  /remove <key>                         — удалить инвариант\n"
        "\nКоманды контролируемого жизненного цикла lab15:\n"
        "  /lifecycle                            — показать жизненный цикл\n"
        "  /approve-plan                         — planning → plan_approved\n"
        "  /start-execution                      — plan_approved → execution\n"
        "  /start-validation                     — execution → validation\n"
        "  /finish                               — validation → done\n"
        "  /stage <state>                        — явный переход, если он разрешён\n"
        "  /ask <вопрос>                         — отправить вопрос AI-агенту\n"
        "  /memory                               — показать память\n"
        "  /ai on|off                            — включить или выключить AI-модель\n"
        "  /demo                                 — показать контролируемые переходы\n"
        "  /clear                                — очистить память и восстановить инварианты\n"
        "  /help                                 — показать команды\n"
        "  exit                                  — выйти\n"
    )


def run_controlled_checks() -> None:
    agent = ControlledInvariantAgent()
    agent.start_task("Сервис отчётности")

    implementation_refusal = agent.process_request("Давай сразу реализуем фичу", use_ai=False)
    stage_refusal = agent.process_request("/stage execution", use_ai=False)
    finish_refusal = agent.process_request("Завершаем финал без проверки", use_ai=False)

    assert "нельзя начинать реализацию" in implementation_refusal
    assert "Недопустимый переход" in stage_refusal
    assert "нельзя завершать задачу" in finish_refusal

    agent.process_request("/approve-plan", use_ai=False)
    assert agent.task.state == ControlledTaskState.PLAN_APPROVED

    agent.process_request("/start-execution", use_ai=False)
    assert agent.task.state == ControlledTaskState.EXECUTION

    agent.task.pause()
    paused = agent.process_request("продолжить", use_ai=False)
    continued = agent.process_request("Что дальше?", use_ai=False)

    assert agent.task.status == "active"
    assert agent.task.state == ControlledTaskState.EXECUTION
    assert "execution" in paused
    assert "Ожидаемое действие" in continued

    agent.process_request("/start-validation", use_ai=False)
    agent.process_request("/finish", use_ai=False)
    assert agent.task.state == ControlledTaskState.DONE
    assert agent.memory.working["controlled_task.state"].value["state"] == "done"

    print("Проверки контролируемых переходов пройдены.")


def run_demo() -> None:
    agent = ControlledInvariantAgent()
    agent.start_task("Новый отчёт")

    print("--- Контролируемый жизненный цикл задачи ---")
    print(agent.process_request("Что дальше?", use_ai=False))
    print()

    print("Попытка перепрыгнуть в реализацию:")
    print(agent.process_request("Давай сразу реализуем фичу", use_ai=False))
    print()

    print("Корректный переход:")
    print(agent.process_request("/approve-plan", use_ai=False))
    print(agent.process_request("/start-execution", use_ai=False))
    print()

    agent.task.pause()
    print("Пауза и продолжение:")
    print(agent.process_request("продолжить", use_ai=False))
    print()

    print(agent.memory.describe())


def run_cli() -> None:
    agent = ControlledInvariantAgent()

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("AI выключен: OPENROUTER_API_KEY не задан. Можно писать /ai on после настройки ключа.")

    print("--- Ассистент с контролируемым жизненным циклом задачи ---")
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

            elif cmd == "/invariants":
                print(agent.invariants.describe())

            elif cmd == "/add":
                if len(parts) < 4:
                    print("Использование: /add <category> <key> <statement> [rationale]")
                else:
                    try:
                        category = {
                            "architecture": InvariantCategory.ARCHITECTURE,
                            "technical": InvariantCategory.TECHNICAL_DECISION,
                            "decision": InvariantCategory.TECHNICAL_DECISION,
                            "stack": InvariantCategory.STACK,
                            "business": InvariantCategory.BUSINESS_RULE,
                            "security": InvariantCategory.SECURITY,
                            "quality": InvariantCategory.QUALITY,
                        }[parts[1].lower()]
                        rationale = parts[4] if len(parts) > 4 else "принято командой"
                        invariant = agent.add_invariant(category, parts[2], parts[3], rationale)
                        print(f"Инвариант добавлен: {invariant.memory_key()}")
                    except (KeyError, ValueError) as exc:
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

            elif cmd == "/lifecycle":
                print(agent.task.describe())

            elif cmd == "/approve-plan":
                try:
                    agent.task.approve_plan()
                    agent._persist_task_state()
                    print(agent.task.describe())
                except (RuntimeError, ValueError) as exc:
                    print(exc)

            elif cmd == "/start-execution":
                try:
                    agent.task.start_execution()
                    agent._persist_task_state()
                    print(agent.task.describe())
                except (RuntimeError, ValueError) as exc:
                    print(exc)

            elif cmd == "/start-validation":
                try:
                    agent.task.start_validation()
                    agent._persist_task_state()
                    print(agent.task.describe())
                except (RuntimeError, ValueError) as exc:
                    print(exc)

            elif cmd == "/finish":
                try:
                    agent.task.finish()
                    agent._persist_task_state()
                    print(agent.task.describe())
                except (RuntimeError, ValueError) as exc:
                    print(exc)

            elif cmd == "/stage":
                if len(parts) < 2:
                    print("Использование: /stage <planning|plan_approved|execution|validation|done>")
                else:
                    try:
                        target = ControlledTaskState(parts[1])
                        agent.task.transition_to(target, "ручной переход")
                        agent._persist_task_state()
                        print(agent.task.describe())
                    except ValueError as exc:
                        print(exc)

            elif cmd == "/state":
                print(agent.task.describe())

            elif cmd == "/advance":
                result = user_text[len(cmd):].strip() or None
                try:
                    answer = agent.task.advance(result)
                    agent._persist_task_state()
                    print(agent._current_state_answer(answer))
                except (RuntimeError, ValueError) as exc:
                    print(exc)

            elif cmd == "/pause":
                agent.task.pause()
                agent._persist_task_state()
                print(f"Пауза на состоянии {agent.task.state.value}.")

            elif cmd == "/resume":
                agent.task.resume()
                agent._persist_task_state()
                print(agent.task.describe())

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
                agent.task = ControlledTaskStateMachine()
                agent._persist_task_state()
                print("Память очищена. Инварианты и жизненный цикл восстановлены.")

            else:
                print("Неизвестная команда. Введите /help")
            continue

        try:
            print(f"Агент: {agent.process_request(user_text)}")
        except RuntimeError as exc:
            print(f"Ошибка AI: {exc}")


if __name__ == "__main__":
    run_cli()
