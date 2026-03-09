"""
Скрипт для расстановки перекрёстных ссылок между статьями энциклопедии.

Для каждого markdown-файла в WEB/entertainment/:
1. Ищет вхождения падежных форм других понятий
2. Заменяет первое вхождение каждого понятия на markdown-ссылку
3. Не заменяет понятие внутри собственной статьи
4. Не заменяет в заголовках (строки с #) и уже существующих ссылках

Использование:
  python crosslink.py
  python crosslink.py --dry-run  # только показать, какие замены будут сделаны
"""

import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONCEPTS_PATH = os.path.join(SCRIPT_DIR, "concepts.json")
PAGES_DIR = os.path.join(SCRIPT_DIR, "..", "..", "WEB", "entertainment")


def load_concepts() -> list[dict]:
    with open(CONCEPTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_form_index(concepts: list[dict]) -> list[tuple[str, str, str]]:
    """
    Строит индекс: [(падежная_форма, concept_id, файл), ...]
    Сортировка по убыванию длины формы — чтобы длинные фразы
    матчились раньше коротких (например, "компьютерная игра" раньше "игра").
    """
    index = []
    for concept in concepts:
        for form in concept["title_forms"]:
            index.append((form.lower(), concept["id"], concept["file"]))
    # Длинные формы первыми — чтобы "образовательная игра" матчилась раньше "игра"
    index.sort(key=lambda x: -len(x[0]))
    return index


def add_crosslinks(
    text: str, current_concept_id: str, form_index: list
) -> tuple[str, list[str]]:
    """
    Расставляет ссылки в тексте. Возвращает (новый_текст, список_замен).
    """
    lines = text.split("\n")
    linked_concepts = set()  # понятия, на которые уже поставлена ссылка
    changes = []

    for line_idx, line in enumerate(lines):
        # Пропускаем заголовки
        if line.strip().startswith("#"):
            continue
        # Пропускаем пустые строки
        if not line.strip():
            continue

        for form, concept_id, filename in form_index:
            # Не ставим ссылку на самого себя
            if concept_id == current_concept_id:
                continue
            # Уже поставили ссылку на это понятие
            if concept_id in linked_concepts:
                continue

            # Ищем форму слова (с границами слов, регистронезависимо)
            pattern = re.compile(
                r"(?<!\[)(?<!\()"  # не внутри существующей ссылки
                r"\b(" + re.escape(form) + r")\b"
                r"(?!\]|\))",  # не внутри существующей ссылки
                re.IGNORECASE,
            )
            match = pattern.search(lines[line_idx])
            if match:
                original_text = match.group(1)
                replacement = f"[{original_text}]({filename})"
                # Заменяем только первое вхождение в этой строке
                lines[line_idx] = (
                    lines[line_idx][: match.start()]
                    + replacement
                    + lines[line_idx][match.end() :]
                )
                linked_concepts.add(concept_id)
                changes.append(f"  '{original_text}' → [{original_text}]({filename})")

    return "\n".join(lines), changes


def find_concept_by_file(concepts: list[dict], filename: str) -> dict | None:
    for c in concepts:
        if c["file"] == filename:
            return c
    return None


def main():
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(PAGES_DIR):
        print(f"Ошибка: директория {PAGES_DIR} не найдена.")
        print("Сначала запустите generate_pages.py")
        sys.exit(1)

    concepts = load_concepts()
    form_index = build_form_index(concepts)

    print(f"Загружено {len(concepts)} понятий, {len(form_index)} падежных форм")
    print(f"Директория статей: {PAGES_DIR}")
    if dry_run:
        print("Режим: dry-run (без записи файлов)\n")
    else:
        print()

    total_changes = 0

    md_files = [
        f for f in os.listdir(PAGES_DIR) if f.endswith(".md") and f != "index.md"
    ]

    for filename in sorted(md_files):
        filepath = os.path.join(PAGES_DIR, filename)
        concept = find_concept_by_file(concepts, filename)

        if not concept:
            print(f"⚠ {filename}: не найдено в concepts.json, пропускаю")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            original_text = f.read()

        new_text, changes = add_crosslinks(original_text, concept["id"], form_index)

        if changes:
            print(f"📝 {filename} ({concept['title']}): {len(changes)} ссылок")
            for change in changes:
                print(change)

            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_text)

            total_changes += len(changes)
        else:
            print(f"  {filename}: без изменений")

    print(
        f"\nИтого: {total_changes} перекрёстных ссылок {'(dry-run)' if dry_run else 'расставлено'}"
    )


if __name__ == "__main__":
    main()
