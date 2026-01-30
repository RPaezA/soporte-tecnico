import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURACIÓN ---
# Conexión a PostgreSQL con tu contraseña
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1) # Corrección para Render

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Luciana%402012@localhost/soporte_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'mi_clave_secreta_super_segura' 

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Esto obliga a Render a crear las tablas automáticamente al encenderse
with app.app_context():
    db.create_all()

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
    # --- LÍNEA NUEVA ---
    solucion = db.Column(db.Text, nullable=True) # Puede estar vacía al principio
    # -------------------
    estado = db.Column(db.String(20), default='Abierto')
    cliente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- RUTAS ---

@app.route('/')
def home():
    # 1. Verificar si el usuario inició sesión
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_rol = session['rol']
    
    # 2. Filtrar tickets según el rol
    if user_rol == 'cliente':
        # El cliente solo ve SUS tickets
        lista_tickets = Ticket.query.filter_by(cliente_id=user_id).all()
    else:
        # Admin y Técnico ven TODOS los tickets
        lista_tickets = Ticket.query.all()

    # 3. Mostrar el Dashboard
    return render_template('dashboard.html', tickets=lista_tickets)

@app.route('/crear_ticket', methods=['GET', 'POST'])
def crear_ticket():
    # Verificar sesión
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        titulo = request.form['titulo']
        desc = request.form['descripcion']
        cliente_actual_id = session['user_id']

        # Guardar en base de datos
        nuevo_ticket = Ticket(titulo=titulo, descripcion=desc, cliente_id=cliente_actual_id)
        db.session.add(nuevo_ticket)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template('crear_ticket.html')

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

# RUTA PARA VER Y RESPONDER TICKETS
@app.route('/ticket/<int:id_ticket>', methods=['GET', 'POST'])
def ver_ticket(id_ticket):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Buscamos el ticket por su ID
    ticket_seleccionado = Ticket.query.get_or_404(id_ticket)

    # Lógica para responder (Solo Técnicos/Admins)
    if request.method == 'POST':
        rol_usuario = session['rol']
        if rol_usuario in ['tecnico', 'admin']:
            respuesta = request.form['solucion_texto']
            
            # Actualizamos el ticket
            ticket_seleccionado.solucion = respuesta
            ticket_seleccionado.estado = 'Cerrado'
            db.session.commit()
            
            flash('Ticket resuelto exitosamente')
            return redirect(url_for('home'))

    return render_template('detalle_ticket.html', ticket=ticket_seleccionado)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)