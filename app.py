import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURACIÓN DE LA BASE DE DATOS (BLINDADA PARA RENDER) ---

# 1. Buscamos la variable en la nube
database_url = os.environ.get('DATABASE_URL')

# 2. Si existe (estamos en Render), corregimos el formato antiguo
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
else:
    # 3. Si NO existe (estamos en tu PC), usamos tu clave local
    # NOTA: Si tu clave local cambió, actualízala aquí
    database_url = 'postgresql://postgres:Luciana%402012@localhost/soporte_db'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'mi_clave_secreta_super_segura' 

db = SQLAlchemy(app)

# --- MODELOS (TABLAS) ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) 
    rol = db.Column(db.String(20), nullable=False) # 'admin', 'tecnico', 'cliente'

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    solucion = db.Column(db.Text, nullable=True) # Respuesta del técnico
    estado = db.Column(db.String(20), default='Abierto')
    cliente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- CREACIÓN AUTOMÁTICA DE TABLAS ---
# Esto se ejecuta cada vez que Render enciende la aplicación
with app.app_context():
    try:
        db.create_all()
        print("--- BASE DE DATOS Y TABLAS VERIFICADAS CORRECTAMENTE ---")
    except Exception as e:
        print(f"--- ERROR AL CONECTAR CON BASE DE DATOS: {e} ---")

# --- RUTAS ---

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_rol = session['rol']
    
    if user_rol == 'cliente':
        lista_tickets = Ticket.query.filter_by(cliente_id=user_id).all()
    else:
        lista_tickets = Ticket.query.all()

    return render_template('dashboard.html', tickets=lista_tickets)

@app.route('/crear_ticket', methods=['GET', 'POST'])
def crear_ticket():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        desc = request.form['descripcion']
        cliente_actual_id = session['user_id']

        nuevo_ticket = Ticket(titulo=titulo, descripcion=desc, cliente_id=cliente_actual_id)
        db.session.add(nuevo_ticket)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template('crear_ticket.html')

@app.route('/ticket/<int:id_ticket>', methods=['GET', 'POST'])
def ver_ticket(id_ticket):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    ticket_seleccionado = Ticket.query.get_or_404(id_ticket)

    if request.method == 'POST':
        rol_usuario = session['rol']
        if rol_usuario in ['tecnico', 'admin']:
            respuesta = request.form['solucion_texto']
            
            ticket_seleccionado.solucion = respuesta
            ticket_seleccionado.estado = 'Cerrado'
            db.session.commit()
            
            return redirect(url_for('home'))

    return render_template('detalle_ticket.html', ticket=ticket_seleccionado)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        usuario = request.form['username']
        clave = request.form['password']
        rol_seleccionado = request.form['rol']

        usuario_existente = User.query.filter_by(username=usuario).first()
        if usuario_existente:
            flash('El nombre de usuario ya existe')
            return redirect(url_for('registro'))

        clave_encriptada = generate_password_hash(clave)

        nuevo_usuario = User(username=usuario, password=clave_encriptada, rol=rol_seleccionado)
        db.session.add(nuevo_usuario)
        db.session.commit()

        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['username']
        clave = request.form['password']

        user = User.query.filter_by(username=usuario).first()

        if user and check_password_hash(user.password, clave):
            session['user_id'] = user.id
            session['username'] = user.username
            session['rol'] = user.rol
            return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrectos')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)