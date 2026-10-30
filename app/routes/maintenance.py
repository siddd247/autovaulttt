from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from app.models import db
from app.models.vehicle import Vehicle
from app.models.maintenance import MaintenanceRecord
from app.routes.auth import login_required, get_current_user

maintenance_bp = Blueprint('maintenance', __name__)

@maintenance_bp.route('/maintenance')
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

    records = []
    total_spend = 0.0
    services_count = 0
    categories = {}

    if selected_vehicle:
        records = MaintenanceRecord.query.filter_by(vehicle_id=selected_vehicle.id).order_by(MaintenanceRecord.date.desc(), MaintenanceRecord.created_at.desc()).all()
        total_spend = sum(r.cost for r in records)
        services_count = len(records)
        for r in records:
            categories[r.service_type] = categories.get(r.service_type, 0) + r.cost

    return render_template(
        'maintenance.html',
        user=user,
        vehicles=vehicles,
        selected_vehicle=selected_vehicle,
        records=records,
        total_spend=round(total_spend, 2),
        services_count=services_count,
        categories=categories
    )

@maintenance_bp.route('/maintenance/add', methods=['POST'])
@login_required
def add():
    user = get_current_user()
    vehicle_id = request.form.get('vehicle_id', type=int)
    vehicle = db.session.get(Vehicle, vehicle_id)

    # Authorization verification (IDOR protection)
    if not vehicle or vehicle.user_id != user.id:
        abort(403)

    date_str = request.form.get('date', '').strip()
    service_type = request.form.get('service_type', '').strip()
    cost_val = request.form.get('cost', type=float)
    odometer_val = request.form.get('odometer', type=int)
    service_center = request.form.get('service_center', '').strip()
    description = request.form.get('description', '').strip()
    notes = request.form.get('notes', '').strip()

    if not date_str or not service_type or cost_val is None:
        flash('Date, Service Type, and Cost are required fields.', 'danger')
        return redirect(url_for('maintenance.index', selected=vehicle.id))

    odometer = odometer_val if odometer_val is not None else vehicle.current_odometer

    record = MaintenanceRecord(
        vehicle_id=vehicle.id,
        date=date_str,
        service_type=service_type,
        cost=max(0.0, cost_val),
        odometer=odometer,
        service_center=service_center,
        description=description,
        notes=notes
    )
    db.session.add(record)

    # Update odometer if maintenance odometer was higher
    if odometer > vehicle.current_odometer:
        vehicle.current_odometer = odometer
        for v in session.get('_user_vehicles', []):
            if v.get('id') == vehicle.id:
                v['current_odometer'] = odometer
                session.modified = True

    db.session.commit()
    flash(f'Maintenance record for "{service_type}" added successfully!', 'success')
    return redirect(url_for('maintenance.index', selected=vehicle.id))

@maintenance_bp.route('/maintenance/delete/<int:record_id>', methods=['POST'])
@login_required
def delete(record_id):
    user = get_current_user()
    record = db.session.get(MaintenanceRecord, record_id)

    if not record:
        abort(404)

    # Authorization verification
    if record.vehicle.user_id != user.id:
        abort(403)

    vehicle_id = record.vehicle_id
    db.session.delete(record)
    db.session.commit()
    flash('Service record removed from ledger.', 'info')
    return redirect(url_for('maintenance.index', selected=vehicle_id))
