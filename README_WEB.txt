INVENTIQ — VERSIÓN WEB
Sistema web de gestión y control de inventarios (Flask + SQLite)

REQUISITOS
- Windows 10/11 o Linux/macOS
- Python 3.10 o superior
- Internet la primera vez para descargar dependencias

INICIO RÁPIDO EN WINDOWS
1. Extrae TODO el ZIP a una carpeta (por ejemplo, Escritorio/INVENTIQ_WEB).
2. Si no tienes Python, instálalo desde https://www.python.org/downloads/
   IMPORTANTE durante instalación: marca “Add Python to PATH”.
3. Haz doble clic en iniciar_inventiq.bat.
4. Espera a que instale dependencias y abra el navegador.
5. Dirección local: http://127.0.0.1:5000

INICIO EN LINUX / MAC
Abre terminal dentro de la carpeta y ejecuta:
  chmod +x iniciar_inventiq.sh
  ./iniciar_inventiq.sh

PRIMER INGRESO
Usuario: admin
Contraseña: admin123
Cambia la contraseña inicial en cuanto sea posible (por ahora, crea una cuenta
Administrador nueva desde Usuarios y desactiva la cuenta inicial).

DATOS DE DEMOSTRACIÓN
En el Panel de control, como Administrador, pulsa “Cargar datos demo”.
Se crean 12 productos, 3 proveedores e historial simulado de movimientos.
Solo carga la demo si no existen productos.

FUNCIONES INCLUIDAS
- Panel de control con métricas, alertas y movimientos recientes.
- Catálogo de productos, alta y desactivación/reactivación.
- Entradas y salidas con validación de stock.
- Proveedores.
- Órdenes de compra, recepción que actualiza existencias y cancelación.
- Análisis ABC, consumo, cobertura, stock de seguridad, punto de reorden,
  rotación y lote económico EOQ.
- Reportes filtrados por fecha y descarga CSV.
- Usuarios con roles Administrador y Operario.
- Registro de auditoría (Administrador).
- SQLite: los datos se guardan en inventiq.db automáticamente.

IMPORTANTE
- El sistema está pensado para ejecución local de demostración/estudio.
- No expongas el servidor a Internet sin configurar HTTPS, una clave secreta
  robusta, protección contra CSRF y controles adicionales.
- Para detener el servidor: Ctrl+C en la consola.
- Copia de seguridad: guarda una copia del archivo inventiq.db con el servidor
  detenido.

ARCHIVOS
webapp.py             Aplicación web Flask
 db.py / auth.py       Lógica de base de datos y autenticación
 analytics.py          Indicadores y cálculos
 seed.py               Dataset de demostración
 templates/             HTML
 static/                CSS y JavaScript
 tests/                 Pruebas de lógica
