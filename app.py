import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'tu_llave_secreta_aqui'  # Cambia esto por algo seguro

# Configuración de la base de datos de Neon
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

@app.route('/')
def catalogo():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM productos')
    productos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('catalogo.html', productos=productos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM usuarios WHERE username = %s AND password = %s', (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['user'] = username
            session['rol'] = user[2]
            
            # Si el usuario venía de intentar comprar algo, lo mandamos allá
            next_page = session.pop('next', None)
            if next_page:
                return redirect(next_page)
            
            # Si no, va al panel del maestro
            return redirect(url_for('maestro'))
        else:
            flash('Usuario o contraseña incorrectos')
    
    return render_template('login.html')

@app.route('/maestro')
def maestro():
    if 'user' not in session or session.get('rol') != 'maestro':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM productos')
    productos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('maestro.html', productos=productos)

@app.route('/comprar/<int:id>')
def comprar(id):
    # Si NO está logueado, lo mandamos al login y guardamos qué quería comprar
    if 'user' not in session:
        session['next'] = url_for('comprar', id=id)
        flash('Debes iniciar sesión para realizar la compra')
        return redirect(url_for('login'))
    
    # Si ya está logueado, procedemos a borrar el producto
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM productos WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    
    flash('¡Compra realizada con éxito! El producto ha sido reservado.')
    return redirect(url_for('catalogo'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('catalogo'))

# Ruta para que el maestro agregue productos (asegúrate de que coincida con tu maestro.html)
@app.route('/agregar', methods=['POST'])
def agregar_producto():
    if 'user' not in session: return redirect(url_for('login'))
    
    prenda = request.form['prenda']
    precio = request.form['precio']
    pago = request.form['pago']
    tiempo = request.form['tiempo']
    dificultad = request.form['dificultad']
    url = request.form['url']
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''INSERT INTO productos (prenda, precio_total, pago_artesano, tiempo_horas, dificultad, imagen_url) 
                   VALUES (%s, %s, %s, %s, %s, %s)''', 
                (prenda, precio, pago, tiempo, dificultad, url))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('maestro'))

if __name__ == '__main__':
    app.run(debug=True)
