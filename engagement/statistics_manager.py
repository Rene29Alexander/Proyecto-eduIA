"""Gestor de Estadísticas"""
from database import db_manager
from datetime import datetime, date, timedelta

class StatisticsManager:
    @staticmethod
    def initialize_user_stats(user_id):
        """Inicializa estadísticas del usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT OR IGNORE INTO user_statistics (user_id)
            VALUES (?)
        ''', (user_id,))
        conn.commit()
    
    @staticmethod
    def update_activity_calendar(user_id, exercises=0, time_minutes=0, points=0, challenges=0):
        """Actualiza calendario de actividad"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        today = date.today().isoformat()
        
        c.execute('''
            INSERT INTO activity_calendar 
            (user_id, activity_date, exercises_completed, time_spent_minutes, points_earned, challenges_completed)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, activity_date) DO UPDATE SET
                exercises_completed = exercises_completed + ?,
                time_spent_minutes = time_spent_minutes + ?,
                points_earned = points_earned + ?,
                challenges_completed = challenges_completed + ?
        ''', (user_id, today, exercises, time_minutes, points, challenges,
              exercises, time_minutes, points, challenges))
        
        conn.commit()
    
    @staticmethod
    def get_activity_calendar(user_id, days=365):
        """Obtiene calendario de actividad (estilo GitHub)"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        start_date = (date.today() - timedelta(days=days)).isoformat()
        
        activities = c.execute('''
            SELECT activity_date, exercises_completed, time_spent_minutes, points_earned
            FROM activity_calendar
            WHERE user_id = ? AND activity_date >= ?
            ORDER BY activity_date ASC
        ''', (user_id, start_date)).fetchall()
        
        return [{'date': a[0], 'exercises': a[1], 'time': a[2], 'points': a[3]} 
                for a in activities]
    
    @staticmethod
    def get_user_statistics(user_id):
        """Obtiene estadísticas completas del usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        stats = c.execute('''
            SELECT total_exercises, exercises_completed, total_time_minutes, 
                   average_score, best_language, courses_completed, duels_won, duels_lost
            FROM user_statistics WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        if not stats:
            StatisticsManager.initialize_user_stats(user_id)
            return {
                'total_exercises': 0, 'exercises_completed': 0, 'total_time_minutes': 0,
                'average_score': 0, 'best_language': None, 'courses_completed': 0,
                'duels_won': 0, 'duels_lost': 0
            }
        
        return {
            'total_exercises': stats[0],
            'exercises_completed': stats[1],
            'total_time_minutes': stats[2],
            'average_score': stats[3],
            'best_language': stats[4],
            'courses_completed': stats[5],
            'duels_won': stats[6],
            'duels_lost': stats[7]
        }
