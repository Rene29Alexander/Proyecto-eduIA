"""
Gestor de Puntos y Niveles para el sistema de engagement
"""

from datetime import datetime
from database import db_manager
import json
import math

class PointsManager:
    """Gestiona puntos, experiencia y niveles de usuarios"""
    
    # Configuración de niveles
    LEVEL_MULTIPLIER = 1.5
    BASE_POINTS_PER_LEVEL = 100
    
    @staticmethod
    def calculate_points_for_level(level):
        """Calcula puntos necesarios para alcanzar un nivel"""
        return int(PointsManager.BASE_POINTS_PER_LEVEL * (PointsManager.LEVEL_MULTIPLIER ** (level - 1)))
    
    @staticmethod
    def calculate_level_from_points(total_points):
        """Calcula el nivel basado en puntos totales"""
        level = 1
        points_needed = 0
        
        while points_needed <= total_points:
            points_needed += PointsManager.calculate_points_for_level(level)
            if points_needed <= total_points:
                level += 1
        
        return level
    
    @staticmethod
    def initialize_user_points(user_id):
        """Inicializa los puntos de un usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT OR IGNORE INTO user_points 
                (user_id, total_points, level, experience_points, points_to_next_level)
                VALUES (?, 0, 1, 0, ?)
            ''', (user_id, PointsManager.calculate_points_for_level(1)))
            
            # Inicializar monedas
            c.execute('''
                INSERT OR IGNORE INTO user_coins (user_id, total_coins)
                VALUES (?, 0)
            ''', (user_id,))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inicializando puntos: {e}")
            return False
    
    @staticmethod
    def add_points(user_id, points, source, description=None, metadata=None):
        """Agrega puntos a un usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Inicializar si no existe
        PointsManager.initialize_user_points(user_id)
        
        # Obtener datos actuales
        user_data = c.execute('''
            SELECT total_points, level, experience_points, points_to_next_level
            FROM user_points WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        if not user_data:
            return False
        
        total_points, current_level, exp_points, points_to_next = user_data
        
        # Actualizar puntos
        new_total = total_points + points
        new_exp = exp_points + points
        
        # Verificar subida de nivel
        level_up = False
        new_level = current_level
        
        while new_exp >= points_to_next:
            new_exp -= points_to_next
            new_level += 1
            level_up = True
            points_to_next = PointsManager.calculate_points_for_level(new_level)
        
        # Actualizar en BD
        c.execute('''
            UPDATE user_points
            SET total_points = ?, level = ?, experience_points = ?, 
                points_to_next_level = ?, weekly_points = weekly_points + ?,
                monthly_points = monthly_points + ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (new_total, new_level, new_exp, points_to_next, points, points, user_id))
        
        # Registrar transacción
        c.execute('''
            INSERT INTO point_transactions
            (user_id, points, transaction_type, source, description, metadata)
            VALUES (?, ?, 'earn', ?, ?, ?)
        ''', (user_id, points, source, description, json.dumps(metadata) if metadata else None))
        
        # Dar monedas (1 moneda por cada 10 puntos)
        coins_earned = points // 10
        if coins_earned > 0:
            PointsManager.add_coins(user_id, coins_earned)
        
        conn.commit()
        
        # Si subió de nivel, verificar badges
        if level_up:
            from .badge_manager import BadgeManager
            BadgeManager.check_level_badges(user_id, new_level)
            
            # Notificar subida de nivel
            from .notification_manager import NotificationManager
            NotificationManager.create_notification(
                user_id, 'achievement',
                f'¡Nivel {new_level}!',
                f'¡Felicitaciones! Has alcanzado el nivel {new_level}',
                None
            )
        
        return {
            'points_added': points,
            'new_total': new_total,
            'level_up': level_up,
            'new_level': new_level,
            'coins_earned': coins_earned
        }

    
    @staticmethod
    def get_user_points_info(user_id):
        """Obtiene información de puntos del usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        user_data = c.execute('''
            SELECT total_points, level, experience_points, points_to_next_level,
                   weekly_points, monthly_points, rank_position
            FROM user_points WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        if not user_data:
            PointsManager.initialize_user_points(user_id)
            return {
                'total_points': 0,
                'level': 1,
                'experience_points': 0,
                'points_to_next_level': PointsManager.calculate_points_for_level(1),
                'weekly_points': 0,
                'monthly_points': 0,
                'rank_position': None,
                'progress_percentage': 0
            }
        
        total, level, exp, points_to_next, weekly, monthly, rank = user_data
        progress = (exp / points_to_next * 100) if points_to_next > 0 else 0
        
        return {
            'total_points': total,
            'level': level,
            'experience_points': exp,
            'points_to_next_level': points_to_next,
            'weekly_points': weekly,
            'monthly_points': monthly,
            'rank_position': rank,
            'progress_percentage': round(progress, 1)
        }
    
    @staticmethod
    def add_coins(user_id, coins):
        """Agrega monedas virtuales a un usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            UPDATE user_coins
            SET total_coins = total_coins + ?,
                coins_earned = coins_earned + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (coins, coins, user_id))
        
        if c.rowcount == 0:
            c.execute('''
                INSERT INTO user_coins (user_id, total_coins, coins_earned)
                VALUES (?, ?, ?)
            ''', (user_id, coins, coins))
        
        conn.commit()
        return True
    
    @staticmethod
    def spend_coins(user_id, coins):
        """Gasta monedas virtuales"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Verificar saldo
        balance = c.execute('''
            SELECT total_coins FROM user_coins WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        if not balance or balance[0] < coins:
            return False, "Saldo insuficiente"
        
        c.execute('''
            UPDATE user_coins
            SET total_coins = total_coins - ?,
                coins_spent = coins_spent + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (coins, coins, user_id))
        
        conn.commit()
        return True, "Compra exitosa"
    
    @staticmethod
    def get_user_coins(user_id):
        """Obtiene el saldo de monedas del usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        coins_data = c.execute('''
            SELECT total_coins, coins_earned, coins_spent
            FROM user_coins WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        if not coins_data:
            return {'total_coins': 0, 'coins_earned': 0, 'coins_spent': 0}
        
        return {
            'total_coins': coins_data[0],
            'coins_earned': coins_data[1],
            'coins_spent': coins_data[2]
        }
