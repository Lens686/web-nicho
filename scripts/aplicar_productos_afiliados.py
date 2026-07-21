#!/usr/bin/env python3
"""Inserta productos de afiliado desde un CSV en articulos Hugo.

Modo seguro por defecto: sin --apply solo muestra lo que haria.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "content" / "post"
DEFAULT_CSV = ROOT / "data" / "productos_afiliados.csv"
DEFAULT_BACKUP_ROOT = ROOT / ".article_backups"
AFFILIATE_RE = re.compile(r"\{\{<\s*afiliado\b.*?>\}\}", re.DOTALL)
TITLE_ATTR_RE = re.compile(r'title="([^"]*)"')


def shortcode(row: dict[str, str]) -> str:
    attrs = []
    for key in ("url", "title", "description", "image", "text"):
        value = (row.get(key) or "").strip()
        if value:
            escaped = value.replace('"', '\\"')
            attrs.append(f'{key}="{escaped}"')
    if not attrs:
        raise ValueError("fila sin datos utiles para el shortcode")
    return "{{< afiliado " + " ".join(attrs) + " >}}"


def remove_blocks_with_title(text: str, title: str) -> str:
    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        title_match = TITLE_ATTR_RE.search(block)
        if title_match and title_match.group(1).strip().lower() == title.strip().lower():
            return ""
        return block

    cleaned = AFFILIATE_RE.sub(replace, text)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def replace_block_with_title(text: str, title: str, new_block: str) -> tuple[str, bool]:
    def replace(match: re.Match[str]) -> str:
        block = match.group(0)
        title_match = TITLE_ATTR_RE.search(block)
        if title_match and title_match.group(1).strip().lower() == title.strip().lower():
            return new_block
        return block

    updated = AFFILIATE_RE.sub(replace, text)
    return updated, updated != text


def replace_pending_after_heading(text: str, heading: str, block: str) -> tuple[str, bool]:
    heading_marker = "\n## " + heading.strip()
    heading_index = text.lower().find(heading_marker.lower())
    if heading_index < 0:
        return text, False

    next_heading = text.find("\n## ", heading_index + len(heading_marker))
    section_end = next_heading if next_heading >= 0 else len(text)
    section = text[heading_index:section_end]
    match = AFFILIATE_RE.search(section)
    if not match:
        return text, False

    existing = match.group(0)
    if "Enlace pendiente" not in existing and 'store="' not in existing:
        return text, False

    start = heading_index + match.start()
    end = heading_index + match.end()
    return text[:start] + block + text[end:], True


def insert_after_intro(text: str, block: str) -> str:
    marker = "Este articulo puede contener enlaces de afiliado."
    marker_index = text.find(marker)
    if marker_index >= 0:
        next_blank = text.find("\n\n", marker_index)
        if next_blank >= 0:
            return text[: next_blank + 2] + block + "\n\n" + text[next_blank + 2 :]

    front_end = text.find("---", 3)
    if text.startswith("---") and front_end >= 0:
        body_start = text.find("\n", front_end + 3)
        if body_start >= 0:
            first_blank = text.find("\n\n", body_start + 1)
            if first_blank >= 0:
                return text[: first_blank + 2] + block + "\n\n" + text[first_blank + 2 :]
    return block + "\n\n" + text


def insert_at_end(text: str, block: str) -> str:
    return text.rstrip() + "\n\n" + block + "\n"


def insert_before_section(text: str, heading: str, block: str) -> str:
    section_marker = "\n## " + heading.strip()
    index = text.lower().find(section_marker.lower())
    if index < 0:
        return insert_at_end(text, block)
    return text[:index].rstrip() + "\n\n" + block + "\n" + text[index:]


def apply_row(text: str, row: dict[str, str]) -> str:
    block = shortcode(row)
    if block in text:
        return text

    position = (row.get("position") or "end").strip()
    if position == "replace":
        title = (row.get("title") or "").strip()
        if not title:
            raise ValueError("position replace requiere title")
        updated, did_replace = replace_block_with_title(text, title, block)
        return updated if did_replace else text

    title = (row.get("title") or "").strip()
    if title:
        text = remove_blocks_with_title(text, title)

    if position == "after_intro":
        return insert_after_intro(text, block)
    if position == "end":
        return insert_at_end(text, block)
    if position.startswith("section:"):
        heading = position.split(":", 1)[1]
        replaced, did_replace = replace_pending_after_heading(text, heading, block)
        if did_replace:
            return replaced
        return insert_before_section(text, heading, block)
    raise ValueError(f"position no valida: {position}")


def backup_file(path: Path, backup_root: Path, stamp: str) -> Path:
    backup_path = backup_root / stamp / path.name
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def detect_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,	")
    except csv.Error:
        dialect = csv.excel()
        dialect.delimiter = ";"
        return dialect


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    sample = csv_path.read_text(encoding="utf-8-sig")[:4096]
    dialect = detect_dialect(sample)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, dialect=dialect))


def validate_row(row: dict[str, str], row_number: int) -> list[str]:
    errors = []
    required = ("article", "position", "title", "description")
    for key in required:
        if not (row.get(key) or "").strip():
            errors.append(f"fila {row_number}: falta {key}")

    url = (row.get("url") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        errors.append(f"fila {row_number}: url no parece enlace valido: {url}")

    image = (row.get("image") or "").strip()
    if image and not image.startswith(("http://", "https://", "/")):
        errors.append(f"fila {row_number}: image no parece URL/ruta valida: {image}")

    extra = row.get(None)
    if extra:
        errors.append(
            f"fila {row_number}: sobran columnas; usa separador ';' o pon entre comillas textos con comas"
        )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inserta bloques de afiliado con enlace e imagen desde un CSV."
    )
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="CSV de productos. Por defecto data/productos_afiliados.csv.")
    parser.add_argument("--apply", action="store_true", help="Aplica cambios. Sin esto solo simula.")
    parser.add_argument("--limit", type=int, default=0, help="Procesa solo las primeras N filas del CSV.")
    parser.add_argument("--skip-empty-url", action="store_true", default=True, help="Omite filas sin URL. Activado por defecto.")
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_ROOT), help="Carpeta de copias de seguridad.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = ROOT / csv_path
    if not csv_path.exists():
        print(f"No existe el CSV: {csv_path}", file=sys.stderr)
        print("Copia data/productos_afiliados.example.csv como data/productos_afiliados.csv y rellenalo.", file=sys.stderr)
        return 2

    rows = load_rows(csv_path)
    if args.limit > 0:
        rows = rows[: args.limit]

    by_article: dict[Path, list[dict[str, str]]] = {}
    had_errors = False
    for index, row in enumerate(rows, start=2):
        if args.skip_empty_url and not (row.get("url") or "").strip():
            continue

        row_errors = validate_row(row, index)
        if row_errors:
            had_errors = True
            for error in row_errors:
                print(f"ERROR {error}", file=sys.stderr)
            continue

        article = (row.get("article") or "").strip()
        path = POSTS_DIR / article
        if not path.exists():
            print(f"SKIP no existe articulo: {path}")
            continue
        by_article.setdefault(path, []).append(row)

    if had_errors:
        print("Corrige el CSV antes de aplicar cambios.", file=sys.stderr)
        return 2

    changed = 0
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = Path(args.backup_dir)
    if not backup_root.is_absolute():
        backup_root = ROOT / backup_root

    for path, article_rows in by_article.items():
        original = path.read_text(encoding="utf-8-sig")
        updated = original
        for row in article_rows:
            updated = apply_row(updated, row)

        if updated == original:
            print(f"SKIP sin cambios: {path}")
            continue

        changed += 1
        if args.apply:
            backup_path = backup_file(path, backup_root, stamp)
            path.write_text(updated, encoding="utf-8", newline="\n")
            print(f"OK actualizado: {path} (backup: {backup_path})")
        else:
            print(f"DRY-RUN actualizaria: {path} con {len(article_rows)} producto(s)")

    mode = "aplicado" if args.apply else "simulacion"
    print(f"Resumen ({mode}): {changed} articulo(s) con cambios, {len(rows)} fila(s) revisadas.")
    if not args.apply:
        print("Ejecuta de nuevo con --apply para escribir cambios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
