"""Datos de demostración realistas (90 días de historial) para probar el sistema."""
import random
from datetime import date, timedelta

import db

PRODUCTS = [
    # código, nombre, categoría, unidad, stock inicial, mín, objetivo, costo, consumo diario aprox., proveedor
    ("P001", "Papel A4 75g", "Papelería", "paquete", 160, 30, 150, 35.0, 3.0, "Distribuidora Andina"),
    ("P002", "Bolígrafo azul", "Papelería", "unidad", 600, 80, 400, 2.5, 8.0, "Distribuidora Andina"),
    ("P003", "Tinta negra", "Impresión", "unidad", 60, 10, 40, 48.0, 0.7, "TecnoSuministros"),
    ("P004", "Carpeta archivadora", "Papelería", "unidad", 120, 15, 80, 12.0, 1.2, "Distribuidora Andina"),
    ("P005", "Tóner impresora", "Impresión", "unidad", 25, 5, 15, 180.0, 0.25, "TecnoSuministros"),
    ("P006", "Cinta adhesiva", "Materiales", "unidad", 90, 10, 50, 6.0, 0.8, "Ferretería Central"),
    ("P007", "Marcador permanente", "Papelería", "unidad", 200, 25, 100, 5.0, 2.0, "Distribuidora Andina"),
    ("P008", "Cuaderno universitario", "Papelería", "unidad", 150, 15, 80, 18.0, 1.5, "Distribuidora Andina"),
    ("P009", "Detergente industrial", "Limpieza", "litro", 80, 10, 50, 22.0, 0.9, "Ferretería Central"),
    ("P010", "Memoria USB 32GB", "Tecnología", "unidad", 40, 5, 25, 55.0, 0.2, "TecnoSuministros"),
    ("P011", "Caja de embalaje", "Materiales", "caja", 220, 30, 120, 4.5, 3.5, "Ferretería Central"),
    ("P012", "Grapas (caja)", "Papelería", "caja", 70, 8, 30, 7.0, 0.05, "Distribuidora Andina"),  # casi sin rotación
]
SUPPLIERS = [
    ("Distribuidora Andina", "Carlos Mamani", "70012345", "ventas@andina.example", 5),
    ("TecnoSuministros", "Lucía Rojas", "71234567", "contacto@tecnosum.example", 10),
    ("Ferretería Central", "Jorge Flores", "72345678", "pedidos@ferrecentral.example", 3),
]


def seed_demo(user_id=None, history_days=90, rng_seed=42):
    """Carga datos solo si no hay productos. Devuelve True si cargó."""
    if len(db.get_products(only_active=False)):
        return False
    rnd = random.Random(rng_seed)
    for s in SUPPLIERS:
        db.add_supplier(*s)
    sup = {r["name"]: int(r["id"]) for _, r in db.get_suppliers().iterrows()}
    cat = {r["name"]: int(r["id"]) for _, r in db.get_categories().iterrows()}
    start = date.today() - timedelta(days=history_days)
    ids = {}
    for code, name, c, unit, stock, mn, obj, cost, _, s in PRODUCTS:
        pid = db.add_product(code, name, cat[c], sup[s], unit, 0, mn, obj, cost,
                             ordering_cost=20.0, holding_rate=0.20, user_id=user_id)
        db.add_movement(pid, "Entrada", stock, cost, "Stock inicial", start, user_id)
        ids[code] = pid
    for offset in range(1, history_days + 1):
        day = start + timedelta(days=offset)
        if day.weekday() == 6:  # sin movimiento los domingos
            continue
        for code, _, _, _, _, mn, obj, cost, rate, _ in PRODUCTS:
            pid = ids[code]
            qty = max(0, round(rnd.gauss(rate * 1.17, rate * 0.6)))
            if qty:
                stock = float(db.query_df("SELECT stock FROM products WHERE id=?", (pid,)).iloc[0, 0])
                qty = min(qty, stock)
                if qty > 0:
                    db.add_movement(pid, "Salida", qty, cost, "Consumo interno", day, user_id)
            stock = float(db.query_df("SELECT stock FROM products WHERE id=?", (pid,)).iloc[0, 0])
            if stock <= mn:  # reposición automática simulada al llegar al mínimo
                db.add_movement(pid, "Entrada", obj - stock, cost, "Reposición de proveedor", day, user_id)
    # dejar algunos productos cerca/por debajo del mínimo para mostrar las alertas
    for code, qty in [("P003", None), ("P005", None)]:
        pid = ids[code]
        stock = float(db.query_df("SELECT stock FROM products WHERE id=?", (pid,)).iloc[0, 0])
        mn = [p[5] for p in PRODUCTS if p[0] == code][0]
        take = stock - mn
        if take > 0:
            db.add_movement(pid, "Salida", take, [p[7] for p in PRODUCTS if p[0] == code][0], "Consumo interno", date.today(), user_id)
    return True
