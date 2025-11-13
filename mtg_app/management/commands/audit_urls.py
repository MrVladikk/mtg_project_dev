from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterable
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.urls import URLPattern, URLResolver, get_resolver

# -------- settings --------
PROJECT_ROOT_GUESS = Path(__file__).resolve().parents[3]  # корень репо
INCLUDE_EXT = {".py", ".html", ".txt"}  # где будем искать вызовы url/reverse
SKIP_DIRS = {
    ".git",
    "env",
    "venv",
    ".venv",
    "__pycache__",
    "node_modules",
    "migrations",
    "staticfiles",
    "media",
}

# Регексы, которые вытаскивают имена из Python и шаблонов
RE_PY_CALL = re.compile(
    r"""\b(?:reverse|reverse_lazy|redirect|resolve_url)\s*\(\s*['"](?P<name>[^'":\s][^'"]*)['"]""",
    re.IGNORECASE,
)
RE_TPL_URL = re.compile(
    r"""\{\%\s*url\s+['"](?P<name>[^'":\s][^'"]*)['"]""",
    re.IGNORECASE,
)

# Примеры коротких имён, которые обычно нужно проставить с namespace
LIKELY_SHORT = {"home", "cards_list", "sets_list", "thread_list", "thread_detail"}


def iter_named_urls(resolver=None, prefix="") -> Iterable[tuple[str, str]]:
    """
    Возвращает пары (полное_имя, пример_путь) из корневого resolver'a.
    """
    if resolver is None:
        resolver = get_resolver()

    for p in resolver.url_patterns:
        if isinstance(p, URLPattern):
            name = p.name
            if name:
                yield (name, str(p.pattern))
        elif isinstance(p, URLResolver):
            # рекурсивно
            for n, patt in iter_named_urls(p, prefix=str(p.pattern)):
                yield (n, patt)


def list_named_urlnames() -> set[str]:
    return {n for n, _ in iter_named_urls()}


def scan_file_for_names(path: Path) -> list[tuple[int, str, str]]:
    """
    Ищет вызовы в файле. Возвращает список (lineno, kind, name)
      kind: "py" | "tpl"
    """
    out: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return out

    for m in RE_PY_CALL.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        out.append((line_no, "py", m.group("name")))

    for m in RE_TPL_URL.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        out.append((line_no, "tpl", m.group("name")))

    return out


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if any(d in parts for d in SKIP_DIRS):
        return True
    if not path.is_file() or path.suffix not in INCLUDE_EXT:
        return True
    return False


def replace_in_text(text: str, replacements: dict[str, str]) -> tuple[str, int]:
    """
    Точечная замена имён без namespace на namespaced-значение в Python/шаблонах.
    Заменяем только внутри известных конструкций (reverse/redirect/{% url %}).
    """
    count = 0

    def repl_py(m):
        nonlocal count
        name = m.group("name")
        new = replacements.get(name)
        if not new:
            return m.group(0)
        count += 1
        return m.group(0).replace(name, new, 1)

    def repl_tpl(m):
        nonlocal count
        name = m.group("name")
        new = replacements.get(name)
        if not new:
            return m.group(0)
        count += 1
        return m.group(0).replace(name, new, 1)

    new_text = RE_PY_CALL.sub(repl_py, text)
    new_text = RE_TPL_URL.sub(repl_tpl, new_text)
    return new_text, count


class Command(BaseCommand):
    help = (
        "Аудит всех URL-имен в проекте: показывает невалидные имена, без-namespace вызовы, "
        "и при --write может автоматически проставить namespace (например mtg_app:...)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--root",
            default=str(PROJECT_ROOT_GUESS),
            help="Корень проекта (по умолчанию – автоопределение).",
        )
        parser.add_argument(
            "--namespace",
            default="mtg_app",
            help="Namespace, который нужно добавить к коротким именам (default: mtg_app).",
        )
        parser.add_argument(
            "--write",
            action="store_true",
            help="Записать правки в файлы (перед этим для каждого файла создаётся .bak).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Вывести результат в JSON (для CI).",
        )

    def handle(self, *args, **opts):
        root = Path(opts["root"]).resolve()
        namespace = opts["namespace"].strip()
        do_write = bool(opts["write"])
        as_json = bool(opts["json"])

        if not root.exists():
            raise CommandError(f"Root not found: {root}")

        # 1) Собираем имена из resolvers
        try:
            all_names = list_named_urlnames()
        except Exception as e:
            raise CommandError(f"Не удалось получить список URL-имён: {e}")

        # 2) Сканы файлов
        findings: dict[str, list[dict]] = {}
        unknown: dict[str, list[dict]] = {}
        plain_without_ns: dict[str, list[dict]] = {}

        for path in root.rglob("*"):
            if should_skip(path):
                continue
            hits = scan_file_for_names(path)
            if not hits:
                continue

            for lineno, kind, name in hits:
                rec = {"file": str(path), "line": lineno, "kind": kind, "name": name}
                findings.setdefault(str(path), []).append(rec)

                # namespaced?
                if ":" in name:
                    # уже namespaced — проверим валидную правую часть
                    short = name.split(":", 1)[1]
                    if short not in all_names:
                        unknown.setdefault(name, []).append(rec)
                else:
                    # без namespace
                    if name in all_names:
                        # имя валидно, но без namespace: считаем кандидатом на починку
                        plain_without_ns.setdefault(name, []).append(rec)
                    else:
                        # вообще неизвестное имя
                        unknown.setdefault(name, []).append(rec)

        result = {
            "project_root": str(root),
            "resolver_names_total": len(all_names),
            "resolver_names": sorted(all_names),
            "usages_total": sum(len(v) for v in findings.values()),
            "unknown_names": {k: v for k, v in sorted(unknown.items(), key=lambda x: x[0])},
            "plain_without_namespace": {
                k: v for k, v in sorted(plain_without_ns.items(), key=lambda x: x[0])
            },
        }

        if as_json:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n== URL audit @ {root} =="))
            self.stdout.write(f"Всего имен у резолвера: {len(all_names)}")
            self.stdout.write(f"Всего найденных вызовов в файлах: {result['usages_total']}")

            if result["unknown_names"]:
                self.stdout.write(self.style.ERROR("\n[НЕИЗВЕСТНЫЕ ИМЕНА]"))
                for name, recs in result["unknown_names"].items():
                    self.stdout.write(self.style.ERROR(f"  - '{name}'"))
                    for r in recs[:10]:
                        self.stdout.write(f"      {r['file']}:{r['line']} ({r['kind']})")
                    if len(recs) > 10:
                        self.stdout.write(f"      ... и ещё {len(recs)-10}")

            if result["plain_without_namespace"]:
                self.stdout.write(
                    self.style.WARNING(
                        "\n[ИМЕНА БЕЗ NAMESPACE] (существуют у резолвера, но без 'app:')"
                    )
                )
                for name, recs in result["plain_without_namespace"].items():
                    self.stdout.write(self.style.WARNING(f"  - {name}: {len(recs)} вхождений"))

        # 3) Автопочинка: добавим namespace к коротким именам (лишь если они есть у резолвера)
        if do_write:
            # составим карту замен: short -> f"{namespace}:{short}"
            replacements: dict[str, str] = {}
            for short_name in plain_without_ns.keys() or LIKELY_SHORT:
                if short_name in all_names:
                    replacements[short_name] = f"{namespace}:{short_name}"

            if not replacements:
                self.stdout.write(self.style.SUCCESS("\nИсправлять нечего — всё уже ок."))
                return

            self.stdout.write(self.style.MIGRATE_HEADING("\n== ПРИМЕНЯЕМ ИСПРАВЛЕНИЯ =="))
            total_changes = 0

            for path in root.rglob("*"):
                if should_skip(path):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                new_text, cnt = replace_in_text(text, replacements)
                if cnt:
                    # backup
                    bak = Path(str(path) + ".bak")
                    try:
                        shutil.copyfile(path, bak)
                    except Exception as e:
                        raise CommandError(f"Не могу сделать backup {bak}: {e}")
                    path.write_text(new_text, encoding="utf-8")
                    total_changes += cnt
                    self.stdout.write(f"[fixed {cnt:>2}] {path}")

            if total_changes:
                self.stdout.write(
                    self.style.SUCCESS(f"\nГотово. Исправлений: {total_changes}. Бэкапы: *.bak")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "\nЗамен не найдено — возможно, вхождения уже были с namespace."
                    )
                )
