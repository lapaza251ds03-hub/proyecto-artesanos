import os
from flask import Flask, render_template, redirect, url_for, session, request, jsonify, flash
from authlib.integrations.flask_client import OAuth
import psycopg2

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'un_secreto_comunitario_muy_seguro_123')

# ==========================================
# CONEXIÓN A LA BASE DE DATOS (NEON.TECH)
# ==========================================
def get_db_connection():
    # Conecta usando la variable de entorno que ya tienes configurada en Render
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    return conn

# ==========================================
# CONFIGURACIÓN DE GOOGLE OAUTH 2.0
# ==========================================
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

# ==========================================
# RUTAS DE LA APLICACIÓN
# ==========================================

@app.route('/')
@app.route('/catalogo')
def catalogo():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # CONTROL DE STOCK: Solo selecciona los productos cuyo stock sea mayor a 0
        cur.execute("""
            SELECT id, nombre, precio, pago_artesano, tiempo_horas, dificultad, imagen_url, stock 
            FROM productos 
            WHERE stock > 0;
        """)
        productos = cur.fetchall()
    except Exception as e:
        print(f"Error al cargar catálogo: {e}")
        productos = []
    finally:
        cur.close()
        conn.close()
        
    return render_template('catalogo.html', productos=productos)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('login_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/callback')
def login_callback():
    try:
        token = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()
        
        # Guardamos los datos esenciales en la sesión de Flask
        session['usuario_id'] = user_info.get('id')
        session['usuario_email'] = user_info.get('email')
        session['usuario_nombre'] = user_info.get('name')
        
        return redirect(url_for('catalogo'))
    except Exception as e:
        return f"Error en la autenticación con Google: {str(e)}"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('catalogo'))

# ==========================================
# RUTA PASARELA DE PAGOS (CULQI + STOCK)
# ==========================================
@app.route('/procesar-pago-culqi', methods=['POST'])
def procesar_pago_culqi():
    data = request.get_json()
    producto_id = data.get('producto_id')
    token_id = data.get('token_id')  # Token generado por el formulario seguro de Culqi
    
    if not producto_id or not token_id:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # CONTROL DE STOCK: Restamos 1 al stock actual del producto comprado
        cur.execute("""
            UPDATE productos 
            SET stock = stock - 1 
            WHERE id = %s AND stock > 0;
        """, (producto_id,))
        
        conn.commit()
        return jsonify({"status": "success", "message": "Pago registrado y stock actualizado"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# En Render la variable PORT se asigna automáticamente, usamos 5000 por defecto local
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
