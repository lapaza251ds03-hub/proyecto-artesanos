# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_cusco_directo')

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

# 1. PORTADA: CATÁLOGO PÚBLICO
@app.route('/')
def catalogo_publico():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Traemos todos los campos incluyendo el ID (p[6])
        cur.execute('SELECT prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url, id FROM productos')
        raw_productos = cur.fetchall()
        cur.close()
        conn.close()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if not lista_p[5]: lista_p[5] = 'default.jpg'
            productos.append(lista_p)
            
        return render_template('catalogo.html', productos=productos)
    except Exception as e:
        return "Error en catálogo: " + str(e)

# 2. RUTA DE COMPRA (Para que no salga el error 404 de tu foto)
@app.route('/comprar/<int:id>')
def comprar(id):
    # Si no ha iniciado sesión, lo mandamos al login
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Si ya inició sesión (como turista o maestro), lo deja "comprar" (borrar)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM productos WHERE id = %s', (id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('catalogo_publico'))
    except Exception as e:
        return "Error al procesar compra: " + str(e)

# 3. LOGIN CON REDIRECCIÓN SEGÚN ROL
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('SELECT rol FROM usuarios WHERE username = %s AND password = %s', (user, pw))
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                session['username'] = user
                session['rol'] = result[0]
                # Si es maestro -> panel maestro
                if session['rol'] == 'maestro':
                    return redirect(url_for('vista_maestro'))
                # Si es turista/cliente -> interfaz cliente
                else:
                    return redirect(url_for('vista_cliente'))
            
            return "Error: Credenciales inválidas"
        except Exception as e:
            return "Error de conexión: " + str(e)
    return render_template('login.html')

# 4. INTERFAZ DE CLIENTE (Turista)
@app.route('/cliente')
def vista_cliente():
    if 'username' not in session: return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # IMPORTANTE: Hemos añadido el ID al final de la consulta (es el p[6])
        cur.execute('SELECT prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url, id FROM productos')
        raw_productos = cur.fetchall()
        cur.close()
        conn.close()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if not lista_p[5]: lista_p[5] = 'default.jpg'
            productos.append(lista_p)
            
        return render_template('cliente.html', productos=productos)
    except Exception as e:
        return "Error en vista cliente: " + str(e)
# 5. INTERFAZ DE MAESTRO
@app.route('/maestro')
def vista_maestro():
    if 'username' not in session or session.get('rol') != 'maestro':
        return redirect(url_for('login'))
    return render_template('maestro.html', usuario=session['username'])

# 6. REGISTRAR PRODUCTO (Solo maestros)
@app.route('/registrar', methods=['POST'])
def registrar():
    if session.get('rol') != 'maestro': return redirect(url_for('login'))
    try:
        prenda = request.form['prenda']
        precio = float(request.form['precio'])
        pago_artesano = precio * 0.8
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
        cur.execute('''INSERT INTO productos (prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url) 
                       VALUES (%s, %s, %s, %s, %s, %s)''',
                    (prenda, precio, pago_artesano, horas, dificultad, filename))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('vista_maestro'))
    except Exception as e:
        return "Error al registrar: " + str(e)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('catalogo_publico'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
