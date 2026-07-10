"""
Extensiones de base de datos para el sistema de engagement.
Incluye tablas para rachas, desafíos diarios, puntos, niveles, notificaciones, etc.
"""

import sqlite3
from database import db_manager

def create_engagement_tables():
    """Crea todas las tablas necesarias para el sistema de engagement"""
    conn = db_manager.get_connection()
    c = conn.cursor()
    
    # Tabla de rachas de usuarios
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_streaks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        current_streak INTEGER DEFAULT 0,
        longest_streak INTEGER DEFAULT 0,
        last_activity_date DATE,
        freeze_count INTEGER DEFAULT 0,
        total_days_active INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(user_id)
    )
    ''')
    
    # Tabla de desafíos diarios
    c.execute('''
    CREATE TABLE IF NOT EXISTS daily_challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_date DATE NOT NULL,
        language TEXT NOT NULL,
        difficulty TEXT NOT NULL CHECK(difficulty IN ('easy', 'medium', 'hard')),
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        exercise_code TEXT,
        solution_code TEXT,
        test_cases TEXT,
        points INTEGER DEFAULT 50,
        bonus_points INTEGER DEFAULT 20,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(challenge_date, language)
    )
    ''')

    
    # Tabla de intentos de desafíos diarios
    c.execute('''
    CREATE TABLE IF NOT EXISTS daily_challenge_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        submitted_code TEXT,
        score REAL DEFAULT 0,
        points_earned INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        feedback TEXT,
        attempt_number INTEGER DEFAULT 1,
        time_spent_seconds INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (challenge_id) REFERENCES daily_challenges(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
    )
    ''')
    
    # Tabla de puntos y experiencia
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        total_points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        experience_points INTEGER DEFAULT 0,
        points_to_next_level INTEGER DEFAULT 100,
        rank_position INTEGER,
        weekly_points INTEGER DEFAULT 0,
        monthly_points INTEGER DEFAULT 0,
        last_level_up TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(user_id)
    )
    ''')

    
    # Tabla de transacciones de puntos
    c.execute('''
    CREATE TABLE IF NOT EXISTS point_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        points INTEGER NOT NULL,
        transaction_type TEXT NOT NULL CHECK(transaction_type IN ('earn', 'spend', 'bonus', 'penalty')),
        source TEXT NOT NULL,
        description TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
    )
    ''')
    
    # Tabla de badges y logros
    c.execute('''
    CREATE TABLE IF NOT EXISTS badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        badge_key TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT,
        category TEXT CHECK(category IN ('streak', 'points', 'completion', 'social', 'special')),
        requirement_type TEXT NOT NULL,
        requirement_value INTEGER,
        points_reward INTEGER DEFAULT 0,
        rarity TEXT DEFAULT 'common' CHECK(rarity IN ('common', 'rare', 'epic', 'legendary')),
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabla de badges ganados por usuarios
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        badge_id INTEGER NOT NULL,
        earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        progress INTEGER DEFAULT 0,
        is_displayed INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE,
        UNIQUE(user_id, badge_id)
    )
    ''')

    
    # Tabla de monedas virtuales
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_coins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        total_coins INTEGER DEFAULT 0,
        coins_earned INTEGER DEFAULT 0,
        coins_spent INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(user_id)
    )
    ''')
    
    # Tabla de tienda de recompensas
    c.execute('''
    CREATE TABLE IF NOT EXISTS reward_shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_key TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        item_type TEXT NOT NULL CHECK(item_type IN ('content', 'certificate', 'discount', 'cosmetic', 'feature')),
        cost_coins INTEGER NOT NULL,
        cost_points INTEGER DEFAULT 0,
        stock INTEGER DEFAULT -1,
        is_available INTEGER DEFAULT 1,
        image_url TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabla de compras de usuarios
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        coins_spent INTEGER NOT NULL,
        points_spent INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed' CHECK(status IN ('completed', 'pending', 'cancelled')),
        purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        redeemed_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES reward_shop_items(id) ON DELETE CASCADE
    )
    ''')

    
    # Tabla de ranking/leaderboard
    c.execute('''
    CREATE TABLE IF NOT EXISTS leaderboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        period TEXT NOT NULL CHECK(period IN ('daily', 'weekly', 'monthly', 'all_time')),
        points INTEGER DEFAULT 0,
        rank_position INTEGER,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(user_id, period, period_start)
    )
    ''')
    
    # Tabla de equipos/clanes
    c.execute('''
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_name TEXT UNIQUE NOT NULL,
        team_code TEXT UNIQUE NOT NULL,
        description TEXT,
        leader_id TEXT NOT NULL,
        max_members INTEGER DEFAULT 10,
        total_points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        avatar_url TEXT,
        is_public INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (leader_id) REFERENCES users(username) ON DELETE CASCADE
    )
    ''')
    
    # Tabla de miembros de equipos
    c.execute('''
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT DEFAULT 'member' CHECK(role IN ('leader', 'co-leader', 'member')),
        points_contributed INTEGER DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(team_id, user_id)
    )
    ''')

    
    # Tabla de duelos 1v1
    c.execute('''
    CREATE TABLE IF NOT EXISTS code_duels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenger_id TEXT NOT NULL,
        opponent_id TEXT NOT NULL,
        challenge_id INTEGER,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'completed', 'cancelled')),
        winner_id TEXT,
        challenger_score REAL DEFAULT 0,
        opponent_score REAL DEFAULT 0,
        time_limit_minutes INTEGER DEFAULT 30,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (challenger_id) REFERENCES users(username) ON DELETE CASCADE,
        FOREIGN KEY (opponent_id) REFERENCES users(username) ON DELETE CASCADE,
        FOREIGN KEY (challenge_id) REFERENCES daily_challenges(id) ON DELETE SET NULL,
        FOREIGN KEY (winner_id) REFERENCES users(username) ON DELETE SET NULL
    )
    ''')
    
    # Tabla de calendario de actividad
    c.execute('''
    CREATE TABLE IF NOT EXISTS activity_calendar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        activity_date DATE NOT NULL,
        exercises_completed INTEGER DEFAULT 0,
        time_spent_minutes INTEGER DEFAULT 0,
        points_earned INTEGER DEFAULT 0,
        challenges_completed INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(user_id, activity_date)
    )
    ''')
    
    # Tabla de estadísticas de usuario
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        total_exercises INTEGER DEFAULT 0,
        exercises_completed INTEGER DEFAULT 0,
        total_time_minutes INTEGER DEFAULT 0,
        average_score REAL DEFAULT 0,
        best_language TEXT,
        courses_completed INTEGER DEFAULT 0,
        duels_won INTEGER DEFAULT 0,
        duels_lost INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(user_id)
    )
    ''')

    
    # Tabla de notificaciones push
    c.execute('''
    CREATE TABLE IF NOT EXISTS push_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        notification_type TEXT NOT NULL CHECK(notification_type IN ('streak', 'challenge', 'ranking', 'achievement', 'duel', 'team', 'reminder')),
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        action_url TEXT,
        is_sent INTEGER DEFAULT 0,
        is_read INTEGER DEFAULT 0,
        scheduled_for TIMESTAMP,
        sent_at TIMESTAMP,
        read_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
    )
    ''')
    
    # Tabla de preferencias de notificaciones
    c.execute('''
    CREATE TABLE IF NOT EXISTS notification_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        email_enabled INTEGER DEFAULT 1,
        push_enabled INTEGER DEFAULT 1,
        streak_reminders INTEGER DEFAULT 1,
        challenge_reminders INTEGER DEFAULT 1,
        ranking_updates INTEGER DEFAULT 1,
        achievement_alerts INTEGER DEFAULT 1,
        duel_invites INTEGER DEFAULT 1,
        team_updates INTEGER DEFAULT 1,
        preferred_time TEXT DEFAULT '20:00',
        timezone TEXT DEFAULT 'UTC',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(user_id)
    )
    ''')
    
    # Tabla de eventos en vivo
    c.execute('''
    CREATE TABLE IF NOT EXISTS live_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL CHECK(event_type IN ('webinar', 'qa', 'workshop', 'competition', 'special')),
        title TEXT NOT NULL,
        description TEXT,
        instructor_id TEXT,
        max_participants INTEGER DEFAULT 100,
        current_participants INTEGER DEFAULT 0,
        event_url TEXT,
        scheduled_start TIMESTAMP NOT NULL,
        scheduled_end TIMESTAMP NOT NULL,
        status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'live', 'completed', 'cancelled')),
        points_reward INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (instructor_id) REFERENCES users(username) ON DELETE SET NULL
    )
    ''')

    
    # Tabla de participantes en eventos
    c.execute('''
    CREATE TABLE IF NOT EXISTS event_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        attended INTEGER DEFAULT 0,
        attendance_time TIMESTAMP,
        points_earned INTEGER DEFAULT 0,
        FOREIGN KEY (event_id) REFERENCES live_events(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
        UNIQUE(event_id, user_id)
    )
    ''')
    
    # Crear índices para optimizar queries
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_user_streaks_user ON user_streaks(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_daily_challenges_date ON daily_challenges(challenge_date)",
        "CREATE INDEX IF NOT EXISTS idx_daily_challenge_attempts_user ON daily_challenge_attempts(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_points_level ON user_points(level DESC)",
        "CREATE INDEX IF NOT EXISTS idx_user_points_total ON user_points(total_points DESC)",
        "CREATE INDEX IF NOT EXISTS idx_point_transactions_user ON point_transactions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_leaderboard_period_rank ON leaderboard(period, rank_position)",
        "CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id)",
        "CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_code_duels_status ON code_duels(status)",
        "CREATE INDEX IF NOT EXISTS idx_activity_calendar_user_date ON activity_calendar(user_id, activity_date)",
        "CREATE INDEX IF NOT EXISTS idx_push_notifications_user ON push_notifications(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_live_events_status ON live_events(status, scheduled_start)",
    ]
    
    for index_sql in indexes:
        try:
            c.execute(index_sql)
        except Exception as e:
            print(f"Error creando índice: {e}")
    
    conn.commit()
    print("✅ Tablas de engagement creadas exitosamente")

def insert_default_badges():
    """Inserta badges por defecto en el sistema"""
    conn = db_manager.get_connection()
    c = conn.cursor()
    
    default_badges = [
        # Badges de racha
        ('streak_7', '🔥 Semana Completa', 'Mantén una racha de 7 días', '🔥', 'streak', 'streak_days', 7, 100, 'common'),
        ('streak_30', '🔥 Mes Imparable', 'Mantén una racha de 30 días', '🔥', 'streak', 'streak_days', 30, 500, 'rare'),
        ('streak_100', '🔥 Centenario', 'Mantén una racha de 100 días', '🔥', 'streak', 'streak_days', 100, 2000, 'epic'),
        ('streak_365', '🔥 Año Legendario', 'Mantén una racha de 365 días', '🔥', 'streak', 'streak_days', 365, 10000, 'legendary'),
        
        # Badges de puntos
        ('points_1000', '⭐ Novato', 'Alcanza 1,000 puntos', '⭐', 'points', 'total_points', 1000, 50, 'common'),
        ('points_5000', '⭐ Aprendiz', 'Alcanza 5,000 puntos', '⭐', 'points', 'total_points', 5000, 200, 'common'),
        ('points_10000', '⭐ Experto', 'Alcanza 10,000 puntos', '⭐', 'points', 'total_points', 10000, 500, 'rare'),
        ('points_50000', '⭐ Maestro', 'Alcanza 50,000 puntos', '⭐', 'points', 'total_points', 50000, 2000, 'epic'),
        ('points_100000', '⭐ Leyenda', 'Alcanza 100,000 puntos', '⭐', 'points', 'total_points', 100000, 5000, 'legendary'),
        
        # Badges de completación
        ('exercises_10', '📝 Primer Paso', 'Completa 10 ejercicios', '📝', 'completion', 'exercises_completed', 10, 50, 'common'),
        ('exercises_50', '📝 Dedicado', 'Completa 50 ejercicios', '📝', 'completion', 'exercises_completed', 50, 200, 'common'),
        ('exercises_100', '📝 Incansable', 'Completa 100 ejercicios', '📝', 'completion', 'exercises_completed', 100, 500, 'rare'),
        ('exercises_500', '📝 Máquina', 'Completa 500 ejercicios', '📝', 'completion', 'exercises_completed', 500, 2000, 'epic'),
        
        # Badges sociales
        ('team_join', '👥 Jugador de Equipo', 'Únete a un equipo', '👥', 'social', 'team_joined', 1, 50, 'common'),
        ('duel_win_1', '⚔️ Primera Victoria', 'Gana tu primer duelo', '⚔️', 'social', 'duels_won', 1, 100, 'common'),
        ('duel_win_10', '⚔️ Guerrero', 'Gana 10 duelos', '⚔️', 'social', 'duels_won', 10, 500, 'rare'),
        ('duel_win_50', '⚔️ Campeón', 'Gana 50 duelos', '⚔️', 'social', 'duels_won', 50, 2000, 'epic'),
        
        # Badges especiales
        ('early_bird', '🌅 Madrugador', 'Completa un desafío antes de las 8am', '🌅', 'special', 'special', 1, 100, 'rare'),
        ('night_owl', '🦉 Búho Nocturno', 'Completa un desafío después de las 11pm', '🦉', 'special', 'special', 1, 100, 'rare'),
        ('perfect_week', '💯 Semana Perfecta', 'Completa todos los desafíos diarios de una semana', '💯', 'special', 'special', 1, 500, 'epic'),
    ]
    
    for badge_data in default_badges:
        try:
            c.execute('''
                INSERT OR IGNORE INTO badges 
                (badge_key, name, description, icon, category, requirement_type, requirement_value, points_reward, rarity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', badge_data)
        except Exception as e:
            print(f"Error insertando badge {badge_data[0]}: {e}")
    
    conn.commit()
    print("✅ Badges por defecto insertados")

def insert_default_shop_items():
    """Inserta items por defecto en la tienda"""
    conn = db_manager.get_connection()
    c = conn.cursor()
    
    default_items = [
        ('content_premium_1', '📚 Curso Premium: Python Avanzado', 'Acceso a contenido premium de Python', 'content', 500, 0, -1, 1, None, None),
        ('content_premium_2', '📚 Curso Premium: JavaScript Avanzado', 'Acceso a contenido premium de JavaScript', 'content', 500, 0, -1, 1, None, None),
        ('certificate_custom', '🎓 Certificado Personalizado', 'Certificado con diseño personalizado', 'certificate', 1000, 0, -1, 1, None, None),
        ('discount_10', '💰 Descuento 10%', 'Descuento del 10% en tu próximo curso', 'discount', 200, 0, -1, 1, None, '{"discount_percentage": 10}'),
        ('discount_25', '💰 Descuento 25%', 'Descuento del 25% en tu próximo curso', 'discount', 500, 0, -1, 1, None, '{"discount_percentage": 25}'),
        ('cosmetic_avatar_1', '🎨 Avatar Especial: Ninja', 'Avatar exclusivo de ninja', 'cosmetic', 300, 0, -1, 1, None, '{"avatar_type": "ninja"}'),
        ('cosmetic_avatar_2', '🎨 Avatar Especial: Robot', 'Avatar exclusivo de robot', 'cosmetic', 300, 0, -1, 1, None, '{"avatar_type": "robot"}'),
        ('feature_freeze', '❄️ Congelador de Racha', 'Protege tu racha por 1 día', 'feature', 100, 0, -1, 1, None, '{"freeze_days": 1}'),
    ]
    
    for item_data in default_items:
        try:
            c.execute('''
                INSERT OR IGNORE INTO reward_shop_items 
                (item_key, name, description, item_type, cost_coins, cost_points, stock, is_available, image_url, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', item_data)
        except Exception as e:
            print(f"Error insertando item {item_data[0]}: {e}")
    
    conn.commit()
    print("✅ Items de tienda por defecto insertados")

if __name__ == "__main__":
    create_engagement_tables()
    insert_default_badges()
    insert_default_shop_items()
