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
        password="iproavatec_36" 
    )

# --- 1. NUEVA RUTA PRINCIPAL: CATÁLOGO PÚBLICO ---
@app.route('/')
def catalogo():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Traemos: nombre(0), precio(1), pago(2), horas(3), dificultad(4), imagen(5), id(6)
        cur.execute('SELECT prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url, id FROM productos')
        raw_productos = cur.fetchall()
        cur.close()
        conn.close()
        
        productos = []
        for p in raw_productos:
            lista_p = list(p)
            if lista_p[5] is None: 
                lista_p[5] = 'default.jpg'
            productos.append(lista_p)
            
        return render_template('catalogo.html', productos=productos)
    except Exception as e:
        return "Error al cargar catalogo: " + str(e)

# --- 2. RUTA DE COMPRA (ELIMINAR) ---
@app.route('/comprar/<int:id>')
def comprar(id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM productos WHERE id = %s', (id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('catalogo'))
    except Exception as e:
        return "Error al procesar compra: " + str(e)

@app.route('/home')
def home():
    if 'username' in session:
        # Si eres maestro, vas a tu panel de control
        if session['rol'] == 'maestro':
            return redirect(url_for('vista_maestro'))
        # Si eres cliente, vas al catálogo (pero ya logueado)
        else:
            return redirect(url_for('catalogo'))
    return redirect(url_for('login'))

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
                return redirect(url_for('home'))
            return "Error: Credenciales no validas"
        except Exception as e:
            return "Error de conexion: " + str(e)
    return render_template('login.html')

@app.route('/cliente')
def vista_cliente():
    if session.get('rol') != 'cliente': return redirect(url_for('home'))
    return redirect(url_for('catalogo')) # El cliente ahora usa el catálogo principal

@app.route('/maestro')
def vista_maestro():
    if session.get('rol') != 'maestro': return redirect(url_for('home'))
    return render_template('maestro.html', usuario=session['username'])

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
    return redirect(url_for('catalogo'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
