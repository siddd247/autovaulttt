from datetime import datetime, timezone, date
from flask import Blueprint, render_template, session, redirect, url_for, request
from app.models.vehicle import Vehicle
from app.models.fuel import FuelEntry
from app.models.maintenance import MaintenanceRecord
from app.models.reminder import Reminder
from app.models.document import Document
from app.routes.auth import login_required, get_current_user

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def landing():
    """Public landing page showcasing AutoVault value proposition & security architecture."""
    user = get_current_user()
    return render_template('landing.html', user=user)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Central user command dashboard populated with real telemetry and event streams."""
    user = get_current_user()
    vehicles = Vehicle.query.filter_by(user_id=user.id).order_by(Vehicle.created_at.desc()).all()
    selected_id = request.args.get('selected', type=int)
    primary_vehicle = None
    if selected_id:
        primary_vehicle = Vehicle.query.filter_by(id=selected_id, user_id=user.id).first()
    if not primary_vehicle and vehicles:
        primary_vehicle = vehicles[0]

    # Fleet-wide Document Expiry Alerts (Insurance & PUCC)
    document_alerts = []
    for v in vehicles:
        ins = v.get_insurance_status()
        if ins['status'] == 'Expired':
            document_alerts.append({
                'vehicle': v, 'type': 'Insurance Policy', 'status': 'Expired',
                'badge': 'badge-vault-red', 'message': f"{v.display_name} ({v.registration_number or 'No Reg'}): Insurance policy expired {ins['days']} days ago!"
            })
        elif ins['status'] == 'Expiring Soon':
            document_alerts.append({
                'vehicle': v, 'type': 'Insurance Policy', 'status': 'Expiring Soon',
                'badge': 'badge-vault-amber', 'message': f"{v.display_name} ({v.registration_number or 'No Reg'}): Insurance policy expires in {ins['days']} days."
            })

        pol = v.get_pollution_status()
        if pol['status'] == 'Expired':
            document_alerts.append({
                'vehicle': v, 'type': 'Pollution (PUCC)', 'status': 'Expired',
                'badge': 'badge-vault-red', 'message': f"{v.display_name} ({v.registration_number or 'No Reg'}): PUCC emission certificate expired {pol['days']} days ago!"
            })
        elif pol['status'] == 'Expiring Soon':
            document_alerts.append({
                'vehicle': v, 'type': 'Pollution (PUCC)', 'status': 'Expiring Soon',
                'badge': 'badge-vault-amber', 'message': f"{v.display_name} ({v.registration_number or 'No Reg'}): PUCC emission certificate expires in {pol['days']} days."
            })

    # Telemetry summaries
    fuel_stats = {'avg_mileage': None, 'monthly_cost': 0.0, 'total_cost': 0.0}
    maint_stats = {'last_service': None, 'monthly_cost': 0.0, 'total_cost': 0.0}
    reminder_stats = {'pending_count': 0, 'overdue_count': 0}
    recent_activities = []

    current_month_prefix = date.today().strftime('%Y-%m')

    if primary_vehicle:
        # 1. Fuel calculations
        fuel_entries = FuelEntry.query.filter_by(vehicle_id=primary_vehicle.id).order_by(FuelEntry.odometer.asc()).all()
        if fuel_entries:
            fuel_stats['total_cost'] = sum(f.total_cost for f in fuel_entries)
            fuel_stats['monthly_cost'] = sum(f.total_cost for f in fuel_entries if f.date.startswith(current_month_prefix))

            # Mileage math
            total_dist = 0
            total_litres = 0.0
            for i in range(1, len(fuel_entries)):
                dist = fuel_entries[i].odometer - fuel_entries[i - 1].odometer
                if dist > 0 and fuel_entries[i].litres > 0:
                    total_dist += dist
                    total_litres += fuel_entries[i].litres
            if total_dist > 0 and total_litres > 0:
                fuel_stats['avg_mileage'] = round(total_dist / total_litres, 1)

            # Fuel activities
            for f in fuel_entries[-3:]:
                recent_activities.append({
                    'timestamp': f.date + ' (Log)',
                    'sort_time': f.created_at,
                    'category': 'Fuel Telemetry',
                    'category_badge': 'badge-vault-blue',
                    'description': f"Fueled {f.litres}L @ Rs.{f.total_cost:,.2f} (Odo: {f.odometer:,} km)",
                    'status': 'Logged',
                    'status_badge': 'badge-vault-green'
                })

        # 2. Maintenance calculations
        maint_records = MaintenanceRecord.query.filter_by(vehicle_id=primary_vehicle.id).order_by(MaintenanceRecord.date.desc()).all()
        if maint_records:
            maint_stats['last_service'] = maint_records[0]
            maint_stats['total_cost'] = sum(m.cost for m in maint_records)
            maint_stats['monthly_cost'] = sum(m.cost for m in maint_records if m.date.startswith(current_month_prefix))

            # Maintenance activities
            for m in maint_records[:3]:
                recent_activities.append({
                    'timestamp': m.date + ' (Service)',
                    'sort_time': m.created_at,
                    'category': 'Maintenance',
                    'category_badge': 'badge-vault-amber',
                    'description': f"{m.service_type} - Rs.{m.cost:,.2f}" + (f" @ {m.service_center}" if m.service_center else ""),
                    'status': 'Serviced',
                    'status_badge': 'badge-vault-green'
                })

        # 3. Reminder calculations
        reminders = Reminder.query.filter_by(vehicle_id=primary_vehicle.id).all()
        for r in reminders:
            status = r.calculate_status()
            if status != 'Completed':
                reminder_stats['pending_count'] += 1
                if status == 'Overdue':
                    reminder_stats['overdue_count'] += 1

        # 4. Document activities
        docs = Document.query.filter_by(vehicle_id=primary_vehicle.id).order_by(Document.uploaded_at.desc()).limit(2).all()
        for d in docs:
            recent_activities.append({
                'timestamp': d.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                'sort_time': d.uploaded_at,
                'category': 'Vault Document',
                'category_badge': 'badge-vault-blue',
                'description': f"Stored {d.document_type}: {d.original_filename} ({d.formatted_size()})",
                'status': 'Secured',
                'status_badge': 'badge-vault-green'
            })

        # Primary vehicle registry activity
        recent_activities.append({
            'timestamp': primary_vehicle.created_at.strftime('%Y-%m-%d %H:%M'),
            'sort_time': primary_vehicle.created_at,
            'category': 'Vehicle Registry',
            'category_badge': 'badge-vault-blue',
            'description': f"Registered {primary_vehicle.display_name} into AutoVault",
            'status': 'Active',
            'status_badge': 'badge-vault-green'
        })

    # Sort composite activity feed
    recent_activities.sort(key=lambda x: x['sort_time'], reverse=True)

    return render_template(
        'dashboard.html',
        user=user,
        vehicles=vehicles,
        primary_vehicle=primary_vehicle,
        fuel_stats=fuel_stats,
        maint_stats=maint_stats,
        reminder_stats=reminder_stats,
        document_alerts=document_alerts,
        recent_activities=recent_activities[:6]
    )
