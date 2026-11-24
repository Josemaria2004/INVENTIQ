"""Capa de datos de INVENTIQ: esquema SQLite y operaciones (CRUD)."""
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("INVENTIQ_DB", APP_DIR / "inventiq.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('Administrador','Operario')),
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    contact TEXT,
    phone TEXT,
    email TEXT,
    lead_time_days INTEGER NOT NULL DEFAULT 7,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    supplier_id INTEGER,
    unit TEXT NOT NULL,
    stock REAL NOT NULL DEFAULT 0 CHECK(stock >= 0),
    min_stock REAL NOT NULL DEFAULT 0,
    target_stock REAL NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    ordering_cost REAL NOT NULL DEFAULT 20,
    holding_rate REAL NOT NULL DEFAULT 0.20,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(category_id) REFERENCES categories(id),
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
);
CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER,
    movement_type TEXT NOT NULL CHECK(movement_type IN ('Entrada','Salida')),
    quantity REAL NOT NULL CHECK(quantity > 0),
    unit_cost REAL NOT NULL DEFAULT 0,
    note TEXT,
    movement_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Pendiente' CHECK(status IN ('Pendiente','Recibida','Cancelada')),
    order_date TEXT NOT NULL,
    received_date TEXT,
    note TEXT,
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL CHECK(quantity > 0),
    unit_cost REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(order_id) REFERENCES purchase_orders(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mov_product ON movements(product_id);
CREATE INDEX IF NOT EXISTS idx_mov_date ON movements(movement_date);
"""

DEFAULT_CATEGORIES = ["Papelería", "Impresión", "Materiales", "Limpieza", "Tecnología", "Otro"]
UNITS = ["unidad", "paquete", "caja", "kg", "litro", "metro"]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def get_conn(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path=None):
    with get_conn(path) as conn:
        conn.executescript(SCHEMA)
        for c in DEFAULT_CATEGORIES:
            conn.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (c,))


def query_df(sql, params=(), path=None):
    conn = get_conn(path)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def log_action(user_id, action, detail=""):
    with get_conn() as conn:
        conn.execute("INSERT INTO audit_log(user_id,action,detail,created_at) VALUES(?,?,?,?)",
                     (user_id, action, detail, now_iso()))


# ---------- Categorías ----------
def get_categories():
    return query_df("SELECT * FROM categories ORDER BY name")


def add_category(name):
    name = name.strip()
    if not name:
        raise ValueError("El nombre de la categoría es obligatorio.")
    with get_conn() as conn:
        try:
            conn.execute("INSERT INTO categories(name) VALUES(?)", (name,))
        except sqlite3.IntegrityError:
            raise ValueError("Esa categoría ya existe.")


# ---------- Proveedores ----------
def get_suppliers(only_active=True):
    sql = "SELECT * FROM suppliers" + (" WHERE active=1" if only_active else "") + " ORDER BY name"
    return query_df(sql)


def add_supplier(name, contact, phone, email, lead_time_days):
    if not name.strip():
        raise ValueError("El nombre del proveedor es obligatorio.")
    with get_conn() as conn:
        try:
            conn.execute("""INSERT INTO suppliers(name,contact,phone,email,lead_time_days)
                            VALUES(?,?,?,?,?)""",
                         (name.strip(), contact, phone, email, int(lead_time_days)))
        except sqlite3.IntegrityError:
            raise ValueError("Ya existe un proveedor con ese nombre.")


def update_supplier(sid, name, contact, phone, email, lead_time_days, active):
    with get_conn() as conn:
        conn.execute("""UPDATE suppliers SET name=?,contact=?,phone=?,email=?,lead_time_days=?,active=?
                        WHERE id=?""", (name.strip(), contact, phone, email, int(lead_time_days),
                                        int(active), sid))


# ---------- Productos ----------
def get_products(only_active=True):
    sql = """
        SELECT p.*, c.name AS category, s.name AS supplier,
               COALESCE(s.lead_time_days, 7) AS lead_time_days
        FROM products p
        JOIN categories c ON c.id = p.category_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
    """
    if only_active:
        sql += " WHERE p.active = 1"
    sql += " ORDER BY p.name"
    return query_df(sql)


def add_product(code, name, category_id, supplier_id, unit, stock, min_stock, target_stock,
                cost, ordering_cost=20.0, holding_rate=0.20, user_id=None):
    if not code.strip() or not name.strip():
        raise ValueError("El código y el nombre son obligatorios.")
    if target_stock < min_stock:
        raise ValueError("El stock objetivo debe ser igual o mayor al stock mínimo.")
    with get_conn() as conn:
        try:
            cur = conn.execute("""
                INSERT INTO products(code,name,category_id,supplier_id,unit,stock,min_stock,
                                     target_stock,cost,ordering_cost,holding_rate,created_at)
                VALUES(?,?,?,?,?,0,?,?,?,?,?,?)
            """, (code.strip().upper(), name.strip(), category_id, supplier_id, unit, min_stock,
                  target_stock, cost, ordering_cost, holding_rate, now_iso()))
        except sqlite3.IntegrityError:
            raise ValueError("Ese código ya existe. Utiliza un código diferente.")
        pid = cur.lastrowid
    if stock and stock > 0:  # el stock inicial queda registrado como un movimiento
        add_movement(pid, "Entrada", stock, cost, "Stock inicial", date.today(), user_id)
    log_action(user_id, "PRODUCTO_NUEVO", f"{code.strip().upper()} - {name.strip()}")
    return pid


def update_product(pid, name, category_id, supplier_id, unit, min_stock, target_stock, cost,
                   ordering_cost, holding_rate, user_id=None):
    if target_stock < min_stock:
        raise ValueError("El stock objetivo debe ser igual o mayor al stock mínimo.")
    with get_conn() as conn:
        conn.execute("""
            UPDATE products SET name=?,category_id=?,supplier_id=?,unit=?,min_stock=?,
                target_stock=?,cost=?,ordering_cost=?,holding_rate=? WHERE id=?
        """, (name.strip(), category_id, supplier_id, unit, min_stock, target_stock, cost,
              ordering_cost, holding_rate, pid))
    log_action(user_id, "PRODUCTO_EDITADO", f"id={pid}")


def deactivate_product(pid, user_id=None):
    """Baja lógica: conserva el historial de movimientos."""
    with get_conn() as conn:
        conn.execute("UPDATE products SET active=0 WHERE id=?", (pid,))
    log_action(user_id, "PRODUCTO_DESACTIVADO", f"id={pid}")


def reactivate_product(pid, user_id=None):
    with get_conn() as conn:
        conn.execute("UPDATE products SET active=1 WHERE id=?", (pid,))
    log_action(user_id, "PRODUCTO_REACTIVADO", f"id={pid}")


# ---------- Movimientos ----------
def _apply_movement(conn, product_id, movement_type, quantity, unit_cost, note, movement_date, user_id):
    if quantity <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")
    row = conn.execute("SELECT stock, active FROM products WHERE id=?", (product_id,)).fetchone()
    if row is None:
        raise ValueError("Producto no encontrado.")
    if not row["active"]:
        raise ValueError("El producto está desactivado.")
    stock = float(row["stock"])
    if movement_type == "Salida" and quantity > stock:
        raise ValueError(f"Stock insuficiente. Disponible: {stock:g}")
    new_stock = stock + quantity if movement_type == "Entrada" else stock - quantity
    conn.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, product_id))
    if movement_type == "Entrada" and unit_cost > 0:  # costo actualizado por última compra
        conn.execute("UPDATE products SET cost=? WHERE id=?", (unit_cost, product_id))
    conn.execute("""
        INSERT INTO movements(product_id,user_id,movement_type,quantity,unit_cost,note,
                              movement_date,created_at) VALUES(?,?,?,?,?,?,?,?)
    """, (product_id, user_id, movement_type, quantity, unit_cost, note,
          movement_date.isoformat(), now_iso()))


def add_movement(product_id, movement_type, quantity, unit_cost, note, movement_date, user_id=None):
    """Registra el movimiento y actualiza el stock en una sola transacción."""
    with get_conn() as conn:
        _apply_movement(conn, product_id, movement_type, quantity, unit_cost, note,
                        movement_date, user_id)


def get_movements(start=None, end=None):
    sql = """
        SELECT m.id, m.movement_date AS fecha, p.code AS codigo, p.name AS producto,
               c.name AS categoria, p.unit AS unidad, m.movement_type AS tipo,
               m.quantity AS cantidad, m.unit_cost AS costo_unitario,
               (m.quantity*m.unit_cost) AS valor, m.note AS observacion,
               COALESCE(u.username,'-') AS usuario, m.product_id
        FROM movements m
        JOIN products p ON p.id = m.product_id
        JOIN categories c ON c.id = p.category_id
        LEFT JOIN users u ON u.id = m.user_id
    """
    params = []
    if start and end:
        sql += " WHERE date(m.movement_date) BETWEEN date(?) AND date(?)"
        params = [start.isoformat(), end.isoformat()]
    sql += " ORDER BY m.movement_date DESC, m.id DESC"
    return query_df(sql, params)


# ---------- Órdenes de compra ----------
def create_purchase_order(supplier_id, items, note="", user_id=None):
    """items: lista de (product_id, cantidad, costo_unitario)."""
    items = [i for i in items if i[1] and i[1] > 0]
    if not items:
        raise ValueError("La orden debe tener al menos un producto con cantidad mayor a cero.")
    with get_conn() as conn:
        cur = conn.execute("""INSERT INTO purchase_orders(supplier_id,user_id,order_date,note)
                              VALUES(?,?,?,?)""", (supplier_id, user_id, date.today().isoformat(), note))
        oid = cur.lastrowid
        conn.executemany("""INSERT INTO purchase_order_items(order_id,product_id,quantity,unit_cost)
                            VALUES(?,?,?,?)""", [(oid, p, q, c) for p, q, c in items])
    log_action(user_id, "ORDEN_CREADA", f"orden #{oid}")
    return oid


def get_purchase_orders():
    return query_df("""
        SELECT o.id, o.order_date AS fecha, s.name AS proveedor, o.status AS estado,
               COUNT(i.id) AS items, COALESCE(SUM(i.quantity*i.unit_cost),0) AS total,
               o.received_date AS recibida, o.note AS nota
        FROM purchase_orders o
        JOIN suppliers s ON s.id = o.supplier_id
        LEFT JOIN purchase_order_items i ON i.order_id = o.id
        GROUP BY o.id ORDER BY o.id DESC
    """)


def get_order_items(order_id):
    return query_df("""
        SELECT p.code AS codigo, p.name AS producto, i.quantity AS cantidad,
               i.unit_cost AS costo_unitario, (i.quantity*i.unit_cost) AS subtotal
        FROM purchase_order_items i JOIN products p ON p.id = i.product_id
        WHERE i.order_id = ?
    """, (order_id,))


def receive_purchase_order(order_id, user_id=None):
    """Marca la orden como recibida y genera las entradas de inventario (transacción única)."""
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM purchase_orders WHERE id=?", (order_id,)).fetchone()
        if order is None:
            raise ValueError("Orden no encontrada.")
        if order["status"] != "Pendiente":
            raise ValueError(f"La orden ya está {order['status'].lower()}.")
        items = conn.execute("SELECT product_id,quantity,unit_cost FROM purchase_order_items WHERE order_id=?",
                             (order_id,)).fetchall()
        for it in items:
            _apply_movement(conn, it["product_id"], "Entrada", it["quantity"], it["unit_cost"],
                            f"Recepción orden #{order_id}", date.today(), user_id)
        conn.execute("UPDATE purchase_orders SET status='Recibida', received_date=? WHERE id=?",
                     (date.today().isoformat(), order_id))
    log_action(user_id, "ORDEN_RECIBIDA", f"orden #{order_id}")


def cancel_purchase_order(order_id, user_id=None):
    with get_conn() as conn:
        cur = conn.execute("UPDATE purchase_orders SET status='Cancelada' WHERE id=? AND status='Pendiente'",
                           (order_id,))
        if cur.rowcount == 0:
            raise ValueError("Solo se pueden cancelar órdenes pendientes.")
    log_action(user_id, "ORDEN_CANCELADA", f"orden #{order_id}")


# ---------- Auditoría ----------
def get_audit_log(limit=200):
    return query_df("""
        SELECT a.created_at AS fecha, COALESCE(u.username,'-') AS usuario, a.action AS accion,
               a.detail AS detalle
        FROM audit_log a LEFT JOIN users u ON u.id = a.user_id
        ORDER BY a.id DESC LIMIT ?
    """, (limit,))
