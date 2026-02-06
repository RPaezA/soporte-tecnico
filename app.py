import os
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'soporte_pro_2026_excel_v1'

# --- CONFIGURACIÓN ---
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Luciana%402012@localhost:5432/soporte_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

# --- MODELOS ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default='cliente')

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    ubicacion = db.Column(db.String(200), nullable=True)
    estado = db.Column(db.String(20), default='Abierto')
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    
    creador = db.relationship('Usuario', foreign_keys=[usuario_id], backref='tickets_reportados')
    tecnico = db.relationship('Usuario', foreign_keys=[tecnico_id])
    informe = db.relationship('InformeVisita', backref='ticket', uselist=False, cascade="all, delete-orphan")

class InformeVisita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    fecha_visita = db.Column(db.String(20))
    hora_visita = db.Column(db.String(20))
    trabajo_realizado = db.Column(db.Text)
    repuestos_utilizados = db.Column(db.Text)
    foto_evidencia = db.Column(db.String(255))

# --- RUTAS DE ACCESO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Credenciales incorrectas', 'danger')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        nuevo = Usuario(username=request.form['username'], email=request.form['email'], 
                        password=hashed_pw, rol=request.form.get('rol', 'cliente'))
        db.session.add(nuevo); db.session.commit()
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# --- DASHBOARD PRINCIPAL ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    u = db.session.get(Usuario, session['user_id'])
    limite = datetime.now() - timedelta(hours=24)
    
    stats = {
        'abiertos': Ticket.query.filter_by(estado='Abierto').count(),
        'proceso': Ticket.query.filter_by(estado='En Proceso').count(),
        'cerrados': Ticket.query.filter_by(estado='Cerrado').count(),
        'vencidos': Ticket.query.filter(Ticket.estado != 'Cerrado', Ticket.fecha_creacion < limite).count()
    }
    
    tecnicos = Usuario.query.filter_by(rol='tecnico').all()
    query = Ticket.query.order_by(Ticket.fecha_creacion.desc())
    
    if u.rol == 'admin': tickets = query.all()
    elif u.rol == 'tecnico': tickets = query.filter_by(tecnico_id=u.id).all()
    else: tickets = query.filter_by(usuario_id=u.id).all()
    
    return render_template('dashboard.html', tickets=tickets, usuario=u, tecnicos=tecnicos, stats=stats, limite=limite)

# --- ACCIONES ---
@app.route('/crear_ticket', methods=['POST'])
def crear_ticket():
    if 'user_id' not in session: return redirect(url_for('login'))
    nuevo = Ticket(titulo=request.form['titulo'], descripcion=request.form['descripcion'], 
                   ubicacion=request.form['ubicacion'], usuario_id=session['user_id'])
    db.session.add(nuevo); db.session.commit()
    return redirect(url_for('index'))

@app.route('/asignar_tecnico', methods=['POST'])
def asignar_tecnico():
    t = db.session.get(Ticket, request.form.get('ticket_id'))
    if t:
        t.tecnico_id = request.form.get('tecnico_id')
        t.estado = 'En Proceso'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/finalizar_ticket', methods=['POST'])
def finalizar_ticket():
    t = db.session.get(Ticket, request.form.get('ticket_id'))
    if t:
        t.estado = request.form.get('estado')
        file = request.files.get('foto')
        filename = t.informe.foto_evidencia if t.informe else None
        if file and file.filename != '':
            filename = secure_filename(f"t{t.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        if not t.informe:
            t.informe = InformeVisita(
                ticket_id=t.id, fecha_visita=request.form.get('fecha'),
                hora_visita=request.form.get('hora'), trabajo_realizado=request.form.get('trabajo_realizado'),
                repuestos_utilizados=request.form.get('repuestos'), foto_evidencia=filename
            )
        else:
            t.informe.fecha_visita = request.form.get('fecha')
            t.informe.hora_visita = request.form.get('hora')
            t.informe.trabajo_realizado = request.form.get('trabajo_realizado')
            t.informe.repuestos_utilizados = request.form.get('repuestos')
            t.informe.foto_evidencia = filename
        db.session.commit()
    return redirect(url_for('index'))

# --- EXPORTAR EXCEL (SOLO ADMIN) ---
@app.route('/exportar_excel')
def exportar_excel():
    if 'user_id' not in session: return redirect(url_for('login'))
    u = db.session.get(Usuario, session['user_id'])
    if u.rol != 'admin': return redirect(url_for('index'))

    tickets = Ticket.query.all()
    data = []
    for t in tickets:
        data.append({
            "ID": t.id,
            "Título": t.titulo,
            "Descripción": t.descripcion,
            "Ubicación": t.ubicacion,
            "Cliente": t.creador.username,
            "Técnico": t.tecnico.username if t.tecnico else "No asignado",
            "Estado": t.estado,
            "Fecha Creación": t.fecha_creacion.strftime('%Y-%m-%d %H:%M'),
            "Trabajo Realizado": t.informe.trabajo_realizado if t.informe else "Sin informe",
            "Repuestos": t.informe.repuestos_utilizados if t.informe else "N/A"
        })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Tickets')
    output.seek(0)
    return send_file(output, download_name="Reporte_Soporte.xlsx", as_attachment=True)

@app.route('/api/pendientes')
def api_pendientes():
    if 'user_id' not in session: return jsonify({'count': 0})
    u = db.session.get(Usuario, session['user_id'])
    if u.rol == 'admin': count = Ticket.query.filter(Ticket.estado != 'Cerrado').count()
    elif u.rol == 'tecnico': count = Ticket.query.filter_by(tecnico_id=u.id).filter(Ticket.estado != 'Cerrado').count()
    else: count = Ticket.query.filter_by(usuario_id=u.id).filter(Ticket.estado != 'Cerrado').count()
    return jsonify({'count': count})

@app.route('/ticket/pdf/<int:id>')
def descargar_pdf(id):
    t = db.session.get(Ticket, id)
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Ticket #{t.id}", ln=True, align='C')
    return send_file(BytesIO(pdf.output(dest='S').encode('latin-1', 'replace')), download_name=f"Ticket_{id}.pdf", as_attachment=True)

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)