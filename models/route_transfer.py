from datetime import datetime
import json
from models.db_setup import db

class RouteTransfer(db.Model):
    """Model for tracking route reassignments from one driver to another."""
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('route_incident.id'), nullable=False)
    
    # Original route information
    original_driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=False)
    original_driver_route_id = db.Column(db.Integer, db.ForeignKey('driver_route.id'), nullable=False)
    
    # New driver information
    new_driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=True)
    new_driver_route_id = db.Column(db.Integer, db.ForeignKey('driver_route.id'), nullable=True)
    
    # Transfer details
    stop_ids = db.Column(db.Text, nullable=False)  # JSON array of stop IDs
    transfer_status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected, completed
    transfer_created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transfer_accepted_at = db.Column(db.DateTime, nullable=True)
    transfer_completed_at = db.Column(db.DateTime, nullable=True)
    
    # Vehicle information
    vehicle_type_required = db.Column(db.String(50), nullable=True)
    min_capacity_required = db.Column(db.Float, nullable=True)
    
    # Relationships will be set up in app.py after all models are defined
    
    @property
    def stop_id_list(self):
        """Convert JSON string to list of stop IDs."""
        return json.loads(self.stop_ids) if self.stop_ids else []
    
    @stop_id_list.setter
    def stop_id_list(self, ids):
        """Convert list of stop IDs to JSON string."""
        self.stop_ids = json.dumps(ids)
    
    def to_dict(self):
        # Import needed here to avoid circular reference - replaced with db queries
        driver_model = db.Model.registry._class_registry['Driver']
        
        # Get driver data safely
        original_driver = db.session.query(driver_model).filter_by(id=self.original_driver_id).first()
        original_driver_name = f"{original_driver.first_name} {original_driver.last_name}" if original_driver else "Unknown"
        
        new_driver = db.session.query(driver_model).filter_by(id=self.new_driver_id).first() if self.new_driver_id else None
        new_driver_name = f"{new_driver.first_name} {new_driver.last_name}" if new_driver else "Unassigned"
        
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'original_driver': {
                'id': self.original_driver_id,
                'name': original_driver_name
            },
            'new_driver': {
                'id': self.new_driver_id,
                'name': new_driver_name
            },
            'stop_count': len(self.stop_id_list),
            'status': self.transfer_status,
            'created_at': self.transfer_created_at.isoformat() if self.transfer_created_at else None,
            'accepted_at': self.transfer_accepted_at.isoformat() if self.transfer_accepted_at else None,
            'completed_at': self.transfer_completed_at.isoformat() if self.transfer_completed_at else None,
            'vehicle_requirements': {
                'type': self.vehicle_type_required,
                'min_capacity': self.min_capacity_required
            }
        }