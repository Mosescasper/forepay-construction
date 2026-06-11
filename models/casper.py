from datetime import datetime
from database import db

class Account(db.Model):
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    
    # Fields
    full_name = db.Column(db.String(150), nullable=False)
    phone_number = db.Column(db.String(20))
    gender = db.Column(db.String(20))
    occupation = db.Column(db.String(100))
    company = db.Column(db.String(100))
    hobbies = db.Column(db.Text)
    skills = db.Column(db.Text)
    profile_picture = db.Column(db.String(255))
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Account User ID: {self.user_id}, Name: {self.full_name}>'
