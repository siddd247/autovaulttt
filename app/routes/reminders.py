# pyrefly: ignore[missing-import]
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app.models import db
from app.models.vehicle import Vehicle
from app.models.reminder import Reminder
from app.routes.auth import login_required, get_current_user

reminders_bp = Blueprint('reminders', __name__)

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
