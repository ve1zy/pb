"""
Лабораторная 32: Автоматизация ревью кода (с LLM)
AI-ревьюер для PR с RAG и локальной LLM (TinyLlama)
"""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


# ============================================================================
# 1. Получение diff и измененных файлов
# ============================================================================

def get_diff() -> str:
    diff_file = "pr_diff.txt"
    if os.path.exists(diff_file):
        with open(diff_file, "r", encoding="utf-8") as f:
            return f.read()
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"


def get_changed_files() -> List[str]:
    files_file = "changed_files.txt"
    if os.path.exists(files_file):
        with open(files_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        return [f for f in result.stdout.split("\n") if f]
    except:
        return []


def parse_diff(diff: str) -> List[Dict]:
    files = []
    current_file = None
    
    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
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
    bugs = []
    
    if re.search(r'except\s*:', code):
        bugs.append("⚠️ `except:` без типа — скрывает все ошибки")
    
    if filename.endswith(".py") and "print(" in code:
        if "test" not in filename and "demo" not in filename:
            bugs.append("ℹ️ Найден `print()` — для логирования используй `logging`")
    
    if re.search(r'(password|secret|token|api_key)\s*=\s*["\']', code, re.IGNORECASE):
        bugs.append("🔴 Возможен hardcoded секрет — используй переменные окружения")
    
    todos = re.findall(r'TODO|FIXME|XXX', code)
    if todos:
        bugs.append(f"📝 Найдено {len(todos)} TODO/FIXME — не забыть")
    
    if re.search(r'execute\s*\(\s*["\'].*%s', code):
        bugs.append("🔴 Возможна SQL injection — используй параметризованные запросы")
    
    if re.search(r'\beval\s*\(|\bexec\s*\(', code):
        bugs.append("🔴 Использование eval/exec — опасно, лучше заменить")
    
    lines = code.split("\n")
    if len(lines) > 50:
        bugs.append(f"ℹ️ Функция/класс длиной {len(lines)} строк — рассмотри разбиение")
    
    return bugs


def check_style(code: str, filename: str) -> List[str]:
    style = []
    
    if not filename.endswith(".py"):
        return style
    
    if "def " in code and "-> " not in code and "import" not in code[:100]:
        style.append("💡 Рассмотри использование type hints")
    
    if "def " in code and '"""' not in code and "'''" not in code:
        style.append("💡 Добавь docstrings к функциям")
    
    return style


def check_architecture(files: List[Dict]) -> List[str]:
    arch = []
    
    has_tests = any("test" in f["file"].lower() for f in files)
    has_impl = any(f["file"].endswith(".py") and "test" not in f["file"].lower() for f in files)
    
    if has_impl and not has_tests:
        arch.append("⚠️ Нет тестов для нового кода")
    
    for f in files:
        total_lines = len(f["additions"]) + len(f["deletions"])
        if total_lines > 300:
            arch.append(f"📦 Файл {f['file']} изменен на {total_lines} строк — рассмотри разбиение")
    
    return arch


# ============================================================================
# 3. RAG: поиск в документации
# ============================================================================

def load_docs() -> List[Dict]:
    docs = []
    docs_dir = Path("docs_lab21")
    if docs_dir.exists():
        for md_file in docs_dir.rglob("*.md"):
            if md_file.is_file():
                with open(md_file, "r", encoding="utf-8") as f:
                    docs.append({"source": str(md_file), "content": f.read()})
    return docs


def find_relevant_docs(code: str, docs: List[Dict], top_k: int = 2) -> List[Dict]:
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
# 4. LLM: локальная модель для расширенного анализа
# ============================================================================

_llm_model = None

def load_llm():
    """Загружает локальную LLM (lazy loading)"""
    global _llm_model
    if _llm_model is not None:
        return _llm_model
    
    try:
        from ctransformers import AutoModelForCausalLM
        print("📦 Загрузка локальной LLM (TinyLlama)...", flush=True)
        _llm_model = AutoModelForCausalLM.from_pretrained(
            "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
            model_file="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
            model_type="llama"
        )
        print("✅ LLM загружена", flush=True)
        return _llm_model
    except Exception as e:
        print(f"⚠️ LLM недоступна: {e}", flush=True)
        return None


def ask_llm(prompt: str, max_tokens: int = 150) -> str:
    """Запрашивает ответ у локальной LLM"""
    model = load_llm()
    if model is None:
        return ""
    
    try:
        response = model(prompt, max_new_tokens=max_tokens, temperature=0.3)
        return response.strip()
    except Exception as e:
        return f"LLM error: {e}"


def get_llm_explanation(bug: str, code_snippet: str) -> str:
    """Получает объяснение бага от LLM"""
    prompt = f"""Проблема в коде: {bug}

Код:
{code_snippet[:200]}

Дай краткое объяснение (1-2 предложения) на русском:"""
    
    return ask_llm(prompt, max_tokens=80)


def get_llm_summary(static_findings: Dict) -> str:
    """Получает общее резюме от LLM"""
    summary = f"Файлов: {static_findings['files_count']}, багов: {len(static_findings['bugs'])}, стиль: {len(static_findings['style'])}"
    
    prompt = f"""Ты — ревьюер кода. Дай краткий комментарий (1-2 предложения).

Найдено: {summary}
Файлы: {', '.join(static_findings['files'][:3])}

Ответ:"""
    
    return ask_llm(prompt, max_tokens=100)


# ============================================================================
# 5. Генерация ревью
# ============================================================================

def generate_review(diff: str, files: List[Dict], use_llm: bool = True) -> str:
    """Генерирует текст ревью"""
    review = []
    review.append("## 🤖 AI Code Review\n")
    review.append(f"**Изменено файлов:** {len(files)}\n")
    review.append(f"**Строк добавлено:** {sum(len(f['additions']) for f in files)}\n")
    review.append(f"**Строк удалено:** {sum(len(f['deletions']) for f in files)}\n")
    review.append("")
    
    all_bugs = []
    all_style = []
    all_added_code = []
    
    for f in files:
        added_code = "\n".join(f["additions"])
        all_added_code.append(added_code)
        bugs = check_bugs(added_code, f["file"])
        style = check_style(added_code, f["file"])
        
        if bugs:
            all_bugs.extend([(f["file"], b) for b in bugs])
        if style:
            all_style.extend([(f["file"], s) for s in style])
    
    arch_issues = check_architecture(files)
    
    all_added = "\n".join(all_added_code)
    docs = load_docs()
    relevant_docs = find_relevant_docs(all_added, docs)
    
    if all_bugs:
        review.append("### 🐛 Потенциальные баги\n")
        for file, bug in all_bugs:
            review.append(f"- **{file}**: {bug}")
            
            # LLM объяснение для критических багов
            if use_llm and ("🔴" in bug or "SQL injection" in bug):
                snippet = next((c for c in all_added_code if file.split('/')[-1] in c or len(c) > 0), "")
                explanation = get_llm_explanation(bug, snippet)
                if explanation and "error" not in explanation.lower():
                    review.append(f"  > 💡 _{explanation[:200]}_")
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
    
    # LLM резюме
    if use_llm and (all_bugs or arch_issues or all_style):
        review.append("### 🎯 Общее резюме (LLM)\n")
        static_findings = {
            "files_count": len(files),
            "bugs": all_bugs,
            "style": all_style,
            "files": [f["file"] for f in files]
        }
        summary = get_llm_summary(static_findings)
        if summary and "error" not in summary.lower() and len(summary) > 10:
            review.append(f"_{summary}_")
            review.append("")
    
    review.append("### 💡 Рекомендации\n")
    review.append("- ✅ Проверь что тесты покрывают новый код")
    review.append("- ✅ Запусти линтер (flake8/pylint/ruff)")
    review.append("- ✅ Проверь что нет hardcoded секретов")
    review.append("- ✅ Убедись что документация обновлена")
    review.append("")
    
    review.append("---")
    review.append("*Сгенерировано AI-ревьюером (статический анализ + RAG + LLM)*")
    
    return "\n".join(review)


# ============================================================================
# 6. Главная функция
# ============================================================================

def main():
    print("=" * 60)
    print("AI Code Review (с LLM)")
    print("=" * 60)
    
    diff = get_diff()
    files = get_changed_files()
    
    print(f"\n📥 Diff: {len(diff)} символов")
    print(f"📁 Изменено файлов: {len(files)}")
    
    parsed = parse_diff(diff)
    
    print("\n🤖 Генерация ревью...")
    review = generate_review(diff, parsed, use_llm=True)
    
    with open("review_output.md", "w", encoding="utf-8") as f:
        f.write(review)
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ РЕВЬЮ")
    print("=" * 60)
    print(review)
    print("\n" + "=" * 60)
    print("✅ Ревью сохранено в review_output.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
