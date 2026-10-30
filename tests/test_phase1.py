import unittest
from app import create_app
from app.models import db
from app.models.user import User
from app.models.vehicle import Vehicle

class TestAutoVaultPhase1(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = 'test-secret-key'
            SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            UPLOAD_FOLDER = 'instance/test_uploads'

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_landing_page(self):
        """Verify landing page loads with 200 OK and brand messaging."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AutoVault', response.data)
        self.assertIn(b'Your Car. Your Data. One Secure Vault.', response.data)

    def test_registration_and_password_hashing(self):
        """Verify user registration stores cryptographic hash, not plaintext."""
        response = self.client.post('/register', data={
            'name': 'Shubham',
            'email': 'shubham@example.com',
            'username': 'shubham01',
            'password': 'StrongPassword123',
            'confirm_password': 'StrongPassword123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            user = User.query.filter_by(username='shubham01').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.email, 'shubham@example.com')
            # Security verification: plaintext password must NOT be stored
            self.assertNotEqual(user.password_hash, 'StrongPassword123')
            self.assertTrue(user.check_password('StrongPassword123'))
            self.assertFalse(user.check_password('WrongPassword'))

    def test_login_and_session_flow(self):
        """Verify valid login authenticates and protects session."""
        with self.app.app_context():
            u = User(name='User Test', email='test@example.com', username='usertest')
            u.set_password('SecretPass123')
            db.session.add(u)
            db.session.commit()

        # Invalid login test
        bad_login = self.client.post('/login', data={
            'identifier': 'usertest',
            'password': 'IncorrectPassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid username/email or password.', bad_login.data)

        # Successful login test
        good_login = self.client.post('/login', data={
            'identifier': 'usertest',
            'password': 'SecretPass123'
        }, follow_redirects=True)
        self.assertEqual(good_login.status_code, 200)
        self.assertIn(b'Welcome back, User Test!', good_login.data)

    def test_protected_routes_require_login(self):
        """Verify unauthenticated requests redirect to login."""
        protected_urls = ['/dashboard', '/vehicle', '/fuel', '/maintenance', '/reminders', '/documents', '/analytics', '/profile']
        for url in protected_urls:
            response = self.client.get(url, follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login', response.headers['Location'])

    def test_vehicle_creation_and_idor_protection(self):
        """Verify vehicle CRUD and authorization boundaries (preventing IDOR)."""
        with self.app.app_context():
            # User A
            user_a = User(name='Alice', email='alice@example.com', username='alice')
            user_a.set_password('PassAlice123')
            # User B
            user_b = User(name='Bob', email='bob@example.com', username='bob')
            user_b.set_password('PassBob123')
            db.session.add_all([user_a, user_b])
            db.session.commit()

            user_a_id = user_a.id
            user_b_id = user_b.id

        # Log in as Alice
        self.client.post('/login', data={'identifier': 'alice', 'password': 'PassAlice123'})

        # Alice adds a vehicle
        response = self.client.post('/vehicle/add', data={
            'manufacturer': 'Hyundai',
            'model': 'i20',
            'variant': 'Sportz',
            'registration_number': 'DL 01 AB 1234',
            'fuel_type': 'Petrol',
            'transmission': 'Manual',
            'manufacturing_year': '2023',
            'current_odometer': '15400'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Hyundai i20', response.data)

        with self.app.app_context():
            vehicle = Vehicle.query.filter_by(manufacturer='Hyundai').first()
            self.assertIsNotNone(vehicle)
            self.assertEqual(vehicle.user_id, user_a_id)
            vehicle_id = vehicle.id

        # Alice logs out
        self.client.get('/logout')

        # Bob logs in
        self.client.post('/login', data={'identifier': 'bob', 'password': 'PassBob123'})

        # Bob tries to delete Alice's vehicle (IDOR attack attempt)
        idor_attack = self.client.post(f'/vehicle/delete/{vehicle_id}')
        # Must return 403 Forbidden!
        self.assertEqual(idor_attack.status_code, 403)

    def test_serverless_session_resilience_and_cold_start_recovery(self):
        """Verify that when a cold start or DB wipe occurs on serverless deployment,
        the authenticated session and vehicle are self-healed and do not redirect to sign in again.
        """
        # Register a new user
        reg_res = self.client.post('/register', data={
            'name': 'Dev Driver',
            'email': 'driver@test.com',
            'username': 'devdriver',
            'password': 'SecurePassword@123',
            'confirm_password': 'SecurePassword@123'
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)

        # Add a vehicle
        add_res = self.client.post('/vehicle/add', data={
            'manufacturer': 'Tata',
            'model': 'Nexon',
            'variant': 'XZ+',
            'registration_number': 'MH 02 XY 9999',
            'fuel_type': 'Petrol',
            'transmission': 'Manual',
            'manufacturing_year': '2024',
            'current_odometer': '5200'
        }, follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)
        self.assertIn(b'Tata Nexon', add_res.data)

        # Simulate cold start / database wipe in a new container instance
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()
            # Verify DB is now completely empty of this user
            self.assertIsNone(User.query.filter_by(username='devdriver').first())
            self.assertEqual(Vehicle.query.count(), 0)

        # Now simulate the next request hitting this fresh container with existing session cookie
        dashboard_res = self.client.get('/dashboard', follow_redirects=False)
        # MUST NOT redirect to /login! Must return 200 OK!
        self.assertEqual(dashboard_res.status_code, 200)
        self.assertIn(b'Tata Nexon', dashboard_res.data)

        # Verify vehicle page also self-heals and renders
        vehicle_res = self.client.get('/vehicle', follow_redirects=False)
        self.assertEqual(vehicle_res.status_code, 200)
        self.assertIn(b'Tata Nexon', vehicle_res.data)

        # Verify DB now contains the restored user and vehicle
        with self.app.app_context():
            restored_user = User.query.filter_by(username='devdriver').first()
            self.assertIsNotNone(restored_user)
            self.assertEqual(restored_user.name, 'Dev Driver')
            restored_vehicle = Vehicle.query.filter_by(manufacturer='Tata', model='Nexon').first()
            self.assertIsNotNone(restored_vehicle)


if __name__ == '__main__':
    unittest.main()
