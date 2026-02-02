import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_pro_123' 

# CONFIGURACIÓN DE BASE DE DATOS
# Corregido: Se asegura el protocolo 'postgresql://' para evitar errores de SQLAlchemy
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://admin:kFcmK5nDznaWa5oQkn2uwBq5DsaIPsCq@dpg-d5uddpngi27c7394a37g-a.oregon-postgres.render.com/soporte_db_bqhc')

# Pequeño truco para corregir automáticamente si la URL viene como postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DE DATOS ---

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default='cliente') # cliente, tecnico, admin

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), default='Abierto')
    solucion = db.Column(db.Text, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

# --- RUTAS ---

@app.route('/')
def home():
    if 'user_id' in session:
        if session['rol'] in ['tecnico', 'admin']:
            tickets = Ticket.query.all()
        else:
            tickets = Ticket.query.filter_by(usuario_id=session['user_id']).all()
        return render_template('dashboard.html', tickets=tickets)
    return redirect(url_for('login'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        user = request.form['username']
        passw = generate_password_hash(request.form['password'])
        rol = request.form['rol']
        
        nuevo_usuario = Usuario(username=user, password=passw, rol=rol)
        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('¡Registro exitoso! Por favor inicia sesión.')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('El usuario ya existe.')
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['rol'] = user.rol
            return redirect(url_for('home'))
        flash('Credenciales incorrectas.')
    return render_template('login.html')

@app.route('/crear_ticket', methods=['GET', 'POST'])
def crear_ticket():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST':
        nuevo_ticket = Ticket(
            titulo=request.form['titulo'],
            descripcion=request.form['descripcion'],
            usuario_id=session['user_id']
        )
        db.session.add(nuevo_ticket)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('crear_ticket.html')

@app.route('/ver_ticket/<int:id_ticket>', methods=['GET', 'POST'])
def ver_ticket(id_ticket):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    ticket = Ticket.query.get_or_404(id_ticket)
    
    if request.method == 'POST' and session['rol'] in ['tecnico', 'admin']:
        ticket.solucion = request.form['solucion_texto']
        ticket.estado = 'Cerrado'
        db.session.commit()
        return redirect(url_for('home'))
            
    return render_template('detalle_ticket.html', ticket=ticket)

@app.route('/reportes')
def reportes():
    if 'user_id' not in session or session.get('rol') != 'admin':
        flash('Solo los administradores pueden ver reportes.')
        return redirect(url_for('home'))

    total = Ticket.query.count()
    abiertos = Ticket.query.filter_by(estado='Abierto').count()
    cerrados = Ticket.query.filter_by(estado='Cerrado').count()
    porcentaje = (cerrados / total * 100) if total > 0 else 0

    return render_template('reportes.html', 
                           total=total, abiertos=abiertos, 
                           cerrados=cerrados, porcentaje=round(porcentaje, 1))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- INICIO ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Ejecución con debug activo para ver errores en consola
    app.run(debug=True)