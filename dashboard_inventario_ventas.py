#!/usr/bin/env python3
"""Dashboard local de inventario y ventas, sin dependencias externas.

Uso:
  python3 dashboard_inventario_ventas.py
  python3 dashboard_inventario_ventas.py --csv ventas.csv --output dashboard.html

CSV requerido: order_date,order_id,product,category,units,unit_price,unit_cost,stock
Las fechas deben usar YYYY-MM-DD. Cada fila es un producto vendido en una orden;
stock representa el stock actual de ese producto y se toma de su fila más reciente.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import webbrowser
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


SAMPLE_ROWS = [
    ("2026-01-05", "V-1001", "Laptop Pro 14", "Tecnología", 2, 1250, 880, 7),
    ("2026-01-08", "V-1002", "Mouse inalámbrico", "Accesorios", 8, 24, 10, 38),
    ("2026-01-14", "V-1003", "Monitor 27 pulgadas", "Tecnología", 3, 310, 205, 11),
    ("2026-01-20", "V-1004", "Teclado mecánico", "Accesorios", 5, 79, 36, 16),
    ("2026-02-02", "V-1005", "Laptop Pro 14", "Tecnología", 1, 1250, 880, 6),
    ("2026-02-06", "V-1006", "Silla ergonómica", "Oficina", 4, 245, 150, 9),
    ("2026-02-13", "V-1007", "Mouse inalámbrico", "Accesorios", 12, 24, 10, 33),
    ("2026-02-21", "V-1008", "Monitor 27 pulgadas", "Tecnología", 2, 310, 205, 10),
    ("2026-03-03", "V-1009", "Laptop Pro 14", "Tecnología", 3, 1250, 880, 4),
    ("2026-03-09", "V-1010", "Teclado mecánico", "Accesorios", 7, 79, 36, 12),
    ("2026-03-16", "V-1011", "Silla ergonómica", "Oficina", 2, 245, 150, 8),
    ("2026-03-25", "V-1012", "Audífonos Bluetooth", "Accesorios", 6, 95, 48, 21),
    ("2026-04-04", "V-1013", "Laptop Pro 14", "Tecnología", 2, 1250, 880, 5),
    ("2026-04-11", "V-1014", "Monitor 27 pulgadas", "Tecnología", 4, 310, 205, 8),
    ("2026-04-18", "V-1015", "Mouse inalámbrico", "Accesorios", 10, 24, 10, 29),
    ("2026-04-26", "V-1016", "Silla ergonómica", "Oficina", 3, 245, 150, 6),
    ("2026-05-02", "V-1017", "Laptop Pro 14", "Tecnología", 1, 1250, 880, 3),
    ("2026-05-10", "V-1018", "Teclado mecánico", "Accesorios", 9, 79, 36, 8),
    ("2026-05-17", "V-1019", "Audífonos Bluetooth", "Accesorios", 5, 95, 48, 17),
    ("2026-05-27", "V-1020", "Monitor 27 pulgadas", "Tecnología", 2, 310, 205, 7),
    ("2026-06-03", "V-1021", "Laptop Pro 14", "Tecnología", 2, 1250, 880, 2),
    ("2026-06-09", "V-1022", "Mouse inalámbrico", "Accesorios", 11, 24, 10, 18),
    ("2026-06-15", "V-1023", "Silla ergonómica", "Oficina", 2, 245, 150, 5),
    ("2026-06-23", "V-1024", "Audífonos Bluetooth", "Accesorios", 7, 95, 48, 13),
]
FIELDS = ("order_date", "order_id", "product", "category", "units", "unit_price", "unit_cost", "stock")
LOW_STOCK_THRESHOLD = 10


def sample_data() -> list[dict[str, Any]]:
    return [dict(zip(FIELDS, row)) for row in SAMPLE_ROWS]


def load_data(csv_path: str | None) -> list[dict[str, Any]]:
    if not csv_path:
        return sample_data()
    with open(csv_path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Faltan columnas requeridas en el CSV: " + ", ".join(sorted(missing)))
        rows = []
        for line_number, source in enumerate(reader, start=2):
            try:
                datetime.strptime(source["order_date"].strip(), "%Y-%m-%d")
                row = {
                    "order_date": source["order_date"].strip(),
                    "order_id": source["order_id"].strip(),
                    "product": source["product"].strip(),
                    "category": source["category"].strip(),
                    "units": int(source["units"]),
                    "unit_price": float(source["unit_price"]),
                    "unit_cost": float(source["unit_cost"]),
                    "stock": int(source["stock"]),
                }
                if row["units"] < 0 or row["unit_price"] < 0 or row["unit_cost"] < 0 or row["stock"] < 0:
                    raise ValueError("unidades, precios, costos y stock deben ser >= 0")
                rows.append(row)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Dato inválido en la fila {line_number}: {exc}") from exc
    if not rows:
        raise ValueError("El CSV no contiene registros.")
    return rows


def money(value: float) -> str:
    return "$" + f"{value:,.2f}"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def compute(data: list[dict[str, Any]]) -> dict[str, Any]:
    revenue = sum(r["units"] * r["unit_price"] for r in data)
    cogs = sum(r["units"] * r["unit_cost"] for r in data)
    profit = revenue - cogs
    orders = len({r["order_id"] for r in data})
    units = sum(r["units"] for r in data)
    inventory: dict[str, dict[str, Any]] = {}
    sales_month = defaultdict(float)
    category_sales = defaultdict(float)
    product_sales = defaultdict(float)
    for r in sorted(data, key=lambda x: x["order_date"]):
        product = r["product"]
        inventory[product] = {"product": product, "category": r["category"], "stock": r["stock"], "unit_cost": r["unit_cost"]}
        sales_month[r["order_date"][:7]] += r["units"] * r["unit_price"]
        category_sales[r["category"]] += r["units"] * r["unit_price"]
        product_sales[product] += r["units"] * r["unit_price"]
    inv_units = sum(p["stock"] for p in inventory.values())
    inv_value = sum(p["stock"] * p["unit_cost"] for p in inventory.values())
    low = sorted((p for p in inventory.values() if p["stock"] <= LOW_STOCK_THRESHOLD), key=lambda p: p["stock"])
    return {
        "revenue": revenue, "cogs": cogs, "profit": profit,
        "margin": (profit / revenue * 100) if revenue else 0,
        "orders": orders, "units_sold": units,
        "avg_order": revenue / orders if orders else 0,
        "inventory_units": inv_units, "inventory_value": inv_value,
        "low_stock": low, "inventory": sorted(inventory.values(), key=lambda p: p["stock"]),
        "months": dict(sorted(sales_month.items())),
        "categories": dict(sorted(category_sales.items(), key=lambda x: x[1], reverse=True)),
        "products": dict(sorted(product_sales.items(), key=lambda x: x[1], reverse=True)),
        "period_start": min(r["order_date"] for r in data),
        "period_end": max(r["order_date"] for r in data),
    }


def bar_chart(title: str, labels: list[str], values: list[float], color: str, fmt: str = "money") -> str:
    width, height = 720, 250
    left, right, top, bottom = 56, 18, 22, 48
    plot_w, plot_h = width - left - right, height - top - bottom
    maximum = max(values, default=0) or 1
    count = max(len(values), 1)
    slot = plot_w / count
    bar_w = min(46, slot * 0.62)
    parts = [f'<section class="chart"><h3>{esc(title)}</h3><svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">']
    for tick in range(5):
        y = top + plot_h * tick / 4
        val = maximum * (4 - tick) / 4
        label = money(val) if fmt == "money" else f"{val:.0f}"
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e8edf4"/><text x="{left-8}" y="{y+4:.1f}" text-anchor="end" class="axis">{esc(label)}</text>')
    for i, (label, value) in enumerate(zip(labels, values)):
        x = left + slot * i + (slot - bar_w) / 2
        bar_h = value / maximum * plot_h
        y = top + plot_h - bar_h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="5" fill="{color}"><title>{esc(label)}: {money(value)}</title></rect>')
        short = label if len(label) <= 12 else label[:11] + "…"
        parts.append(f'<text x="{x+bar_w/2:.1f}" y="{height-24}" text-anchor="middle" class="axis">{esc(short)}</text>')
    parts.append("</svg></section>")
    return "".join(parts)


def make_html(metrics: dict[str, Any], currency: str = "USD") -> str:
    # Los importes se presentan en USD por defecto; cambie el argumento --currency si corresponde.
    cards = [
        ("Ventas totales", money(metrics["revenue"]), "Ingresos brutos"),
        ("Ganancia bruta", money(metrics["profit"]), f"Margen bruto: {metrics['margin']:.1f}%"),
        ("Órdenes", f"{metrics['orders']:,}", f"Ticket promedio: {money(metrics['avg_order'])}"),
        ("Unidades vendidas", f"{metrics['units_sold']:,}", "Volumen del período"),
        ("Valor del inventario", money(metrics["inventory_value"]), f"{metrics['inventory_units']:,} unidades en stock"),
        ("Stock bajo", f"{len(metrics['low_stock'])}", f"Umbral: {LOW_STOCK_THRESHOLD} unidades o menos"),
    ]
    kpis = "".join(f'<article class="kpi"><span>{esc(title)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small></article>' for title, value, note in cards)
    charts = bar_chart("Ventas por mes", list(metrics["months"]), list(metrics["months"].values()), "#3457d5")
    charts += bar_chart("Ventas por categoría", list(metrics["categories"]), list(metrics["categories"].values()), "#16a085")
    top_products = dict(list(metrics["products"].items())[:6])
    charts += bar_chart("Productos con más ventas", list(top_products), list(top_products.values()), "#f39c38")
    stock_rows = "".join(
        f'<tr><td>{esc(p["product"])}</td><td>{esc(p["category"])}</td><td>{p["stock"]}</td><td>{money(p["unit_cost"])}</td><td>{money(p["stock"]*p["unit_cost"])}</td><td><span class="pill {"alert" if p["stock"] <= LOW_STOCK_THRESHOLD else "ok"}">{"Reponer" if p["stock"] <= LOW_STOCK_THRESHOLD else "Disponible"}</span></td></tr>'
        for p in metrics["inventory"]
    )
    low_names = ", ".join(p["product"] for p in metrics["low_stock"]) or "No hay productos bajo el umbral."
    data_json = json.dumps({"period": [metrics["period_start"], metrics["period_end"]]}, ensure_ascii=False)
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard de inventario y ventas</title>
<style>
:root{{--ink:#17233c;--muted:#68758b;--bg:#f4f7fb;--card:#fff;--line:#e5eaf1;--blue:#3457d5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1250px;margin:0 auto;padding:32px 22px 50px}}header{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:24px}}
h1{{font-size:clamp(25px,4vw,36px);line-height:1.15;margin:0 0 8px}}.sub{{color:var(--muted);margin:0}}.period{{color:var(--muted);font-size:13px;text-align:right}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.kpi,.chart,.panel{{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 4px 18px #1d35570a}}
.kpi{{padding:19px 20px;min-height:126px;display:flex;flex-direction:column;gap:4px}}.kpi span,.kpi small{{color:var(--muted)}}.kpi strong{{font-size:26px;letter-spacing:-.5px}}.kpi small{{font-size:12px}}
.charts{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:18px}}.chart{{padding:18px 18px 8px;overflow:hidden}}.chart h3{{font-size:16px;margin:0 0 8px}}.chart svg{{display:block;width:100%;height:auto;overflow:visible}}.axis{{font-size:11px;fill:#78849a}}
.panel{{padding:20px;margin-top:18px}}.panel h2{{font-size:18px;margin:0 0 5px}}.hint{{color:var(--muted);font-size:13px;margin:0 0 14px}}.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:680px;font-size:14px}}th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}}.pill{{display:inline-block;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:650}}.alert{{color:#a33b22;background:#fff0e9}}.ok{{color:#15704e;background:#e6f7ef}}.notice{{border-left:4px solid #f0a73b;padding:11px 14px;background:#fff9ec;border-radius:8px;margin-top:14px;color:#654d20;font-size:14px}}footer{{color:var(--muted);font-size:12px;margin-top:18px}}
@media(max-width:850px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.charts{{grid-template-columns:1fr}}header{{align-items:flex-start;flex-direction:column}}.period{{text-align:left}}}}@media(max-width:520px){{main{{padding:22px 14px}}.grid{{grid-template-columns:1fr 1fr;gap:10px}}.kpi{{padding:14px;min-height:116px}}.kpi strong{{font-size:21px}}}}
</style></head><body><main>
<header><div><h1>Inventario y ventas</h1><p class="sub">Panel de control para seguimiento comercial y reposición</p></div><div class="period">Período analizado<br><strong>{esc(metrics['period_start'])} — {esc(metrics['period_end'])}</strong><br>Moneda: {esc(currency)}</div></header>
<section class="grid" aria-label="Indicadores clave">{kpis}</section>
<section class="charts" aria-label="Gráficos de ventas">{charts}</section>
<section class="panel"><h2>Estado del inventario</h2><p class="hint">Valoración calculada a costo unitario. Se usa el stock de la fila más reciente de cada producto.</p><div class="table-wrap"><table><thead><tr><th>Producto</th><th>Categoría</th><th>Stock</th><th>Costo unitario</th><th>Valor en stock</th><th>Estado</th></tr></thead><tbody>{stock_rows}</tbody></table></div>
<div class="notice"><strong>Atención de reposición:</strong> {esc(low_names)}{f' — {len(metrics["low_stock"])} producto(s) en o bajo el umbral.' if metrics['low_stock'] else ''}</div></section>
<footer>Generado con Python estándar, sin paquetes externos. Fuente: datos de demostración o archivo CSV local. Verifica que tu archivo tenga datos actualizados antes de usarlo para decisiones operativas.</footer>
<script type="application/json" id="dashboard-meta">{data_json}</script></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un dashboard HTML autónomo de inventario y ventas.")
    parser.add_argument("--csv", help="Ruta al CSV con las columnas requeridas; si se omite usa datos de ejemplo.")
    parser.add_argument("--output", default="dashboard_inventario_ventas.html", help="Archivo HTML de salida (por defecto: dashboard_inventario_ventas.html).")
    parser.add_argument("--currency", default="USD", help="Código o símbolo de moneda mostrado en el panel (por defecto: USD).")
    parser.add_argument("--no-open", action="store_true", help="No abrir el panel en el navegador automáticamente.")
    args = parser.parse_args()
    data = load_data(args.csv)
    output = Path(args.output).expanduser().resolve()
    output.write_text(make_html(compute(data), args.currency), encoding="utf-8")
    print(f"Dashboard creado: {output}")
    if not args.no_open:
        webbrowser.open(output.as_uri())


if __name__ == "__main__":
    main()
