import os
import io
import unittest
from app import create_app
from app.models import db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.fuel import FuelEntry
from app.models.maintenance import MaintenanceRecord
from app.models.reminder import Reminder
from app.models.document import Document

class TestAutoVaultAllFeatures(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = 'test-secret-key-123'
            SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            UPLOAD_FOLDER = os.path.abspath('instance/test_uploads')

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Create test user A and vehicle A
            user_a = User(name='Alice User', email='alice@vault.com', username='alice')
            user_a.set_password('SecretAlice123')
            db.session.add(user_a)
            db.session.commit()

            vehicle_a = Vehicle(
                user_id=user_a.id,
                manufacturer='Hyundai',
                model='i20',
                variant='Sportz',
                registration_number='DL 01 AB 1234',
                fuel_type='Petrol',
                transmission='Manual',
                current_odometer=10000
            )
            db.session.add(vehicle_a)

            # Create user B and vehicle B for IDOR testing
            user_b = User(name='Bob User', email='bob@vault.com', username='bob')
            user_b.set_password('SecretBob123')
            db.session.add(user_b)
            db.session.commit()

            vehicle_b = Vehicle(
                user_id=user_b.id,
                manufacturer='Honda',
                model='City',
                current_odometer=20000
            )
            db.session.add(vehicle_b)
            db.session.commit()

            self.user_a_id = user_a.id
            self.user_b_id = user_b.id
            self.vehicle_a_id = vehicle_a.id
            self.vehicle_b_id = vehicle_b.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login_as_alice(self):
        return self.client.post('/login', data={'identifier': 'alice', 'password': 'SecretAlice123'})

    def login_as_bob(self):
        return self.client.post('/login', data={'identifier': 'bob', 'password': 'SecretBob123'})

    def test_fuel_crud_and_mileage_calculation(self):
        """Test fuel entry logging, automatic odometer update, and interval mileage computation."""
        self.login_as_alice()

        # Log first refill @ 10,000 km, 30L
        res1 = self.client.post('/fuel/add', data={
            'vehicle_id': self.vehicle_a_id,
            'date': '2026-10-01',
            'odometer': 10000,
            'litres': 30.0,
            'price_per_litre': 100.0,
            'total_cost': 3000.0,
            'station': 'Shell Sector 21'
        }, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        # Log second refill @ 10,450 km (distance = 450 km), 30L -> Expected mileage = 450 / 30 = 15.0 km/L
        res2 = self.client.post('/fuel/add', data={
            'vehicle_id': self.vehicle_a_id,
            'date': '2026-10-05',
            'odometer': 10450,
            'litres': 30.0,
            'price_per_litre': 100.0,
            'total_cost': 3000.0,
            'station': 'IndianOil'
        }, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

        # Verify on page that mileage 15 km/L is displayed
        fuel_page = self.client.get('/fuel')
        self.assertIn(b'15.0', fuel_page.data)
        self.assertIn(b'Shell Sector 21', fuel_page.data)

        with self.app.app_context():
            v = db.session.get(Vehicle, self.vehicle_a_id)
            # Odometer must have updated automatically to 10450
            self.assertEqual(v.current_odometer, 10450)

    def test_maintenance_crud(self):
        """Test adding and viewing maintenance records with cost tracking."""
        self.login_as_alice()

        res = self.client.post('/maintenance/add', data={
            'vehicle_id': self.vehicle_a_id,
            'date': '2026-10-03',
            'service_type': 'Engine Oil & Filter',
            'cost': 4200.0,
            'odometer': 10200,
            'service_center': 'Hyundai Express Care',
            'description': 'Full synthetic 5W-30 + OEM filter'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Engine Oil &amp; Filter', res.data)
        self.assertIn(b'Hyundai Express Care', res.data)

        with self.app.app_context():
            record = MaintenanceRecord.query.filter_by(vehicle_id=self.vehicle_a_id).first()
            self.assertIsNotNone(record)
            self.assertEqual(record.cost, 4200.0)

    def test_reminders_status_and_completion(self):
        """Test reminder creation and dynamic status computation."""
        self.login_as_alice()

        # Add reminder with past due date (must evaluate to Overdue)
        self.client.post('/reminders/add', data={
            'vehicle_id': self.vehicle_a_id,
            'title': 'Overdue Inspection',
            'due_date': '2025-01-01',
            'priority': 'High'
        }, follow_redirects=True)

        rem_page = self.client.get('/reminders')
        self.assertIn(b'Overdue Inspection', rem_page.data)
        self.assertIn(b'Overdue', rem_page.data)

        # Toggle completion
        with self.app.app_context():
            rem = Reminder.query.filter_by(title='Overdue Inspection').first()
            rem_id = rem.id

        toggle_res = self.client.post(f'/reminders/toggle/{rem_id}', follow_redirects=True)
        self.assertEqual(toggle_res.status_code, 200)

        with self.app.app_context():
            rem = db.session.get(Reminder, rem_id)
            self.assertEqual(rem.status, 'Completed')

    def test_document_vault_upload_and_idor_protection(self):
        """Test secure document uploading, access, and cross-user authorization defense."""
        self.login_as_alice()

        # Fake PDF file
        file_content = b"%PDF-1.4 simulated vehicle registration certificate"
        data = {
            'vehicle_id': self.vehicle_a_id,
            'document_type': 'Registration Certificate (RC)',
            'document_file': (io.BytesIO(file_content), 'RC_Doc.pdf')
        }

        upload_res = self.client.post('/documents/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(upload_res.status_code, 200)
        self.assertIn(b'RC_Doc.pdf', upload_res.data)

        with self.app.app_context():
            doc = Document.query.filter_by(original_filename='RC_Doc.pdf').first()
            self.assertIsNotNone(doc)
            doc_id = doc.id
            self.assertEqual(doc.vehicle_id, self.vehicle_a_id)

        # Alice views the document -> 200
        view_res = self.client.get(f'/documents/view/{doc_id}')
        self.assertEqual(view_res.status_code, 200)
        self.assertEqual(view_res.data, file_content)
        view_res.close()

        # Log out Alice, log in Bob
        self.client.get('/logout')
        self.login_as_bob()

        # Bob attempts IDOR access on Alice's document -> must be 403 Forbidden!
        idor_doc = self.client.get(f'/documents/view/{doc_id}')
        self.assertEqual(idor_doc.status_code, 403)

        # Bob attempts IDOR deletion on Alice's document -> must be 403 Forbidden!
        idor_del = self.client.post(f'/documents/delete/{doc_id}')
        self.assertEqual(idor_del.status_code, 403)

    def test_analytics_and_dashboard_integration(self):
        """Verify analytics and dashboard render with live database metrics."""
        self.login_as_alice()

        # Add fuel and maintenance
        self.client.post('/fuel/add', data={
            'vehicle_id': self.vehicle_a_id,
            'date': '2026-10-01',
            'odometer': 10000,
            'litres': 20.0,
            'price_per_litre': 100.0,
            'total_cost': 2000.0
        })

        self.client.post('/maintenance/add', data={
            'vehicle_id': self.vehicle_a_id,
            'date': '2026-10-02',
            'service_type': 'Brake Service',
            'cost': 1500.0,
            'odometer': 10050
        })

        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Brake Service', dash_res.data)
        self.assertIn(b'Hyundai i20', dash_res.data)

        analytics_res = self.client.get('/analytics')
        self.assertEqual(analytics_res.status_code, 200)
        self.assertIn(b'monthlySpendingChart', analytics_res.data)

    def test_view_demo_fleet_and_leave_demo_flow(self):
        """Test one-click 'View Demo' entry, multi-vehicle fleet (Car, Bike, SUV),
        document expiry indicators, calculated mileage, and 'Leave Demo' exit.
        """
        # 1. Click "View Demo"
        demo_enter = self.client.get('/demo', follow_redirects=True)
        self.assertEqual(demo_enter.status_code, 200)
        self.assertIn(b'DEMO MODE', demo_enter.data)
        self.assertIn(b'Shubranshu Verma', demo_enter.data)
        self.assertIn(b'Leave Demo', demo_enter.data)

        # 2. Verify all 3 vehicles exist in database under Shubranshu Verma and JK 02
        with self.app.app_context():
            demo_user = User.query.filter_by(username='demo_driver').first()
            self.assertIsNotNone(demo_user)
            self.assertEqual(demo_user.name, 'Shubranshu Verma')

            vehicles = Vehicle.query.filter_by(user_id=demo_user.id).all()
            # Must have at least 3 vehicles: Car (i20), Bike (Hunter 350), SUV (XUV700)
            self.assertGreaterEqual(len(vehicles), 3)

            car = next((v for v in vehicles if 'i20' in v.model), None)
            bike = next((v for v in vehicles if 'Hunter' in v.model), None)
            suv = next((v for v in vehicles if 'XUV700' in v.model), None)

            self.assertIsNotNone(car)
            self.assertIsNotNone(bike)
            self.assertIsNotNone(suv)

            # All vehicles must be JK 02
            self.assertTrue(car.registration_number.startswith('JK 02'))
            self.assertTrue(bike.registration_number.startswith('JK 02'))
            self.assertTrue(suv.registration_number.startswith('JK 02'))

            # Document expiry verification:
            # Bike has expired insurance
            bike_ins = bike.get_insurance_status()
            self.assertEqual(bike_ins['status'], 'Expired')

            # SUV has expired pollution (PUCC)
            suv_pucc = suv.get_pollution_status()
            self.assertEqual(suv_pucc['status'], 'Expired')

            # Car has upcoming pollution expiry
            car_pucc = car.get_pollution_status()
            self.assertEqual(car_pucc['status'], 'Expiring Soon')

            # Fuel entries exist for all vehicles with interval mileage calculated
            car_fuel = FuelEntry.query.filter_by(vehicle_id=car.id).all()
            self.assertGreaterEqual(len(car_fuel), 3)

            bike_fuel = FuelEntry.query.filter_by(vehicle_id=bike.id).all()
            self.assertGreaterEqual(len(bike_fuel), 3)

            suv_fuel = FuelEntry.query.filter_by(vehicle_id=suv.id).all()
            self.assertGreaterEqual(len(suv_fuel), 3)

            # Documents exist for the demo vehicles
            car_docs = Document.query.filter_by(vehicle_id=car.id).all()
            self.assertGreaterEqual(len(car_docs), 1)

        # 3. Check Dashboard reflects document alerts and multi-vehicle switcher
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertTrue(b'Expired' in dash_res.data or b'EXPIRED' in dash_res.data)
        self.assertIn(b'Royal Enfield Hunter 350', dash_res.data)
        self.assertIn(b'Mahindra XUV700', dash_res.data)

        # 4. Check vehicle profile displays dynamic expiry badges
        veh_res = self.client.get(f'/vehicle?selected={bike.id}')
        self.assertEqual(veh_res.status_code, 200)
        self.assertTrue(b'Expired' in veh_res.data or b'EXPIRED' in veh_res.data)

        # 5. Check fuel page shows calculated mileage
        fuel_bike_res = self.client.get(f'/fuel?selected={bike.id}')
        self.assertEqual(fuel_bike_res.status_code, 200)
        self.assertIn(b'km/L', fuel_bike_res.data)

        # 6. Click "Leave Demo Mode"
        exit_res = self.client.get('/leave-demo', follow_redirects=True)
        self.assertEqual(exit_res.status_code, 200)
        self.assertIn(b'You have safely exited demo mode', exit_res.data)

        # 7. Verify unauthenticated: accessing /dashboard now redirects to /login
        protect_check = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(protect_check.status_code, 302)
        self.assertIn('/login', protect_check.headers['Location'])

    def test_reminder_completion_with_insurance_renewal_and_document_upload(self):
        """Test completing an insurance reminder updates vehicle validity and stores policy document."""
        self.login_as_alice()

        with self.app.app_context():
            vehicle = db.session.get(Vehicle, self.vehicle_a_id)
            # Set vehicle insurance as expired
            vehicle.insurance_expiry = '2026-01-01'
            reminder = Reminder(
                vehicle_id=vehicle.id,
                title='Comprehensive Policy Renewal',
                description='Annual insurance coverage expired.',
                due_date='2026-01-01',
                priority='High',
                status='Upcoming'
            )
            db.session.add(reminder)
            db.session.commit()
            reminder_id = reminder.id

            self.assertEqual(vehicle.get_insurance_status()['status'], 'Expired')

        # Alice completes reminder, providing new expiry date and uploading policy document
        dummy_file = (io.BytesIO(b'%PDF-1.4 Dummy Policy Document Content'), 'policy_2027.pdf')
        res = self.client.post(f'/reminders/complete/{reminder_id}', data={
            'new_expiry_date': '2027-10-30',
            'completion_notes': 'Renewed via portal, receipt #99120',
            'document_file': dummy_file
        }, content_type='multipart/form-data', follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Insurance renewed', res.data)

        with self.app.app_context():
            v = db.session.get(Vehicle, self.vehicle_a_id)
            r = db.session.get(Reminder, reminder_id)

            # Reminder must be completed
            self.assertEqual(r.status, 'Completed')
            self.assertIn('Renewed via portal', r.description)

            # Vehicle insurance expiry must be updated
            self.assertEqual(v.insurance_expiry, '2027-10-30')
            self.assertEqual(v.get_insurance_status()['status'], 'Active')

            # Document must be filed in Document table
            doc = Document.query.filter_by(vehicle_id=v.id, document_type='Insurance').order_by(Document.uploaded_at.desc()).first()
            self.assertIsNotNone(doc)
            self.assertEqual(doc.original_filename, 'policy_2027.pdf')

        # Dashboard must not flag this vehicle for expired insurance
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertNotIn(b'Insurance policy expired', dash_res.data)

    def test_reminder_completion_with_skip_document_option(self):
        """Test completing a pollution reminder with skip_document updates vehicle validity without file."""
        self.login_as_alice()

        with self.app.app_context():
            vehicle = db.session.get(Vehicle, self.vehicle_a_id)
            vehicle.pollution_expiry = '2026-02-15'
            reminder = Reminder(
                vehicle_id=vehicle.id,
                title='Pollution (PUCC) Certificate Renewal',
                description='Emission testing renewal required.',
                due_date='2026-02-15',
                priority='Medium',
                status='Upcoming'
            )
            db.session.add(reminder)
            db.session.commit()
            reminder_id = reminder.id

            self.assertEqual(vehicle.get_pollution_status()['status'], 'Expired')

        # Complete reminder with skip_document flag
        res = self.client.post(f'/reminders/complete/{reminder_id}', data={
            'new_expiry_date': '2027-08-15',
            'skip_document': '1',
            'completion_notes': 'Inspection done at authorized station'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Pollution (PUCC) renewed', res.data)

        with self.app.app_context():
            v = db.session.get(Vehicle, self.vehicle_a_id)
            r = db.session.get(Reminder, reminder_id)

            self.assertEqual(r.status, 'Completed')
            self.assertEqual(v.pollution_expiry, '2027-08-15')
            self.assertEqual(v.get_pollution_status()['status'], 'Active')

            # No PUCC document should have been created
            doc = Document.query.filter_by(vehicle_id=v.id, document_type='PUCC').first()
            self.assertIsNone(doc)

    def test_vehicle_edit_specifications_and_compliance(self):
        """Test editing vehicle details and compliance dates directly."""
        self.login_as_alice()

        edit_res = self.client.post(f'/vehicle/edit/{self.vehicle_a_id}', data={
            'manufacturer': 'Hyundai',
            'model': 'i20 N Line',
            'variant': 'N8 DCT Turbo',
            'registration_number': 'DL 01 AB 9999',
            'fuel_type': 'Petrol',
            'transmission': 'DCT',
            'manufacturing_year': 2024,
            'current_odometer': 18500,
            'color': 'Thunder Blue',
            'insurance_expiry': '2027-11-01',
            'pollution_expiry': '2027-05-01'
        }, follow_redirects=True)

        self.assertEqual(edit_res.status_code, 200)
        self.assertIn(b'Specifications and compliance records', edit_res.data)

        with self.app.app_context():
            v = db.session.get(Vehicle, self.vehicle_a_id)
            self.assertEqual(v.model, 'i20 N Line')
            self.assertEqual(v.variant, 'N8 DCT Turbo')
            self.assertEqual(v.registration_number, 'DL 01 AB 9999')
            self.assertEqual(v.transmission, 'DCT')
            self.assertEqual(v.current_odometer, 18500)
            self.assertEqual(v.insurance_expiry, '2027-11-01')
            self.assertEqual(v.pollution_expiry, '2027-05-01')

if __name__ == '__main__':
    unittest.main()
