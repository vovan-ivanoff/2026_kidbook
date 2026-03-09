"""
Скрипт для генерации markdown-страничек детской энциклопедии
через GigaChat API (Python SDK).

Для каждого понятия из concepts.json генерирует статью,
используя контекст из WikiData (если доступен).

Использование:
  1. Установите зависимости: pip install -r requirements.txt
  2. Создайте файл .env рядом со скриптом и укажите:
       GIGACHAT_CREDENTIALS=ваш_ключ_авторизации
     (ключ авторизации (Authorization key) из https://developers.sber.ru/studio/)
     Либо задайте переменную окружения GIGACHAT_CREDENTIALS.
  3. Запустите: python generate_pages.py

  Опционально: сначала запустите wikidata_extract.py,
  чтобы обогатить промпты данными из WikiData.
"""

import json
import os
import sys
import time

from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Загружаем переменные из .env файла (если есть)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Пути
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONCEPTS_PATH = os.path.join(SCRIPT_DIR, "concepts.json")
CONTEXTS_PATH = os.path.join(SCRIPT_DIR, "wikidata", "_contexts.json")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "..", "WEB", "entertainment")

# Параметры генерации
TEMPERATURE = 0.7
MAX_TOKENS = 1500
MODEL = "GigaChat"  # бесплатная модель

SYSTEM_PROMPT = (
    "Ты автор детской энциклопедии. Пиши просто, интересно и понятно "
    "для десятилетнего ребёнка. Используй короткие предложения, яркие "
    "примеры и аналогии из повседневной жизни. Добавляй забавные факты. "
    "Структурируй текст с помощью markdown-заголовков."
)

USER_PROMPT_TEMPLATE = (
    "Напиши статью для детской энциклопедии о понятии «{title}».\n\n"
    "Требования:\n"
    "- Объясни для десятилетнего ребёнка, что это такое\n"
    "- Расскажи краткую историю\n"
    "- Приведи 2-3 интересных факта\n"
    "- Приведи примеры из реальной жизни\n"
    "- Объясни, чем это полезно\n"
    "- Расскажи, что может быть вредно при неправильном использовании\n"
    "- Дай совет по балансу пользы и развлечения\n"
    "{wikidata_context}"
    "\nОтвет в формате markdown. Начни с заголовка # {title}."
)


def load_concepts() -> list[dict]:
    with open(CONCEPTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_wikidata_contexts() -> dict[str, str]:
    if os.path.exists(CONTEXTS_PATH):
        with open(CONTEXTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_prompt(concept: dict, wikidata_context: str) -> str:
    ctx_block = ""
    if wikidata_context:
        ctx_block = f"\nДополнительная информация из WikiData: {wikidata_context}\n"
    return USER_PROMPT_TEMPLATE.format(
        title=concept["title"],
        wikidata_context=ctx_block,
    )


def generate_article(giga: GigaChat, concept: dict, wikidata_context: str) -> str:
    user_prompt = build_prompt(concept, wikidata_context)

    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT),
            Messages(role=MessagesRole.USER, content=user_prompt),
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    response = giga.chat(payload)
    return response.choices[0].message.content


def main():
    # Credentials: из .env файла или переменной окружения GIGACHAT_CREDENTIALS
    credentials = os.getenv("GIGACHAT_CREDENTIALS", "")
    if not credentials:
        print("Ошибка: ключ авторизации GigaChat не найден.")
        print()
        print("Способ 1 (рекомендуемый): создайте файл .env рядом со скриптом:")
        print("  GIGACHAT_CREDENTIALS=ваш_authorization_key")
        print()
        print("Способ 2: задайте переменную окружения:")
        print("  Windows PowerShell:  $env:GIGACHAT_CREDENTIALS='ваш_ключ'")
        print("  Linux/macOS:         export GIGACHAT_CREDENTIALS=ваш_ключ")
        print()
        print("Ключ авторизации (Authorization key) берётся на странице:")
        print("  https://developers.sber.ru/studio/")
        sys.exit(1)

    concepts = load_concepts()
    wikidata_contexts = load_wikidata_contexts()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Загружено {len(concepts)} понятий")
    print(
        f"WikiData-контексты: {'найдены' if wikidata_contexts else 'не найдены (запустите wikidata_extract.py)'}"
    )
    print(f"Выходная директория: {OUTPUT_DIR}")
    print(f"Модель: {MODEL}, temperature={TEMPERATURE}\n")

    generated = 0
    errors = 0

    with GigaChat(
        credentials=credentials,
        verify_ssl_certs=False,
        model=MODEL,
        scope="GIGACHAT_API_PERS",
    ) as giga:
        for i, concept in enumerate(concepts, 1):
            print(f"[{i}/{len(concepts)}] Генерирую: {concept['title']}...", end=" ")

            # Проверяем, не сгенерирован ли уже файл
            output_path = os.path.join(OUTPUT_DIR, concept["file"])
            if os.path.exists(output_path):
                print("⏭ уже существует, пропускаю")
                generated += 1
                continue

            try:
                ctx = wikidata_contexts.get(concept["id"], "")
                text = generate_article(giga, concept, ctx)

                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text)

                print(f"✓ ({len(text)} символов)")
                generated += 1

            except Exception as e:
                print(f"✗ Ошибка: {e}")
                errors += 1

            # Пауза между запросами (ограничение бесплатного лимита)
            if i < len(concepts):
                time.sleep(2)

    print(f"\nГотово! Сгенерировано: {generated}, ошибок: {errors}")
    print(f"Файлы сохранены в: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
