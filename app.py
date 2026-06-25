# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_minka_community')

UPLOAD_FOLDER = os.path.join('static', 'img', 'productos')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

# 1. CATÁLOGO PÚBLICO (Fase: Portada General)
@app.route('/')
def catalogo_publico():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Adaptado a la nueva estructura de la tabla productos (7 campos)
        cur.execute('SELECT id, prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url FROM productos')
        raw_productos = cur.fetchall()
        cur.close()
        conn.close()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if not lista_p[6]: lista_p[6] = 'default.jpg'  # p[6] es imagen_url ahora
            productos.append(lista_p)
            
        return render_template('catalogo.html', productos=productos)
    except Exception as e:
        return "Error en catálogo público: " + str(e)

# 2. LOGIN CON CONTROL DE ID DE USUARIO (Para amarrar el carrito)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            # Traemos el ID además del rol para guardarlo en la sesión del navegador
            cur.execute('SELECT id, rol FROM usuarios WHERE username = %s AND password = %s', (user, pw))
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                session['usuario_id'] = result[0]  # <--- CRUCIAL: Guardamos el ID del usuario
                session['username'] = user
                session['rol'] = result[1]
                
                if session['rol'] == 'maestro':
                    return redirect(url_for('vista_maestro'))
                else:
                    return redirect(url_for('vista_cliente'))
            
            return "Error: Credenciales incorrectas."
        except Exception as e:
            return "Error de conexión en login: " + str(e)
    return render_template('login.html')

@app.route('/cliente')
def vista_cliente():
    if 'usuario_id' not in session: 
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Traemos todos los productos para la tienda
        cur.execute('SELECT id, prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url FROM productos')
        raw_productos = cur.fetchall()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if not lista_p[6]: lista_p[6] = 'default.jpg'
            productos.append(lista_p)
            
        # 2. Traemos el carrito activo ('pendiente') de este usuario específico
        cur.execute("SELECT id, total FROM compras WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        carrito = cur.fetchone()
        
        items_carrito = []
        total_carrito = 0.00
        impacto_total = 0.00
        
        if carrito:
            compra_id = carrito[0]
            total_carrito = carrito[1]
            # JOIN para traer los detalles junto con el nombre e imagen del producto
            cur.execute('''
                SELECT d.id, p.prenda, d.cantidad, d.precio_unitario, (d.cantidad * d.precio_unitario) as subtotal, p.imagen_url, p.pago_artesano
                FROM detalle_compras d
                JOIN productos p ON d.producto_id = p.id
                WHERE d.compra_id = %s
            ''', (compra_id,))
            items_carrito = cur.fetchall()
            # Calculamos el impacto ético acumulado del carrito
            impacto_total = sum(float(item[6]) * int(item[2]) for item in items_carrito)
            
        cur.close()
        conn.close()
        
        # Le mandamos TODO a la misma plantilla cliente.html
        return render_template('cliente.html', 
                               productos=productos, 
                               items=items_carrito, 
                               total=total_carrito, 
                               impacto_total=impacto_total, 
                               usuario=session['username'])
    except Exception as e:
        return "Error en vista cliente: " + str(e)

# 4. INTERFAZ DE MAESTRO (Alineado a los nuevos nombres de columnas)
@app.route('/maestro')
def vista_maestro():
    if 'username' not in session or session.get('rol') != 'maestro':
        return redirect(url_for('login'))
    return render_template('maestro.html', usuario=session['username'])

# 5. REGISTRAR PRODUCTO (Fase: Publicación del Maestro)
@app.route('/registrar', methods=['POST'])
def registrar():
    if session.get('rol') != 'maestro': 
        return redirect(url_for('login'))
    try:
        prenda = request.form['prenda']
        precio = float(request.form['precio'])
        pago_artesano = precio * 0.8  # Impacto ético directo automático (80%)
        horas = request.form['horas']
        dificultad = request.form['dificultad']
        
        file = request.files.get('archivo')
        filename = "default.jpg"
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        cur = conn.cursor()
        # Insertando respetando el orden exacto de tu nuevo diagrama de Neon
        cur.execute('''INSERT INTO productos (prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url) 
                       VALUES (%s, %s, %s, %s, %s, %s)''',
                    (prenda, precio, pago_artesano, horas, dificultad, filename))
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

# PASO 3 Y 4: Añadir un producto al carrito (o crearlo si no existe)
@app.route('/carrito/anadir/<int:producto_id>')
def anadir_al_carrito(producto_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    usuario_id = session['usuario_id']
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Buscamos si el usuario ya tiene un carrito 'pendiente' activo
        cur.execute("SELECT id FROM compras WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        carrito = cur.fetchone()
        
        if not carrito:
            # Si no tiene carrito activo, lo creamos (Paso 3 de tu flujo)
            cur.execute("INSERT INTO compras (usuario_id, total, estado) VALUES (%s, 0.00, 'pendiente') RETURNING id", (usuario_id,))
            compra_id = cur.fetchone()[0]
        else:
            compra_id = carrito[0]
            
        # 2. Buscamos el precio del producto que se quiere añadir
        cur.execute("SELECT precio_total FROM productos WHERE id = %s", (producto_id,))
        producto = cur.fetchone()
        if not producto:
            return "Producto no encontrado", 404
        precio_unitario = producto[0]
        
        # 3. Verificamos si el producto ya estaba en el detalle de este carrito
        cur.execute("SELECT id, cantidad FROM detalle_compras WHERE compra_id = %s AND producto_id = %s", (compra_id, producto_id))
        detalle_existente = cur.fetchone()
        
        if detalle_existente:
            # Si ya existe, le sumamos 1 a la cantidad
            nueva_cantidad = detalle_existente[1] + 1
            cur.execute("UPDATE detalle_compras SET cantidad = %s WHERE id = %s", (nueva_cantidad, detalle_existente[0]))
        else:
            # Si es nuevo, lo insertamos al detalle (Paso 4 de tu flujo)
            cur.execute("INSERT INTO detalle_compras (compra_id, producto_id, cantidad, precio_unitario) VALUES (%s, %s, 1, %s)", 
                        (compra_id, producto_id, precio_unitario))
            
        # 4. Recalculamos el total del carrito sumando todos sus detalles
        cur.execute("SELECT SUM(cantidad * precio_unitario) FROM detalle_compras WHERE compra_id = %s", (compra_id,))
        nuevo_total = cur.fetchone()[0] or 0.00
        
        # 5. Actualizamos el total en la tabla compras
        cur.execute("UPDATE compras SET total = %s WHERE id = %s", (nuevo_total, compra_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Redirigimos a la vista del cliente para que siga viendo la tienda
        return redirect(url_for('vista_cliente'))
        
    except Exception as e:
        return "Error al añadir al carrito: " + str(e)


# PASO 5: Ver el Carrito (Comparar, Modificar o Eliminar ítems)
@app.route('/carrito')
def ver_carrito():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Buscamos el carrito activo del usuario
        cur.execute("SELECT id, total FROM compras WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        carrito = cur.fetchone()
        
        if not carrito:
            # Carrito vacío por defecto si no hay registros pendientes
            return render_template('carrito.html', items=[], total=0.00)
            
        compra_id = carrito[0]
        total_carrito = carrito[1]
        
        # Hacemos un JOIN para traer los datos del producto mezclados con los del detalle
        cur.execute('''
            SELECT d.id, p.prenda, d.cantidad, d.precio_unitario, (d.cantidad * d.precio_unitario) as subtotal, p.imagen_url, p.pago_artesano, p.tiempo_horas
            FROM detalle_compras d
            JOIN productos p ON d.producto_id = p.id
            WHERE d.compra_id = %s
        ''', (compra_id,))
        items = cur.fetchall()
        
        # Calculamos el Impacto Ético Total (Suma del 80% de lo acumulado para los artesanos)
        impacto_total = sum(float(item[6]) * int(item[2]) for item in items)
        
        cur.close()
        conn.close()
        
        return render_template('carrito.html', items=items, total=total_carrito, impacto_total=impacto_total)
    except Exception as e:
        return "Error al cargar el carrito: " + str(e)


# PASO 6: Simular el pago y cerrar el carrito activo
@app.route('/carrito/pagar')
def pagar_carrito():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Cambiamos el estado de 'pendiente' a 'pagado'
        cur.execute("UPDATE compras SET estado = 'pagado' WHERE usuario_id = %s AND estado = 'pendiente'", (usuario_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        # Al pagar con éxito, lo mandamos de vuelta a su panel con el carrito limpio
        return "¡Compra realizada con éxito! Tu orden ha sido guardada en tu historial. <a href='/cliente'>Volver a la tienda</a>"
    except Exception as e:
        return "Error al procesar el pago: " + str(e)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
