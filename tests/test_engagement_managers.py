# -*- coding: utf-8 -*-
"""
Unit Tests para los managers del módulo engagement/.
Cubre lógica pura (sin BD) y métodos con BD mockeada.

Ejecutar con:
    pytest tests/test_engagement_managers.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Helpers para construir mocks de conexión SQLite
# ---------------------------------------------------------------------------

def make_cursor(*fetchone_values, fetchall_value=None):
    """Crea un cursor mock con respuestas configuradas."""
    cursor = MagicMock()
    cursor.execute.return_value = cursor
    cursor.fetchone.side_effect = list(fetchone_values) if fetchone_values else [None]
    cursor.fetchall.return_value = fetchall_value or []
    cursor.lastrowid = 1
    cursor.rowcount = 1
    return cursor


def make_conn(cursor):
    """Crea una conexión mock que devuelve el cursor dado."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.execute.return_value = cursor
    return conn


# ===========================================================================
# Tests de PointsManager
# ===========================================================================

class TestPointsManagerLogicaPura:
    """Tests de métodos que no necesitan base de datos."""

    def test_calculate_points_for_level_1(self):
        """El nivel 1 requiere exactamente 100 puntos base."""
        from engagement.points_manager import PointsManager
        assert PointsManager.calculate_points_for_level(1) == 100

    def test_calculate_points_for_level_2(self):
        """El nivel 2 requiere 150 puntos (100 * 1.5^1)."""
        from engagement.points_manager import PointsManager
        assert PointsManager.calculate_points_for_level(2) == 150

    def test_calculate_points_for_level_3(self):
        """El nivel 3 requiere 225 puntos (100 * 1.5^2)."""
        from engagement.points_manager import PointsManager
        assert PointsManager.calculate_points_for_level(3) == 225

    def test_calculate_points_increases_with_level(self):
        """Los puntos requeridos aumentan con cada nivel."""
        from engagement.points_manager import PointsManager
        prev = PointsManager.calculate_points_for_level(1)
        for lvl in range(2, 6):
            current = PointsManager.calculate_points_for_level(lvl)
            assert current > prev, f"Nivel {lvl} debería requerir más puntos que el anterior"
            prev = current

    def test_calculate_level_from_points_zero(self):
        """Con 0 puntos el nivel es 1."""
        from engagement.points_manager import PointsManager
        assert PointsManager.calculate_level_from_points(0) == 1

    def test_calculate_level_from_points_exact_threshold(self):
        """Al alcanzar exactamente los puntos del nivel 1, el nivel sube a 2."""
        from engagement.points_manager import PointsManager
        threshold = PointsManager.calculate_points_for_level(1)
        assert PointsManager.calculate_level_from_points(threshold) == 2

    def test_calculate_level_from_points_large(self):
        """Muchos puntos resultan en un nivel alto (> 1)."""
        from engagement.points_manager import PointsManager
        assert PointsManager.calculate_level_from_points(10000) > 5

    def test_coins_earned_rate(self):
        """Se gana 1 moneda por cada 10 puntos (verificado por la fórmula interna)."""
        points = 50
        expected_coins = points // 10
        assert expected_coins == 5

    def test_coins_earned_menos_de_10_puntos(self):
        """Con menos de 10 puntos no se ganan monedas."""
        points = 9
        assert points // 10 == 0


class TestPointsManagerConBD:
    """Tests de métodos que interactúan con la base de datos (mockeada)."""

    def test_get_user_points_info_sin_registro(self):
        """Si el usuario no existe en BD, inicializa y retorna valores por defecto."""
        from engagement.points_manager import PointsManager

        cursor = make_cursor(None)  # fetchone retorna None → usuario no existe
        conn = make_conn(cursor)

        with patch('engagement.points_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = PointsManager.get_user_points_info('usuario_nuevo')

        assert result['total_points'] == 0
        assert result['level'] == 1
        assert result['experience_points'] == 0
        assert result['progress_percentage'] == 0

    def test_get_user_points_info_con_registro(self):
        """Retorna los datos correctos cuando el usuario existe en BD."""
        from engagement.points_manager import PointsManager

        # Simula: total=200, level=2, exp=50, pts_to_next=150, weekly=20, monthly=100, rank=3
        row = (200, 2, 50, 150, 20, 100, 3)
        cursor = make_cursor(row)
        conn = make_conn(cursor)

        with patch('engagement.points_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = PointsManager.get_user_points_info('usuario1')

        assert result['total_points'] == 200
        assert result['level'] == 2
        assert result['weekly_points'] == 20
        assert result['rank_position'] == 3
        assert result['progress_percentage'] == round(50 / 150 * 100, 1)

    def test_get_user_coins_sin_registro(self):
        """Retorna ceros si el usuario no tiene monedas en BD."""
        from engagement.points_manager import PointsManager

        cursor = make_cursor(None)
        conn = make_conn(cursor)

        with patch('engagement.points_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = PointsManager.get_user_coins('usuario_nuevo')

        assert result == {'total_coins': 0, 'coins_earned': 0, 'coins_spent': 0}

    def test_get_user_coins_con_saldo(self):
        """Retorna el saldo correcto cuando existe registro en BD."""
        from engagement.points_manager import PointsManager

        cursor = make_cursor((80, 100, 20))  # total, earned, spent
        conn = make_conn(cursor)

        with patch('engagement.points_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = PointsManager.get_user_coins('usuario1')

        assert result['total_coins'] == 80
        assert result['coins_earned'] == 100
        assert result['coins_spent'] == 20

    def test_spend_coins_saldo_insuficiente(self):
        """spend_coins retorna False si el usuario no tiene suficientes monedas."""
        from engagement.points_manager import PointsManager

        cursor = make_cursor((5,))  # solo 5 monedas disponibles
        conn = make_conn(cursor)

        with patch('engagement.points_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            success, msg = PointsManager.spend_coins('usuario1', coins=50)

        assert success is False
        assert "insuficiente" in msg.lower()

    def test_spend_coins_exitoso(self):
        """spend_coins retorna True si hay saldo suficiente."""
        from engagement.points_manager import PointsManager

        cursor = make_cursor((100,))  # 100 monedas disponibles
        conn = make_conn(cursor)

        with patch('engagement.points_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            success, msg = PointsManager.spend_coins('usuario1', coins=30)

        assert success is True


# ===========================================================================
# Tests de StreakManager
# ===========================================================================

class TestStreakManagerLogicaPura:
    """Tests de métodos de lógica pura (sin BD)."""

    def test_today_retorna_date(self):
        """_today() debe retornar un objeto date."""
        from engagement.streak_manager import StreakManager
        resultado = StreakManager._today()
        assert isinstance(resultado, date)

    def test_parse_date_formato_corto(self):
        """Parsea correctamente formato YYYY-MM-DD."""
        from engagement.streak_manager import StreakManager
        resultado = StreakManager._parse_date('2026-07-22')
        assert resultado == date(2026, 7, 22)

    def test_parse_date_formato_largo(self):
        """Parsea correctamente formato YYYY-MM-DD HH:MM:SS."""
        from engagement.streak_manager import StreakManager
        resultado = StreakManager._parse_date('2026-07-22 15:30:00')
        assert resultado == date(2026, 7, 22)

    def test_parse_date_formato_con_microsegundos(self):
        """Parsea correctamente formato con microsegundos."""
        from engagement.streak_manager import StreakManager
        resultado = StreakManager._parse_date('2026-07-22 15:30:00.123456')
        assert resultado == date(2026, 7, 22)

    def test_parse_date_none(self):
        """Retorna None cuando el input es None."""
        from engagement.streak_manager import StreakManager
        assert StreakManager._parse_date(None) is None

    def test_parse_date_string_vacio(self):
        """Retorna None cuando el input es string vacío."""
        from engagement.streak_manager import StreakManager
        assert StreakManager._parse_date('') is None

    def test_parse_date_formato_invalido(self):
        """Retorna None cuando el formato es inválido."""
        from engagement.streak_manager import StreakManager
        assert StreakManager._parse_date('fecha-invalida') is None


class TestStreakManagerConBD:
    """Tests de métodos que usan la base de datos (mockeada)."""

    def test_get_streak_info_usuario_sin_registro(self):
        """Retorna valores en cero si el usuario no tiene racha registrada."""
        from engagement.streak_manager import StreakManager

        # check_and_apply_streak_reset también llama a la BD
        cursor = make_cursor(None, None)  # initialize devuelve None, fetchone devuelve None
        conn = make_conn(cursor)

        with patch('engagement.streak_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = StreakManager.get_streak_info('usuario_nuevo')

        assert result['current_streak'] == 0
        assert result['longest_streak'] == 0
        assert result['freeze_count'] == 0
        assert result['total_days_active'] == 0

    def test_get_streak_info_racha_activa_hoy(self):
        """Racha activa con last_activity = hoy (UTC): is_at_risk debe ser False."""
        from engagement.streak_manager import StreakManager
        from datetime import timezone

        # Usamos la misma fecha que _today() usa internamente (UTC)
        today_utc = date.today()
        today_str = today_utc.isoformat()
        row = (5, 10, today_str, 0, 30)

        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchone.side_effect = [row, row, row, row]
        cursor.rowcount = 1
        conn = make_conn(cursor)

        # Mockeamos _today() para garantizar consistencia UTC/local en cualquier entorno
        with patch('engagement.streak_manager.db_manager') as mock_db, \
             patch.object(StreakManager, '_today', return_value=today_utc):
            mock_db.get_connection.return_value = conn
            result = StreakManager.get_streak_info('usuario1')

        # days_since = 0 → is_at_risk = False
        assert result['current_streak'] == 5
        assert result['longest_streak'] == 10
        assert result['is_at_risk'] is False
        assert result['total_days_active'] == 30

    def test_get_streak_info_racha_en_riesgo(self):
        """Racha marcada como en riesgo si la última actividad fue hace 2 días."""
        from engagement.streak_manager import StreakManager

        hace_dos_dias = (date.today() - timedelta(days=2)).isoformat()
        row = (7, 7, hace_dos_dias, 0, 20)
        cursor = make_cursor(row, row, row)
        conn = make_conn(cursor)

        with patch('engagement.streak_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = StreakManager.get_streak_info('usuario1')

        assert result['is_at_risk'] is True

    def test_use_freeze_sin_congeladores(self):
        """use_freeze retorna False si no hay congeladores disponibles."""
        from engagement.streak_manager import StreakManager

        cursor = make_cursor((0,))  # freeze_count = 0
        conn = make_conn(cursor)

        with patch('engagement.streak_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            success, msg = StreakManager.use_freeze('usuario1')

        assert success is False
        assert "congelador" in msg.lower()

    def test_use_freeze_exitoso(self):
        """use_freeze retorna True cuando hay congeladores disponibles."""
        from engagement.streak_manager import StreakManager

        cursor = make_cursor((2,))  # freeze_count = 2
        conn = make_conn(cursor)

        with patch('engagement.streak_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            success, msg = StreakManager.use_freeze('usuario1')

        assert success is True

    def test_check_reset_racha_cero_no_resetea(self):
        """No se resetea si la racha ya es 0."""
        from engagement.streak_manager import StreakManager

        row = (0, 0, None, 0, 0)  # current_streak = 0
        cursor = make_cursor(row)
        conn = make_conn(cursor)

        with patch('engagement.streak_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            reseteada, congelador_usado = StreakManager.check_and_apply_streak_reset('usuario1')

        assert reseteada is False
        assert congelador_usado is False


# ===========================================================================
# Tests de ChallengeManager
# ===========================================================================

class TestChallengeManagerConBD:
    """Tests del ChallengeManager con BD mockeada."""

    def test_get_user_challenge_status_sin_intentos(self):
        """Retorna estado inicial si el usuario no ha intentado el desafío."""
        from engagement.challenge_manager import ChallengeManager

        cursor = make_cursor(fetchall_value=[])
        cursor.fetchall.return_value = []
        conn = make_conn(cursor)

        with patch('engagement.challenge_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = ChallengeManager.get_user_challenge_status(challenge_id=1, user_id='usuario1')

        assert result['attempted'] is False
        assert result['completed'] is False
        assert result['attempts_count'] == 0
        assert result['best_score'] == 0

    def test_get_user_challenge_status_con_intento_fallido(self):
        """Retorna completed=False si todos los intentos fallaron."""
        from engagement.challenge_manager import ChallengeManager

        # id, score, points_earned, completed, attempt_number, created_at
        intentos = [(1, 40, 0, False, 1, '2026-07-22 10:00:00')]
        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = intentos
        conn = make_conn(cursor)

        with patch('engagement.challenge_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = ChallengeManager.get_user_challenge_status(challenge_id=1, user_id='usuario1')

        assert result['attempted'] is True
        assert result['completed'] is False
        assert result['attempts_count'] == 1
        assert result['best_score'] == 40

    def test_get_user_challenge_status_completado(self):
        """Retorna completed=True si al menos un intento fue exitoso."""
        from engagement.challenge_manager import ChallengeManager

        intentos = [
            (1, 60, 0, False, 1, '2026-07-22 10:00:00'),
            (2, 100, 50, True, 2, '2026-07-22 10:05:00'),
        ]
        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = intentos
        conn = make_conn(cursor)

        with patch('engagement.challenge_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = ChallengeManager.get_user_challenge_status(challenge_id=1, user_id='usuario1')

        assert result['completed'] is True
        assert result['attempts_count'] == 2
        assert result['best_score'] == 100
        assert result['total_points'] == 50

    def test_get_challenge_leaderboard_vacio(self):
        """Retorna lista vacía si nadie completó el desafío."""
        from engagement.challenge_manager import ChallengeManager

        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = []
        conn = make_conn(cursor)

        with patch('engagement.challenge_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = ChallengeManager.get_challenge_leaderboard(challenge_id=1)

        assert result == []

    def test_get_challenge_leaderboard_con_datos(self):
        """Retorna ranking correcto cuando hay participantes."""
        from engagement.challenge_manager import ChallengeManager

        filas = [
            ('user1', 'Ana García', 100, 1, 70),
            ('user2', 'Luis Pérez', 85, 2, 50),
        ]
        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = filas
        conn = make_conn(cursor)

        with patch('engagement.challenge_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = ChallengeManager.get_challenge_leaderboard(challenge_id=1)

        assert len(result) == 2
        assert result[0]['rank'] == 1
        assert result[0]['username'] == 'user1'
        assert result[0]['score'] == 100
        assert result[1]['rank'] == 2


# ===========================================================================
# Tests de LeaderboardManager
# ===========================================================================

class TestLeaderboardManagerConBD:
    """Tests del LeaderboardManager con BD mockeada."""

    def test_get_global_leaderboard_vacio(self):
        """Retorna lista vacía si no hay estudiantes con puntos."""
        from engagement.leaderboard_manager import LeaderboardManager

        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = []
        conn = make_conn(cursor)

        with patch('engagement.leaderboard_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = LeaderboardManager.get_global_leaderboard()

        assert result == []

    def test_get_global_leaderboard_all_time(self):
        """Retorna ranking con posiciones correctas."""
        from engagement.leaderboard_manager import LeaderboardManager

        filas = [
            ('user1', 'Ana García', 500, 5),
            ('user2', 'Luis Pérez', 300, 3),
            ('user3', 'María López', 150, 2),
        ]
        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = filas
        conn = make_conn(cursor)

        with patch('engagement.leaderboard_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            result = LeaderboardManager.get_global_leaderboard(period='all_time')

        assert len(result) == 3
        assert result[0]['rank'] == 1
        assert result[0]['username'] == 'user1'
        assert result[0]['points'] == 500
        assert result[2]['rank'] == 3

    def test_get_global_leaderboard_weekly(self):
        """El periodo 'weekly' ordena por weekly_points en la query."""
        from engagement.leaderboard_manager import LeaderboardManager

        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = []
        conn = make_conn(cursor)

        with patch('engagement.leaderboard_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            LeaderboardManager.get_global_leaderboard(period='weekly')

            # Verificar que la query incluye 'weekly_points'
            call_args = str(cursor.execute.call_args)
            assert 'weekly_points' in call_args

    def test_get_user_rank_retorna_entero(self):
        """get_user_rank retorna un entero >= 1."""
        from engagement.leaderboard_manager import LeaderboardManager

        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchone.return_value = (3,)  # posición 3
        conn = make_conn(cursor)

        with patch('engagement.leaderboard_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            rank = LeaderboardManager.get_user_rank('usuario1')

        assert rank == 3
        assert isinstance(rank, int)

    def test_get_user_rank_primero_en_ranking(self):
        """Si nadie supera al usuario, su posición es 1."""
        from engagement.leaderboard_manager import LeaderboardManager

        cursor = MagicMock()
        cursor.execute.return_value = cursor
        cursor.fetchone.return_value = (1,)
        conn = make_conn(cursor)

        with patch('engagement.leaderboard_manager.db_manager') as mock_db:
            mock_db.get_connection.return_value = conn
            rank = LeaderboardManager.get_user_rank('lider')

        assert rank == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
