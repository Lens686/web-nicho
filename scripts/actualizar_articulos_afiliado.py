#!/usr/bin/env python3
"""Convierte articulos existentes al formato de guia de compra para afiliacion.

Por seguridad, el script funciona en modo simulacion por defecto. Solo modifica
archivos cuando se pasa --apply.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from crear_articulo_afiliado import ROOT, build_article, infer_product


DEFAULT_CONTENT_DIR = ROOT / "content" / "post"
DEFAULT_BACKUP_ROOT = ROOT / ".article_backups"


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL)


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text

    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values, text[match.end() :]


def has_affiliate_format(text: str) -> bool:
    return "{{< afiliado" in text or "Este articulo puede contener enlaces de afiliado" in text


def infer_audience(title: str, default: str) -> str:
    lowered = title.lower()
    patterns = [
        (r"\bpara familias\b", "familias"),
        (r"\bpara principiantes\b", "principiantes"),
        (r"\bpara trabajar en la oficina\b", "oficinas y trabajo diario"),
        (r"\bpara la oficina\b", "oficinas y trabajo diario"),
        (r"\bpara varios dias\b", "rutas de varios dias"),
        (r"\bpara casas con mascotas\b", "casas con mascotas"),
        (r"\bpara ni", "familias con ninos"),
        (r"\bpara senderismo\b", "senderismo"),
        (r"\bpara montan", "montana y trekking"),
        (r"\bpara videojuegos\b", "videojuegos"),
    ]
    for pattern, audience in patterns:
        if re.search(pattern, lowered):
            return audience
    return default


def iter_markdown_files(content_dir: Path, glob_pattern: str) -> list[Path]:
    return sorted(path for path in content_dir.glob(glob_pattern) if path.is_file())


def backup_file(path: Path, content_dir: Path, backup_root: Path, stamp: str) -> Path:
    relative = path.relative_to(content_dir)
    backup_path = backup_root / stamp / relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def convert_file(path: Path, default_audience: str) -> tuple[str, str]:
    original = path.read_text(encoding="utf-8-sig")
    front_matter, _body = parse_front_matter(original)
    title = front_matter.get("title") or path.stem.replace("_", " ").title()
    date = front_matter.get("date") or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    draft = front_matter.get("draft", "false").lower()
    audience = infer_audience(title, default_audience)
    product = infer_product(title)
    article = build_article(title, date, product, audience)
    article = article.replace("draft: false", f"draft: {draft}", 1)
    return original, article


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Actualiza articulos Markdown existentes al formato de guia de compra para afiliados."
    )
    parser.add_argument(
        "--content-dir",
        default=str(DEFAULT_CONTENT_DIR),
        help="Carpeta con articulos Markdown. Por defecto content/post.",
    )
    parser.add_argument(
        "--glob",
        default="*.md",
        help="Patron de archivos a procesar. Por defecto *.md.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Procesa solo los primeros N archivos. Util para probar.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica cambios. Sin esta opcion solo muestra lo que haria.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocesa tambien articulos que ya tienen bloques de afiliado.",
    )
    parser.add_argument(
        "--allow-generic-rewrite",
        action="store_true",
        help="Permite usar el conversor generico. No recomendado para articulos finales.",
    )
    parser.add_argument(
        "--audience",
        default="la mayoria de usuarios",
        help="Publico por defecto si no puede deducirse del titulo.",
    )
    parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_ROOT),
        help="Carpeta donde guardar copias antes de sobrescribir.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and not args.allow_generic_rewrite:
        print(
            "Bloqueado: este conversor genera articulos demasiado genericos. "
            "Usa scripts/asistente_afiliados.py para enlaces o pasa "
            "--allow-generic-rewrite si sabes que quieres sobrescribir contenido.",
            file=sys.stderr,
        )
        return 2

    content_dir = Path(args.content_dir)
    if not content_dir.is_absolute():
        content_dir = ROOT / content_dir
    if not content_dir.exists():
        print(f"No existe la carpeta: {content_dir}", file=sys.stderr)
        return 2

    backup_root = Path(args.backup_dir)
    if not backup_root.is_absolute():
        backup_root = ROOT / backup_root
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    files = iter_markdown_files(content_dir, args.glob)
    if args.limit > 0:
        files = files[: args.limit]

    changed = 0
    skipped = 0
    for path in files:
        original_text = path.read_text(encoding="utf-8-sig")
        if has_affiliate_format(original_text) and not args.force:
            skipped += 1
            print(f"SKIP ya preparado: {path}")
            continue

        original, converted = convert_file(path, args.audience)
        if original == converted:
            skipped += 1
            print(f"SKIP sin cambios: {path}")
            continue

        changed += 1
        if args.apply:
            backup_path = backup_file(path, content_dir, backup_root, stamp)
            path.write_text(converted, encoding="utf-8", newline="\n")
            print(f"OK actualizado: {path} (backup: {backup_path})")
        else:
            print(f"DRY-RUN actualizaria: {path}")

    mode = "aplicado" if args.apply else "simulacion"
    print(f"Resumen ({mode}): {changed} para actualizar, {skipped} omitidos, {len(files)} revisados.")
    if not args.apply:
        print("Ejecuta de nuevo con --apply para escribir cambios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
