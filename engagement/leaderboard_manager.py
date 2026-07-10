"""Gestor de Rankings"""
from database import db_manager

class LeaderboardManager:
    @staticmethod
    def get_global_leaderboard(period='all_time', limit=100):
        """Obtiene ranking global"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        if period == 'weekly':
            order_by = 'weekly_points'
        elif period == 'monthly':
            order_by = 'monthly_points'
        else:
            order_by = 'total_points'
        
        leaders = c.execute(f'''
            SELECT u.username, u.full_name, up.{order_by} as points, up.level
            FROM user_points up
            JOIN users u ON up.user_id = u.username
            WHERE u.role = 'student'
            ORDER BY points DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        
        return [{'rank': idx+1, 'username': l[0], 'full_name': l[1], 
                 'points': l[2], 'level': l[3]} for idx, l in enumerate(leaders)]
    
    @staticmethod
    def get_user_rank(user_id, period='all_time'):
        """Obtiene posición del usuario en el ranking"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        if period == 'weekly':
            points_col = 'weekly_points'
        elif period == 'monthly':
            points_col = 'monthly_points'
        else:
            points_col = 'total_points'
        
        rank = c.execute(f'''
            SELECT COUNT(*) + 1
            FROM user_points
            WHERE {points_col} > (SELECT {points_col} FROM user_points WHERE user_id = ?)
        ''', (user_id,)).fetchone()[0]
        
        return rank
