"""Gestor de Duelos 1v1"""
from database import db_manager
from datetime import datetime

class DuelManager:
    @staticmethod
    def create_duel(challenger_id, opponent_id, challenge_id=None, time_limit=30):
        """Crea un duelo"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO code_duels (challenger_id, opponent_id, challenge_id, time_limit_minutes, status)
            VALUES (?, ?, ?, ?, 'pending')
        ''', (challenger_id, opponent_id, challenge_id, time_limit))
        
        conn.commit()
        
        # Notificar al oponente
        from .notification_manager import NotificationManager
        NotificationManager.create_notification(
            opponent_id, 'duel',
            '⚔️ Desafío de Duelo',
            f'{challenger_id} te ha retado a un duelo de código!',
            f'/duel/{c.lastrowid}'
        )
        
        return c.lastrowid
    
    @staticmethod
    def accept_duel(duel_id):
        """Acepta un duelo"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            UPDATE code_duels 
            SET status = 'active', started_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
        ''', (duel_id,))
        
        conn.commit()
        return c.rowcount > 0
    
    @staticmethod
    def complete_duel(duel_id, challenger_score, opponent_score):
        """Completa un duelo"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        winner_id = None
        if challenger_score > opponent_score:
            winner_id = c.execute('SELECT challenger_id FROM code_duels WHERE id = ?', (duel_id,)).fetchone()[0]
        elif opponent_score > challenger_score:
            winner_id = c.execute('SELECT opponent_id FROM code_duels WHERE id = ?', (duel_id,)).fetchone()[0]
        
        c.execute('''
            UPDATE code_duels
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                challenger_score = ?, opponent_score = ?, winner_id = ?
            WHERE id = ?
        ''', (challenger_score, opponent_score, winner_id, duel_id))
        
        conn.commit()
        
        # Dar puntos al ganador
        if winner_id:
            from .points_manager import PointsManager
            PointsManager.add_points(winner_id, 100, 'duel_won', 'Victoria en duelo')
        
        return winner_id
