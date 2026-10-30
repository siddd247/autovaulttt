from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from app.models import db
from app.models.vehicle import Vehicle
from app.routes.auth import login_required, get_current_user

vehicle_bp = Blueprint('vehicle', __name__)

@vehicle_bp.route('/vehicle')
@login_required
def index():
    """List all vehicles owned by the logged-in user."""
    user = get_current_user()
    vehicles = Vehicle.query.filter_by(user_id=user.id).order_by(Vehicle.created_at.desc()).all()
    selected_id = request.args.get('selected', type=int)
    
    selected_vehicle = None
    if selected_id:
        selected_vehicle = Vehicle.query.filter_by(id=selected_id, user_id=user.id).first()
    if not selected_vehicle and vehicles:
        selected_vehicle = vehicles[0]

    return render_template(
        'vehicle.html',
        user=user,
        vehicles=vehicles,
        selected_vehicle=selected_vehicle
    )

@vehicle_bp.route('/vehicle/add', methods=['POST'])
@login_required
def add():
    """Add a new vehicle under the authenticated user's ownership."""
    user = get_current_user()
    
    manufacturer = request.form.get('manufacturer', '').strip()
    model = request.form.get('model', '').strip()
    variant = request.form.get('variant', '').strip()
    registration_number = request.form.get('registration_number', '').strip().upper()
    fuel_type = request.form.get('fuel_type', 'Petrol').strip()
    transmission = request.form.get('transmission', 'Manual').strip()
    manufacturing_year_val = request.form.get('manufacturing_year', '').strip()
    purchase_date = request.form.get('purchase_date', '').strip()
    odometer_val = request.form.get('current_odometer', '').strip()
    color = request.form.get('color', '').strip()
    insurance_expiry = request.form.get('insurance_expiry', '').strip()
    pollution_expiry = request.form.get('pollution_expiry', '').strip()

    if not manufacturer or not model:
        flash('Manufacturer and Model are required fields.', 'danger')
        return redirect(url_for('vehicle.index'))

    # Parse numeric fields safely
    manufacturing_year = None
    if manufacturing_year_val:
        try:
            manufacturing_year = int(manufacturing_year_val)
        except ValueError:
            flash('Invalid manufacturing year.', 'danger')
            return redirect(url_for('vehicle.index'))

    current_odometer = 0
    if odometer_val:
        try:
            current_odometer = max(0, int(odometer_val))
        except ValueError:
            flash('Invalid odometer reading.', 'danger')
            return redirect(url_for('vehicle.index'))

    vehicle = Vehicle(
        user_id=user.id,
        manufacturer=manufacturer,
        model=model,
        variant=variant,
        registration_number=registration_number,
        fuel_type=fuel_type,
        transmission=transmission,
        manufacturing_year=manufacturing_year,
        purchase_date=purchase_date,
        current_odometer=current_odometer,
        color=color,
        insurance_expiry=insurance_expiry,
        pollution_expiry=pollution_expiry
    )

    db.session.add(vehicle)
    db.session.commit()

    # Synchronize vehicle into session cache for cross-container serverless persistence
    cached = session.get('_user_vehicles', [])
    cached.append({
        'id': vehicle.id,
        'manufacturer': vehicle.manufacturer,
        'model': vehicle.model,
        'variant': vehicle.variant,
        'registration_number': vehicle.registration_number,
        'fuel_type': vehicle.fuel_type,
        'transmission': vehicle.transmission,
        'manufacturing_year': vehicle.manufacturing_year,
        'purchase_date': vehicle.purchase_date,
        'current_odometer': vehicle.current_odometer,
        'color': vehicle.color,
        'insurance_expiry': vehicle.insurance_expiry,
        'pollution_expiry': vehicle.pollution_expiry
    })
    session['_user_vehicles'] = cached
    session.modified = True

    flash(f'Vehicle "{vehicle.display_name}" added to your vault successfully!', 'success')
    return redirect(url_for('vehicle.index', selected=vehicle.id))

@vehicle_bp.route('/vehicle/edit/<int:vehicle_id>', methods=['POST'])
@login_required
def edit(vehicle_id):
    """Update vehicle specifications, odometer, and compliance dates."""
    user = get_current_user()
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle:
        abort(404)

    # Ownership validation
    if vehicle.user_id != user.id:
        abort(403)

    manufacturer = request.form.get('manufacturer', '').strip()
    model = request.form.get('model', '').strip()
    variant = request.form.get('variant', '').strip()
    registration_number = request.form.get('registration_number', '').strip().upper()
    fuel_type = request.form.get('fuel_type', vehicle.fuel_type).strip()
    transmission = request.form.get('transmission', vehicle.transmission).strip()
    manufacturing_year_val = request.form.get('manufacturing_year', '').strip()
    odometer_val = request.form.get('current_odometer', '').strip()
    color = request.form.get('color', '').strip()
    insurance_expiry = request.form.get('insurance_expiry', '').strip()
    pollution_expiry = request.form.get('pollution_expiry', '').strip()

    if not manufacturer or not model:
        flash('Manufacturer and Model are required.', 'danger')
        return redirect(url_for('vehicle.index', selected=vehicle.id))

    if manufacturing_year_val:
        try:
            vehicle.manufacturing_year = int(manufacturing_year_val)
        except ValueError:
            pass

    if odometer_val:
        try:
            vehicle.current_odometer = max(0, int(odometer_val))
        except ValueError:
            pass

    vehicle.manufacturer = manufacturer
    vehicle.model = model
    vehicle.variant = variant
    vehicle.registration_number = registration_number
    vehicle.fuel_type = fuel_type
    vehicle.transmission = transmission
    vehicle.color = color
    vehicle.insurance_expiry = insurance_expiry or None
    vehicle.pollution_expiry = pollution_expiry or None

    db.session.commit()

    # Synchronize session cache
    cached = session.get('_user_vehicles', [])
    for uv in cached:
        if uv.get('id') == vehicle.id:
            uv.update({
                'manufacturer': vehicle.manufacturer,
                'model': vehicle.model,
                'variant': vehicle.variant,
                'registration_number': vehicle.registration_number,
                'fuel_type': vehicle.fuel_type,
                'transmission': vehicle.transmission,
                'manufacturing_year': vehicle.manufacturing_year,
                'current_odometer': vehicle.current_odometer,
                'color': vehicle.color,
                'insurance_expiry': vehicle.insurance_expiry,
                'pollution_expiry': vehicle.pollution_expiry
            })
    session['_user_vehicles'] = cached
    session.modified = True

    flash(f'Specifications and compliance records for {vehicle.display_name} updated successfully!', 'success')
    return redirect(url_for('vehicle.index', selected=vehicle.id))

@vehicle_bp.route('/vehicle/delete/<int:vehicle_id>', methods=['POST'])
@login_required
def delete(vehicle_id):
    """Securely delete a vehicle with strict ownership validation (IDOR prevention)."""
    user = get_current_user()
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle:
        abort(404)

    # Security: Verify ownership (IDOR prevention)
    if vehicle.user_id != user.id:
        abort(403)

    name = vehicle.display_name
    db.session.delete(vehicle)
    db.session.commit()

    # Synchronize removal from session cache
    cached = session.get('_user_vehicles', [])
    session['_user_vehicles'] = [v for v in cached if v.get('id') != vehicle_id]
    session.modified = True

    flash(f'Vehicle "{name}" has been removed from your vault.', 'info')
    return redirect(url_for('vehicle.index'))
