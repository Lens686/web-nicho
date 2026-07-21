#!/usr/bin/env python3
"""Asistente simple para rellenar enlaces de afiliado sin editar CSV."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from aplicar_productos_afiliados import DEFAULT_BACKUP_ROOT, shortcode
from generar_csv_pendientes_afiliados import AFFILIATE_RE, POSTS_DIR, parse_attrs


TITLE_RE = re.compile(r'title:\s*"([^"]+)"')


def page_title(path: Path, text: str) -> str:
    match = TITLE_RE.search(text)
    return match.group(1) if match else path.stem.replace("_", " ")


def pending_items() -> list[dict[str, str]]:
    items = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        title = page_title(path, text)
        for index, match in enumerate(AFFILIATE_RE.finditer(text), start=1):
            attrs = parse_attrs(match.group("attrs"))
            if attrs.get("url") and attrs.get("store") != "Enlace pendiente":
                continue
            items.append(
                {
                    "article": path.name,
                    "article_title": title,
                    "block_title": attrs.get("title", "Producto recomendado"),
                    "description": attrs.get("description", ""),
                    "text": attrs.get("text", "Ver en Amazon"),
                    "start": str(match.start()),
                    "end": str(match.end()),
                }
            )
    return items


def backup_file(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = DEFAULT_BACKUP_ROOT / stamp / path.name
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def show_items(items: list[dict[str, str]], offset: int, page_size: int) -> None:
    end = min(offset + page_size, len(items))
    print()
    print(f"Pendientes {offset + 1}-{end} de {len(items)}")
    for number, item in enumerate(items[offset:end], start=offset + 1):
        print(f"{number}. {item['article_title']}")
        print(f"   Producto: {item['block_title']}")


def ask_index(items: list[dict[str, str]]) -> int | None:
    page_size = 12
    offset = 0
    while True:
        show_items(items, offset, page_size)
        print()
        print("Escribe numero, n siguiente, p anterior, q salir.")
        try:
            choice = input("> ").strip().lower()
        except EOFError:
            return None
        if choice == "q":
            return None
        if choice == "n":
            offset = min(offset + page_size, max(0, len(items) - 1))
            continue
        if choice == "p":
            offset = max(0, offset - page_size)
            continue
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(items):
                return index
        print("Opcion no valida.")


def update_item(item: dict[str, str], url: str, image: str) -> Path:
    path = POSTS_DIR / item["article"]
    text = path.read_text(encoding="utf-8-sig")
    start = int(item["start"])
    end = int(item["end"])
    row = {
        "url": url,
        "title": item["block_title"],
        "description": item["description"],
        "image": image,
        "text": item["text"] or "Ver en Amazon",
    }
    new_block = shortcode(row)
    backup_file(path)
    path.write_text(text[:start] + new_block + text[end:], encoding="utf-8", newline="\n")
    return path


def main() -> int:
    while True:
        items = pending_items()
        if not items:
            print("No quedan bloques de afiliado pendientes.")
            return 0

        selected = ask_index(items)
        if selected is None:
            return 0

        item = items[selected]
        print()
        print(f"Articulo: {item['article_title']}")
        print(f"Producto: {item['block_title']}")
        print(f"Descripcion: {item['description']}")
        url = input("Pega enlace de Amazon (intro para cancelar): ").strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            print("Ese enlace no parece valido.")
            continue
        image = input("Imagen opcional (intro para omitir): ").strip()
        updated = update_item(item, url, image)
        print(f"Actualizado: {updated}")


if __name__ == "__main__":
    raise SystemExit(main())
