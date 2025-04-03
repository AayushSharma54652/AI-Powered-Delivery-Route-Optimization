# utils/notification_service.py
from datetime import datetime
import json
from models.db_setup import db

class Notification(db.Model):
    """Model for storing notifications."""
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, nullable=False)  # Driver ID or admin ID
    recipient_type = db.Column(db.String(20), default='driver')  # driver or admin
    notification_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    data = db.Column(db.Text, nullable=True)  # JSON data
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'notification_type': self.notification_type,
            'content': self.content,
            'data': json.loads(self.data) if self.data else None,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }

def send_driver_notification(driver_id, notification_type, data=None):
    """
    Send a notification to a driver.
    
    Args:
        driver_id (int): ID of the driver
        notification_type (str): Type of notification
        data (dict, optional): Additional data for the notification
    
    Returns:
        Notification: The created notification
    """
    import json
    
    # Create notification content based on type
    content = ''
    if notification_type == 'assistance_needed':
        content = 'A driver nearby needs assistance with their route. Can you help?'
    elif notification_type == 'assistance_assigned':
        content = 'Help is on the way! Another driver has accepted to take over your remaining stops.'
    elif notification_type == 'transfer_completed':
        content = 'Route transfer has been completed successfully.'
    else:
        content = 'You have a new notification.'
    
    # Create the notification
    notification = Notification(
        recipient_id=driver_id,
        recipient_type='driver',
        notification_type=notification_type,
        content=content,
        data=json.dumps(data) if data else None
    )
    
    db.session.add(notification)
    db.session.commit()
    
    # In a production system, you would also push this notification
    # to the driver's device via WebSockets, push notifications, etc.
    # This would make it real-time.
    
    return notification

def notify_admin(notification_type, data=None):
    """
    Send a notification to all admin users.
    
    Args:
        notification_type (str): Type of notification
        data (dict, optional): Additional data for the notification
    
    Returns:
        list: List of created notifications
    """
    import json
    
    # Get all admin users (simplified for now)
    # In a real system, you'd have an Admin model
    admin_ids = [1]  # Assuming admin ID 1 for simplicity
    
    # Create notification content based on type
    content = ''
    if notification_type == 'incident_reported':
        content = 'A driver has reported an incident and needs assistance.'
    else:
        content = 'New system notification.'
    
    notifications = []
    for admin_id in admin_ids:
        notification = Notification(
            recipient_id=admin_id,
            recipient_type='admin',
            notification_type=notification_type,
            content=content,
            data=json.dumps(data) if data else None
        )
        
        db.session.add(notification)
        notifications.append(notification)
    
    db.session.commit()
    
    # Again, in a production system, you'd push these to admin dashboards
    
    return notifications