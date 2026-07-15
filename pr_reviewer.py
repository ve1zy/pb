"""
Лабораторная 32: Автоматизация ревью кода
AI-ревьюер для PR с RAG и локальной LLM
"""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple


# ============================================================================
# 1. Получение diff и измененных файлов
# ============================================================================

def get_diff() -> str:
    """Получает diff PR"""
    diff_file = "pr_diff.txt"
    if os.path.exists(diff_file):
        with open(diff_file, "r", encoding="utf-8") as f:
            return f.read()
    
    # Fallback: получить из git
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"


def get_changed_files() -> List[str]:
    """Получает список измененных файлов"""
    files_file = "changed_files.txt"
    if os.path.exists(files_file):
        with open(files_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    
    # Fallback
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        return [f for f in result.stdout.split("\n") if f]
    except:
        return []


def parse_diff(diff: str) -> List[Dict]:
    """Парсит diff на файлы с изменениями"""
    files = []
    current_file = None
    
    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
            # Извлекаем имя файла
            match = re.search(r"b/(.+)", line)
            filename = match.group(1) if match else "unknown"
            current_file = {"file": filename, "additions": [], "deletions": []}
        elif current_file:
            if line.startswith("+") and not line.startswith("+++"):
                current_file["additions"].append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                current_file["deletions"].append(line[1:])
    
    if current_file:
        files.append(current_file)
    
    return files


# ============================================================================
# 2. Статический анализ
# ============================================================================

def check_bugs(code: str, filename: str) -> List[str]:
    """Проверяет код на потенциальные баги"""
    bugs = []
    
    # Проверка на except без типа
    if re.search(r'except\s*:', code):
        bugs.append("⚠️ `except:` без типа — скрывает все ошибки")
    
    # Проверка на print (для production кода)
    if filename.endswith(".py") and "print(" in code:
        if "test" not in filename and "demo" not in filename:
            bugs.append("ℹ️ Найден `print()` — для логирования используй `logging`")
    
    # Проверка на hardcoded passwords
    if re.search(r'(password|secret|token|api_key)\s*=\s*["\']', code, re.IGNORECASE):
        bugs.append("🔴 Возможен hardcoded секрет — используй переменные окружения")
    
    # Проверка на TODO/FIXME
    todos = re.findall(r'TODO|FIXME|XXX', code)
    if todos:
        bugs.append(f"📝 Найдено {len(todos)} TODO/FIXME — не забыть")
    
    # Проверка на SQL injection
    if re.search(r'execute\s*\(\s*["\'].*%s', code):
        bugs.append("🔴 Возможна SQL injection — используй параметризованные запросы")
    
    # Проверка на eval/exec
    if re.search(r'\beval\s*\(|\bexec\s*\(', code):
        bugs.append("🔴 Использование eval/exec — опасно, лучше заменить")
    
    # Проверка на длинные функции
    lines = code.split("\n")
    if len(lines) > 50:
        bugs.append(f"ℹ️ Функция/класс длиной {len(lines)} строк — рассмотри разбиение")
    
    return bugs


def check_style(code: str, filename: str) -> List[str]:
    """Проверяет стиль кода"""
    style = []
    
    if not filename.endswith(".py"):
        return style
    
    # Проверка на type hints
    if "def " in code and "-> " not in code and "import" not in code[:100]:
        style.append("💡 Рассмотри использование type hints")
    
    # Проверка на docstrings
    if "def " in code and '"""' not in code and "'''" not in code:
        style.append("💡 Добавь docstrings к функциям")
    
    return style


def check_architecture(files: List[Dict]) -> List[str]:
    """Проверяет архитектурные проблемы"""
    arch = []
    
    # Проверка на смешивание ответственностей
    has_tests = any("test" in f["file"].lower() for f in files)
    has_impl = any(f["file"].endswith(".py") and "test" not in f["file"].lower() for f in files)
    
    if has_impl and not has_tests:
        arch.append("⚠️ Нет тестов для нового кода")
    
    # Проверка на большие файлы
    for f in files:
        total_lines = len(f["additions"]) + len(f["deletions"])
        if total_lines > 300:
            arch.append(f"📦 Файл {f['file']} изменен на {total_lines} строк — рассмотри разбиение")
    
    return arch


# ============================================================================
# 3. RAG: поиск в документации
# ============================================================================

def load_docs() -> List[Dict]:
    """Загружает документацию проекта"""
    docs = []
    docs_dir = Path("docs_lab21")
    if docs_dir.exists():
        for md_file in docs_dir.rglob("*.md"):
            if md_file.is_file():
                with open(md_file, "r", encoding="utf-8") as f:
                    docs.append({"source": str(md_file), "content": f.read()})
    return docs


def find_relevant_docs(code: str, docs: List[Dict], top_k: int = 2) -> List[Dict]:
    """Находит релевантную документацию"""
    # Простой keyword-based поиск
    keywords = set(re.findall(r'\b[a-z]{4,}\b', code.lower()))
    
    scored = []
    for doc in docs:
        doc_words = set(re.findall(r'\b[a-z]{4,}\b', doc["content"].lower()))
        overlap = len(keywords & doc_words)
        if overlap > 0:
            scored.append((doc, overlap))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in scored[:top_k]]


# ============================================================================
# 4. Генерация ревью
# ============================================================================

def generate_review(diff: str, files: List[Dict]) -> str:
    """Генерирует текст ревью"""
    review = []
    review.append("## 🤖 AI Code Review\n")
    review.append(f"**Изменено файлов:** {len(files)}\n")
    review.append(f"**Строк добавлено:** {sum(len(f['additions']) for f in files)}\n")
    review.append(f"**Строк удалено:** {sum(len(f['deletions']) for f in files)}\n")
    review.append("")
    
    # Статический анализ
    all_bugs = []
    all_style = []
    
    for f in files:
        added_code = "\n".join(f["additions"])
        bugs = check_bugs(added_code, f["file"])
        style = check_style(added_code, f["file"])
        
        if bugs:
            all_bugs.extend([(f["file"], b) for b in bugs])
        if style:
            all_style.extend([(f["file"], s) for s in style])
    
    # Архитектура
    arch_issues = check_architecture(files)
    
    # RAG: релевантная документация
    all_added = "\n".join("\n".join(f["additions"]) for f in files)
    docs = load_docs()
    relevant_docs = find_relevant_docs(all_added, docs)
    
    # Вывод
    if all_bugs:
        review.append("### 🐛 Потенциальные баги\n")
        for file, bug in all_bugs:
            review.append(f"- **{file}**: {bug}")
        review.append("")
    
    if arch_issues:
        review.append("### 🏗️ Архитектурные проблемы\n")
        for issue in arch_issues:
            review.append(f"- {issue}")
        review.append("")
    
    if all_style:
        review.append("### 💅 Стиль кода\n")
        for file, note in all_style:
            review.append(f"- **{file}**: {note}")
        review.append("")
    
    if relevant_docs:
        review.append("### 📚 Релевантная документация\n")
        for doc in relevant_docs:
            review.append(f"- `{doc['source']}`")
        review.append("")
    
    # Рекомендации
    review.append("### 💡 Рекомендации\n")
    review.append("- ✅ Проверь что тесты покрывают новый код")
    review.append("- ✅ Запусти линтер (flake8/pylint/ruff)")
    review.append("- ✅ Проверь что нет hardcoded секретов")
    review.append("- ✅ Убедись что документация обновлена")
    review.append("")
    
    review.append("---")
    review.append("*Сгенерировано AI-ревьюером (ctransformers + RAG)*")
    
    return "\n".join(review)


# ============================================================================
# 5. Главная функция
# ============================================================================

def main():
    print("=" * 60)
    print("AI Code Review")
    print("=" * 60)
    
    # Получаем diff
    print("\n📥 Получение diff...")
    diff = get_diff()
    files = get_changed_files()
    
    print(f"   Изменено файлов: {len(files)}")
    for f in files[:10]:
        print(f"   - {f}")
    
    # Парсим diff
    print("\n🔍 Парсинг diff...")
    parsed = parse_diff(diff)
    print(f"   Файлов с изменениями: {len(parsed)}")
    
    # Генерируем ревью
    print("\n🤖 Генерация ревью...")
    review = generate_review(diff, parsed)
    
    # Сохраняем
    with open("review_output.md", "w", encoding="utf-8") as f:
        f.write(review)
    
    # Выводим
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ РЕВЬЮ")
    print("=" * 60)
    print(review)
    print("\n" + "=" * 60)
    print("✅ Ревью сохранено в review_output.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
