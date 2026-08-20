"""
Extensiones de base de datos para el sistema de engagement.
Las tablas se crean en database.py (init_db) para soporte dual SQLite/PostgreSQL.
Este módulo mantiene compatibilidad con código que llame create_engagement_tables()
e incluye la semilla de badges e items de tienda.
"""

from database import db_manager, USE_POSTGRES


def create_engagement_tables():
    """
    Las tablas de engagement se crean en database.py init_db.
    Esta función solo inserta los datos semilla si no existen.
    """
    insert_default_badges()
    insert_default_shop_items()
    print("✅ Datos de engagement verificados")


def insert_default_badges():
    """Inserta badges por defecto en el sistema"""
    conn = db_manager.get_connection()
    c = conn.cursor()

    default_badges = [
        ('streak_7',    '🔥 Semana Completa',   'Mantén una racha de 7 días',    '🔥', 'streak',     'streak_days',         7,      100,   'common'),
        ('streak_30',   '🔥 Mes Imparable',      'Mantén una racha de 30 días',   '🔥', 'streak',     'streak_days',         30,     500,   'rare'),
        ('streak_100',  '🔥 Centenario',          'Mantén una racha de 100 días',  '🔥', 'streak',     'streak_days',         100,    2000,  'epic'),
        ('streak_365',  '🔥 Año Legendario',      'Mantén una racha de 365 días',  '🔥', 'streak',     'streak_days',         365,    10000, 'legendary'),
        ('points_1000', '⭐ Novato',              'Alcanza 1,000 puntos',          '⭐', 'points',     'total_points',        1000,   50,    'common'),
        ('points_5000', '⭐ Aprendiz',            'Alcanza 5,000 puntos',          '⭐', 'points',     'total_points',        5000,   200,   'common'),
        ('points_10000','⭐ Experto',             'Alcanza 10,000 puntos',         '⭐', 'points',     'total_points',        10000,  500,   'rare'),
        ('points_50000','⭐ Maestro',             'Alcanza 50,000 puntos',         '⭐', 'points',     'total_points',        50000,  2000,  'epic'),
        ('points_100000','⭐ Leyenda',            'Alcanza 100,000 puntos',        '⭐', 'points',     'total_points',        100000, 5000,  'legendary'),
        ('exercises_10','📝 Primer Paso',         'Completa 10 ejercicios',        '📝', 'completion', 'exercises_completed', 10,     50,    'common'),
        ('exercises_50','📝 Dedicado',            'Completa 50 ejercicios',        '📝', 'completion', 'exercises_completed', 50,     200,   'common'),
        ('exercises_100','📝 Incansable',         'Completa 100 ejercicios',       '📝', 'completion', 'exercises_completed', 100,    500,   'rare'),
        ('exercises_500','📝 Máquina',            'Completa 500 ejercicios',       '📝', 'completion', 'exercises_completed', 500,    2000,  'epic'),
        ('team_join',   '👥 Jugador de Equipo',   'Únete a un equipo',             '👥', 'social',     'team_joined',         1,      50,    'common'),
        ('duel_win_1',  '⚔️ Primera Victoria',   'Gana tu primer duelo',          '⚔️', 'social',     'duels_won',           1,      100,   'common'),
        ('duel_win_10', '⚔️ Guerrero',            'Gana 10 duelos',                '⚔️', 'social',     'duels_won',           10,     500,   'rare'),
        ('duel_win_50', '⚔️ Campeón',             'Gana 50 duelos',                '⚔️', 'social',     'duels_won',           50,     2000,  'epic'),
        ('early_bird',  '🌅 Madrugador',          'Completa un desafío antes de las 8am', '🌅', 'special', 'special',         1,      100,   'rare'),
        ('night_owl',   '🦉 Búho Nocturno',       'Completa un desafío después de las 11pm', '🦉', 'special', 'special',      1,      100,   'rare'),
        ('perfect_week','💯 Semana Perfecta',     'Completa todos los desafíos de una semana', '💯', 'special', 'special',    1,      500,   'epic'),
    ]

    if USE_POSTGRES:
        sql = """INSERT INTO badges
                 (badge_key, name, description, icon, category, requirement_type,
                  requirement_value, points_reward, rarity)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                 ON CONFLICT (badge_key) DO NOTHING"""
    else:
        sql = """INSERT OR IGNORE INTO badges
                 (badge_key, name, description, icon, category, requirement_type,
                  requirement_value, points_reward, rarity)
                 VALUES (?,?,?,?,?,?,?,?,?)"""

    for badge_data in default_badges:
        try:
            c.execute(sql, badge_data)
        except Exception as e:
            print(f"Error insertando badge {badge_data[0]}: {e}")
    try:
        conn.commit()
    except Exception:
        pass
    print("✅ Badges por defecto verificados")


def insert_default_shop_items():
    """Inserta items por defecto en la tienda"""
    conn = db_manager.get_connection()
    c = conn.cursor()

    default_items = [
        ('content_premium_1',  '📚 Curso Premium: Python Avanzado',      'Acceso a contenido premium de Python',       'content',     500,  0, -1, 1, None, None),
        ('content_premium_2',  '📚 Curso Premium: JavaScript Avanzado',   'Acceso a contenido premium de JavaScript',   'content',     500,  0, -1, 1, None, None),
        ('certificate_custom', '🎓 Certificado Personalizado',             'Certificado con diseño personalizado',       'certificate', 1000, 0, -1, 1, None, None),
        ('discount_10',        '💰 Descuento 10%',                         'Descuento del 10% en tu próximo curso',      'discount',    200,  0, -1, 1, None, '{"discount_percentage": 10}'),
        ('discount_25',        '💰 Descuento 25%',                         'Descuento del 25% en tu próximo curso',      'discount',    500,  0, -1, 1, None, '{"discount_percentage": 25}'),
        ('cosmetic_avatar_1',  '🎨 Avatar Especial: Ninja',                'Avatar exclusivo de ninja',                  'cosmetic',    300,  0, -1, 1, None, '{"avatar_type": "ninja"}'),
        ('cosmetic_avatar_2',  '🎨 Avatar Especial: Robot',                'Avatar exclusivo de robot',                  'cosmetic',    300,  0, -1, 1, None, '{"avatar_type": "robot"}'),
        ('feature_freeze',     '❄️ Congelador de Racha',                  'Protege tu racha por 1 día',                 'feature',     100,  0, -1, 1, None, '{"freeze_days": 1}'),
    ]

    if USE_POSTGRES:
        sql = """INSERT INTO reward_shop_items
                 (item_key, name, description, item_type, cost_coins, cost_points,
                  stock, is_available, image_url, metadata)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                 ON CONFLICT (item_key) DO NOTHING"""
    else:
        sql = """INSERT OR IGNORE INTO reward_shop_items
                 (item_key, name, description, item_type, cost_coins, cost_points,
                  stock, is_available, image_url, metadata)
                 VALUES (?,?,?,?,?,?,?,?,?,?)"""

    for item_data in default_items:
        try:
            c.execute(sql, item_data)
        except Exception as e:
            print(f"Error insertando item {item_data[0]}: {e}")
    try:
        conn.commit()
    except Exception:
        pass
    print("✅ Items de tienda por defecto verificados")


if __name__ == "__main__":
    create_engagement_tables()
