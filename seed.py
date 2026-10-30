"""
AutoVault Sample Data Seeder
----------------------------
Populates realistic demonstration fleet for Shubranshu Verma:
- Hyundai i20 (Car) - JK 02 AB 9988
- Royal Enfield Hunter 350 (Bike) - JK 02 HL 4521
- Mahindra XUV700 (SUV) - JK 02 TS 7700

All vehicles are registered under JK 02 (Jammu & Kashmir).
Features subtle, executive regulatory status tracking and realistic logs.

Usage: python seed.py
"""

import os
from datetime import date, timedelta
from flask import current_app
from app import create_app
from app.models import db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.fuel import FuelEntry
from app.models.maintenance import MaintenanceRecord
from app.models.reminder import Reminder
from app.models.document import Document

DUMMY_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (AutoVault Verified Secure Document) ET\nendstream\nendobj\n"
    b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000214 00000 n \n"
    b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n308\n%%EOF"
)

def _ensure_dummy_file(docs_dir: str, filename: str) -> str:
    """Ensures a valid sample PDF file exists on disk."""
    os.makedirs(docs_dir, exist_ok=True)
    full_path = os.path.join(docs_dir, filename)
    if not os.path.exists(full_path):
        with open(full_path, 'wb') as f:
            f.write(DUMMY_PDF_BYTES)
    return full_path

def seed_demo_data_in_context():
    """Seed comprehensive demo data for Shubranshu Verma with JK 02 fleet."""
    today = date.today()

    # 1. Demo User Account: Shubranshu Verma
    demo_user = User.query.filter_by(username='demo_driver').first()
    if not demo_user:
        demo_user = User(
            name='Shubranshu Verma',
            email='shubranshu.verma@autovault.in',
            username='demo_driver'
        )
        demo_user.set_password('AutoVault@2026')
        db.session.add(demo_user)
        db.session.commit()
        print("Created demo account: Shubranshu Verma (demo_driver / AutoVault@2026)")
    else:
        # Update name and email if previously set to another name
        if demo_user.name != 'Shubranshu Verma':
            demo_user.name = 'Shubranshu Verma'
            demo_user.email = 'shubranshu.verma@autovault.in'
            db.session.commit()
            print("Updated demo account name to: Shubranshu Verma")

    # Document upload folder path
    upload_root = current_app.config.get('UPLOAD_FOLDER', 'instance/uploads') if current_app else 'instance/uploads'
    docs_dir = os.path.join(upload_root, 'documents')

    # 2. Vehicle 1: Hyundai i20 (Car / Hatchback) - JK 02 AB 9988
    v_car = Vehicle.query.filter_by(user_id=demo_user.id, model='i20').first()
    if not v_car:
        v_car = Vehicle(
            user_id=demo_user.id,
            manufacturer='Hyundai',
            model='i20',
            variant='Sportz 1.2 Petrol',
            registration_number='JK 02 AB 9988',
            fuel_type='Petrol',
            transmission='Manual',
            manufacturing_year=2023,
            purchase_date='2023-04-15',
            current_odometer=14850,
            color='Titan Gray',
            insurance_expiry=(today + timedelta(days=180)).isoformat(),   # Active
            pollution_expiry=(today + timedelta(days=4)).isoformat()       # Expiring soon (4 days)
        )
        db.session.add(v_car)
        db.session.commit()
        print("Added Car: Hyundai i20 (JK 02 AB 9988)")
    else:
        if v_car.registration_number != 'JK 02 AB 9988':
            v_car.registration_number = 'JK 02 AB 9988'
            v_car.pollution_expiry = (today + timedelta(days=4)).isoformat()
            db.session.commit()

    # Seed Car Fuel Logs
    if not FuelEntry.query.filter_by(vehicle_id=v_car.id).first():
        car_fills = [
            {'date': (today - timedelta(days=60)).isoformat(), 'odometer': 12000, 'litres': 35.0, 'price': 96.50, 'station': 'IndianOil Jammu Bypass', 'notes': 'Highway drive start'},
            {'date': (today - timedelta(days=48)).isoformat(), 'odometer': 12520, 'litres': 34.5, 'price': 96.80, 'station': 'Shell Gandhi Nagar', 'notes': 'City commute'},
            {'date': (today - timedelta(days=34)).isoformat(), 'odometer': 13080, 'litres': 36.0, 'price': 97.00, 'station': 'BPCL Expressway', 'notes': 'Full tank fill'},
            {'date': (today - timedelta(days=22)).isoformat(), 'odometer': 13650, 'litres': 35.5, 'price': 96.90, 'station': 'HPCL AutoCare', 'notes': 'Weekend roadtrip'},
            {'date': (today - timedelta(days=11)).isoformat(), 'odometer': 14220, 'litres': 36.2, 'price': 97.20, 'station': 'IndianOil Ring Road', 'notes': 'Office commute'},
            {'date': (today - timedelta(days=2)).isoformat(),  'odometer': 14850, 'litres': 38.0, 'price': 97.10, 'station': 'Shell Jammu Express', 'notes': 'Recent refill'}
        ]
        for f in car_fills:
            db.session.add(FuelEntry(
                vehicle_id=v_car.id,
                date=f['date'],
                odometer=f['odometer'],
                litres=f['litres'],
                price_per_litre=f['price'],
                total_cost=round(f['litres'] * f['price'], 2),
                station=f['station'],
                notes=f['notes']
            ))
        db.session.commit()

    # Seed Car Maintenance
    if not MaintenanceRecord.query.filter_by(vehicle_id=v_car.id).first():
        car_services = [
            {'date': (today - timedelta(days=150)).isoformat(), 'odometer': 10000, 'service_type': 'General Service', 'cost': 4800.0, 'service_center': 'Hyundai Motor Plaza', 'description': '10,000 km inspection, synthetic 5W-30 filled, OEM oil filter replaced.', 'notes': 'Invoice #HMP-78190'},
            {'date': (today - timedelta(days=85)).isoformat(),  'odometer': 11800, 'service_type': 'Wheel Alignment', 'cost': 950.0, 'service_center': 'Bridgestone Tyre Care', 'description': '4-wheel computerized alignment and balancing with tyre rotation.', 'notes': 'Tyre tread depth 6.5mm'},
            {'date': (today - timedelta(days=30)).isoformat(),  'odometer': 13200, 'service_type': 'AC Service', 'cost': 1850.0, 'service_center': 'Bosch Car Workshop', 'description': 'Cabin AC pollen filter replaced, refrigerant gas pressure checked, evaporator disinfection.', 'notes': 'Optimal cooling restored'}
        ]
        for s in car_services:
            db.session.add(MaintenanceRecord(
                vehicle_id=v_car.id, date=s['date'], odometer=s['odometer'],
                service_type=s['service_type'], cost=s['cost'],
                service_center=s['service_center'], description=s['description'], notes=s['notes']
            ))
        db.session.commit()

    # Seed Car Reminders
    if not Reminder.query.filter_by(vehicle_id=v_car.id).first():
        car_reminders = [
            {'title': 'Pollution (PUCC) Certificate Renewal', 'description': 'Emission inspection renewal window open before deadline.', 'due_date': (today + timedelta(days=4)).isoformat(), 'due_mileage': None, 'priority': 'Medium', 'status': 'Upcoming'},
            {'title': '20,000 KM Major Periodic Service', 'description': 'Spark plugs check, brake fluid flush, throttle body inspection.', 'due_date': (today + timedelta(days=120)).isoformat(), 'due_mileage': 20000, 'priority': 'Medium', 'status': 'Upcoming'},
            {'title': 'Tyre Pressure & Rotation Check', 'description': 'Rotate front and rear tyres to maintain even tread depth.', 'due_date': (today + timedelta(days=20)).isoformat(), 'due_mileage': 15000, 'priority': 'Low', 'status': 'Upcoming'}
        ]
        for r in car_reminders:
            db.session.add(Reminder(
                vehicle_id=v_car.id, title=r['title'], description=r['description'],
                due_date=r['due_date'], due_mileage=r['due_mileage'], priority=r['priority'], status=r['status']
            ))
        db.session.commit()

    # Seed Car Documents
    if not Document.query.filter_by(vehicle_id=v_car.id).first():
        f1 = _ensure_dummy_file(docs_dir, 'i20_rc_doc.pdf')
        f2 = _ensure_dummy_file(docs_dir, 'i20_insurance_doc.pdf')
        f3 = _ensure_dummy_file(docs_dir, 'i20_pucc_doc.pdf')
        db.session.add_all([
            Document(vehicle_id=v_car.id, document_type='RC', filename='i20_rc_doc.pdf', original_filename='JK02AB9988_RC_SmartCard.pdf', secure_storage_path=f1, file_size=os.path.getsize(f1)),
            Document(vehicle_id=v_car.id, document_type='Insurance', filename='i20_insurance_doc.pdf', original_filename='HDFC_ERGO_Comprehensive_Policy.pdf', secure_storage_path=f2, file_size=os.path.getsize(f2)),
            Document(vehicle_id=v_car.id, document_type='PUCC', filename='i20_pucc_doc.pdf', original_filename='JK_Transport_PUCC_Certificate.pdf', secure_storage_path=f3, file_size=os.path.getsize(f3))
        ])
        db.session.commit()

    # 3. Vehicle 2: Royal Enfield Hunter 350 (Bike / Motorcycle) - JK 02 HL 4521
    v_bike = Vehicle.query.filter_by(user_id=demo_user.id, model='Hunter 350').first()
    if not v_bike:
        v_bike = Vehicle(
            user_id=demo_user.id,
            manufacturer='Royal Enfield',
            model='Hunter 350',
            variant='Dapper Ash 350cc',
            registration_number='JK 02 HL 4521',
            fuel_type='Petrol',
            transmission='Manual',
            manufacturing_year=2024,
            purchase_date='2024-02-10',
            current_odometer=6420,
            color='Dapper Ash & Black',
            insurance_expiry=(today - timedelta(days=12)).isoformat(),  # Expired 12 days ago
            pollution_expiry=(today + timedelta(days=95)).isoformat()    # Active
        )
        db.session.add(v_bike)
        db.session.commit()
        print("Added Bike: Royal Enfield Hunter 350 (JK 02 HL 4521)")
    else:
        if v_bike.registration_number != 'JK 02 HL 4521':
            v_bike.registration_number = 'JK 02 HL 4521'
            db.session.commit()

    # Seed Bike Fuel Logs
    if not FuelEntry.query.filter_by(vehicle_id=v_bike.id).first():
        bike_fills = [
            {'date': (today - timedelta(days=45)).isoformat(), 'odometer': 5100, 'litres': 10.5, 'price': 101.50, 'station': 'Shell Canal Road', 'notes': 'Full tank initial log'},
            {'date': (today - timedelta(days=32)).isoformat(), 'odometer': 5440, 'litres': 9.8,  'price': 101.80, 'station': 'HPCL Jammu Cantt', 'notes': 'Commute run (34.7 km/L)'},
            {'date': (today - timedelta(days=21)).isoformat(), 'odometer': 5780, 'litres': 9.5,  'price': 102.00, 'station': 'IndianOil Nagrota', 'notes': 'Highway morning ride (35.8 km/L)'},
            {'date': (today - timedelta(days=10)).isoformat(), 'odometer': 6110, 'litres': 9.6,  'price': 101.90, 'station': 'BPCL Jammu City', 'notes': 'Weekend commute (34.4 km/L)'},
            {'date': (today - timedelta(days=1)).isoformat(),  'odometer': 6420, 'litres': 9.0,  'price': 102.10, 'station': 'Shell Canal Road', 'notes': 'Latest top-up (34.4 km/L)'}
        ]
        for f in bike_fills:
            db.session.add(FuelEntry(
                vehicle_id=v_bike.id,
                date=f['date'],
                odometer=f['odometer'],
                litres=f['litres'],
                price_per_litre=f['price'],
                total_cost=round(f['litres'] * f['price'], 2),
                station=f['station'],
                notes=f['notes']
            ))
        db.session.commit()

    # Seed Bike Maintenance
    if not MaintenanceRecord.query.filter_by(vehicle_id=v_bike.id).first():
        bike_services = [
            {'date': (today - timedelta(days=160)).isoformat(), 'odometer': 500,  'service_type': 'First Free Service', 'cost': 1450.0, 'service_center': 'Acclaim Motors RE Workshop', 'description': 'Initial engine oil replacement with Liquid Gun Semi-synthetic 15W-50, valve adjustment.', 'notes': 'Running-in check passed'},
            {'date': (today - timedelta(days=70)).isoformat(),  'odometer': 3200, 'service_type': 'Chain Lubrication & Lube', 'cost': 450.0, 'service_center': 'MotoGarage Care', 'description': 'Drive chain tension adjustment, ultrasonic degrease wash, Motul chain lube coat.', 'notes': 'Optimal chain slack set'},
            {'date': (today - timedelta(days=15)).isoformat(),  'odometer': 6000, 'service_type': 'Brake Pad & Cable Check', 'cost': 850.0, 'service_center': 'Acclaim Motors RE Workshop', 'description': 'Bybre front brake pads cleaned, clutch free-play adjusted, throttle cable lubricated.', 'notes': 'Brake bite verified'}
        ]
        for s in bike_services:
            db.session.add(MaintenanceRecord(
                vehicle_id=v_bike.id, date=s['date'], odometer=s['odometer'],
                service_type=s['service_type'], cost=s['cost'],
                service_center=s['service_center'], description=s['description'], notes=s['notes']
            ))
        db.session.commit()

    # Seed Bike Reminders
    if not Reminder.query.filter_by(vehicle_id=v_bike.id).first():
        bike_reminders = [
            {'title': 'Comprehensive Policy Renewal', 'description': 'Two-wheeler insurance coverage lapsed 12 days ago. Policy renewal required.', 'due_date': (today - timedelta(days=12)).isoformat(), 'due_mileage': None, 'priority': 'Medium', 'status': 'Upcoming'},
            {'title': 'Drive Chain Clean & Lubrication', 'description': 'Scheduled cleaning and tension adjustment to preserve sprocket life.', 'due_date': (today + timedelta(days=8)).isoformat(), 'due_mileage': 6900, 'priority': 'Low', 'status': 'Upcoming'},
            {'title': '10,000 KM Major Periodic Service', 'description': 'Engine oil flush, spark plug inspect, air filter replacement.', 'due_date': (today + timedelta(days=140)).isoformat(), 'due_mileage': 10000, 'priority': 'Medium', 'status': 'Upcoming'}
        ]
        for r in bike_reminders:
            db.session.add(Reminder(
                vehicle_id=v_bike.id, title=r['title'], description=r['description'],
                due_date=r['due_date'], due_mileage=r['due_mileage'], priority=r['priority'], status=r['status']
            ))
        db.session.commit()

    # Seed Bike Documents
    if not Document.query.filter_by(vehicle_id=v_bike.id).first():
        f4 = _ensure_dummy_file(docs_dir, 'bike_rc_doc.pdf')
        f5 = _ensure_dummy_file(docs_dir, 'bike_insurance_expired.pdf')
        db.session.add_all([
            Document(vehicle_id=v_bike.id, document_type='RC', filename='bike_rc_doc.pdf', original_filename='JK02HL4521_TwoWheeler_RC.pdf', secure_storage_path=f4, file_size=os.path.getsize(f4)),
            Document(vehicle_id=v_bike.id, document_type='Insurance', filename='bike_insurance_expired.pdf', original_filename='ICICI_Lombard_Motor_Policy.pdf', secure_storage_path=f5, file_size=os.path.getsize(f5))
        ])
        db.session.commit()

    # 4. Vehicle 3: Mahindra XUV700 (SUV) - JK 02 TS 7700
    v_suv = Vehicle.query.filter_by(user_id=demo_user.id, model='XUV700').first()
    if not v_suv:
        v_suv = Vehicle(
            user_id=demo_user.id,
            manufacturer='Mahindra',
            model='XUV700',
            variant='AX7 Diesel AT AWD',
            registration_number='JK 02 TS 7700',
            fuel_type='Diesel',
            transmission='Automatic',
            manufacturing_year=2023,
            purchase_date='2023-08-20',
            current_odometer=28600,
            color='Midnight Black',
            insurance_expiry=(today + timedelta(days=240)).isoformat(),  # Active
            pollution_expiry=(today - timedelta(days=3)).isoformat()       # Expired 3 days ago
        )
        db.session.add(v_suv)
        db.session.commit()
        print("Added SUV: Mahindra XUV700 (JK 02 TS 7700)")
    else:
        if v_suv.registration_number != 'JK 02 TS 7700':
            v_suv.registration_number = 'JK 02 TS 7700'
            v_suv.pollution_expiry = (today - timedelta(days=3)).isoformat()
            db.session.commit()

    # Seed SUV Fuel Logs
    if not FuelEntry.query.filter_by(vehicle_id=v_suv.id).first():
        suv_fills = [
            {'date': (today - timedelta(days=50)).isoformat(), 'odometer': 26400, 'litres': 50.0, 'price': 89.50, 'station': 'HPCL Jammu Expressway', 'notes': 'Highway refill (full tank)'},
            {'date': (today - timedelta(days=38)).isoformat(), 'odometer': 27000, 'litres': 46.0, 'price': 89.80, 'station': 'IndianOil Channi Himmat', 'notes': 'City commute (13.0 km/L)'},
            {'date': (today - timedelta(days=26)).isoformat(), 'odometer': 27550, 'litres': 42.0, 'price': 89.70, 'station': 'Shell Bari Brahmana', 'notes': 'Highway cruise (13.1 km/L)'},
            {'date': (today - timedelta(days=14)).isoformat(), 'odometer': 28100, 'litres': 41.5, 'price': 89.90, 'station': 'BPCL Narwal', 'notes': 'Bypass run (13.3 km/L)'},
            {'date': (today - timedelta(days=3)).isoformat(),  'odometer': 28600, 'litres': 37.0, 'price': 90.10, 'station': 'HPCL Jammu Expressway', 'notes': 'Latest refill (13.5 km/L)'}
        ]
        for f in suv_fills:
            db.session.add(FuelEntry(
                vehicle_id=v_suv.id,
                date=f['date'],
                odometer=f['odometer'],
                litres=f['litres'],
                price_per_litre=f['price'],
                total_cost=round(f['litres'] * f['price'], 2),
                station=f['station'],
                notes=f['notes']
            ))
        db.session.commit()

    # Seed SUV Maintenance
    if not MaintenanceRecord.query.filter_by(vehicle_id=v_suv.id).first():
        suv_services = [
            {'date': (today - timedelta(days=190)).isoformat(), 'odometer': 10000, 'service_type': 'First Periodic Service', 'cost': 3200.0, 'service_center': 'Jammu Auto Mahindra', 'description': '10,000 km standard checkup, wheel alignment, AdBlue DEF fluid top-up.', 'notes': 'DEF topped up 10L'},
            {'date': (today - timedelta(days=80)).isoformat(),  'odometer': 20000, 'service_type': 'Major 20,000 KM Service', 'cost': 8450.0, 'service_center': 'Jammu Auto Mahindra', 'description': 'mHawk synthetic oil flush (6L 5W-30), diesel fuel filter replacement, cabin filter.', 'notes': 'Invoice #JAM-9821'},
            {'date': (today - timedelta(days=18)).isoformat(),  'odometer': 26500, 'service_type': 'DPF Regeneration & Alignment', 'cost': 1950.0, 'service_center': 'Mahindra Care Jammu', 'description': 'Standard DPF soot burn cycle, all-wheel computerized alignment and balancing.', 'notes': 'DPF soot load reduced to 2%'}
        ]
        for s in suv_services:
            db.session.add(MaintenanceRecord(
                vehicle_id=v_suv.id, date=s['date'], odometer=s['odometer'],
                service_type=s['service_type'], cost=s['cost'],
                service_center=s['service_center'], description=s['description'], notes=s['notes']
            ))
        db.session.commit()

    # Seed SUV Reminders - subtle and settled
    if not Reminder.query.filter_by(vehicle_id=v_suv.id).first():
        suv_reminders = [
            {'title': 'Pollution (PUCC) Emission Renewal', 'description': 'Periodic emission testing inspection due for vehicle compliance.', 'due_date': (today - timedelta(days=3)).isoformat(), 'due_mileage': None, 'priority': 'Medium', 'status': 'Upcoming'},
            {'title': 'AdBlue DEF Fluid Level Check', 'description': 'Check exhaust fluid level before upcoming highway drive.', 'due_date': (today + timedelta(days=15)).isoformat(), 'due_mileage': 29500, 'priority': 'Low', 'status': 'Upcoming'},
            {'title': '30,000 KM Periodic Inspection', 'description': 'Transmission fluid inspect, differential oil check, brake pads wear measure.', 'due_date': (today + timedelta(days=60)).isoformat(), 'due_mileage': 30000, 'priority': 'Medium', 'status': 'Upcoming'}
        ]
        for r in suv_reminders:
            db.session.add(Reminder(
                vehicle_id=v_suv.id, title=r['title'], description=r['description'],
                due_date=r['due_date'], due_mileage=r['due_mileage'], priority=r['priority'], status=r['status']
            ))
        db.session.commit()

    # Seed SUV Documents
    if not Document.query.filter_by(vehicle_id=v_suv.id).first():
        f6 = _ensure_dummy_file(docs_dir, 'suv_rc_doc.pdf')
        f7 = _ensure_dummy_file(docs_dir, 'suv_insurance_doc.pdf')
        f8 = _ensure_dummy_file(docs_dir, 'suv_pucc_expired.pdf')
        db.session.add_all([
            Document(vehicle_id=v_suv.id, document_type='RC', filename='suv_rc_doc.pdf', original_filename='JK02TS7700_SmartCard_RC.pdf', secure_storage_path=f6, file_size=os.path.getsize(f6)),
            Document(vehicle_id=v_suv.id, document_type='Insurance', filename='suv_insurance_doc.pdf', original_filename='Bajaj_Allianz_DriveAssure_Policy.pdf', secure_storage_path=f7, file_size=os.path.getsize(f7)),
            Document(vehicle_id=v_suv.id, document_type='PUCC', filename='suv_pucc_expired.pdf', original_filename='JK_Transport_Expired_PUCC.pdf', secure_storage_path=f8, file_size=os.path.getsize(f8))
        ])
        db.session.commit()

    print("=== Demo Fleet Seeding Completed Successfully! ===")
    print("Demo Fleet populated for Shubranshu Verma: Hyundai i20 (JK 02 AB 9988), Royal Enfield Hunter 350 (JK 02 HL 4521), Mahindra XUV700 (JK 02 TS 7700).")

def seed_demo_data():
    """Create app instance and populate demo data."""
    app = create_app()
    with app.app_context():
        seed_demo_data_in_context()

if __name__ == '__main__':
    seed_demo_data()
