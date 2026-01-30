from app import app, db

# Esto entra a la configuración de tu app
with app.app_context():
    print("1. Borrando tablas viejas (con limite de 50 caracteres)...")
    db.drop_all() # Borra todo

    print("2. Creando tablas nuevas (con limite de 255 caracteres)...")
    db.create_all() # Crea todo de nuevo

    print("¡Listo! Base de datos actualizada.")