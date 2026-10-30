import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session, current_app
from werkzeug.utils import secure_filename
from app.models import db
from app.models.vehicle import Vehicle
from app.models.reminder import Reminder
from app.models.document import Document
from app.routes.auth import login_required, get_current_user

reminders_bp = Blueprint('reminders', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@reminders_bp.route('/reminders')
@login_required
def index():
    user = get_current_user()
    vehicles = Vehicle.query.filter_by(user_id=user.id).order_by(Vehicle.created_at.desc()).all()
    selected_id = request.args.get('selected', type=int)

    selected_vehicle = None
    if selected_id:
        selected_vehicle = Vehicle.query.filter_by(id=selected_id, user_id=user.id).first()
    if not selected_vehicle and vehicles:
        selected_vehicle = vehicles[0]

    all_reminders = []
    active_reminders = []
    completed_reminders = []
    overdue_count = 0
    due_soon_count = 0

    if selected_vehicle:
        all_reminders = Reminder.query.filter_by(vehicle_id=selected_vehicle.id).all()
        for r in all_reminders:
            calculated = r.calculate_status()
            r.computed_status = calculated
            if calculated == 'Completed':
                completed_reminders.append(r)
            else:
                active_reminders.append(r)
                if calculated == 'Overdue':
                    overdue_count += 1
                elif calculated == 'Due Soon':
                    due_soon_count += 1

    return render_template(
        'reminders.html',
        user=user,
        vehicles=vehicles,
        selected_vehicle=selected_vehicle,
        active_reminders=active_reminders,
        completed_reminders=completed_reminders,
        overdue_count=overdue_count,
        due_soon_count=due_soon_count
    )

@reminders_bp.route('/reminders/add', methods=['POST'])
@login_required
def add():
    user = get_current_user()
    vehicle_id = request.form.get('vehicle_id', type=int)
    vehicle = db.session.get(Vehicle, vehicle_id)

    # Authorization verification
    if not vehicle or vehicle.user_id != user.id:
        abort(403)

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    due_date = request.form.get('due_date', '').strip()
    due_mileage_val = request.form.get('due_mileage', '').strip()
    priority = request.form.get('priority', 'Medium').strip()

    if not title:
        flash('Reminder title is required.', 'danger')
        return redirect(url_for('reminders.index', selected=vehicle.id))

    due_mileage = int(due_mileage_val) if due_mileage_val and due_mileage_val.isdigit() else None

    reminder = Reminder(
        vehicle_id=vehicle.id,
        title=title,
        description=description,
        due_date=due_date if due_date else None,
        due_mileage=due_mileage,
        priority=priority,
        status='Upcoming'
    )
    db.session.add(reminder)
    db.session.commit()
    flash(f'Reminder "{title}" set successfully!', 'success')
    return redirect(url_for('reminders.index', selected=vehicle.id))

@reminders_bp.route('/reminders/complete/<int:reminder_id>', methods=['POST'])
@login_required
def complete(reminder_id):
    """Complete a reminder with optional new validity date, document upload, or skip option."""
    user = get_current_user()
    reminder = db.session.get(Reminder, reminder_id)

    if not reminder:
        abort(404)

    vehicle = reminder.vehicle
    if not vehicle or vehicle.user_id != user.id:
        abort(403)

    new_expiry_date = request.form.get('new_expiry_date', '').strip()
    skip_document = request.form.get('skip_document') == '1'
    completion_notes = request.form.get('completion_notes', '').strip()

    is_insurance = reminder.is_insurance_reminder()
    is_pollution = reminder.is_pollution_reminder()
    doc_type = 'Insurance' if is_insurance else ('PUCC' if is_pollution else 'Invoice')

    # Update vehicle compliance expiration if date provided
    updated_compliance = False
    if is_insurance and new_expiry_date:
        vehicle.insurance_expiry = new_expiry_date
        updated_compliance = True
    elif is_pollution and new_expiry_date:
        vehicle.pollution_expiry = new_expiry_date
        updated_compliance = True

    # Handle document upload if provided and not skipped
    uploaded_doc_name = None
    if not skip_document and 'document_file' in request.files:
        file = request.files['document_file']
        if file and file.filename != '':
            if allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                random_filename = f"{uuid.uuid4().hex}.{extension}"

                docs_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
                os.makedirs(docs_upload_dir, exist_ok=True)
                disk_path = os.path.join(docs_upload_dir, random_filename)
                file.save(disk_path)
                file_size = os.path.getsize(disk_path)

                doc = Document(
                    vehicle_id=vehicle.id,
                    document_type=doc_type,
                    filename=random_filename,
                    original_filename=original_filename,
                    secure_storage_path=disk_path,
                    file_size=file_size
                )
                db.session.add(doc)
                uploaded_doc_name = original_filename
            else:
                flash('Uploaded file type is unsupported. Allowed: PDF, PNG, JPG, JPEG, WEBP.', 'warning')

    # Update reminder status and optional completion note
    reminder.status = 'Completed'
    if completion_notes:
        if reminder.description:
            reminder.description = f"{reminder.description} • Note: {completion_notes}"
        else:
            reminder.description = f"Note: {completion_notes}"

    # Sync session cached vehicles for cross-container serverless persistence
    cached_vehicles = session.get('_user_vehicles', [])
    for uv in cached_vehicles:
        if uv.get('id') == vehicle.id:
            uv['insurance_expiry'] = vehicle.insurance_expiry
            uv['pollution_expiry'] = vehicle.pollution_expiry
    session['_user_vehicles'] = cached_vehicles
    session.modified = True

    db.session.commit()

    # User feedback flashes
    if is_insurance and updated_compliance:
        flash(f'Insurance renewed! {vehicle.display_name} policy expiry updated to {new_expiry_date}.', 'success')
    elif is_pollution and updated_compliance:
        flash(f'Pollution (PUCC) renewed! {vehicle.display_name} PUCC validity updated to {new_expiry_date}.', 'success')
    else:
        flash(f'Task "{reminder.title}" marked as completed!', 'success')

    if uploaded_doc_name:
        flash(f'Certificate "{uploaded_doc_name}" securely filed into Document Vault.', 'info')

    return redirect(url_for('reminders.index', selected=vehicle.id))

@reminders_bp.route('/reminders/toggle/<int:reminder_id>', methods=['POST'])
@login_required
def toggle(reminder_id):
    user = get_current_user()
    reminder = db.session.get(Reminder, reminder_id)

    if not reminder:
        abort(404)

    # Authorization verification
    if reminder.vehicle.user_id != user.id:
        abort(403)

    if reminder.status == 'Completed':
        reminder.status = 'Upcoming'
        flash(f'Reminder "{reminder.title}" marked as pending.', 'info')
    else:
        # If toggling an active reminder without modal (fallback)
        reminder.status = 'Completed'
        flash(f'Reminder "{reminder.title}" marked as completed!', 'success')

    db.session.commit()
    return redirect(url_for('reminders.index', selected=reminder.vehicle_id))

@reminders_bp.route('/reminders/delete/<int:reminder_id>', methods=['POST'])
@login_required
def delete(reminder_id):
    user = get_current_user()
    reminder = db.session.get(Reminder, reminder_id)

    if not reminder:
        abort(404)

    # Authorization verification
    if reminder.vehicle.user_id != user.id:
        abort(403)

    vehicle_id = reminder.vehicle_id
    db.session.delete(reminder)
    db.session.commit()
    flash('Reminder removed.', 'info')
    return redirect(url_for('reminders.index', selected=vehicle_id))
