from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app.models import db
from app.routes.auth import login_required, get_current_user

modules_bp = Blueprint('modules', __name__)

@modules_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management and security settings."""
    user = get_current_user()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_info':
            new_name = request.form.get('name', '').strip()
            if new_name:
                user.name = new_name
                db.session.commit()
                if '_auth_user' in session:
                    session['_auth_user']['name'] = new_name
                    session.modified = True
                flash('Profile details updated successfully.', 'success')
            else:
                flash('Name cannot be empty.', 'danger')
        elif action == 'change_password':
            old_pass = request.form.get('old_password', '')
            new_pass = request.form.get('new_password', '')
            confirm_pass = request.form.get('confirm_password', '')

            if not user.check_password(old_pass):
                flash('Current password is incorrect.', 'danger')
            elif len(new_pass) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
            elif new_pass != confirm_pass:
                flash('New passwords do not match.', 'danger')
            else:
                user.set_password(new_pass)
                db.session.commit()
                if '_auth_user' in session:
                    session['_auth_user']['password_hash'] = user.password_hash
                    session.modified = True
                flash('Password changed successfully!', 'success')
        return redirect(url_for('modules.profile'))

    return render_template('profile.html', user=user)

@modules_bp.route('/security')
def security():
    """Dedicated Cyber Security Command Centre showcasing defense-in-depth architecture."""
    user = get_current_user()
    return render_template('security.html', user=user)

@modules_bp.route('/assistant')
def assistant():
    """Future Feature Preview: AI Car Assistant."""
    user = get_current_user()
    return render_template('assistant.html', user=user)

@modules_bp.route('/services')
def services():
    """Future Feature Preview: Nearby Services and Reviews."""
    user = get_current_user()
    return render_template('services.html', user=user)

