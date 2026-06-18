from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from lab11 import (
    DEFAULT_AI_MODEL,
    LongTermCategory,
    MemoryAgent,
    MemoryLayer,
    create_openrouter_model,
)


@dataclass
class UserProfile:
    name: str
    style: str = "нейтральный"
    response_format: str = "кратко"
    constraints: str = "не выдумывать факты"
    goals: str = "помогать эффективно"
    notes: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key:
            self.key = _profile_key(self.name)

    key: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "style": self.style,
            "response_format": self.response_format,
            "constraints": self.constraints,
            "goals": self.goals,
            "notes": dict(self.notes),
        }

    def to_prompt(self) -> str:
        notes = "; ".join(f"{key}: {value}" for key, value in self.notes.items())
        if not notes:
            notes = "нет"
        return (
            f"Имя/роль: {self.name}\n"
            f"Стиль общения: {self.style}\n"
            f"Формат ответа: {self.response_format}\n"
            f"Ограничения: {self.constraints}\n"
            f"Цели: {self.goals}\n"
            f"Заметки: {notes}"
        )


class PersonalizedMemoryAgent(MemoryAgent):
    def __init__(self, name: str = "PersonalizedMemoryAgent", short_limit: int = 8) -> None:
        super().__init__(name=name, short_limit=short_limit)
        self.profiles: Dict[str, UserProfile] = {}
        self.active_profile_name = ""
        self.create_profile(
            UserProfile(
                name="default",
                style="нейтральный",
                response_format="кратко и по делу",
                constraints="не выдумывать факты, явно указывать слой памяти",
                goals="помогать с задачами и объяснять решения",
            ),
            switch=True,
        )

    def create_profile(self, profile: UserProfile, *, switch: bool = True) -> UserProfile:
        self.profiles[profile.key] = profile
        self._persist_profile(profile)
        if switch:
            self.active_profile_name = profile.key
        return profile

    def switch_profile(self, profile_name: str) -> UserProfile:
        key = _profile_key(profile_name)
        if key not in self.profiles:
            raise KeyError(f"Профиль не найден: {profile_name}")
        self.active_profile_name = key
        self._persist_active_profile()
        return self.active_profile

    @property
    def active_profile(self) -> UserProfile:
        return self.profiles[self.active_profile_name]

    def update_profile_field(self, field: str, value: str) -> None:
        field = field.lower()
        profile = self.active_profile

        if field == "style":
            profile.style = value
        elif field == "format":
            profile.response_format = value
        elif field == "constraints":
            profile.constraints = value
        elif field == "goals":
            profile.goals = value
        elif field.startswith("note:"):
            note_key = field.split(":", 1)[1]
            profile.notes[note_key] = value
        else:
            raise ValueError("Поле должно быть: style, format, constraints, goals или note:<ключ>")

        self._persist_active_profile()

    def process_request(self, user_input: str, *, use_ai: Optional[bool] = None) -> str:
        self._persist_active_profile()
        return super().process_request(user_input, use_ai=use_ai)

    def _system_prompt(self) -> str:
        base_prompt = super()._system_prompt()
        return (
            f"{base_prompt}\n\n"
            "Активный профиль пользователя подключён к каждому запросу:\n"
            f"{self.active_profile.to_prompt()}"
        )

    def _memory_context_for_ai(self) -> str:
        context = super()._memory_context_for_ai()
        return (
            f"{context}\n\n"
            "active_profile:\n"
            f"{self.active_profile.to_prompt()}"
        )

    def _answer(self, message: str, previous_user_message: Optional[str]) -> str:
        lower = message.lower()

        if self._is_profile_question(lower):
            return self._profile_answer()

        if "дедлайн" in lower or "проблем" in lower or "объясн" in lower:
            return self._profile_specific_advice(message)

        answer = super()._answer(message, previous_user_message)
        return self._apply_profile_style(answer)

    def _is_profile_question(self, lower: str) -> bool:
        return (
            "профиль" in lower
            or "предпочтен" in lower
            or "формат" in lower
            or "стиль" in lower
            or "ограничен" in lower
            or "что ты знаешь обо мне" in lower
            or "как меня зовут" in lower
        )

    def _profile_answer(self) -> str:
        profile = self.active_profile
        return (
            f"Активный профиль: {profile.name}.\n"
            f"Стиль: {profile.style}.\n"
            f"Формат: {profile.response_format}.\n"
            f"Ограничения: {profile.constraints}.\n"
            f"Цели: {profile.goals}.\n"
            "Профиль сохранён в long_term как профиль пользователя и подключается к каждому запросу."
        )

    def _profile_specific_advice(self, message: str) -> str:
        profile = self.active_profile
        key = profile.key

        if key == "developer":
            return (
                "Для профиля developer: объясни технически — причина, затронутый модуль, "
                "план фикса, оценка срока и следующий шаг. Формат: коротко, с примером кода или шагами."
            )
        if key == "manager":
            return (
                "Для профиля manager: объясни через бизнес-влияние — сроки, риски, решение, "
                "ответственный и следующий управленческий шаг. Формат: без кода, буллетами."
            )
        if key == "designer":
            return (
                "Для профиля designer: объясни через пользовательский сценарий — где возникает боль, "
                "как это влияет на UX, какие варианты решения и компромиссы. Формат: кратко и наглядно."
            )

        return (
            f"С учётом профиля {profile.name}: {message}. "
            f"Ответ нужно дать в стиле '{profile.style}' и формате '{profile.response_format}'."
        )

    def _apply_profile_style(self, answer: str) -> str:
        profile = self.active_profile
        style = profile.style.lower()
        response_format = profile.response_format.lower()

        if "техническ" in style and not answer.startswith("Технически:"):
            return f"Технически: {answer}"
        if "делов" in style and not answer.startswith("Деловой вывод:"):
            return f"Деловой вывод: {answer}"
        if "подроб" in response_format and "Подробнее:" not in answer:
            return f"{answer}\nПодробнее: это следует из активного профиля пользователя."
        return answer

    def _persist_active_profile(self) -> None:
        self._persist_profile(self.active_profile)

    def _persist_profile(self, profile: UserProfile) -> None:
        self.remember_long_term(
            LongTermCategory.PROFILE,
            profile.key,
            profile.to_dict(),
            "профиль пользователя подключён к запросам",
        )


def _profile_key(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name.strip()).strip("_") or "default"


def print_help() -> None:
    print(
        "\nКоманды lab11:\n"
        "  /short <текст>                        — сохранить в краткосрочную память\n"
        "  /working <ключ> <значение>            — сохранить в рабочую память\n"
        "  /long <profile|decision|knowledge> <ключ> <значение>\n"
        "  /task <название> [цель]               — начать задачу\n"
        "\nКоманды персонализации lab12:\n"
        "  /profiles                         — показать профили\n"
        "  /profile [имя]                    — показать активный или выбранный профиль\n"
        "  /new <имя>                        — создать профиль\n"
        "  /switch <имя>                     — переключить активный профиль\n"
        "  /set <style|format|constraints|goals> <значение>\n"
        "  /set note:<ключ> <значение>        — добавить заметку в профиль\n"
        "  /ask <вопрос>                     — отправить вопрос агенту\n"
        "  /memory                           — показать слои памяти\n"
        "  /ai on|off                        — включить или выключить AI-модель\n"
        "  /demo                             — показать ответы для разных профилей\n"
        "  /clear                            — очистить память агента\n"
        "  /help                             — показать команды\n"
        "  exit                              — выйти\n"
    )


def run_profile_checks() -> None:
    agent = PersonalizedMemoryAgent()

    agent.create_profile(
        UserProfile(
            name="developer",
            style="технический",
            response_format="код + шаги",
            constraints="без воды, использовать Python-примеры",
            goals="быстро находить причины багов и чинить код",
            notes={"language": "Python"},
        )
    )
    agent.create_profile(
        UserProfile(
            name="manager",
            style="деловой",
            response_format="буллеты: риски, решение, следующий шаг",
            constraints="без кода, акцент на сроки и ответственность",
            goals="принимать управленческие решения",
            notes={"focus": "delivery"},
        )
    )

    agent.switch_profile("developer")
    developer_answer = agent.process_request("Объясни проблему с дедлайном", use_ai=False)

    agent.switch_profile("manager")
    manager_answer = agent.process_request("Объясни проблему с дедлайном", use_ai=False)

    assert "developer" in developer_answer
    assert "код" in developer_answer
    assert "manager" in manager_answer
    assert "риски" in manager_answer
    assert "profile.developer" in agent.memory.long_term
    assert "profile.manager" in agent.memory.long_term
    assert "Активный профиль пользователя" in agent._system_prompt()

    print("Проверки персонализации пройдены.")


def run_demo() -> None:
    agent = PersonalizedMemoryAgent()

    agent.create_profile(
        UserProfile(
            name="developer",
            style="технический",
            response_format="код + шаги",
            constraints="без воды, использовать Python-примеры",
            goals="быстро находить причины багов и чинить код",
        )
    )
    agent.create_profile(
        UserProfile(
            name="manager",
            style="деловой",
            response_format="буллеты: риски, решение, следующий шаг",
            constraints="без кода, акцент на сроки и ответственность",
            goals="принимать управленческие решения",
        )
    )

    print("--- Персонализированный агент ---")
    print()

    agent.switch_profile("developer")
    print("Профиль developer:")
    print(agent.process_request("Объясни проблему с дедлайном", use_ai=False))
    print()

    agent.switch_profile("manager")
    print("Профиль manager:")
    print(agent.process_request("Объясни проблему с дедлайном", use_ai=False))
    print()

    print(agent.memory.describe())


def run_cli() -> None:
    agent = PersonalizedMemoryAgent()

    try:
        agent.use_ai_model(create_openrouter_model())
        print(f"AI включён: {DEFAULT_AI_MODEL}")
    except RuntimeError:
        print("AI выключен: OPENROUTER_API_KEY не задан. Можно писать /ai on после настройки ключа.")

    print("--- Персонализированный агент с memory layers ---")
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

            elif cmd == "/clear":
                agent.clear_history()
                agent._persist_active_profile()
                print("Память очищена. Активный профиль восстановлен.")

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
            print(f"Ошибка AI: {exc}")


if __name__ == "__main__":
    run_cli()
