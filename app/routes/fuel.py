from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from app.models import db
from app.models.vehicle import Vehicle
from app.models.fuel import FuelEntry
from app.routes.auth import login_required, get_current_user

fuel_bp = Blueprint('fuel', __name__)

def calculate_fuel_stats(entries):
    """Calculates total spend, total litres, average price per litre, and interval mileage."""
    if not entries:
        return {
            'total_cost': 0.0,
            'total_litres': 0.0,
            'avg_price': 0.0,
            'avg_mileage': None,
            'entries_with_mileage': []
        }

    total_cost = sum(e.total_cost for e in entries)
    total_litres = sum(e.litres for e in entries)
    avg_price = (total_cost / total_litres) if total_litres > 0 else 0.0

    # Sort entries chronologically / by odometer for interval mileage math
    sorted_entries = sorted(entries, key=lambda x: (x.odometer, x.date))
    entries_with_mileage = []

    total_distance_logged = 0
    total_litres_for_distance = 0.0

    for i, e in enumerate(sorted_entries):
        mileage = None
        distance = None
        if i > 0:
            prev = sorted_entries[i - 1]
            diff = e.odometer - prev.odometer
            if diff > 0 and e.litres > 0:
                distance = diff
                mileage = round(diff / e.litres, 2)
                total_distance_logged += diff
                total_litres_for_distance += e.litres

        entries_with_mileage.append({
            'entry': e,
            'distance': distance,
            'mileage': mileage
        })

    # Most recent entries first for the UI table
    entries_with_mileage.reverse()

    avg_mileage = None
    if total_distance_logged > 0 and total_litres_for_distance > 0:
        avg_mileage = round(total_distance_logged / total_litres_for_distance, 2)

    return {
        'total_cost': round(total_cost, 2),
        'total_litres': round(total_litres, 2),
        'avg_price': round(avg_price, 2),
        'avg_mileage': avg_mileage,
        'entries_with_mileage': entries_with_mileage
    }

@fuel_bp.route('/fuel')
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

    stats = None
    if selected_vehicle:
        entries = FuelEntry.query.filter_by(vehicle_id=selected_vehicle.id).all()
        stats = calculate_fuel_stats(entries)

    return render_template(
        'fuel.html',
        user=user,
        vehicles=vehicles,
        selected_vehicle=selected_vehicle,
        stats=stats
    )

@fuel_bp.route('/fuel/add', methods=['POST'])
@login_required
def add():
    user = get_current_user()
    vehicle_id = request.form.get('vehicle_id', type=int)
    vehicle = db.session.get(Vehicle, vehicle_id)

    # Authorization verification (IDOR protection)
    if not vehicle or vehicle.user_id != user.id:
        abort(403)

    date_str = request.form.get('date', '').strip()
    odometer = request.form.get('odometer', type=int)
    litres = request.form.get('litres', type=float)
    price_per_litre = request.form.get('price_per_litre', type=float)
    total_cost_val = request.form.get('total_cost', type=float)
    station = request.form.get('station', '').strip()
    notes = request.form.get('notes', '').strip()

    if not date_str or odometer is None or not litres or not price_per_litre:
        flash('Date, odometer, litres, and price per litre are required.', 'danger')
        return redirect(url_for('fuel.index', selected=vehicle.id))

    total_cost = total_cost_val if total_cost_val else round(litres * price_per_litre, 2)

    entry = FuelEntry(
        vehicle_id=vehicle.id,
        date=date_str,
        odometer=odometer,
        litres=litres,
        price_per_litre=price_per_litre,
        total_cost=total_cost,
        station=station,
        notes=notes
    )
    db.session.add(entry)

    # If the fuel entry odometer exceeds current odometer, update vehicle current odometer automatically
    if odometer > vehicle.current_odometer:
        vehicle.current_odometer = odometer
        for v in session.get('_user_vehicles', []):
            if v.get('id') == vehicle.id:
                v['current_odometer'] = odometer
                session.modified = True

    db.session.commit()
    flash(f'Fuel entry of {litres}L recorded successfully!', 'success')
    return redirect(url_for('fuel.index', selected=vehicle.id))

@fuel_bp.route('/fuel/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete(entry_id):
    user = get_current_user()
    entry = db.session.get(FuelEntry, entry_id)

    if not entry:
        abort(404)

    # Authorization verification
    if entry.vehicle.user_id != user.id:
        abort(403)

    vehicle_id = entry.vehicle_id
    db.session.delete(entry)
    db.session.commit()
    flash('Fuel entry deleted successfully.', 'info')
    return redirect(url_for('fuel.index', selected=vehicle_id))
