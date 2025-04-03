from datetime import datetime
from models.db_setup import db

class RouteIncident(db.Model):
    """Model for tracking driver-reported incidents during route execution."""
    id = db.Column(db.Integer, primary_key=True)
    driver_route_id = db.Column(db.Integer, db.ForeignKey('driver_route.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=False)
    
    # Incident details
    incident_type = db.Column(db.String(50), nullable=False)  # breakdown, accident, personal_emergency, etc.
    description = db.Column(db.Text, nullable=True)
    location_lat = db.Column(db.Float, nullable=False)
    location_lng = db.Column(db.Float, nullable=False)
    location_address = db.Column(db.String(200), nullable=True)
    
    # Status tracking
    reported_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='reported')  # reported, assistance_assigned, resolved, cancelled
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships will be set up in app.py after all models are defined
    
    def to_dict(self):
        # Import needed here to avoid circular reference - replaced with db.session query
        # Instead of import, use session query for Driver
        driver = None
        try:
            driver_model = db.Model.registry._class_registry['Driver']
            driver = db.session.query(driver_model).filter_by(id=self.driver_id).first()
        except:
            # Fallback in case the registry look-up fails
            pass
            
        driver_name = f"{driver.first_name} {driver.last_name}" if driver else "Unknown Driver"
        
        # Build the dictionary
        data = {
            'id': self.id,
            'driver_route_id': self.driver_route_id,
            'driver_id': self.driver_id,
            'driver_name': driver_name,
            'incident_type': self.incident_type,
            'description': self.description,
            'location': {
                'lat': self.location_lat,
                'lng': self.location_lng,
                'address': self.location_address
            },
            'reported_at': self.reported_at.isoformat() if self.reported_at else None,
            'status': self.status,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }
        
        # Add transfers if they exist
        if hasattr(self, 'transfers'):
            data['transfers'] = [transfer.to_dict() for transfer in self.transfers]
        else:
            data['transfers'] = []
            
        return data