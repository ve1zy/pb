from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from lab11 import LongTermCategory
from lab12 import (
    DEFAULT_AI_MODEL,
    MemoryAgent,
    PersonalizedMemoryAgent,
    UserProfile,
    _profile_key,
    create_openrouter_model,
)


class TaskStage(str, Enum):
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    DONE = "done"


class TaskStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"


@dataclass
class TaskStep:
    title: str
    description: str
    expected_action: str
    stage: TaskStage = TaskStage.PLANNING
    result: Optional[str] = None
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "expected_action": self.expected_action,
            "stage": self.stage.value,
            "result": self.result,
            "completed": self.completed,
        }


@dataclass
class TaskSnapshot:
    title: str
    stage: str
    status: str
    current_step: int
    total_steps: int
    current_step_title: str
    current_step_description: str
    expected_action: str
    paused_from: Optional[str]
    steps: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "stage": self.stage,
            "status": self.status,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_step_title": self.current_step_title,
            "current_step_description": self.current_step_description,
            "expected_action": self.expected_action,
            "paused_from": self.paused_from,
            "steps": self.steps,
        }


class TaskStateMachine:
    def __init__(self) -> None:
        self.title = ""
        self.steps: List[TaskStep] = []
        self.stage = TaskStage.PLANNING
        self.status = TaskStatus.PAUSED
        self.current_step = 1
        self.expected_action = "Задайте задачу через /start"
        self.paused_from: Optional[TaskStage] = None

    def start_task(self, title: str, steps: Optional[Sequence[TaskStep | Tuple[str, str, str]]] = None) -> None:
        self.title = title
        self.steps = [
            _normalize_step(step, index)
            for index, step in enumerate(steps or _default_steps(), start=1)
        ]
        self.stage = TaskStage.PLANNING
        self.status = TaskStatus.ACTIVE
        self.current_step = 1
        self.expected_action = self._current_step().expected_action
        self.paused_from = None

    def pause(self) -> None:
        if self.status == TaskStatus.ACTIVE:
            self.status = TaskStatus.PAUSED
            self.paused_from = self.stage

    def resume(self) -> None:
        if self.status == TaskStatus.PAUSED:
            if self.paused_from is not None:
                self.stage = self.paused_from
            self.status = TaskStatus.ACTIVE
            self.paused_from = None

    def advance(self, result: Optional[str] = None) -> None:
        if self.status == TaskStatus.PAUSED:
            raise RuntimeError("Задача на паузе. Сначала выполните /resume")
        if self.stage == TaskStage.DONE:
            self.expected_action = "Задача уже завершена"
            return

        step = self._current_step()
        step.result = result
        step.completed = True

        if self._is_last_step_of_stage():
            next_stage = self._next_stage(self.stage)
            if next_stage is None:
                self.stage = TaskStage.DONE
                self.current_step = len(self.steps)
                self.expected_action = "Задача завершена"
            else:
                self.stage = next_stage
                self.current_step = self._first_step_number(next_stage)
                self.expected_action = self._current_step().expected_action
            return

        self.current_step += 1
        self.expected_action = self._current_step().expected_action

    def set_stage(self, stage_name: str) -> None:
        stage = TaskStage(stage_name)
        self.stage = stage
        self.status = TaskStatus.ACTIVE
        self.paused_from = None
        if stage == TaskStage.DONE:
            self.current_step = len(self.steps)
            self.expected_action = "Задача завершена"
        else:
            self.current_step = self._first_step_number(stage)
            self.expected_action = self._current_step().expected_action

    def set_current_step(self, step_number: int) -> None:
        if not 1 <= step_number <= len(self.steps):
            raise ValueError(f"Шаг должен быть от 1 до {len(self.steps)}")
        self.current_step = step_number
        self.expected_action = self._current_step().expected_action

    def set_expected_action(self, action: str) -> None:
        self.expected_action = action

    def snapshot(self) -> TaskSnapshot:
        step = self._current_step() if self.steps else TaskStep("нет", "нет", "нет")
        return TaskSnapshot(
            title=self.title or "Без названия",
            stage=self.stage.value,
            status=self.status.value,
            current_step=self.current_step,
            total_steps=len(self.steps),
            current_step_title=step.title,
            current_step_description=step.description,
            expected_action=self.expected_action,
            paused_from=None if self.paused_from is None else self.paused_from.value,
            steps=[step.to_dict() for step in self.steps],
        )

    def describe(self) -> str:
        snapshot = self.snapshot()
        paused = f", пауза с этапа {snapshot.paused_from}" if snapshot.paused_from else ""
        return (
            f"Задача: {snapshot.title}\n"
            f"Статус: {snapshot.status}{paused}\n"
            f"Этап: {snapshot.stage}\n"
            f"Текущий шаг: {snapshot.current_step}/{snapshot.total_steps} — {snapshot.current_step_title}\n"
            f"Описание шага: {snapshot.current_step_description}\n"
            f"Ожидаемое действие: {snapshot.expected_action}"
        )

    def _first_step_number(self, stage: TaskStage) -> int:
        for index, step in enumerate(self.steps, start=1):
            if step.stage == stage:
                return index
        return 1

    def _next_stage(self, stage: TaskStage) -> Optional[TaskStage]:
        order = [TaskStage.PLANNING, TaskStage.EXECUTION, TaskStage.VALIDATION]
        if stage not in order:
            return None
        position = order.index(stage)
        if position + 1 >= len(order):
            return None
        return order[position + 1]

    def _is_last_step_of_stage(self) -> bool:
        current_stage = self._current_step().stage
        for step in self.steps[self.current_step:]:
            if step.stage == current_stage:
                return False
        return True

    def _current_step(self) -> TaskStep:
        if not self.steps:
            raise RuntimeError("Задача не начата")
        return self.steps[self.current_step - 1]


class TaskStateAgent(PersonalizedMemoryAgent):
    def __init__(self, name: str = "TaskStateAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.task = TaskStateMachine()
        self._persist_task_state()

    def start_task(self, title: str, steps: Optional[Sequence[TaskStep | Tuple[str, str, str]]] = None) -> str:
        self.task.start_task(title, steps)
        self._persist_task_state()
        return self.task.describe()

    def process_request(self, user_input: str, *, use_ai: Optional[bool] = None) -> str:
        self._persist_task_state()

        if self.task.status == TaskStatus.PAUSED and not self._is_resume_input(user_input):
            return "Задача на паузе. Введите /resume, чтобы продолжить с текущего шага без повторных объяснений."

        if self._should_use_ai(use_ai):
            if self.ai_model is None:
                raise RuntimeError("AI-модель не подключена к агенту")
            return super().process_request(user_input, use_ai=True)

        return self._rule_answer(user_input)

    def _rule_answer(self, user_input: str) -> str:
        text = user_input.strip()
        lower = text.lower()

        if lower in {"pause", "/pause", "пауза"} or lower.startswith("/pause "):
            self.task.pause()
            self._persist_task_state()
            return f"Задача поставлена на паузу на этапе {self.task.stage.value}."

        if lower in {"resume", "/resume", "продолжить", "continue"} or lower.startswith("/resume "):
            self.task.resume()
            self._persist_task_state()
            return self._current_state_answer("Задача продолжена.")

        if lower in {"state", "/state", "что дальше", "что сейчас", "продолжить без объяснений"} or lower.startswith("/state "):
            return self._current_state_answer()

        if (
            lower in {"advance", "/advance", "next", "/next", "done", "/done", "готово"}
            or lower.startswith("/advance ")
            or lower.startswith("/next ")
            or lower.startswith("/done ")
        ):
            result = None
            if text.startswith("/advance "):
                result = text[len("/advance "):].strip() or None
            elif text.startswith("/next "):
                result = text[len("/next "):].strip() or None
            elif text.startswith("/done "):
                result = text[len("/done "):].strip() or None
            self.task.advance(result)
            self._persist_task_state()
            if self.task.stage == TaskStage.DONE:
                return "Задача завершена. Состояние: done."
            return self._current_state_answer("Шаг завершён.")

        if text.startswith("/start"):
            title = text[len("/start"):].strip() or "Новая задача"
            return self.start_task(title)

        if text.startswith("/step"):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                return "Использование: /step <номер шага>"
            self.task.set_current_step(int(parts[1]))
            self._persist_task_state()
            return self._current_state_answer("Шаг установлен.")

        if text.startswith("/action"):
            action = text[len("/action"):].strip()
            if not action:
                return "Использование: /action <ожидаемое действие>"
            self.task.set_expected_action(action)
            self._persist_task_state()
            return self._current_state_answer("Ожидаемое действие обновлено.")

        if text.startswith("/stage"):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                return "Использование: /stage <planning|execution|validation|done>"
            self.task.set_stage(parts[1])
            self._persist_task_state()
            return self._current_state_answer("Этап установлен.")

        return self._current_state_answer()

    def _system_prompt(self) -> str:
        base_prompt = super()._system_prompt()
        return (
            f"{base_prompt}\n\n"
            "Текущее формализованное состояние задачи:\n"
            f"{self.task.describe()}\n\n"
            "Не повторяй уже завершённые шаги. Отвечай только по текущему этапу, "
            "текущему шагу и ожидаемому действию, если пользователь не попросил полную историю."
        )

    def _memory_context_for_ai(self) -> str:
        context = super()._memory_context_for_ai()
        return (
            f"{context}\n\n"
            "task_state_machine:\n"
            f"{self.task.describe()}"
        )

    def _current_state_answer(self, prefix: Optional[str] = None) -> str:
        answer = self.task.describe()
        return f"{prefix}\n{answer}" if prefix else answer

    def _is_resume_input(self, user_input: str) -> bool:
        return user_input.strip().lower() in {"resume", "/resume", "продолжить", "continue"}

    def _should_use_ai(self, use_ai: Optional[bool]) -> bool:
        return self.default_use_ai if use_ai is None else use_ai

    def _persist_task_state(self) -> None:
        self.remember_working("task.state", self.task.snapshot().to_dict(), "формализованное состояние задачи")


def _normalize_step(step: TaskStep | Tuple[str, str, str] | Tuple[str, str, str, TaskStage], index: int) -> TaskStep:
    if isinstance(step, TaskStep):
        return step
    if len(step) == 4:
        title, description, expected_action, stage = step
        return TaskStep(title=title, description=description, expected_action=expected_action, stage=stage)
    title, description, expected_action = step
    return TaskStep(
        title=title,
        description=description,
        expected_action=expected_action,
        stage=_infer_stage_by_index(index),
    )


def _infer_stage_by_index(index: int) -> TaskStage:
    if index <= 2:
        return TaskStage.PLANNING
    if index == 3:
        return TaskStage.EXECUTION
    return TaskStage.VALIDATION


def _default_steps() -> List[TaskStep]:
    return [
        TaskStep(
            "Сформулировать цель",
            "Определить результат, критерий успеха и ограничения.",
            "Подтвердить цель задачи",
        ),
        TaskStep(
            "Составить план",
            "Разбить задачу на последовательные действия.",
            "Подтвердить план выполнения",
            TaskStage.PLANNING,
        ),
        TaskStep(
            "Выполнить работу",
            "Сделать основной результат по плану.",
            "Показать готовый результат",
            TaskStage.EXECUTION,
        ),
        TaskStep(
            "Проверить результат",
            "Сверить результат с критерием успеха.",
            "Подтвердить валидацию",
            TaskStage.VALIDATION,
        ),
    ]


def print_help() -> None:
    print(
        "\nКоманды lab11/lab12:\n"
        "  /short <текст>                        — сохранить в краткосрочную память\n"
        "  /working <ключ> <значение>            — сохранить в рабочую память\n"
        "  /long <profile|decision|knowledge> <ключ> <значение>\n"
        "  /task <название> [цель]               — начать задачу\n"
        "  /profiles                             — показать профили\n"
        "  /profile [имя]                        — показать профиль\n"
        "  /new <имя>                            — создать профиль\n"
        "  /switch <имя>                         — переключить профиль\n"
        "  /set <style|format|constraints|goals> <значение>\n"
        "\nКоманды Task State Machine lab13:\n"
        "  /start [название]                     — начать задачу\n"
        "  /state                                — показать текущее состояние\n"
        "  /advance [результат]                  — завершить текущий шаг и перейти дальше\n"
        "  /pause                                — поставить задачу на паузу\n"
        "  /resume                               — продолжить без повторных объяснений\n"
        "  /step <номер>                         — перейти к шагу\n"
        "  /action <ожидаемое действие>          — задать ожидаемое действие\n"
        "  /stage <planning|execution|validation|done>\n"
        "  /ask <вопрос>                         — отправить вопрос AI-агенту\n"
        "  /memory                               — показать память\n"
        "  /ai on|off                            — включить или выключить AI-модель\n"
        "  /demo                                 — показать сценарий паузы и продолжения\n"
        "  /clear                                — очистить память\n"
        "  /help                                 — показать команды\n"
        "  exit                                  — выйти\n"
    )


def run_task_state_checks() -> None:
    agent = TaskStateAgent()
    steps = [
        ("Сформулировать цель", "Определить результат и критерий успеха.", "Подтвердить цель", TaskStage.PLANNING),
        ("Составить план", "Разбить работу на шаги.", "Подтвердить план", TaskStage.PLANNING),
        ("Выполнить шаг", "Сделать основной результат.", "Показать результат", TaskStage.EXECUTION),
        ("Проверить результат", "Сверить результат с критерием.", "Подтвердить валидацию", TaskStage.VALIDATION),
    ]

    agent.start_task("Отчёт по проекту", steps)
    first_answer = agent.process_request("Что дальше?", use_ai=False)
    agent.process_request("/advance цель подтверждена", use_ai=False)

    agent.task.pause()
    assert agent.task.snapshot().to_dict()["status"] == "paused"
    assert agent.task.snapshot().paused_from == "planning"
    paused_answer = agent.process_request("продолжить", use_ai=False)
    continued_answer = agent.process_request("Что дальше?", use_ai=False)

    assert "planning" in paused_answer
    assert "Ожидаемое действие: Подтвердить план" in continued_answer
    assert "Сформулировать цель" not in continued_answer
    assert first_answer != continued_answer

    agent.process_request("/advance план подтверждён", use_ai=False)
    agent.task.pause()
    assert agent.task.snapshot().paused_from == "execution"
    agent.process_request("resume", use_ai=False)
    assert agent.task.status == TaskStatus.ACTIVE
    assert agent.task.stage == TaskStage.EXECUTION

    agent.process_request("/advance результат готов", use_ai=False)
    agent.process_request("/advance валидация пройдена", use_ai=False)
    assert agent.task.stage == TaskStage.DONE
    assert agent.task.snapshot().expected_action == "Задача завершена"
    assert agent.memory.working["task.state"].value["stage"] == "done"

    print("Проверки Task State Machine пройдены.")


def run_demo() -> None:
    agent = TaskStateAgent()
    agent.start_task(
        "Подготовка презентации",
        [
            ("План", "Определить структуру слайдов.", "Подтвердить структуру", TaskStage.PLANNING),
            ("Контент", "Написать текст для слайдов.", "Показать черновик", TaskStage.EXECUTION),
            ("Проверка", "Проверить ясность и сроки.", "Подтвердить готовность", TaskStage.VALIDATION),
        ],
    )

    print("--- Task State Machine Demo ---")
    print(agent.process_request("Что дальше?", use_ai=False))
    print()

    agent.process_request("/advance структура утверждена", use_ai=False)
    agent.task.pause()
    print(agent.process_request("продолжить", use_ai=False))
    print()

    print(agent.process_request("Что дальше?", use_ai=False))
    print()

    print(agent.memory.describe())


def run_cli() -> None:
    agent = TaskStateAgent()

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("AI выключен: OPENROUTER_API_KEY не задан. Можно писать /ai on после настройки ключа.")

    print("--- Агент с Task State Machine ---")
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

            elif cmd == "/clear":
                agent.clear_history()
                agent._persist_task_state()
                print("Память очищена. Состояние задачи сохранено.")

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

            else:
                print("Неизвестная команда. Введите /help")
            continue

        try:
            print(f"Агент: {agent.process_request(user_text)}")
        except RuntimeError as exc:
            print(f"Ошибка: {exc}")


if __name__ == "__main__":
    run_cli()
