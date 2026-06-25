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

# 3. INTERFAZ DE CLIENTE (Turista con sesión activa)
@app.route('/cliente')
def vista_cliente():
    if 'username' not in session: 
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url FROM productos')
        raw_productos = cur.fetchall()
        cur.close()
        conn.close()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if not lista_p[6]: lista_p[6] = 'default.jpg'
            productos.append(lista_p)
            
        return render_template('cliente.html', productos=productos, usuario=session['username'])
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
