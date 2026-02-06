from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Tabla intermedia Muchos-a-Muchos para Materiales y Reportes
reporte_materiales = db.Table('reporte_materiales',
    db.Column('reporte_id', db.Integer, db.ForeignKey('reporte_solucion.id'), primary_key=True),
    db.Column('material_id', db.Integer, db.ForeignKey('material.id'), primary_key=True)
)

class Material(db.Model):
    __tablename__ = 'material'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)

class Ticket(db.Model):
    __tablename__ = 'ticket'
    id = db.Column(db.Integer, primary_key=True)
    # ... (tus campos actuales: titulo, descripcion, etc.)
    fecha_asignacion = db.Column(db.DateTime, default=datetime.now)
    estatus = db.Column(db.String(20), default='Asignado')
    
    # Relación uno-a-uno con el reporte de solución
    reporte = db.relationship('ReporteSolucion', backref='ticket', uselist=False)

class ReporteSolucion(db.Model):
    __tablename__ = 'reporte_solucion'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    fecha_visita = db.Column(db.Date, nullable=False)
    hora_visita = db.Column(db.Time, nullable=False)
    direccion = db.Column(db.String(255), nullable=False)
    descripcion_solucion = db.Column(db.Text, nullable=False)
    foto_inicio = db.Column(db.String(255)) # Nombre del archivo
    foto_fin = db.Column(db.String(255))    # Nombre del archivo
    
    # Relación con la tabla materiales
    materiales = db.relationship('Material', secondary=reporte_materiales, backref='reportes')