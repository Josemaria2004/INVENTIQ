"""INVENTIQ — Sistema inteligente de gestión y control de inventarios (interfaz Streamlit)."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import analytics
import auth
import db
import seed

st.set_page_config(page_title="INVENTIQ | Gestión de Inventarios", page_icon="📦", layout="wide")
db.init_db()
auth.ensure_default_admin()

st.markdown("""
<style>
    .stApp { background-color: #f5f7f6; }
    section[data-testid="stSidebar"] { background: #173d32; }
    section[data-testid="stSidebar"] * { color: #f3f8f4 !important; }
    .brand { font-size: 30px; font-weight: 800; letter-spacing: 1px; color: #173d32; }
    .brand-sub { color: #60746b; font-size: 14px; margin-top: -8px; }
    div[data-testid="stMetric"] { background: white; padding: 16px; border-radius: 12px; border: 1px solid #e3e9e5; }
</style>
""", unsafe_allow_html=True)


def fmt_bs(x):
    return f"Bs {x:,.2f}"


def flash():
    """Muestra un mensaje guardado antes de un st.rerun()."""
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg)


def done(msg):
    st.session_state["flash"] = msg
    st.rerun()


def prod_label(products):
    return lambda pid: (f'{products.loc[products["id"] == pid, "code"].iloc[0]} — '
                        f'{products.loc[products["id"] == pid, "name"].iloc[0]}')


# ======================= LOGIN =======================
if "user" not in st.session_state:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div class="brand">📦 INVENTIQ</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-sub">Sistema inteligente de gestión y control de inventarios</div>',
                    unsafe_allow_html=True)
        st.write("")
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", type="primary", use_container_width=True):
                user = auth.authenticate(u, p)
                if user:
                    st.session_state["user"] = user
                    db.log_action(user["id"], "LOGIN", user["username"])
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
        st.caption("Primer ingreso: usuario `admin` · contraseña `admin123` (cámbiala en el menú Usuarios).")
    st.stop()

user = st.session_state["user"]
is_admin = user["role"] == "Administrador"

# ======================= SIDEBAR =======================
pages = ["Dashboard", "Productos", "Movimientos", "Alertas y reposición", "Análisis de inventario",
         "Proveedores", "Órdenes de compra", "Reportes"]
if is_admin:
    pages += ["Usuarios", "Auditoría"]
with st.sidebar:
    st.markdown("## 📦 INVENTIQ")
    st.caption(f"👤 {user['full_name']} · {user['role']}")
    page = st.radio("MENÚ PRINCIPAL", pages)
    st.divider()
    st.caption("Python + Streamlit + SQLite")
    if is_admin and st.button("🧪 Cargar datos de demostración", use_container_width=True):
        with st.spinner("Generando 90 días de historial..."):
            ok = seed.seed_demo(user["id"])
        if ok:
            done("Datos de demostración cargados.")
        else:
            st.warning("Ya existen productos; no se duplicaron datos.")
    if st.button("Cerrar sesión", use_container_width=True):
        db.log_action(user["id"], "LOGOUT", user["username"])
        del st.session_state["user"]
        st.rerun()

st.markdown('<div class="brand">INVENTIQ</div>', unsafe_allow_html=True)
st.markdown('<div class="brand-sub">Sistema inteligente de gestión y control de inventarios</div>',
            unsafe_allow_html=True)
flash()

products = db.get_products()
categories = db.get_categories()
suppliers = db.get_suppliers()

# ======================= DASHBOARD =======================
if page == "Dashboard":
    st.title("Panel de control")
    if products.empty:
        st.info("Aún no hay productos. Registra productos o carga datos de demostración desde el menú lateral.")
    else:
        an = analytics.inventory_analysis()
        to_reorder = an[an["estado"].isin(["Agotado", "Crítico", "Reponer"])]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Productos activos", len(an))
        c2.metric("Unidades en stock", f"{an['stock'].sum():,.0f}")
        c3.metric("Valor del inventario", fmt_bs(an["valor_stock"].sum()))
        c4.metric("Por reponer", len(to_reorder))
        rot = an["value_out"].sum() / an["valor_stock"].sum() if an["valor_stock"].sum() else 0
        c5.metric("Rotación (90 días)", f"{rot:.2f}x")

        left, right = st.columns(2)
        with left:
            st.subheader("Valor del inventario por categoría")
            st.bar_chart(an.groupby("category")["valor_stock"].sum())
        with right:
            st.subheader("Valor por clase ABC")
            st.bar_chart(an.groupby("clase_abc")["valor_stock"].sum())

        st.subheader("Entradas y salidas (últimos 60 días)")
        flow = analytics.daily_flow(60)
        if flow.empty:
            st.info("Sin movimientos en el período.")
        else:
            st.line_chart(flow)

        st.subheader("Productos que requieren atención")
        if to_reorder.empty:
            st.success("Todo el inventario está sobre su punto de reorden.")
        else:
            st.dataframe(to_reorder[["code", "name", "stock", "min_stock", "punto_reorden", "estado"]].rename(
                columns={"code": "Código", "name": "Producto", "stock": "Stock", "min_stock": "Mínimo",
                         "punto_reorden": "Punto de reorden", "estado": "Estado"}).round(1),
                hide_index=True, use_container_width=True)

# ======================= PRODUCTOS =======================
elif page == "Productos":
    st.title("Gestión de productos")
    tabs = ["📋 Catálogo"] + (["➕ Registrar", "✏️ Editar / desactivar", "🗂️ Categorías"] if is_admin else [])
    tab_objs = st.tabs(tabs)

    with tab_objs[0]:
        search = st.text_input("Buscar por código, nombre, categoría o proveedor")
        show_inactive = st.checkbox("Mostrar también productos desactivados")
        allp = db.get_products(only_active=not show_inactive)
        if search:
            mask = allp[["code", "name", "category", "supplier"]].astype(str).apply(
                lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
            allp = allp[mask]
        if allp.empty:
            st.info("No hay productos para mostrar.")
        else:
            allp = allp.assign(valor=allp["stock"] * allp["cost"])
            view = allp[["code", "name", "category", "supplier", "unit", "stock", "min_stock",
                         "target_stock", "cost", "valor", "active"]].rename(columns={
                "code": "Código", "name": "Producto", "category": "Categoría", "supplier": "Proveedor",
                "unit": "Unidad", "stock": "Existencia", "min_stock": "Mínimo", "target_stock": "Objetivo",
                "cost": "Costo unit. (Bs)", "valor": "Valor (Bs)", "active": "Activo"})
            st.dataframe(view, hide_index=True, use_container_width=True)
            st.download_button("⬇️ Descargar catálogo CSV", view.to_csv(index=False).encode("utf-8-sig"),
                               "inventiq_catalogo.csv", "text/csv")

    if is_admin:
        with tab_objs[1]:
            with st.form("add_product", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                code = c1.text_input("Código *", placeholder="Ej. P013")
                name = c2.text_input("Nombre *")
                cat_id = c3.selectbox("Categoría", categories["id"].tolist(),
                                      format_func=lambda i: categories.loc[categories["id"] == i, "name"].iloc[0])
                c4, c5, c6, c7 = st.columns(4)
                unit = c4.selectbox("Unidad", db.UNITS)
                stock = c5.number_input("Stock inicial", min_value=0.0, step=1.0)
                mn = c6.number_input("Stock mínimo", min_value=0.0, step=1.0)
                tg = c7.number_input("Stock objetivo", min_value=0.0, step=1.0)
                c8, c9, c10 = st.columns(3)
                cost = c8.number_input("Costo unitario (Bs)", min_value=0.0, step=0.5, format="%.2f")
                oc = c9.number_input("Costo de emitir un pedido (Bs)", min_value=0.0, value=20.0, step=1.0)
                hr = c10.number_input("Costo de mantener (% anual)", min_value=0.0, max_value=100.0, value=20.0) / 100
                sup_opts = [None] + suppliers["id"].tolist()
                sup_id = st.selectbox("Proveedor", sup_opts, format_func=lambda i: "— Sin proveedor —" if i is None
                                      else suppliers.loc[suppliers["id"] == i, "name"].iloc[0])
                if st.form_submit_button("Guardar producto", type="primary"):
                    try:
                        db.add_product(code, name, cat_id, sup_id, unit, stock, mn, tg, cost, oc, hr, user["id"])
                        done("Producto registrado correctamente.")
                    except ValueError as e:
                        st.error(str(e))

        with tab_objs[2]:
            allp = db.get_products(only_active=False)
            if allp.empty:
                st.info("Primero registra productos.")
            else:
                chosen = st.selectbox("Seleccionar producto", allp["id"].tolist(), format_func=prod_label(allp))
                it = allp[allp["id"] == chosen].iloc[0]
                cat_ids = categories["id"].tolist()
                sup_opts = [None] + suppliers["id"].tolist()
                with st.form("edit_product"):
                    en = st.text_input("Nombre", value=it["name"])
                    ec = st.selectbox("Categoría", cat_ids, index=cat_ids.index(int(it["category_id"])),
                                      format_func=lambda i: categories.loc[categories["id"] == i, "name"].iloc[0])
                    cur_sup = None if pd.isna(it["supplier_id"]) else int(it["supplier_id"])
                    es = st.selectbox("Proveedor", sup_opts, index=sup_opts.index(cur_sup) if cur_sup in sup_opts else 0,
                                      format_func=lambda i: "— Sin proveedor —" if i is None
                                      else suppliers.loc[suppliers["id"] == i, "name"].iloc[0])
                    eu = st.selectbox("Unidad", db.UNITS, index=db.UNITS.index(it["unit"]) if it["unit"] in db.UNITS else 0)
                    e1, e2, e3 = st.columns(3)
                    emn = e1.number_input("Stock mínimo", min_value=0.0, value=float(it["min_stock"]), step=1.0)
                    etg = e2.number_input("Stock objetivo", min_value=0.0, value=float(it["target_stock"]), step=1.0)
                    ecost = e3.number_input("Costo unitario (Bs)", min_value=0.0, value=float(it["cost"]), step=0.5, format="%.2f")
                    e4, e5 = st.columns(2)
                    eoc = e4.number_input("Costo de emitir un pedido (Bs)", min_value=0.0, value=float(it["ordering_cost"]))
                    ehr = e5.number_input("Costo de mantener (% anual)", min_value=0.0, max_value=100.0,
                                          value=float(it["holding_rate"]) * 100) / 100
                    if st.form_submit_button("Guardar cambios"):
                        try:
                            db.update_product(chosen, en, ec, es, eu, emn, etg, ecost, eoc, ehr, user["id"])
                            done("Producto actualizado.")
                        except ValueError as e:
                            st.error(str(e))
                if it["active"]:
                    if st.button("🚫 Desactivar producto (conserva el historial)"):
                        db.deactivate_product(chosen, user["id"])
                        done("Producto desactivado.")
                else:
                    if st.button("♻️ Reactivar producto"):
                        db.reactivate_product(chosen, user["id"])
                        done("Producto reactivado.")

        with tab_objs[3]:
            st.dataframe(categories.rename(columns={"id": "ID", "name": "Categoría"}), hide_index=True)
            with st.form("add_cat", clear_on_submit=True):
                nc = st.text_input("Nueva categoría")
                if st.form_submit_button("Agregar"):
                    try:
                        db.add_category(nc)
                        done("Categoría agregada.")
                    except ValueError as e:
                        st.error(str(e))

# ======================= MOVIMIENTOS =======================
elif page == "Movimientos":
    st.title("Registro de movimientos")
    if products.empty:
        st.warning("Registra productos antes de ingresar movimientos.")
    else:
        pid = st.selectbox("Producto", products["id"].tolist(),
                           format_func=lambda i: f'{prod_label(products)(i)} (stock: '
                                                 f'{products.loc[products["id"] == i, "stock"].iloc[0]:g})')
        sel = products[products["id"] == pid].iloc[0]
        with st.form("movement", clear_on_submit=True):
            mtype = st.radio("Tipo de movimiento", ["Entrada", "Salida"], horizontal=True)
            qty = st.number_input("Cantidad", min_value=0.0, step=1.0)
            ucost = st.number_input("Costo unitario (Bs)", min_value=0.0, value=float(sel["cost"]), step=0.5, format="%.2f")
            mdate = st.date_input("Fecha", value=date.today(), max_value=date.today())
            note = st.text_input("Observación")
            if st.form_submit_button("Registrar movimiento", type="primary"):
                try:
                    db.add_movement(int(pid), mtype, qty, ucost, note, mdate, user["id"])
                    done(f"{mtype} registrada. Stock actualizado.")
                except ValueError as e:
                    st.error(str(e))
    st.subheader("Historial")
    mv = db.get_movements().drop(columns=["product_id"])
    if mv.empty:
        st.info("No hay movimientos registrados.")
    else:
        st.dataframe(mv.head(500), hide_index=True, use_container_width=True)
        st.download_button("⬇️ Descargar movimientos CSV", mv.to_csv(index=False).encode("utf-8-sig"),
                           "inventiq_movimientos.csv", "text/csv")

# ======================= ALERTAS =======================
elif page == "Alertas y reposición":
    st.title("Alertas inteligentes de reposición")
    if products.empty:
        st.info("No hay productos registrados.")
    else:
        an = analytics.inventory_analysis()
        alerts = an[an["estado"].isin(["Agotado", "Crítico", "Reponer"])].copy()
        if alerts.empty:
            st.success("Todos los productos están sobre su punto de reorden.")
        else:
            st.warning(f"{len(alerts)} producto(s) necesitan reposición.")
            alerts["cantidad_sugerida"] = alerts.apply(analytics.suggested_order_qty, axis=1)
            alerts["costo_reposicion"] = alerts["cantidad_sugerida"] * alerts["cost"]
            st.dataframe(alerts[["code", "name", "supplier", "stock", "min_stock", "punto_reorden", "dias_cobertura",
                                 "estado", "cantidad_sugerida", "costo_reposicion"]].rename(columns={
                "code": "Código", "name": "Producto", "supplier": "Proveedor", "stock": "Stock",
                "min_stock": "Mínimo", "punto_reorden": "Pto. reorden", "dias_cobertura": "Días de cobertura",
                "estado": "Estado", "cantidad_sugerida": "Cantidad sugerida",
                "costo_reposicion": "Costo estimado (Bs)"}).replace(float("inf"), None).round(1),
                hide_index=True, use_container_width=True)
            st.metric("Costo estimado de reposición", fmt_bs(alerts["costo_reposicion"].sum()))
            st.caption("Estados: Agotado (stock 0) · Crítico (≤ mínimo) · Reponer (≤ punto de reorden = demanda durante "
                       "el plazo del proveedor + stock de seguridad). Puedes crear la orden en «Órdenes de compra».")
        st.subheader("Productos sin movimiento en 30 días")
        stale = db.query_df("""
            SELECT p.code AS Código, p.name AS Producto, p.stock AS Stock,
                   MAX(CASE WHEN m.movement_type='Salida' THEN m.movement_date END) AS "Última salida"
            FROM products p LEFT JOIN movements m ON m.product_id = p.id
            WHERE p.active = 1 GROUP BY p.id
            HAVING "Última salida" IS NULL OR date("Última salida") < date(?)
        """, ((date.today() - timedelta(days=30)).isoformat(),))
        if stale.empty:
            st.info("Todos los productos tuvieron salidas en los últimos 30 días.")
        else:
            st.dataframe(stale, hide_index=True, use_container_width=True)

# ======================= ANÁLISIS =======================
elif page == "Análisis de inventario":
    st.title("Análisis de inventario")
    if products.empty:
        st.info("No hay productos registrados.")
    else:
        days = st.slider("Ventana de análisis (días)", 30, 365, 90, step=30)
        an = analytics.inventory_analysis(days)
        t1, t2, t3 = st.tabs(["🅰️ Clasificación ABC", "🔁 Rotación y cobertura", "📐 Punto de reorden y EOQ"])
        with t1:
            st.caption("Clasifica según el valor consumido: A ≈ 80 % del valor, B ≈ 15 %, C ≈ 5 %. "
                       "Los productos A merecen el control más estricto.")
            abc = an.sort_values("value_out", ascending=False)
            st.bar_chart(abc.set_index("name")["value_out"])
            summary = an.groupby("clase_abc").agg(Productos=("id", "count"), Valor_consumido=("value_out", "sum"),
                                                  Valor_en_stock=("valor_stock", "sum")).round(2)
            st.dataframe(summary, use_container_width=True)
            st.dataframe(abc[["code", "name", "clase_abc", "qty_out", "value_out"]].rename(columns={
                "code": "Código", "name": "Producto", "clase_abc": "Clase", "qty_out": "Unidades consumidas",
                "value_out": "Valor consumido (Bs)"}).round(2), hide_index=True, use_container_width=True)
        with t2:
            st.caption("Rotación = valor consumido ÷ valor actual en stock. Cobertura = stock ÷ consumo diario.")
            r = an[["code", "name", "stock", "consumo_diario", "dias_cobertura", "rotacion", "estado"]].rename(columns={
                "code": "Código", "name": "Producto", "stock": "Stock", "consumo_diario": "Consumo diario",
                "dias_cobertura": "Días de cobertura", "rotacion": "Rotación", "estado": "Estado"})
            st.dataframe(r.replace(float("inf"), None).round(2), hide_index=True, use_container_width=True)
            st.bar_chart(an.set_index("name")["rotacion"])
        with t3:
            st.caption("Punto de reorden = consumo diario × plazo del proveedor + stock de seguridad (nivel de servicio 95 %). "
                       "EOQ = √(2·D·S/H), con D demanda anual, S costo por pedido y H costo anual de mantener una unidad.")
            r = an[["code", "name", "lead_time_days", "consumo_diario", "stock_seguridad", "punto_reorden", "eoq"]].rename(columns={
                "code": "Código", "name": "Producto", "lead_time_days": "Plazo (días)", "consumo_diario": "Consumo diario",
                "stock_seguridad": "Stock de seguridad", "punto_reorden": "Punto de reorden", "eoq": "Lote económico (EOQ)"})
            st.dataframe(r.round(1), hide_index=True, use_container_width=True)
        st.download_button("⬇️ Descargar análisis completo CSV",
                           an.replace(float("inf"), None).to_csv(index=False).encode("utf-8-sig"),
                           "inventiq_analisis.csv", "text/csv")

# ======================= PROVEEDORES =======================
elif page == "Proveedores":
    st.title("Proveedores")
    allsup = db.get_suppliers(only_active=False)
    if not allsup.empty:
        st.dataframe(allsup.rename(columns={"id": "ID", "name": "Proveedor", "contact": "Contacto", "phone": "Teléfono",
                                            "email": "Correo", "lead_time_days": "Plazo (días)", "active": "Activo"}),
                     hide_index=True, use_container_width=True)
    if is_admin:
        a, b = st.tabs(["➕ Nuevo proveedor", "✏️ Editar"])
        with a:
            with st.form("add_sup", clear_on_submit=True):
                n = st.text_input("Nombre *")
                c1, c2, c3 = st.columns(3)
                ct, ph, em = c1.text_input("Contacto"), c2.text_input("Teléfono"), c3.text_input("Correo")
                lt = st.number_input("Plazo de entrega (días)", min_value=1, value=7, step=1)
                if st.form_submit_button("Guardar proveedor", type="primary"):
                    try:
                        db.add_supplier(n, ct, ph, em, lt)
                        done("Proveedor registrado.")
                    except ValueError as e:
                        st.error(str(e))
        with b:
            if allsup.empty:
                st.info("Aún no hay proveedores.")
            else:
                sid = st.selectbox("Proveedor", allsup["id"].tolist(),
                                   format_func=lambda i: allsup.loc[allsup["id"] == i, "name"].iloc[0])
                s = allsup[allsup["id"] == sid].iloc[0]
                with st.form("edit_sup"):
                    n = st.text_input("Nombre", value=s["name"])
                    c1, c2, c3 = st.columns(3)
                    ct = c1.text_input("Contacto", value=s["contact"] or "")
                    ph = c2.text_input("Teléfono", value=s["phone"] or "")
                    em = c3.text_input("Correo", value=s["email"] or "")
                    lt = st.number_input("Plazo de entrega (días)", min_value=1, value=int(s["lead_time_days"]), step=1)
                    ac = st.checkbox("Activo", value=bool(s["active"]))
                    if st.form_submit_button("Guardar cambios"):
                        db.update_supplier(int(sid), n, ct, ph, em, lt, ac)
                        done("Proveedor actualizado.")

# ======================= ÓRDENES DE COMPRA =======================
elif page == "Órdenes de compra":
    st.title("Órdenes de compra")
    tab_new, tab_list = st.tabs(["🛒 Nueva orden", "📑 Órdenes"])
    with tab_new:
        if suppliers.empty or products.empty:
            st.info("Necesitas al menos un proveedor y un producto.")
        else:
            sid = st.selectbox("Proveedor", suppliers["id"].tolist(),
                               format_func=lambda i: suppliers.loc[suppliers["id"] == i, "name"].iloc[0])
            sp = products[products["supplier_id"] == sid]
            if sp.empty:
                st.info("Este proveedor no tiene productos asignados. Asígnalos en Productos → Editar.")
            else:
                an = analytics.inventory_analysis()
                an = an[an["supplier_id"] == sid].copy()
                an["cantidad"] = an.apply(analytics.suggested_order_qty, axis=1)
                st.caption("Las cantidades se sugieren automáticamente; edítalas antes de crear la orden.")
                edited = st.data_editor(
                    an[["id", "code", "name", "stock", "estado", "cantidad", "cost"]].rename(columns={
                        "id": "ID", "code": "Código", "name": "Producto", "stock": "Stock", "estado": "Estado",
                        "cantidad": "Cantidad a pedir", "cost": "Costo unit. (Bs)"}),
                    hide_index=True, use_container_width=True,
                    disabled=["ID", "Código", "Producto", "Stock", "Estado"], key=f"po_{sid}")
                note = st.text_input("Nota de la orden")
                total = float((edited["Cantidad a pedir"] * edited["Costo unit. (Bs)"]).sum())
                st.metric("Total estimado", fmt_bs(total))
                if st.button("Crear orden de compra", type="primary"):
                    items = [(int(r["ID"]), float(r["Cantidad a pedir"]), float(r["Costo unit. (Bs)"]))
                             for _, r in edited.iterrows()]
                    try:
                        oid = db.create_purchase_order(int(sid), items, note, user["id"])
                        done(f"Orden #{oid} creada.")
                    except ValueError as e:
                        st.error(str(e))
    with tab_list:
        orders = db.get_purchase_orders()
        if orders.empty:
            st.info("Todavía no hay órdenes.")
        else:
            st.dataframe(orders, hide_index=True, use_container_width=True)
            oid = st.selectbox("Ver detalle de la orden", orders["id"].tolist())
            st.dataframe(db.get_order_items(int(oid)), hide_index=True, use_container_width=True)
            status = orders.loc[orders["id"] == oid, "estado"].iloc[0]
            if status == "Pendiente":
                c1, c2 = st.columns(2)
                if c1.button("✅ Marcar como recibida (genera entradas)", type="primary"):
                    try:
                        db.receive_purchase_order(int(oid), user["id"])
                        done(f"Orden #{oid} recibida. Stock actualizado.")
                    except ValueError as e:
                        st.error(str(e))
                if is_admin and c2.button("✖️ Cancelar orden"):
                    try:
                        db.cancel_purchase_order(int(oid), user["id"])
                        done(f"Orden #{oid} cancelada.")
                    except ValueError as e:
                        st.error(str(e))

# ======================= REPORTES =======================
elif page == "Reportes":
    st.title("Reportes por período")
    c1, c2 = st.columns(2)
    start = c1.date_input("Fecha inicial", value=date.today() - timedelta(days=30), key="rs")
    end = c2.date_input("Fecha final", value=date.today(), key="re")
    if start > end:
        st.error("La fecha inicial no puede ser posterior a la final.")
    else:
        rep = db.get_movements(start, end)
        if rep.empty:
            st.info("No se encontraron movimientos en este período.")
        else:
            ent, sal = rep[rep["tipo"] == "Entrada"], rep[rep["tipo"] == "Salida"]
            a, b, c, d = st.columns(4)
            a.metric("Movimientos", len(rep))
            b.metric("Unidades que entraron", f"{ent['cantidad'].sum():,.0f}")
            c.metric("Unidades que salieron", f"{sal['cantidad'].sum():,.0f}")
            d.metric("Valor consumido", fmt_bs(sal["valor"].sum()))
            st.subheader("Consumo por producto (solo salidas)")
            if sal.empty:
                st.info("No hubo salidas en el período.")
            else:
                rank = sal.groupby("producto")["cantidad"].sum().sort_values(ascending=False).head(10)
                st.bar_chart(rank)
                st.subheader("Consumo por categoría (valor)")
                st.bar_chart(sal.groupby("categoria")["valor"].sum())
            st.subheader("Detalle")
            det = rep.drop(columns=["product_id"])
            st.dataframe(det, hide_index=True, use_container_width=True)
            st.download_button("⬇️ Descargar reporte CSV", det.to_csv(index=False).encode("utf-8-sig"),
                               f"inventiq_reporte_{start}_{end}.csv", "text/csv")

# ======================= USUARIOS =======================
elif page == "Usuarios" and is_admin:
    st.title("Usuarios y permisos")
    st.caption("Administrador: acceso total. Operario: consulta, registra movimientos y recibe órdenes.")
    users = auth.list_users()
    st.dataframe(users.rename(columns={"username": "Usuario", "full_name": "Nombre", "role": "Rol",
                                       "active": "Activo", "created_at": "Creado"}).drop(columns=["id"]),
                 hide_index=True, use_container_width=True)
    a, b = st.tabs(["➕ Nuevo usuario", "🔑 Contraseña / estado"])
    with a:
        with st.form("new_user", clear_on_submit=True):
            c1, c2 = st.columns(2)
            un, fn = c1.text_input("Usuario *"), c2.text_input("Nombre completo *")
            c3, c4 = st.columns(2)
            pw = c3.text_input("Contraseña * (mín. 6)", type="password")
            role = c4.selectbox("Rol", ["Operario", "Administrador"])
            if st.form_submit_button("Crear usuario", type="primary"):
                try:
                    auth.create_user(un, fn, pw, role)
                    db.log_action(user["id"], "USUARIO_CREADO", un)
                    done("Usuario creado.")
                except ValueError as e:
                    st.error(str(e))
    with b:
        uid = st.selectbox("Usuario", users["id"].tolist(),
                           format_func=lambda i: users.loc[users["id"] == i, "username"].iloc[0])
        with st.form("chg_pw", clear_on_submit=True):
            npw = st.text_input("Nueva contraseña", type="password")
            if st.form_submit_button("Cambiar contraseña"):
                try:
                    auth.change_password(int(uid), npw)
                    db.log_action(user["id"], "PASSWORD_CAMBIADA", f"id={uid}")
                    done("Contraseña actualizada.")
                except ValueError as e:
                    st.error(str(e))
        active_now = bool(users.loc[users["id"] == uid, "active"].iloc[0])
        if int(uid) == user["id"]:
            st.caption("No puedes desactivar tu propio usuario.")
        elif st.button("Desactivar usuario" if active_now else "Reactivar usuario"):
            auth.set_active(int(uid), not active_now)
            done("Estado actualizado.")

# ======================= AUDITORÍA =======================
elif page == "Auditoría" and is_admin:
    st.title("Registro de auditoría")
    st.dataframe(db.get_audit_log(), hide_index=True, use_container_width=True)

st.divider()
st.caption("INVENTIQ • Proyecto académico • Datos almacenados en la base de datos local inventiq.db (SQLite)")
