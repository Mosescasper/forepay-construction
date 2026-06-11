from extensions import db          # ← get db from extensions
from flask_migrate import Migrate

migrate = Migrate()

def init_db(app):
    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
        from models import User, Worker, Attendance, Payment
        db.create_all()
    return db