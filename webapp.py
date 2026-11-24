from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from datetime import date, timedelta
import csv, io, os
import db, auth, analytics, seed

app = Flask(__name__)
app.secret_key = os.environ.get('INVENTIQ_SECRET', 'inventiq-local-dev-secret-change-me')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
db.init_db(); auth.ensure_default_admin()

@app.context_processor
def globals_ctx():
    return {'current_user': session.get('user'), 'today': date.today().isoformat()}

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('user'): return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('user'): return redirect(url_for('login'))
        if session['user']['role'] != 'Administrador':
            flash('Esta sección requiere permisos de Administrador.', 'warning'); return redirect(url_for('dashboard'))
        return fn(*args, **kwargs)
    return wrapped

def safe_float(name, default=0):
    try: return float(request.form.get(name, default) or default)
    except ValueError: return default

def safe_int(name, default=0):
    try: return int(request.form.get(name, default) or default)
    except ValueError: return default

@app.route('/')
@login_required
def dashboard():
    products=db.get_products(); analysis=analytics.inventory_analysis()
    movements=db.get_movements(date.today()-timedelta(days=30), date.today())
    orders=db.get_purchase_orders()
    total_items=len(products); stock_value=float((products.stock*products.cost).sum()) if not products.empty else 0
    alerts=analysis[analysis.estado.isin(['Agotado','Crítico','Reponer'])] if not analysis.empty else analysis
    out30=movements[movements.tipo=='Salida'].cantidad.sum() if not movements.empty else 0
    in30=movements[movements.tipo=='Entrada'].cantidad.sum() if not movements.empty else 0
    recent=movements.head(8) if not movements.empty else movements
    return render_template('dashboard.html', active='dashboard', products=products, total_items=total_items, stock_value=stock_value, alerts=alerts, out30=out30, in30=in30, recent=recent, orders=orders, analysis=analysis)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=auth.authenticate(request.form.get('username',''),request.form.get('password',''))
        if u: session['user']=u; return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos.','danger')
    return render_template('login.html')
@app.route('/change-password', methods=['GET','POST'])
@login_required
def change_password_page():
    if request.method == 'POST':
        old = auth.authenticate(session['user']['username'], request.form.get('current_password',''))
        if not old: flash('La contraseña actual no es correcta.','danger')
        elif request.form.get('new_password','') != request.form.get('confirm_password',''): flash('Las nuevas contraseñas no coinciden.','danger')
        else:
            try: auth.change_password(session['user']['id'],request.form['new_password']); flash('Contraseña cambiada correctamente.','success'); return redirect(url_for('dashboard'))
            except Exception as e: flash(str(e),'danger')
    return render_template('change_password.html',active='')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/products', methods=['GET','POST'])
@login_required
def products():
    if request.method=='POST':
        try:
            db.add_product(request.form['code'],request.form['name'],safe_int('category_id'),safe_int('supplier_id') or None,request.form['unit'],safe_float('stock'),safe_float('min_stock'),safe_float('target_stock'),safe_float('cost'),safe_float('ordering_cost',20),safe_float('holding_rate',.2),session['user']['id'])
            flash('Producto registrado.','success')
        except Exception as e: flash(str(e),'danger')
        return redirect(url_for('products'))
    df=db.get_products(only_active=False); cats=db.get_categories(); sups=db.get_suppliers(only_active=False)
    return render_template('products.html',active='products', products=df,categories=cats,suppliers=sups)
@app.route('/products/deactivate/<int:pid>')
@admin_required
def deactivate(pid): db.deactivate_product(pid,session['user']['id']); flash('Producto desactivado.','success'); return redirect(url_for('products'))
@app.route('/products/reactivate/<int:pid>')
@admin_required
def reactivate(pid): db.reactivate_product(pid,session['user']['id']); flash('Producto reactivado.','success'); return redirect(url_for('products'))

@app.route('/suppliers', methods=['GET','POST'])
@login_required
def suppliers():
    if request.method=='POST':
        try: db.add_supplier(request.form['name'],request.form.get('contact',''),request.form.get('phone',''),request.form.get('email',''),safe_int('lead_time_days',7)); flash('Proveedor creado.','success')
        except Exception as e: flash(str(e),'danger')
        return redirect(url_for('suppliers'))
    return render_template('suppliers.html',active='suppliers',suppliers=db.get_suppliers(only_active=False))

@app.route('/movements', methods=['GET','POST'])
@login_required
def movements():
    if request.method=='POST':
        try: db.add_movement(safe_int('product_id'),request.form['movement_type'],safe_float('quantity'),safe_float('unit_cost'),request.form.get('note',''),date.fromisoformat(request.form.get('movement_date') or date.today().isoformat()),session['user']['id']); flash('Movimiento registrado.','success')
        except Exception as e: flash(str(e),'danger')
        return redirect(url_for('movements'))
    start=request.args.get('start'); end=request.args.get('end');
    df=db.get_movements(date.fromisoformat(start) if start else None,date.fromisoformat(end) if end else None)
    return render_template('movements.html',active='movements',movements=df,products=db.get_products(),start=start or '',end=end or '')

@app.route('/orders',methods=['GET','POST'])
@login_required
def orders():
    if request.method=='POST':
        try:
            product_ids=request.form.getlist('product_id'); qtys=request.form.getlist('quantity'); costs=request.form.getlist('unit_cost')
            items=[(int(p),float(q),float(c)) for p,q,c in zip(product_ids,qtys,costs) if q and float(q)>0]
            oid=db.create_purchase_order(safe_int('supplier_id'),items,request.form.get('note',''),session['user']['id']); flash(f'Orden #{oid} creada.','success')
        except Exception as e: flash(str(e),'danger')
        return redirect(url_for('orders'))
    return render_template('orders.html',active='orders',orders=db.get_purchase_orders(),suppliers=db.get_suppliers(),products=db.get_products())
@app.route('/orders/receive/<int:oid>')
@login_required
def receive(oid):
    try: db.receive_purchase_order(oid,session['user']['id']); flash('Orden recibida; stock actualizado.','success')
    except Exception as e: flash(str(e),'danger')
    return redirect(url_for('orders'))
@app.route('/orders/cancel/<int:oid>')
@login_required
def cancel(oid):
    try: db.cancel_purchase_order(oid,session['user']['id']); flash('Orden cancelada.','success')
    except Exception as e: flash(str(e),'danger')
    return redirect(url_for('orders'))

@app.route('/analysis')
@login_required
def analysis_page():
    days=safe_int_query('days',90); df=analytics.inventory_analysis(days)
    return render_template('analysis.html',active='analysis',data=df,days=days,inf=float('inf'))
def safe_int_query(name,default):
    try:return int(request.args.get(name,default))
    except:return default

@app.route('/reports')
@login_required
def reports():
    start=request.args.get('start'); end=request.args.get('end'); df=db.get_movements(date.fromisoformat(start) if start else None,date.fromisoformat(end) if end else None)
    return render_template('reports.html',active='reports',data=df,start=start or '',end=end or '')
@app.route('/reports/csv')
@login_required
def csv_report():
    start=request.args.get('start'); end=request.args.get('end'); df=db.get_movements(date.fromisoformat(start) if start else None,date.fromisoformat(end) if end else None)
    buf=io.StringIO(); df.to_csv(buf,index=False); return Response(buf.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=inventiq_movimientos.csv'})

@app.route('/users',methods=['GET','POST'])
@admin_required
def users():
    if request.method=='POST':
        try: auth.create_user(request.form['username'],request.form['full_name'],request.form['password'],request.form['role']); flash('Usuario creado.','success')
        except Exception as e: flash(str(e),'danger')
        return redirect(url_for('users'))
    return render_template('users.html',active='users',users=auth.list_users())
@app.route('/users/toggle/<int:uid>')
@admin_required
def user_toggle(uid):
    if uid==session['user']['id']: flash('No puedes desactivar tu propia cuenta.','warning')
    else:
        rows=auth.list_users(); active=bool(rows[rows.id==uid].iloc[0].active); auth.set_active(uid,not active); flash('Estado actualizado.','success')
    return redirect(url_for('users'))
@app.route('/audit')
@admin_required
def audit(): return render_template('audit.html',active='audit',logs=db.get_audit_log())
@app.route('/demo',methods=['POST'])
@admin_required
def demo():
    if seed.seed_demo(session['user']['id']): flash('Datos de demostración cargados (productos, proveedores e historial).','success')
    else: flash('Ya existen productos; no se cargaron datos de demo.','warning')
    return redirect(url_for('dashboard'))

if __name__=='__main__':
    app.run(host='127.0.0.1',port=5000,debug=False)
