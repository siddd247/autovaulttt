from datetime import datetime, timezone, date
from app.models import db

class Reminder(db.Model):
    """Predictive and scheduled maintenance reminder model."""
    __tablename__ = 'reminders'

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.String(20), nullable=True)  # ISO Date YYYY-MM-DD
    due_mileage = db.Column(db.Integer, nullable=True)
    priority = db.Column(db.String(20), nullable=False, default='Medium')  # Low, Medium, High
    status = db.Column(db.String(20), nullable=False, default='Upcoming')  # Upcoming, Due Soon, Overdue, Completed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    vehicle = db.relationship(
        'Vehicle',
        backref=db.backref('reminders', lazy=True, cascade='all, delete-orphan', order_by='Reminder.due_date.asc()')
    )

    def calculate_status(self) -> str:
        """Dynamically computes the actual status based on today's date and vehicle odometer."""
        if self.status == 'Completed':
            return 'Completed'

        today_str = date.today().isoformat()
        
        # Check date-based overdue/due soon
        if self.due_date:
            if self.due_date < today_str:
                return 'Overdue'
            try:
                due_d = datetime.strptime(self.due_date, '%Y-%m-%d').date()
                delta_days = (due_d - date.today()).days
                if 0 <= delta_days <= 7:
                    return 'Due Soon'
            except ValueError:
                pass

        # Check mileage-based overdue/due soon
        if self.due_mileage and self.vehicle and self.vehicle.current_odometer:
            diff = self.due_mileage - self.vehicle.current_odometer
            if diff <= 0:
                return 'Overdue'
            elif diff <= 500:
                return 'Due Soon'

        return 'Upcoming'

    def is_insurance_reminder(self) -> bool:
        """Checks if this reminder pertains to vehicle insurance renewal."""
        t = (self.title or '').lower()
        d = (self.description or '').lower()
        return ('insurance' in t) or ('policy' in t) or ('insurance' in d)

    def is_pollution_reminder(self) -> bool:
        """Checks if this reminder pertains to vehicle pollution / PUCC emission certification."""
        t = (self.title or '').lower()
        d = (self.description or '').lower()
        return (
            ('pollution' in t) or ('pucc' in t) or ('emission' in t) or ('puc' in t) or
            ('pollution' in d) or ('pucc' in d) or ('emission' in d)
        )

    def __repr__(self):
        return f"<Reminder {self.title} status={self.status}>"
