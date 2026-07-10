"""
Gestor de Desafíos Diarios para el sistema de engagement
"""

from datetime import datetime, date
from database import db_manager
import json

class ChallengeManager:
    """Gestiona los desafíos diarios"""
    
    @staticmethod
    def create_daily_challenge(challenge_date, language, difficulty, title, description, 
                               exercise_code=None, solution_code=None, test_cases=None, 
                               points=50, bonus_points=20):
        """Crea un desafío diario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT INTO daily_challenges 
                (challenge_date, language, difficulty, title, description, exercise_code, 
                 solution_code, test_cases, points, bonus_points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (challenge_date, language, difficulty, title, description, exercise_code,
                  solution_code, test_cases, points, bonus_points))
            
            conn.commit()
            return c.lastrowid
        except Exception as e:
            print(f"Error creando desafío diario: {e}")
            return None
    
    @staticmethod
    def get_today_challenge(language='Python'):
        """Obtiene el desafío del día para un lenguaje, generándolo si no existe"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        today = date.today().isoformat()
        
        challenge = c.execute('''
            SELECT id, challenge_date, language, difficulty, title, description, 
                   exercise_code, solution_code, test_cases, points, bonus_points
            FROM daily_challenges
            WHERE challenge_date = ? AND language = ?
        ''', (today, language)).fetchone()
        
        if challenge:
            return {
                'id': challenge[0],
                'challenge_date': challenge[1],
                'language': challenge[2],
                'difficulty': challenge[3],
                'title': challenge[4],
                'description': challenge[5],
                'exercise_code': challenge[6],
                'solution_code': challenge[7],
                'test_cases': challenge[8],
                'points': challenge[9],
                'bonus_points': challenge[10]
            }
        
        # Si no existe, generar uno nuevo con IA
        try:
            from utils_ai import generate_daily_challenge
            import google.generativeai as genai
            import streamlit as st
            
            # Configurar modelo
            api_key = st.secrets.get("GEMINI_API_KEY", "")
            if not api_key:
                return None
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
            
            # Generar desafío con IA
            import random
            difficulty = random.choice(['easy', 'medium', 'hard'])
            challenge_data = generate_daily_challenge(model, language, difficulty)
            
            if not challenge_data:
                return None
            
            # Guardar en base de datos
            # Crear descripción estructurada en JSON
            structured_description = json.dumps({
                'description': challenge_data['description'],
                'input_description': challenge_data.get('input_description', ''),
                'output_description': challenge_data.get('output_description', ''),
                'example_1_input': challenge_data.get('example_1_input', ''),
                'example_1_output': challenge_data.get('example_1_output', ''),
                'example_2_input': challenge_data.get('example_2_input', ''),
                'example_2_output': challenge_data.get('example_2_output', ''),
                'restrictions': challenge_data.get('restrictions', []),
                'hint': challenge_data.get('hint', '')
            })
            
            c.execute('''
                INSERT INTO daily_challenges 
                (challenge_date, language, difficulty, title, description, exercise_code, 
                 solution_code, test_cases, points, bonus_points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today,
                language,
                challenge_data['difficulty'],
                challenge_data['title'],
                structured_description,  # Guardar como JSON
                '',  # exercise_code vacío
                challenge_data.get('solution_code', ''),
                json.dumps(challenge_data.get('test_cases', [])),
                challenge_data['points'],
                challenge_data['bonus_points']
            ))
            
            conn.commit()
            challenge_id = c.lastrowid
            
            # Retornar desafío generado
            return {
                'id': challenge_id,
                'challenge_date': today,
                'language': language,
                'difficulty': challenge_data['difficulty'],
                'title': challenge_data['title'],
                'description': structured_description,  # Retornar JSON
                'exercise_code': '',
                'solution_code': challenge_data.get('solution_code', ''),
                'test_cases': json.dumps(challenge_data.get('test_cases', [])),
                'points': challenge_data['points'],
                'bonus_points': challenge_data['bonus_points']
            }
        except Exception as e:
            print(f"Error generando desafío automático: {e}")
            return None
    
    @staticmethod
    def submit_challenge_attempt(challenge_id, user_id, submitted_code, score, 
                                 completed, feedback=None, time_spent=0):
        """Registra un intento de desafío"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Obtener número de intento
        attempt_count = c.execute('''
            SELECT COUNT(*) FROM daily_challenge_attempts
            WHERE challenge_id = ? AND user_id = ?
        ''', (challenge_id, user_id)).fetchone()[0]
        
        attempt_number = attempt_count + 1
        
        # Calcular puntos ganados
        challenge_data = c.execute('''
            SELECT points, bonus_points FROM daily_challenges WHERE id = ?
        ''', (challenge_id,)).fetchone()
        
        if not challenge_data:
            return None
        
        base_points, bonus_points = challenge_data
        points_earned = 0
        
        if completed:
            points_earned = base_points
            # Bonus por primer intento
            if attempt_number == 1:
                points_earned += bonus_points
        
        # Insertar intento
        c.execute('''
            INSERT INTO daily_challenge_attempts
            (challenge_id, user_id, submitted_code, score, points_earned, completed, 
             feedback, attempt_number, time_spent_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (challenge_id, user_id, submitted_code, score, points_earned, completed,
              feedback, attempt_number, time_spent))
        
        conn.commit()
        
        # Si completó, dar puntos y actualizar racha
        if completed:
            from .points_manager import PointsManager
            from .streak_manager import StreakManager
            
            PointsManager.add_points(user_id, points_earned, 'daily_challenge', 
                                    f'Desafío diario completado')
            StreakManager.update_streak(user_id)
        
        return {
            'attempt_id': c.lastrowid,
            'points_earned': points_earned,
            'attempt_number': attempt_number
        }

    
    @staticmethod
    def get_user_challenge_status(challenge_id, user_id):
        """Obtiene el estado del desafío para un usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        attempts = c.execute('''
            SELECT id, score, points_earned, completed, attempt_number, created_at
            FROM daily_challenge_attempts
            WHERE challenge_id = ? AND user_id = ?
            ORDER BY attempt_number DESC
        ''', (challenge_id, user_id)).fetchall()
        
        if not attempts:
            return {
                'attempted': False,
                'completed': False,
                'attempts_count': 0,
                'best_score': 0,
                'total_points': 0
            }
        
        completed = any(a[3] for a in attempts)
        best_score = max(a[1] for a in attempts)
        total_points = sum(a[2] for a in attempts)
        
        return {
            'attempted': True,
            'completed': completed,
            'attempts_count': len(attempts),
            'best_score': best_score,
            'total_points': total_points,
            'attempts': [
                {
                    'id': a[0],
                    'score': a[1],
                    'points_earned': a[2],
                    'completed': a[3],
                    'attempt_number': a[4],
                    'created_at': a[5]
                } for a in attempts
            ]
        }
    
    @staticmethod
    def get_challenge_leaderboard(challenge_id, limit=10):
        """Obtiene el ranking de un desafío"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        leaderboard = c.execute('''
            SELECT u.username, u.full_name, MAX(dca.score) as best_score, 
                   MIN(dca.attempt_number) as attempts, MAX(dca.points_earned) as points
            FROM daily_challenge_attempts dca
            JOIN users u ON dca.user_id = u.username
            WHERE dca.challenge_id = ? AND dca.completed = 1
            GROUP BY dca.user_id
            ORDER BY best_score DESC, attempts ASC
            LIMIT ?
        ''', (challenge_id, limit)).fetchall()
        
        return [
            {
                'rank': idx + 1,
                'username': row[0],
                'full_name': row[1],
                'score': row[2],
                'attempts': row[3],
                'points': row[4]
            } for idx, row in enumerate(leaderboard)
        ]

    
    @staticmethod
    def delete_today_challenge(language='Python'):
        """Elimina el desafío de hoy para regenerarlo"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        today = date.today().isoformat()
        
        try:
            c.execute('''
                DELETE FROM daily_challenges
                WHERE challenge_date = ? AND language = ?
            ''', (today, language))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error eliminando desafío: {e}")
            return False
