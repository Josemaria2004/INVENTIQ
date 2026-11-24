"""Indicadores de ingeniería industrial: consumo, cobertura, ABC, punto de reorden y EOQ."""
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

import db

SERVICE_Z = 1.65  # nivel de servicio ~95 %


def consumption(days=90):
    """Consumo (salidas) por producto en la ventana de `days` días."""
    start = date.today() - timedelta(days=days)
    mov = db.get_movements(start, date.today())
    if mov.empty:
        return pd.DataFrame(columns=["product_id", "qty_out", "value_out", "std_daily"])
    out = mov[mov["tipo"] == "Salida"].copy()
    if out.empty:
        return pd.DataFrame(columns=["product_id", "qty_out", "value_out", "std_daily"])
    g = out.groupby("product_id").agg(qty_out=("cantidad", "sum"), value_out=("valor", "sum")).reset_index()
    # desviación estándar de la demanda diaria (días sin salida cuentan como 0)
    idx = pd.date_range(start, date.today())
    daily = out.assign(fecha=pd.to_datetime(out["fecha"])).pivot_table(
        index="fecha", columns="product_id", values="cantidad", aggfunc="sum").reindex(idx, fill_value=0).fillna(0)
    std = daily.std(ddof=0).rename("std_daily").reset_index().rename(columns={"index": "product_id"})
    std.columns = ["product_id", "std_daily"]
    return g.merge(std, on="product_id", how="left")


def inventory_analysis(days=90):
    """Tabla completa por producto con todos los indicadores."""
    products = db.get_products()
    if products.empty:
        return products
    cons = consumption(days)
    df = products.merge(cons, left_on="id", right_on="product_id", how="left")
    for c in ["qty_out", "value_out", "std_daily"]:
        df[c] = df[c].fillna(0.0)
    df["consumo_diario"] = df["qty_out"] / days
    df["valor_stock"] = df["stock"] * df["cost"]
    df["dias_cobertura"] = np.where(df["consumo_diario"] > 0, df["stock"] / df["consumo_diario"], np.inf)
    # rotación = costo de lo consumido / valor promedio (aprox. valor actual) del inventario
    df["rotacion"] = np.where(df["valor_stock"] > 0, df["value_out"] / df["valor_stock"], 0.0)
    # punto de reorden = demanda durante el lead time + stock de seguridad
    df["stock_seguridad"] = SERVICE_Z * df["std_daily"] * np.sqrt(df["lead_time_days"])
    df["stock_seguridad"] = np.maximum(df["stock_seguridad"], df["min_stock"])
    df["punto_reorden"] = df["consumo_diario"] * df["lead_time_days"] + df["stock_seguridad"]
    # lote económico (EOQ) = sqrt(2·D·S / H)
    D = df["consumo_diario"] * 365
    H = df["cost"] * df["holding_rate"]
    df["eoq"] = np.where((D > 0) & (H > 0), np.sqrt(2 * D * df["ordering_cost"] / H.replace(0, np.nan)), 0.0)
    df["eoq"] = df["eoq"].fillna(0).round(0)
    df["clase_abc"] = abc_classification(df)
    df["estado"] = df.apply(_status, axis=1)
    return df


def abc_classification(df):
    """Clasificación ABC por valor consumido: A = 80 % acumulado, B = 95 %, C = resto."""
    total = df["value_out"].sum()
    if total <= 0:
        return pd.Series("C", index=df.index)
    ordered = df["value_out"].sort_values(ascending=False)
    cum_before = ordered.cumsum() / total - ordered / total  # % acumulado antes de este producto
    cls = pd.Series("C", index=ordered.index)
    cls[cum_before < 0.95] = "B"
    cls[cum_before < 0.80] = "A"
    cls[ordered <= 0] = "C"
    return cls.reindex(df.index)


def _status(r):
    if r["stock"] <= 0:
        return "Agotado"
    if r["stock"] <= r["min_stock"]:
        return "Crítico"
    if r["stock"] <= r["punto_reorden"]:
        return "Reponer"
    if r["consumo_diario"] == 0:
        return "Sin rotación"
    return "OK"


def suggested_order_qty(row):
    """Cantidad a pedir: lo necesario para llegar al stock objetivo (mínimo el EOQ si aplica)."""
    need = max(row["target_stock"] - row["stock"], 0)
    return float(math.ceil(max(need, row["eoq"]))) if need > 0 else 0.0


def daily_flow(days=60):
    """Entradas y salidas por día (para gráfico de tendencia)."""
    mov = db.get_movements(date.today() - timedelta(days=days), date.today())
    if mov.empty:
        return pd.DataFrame()
    mov["fecha"] = pd.to_datetime(mov["fecha"])
    t = mov.pivot_table(index="fecha", columns="tipo", values="cantidad", aggfunc="sum").fillna(0)
    return t.reindex(pd.date_range(t.index.min(), date.today()), fill_value=0)
