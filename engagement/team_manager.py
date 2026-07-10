"""Gestor de Equipos"""
from database import db_manager
import random, string

class TeamManager:
    @staticmethod
    def create_team(team_name, leader_id, description=None, max_members=10):
        """Crea un equipo"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Generar código único
        team_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        c.execute('''
            INSERT INTO teams (team_name, team_code, description, leader_id, max_members)
            VALUES (?, ?, ?, ?, ?)
        ''', (team_name, team_code, description, leader_id, max_members))
        
        team_id = c.lastrowid
        
        # Agregar líder como miembro
        c.execute('''
            INSERT INTO team_members (team_id, user_id, role)
            VALUES (?, ?, 'leader')
        ''', (team_id, leader_id))
        
        conn.commit()
        return {'team_id': team_id, 'team_code': team_code}
    
    @staticmethod
    def join_team(team_code, user_id):
        """Unirse a un equipo"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Verificar equipo
        team = c.execute('SELECT id, max_members FROM teams WHERE team_code = ?', (team_code,)).fetchone()
        if not team:
            return False, "Equipo no encontrado"
        
        team_id, max_members = team
        
        # Verificar capacidad
        current_members = c.execute('SELECT COUNT(*) FROM team_members WHERE team_id = ?', (team_id,)).fetchone()[0]
        if current_members >= max_members:
            return False, "Equipo lleno"
        
        # Unirse
        try:
            c.execute('INSERT INTO team_members (team_id, user_id) VALUES (?, ?)', (team_id, user_id))
            conn.commit()
            return True, "Te uniste al equipo"
        except:
            return False, "Ya eres miembro de este equipo"
    
    @staticmethod
    def get_team_leaderboard(limit=20):
        """Ranking de equipos"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        teams = c.execute('''
            SELECT t.team_name, t.total_points, t.level, COUNT(tm.user_id) as members
            FROM teams t
            LEFT JOIN team_members tm ON t.id = tm.team_id
            GROUP BY t.id
            ORDER BY t.total_points DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        
        return [{'rank': idx+1, 'name': t[0], 'points': t[1], 'level': t[2], 'members': t[3]} 
                for idx, t in enumerate(teams)]
