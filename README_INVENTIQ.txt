INVENTIQ — Sistema inteligente de gestión y control de inventarios
===================================================================

REQUISITOS
- Python 3.10 o superior
- Internet solo la primera vez, para instalar las librerías.

INSTALACIÓN Y EJECUCIÓN
1. Descomprime la carpeta y abre una terminal dentro de ella.
2. pip install -r requirements.txt
3. streamlit run app.py
4. Se abre en el navegador (http://localhost:8501).

PRIMER INGRESO
Usuario: admin   Contraseña: admin123   (cámbiala en el menú Usuarios)
Luego, en el menú lateral, presiona "Cargar datos de demostración" (12 productos, 3 proveedores y 90 días de historial).

BASE DE DATOS (SQLite, archivo inventiq.db, se crea sola)
Tablas: users, categories, suppliers, products, movements,
        purchase_orders, purchase_order_items, audit_log
- Todo lo que se registra en la aplicación queda guardado en la base de datos.
- Claves foráneas activas, restricciones CHECK (stock >= 0, cantidades > 0) y transacciones:
  cada movimiento actualiza stock + historial de forma atómica.
- Los productos no se borran: se desactivan, para conservar el historial.
- Las contraseñas se guardan cifradas (PBKDF2-SHA256 con sal), nunca en texto plano.
- Para empezar de cero, cierra la aplicación y borra inventiq.db.
- Se puede abrir inventiq.db con "DB Browser for SQLite" para ver las tablas.

FUNCIONES
- Login con roles: Administrador (todo) y Operario (consulta, movimientos, recepción de órdenes).
- Productos: registro, búsqueda, edición, desactivación, categorías, CSV.
- Movimientos de entrada/salida con validación de stock y usuario responsable.
- Alertas: Agotado / Crítico / Reponer, cantidad sugerida y costo de reposición.
- Análisis de ingeniería industrial: clasificación ABC, rotación, días de cobertura,
  stock de seguridad, punto de reorden y lote económico (EOQ).
- Proveedores con plazo de entrega y órdenes de compra (al recibirlas se generan las entradas).
- Reportes por fechas con gráficos y exportación CSV.
- Auditoría de acciones (solo administrador).

ARCHIVOS
app.py        interfaz (Streamlit)
db.py         esquema y operaciones de la base de datos
auth.py       usuarios y contraseñas
analytics.py  ABC, rotación, punto de reorden, EOQ
seed.py       datos de demostración
tests/        pruebas automáticas:  python -m unittest discover tests -v

FÓRMULAS
Consumo diario = salidas de la ventana / días
Punto de reorden = consumo diario x plazo del proveedor + stock de seguridad
Stock de seguridad = 1.65 x desv. estándar diaria x raiz(plazo)   (mínimo: stock mínimo)
EOQ = raiz(2 x D x S / H)   D = demanda anual, S = costo por pedido, H = costo de mantener x costo unitario
Rotación = valor consumido / valor actual en stock
