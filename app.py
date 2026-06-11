import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify  # type: ignore[import]
from flask_mail import Message  # type: ignore[import]
from config import config
from extensions import db
from database import init_db
from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore[import]
from datetime import datetime, timezone
from modules.authy import is_admin_credentials

def create_app(config_name=None):
    app = Flask(__name__)

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app.config.from_object(config[config_name])
    init_db(app)
    
    # Initialize mail
    from extensions import mail
    mail.init_app(app)

    # Register the stripped-down authy blueprint (logout only)
    from apis.authy import authy_bp
    app.register_blueprint(authy_bp)

    @app.route('/')
    def index():
        # If already logged in, skip straight to dashboard
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('index.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # Already logged in? Skip the login page entirely
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            if not username or not password:
                flash('Please enter your username and password.', 'error')
                return render_template('login.html')

            if is_admin_credentials(username, password):
                from models import User

                admin_user = User.query.filter_by(username=username).first()
                if not admin_user:
                    admin_user = User.query.filter_by(email=username).first()
                
                if not admin_user:
                    try:
                        admin_user = User(
                            username=username,
                            email=username,
                            full_name=os.getenv('ADMIN_NAME', 'Admin User'),
                            hashed_password=generate_password_hash(password),
                            role='admin',
                            is_active=True,
                        )
                        db.session.add(admin_user)
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        admin_user = User.query.filter_by(email=username).first()
                        if not admin_user:
                            raise e

                try:
                    session['user_id'] = int(admin_user.id)
                except (TypeError, ValueError):
                    session['user_id'] = admin_user.id
                session['username'] = username
                session['role'] = 'admin'
                session['is_admin'] = True
                return redirect(url_for('dashboard'))

            flash('Invalid username or password.', 'error')

        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            from models import User
            username         = request.form.get('username', '').strip()
            email            = request.form.get('email', '').strip()
            password         = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('login.html')

            if User.query.filter_by(username=username).first():
                flash('Username already taken.', 'error')
                return render_template('login.html')

            if User.query.filter_by(email=email).first():
                flash('Email already registered.', 'error')
                return render_template('login.html')

            user = User(
                username=username,
                email=email,
                hashed_password=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            flash('Account created! You can now sign in.', 'success')
            return redirect(url_for('login'))

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))

        from models import Worker, Payment
        workers     = Worker.query.filter_by(is_active=True).all()
        total_wages = sum(w.wage_amount * 22 for w in workers)
        paid_today  = Payment.query.filter(
            db.func.date(Payment.payment_date) == datetime.now(timezone.utc).date()
        ).count()

        return render_template('admin/dashboard.html',
                               workers=workers,
                               total_wages=total_wages,
                               paid_today=paid_today)

    @app.route('/workers')
    def workers():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        from models import Worker
        all_workers = Worker.query.filter_by(is_active=True).all()
        return render_template('admin/workers.html', workers=all_workers)

    @app.route('/send-test-email', methods=['GET', 'POST'])
    def send_test_email():
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))

        if request.method == 'POST':
            test_email = request.form.get('email', '').strip()
            if not test_email:
                flash('Enter a recipient email address.', 'error')
                return render_template('send_test_email.html')

            from extensions import mail

            try:
                msg = Message(
                    subject='ForePay Mailgun Test Email',
                    recipients=[test_email],
                    body='This is a test email sent from ForePay using Mailgun SMTP.',
                    html=f'<p>This is a test email sent from ForePay using Mailgun SMTP.</p>',
                )
                mail.send(msg)
                flash(f'Test email sent to {test_email}.', 'success')
            except Exception as e:
                app.logger.exception('Failed to send test email')
                flash(f'Test email failed: {str(e)}', 'error')

            return redirect(url_for('send_test_email'))

        return render_template('send_test_email.html')

    @app.route('/workers/add', methods=['GET', 'POST'])
    def add_worker():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if request.method == 'POST':
            from models import Worker
            from extensions import mail
            
            full_name = request.form.get('full_name')
            phone_number = request.form.get('phone_number')
            worker_email = request.form.get('email', '').strip()
            role = request.form.get('role')
            wage_type = request.form.get('wage_type')
            wage_amount = float(request.form.get('wage_amount', 0))
            
            try:
                worker_user_id = int(session['user_id'])
            except (TypeError, ValueError):
                worker_user_id = session['user_id']

            worker = Worker(
                full_name    = full_name,
                phone_number = phone_number,
                role         = role,
                wage_type    = wage_type,
                wage_amount  = wage_amount,
                user_id      = worker_user_id
            )
            db.session.add(worker)
            db.session.commit()
            
            result_message = 'Worker added successfully!'
            flash_category = 'success'

            if worker_email:
                try:
                    msg = Message(
                        subject='Welcome to ForePay',
                        recipients=[worker_email],
                        body=f"Welcome to ForePay, {full_name}!\n\nYou have been added as a {role} worker.\n\nYour details:\n- Role: {role}\n- Wage Type: {wage_type}\n- Phone: {phone_number}\n\nIf you have any questions, please contact your administrator.\n\nBest regards,\nForePay Team",
                        html=f"""
                        <h2>Welcome to ForePay, {full_name}!</h2>
                        <p>You have been added as a {role} worker.</p>
                        <p><strong>Your Details:</strong></p>
                        <ul>
                            <li>Role: {role}</li>
                            <li>Wage Type: {wage_type}</li>
                            <li>Phone: {phone_number}</li>
                        </ul>
                        <p>If you have any questions, please contact your administrator.</p>
                        <p>Best regards,<br>ForePay Team</p>
                        """
                    )
                    mail.send(msg)
                    result_message = f'Worker added and email sent to {worker_email}!'
                except Exception as e:
                    app.logger.exception('Failed to send worker email')
                    result_message = f'Worker added but email failed to send: {str(e)}'
                    flash_category = 'warning'

            if request.headers.get('Accept', '').find('application/json') >= 0:
                status_code = 200 if flash_category == 'success' else 500
                return jsonify({'status': flash_category, 'message': result_message}), status_code

            flash(result_message, flash_category)
            return redirect(url_for('workers'))
        return render_template('admin/add_worker.html')

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template('500.html'), 500

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)