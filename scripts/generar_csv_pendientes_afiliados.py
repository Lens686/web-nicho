#!/usr/bin/env python3
"""Genera un CSV con los bloques de afiliado pendientes de rellenar."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "content" / "post"
DEFAULT_OUTPUT = ROOT / "data" / "productos_afiliados.csv"
AFFILIATE_RE = re.compile(r"\{\{<\s*afiliado\b(?P<attrs>.*?)>\}\}", re.DOTALL)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def parse_attrs(attrs: str) -> dict[str, str]:
    return {key: value for key, value in ATTR_RE.findall(attrs)}


def is_pending(attrs: dict[str, str]) -> bool:
    return not attrs.get("url") or attrs.get("store") == "Enlace pendiente"


def iter_pending_rows() -> list[dict[str, str]]:
    rows = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        for match in AFFILIATE_RE.finditer(text):
            attrs = parse_attrs(match.group("attrs"))
            if not is_pending(attrs):
                continue
            rows.append(
                {
                    "article": path.name,
                    "position": "replace",
                    "title": attrs.get("title", "Producto recomendado"),
                    "description": attrs.get("description", ""),
                    "url": "",
                    "image": attrs.get("image", ""),
                    "text": attrs.get("text", "Ver en Amazon"),
                }
            )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crea un CSV con productos pendientes de enlace.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Ruta del CSV de salida.")
    parser.add_argument("--force", action="store_true", help="Sobrescribe el CSV si ya existe.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    if output.exists() and not args.force:
        print(f"El CSV ya existe: {output}")
        print("Usa --force si quieres regenerarlo.")
        return 1

    rows = iter_pending_rows()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["article", "position", "title", "description", "url", "image", "text"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV generado: {output}")
    print(f"Productos pendientes: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
