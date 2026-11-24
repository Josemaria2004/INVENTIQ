"""Pruebas de la lógica (sin interfaz). Ejecutar: python -m unittest discover tests -v"""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["INVENTIQ_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")

import analytics, auth, db, seed  # noqa: E402


class InventiqTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        auth.ensure_default_admin()

    def test_01_auth(self):
        self.assertIsNotNone(auth.authenticate("admin", "admin123"))
        self.assertIsNone(auth.authenticate("admin", "mala"))
        with self.assertRaises(ValueError):
            auth.create_user("admin", "Otro", "123456")

    def test_02_stock_rules(self):
        cat = int(db.get_categories().iloc[0]["id"])
        pid = db.add_product("T1", "Prueba", cat, None, "unidad", 10, 2, 20, 5.0)
        with self.assertRaises(ValueError):
            db.add_movement(pid, "Salida", 11, 5, "", date.today())
        db.add_movement(pid, "Salida", 4, 5, "", date.today())
        self.assertEqual(float(db.get_products().query("id==@pid").iloc[0]["stock"]), 6)
        with self.assertRaises(ValueError):
            db.add_product("T1", "Duplicado", cat, None, "unidad", 0, 1, 2, 1)
        with self.assertRaises(ValueError):
            db.add_movement(pid, "Entrada", 0, 5, "", date.today())

    def test_03_purchase_order_flow(self):
        db.add_supplier("Prov Test", "", "", "", 4)
        sid = int(db.get_suppliers().query("name=='Prov Test'").iloc[0]["id"])
        cat = int(db.get_categories().iloc[0]["id"])
        pid = db.add_product("T2", "Orden", cat, sid, "unidad", 5, 2, 20, 3.0)
        oid = db.create_purchase_order(sid, [(pid, 15, 3.5)])
        db.receive_purchase_order(oid)
        self.assertEqual(float(db.get_products().query("id==@pid").iloc[0]["stock"]), 20)
        with self.assertRaises(ValueError):
            db.receive_purchase_order(oid)  # no se puede recibir dos veces

    def test_04_deactivate_keeps_history(self):
        pid = int(db.get_products().query("code=='T1'").iloc[0]["id"])
        db.deactivate_product(pid)
        self.assertNotIn("T1", db.get_products()["code"].tolist())
        self.assertIn(pid, db.get_movements()["product_id"].tolist())

    def test_05_seed_and_analytics(self):
        other = str(Path(tempfile.mkdtemp()) / "seed.db")
        os.environ["INVENTIQ_DB"] = other
        db.DB_PATH = Path(other)
        db.init_db()
        self.assertTrue(seed.seed_demo())
        self.assertFalse(seed.seed_demo())  # no duplica
        an = analytics.inventory_analysis()
        self.assertEqual(len(an), 12)
        self.assertTrue((an["stock"] >= 0).all())
        self.assertTrue(set(an["clase_abc"]) <= {"A", "B", "C"})
        self.assertIn("A", set(an["clase_abc"]))
        # el stock de cada producto debe cuadrar con la suma de sus movimientos
        mv = db.get_movements()
        for _, p in an.iterrows():
            m = mv[mv["product_id"] == p["id"]]
            net = m.loc[m["tipo"] == "Entrada", "cantidad"].sum() - m.loc[m["tipo"] == "Salida", "cantidad"].sum()
            self.assertAlmostEqual(net, p["stock"], places=6)
        self.assertTrue(an["estado"].isin(["Crítico", "Agotado", "Reponer"]).any())


if __name__ == "__main__":
    unittest.main()
