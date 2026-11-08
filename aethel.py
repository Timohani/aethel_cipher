#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aethel — искусственный контекстный язык."""

import random
import os
from pathlib import Path

# Включаем поддержку ANSI-цветов в Windows 10 (CMD/PowerShell)
if os.name == 'nt':
    os.system('')

DIALECTS_DIR = Path("dialects")
STATE_FILE = Path(".last_dialect.txt")  # Файл для запоминания активного диалекта
ALPHABET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
SPACE = " "
PREV_STATES = list(ALPHABET) + [SPACE]
START_PREV = SPACE
MARKER = "/"
SPACE_ALIAS = "_"


# --- ЦВЕТА ДЛЯ ТЕРМИНАЛА ---
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


# --- УПРАВЛЕНИЕ ДИАЛЕКТАМИ ---

def get_dialect_files():
    """Возвращает список кортежей: (путь_к_файлу, имя_диалекта_из_header)."""
    if not DIALECTS_DIR.exists():
        return []

    dialects = []
    for file in DIALECTS_DIR.glob("cipher_config*.txt"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("# Диалект:"):
                    name = first_line.split(":", 1)[1].strip()
                    dialects.append((file, name))
                else:
                    dialects.append((file, "Без имени"))
        except Exception:
            continue

    dialects.sort(key=lambda x: x[0].name)
    return dialects


def save_active_dialect(filepath):
    """Сохраняет имя файла активного диалекта в скрытый файл состояния."""
    try:
        STATE_FILE.write_text(filepath.name, encoding="utf-8")
    except Exception:
        pass


def load_active_dialect(dialects):
    """Возвращает (file, name) последнего активного диалекта, если он существует."""
    if STATE_FILE.exists():
        try:
            last_name = STATE_FILE.read_text(encoding="utf-8").strip()
            for file, name in dialects:
                if file.name == last_name:
                    return file, name
        except Exception:
            pass
    return dialects[0]


def create_dialect():
    """Создает новый файл диалекта в папке."""
    DIALECTS_DIR.mkdir(exist_ok=True)

    print(f"\n{C.CYAN}--- СОЗДАНИЕ НОВОГО ДИАЛЕКТА AETHEL ---{C.RESET}")
    name = input(f"{C.GREEN}Введите название диалекта (или Enter для автогенерации): {C.RESET}").strip()
    if not name:
        name = f"Случайный_{random.randint(1000, 9999)}"

    print(f"{C.GRAY}[i] Создается диалект: '{name}'{C.RESET}")
    rng = random.Random(name)

    file_num = 1
    while (DIALECTS_DIR / f"cipher_config{file_num}.txt").exists():
        file_num += 1
    filepath = DIALECTS_DIR / f"cipher_config{file_num}.txt"

    lines = [
        f"# Диалект: {name}",
        "# letter|previous|symbol"
    ]

    ranges = [
        (0x00C0, 0x024F), (0x0370, 0x03FF), (0x0400, 0x04FF),
        (0x0530, 0x058F), (0x10A0, 0x10FF), (0x3040, 0x309F),
        (0x30A0, 0x30FF), (0x1200, 0x137F),
    ]
    russian = set(ALPHABET + ALPHABET.upper())
    pool = []

    for start, end in ranges:
        for cp in range(start, end + 1):
            ch = chr(cp)
            if ch.isalpha() and ch not in russian:
                pool.append(ch)

    if len(pool) < 1122:
        raise RuntimeError("Не хватило символов в выбранных диапазонах юникода!")

    pool = pool[:1122]
    rng.shuffle(pool)

    rules = [(letter, prev) for prev in PREV_STATES for letter in ALPHABET]
    rng.shuffle(rules)

    idx = 0
    for letter, prev in rules:
        prev_str = SPACE_ALIAS if prev == SPACE else prev
        lines.append(f"{letter}|{prev_str}|{pool[idx]}")
        idx += 1

    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{C.GREEN}[i] Файл сохранен: {filepath}{C.RESET}")
    return filepath


def load_dialect_file(filepath):
    """Загружает правила из конкретного файла."""
    mapping, reverse = {}, {}
    lines = filepath.read_text(encoding="utf-8").splitlines()

    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            raise ValueError(f"строка {n}: ожидалось 'буква|предыдущая|символ'")

        letter, prev, symbol = parts
        if prev in ("", SPACE_ALIAS):
            prev = SPACE

        if letter not in ALPHABET: raise ValueError(f"строка {n}: неизвестная буква {letter!r}")
        if prev not in PREV_STATES: raise ValueError(f"строка {n}: недопустимый предыдущий {prev!r}")
        if not symbol.isalpha(): raise ValueError(f"строка {n}: символ {symbol!r} должен быть буквой")

        key = (letter, prev)
        if key in mapping or symbol in reverse: raise ValueError(f"строка {n}: дубликат")

        mapping[key] = symbol
        reverse[symbol] = key

    need = len(ALPHABET) * len(PREV_STATES)
    if len(mapping) != need:
        raise ValueError(f"в конфиге {len(mapping)} правил, а нужно {need}")
    return mapping, reverse


# --- ШИФРОВАНИЕ И РАСШИФРОВКА ---

def encrypt_full(text, mapping):
    out, prev = [], START_PREV
    for ch in text:
        low = ch.lower()
        if low in ALPHABET:
            out.append(mapping[(low, prev)])
            prev = low
        elif ch == SPACE:
            out.append(ch)
            prev = SPACE
        elif ch == MARKER:
            out.append(MARKER + MARKER)
        elif ch.isalpha():
            out.append(MARKER + ch)
        else:
            out.append(ch)
    return "".join(out)


def encrypt_short(text, mapping):
    out, prev, pending = [], START_PREV, None

    def flush_pending():
        nonlocal pending, prev
        if pending:
            out.append(mapping[(pending, prev)])
            prev = pending
            pending = None

    for ch in text:
        low = ch.lower()
        if low in ALPHABET:
            if pending:
                out.append(mapping[(low, pending)])
                prev = low
                pending = None
            else:
                pending = low
        else:
            flush_pending()
            if ch == SPACE:
                out.append(ch)
                prev = SPACE
            elif ch == MARKER:
                out.append(MARKER + MARKER)
            elif ch.isalpha():
                out.append(MARKER + ch)
            else:
                out.append(ch)

    flush_pending()
    return "".join(out)


def decrypt_dynamic(cipher, reverse):
    out, prev, i = [], START_PREV, 0

    while i < len(cipher):
        ch = cipher[i]

        if ch == MARKER:
            if i + 1 >= len(cipher):
                out.append(MARKER)
                i += 1
                continue
            nxt = cipher[i + 1]
            out.append(MARKER if nxt == MARKER else nxt)
            i += 2

        elif ch == "(":
            i += 1
            while i < len(cipher) and cipher[i] != ")":
                sym = cipher[i]
                if sym in reverse:
                    letter, expected_prev = reverse[sym]
                    out.append(expected_prev)
                    out.append(letter)
                    prev = letter
                i += 1
            i += 1

        elif ch in reverse:
            letter, expected_prev = reverse[ch]
            if expected_prev == prev:
                out.append(letter)
                prev = letter
            else:
                out.append(expected_prev)
                out.append(letter)
                prev = letter
            i += 1

        elif ch == SPACE:
            out.append(ch)
            prev = SPACE
            i += 1
        else:
            out.append(ch)
            i += 1

    return "".join(out)


# --- ГЛАВНЫЙ ЦИКЛ ---

def show_about():
    print(f"\n{C.CYAN}{'=' * 50}")
    print(f"{C.BOLD}            О ЯЗЫКЕ AETHEL{C.RESET}{C.CYAN}")
    print(f"{'=' * 50}{C.RESET}")
    print("Aethel — это искусственный язык, в котором")
    print("написание буквы зависит от предыдущей буквы.")
    print(f"\n{C.YELLOW}Особенности:{C.RESET}")
    print("• Полный режим: 1 буква = 1 символ (как в обычном письме).")
    print("• Краткий режим: 2 буквы = 1 символ (как в скороговорке).")
    print("• Скобки (): используются как 'ударение', чтобы подсказать")
    print("  программе, что внутри скобок 100% пара букв.")
    print(f"\n{C.YELLOW}Диалекты:{C.RESET} Чтобы общаться с другом, создайте")
    print("одинаковые диалекты (введите один и тот же ключ).")
    print(f"\n{C.RED}Автор:{C.RESET} TIMOHANI")
    print(f"{C.GREEN}Соавтор:{C.RESET} EXSIICYAN")
    print(f"{C.CYAN}{'=' * 50}{C.RESET}\n")


def main():
    print(f"\n{C.CYAN}{'=' * 50}")
    print(f"{C.BOLD}{C.CYAN}                  A E T H E L{C.RESET}")
    print(f"{C.ITALIC}{C.GRAY}          Искусственный контекстный язык{C.RESET}")
    print(f"{C.CYAN}{'=' * 50}{C.RESET}")

    DIALECTS_DIR.mkdir(exist_ok=True)
    current_mapping, current_reverse = None, None
    current_name = ""
    current_file = None

    dialects = get_dialect_files()
    if not dialects:
        print(f"{C.RED}[!] Не найдено ни одного диалекта. Создадим первый!{C.RESET}")
        current_file = create_dialect()
        current_mapping, current_reverse = load_dialect_file(current_file)
        current_name = "Только что созданный"
        save_active_dialect(current_file)
    else:
        current_file, current_name = load_active_dialect(dialects)
        current_mapping, current_reverse = load_dialect_file(current_file)

    print(f"\n{C.GREEN}[i] Активный диалект: {C.YELLOW}«{current_name}»{C.RESET}\n")

    while True:
        print(f"{C.CYAN}{'-' * 50}{C.RESET}")
        print(f"{C.WHITE}Текущий диалект: {C.YELLOW}{current_name}{C.RESET}")
        print(f"{C.BLUE}1{C.RESET} — Перевести текст на Aethel")
        print(f"{C.BLUE}2{C.RESET} — Перевести текст с Aethel")
        print(f"{C.BLUE}3{C.RESET} — Сменить диалект")
        print(f"{C.BLUE}4{C.RESET} — Создать новый диалект")
        print(f"{C.BLUE}5{C.RESET} — О языке Aethel")
        print(f"{C.BLUE}6{C.RESET} — Выход")

        try:
            choice = input(f"\n{C.GREEN}Выбор: {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "6":
            break

        elif choice == "5":
            show_about()
            continue

        elif choice == "4":
            try:
                new_file = create_dialect()
                current_mapping, current_reverse = load_dialect_file(new_file)
                current_file = new_file
                current_name = [name for f, name in get_dialect_files() if f == new_file][0]
                save_active_dialect(current_file)
                print(f"\n{C.GREEN}[i] Диалект успешно сменен на «{C.YELLOW}{current_name}{C.GREEN}»{C.RESET}\n")
            except Exception as e:
                print(f"{C.RED}Ошибка при создании: {e}{C.RESET}")
            continue

        elif choice == "3":
            dialects = get_dialect_files()
            if not dialects:
                print(f"{C.RED}Нет доступных диалектов.{C.RESET}\n")
                continue

            print(f"\n{C.CYAN}--- ДОСТУПНЫЕ ДИАЛЕКТЫ ---{C.RESET}")
            for idx, (file, name) in enumerate(dialects, 1):
                mark = f" {C.GREEN}[АКТИВЕН]{C.RESET}" if file == current_file else ""
                print(f"{C.BLUE}{idx}{C.RESET}. {name}{mark}")

            try:
                sel = input(f"\n{C.GREEN}Выберите номер (или Enter для отмены): {C.RESET}").strip()
                if not sel:
                    continue
                sel_idx = int(sel) - 1
                if 0 <= sel_idx < len(dialects):
                    current_file, current_name = dialects[sel_idx]
                    current_mapping, current_reverse = load_dialect_file(current_file)
                    save_active_dialect(current_file)
                    print(f"\n{C.GREEN}[i] Загружен диалект: {C.YELLOW}«{current_name}»{C.RESET}\n")
                else:
                    print(f"{C.RED}Неверный номер.{C.RESET}\n")
            except ValueError:
                print(f"{C.RED}Нужно ввести число.{C.RESET}\n")
            continue

        if choice not in ("1", "2"):
            print(f"{C.RED}Не понял, попробуйте ещё раз.{C.RESET}\n")
            continue

        try:
            text = input(f"{C.GREEN}Текст: {C.RESET}")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        try:
            if choice == "1":
                print(f"\n{C.CYAN}[Полная запись]:{C.RESET}")
                print(f"{C.MAGENTA}{encrypt_full(text, current_mapping)}{C.RESET}")
                print(f"\n{C.CYAN}[Краткая запись (слоговая)]:{C.RESET}")
                print(f"{C.MAGENTA}{encrypt_short(text, current_mapping)}{C.RESET}")
            elif choice == "2":
                print(f"\n{C.CYAN}[Перевод на русский]:{C.RESET}")
                print(f"{C.GREEN}{decrypt_dynamic(text, current_reverse)}{C.RESET}")
        except ValueError as e:
            print(f"{C.RED}Ошибка: {e}{C.RESET}")
        print()


if __name__ == "__main__":
    main()