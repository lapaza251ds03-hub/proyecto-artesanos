# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_minka_community')

app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

UPLOAD_FOLDER = os.path.join('static', 'img', 'productos')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

# CONEXIÓN A LA BASE DE DATOS NEON
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return psycopg2.connect(db_url)
    
    return psycopg2.connect(
        host="localhost",
        database="artesania_db",
        user="postgres",
        password="password_local" 
    )

# 1. CATÁLOGO PÚBLICO (CON BÚSQUEDA Y NOMBRE DE MAESTRO)
@app.route('/')
def catalogo_publico():
    try:
        q = request.args.get('q', '').strip()
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Consulta base uniendo la tabla usuarios para obtener el nombre del maestro
        query = """
            SELECT p.id, p.prenda, p.precio_total, p.pago_artesano, p.tiempo_horas, p.dificultad, p.imagen_url, p.stock, u.username 
            FROM productos p
            LEFT JOIN usuarios u ON p.maestro_id = u.id
            WHERE p.stock > 0
        """
        
        if q:
            query += " AND (p.prenda ILIKE %s OR u.username ILIKE %s);"
            cur.execute(query, (f'%{q}%', f'%{q}%'))
        else:
            query += ";"
            cur.execute(query)
            
        raw_productos = cur.fetchall()
        cur.close()
        conn.close()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if not lista_p[6]: lista_p[6] = 'default.jpg'
            productos.append(lista_p)
            
        return render_template('catalogo.html', productos=productos, busqueda=q)
    except Exception as e:
        return "Error en catálogo público: " + str(e)


# 3. INTERFAZ DE CLIENTE (CON BÚSQUEDA Y NOMBRE DE MAESTRO)
@app.route('/cliente')
def vista_cliente():
    if 'usuario_id' not in session: 
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    q = request.args.get('q', '').strip()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Consulta incluyendo el username del maestro
        query = """
            SELECT p.id, p.prenda, p.precio_total, p.pago_artesano, p.tiempo_horas, p.dificultad, p.imagen_url, p.stock, u.username 
            FROM productos p
            LEFT JOIN usuarios u ON p.maestro_id = u.id
        """
        
        if q:
            query += " WHERE (p.prenda ILIKE %s OR u.username ILIKE %s);"
            cur.execute(query, (f'%{q}%', f'%{q}%'))
        else:
            cur.execute(query)
            
        raw_productos = cur.fetchall()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if not lista_p[6]: lista_p[6] = 'default.jpg'
            productos.append(lista_p)
            
        cur.execute("SELECT id, total FROM compras WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        carrito = cur.fetchone()
        
        items_carrito = []
        total_carrito = 0.00
        impacto_total = 0.00
        
        if carrito:
            compra_id = carrito[0]
            total_carrito = carrito[1]
            cur.execute('''
                SELECT d.id, p.prenda, d.cantidad, d.precio_unitario, (d.cantidad * d.precio_unitario) as subtotal, p.imagen_url, p.pago_artesano, p.id
                FROM detalle_compras d
                JOIN productos p ON d.producto_id = p.id
                WHERE d.compra_id = %s
            ''', (compra_id,))
            items_carrito = cur.fetchall()
            impacto_total = sum(float(item[6]) * int(item[2]) for item in items_carrito)
            
        cur.close()
        conn.close()
        
        return render_template('cliente.html', 
                               productos=productos, 
                               items=items_carrito, 
                               total=total_carrito, 
                               impacto_total=impacto_total, 
                               usuario=session['username'],
                               busqueda=q)
    except Exception as e:
        return "Error en vista cliente: " + str(e)

# MOTOR DEL CARRITO (AÑADIR)
@app.route('/carrito/anadir/<int:producto_id>')
def anadir_al_carrito(producto_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM compras WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        carrito = cur.fetchone()
        
        if not carrito:
            cur.execute("INSERT INTO compras (usuario_id, total, estado) VALUES (%s, 0.00, 'pendiente') RETURNING id", (usuario_id,))
            compra_id = cur.fetchone()[0]
        else:
            compra_id = carrito[0]
            
        cur.execute("SELECT precio_total, stock FROM productos WHERE id = %s", (producto_id,))
        producto = cur.fetchone()
        if not producto or producto[1] <= 0:
            cur.close()
            conn.close()
            return "Producto sin stock disponible", 400
            
        precio_unitario = producto[0]
        
        cur.execute("SELECT id, cantidad FROM detalle_compras WHERE compra_id = %s AND producto_id = %s", (compra_id, producto_id))
        detalle_existente = cur.fetchone()
        
        if detalle_existente:
            nueva_cantidad = detalle_existente[1] + 1
            cur.execute("UPDATE detalle_compras SET cantidad = %s WHERE id = %s", (nueva_cantidad, detalle_existente[0]))
        else:
            cur.execute("INSERT INTO detalle_compras (compra_id, producto_id, cantidad, precio_unitario) VALUES (%s, %s, 1, %s)", 
                        (compra_id, producto_id, precio_unitario))
            
        cur.execute("SELECT SUM(cantidad * precio_unitario) FROM detalle_compras WHERE compra_id = %s", (compra_id,))
        nuevo_total = cur.fetchone()[0] or 0.00
        
        cur.execute("UPDATE compras SET total = %s WHERE id = %s", (nuevo_total, compra_id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('vista_cliente'))
    except Exception as e:
        return "Error al añadir al carrito: " + str(e)

# MOTOR DEL CARRITO (PAGAR TRADICIONAL / LLAMADO POR CULQI)
@app.route('/carrito/pagar')
def pagar_carrito():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Descontamos el stock físico según las unidades de cada prenda comprada
        cur.execute('''
            SELECT producto_id, cantidad FROM detalle_compras 
            WHERE compra_id = (SELECT id FROM compras WHERE usuario_id = %s AND estado = 'pendiente')
        ''', (usuario_id,))
        items = cur.fetchall()
        
        for item in items:
            cur.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (item[1], item[0]))
            
        cur.execute("UPDATE compras SET estado = 'pagado' WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        conn.commit()
        cur.close()
        conn.close()
        return "¡Compra realizada con éxito con Culqi! <a href='/cliente'>Volver a la tienda</a>"
    except Exception as e:
        return "Error al procesar el pago: " + str(e)

# 4. NUEVA INTERFAZ EXCLUSIVA PARA LA PASARELA DE CULQI
@app.route('/resumen-pago')
def resumen_pago():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    usuario_id = session['usuario_id']
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, total FROM compras WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        carrito = cur.fetchone()
        if not carrito or carrito[1] <= 0:
            cur.close()
            conn.close()
            return redirect(url_for('vista_cliente'))
        
        compra_id = carrito[0]
        total_carrito = carrito[1]
        cur.execute('''
            SELECT p.prenda, d.cantidad, d.precio_unitario, (d.cantidad * d.precio_unitario) as subtotal
            FROM detalle_compras d
            JOIN productos p ON d.producto_id = p.id
            WHERE d.compra_id = %s
        ''', (compra_id,))
        items = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('pago.html', items=items, total=total_carrito)
    except Exception as e:
        return "Error al cargar la pasarela de pago: " + str(e)

# 5. INTERFAZ DE MAESTRO
@app.route('/maestro')
def vista_maestro():
    if 'username' not in session or session.get('rol') != 'maestro':
        return redirect(url_for('login'))
    return render_template('maestro.html', usuario=session['username'])

@app.route('/registrar', methods=['POST'])
def registrar():
    if session.get('rol') != 'maestro': 
        return redirect(url_for('login'))
    try:
        prenda = request.form['prenda']
        precio = float(request.form['precio'])
        pago_artesano = precio * 0.8
        horas = request.form['horas']
        dificultad = request.form['dificultad']
        stock = int(request.form.get('stock', 1)) # Captura el stock digitado
        maestro_id = session['usuario_id'] 
        
        file = request.files.get('archivo')
        filename = "default.jpg"
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''INSERT INTO productos (prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url, maestro_id, stock) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                    (prenda, precio, pago_artesano, horas, dificultad, filename, maestro_id, stock))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('vista_maestro'))
    except Exception as e:
        return "Error al registrar producto: " + str(e)

# 6. LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('catalogo_publico'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
