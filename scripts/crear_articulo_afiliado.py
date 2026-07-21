#!/usr/bin/env python3
"""Crea articulos Hugo con formato de guia de compra para afiliacion."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "content" / "post"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text.lower()).strip("_")
    return re.sub(r"_+", "_", slug)


def clean_title(text: str) -> str:
    return " ".join(text.strip().split())


def infer_product(title: str) -> str:
    lowered = title.lower()
    prefixes = [
        "mejores ",
        "mejor ",
        "las mejores ",
        "los mejores ",
        "guia definitiva de compra para ",
        "guia de compra para ",
        "guia de compra de ",
        "comparativa de ",
        "comparativa completa de ",
    ]
    product = lowered
    for prefix in prefixes:
        if product.startswith(prefix):
            product = product[len(prefix) :]
            break
    product = re.sub(r"\b(baratas?|economicas?|del mercado|actual|completa|para .*)\b", "", product)
    product = " ".join(product.split())
    return product or lowered


def affiliate_block(title: str, description: str) -> str:
    return (
        '{{< afiliado '
        f'title="{title}" '
        f'description="{description}" '
        'store="Enlace pendiente" '
        ">}}"
    )


def build_article(title: str, date: str, product: str, audience: str) -> str:
    title = clean_title(title)
    product = clean_title(product)
    audience = clean_title(audience)

    return f"""---
title: "{title}"
date: {date}
draft: false
---

Elegir {product} no consiste solo en encontrar una opcion barata. Lo importante es comprar un producto que encaje con tu uso real, tenga buenas prestaciones para su precio y no acabe guardado despues de pocos dias.

Este articulo puede contener enlaces de afiliado. Si compras desde uno de ellos, la web puede recibir una comision sin coste adicional para ti.

{affiliate_block(
        f'Producto recomendado: {product}',
        'Sustituye este bloque por tu enlace de Amazon cuando tengas una opcion clara para recomendar.',
    )}

## Que mirar antes de comprar

### Uso principal

Antes de comparar modelos, define para que lo vas a usar. No necesita lo mismo una persona que busca una opcion sencilla para uso ocasional que alguien que va a utilizarlo varias veces por semana.

### Calidad y materiales

Revisa materiales, acabados, facilidad de limpieza y disponibilidad de recambios. En productos de uso frecuente, una construccion solida suele compensar mas que una lista larga de funciones secundarias.

### Tamano y espacio

Comprueba medidas, peso y espacio disponible en casa. Un producto demasiado grande o incomodo puede parecer mejor sobre el papel, pero resultar poco practico en el dia a dia.

### Facilidad de uso

Busca controles claros, mantenimiento sencillo e instrucciones faciles de seguir. Cuanto mas simple sea usarlo bien, mas probable es que le saques partido.

## Mejor opcion para {audience}

Para {audience}, conviene priorizar equilibrio entre precio, comodidad y durabilidad. No hace falta elegir el modelo mas caro si las funciones extra no aportan nada a tu caso.

Ventajas:

- Buena relacion entre precio y utilidad.
- Uso sencillo desde el primer dia.
- Adecuado para necesidades habituales.

Inconvenientes:

- Puede quedarse corto si buscas prestaciones avanzadas.
- No siempre incluye accesorios o extras.

{affiliate_block(
        f'Opcion equilibrada de {product}',
        'Coloca aqui una alternativa con buena relacion calidad-precio y valoraciones consistentes.',
    )}

## Mejor opcion economica

Si tu prioridad es gastar poco, busca un modelo basico pero fiable. Evita comprar solo por precio: una opcion muy barata puede salir cara si dura poco, funciona mal o resulta incomoda.

Una buena opcion economica deberia cumplir lo esencial sin prometer funciones que probablemente no vas a usar.

## Mejor opcion si quieres algo mas completo

Si vas a usarlo a menudo, puede tener sentido pagar algo mas por mejor construccion, accesorios utiles, mas potencia, mayor comodidad o limpieza mas facil.

Aqui conviene comparar no solo el precio inicial, sino tambien mantenimiento, garantia y disponibilidad de recambios.

{affiliate_block(
        f'Alternativa mas completa de {product}',
        'Usa este espacio para un modelo superior si quieres ofrecer una opcion de mayor presupuesto.',
    )}

## Errores comunes

- Comprar solo por precio.
- No revisar medidas, peso o compatibilidad.
- Fijarse en funciones llamativas que no vas a usar.
- No leer opiniones recientes de compradores.
- No comprobar condiciones de garantia y devolucion.

## Recomendacion final

Para la mayoria de usuarios, la mejor compra suele estar en el punto medio: un producto facil de usar, con buenas valoraciones, precio razonable y caracteristicas suficientes para el uso diario.

Cuando tengas tus enlaces de afiliado, sustituye los bloques marcados como "Enlace pendiente" por enlaces reales de Amazon u otra plataforma.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un articulo Hugo con formato de guia de compra para afiliados."
    )
    parser.add_argument("title", help="Titulo del articulo.")
    parser.add_argument(
        "--product",
        help="Producto principal. Si se omite, se deduce del titulo.",
    )
    parser.add_argument(
        "--audience",
        default="la mayoria de usuarios",
        help="Publico principal, por ejemplo: familias, principiantes, oficinas.",
    )
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        help="Fecha Hugo. Por defecto usa la fecha actual UTC.",
    )
    parser.add_argument(
        "--slug",
        help="Slug del archivo sin extension. Si se omite, se genera desde el titulo.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(POSTS_DIR),
        help="Carpeta de salida. Por defecto content/post.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribe el archivo si ya existe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    title = clean_title(args.title)
    product = args.product or infer_product(title)
    slug = args.slug or slugify(title)
    if not slug:
        print("No se pudo generar un slug valido.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    target = output_dir / f"{slug}.md"
    if target.exists() and not args.force:
        print(f"El archivo ya existe: {target}", file=sys.stderr)
        print("Usa --force si quieres sobrescribirlo.", file=sys.stderr)
        return 1

    article = build_article(title, args.date, product, args.audience)
    target.write_text(article, encoding="utf-8", newline="\n")
    print(f"Articulo creado: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
