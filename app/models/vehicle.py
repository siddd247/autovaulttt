from datetime import datetime, timezone, date
from app.models import db

class Vehicle(db.Model):
    """Vehicle model representing vehicles owned by a registered user."""
    __tablename__ = 'vehicles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    manufacturer = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    variant = db.Column(db.String(50), nullable=True)
    registration_number = db.Column(db.String(30), nullable=True)
    fuel_type = db.Column(db.String(30), nullable=False, default='Petrol')
    transmission = db.Column(db.String(30), nullable=False, default='Manual')
    manufacturing_year = db.Column(db.Integer, nullable=True)
    purchase_date = db.Column(db.String(20), nullable=True)
    current_odometer = db.Column(db.Integer, nullable=False, default=0)
    color = db.Column(db.String(30), nullable=True)
    insurance_expiry = db.Column(db.String(20), nullable=True)
    pollution_expiry = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def display_name(self) -> str:
        """Helper to return readable title e.g. 'Hyundai i20'."""
        return f"{self.manufacturer} {self.model}"

    def get_insurance_status(self) -> dict:
        """Evaluate insurance policy expiry dynamically against today's date."""
        if not self.insurance_expiry:
            return {'status': 'Unspecified', 'badge': 'badge-vault-gray', 'days': None, 'text': 'Not Set'}
        try:
            exp_date = datetime.strptime(self.insurance_expiry, '%Y-%m-%d').date()
            delta = (exp_date - date.today()).days
            if delta < 0:
                return {
                    'status': 'Expired',
                    'badge': 'badge-vault-red',
                    'days': abs(delta),
                    'text': f'Expired {abs(delta)} days ago ({self.insurance_expiry})'
                }
            elif delta <= 15:
                return {
                    'status': 'Expiring Soon',
                    'badge': 'badge-vault-amber',
                    'days': delta,
                    'text': f'Expires in {delta} days ({self.insurance_expiry})'
                }
            else:
                return {
                    'status': 'Active',
                    'badge': 'badge-vault-green',
                    'days': delta,
                    'text': f'Valid until {self.insurance_expiry} ({delta}d)'
                }
        except ValueError:
            return {'status': 'Valid', 'badge': 'badge-vault-green', 'days': None, 'text': self.insurance_expiry}

    def get_pollution_status(self) -> dict:
        """Evaluate pollution (PUCC) certificate expiry dynamically against today's date."""
        if not self.pollution_expiry:
            return {'status': 'Unspecified', 'badge': 'badge-vault-gray', 'days': None, 'text': 'Not Set'}
        try:
            exp_date = datetime.strptime(self.pollution_expiry, '%Y-%m-%d').date()
            delta = (exp_date - date.today()).days
            if delta < 0:
                return {
                    'status': 'Expired',
                    'badge': 'badge-vault-red',
                    'days': abs(delta),
                    'text': f'Expired {abs(delta)} days ago ({self.pollution_expiry})'
                }
            elif delta <= 7:
                return {
                    'status': 'Expiring Soon',
                    'badge': 'badge-vault-amber',
                    'days': delta,
                    'text': f'Expires in {delta} days ({self.pollution_expiry})'
                }
            else:
                return {
                    'status': 'Active',
                    'badge': 'badge-vault-green',
                    'days': delta,
                    'text': f'Valid until {self.pollution_expiry} ({delta}d)'
                }
        except ValueError:
            return {'status': 'Valid', 'badge': 'badge-vault-green', 'days': None, 'text': self.pollution_expiry}

    def __repr__(self):
        return f"<Vehicle {self.manufacturer} {self.model} ({self.registration_number})>"
