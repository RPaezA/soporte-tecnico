import os
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from fpdf import FPDF
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = 'soporte_pro_2026_full_shield_v10'

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
    prioridad = db.Column(db.String(20), default='Media')
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

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'REPORTE TECNICO DE SERVICIO', 0, 1, 'C')
        self.ln(5)

# --- RUTAS DE ACCESO ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        nuevo = Usuario(username=request.form['username'], email=request.form['email'], password=hashed_pw, rol=request.form.get('rol', 'cliente'))
        db.session.add(nuevo); db.session.commit()
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# --- DASHBOARD ---
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
    
    tecnicos = Usuario.query.filter(Usuario.rol.ilike('tecnico')).all()
    filtro = request.args.get('ver')
    query = Ticket.query.order_by(db.case({ 'Alta': 1, 'Media': 2, 'Baja': 3 }, value=Ticket.prioridad).asc(), Ticket.fecha_creacion.desc())
    
    if u.rol.lower() in ['admin', 'administrador']:
        if filtro == 'vencidos':
            tickets = query.filter(Ticket.estado != 'Cerrado', Ticket.fecha_creacion < limite).all()
        elif filtro in ['Abierto', 'En Proceso', 'Cerrado']:
            tickets = query.filter_by(estado=filtro).all()
        else:
            tickets = query.all()
    elif u.rol.lower() == 'tecnico':
        tickets = query.filter_by(tecnico_id=u.id).all()
    else:
        tickets = query.filter_by(usuario_id=u.id).all()
        
    return render_template('dashboard.html', tickets=tickets, usuario=u, tecnicos=tecnicos, stats=stats, limite=limite, filtro=filtro)

# --- ESTA ES LA RUTA QUE RECUPERA TODO EL CONTENIDO DEL PDF ---
@app.route('/ticket/pdf/<int:id>')
def descargar_pdf(id):
    t = db.session.get(Ticket, id)
    pdf = PDF()
    pdf.add_page()
    
    # Encabezado Ticket
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"TICKET #{t.id} - ESTADO: {t.estado}", 1, 1, 'L')
    pdf.ln(2)
    
    # Datos del Cliente
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 8, "Fecha Reporte:"); pdf.set_font('Arial', '', 10); pdf.cell(0, 8, f"{t.fecha_creacion.strftime('%d/%m/%Y %H:%M')}", 0, 1)
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 8, "Prioridad:"); pdf.set_font('Arial', '', 10); pdf.cell(0, 8, f"{t.prioridad}", 0, 1)
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 8, "Sede/Ubicacion:"); pdf.set_font('Arial', '', 10); pdf.cell(0, 8, f"{t.ubicacion}", 0, 1)
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 8, "Reportado por:"); pdf.set_font('Arial', '', 10); pdf.cell(0, 8, f"{t.creador.username}", 0, 1)
    pdf.ln(2)
    
    # Descripción
    pdf.set_font('Arial', 'B', 10); pdf.cell(0, 8, "Descripcion del Problema:", 0, 1)
    pdf.set_font('Arial', '', 10); pdf.multi_cell(0, 6, t.descripcion)
    pdf.ln(5)
    
    # DATOS DEL INFORME TÉCNICO (LO QUE SE HABÍA PERDIDO)
    if t.informe:
        pdf.set_fill_color(230, 230, 230)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "DETALLES DE LA INTERVENCION TECNICA", 0, 1, 'L', True)
        pdf.ln(2)
        
        pdf.set_font('Arial', 'B', 10); pdf.cell(40, 8, "Fecha Visita:"); pdf.set_font('Arial', '', 10); pdf.cell(0, 8, f"{t.informe.fecha_visita} {t.informe.hora_visita}", 0, 1)
        pdf.set_font('Arial', 'B', 10); pdf.cell(40, 8, "Tecnico:"); pdf.set_font('Arial', '', 10); pdf.cell(0, 8, f"{t.tecnico.username if t.tecnico else 'N/A'}", 0, 1)
        
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 10); pdf.cell(0, 8, "Trabajo Realizado:", 0, 1)
        pdf.set_font('Arial', '', 10); pdf.multi_cell(0, 6, t.informe.trabajo_realizado)
        
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 10); pdf.cell(0, 8, "Repuestos/Materiales:", 0, 1)
        pdf.set_font('Arial', '', 10); pdf.multi_cell(0, 6, t.informe.repuestos_utilizados if t.informe.repuestos_utilizados else "Ninguno")
        
        # Inserción de Foto si existe
        if t.informe.foto_evidencia:
            ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], t.informe.foto_evidencia)
            if os.path.exists(ruta_foto):
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 10); pdf.cell(0, 8, "Evidencia Fotografica:", 0, 1)
                pdf.image(ruta_foto, x=10, w=100) # Ajusta el ancho a 100mm
    else:
        pdf.set_font('Arial', 'I', 10); pdf.cell(0, 10, "No se ha generado informe tecnico todavia.", 0, 1)

    output = BytesIO()
    pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
    output.write(pdf_out)
    output.seek(0)
    return send_file(output, download_name=f"Reporte_Ticket_{id}.pdf", as_attachment=True)

# --- OTRAS RUTAS (SIN CAMBIOS) ---
import matplotlib.pyplot as plt # Añade esta línea al inicio del archivo

@app.route('/informe_ejecutivo')
def informe_ejecutivo():
    if 'user_id' not in session: return redirect(url_for('login'))
    u = db.session.get(Usuario, session['user_id'])
    if u.rol.lower() not in ['admin', 'administrador']: return "Acceso denegado"

    # 1. RECOPILACIÓN DE DATOS
    total = Ticket.query.count()
    abiertos = Ticket.query.filter_by(estado='Abierto').count()
    proceso = Ticket.query.filter_by(estado='En Proceso').count()
    cerrados = Ticket.query.filter_by(estado='Cerrado').count()
    
    limite_vencido = datetime.now() - timedelta(hours=24)
    vencidos = Ticket.query.filter(Ticket.estado != 'Cerrado', Ticket.fecha_creacion < limite_vencido).count()

    # 2. GENERACIÓN DE GRÁFICO (Se guarda temporalmente)
    labels = ['Abiertos', 'En Proceso', 'Cerrados']
    sizes = [abiertos, proceso, cerrados]
    colors = ['#ffc107', '#17a2b8', '#28a745']
    
    plt.figure(figsize=(5, 4))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors)
    plt.title('Distribución por Estado')
    chart_path = os.path.join(app.config['UPLOAD_FOLDER'], 'chart_temp.png')
    plt.savefig(chart_path)
    plt.close()

    # 3. CREACIÓN DEL PDF EJECUTIVO
    pdf = PDF()
    pdf.add_page()
    
    # --- ENCABEZADO MODO EJECUTIVO ---
    # Si tienes un logo, descomenta la siguiente línea y pon la ruta:
    # pdf.image('static/logo.png', 10, 8, 33) 
    pdf.set_font('Arial', 'B', 20)
    pdf.set_text_color(33, 37, 41)
    pdf.cell(0, 10, 'REPORTE GERENCIAL DE OPERACIONES', 0, 1, 'C')
    pdf.set_font('Arial', 'I', 10)
    pdf.cell(0, 10, f'Periodo: {datetime.now().strftime("%B %Y")} | Departamento de IT', 0, 1, 'C')
    pdf.ln(10)

    # --- RESUMEN NUMÉRICO ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' 1. RESUMEN ESTADISTICO', 0, 1, 'L', True)
    pdf.ln(2)
    pdf.set_font('Arial', '', 11)
    pdf.cell(95, 8, f"Total de Tickets Gestionados: {total}", 0, 0)
    pdf.cell(95, 8, f"Tickets Finalizados: {cerrados}", 0, 1)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(95, 8, f"Tickets Vencidos (+24h): {vencidos}", 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    # --- GRÁFICO ---
    pdf.image(chart_path, x=50, y=75, w=110)
    pdf.ln(85)

    # --- ESTADÍSTICA DE EFECTIVIDAD POR TÉCNICO ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' 2. DESEMPEÑO POR TECNICO (EFECTIVIDAD)', 0, 1, 'L', True)
    pdf.ln(2)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(60, 8, 'Tecnico', 1); pdf.cell(40, 8, 'Asignados', 1); pdf.cell(40, 8, 'Cerrados', 1); pdf.cell(50, 8, '% Efectividad', 1); pdf.ln()
    
    pdf.set_font('Arial', '', 10)
    tecnicos = Usuario.query.filter(Usuario.rol.ilike('tecnico')).all()
    for tec in tecnicos:
        asig = Ticket.query.filter_by(tecnico_id=tec.id).count()
        done = Ticket.query.filter_by(tecnico_id=tec.id, estado='Cerrado').count()
        efectividad = (done / asig * 100) if asig > 0 else 0
        
        pdf.cell(60, 8, tec.username, 1)
        pdf.cell(40, 8, str(asig), 1)
        pdf.cell(40, 8, str(done), 1)
        pdf.cell(50, 8, f"{efectividad:.1f}%", 1)
        pdf.ln()

    # --- CONCLUSIONES ---
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' 3. CONCLUSIONES Y RECOMENDACIONES', 0, 1, 'L', True)
    pdf.set_font('Arial', '', 11)
    pdf.ln(2)
    if vencidos > (total * 0.2):
        pdf.multi_cell(0, 7, "ALERTA: Se detecta un alto volumen de tickets vencidos. Se recomienda reforzar la disponibilidad técnica o revisar los tiempos de respuesta actuales.")
    else:
        pdf.multi_cell(0, 7, "La operacion se mantiene dentro de los parametros normales. El indice de cierre es satisfactorio.")
    
    pdf.ln(5)
    pdf.multi_cell(0, 7, "Se sugiere mantener el seguimiento de los tickets 'En Proceso' para evitar que superen el umbral de 24 horas.")

    output = BytesIO()
    pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
    output.write(pdf_out)
    output.seek(0)
    return send_file(output, download_name="Informe_Ejecutivo_Gerencial.pdf", as_attachment=True)

@app.route('/asignar_tecnico', methods=['POST'])
def asignar_tecnico():
    t = db.session.get(Ticket, request.form.get('ticket_id'))
    if t:
        tec_id = request.form.get('tecnico_id')
        t.tecnico_id = tec_id if tec_id else None
        t.estado = 'En Proceso' if tec_id else 'Abierto'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/finalizar_ticket', methods=['POST'])
def finalizar_ticket():
    t = db.session.get(Ticket, request.form.get('ticket_id'))
    if t:
        t.estado = request.form.get('estado')
        file = request.files.get('foto')
        if not t.informe: t.informe = InformeVisita(ticket_id=t.id)
        
        if file and file.filename != '':
            filename = secure_filename(f"t{t.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            t.informe.foto_evidencia = filename
            
        t.informe.fecha_visita = request.form.get('fecha')
        t.informe.hora_visita = request.form.get('hora')
        t.informe.trabajo_realizado = request.form.get('trabajo_realizado')
        t.informe.repuestos_utilizados = request.form.get('repuestos')
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/crear_ticket', methods=['POST'])
def crear_ticket():
    nuevo = Ticket(titulo=request.form['titulo'], descripcion=request.form['descripcion'], 
                   ubicacion=request.form['ubicacion'], prioridad=request.form.get('prioridad', 'Media'),
                   usuario_id=session['user_id'])
    db.session.add(nuevo); db.session.commit()
    return redirect(url_for('index'))

@app.route('/eliminar_ticket/<int:id>', methods=['POST'])
def eliminar_ticket(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    u = db.session.get(Usuario, session['user_id'])
    
    # Verificación de seguridad: solo admin puede borrar
    if u.rol.lower() in ['admin', 'administrador']:
        t = db.session.get(Ticket, id)
        if t:
            db.session.delete(t)
            db.session.commit()
            flash('Ticket eliminado correctamente', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)