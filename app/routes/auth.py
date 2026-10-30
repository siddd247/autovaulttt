from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from app.models import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            session.pop('user_id', None)
            session.pop('username', None)
            session.pop('_auth_user', None)
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Retrieve the currently authenticated user from database, or None.
    Features self-healing session restoration for ephemeral/serverless environments.
    """
    if 'user_id' not in session:
        return None

    user = db.session.get(User, session['user_id'])
    if user:
        return user

    # Self-healing: if serverless instance rotated or cold-booted, restore user from signed session
    auth_user = session.get('_auth_user')
    if auth_user and isinstance(auth_user, dict):
        try:
            # Check by username or email first to avoid duplicates
            existing = User.query.filter(
                (User.username == auth_user.get('username')) | 
                (User.email == auth_user.get('email'))
            ).first()

            if existing:
                session['user_id'] = existing.id
                user = existing
            else:
                user = User(
                    name=auth_user.get('name', 'User'),
                    email=auth_user.get('email'),
                    username=auth_user.get('username'),
                    password_hash=auth_user.get('password_hash')
                )
                if auth_user.get('id'):
                    user.id = auth_user.get('id')
                db.session.add(user)
                db.session.commit()
                session['user_id'] = user.id

            # Restore cached vehicles for this user in ephemeral database
            cached_vehicles = session.get('_user_vehicles', [])
            if cached_vehicles:
                from app.models.vehicle import Vehicle
                for v_data in cached_vehicles:
                    v_id = v_data.get('id')
                    existing_v = Vehicle.query.filter_by(id=v_id).first() if v_id else None
                    if not existing_v:
                        v = Vehicle(
                            user_id=user.id,
                            manufacturer=v_data.get('manufacturer', ''),
                            model=v_data.get('model', ''),
                            variant=v_data.get('variant'),
                            registration_number=v_data.get('registration_number'),
                            fuel_type=v_data.get('fuel_type', 'Petrol'),
                            transmission=v_data.get('transmission', 'Manual'),
                            manufacturing_year=v_data.get('manufacturing_year'),
                            purchase_date=v_data.get('purchase_date'),
                            current_odometer=v_data.get('current_odometer', 0),
                            color=v_data.get('color'),
                            insurance_expiry=v_data.get('insurance_expiry'),
                            pollution_expiry=v_data.get('pollution_expiry')
                        )
                        if v_id:
                            v.id = v_id
                        db.session.add(v)
                db.session.commit()

            return user
        except Exception:
            db.session.rollback()

    return None

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with validation and password hashing."""
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Basic validations
        if not name or not email or not username or not password or not confirm_password:
            flash('All fields are required.', 'danger')
            return render_template('register.html', name=name, email=email, username=username)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html', name=name, email=email, username=username)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', name=name, email=email, username=username)

        # Check uniqueness
        if User.query.filter_by(email=email).first():
            flash('An account with this email address already exists.', 'danger')
            return render_template('register.html', name=name, username=username)

        if User.query.filter_by(username=username).first():
            flash('This username is already taken. Please choose another.', 'danger')
            return render_template('register.html', name=name, email=email)

        # Create new user with hashed password
        new_user = User(name=name, email=email, username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Seamless login on registration: prevents immediately forcing the user to sign in
        session.clear()
        session.permanent = True
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        session['_auth_user'] = {
            'id': new_user.id,
            'name': new_user.name,
            'email': new_user.email,
            'username': new_user.username,
            'password_hash': new_user.password_hash
        }
        session['_user_vehicles'] = []

        flash(f'Account created successfully! Welcome to AutoVault, {new_user.name}.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with secure generic error messages."""
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        password = request.form.get('password', '')

        if not identifier or not password:
            flash('Please provide both username/email and password.', 'danger')
            return render_template('login.html', identifier=identifier)

        # Query by username or email
        user = User.query.filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()

        # Secure verification: generic error message to prevent account enumeration
        if user and user.check_password(password):
            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['_auth_user'] = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'username': user.username,
                'password_hash': user.password_hash
            }

            from app.models.vehicle import Vehicle
            user_vehicles = Vehicle.query.filter_by(user_id=user.id).all()
            session['_user_vehicles'] = [{
                'id': v.id,
                'manufacturer': v.manufacturer,
                'model': v.model,
                'variant': v.variant,
                'registration_number': v.registration_number,
                'fuel_type': v.fuel_type,
                'transmission': v.transmission,
                'manufacturing_year': v.manufacturing_year,
                'purchase_date': v.purchase_date,
                'current_odometer': v.current_odometer,
                'color': v.color,
                'insurance_expiry': v.insurance_expiry,
                'pollution_expiry': v.pollution_expiry
            } for v in user_vehicles]

            flash(f'Welcome back, {user.name}!', 'success')

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username/email or password.', 'danger')
            return render_template('login.html', identifier=identifier)

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Securely log out by destroying session data."""
    session.clear()
    flash('You have been securely logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/demo')
def demo():
    """Instant one-click demo login showcasing multi-vehicle fleet with realistic telemetry & document expiries."""
    from app.models.vehicle import Vehicle
    from seed import seed_demo_data_in_context
    demo_user = User.query.filter_by(username='demo_driver').first()
    if not demo_user or Vehicle.query.filter_by(user_id=demo_user.id).count() < 3:
        try:
            seed_demo_data_in_context()
            demo_user = User.query.filter_by(username='demo_driver').first()
        except Exception:
            pass

    if not demo_user:
        flash('Demo environment is initializing. Please try again.', 'warning')
        return redirect(url_for('dashboard.landing'))

    session.clear()
    session.permanent = True
    session['user_id'] = demo_user.id
    session['username'] = demo_user.username
    session['is_demo'] = True
    session['_auth_user'] = {
        'id': demo_user.id,
        'name': demo_user.name,
        'email': demo_user.email,
        'username': demo_user.username,
        'password_hash': demo_user.password_hash
    }

    user_vehicles = Vehicle.query.filter_by(user_id=demo_user.id).order_by(Vehicle.created_at.asc()).all()
    session['_user_vehicles'] = [{
        'id': v.id,
        'manufacturer': v.manufacturer,
        'model': v.model,
        'variant': v.variant,
        'registration_number': v.registration_number,
        'fuel_type': v.fuel_type,
        'transmission': v.transmission,
        'manufacturing_year': v.manufacturing_year,
        'purchase_date': v.purchase_date,
        'current_odometer': v.current_odometer,
        'color': v.color,
        'insurance_expiry': v.insurance_expiry,
        'pollution_expiry': v.pollution_expiry
    } for v in user_vehicles]

    flash('Welcome to AutoVault Live Demo! Exploring simulated multi-vehicle fleet (Car, Bike, SUV).', 'success')
    return redirect(url_for('dashboard.index'))

@auth_bp.route('/leave-demo')
@auth_bp.route('/demo/leave')
def leave_demo():
    """Exit demo mode and return cleanly to the landing page."""
    session.clear()
    flash('You have safely exited demo mode. Create your private vault or sign in anytime!', 'info')
    return redirect(url_for('dashboard.landing'))
