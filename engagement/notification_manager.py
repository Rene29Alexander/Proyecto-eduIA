"""Gestor de Notificaciones"""
from database import db_manager
from datetime import datetime

class NotificationManager:
    @staticmethod
    def create_notification(user_id, notif_type, title, message, action_url=None):
        """Crea una notificación"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO push_notifications (user_id, notification_type, title, message, action_url)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, notif_type, title, message, action_url))
        conn.commit()
        return c.lastrowid
    
    @staticmethod
    def get_unread_notifications(user_id, limit=10):
        """Obtiene notificaciones no leídas"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        notifs = c.execute('''
            SELECT id, notification_type, title, message, action_url, created_at
            FROM push_notifications
            WHERE user_id = ? AND is_read = 0
            ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit)).fetchall()
        
        return [{'id': n[0], 'type': n[1], 'title': n[2], 'message': n[3], 
                 'action_url': n[4], 'created_at': n[5]} for n in notifs]
    
    @staticmethod
    def mark_as_read(notification_id):
        """Marca notificación como leída"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        c.execute('UPDATE push_notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP WHERE id = ?', 
                 (notification_id,))
        conn.commit()
