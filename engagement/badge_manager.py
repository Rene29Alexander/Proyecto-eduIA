"""Gestor de Badges y Logros"""
from database import db_manager

class BadgeManager:
    @staticmethod
    def check_streak_badges(user_id, streak_days):
        """Verifica y otorga badges de racha"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Badges de racha: 7, 30, 100, 365 días
        streak_badges = {
            7: 'streak_7',
            30: 'streak_30',
            100: 'streak_100',
            365: 'streak_365'
        }
        
        for days, badge_key in streak_badges.items():
            if streak_days >= days:
                BadgeManager.award_badge(user_id, badge_key)
    
    @staticmethod
    def check_level_badges(user_id, level):
        """Verifica badges de nivel"""
        # Implementar lógica similar
        pass
    
    @staticmethod
    def award_badge(user_id, badge_key):
        """Otorga un badge a un usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Obtener badge
        badge = c.execute('SELECT id, points_reward FROM badges WHERE badge_key = ?', (badge_key,)).fetchone()
        if not badge:
            return False
        
        badge_id, points = badge
        
        # Verificar si ya lo tiene
        existing = c.execute('SELECT 1 FROM user_badges WHERE user_id = ? AND badge_id = ?', 
                            (user_id, badge_id)).fetchone()
        if existing:
            return False
        
        # Otorgar badge
        c.execute('INSERT INTO user_badges (user_id, badge_id) VALUES (?, ?)', (user_id, badge_id))
        
        # Dar puntos de recompensa
        if points > 0:
            from .points_manager import PointsManager
            PointsManager.add_points(user_id, points, 'badge_earned', f'Badge: {badge_key}')
        
        conn.commit()
        return True
    
    @staticmethod
    def get_user_badges(user_id):
        """Obtiene badges del usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        badges = c.execute('''
            SELECT b.badge_key, b.name, b.description, b.icon, b.category, b.rarity, ub.earned_at
            FROM user_badges ub
            JOIN badges b ON ub.badge_id = b.id
            WHERE ub.user_id = ?
            ORDER BY ub.earned_at DESC
        ''', (user_id,)).fetchall()
        
        return [{'key': b[0], 'name': b[1], 'description': b[2], 'icon': b[3], 
                 'category': b[4], 'rarity': b[5], 'earned_at': b[6]} for b in badges]
