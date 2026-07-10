"""
Gestor de Rachas (Streaks) para el sistema de engagement
Lógica:
- Responder correctamente la pregunta diaria suma 1 día a la racha
- Si pasan 24h sin responder (nuevo día sin actividad), la racha se resetea a 0
- El congelador protege la racha por exactamente 24h (1 día)
- Después de esas 24h, si no se respondió, la racha se resetea igual
- Responder mal NO suma racha (solo respuesta correcta suma)

NOTA IMPORTANTE - Zona horaria:
  SQLite guarda CURRENT_TIMESTAMP en UTC.
  Para ser consistente se usa datetime.utcnow().date() en todos los cálculos
  de fecha, evitando que diferencias de zona horaria rompan la detección
  de días consecutivos.
"""

from datetime import datetime, timedelta, date, timezone
from database import db_manager


class StreakManager:
    """Gestiona las rachas de actividad de los usuarios"""

    @staticmethod
    def _today():
        """
        Fecha actual en UTC — consistente con los timestamps de SQLite
        (CURRENT_TIMESTAMP también es UTC).
        """
        return datetime.now(timezone.utc).date()

    @staticmethod
    def _parse_date(date_str):
        """
        Parsea fecha desde string. Acepta:
          '2026-03-19'
          '2026-03-19 03:48:44'
          '2026-03-19 03:48:44.123456'
        Retorna objeto date o None.
        """
        if not date_str:
            return None
        try:
            return datetime.strptime(str(date_str).strip()[:10], '%Y-%m-%d').date()
        except Exception:
            return None

    @staticmethod
    def initialize_user_streak(user_id):
        """Inicializa la racha de un usuario si no existe"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT OR IGNORE INTO user_streaks
                (user_id, current_streak, longest_streak, last_activity_date, freeze_count, total_days_active)
                VALUES (?, 0, 0, NULL, 0, 0)
            ''', (user_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inicializando racha: {e}")
            return False

    @staticmethod
    def check_and_apply_streak_reset(user_id):
        """
        Verifica si la racha debe resetearse por inactividad.
        Reglas:
        - Si last_activity_date es de anteayer o antes → racha en riesgo
        - Si tiene congelador disponible → se consume y protege 1 día más
        - Si no tiene congelador → racha se resetea a 0
        Retorna: (racha_reseteada: bool, congelador_usado: bool)
        """
        conn = db_manager.get_connection()
        c = conn.cursor()

        StreakManager.initialize_user_streak(user_id)

        today = StreakManager._today()

        streak_data = c.execute('''
            SELECT current_streak, longest_streak, last_activity_date, freeze_count, total_days_active
            FROM user_streaks WHERE user_id = ?
        ''', (user_id,)).fetchone()

        if not streak_data:
            return False, False

        current_streak, longest_streak, last_activity_str, freeze_count, total_days = streak_data

        if current_streak == 0 or not last_activity_str:
            return False, False

        last_activity = StreakManager._parse_date(last_activity_str)
        if not last_activity:
            return False, False

        days_diff = (today - last_activity).days

        # Racha segura si respondió hoy o ayer
        if days_diff <= 1:
            return False, False

        # Más de 1 día sin actividad → racha en riesgo
        if freeze_count > 0:
            yesterday = today - timedelta(days=1)
            c.execute('''
                UPDATE user_streaks
                SET freeze_count = freeze_count - 1,
                    last_activity_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (yesterday.isoformat(), user_id))
            conn.commit()
            print(f"[STREAK] Congelador usado para {user_id}. Racha protegida por 1 día más.")
            return False, True
        else:
            c.execute('''
                UPDATE user_streaks
                SET current_streak = 0,
                    last_activity_date = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            print(f"[STREAK] Racha reseteada para {user_id} por inactividad.")
            return True, False

    @staticmethod
    def update_streak(user_id):
        """
        Actualiza la racha del usuario cuando responde correctamente.
        - Si ya respondió hoy (UTC) → no suma, retorna True
        - Si respondió ayer (UTC) → suma 1 día consecutivo
        - Si saltó más de 1 día → resetea a 1
        - Primera vez → empieza en 1
        """
        conn = db_manager.get_connection()
        c = conn.cursor()

        StreakManager.initialize_user_streak(user_id)

        today = StreakManager._today()

        streak_data = c.execute('''
            SELECT current_streak, longest_streak, last_activity_date, freeze_count, total_days_active
            FROM user_streaks WHERE user_id = ?
        ''', (user_id,)).fetchone()

        if not streak_data:
            return False

        current_streak, longest_streak, last_activity_str, freeze_count, total_days = streak_data

        last_activity = StreakManager._parse_date(last_activity_str)

        # Ya respondió hoy → no duplicar
        if last_activity and last_activity == today:
            return True

        # Calcular nueva racha
        if last_activity:
            days_diff = (today - last_activity).days
            if days_diff == 1:
                # Día consecutivo → sumar
                current_streak += 1
            else:
                # Saltó días → resetear y empezar desde 1
                current_streak = 1
        else:
            # Primera actividad
            current_streak = 1

        if current_streak > longest_streak:
            longest_streak = current_streak

        total_days += 1

        c.execute('''
            UPDATE user_streaks
            SET current_streak = ?, longest_streak = ?, last_activity_date = ?,
                total_days_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (current_streak, longest_streak, today.isoformat(), total_days, user_id))
        conn.commit()

        print(f"[STREAK] {user_id}: racha actualizada a {current_streak} días (last={today})")

        try:
            from .badge_manager import BadgeManager
            BadgeManager.check_streak_badges(user_id, current_streak)
        except Exception as e:
            print(f"Error verificando badges: {e}")

        return True

    @staticmethod
    def get_streak_info(user_id):
        """
        Obtiene información de la racha del usuario.
        Aplica automáticamente el reset o congelador si corresponde.
        """
        StreakManager.check_and_apply_streak_reset(user_id)

        conn = db_manager.get_connection()
        c = conn.cursor()

        streak_data = c.execute('''
            SELECT current_streak, longest_streak, last_activity_date, freeze_count, total_days_active
            FROM user_streaks WHERE user_id = ?
        ''', (user_id,)).fetchone()

        if not streak_data:
            StreakManager.initialize_user_streak(user_id)
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'last_activity_date': None,
                'freeze_count': 0,
                'total_days_active': 0,
                'is_at_risk': False,
                'freeze_active': False
            }

        current_streak, longest_streak, last_activity_str, freeze_count, total_days = streak_data

        is_at_risk = False
        freeze_active = False

        if last_activity_str and current_streak > 0:
            last_activity = StreakManager._parse_date(last_activity_str)
            if last_activity:
                today = StreakManager._today()
                days_since = (today - last_activity).days
                is_at_risk = days_since >= 1
                freeze_active = is_at_risk and freeze_count > 0

        return {
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'last_activity_date': last_activity_str,
            'freeze_count': freeze_count,
            'total_days_active': total_days,
            'is_at_risk': is_at_risk,
            'freeze_active': freeze_active
        }

    @staticmethod
    def use_freeze(user_id):
        """Usa un congelador de racha manualmente"""
        conn = db_manager.get_connection()
        c = conn.cursor()

        row = c.execute('SELECT freeze_count FROM user_streaks WHERE user_id = ?', (user_id,)).fetchone()
        if not row or row[0] <= 0:
            return False, "No tienes congeladores disponibles"

        # Avanzar last_activity_date 1 día para proteger la racha
        today = StreakManager._today()
        c.execute('''
            UPDATE user_streaks
            SET freeze_count = freeze_count - 1,
                last_activity_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (today.isoformat(), user_id))
        conn.commit()
        return True, "Congelador usado exitosamente. Tu racha está protegida por hoy."

    @staticmethod
    def add_freeze(user_id, count=1):
        """Agrega congeladores de racha al usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()

        StreakManager.initialize_user_streak(user_id)

        c.execute('''
            UPDATE user_streaks
            SET freeze_count = freeze_count + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (count, user_id))
        conn.commit()
        return True

    @staticmethod
    def get_top_streaks(limit=3):
        """
        Retorna el top N de usuarios con mayor racha actual.
        Retorna lista de dicts con user_id, display_name, current_streak, longest_streak.
        """
        conn = db_manager.get_connection()
        try:
            rows = conn.execute('''
                SELECT s.user_id,
                       COALESCE(u.full_name, s.user_id) AS display_name,
                       s.current_streak,
                       s.longest_streak
                FROM user_streaks s
                LEFT JOIN users u ON s.user_id = u.username
                WHERE s.current_streak > 0
                ORDER BY s.current_streak DESC, s.longest_streak DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error obteniendo top streaks: {e}")
            return []
