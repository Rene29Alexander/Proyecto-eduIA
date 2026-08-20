# -*- coding: utf-8 -*-
"""
Script de migración COMPLETO: SQLite → PostgreSQL (Supabase)

Mejoras sobre la versión anterior:
  - Crea el schema completo con init_db() antes de migrar
  - Respeta el orden correcto de foreign keys
  - Convierte tipos Python correctamente (bytes → memoryview para BYTEA)
  - Maneja columnas que existen en SQLite pero no en PostgreSQL
  - Inyecta valores por defecto para columnas NOT NULL que estén vacías
  - Muestra progreso detallado por tabla

Uso:
    1. Asegúrate de tener DATABASE_URL configurado en .streamlit/secrets.toml
    2. Ejecutar: python scripts/migrate_to_postgres.py
"""

import os
import sys
import sqlite3
import psycopg2
import psycopg2.extras
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SQLITE_PATH = ROOT / "learning_platform.db"

# Valores por defecto para columnas NOT NULL vacías al migrar
NOT_NULL_DEFAULTS = {
    # (tabla, columna): valor_default
    ('ai_courses',                          'title'):     'Curso IA',
    ('private_messages',                    'content'):   '',
    ('admin_messages',                      'content'):   '',
    ('admin_teacher_messages',              'student_id'):'',
    ('learning_progress',                   'entity_type'):'course',
    ('learning_progress',                   'entity_id'): 0,
    ('module_ai_chat_suggested_questions',  'question'):  '—',
    ('module_ai_chat_conversations',        'user_id'):   'unknown',
    ('module_ai_chat_conversations',        'role'):      'user',
    ('module_ai_group_chat',                'role'):      'user',
}

# Intentar obtener DATABASE_URL de secrets.toml o entorno
def get_database_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    # Intentar desde secrets.toml de Streamlit
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        try:
            import re
            content = secrets_path.read_text(encoding='utf-8')
            m = re.search(r'DATABASE_URL\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
    return ""


# Orden de migración respetando foreign keys
TABLE_ORDER = [
    # Sin dependencias
    "users",
    "settings",
    "system_settings",
    "badges",
    "reward_shop_items",
    "live_events",
    # Dependen de users
    "courses",
    "user_streaks",
    "user_points",
    "user_coins",
    "user_badges",
    "user_statistics",
    "user_active_items",
    "user_purchases",
    "point_transactions",
    "push_notifications",
    "notification_preferences",
    "activity_calendar",
    "student_achievements",
    "learning_resources",
    # Dependen de courses/users
    "modules",
    "enrollments",
    "tasks",
    "course_materials",
    "exams",
    "forum_posts",
    "activity_logs",
    "notifications",
    "ai_courses",
    "teams",
    # Dependen de modules/courses
    "module_ai_chat_content",
    "module_ai_chat_suggested_questions",
    "module_ai_chat_conversations",
    "module_ai_group_chat",
    # Dependen de teams
    "team_members",
    # Dependen de tasks/exams
    "submissions",
    "exam_questions",
    # Dependen de exams/users
    "exam_attempts",
    # Dependen de exam_attempts
    "exam_responses",
    # Dependen de enrollments/users
    "conversations",
    # Dependen de conversations
    "private_messages",
    "message_attachments",
    # Dependen de ai_courses
    "ai_course_topics",
    "ai_course_materials",
    "ai_topic_materials",
    "ai_course_chat",
    "ai_course_final_exams",
    "language_assessments",
    "ai_topic_exercises",
    "ai_exercise_attempts",
    "ai_topic_evaluations",
    # Engagement
    "daily_challenges",
    "daily_challenge_attempts",
    "daily_questions",
    "daily_question_answers",
    "code_duels",
    "event_participants",
    "leaderboard",
    "learning_progress",
    "personal_exercises",
    "personal_exercise_attempts",
    # Admin chat
    "admin_messages",
    "admin_message_files",
    "admin_direct_messages",
    "admin_direct_files",
    "admin_student_messages",
    "admin_student_files",
    "admin_teacher_messages",
    "admin_teacher_files",
    # Misc
    "admin_broadcast_messages",
    "progress_calculation_log",
]


def get_pg_columns(pg_conn, table):
    """Obtiene columnas que existen en PostgreSQL para una tabla."""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    return {r[0] for r in cur.fetchall()}


def get_sqlite_columns(sqlite_conn, table):
    """Obtiene columnas de una tabla SQLite."""
    rows = sqlite_conn.execute(f"PRAGMA table_info(\"{table}\")").fetchall()
    return [r[1] for r in rows]


def adapt_value(val):
    """Convierte valores Python para PostgreSQL."""
    if isinstance(val, bytes):
        # BYTEA en psycopg2 requiere memoryview o psycopg2.Binary
        return psycopg2.Binary(val)
    return val


def migrate_table(sqlite_conn, pg_conn, table, pg_columns):
    """Migra una tabla completa de SQLite a PostgreSQL."""
    sqlite_cols = get_sqlite_columns(sqlite_conn, table)
    if not sqlite_cols:
        return 0, 0

    # Columnas extras a inyectar (existen en PG pero no en SQLite)
    # (tabla): {columna_pg: valor_default}
    EXTRA_COLS = {
        'ai_courses': {'title': 'Curso IA'},
        # role no existe en SQLite para estas tablas — inyectar default
        'module_ai_chat_conversations': {'role': 'user'},
        'module_ai_group_chat':         {'role': 'user'},
        # learning_progress: entity_id y entity_type no existen en SQLite con esos nombres
        'learning_progress': {'entity_type': 'course', 'entity_id': 0},
    }

    # Columnas a renombrar: (tabla, col_sqlite) → col_pg
    RENAMES = {
        ('admin_teacher_messages',             'teacher_id'): 'student_id',
        ('module_ai_chat_suggested_questions', 'question_text'): 'question',
        ('module_ai_chat_conversations',       'student_id'): 'user_id',
    }

    # Solo migrar columnas que existen en ambos lados
    common_cols = []
    rename_map  = {}   # col_sqlite → col_pg
    for c in sqlite_cols:
        key = (table, c)
        if key in RENAMES:
            pg_col = RENAMES[key]
            if pg_col in pg_columns:
                common_cols.append(c)
                rename_map[c] = pg_col
        elif c in pg_columns:
            common_cols.append(c)

    skip_cols = [c for c in sqlite_cols if c not in common_cols]
    if skip_cols:
        print(f"    ⚠  columnas ignoradas (no en PG): {', '.join(skip_cols)}")

    if not common_cols and not EXTRA_COLS.get(table):
        print(f"    ⚠  sin columnas comunes, saltando")
        return 0, 0

    # Extras a inyectar
    extras = EXTRA_COLS.get(table, {})
    # Filtrar extras a solo los que existen en PG y NO están ya en common_cols
    extras = {k: v for k, v in extras.items() if k in pg_columns and k not in common_cols}

    # Obtener datos de SQLite
    col_sql = ", ".join(f'"{c}"' for c in common_cols)
    try:
        rows = sqlite_conn.execute(f'SELECT {col_sql} FROM "{table}"').fetchall()
    except Exception as e:
        print(f"    ❌ Error leyendo SQLite: {e}")
        return 0, 0

    if not rows:
        return 0, 0

    # Columnas finales para el INSERT (renombradas + extras)
    final_pg_cols = [rename_map.get(c, c) for c in common_cols] + list(extras.keys())
    placeholders  = ", ".join(["%s"] * len(final_pg_cols))
    col_list      = ", ".join(f'"{c}"' for c in final_pg_cols)
    insert_sql    = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

    pg_cur = pg_conn.cursor()
    ok = 0
    skipped = 0

    for row in rows:
        adapted = list(row)
        # Aplicar defaults NOT NULL para valores None
        for i, col in enumerate(common_cols):
            if adapted[i] is None:
                pg_col = rename_map.get(col, col)
                default = NOT_NULL_DEFAULTS.get((table, pg_col)) or NOT_NULL_DEFAULTS.get((table, col))
                if default is not None:
                    adapted[i] = default
            if isinstance(adapted[i], bytes):
                adapted[i] = psycopg2.Binary(adapted[i])
        # Agregar valores extras
        for _, val in extras.items():
            adapted.append(val)

        try:
            pg_cur.execute(insert_sql, adapted)
            ok += 1
        except Exception as e:
            skipped += 1
            if skipped <= 3:
                print(f"    ⚠  fila omitida: {str(e)[:120]}")
            pg_conn.rollback()
            pg_cur = pg_conn.cursor()

    try:
        pg_conn.commit()
    except Exception as e:
        print(f"    ❌ Error en commit: {e}")
        pg_conn.rollback()

    return ok, skipped


def reset_sequences(pg_conn):
    """
    Reinicia las secuencias de PostgreSQL (SERIAL) para que los nuevos
    INSERT generen IDs mayores que los ya migrados.
    """
    pg_cur = pg_conn.cursor()
    pg_cur.execute("""
        SELECT sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    """)
    sequences = [r[0] for r in pg_cur.fetchall()]

    for seq in sequences:
        try:
            # Obtener el nombre de tabla y columna a partir del nombre de secuencia
            pg_cur.execute(f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM \"{seq.replace('_id_seq','').replace('_seq','')}\"), 1))")
        except Exception:
            pass

    pg_conn.commit()
    print(f"  ✅ {len(sequences)} secuencias reiniciadas")


def main():
    DATABASE_URL = get_database_url()

    if not DATABASE_URL:
        print("❌ DATABASE_URL no configurada.")
        print()
        print("Opciones para configurarla:")
        print("  1. Agregar en .streamlit/secrets.toml:")
        print('     DATABASE_URL = "postgresql://postgres:PASSWORD@HOST:5432/postgres"')
        print()
        print("  2. Variable de entorno (PowerShell):")
        print('     $env:DATABASE_URL="postgresql://postgres:PASSWORD@HOST:5432/postgres"')
        print()
        print("  Obtén la URL en Supabase: Settings → Database → Connection string → URI")
        sys.exit(1)

    if not SQLITE_PATH.exists():
        print(f"❌ Base de datos SQLite no encontrada: {SQLITE_PATH}")
        sys.exit(1)

    print(f"{'='*60}")
    print("  MIGRACIÓN SQLite → PostgreSQL")
    print(f"{'='*60}")
    print(f"  Origen : {SQLITE_PATH} ({SQLITE_PATH.stat().st_size/1024:.0f} KB)")
    print(f"  Destino: {DATABASE_URL[:50]}...")
    print(f"{'='*60}\n")

    # ── Conectar a SQLite ──────────────────────────────────────
    print("📦 Conectando a SQLite...")
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row

    sqlite_tables = set(
        r[0] for r in sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    )
    print(f"   {len(sqlite_tables)} tablas encontradas en SQLite")

    # ── Conectar a PostgreSQL ──────────────────────────────────
    print("\n🐘 Conectando a PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_conn.autocommit = False
        print("   Conexión exitosa")
    except Exception as e:
        print(f"❌ No se pudo conectar: {e}")
        sys.exit(1)

    # ── Crear schema en PostgreSQL ─────────────────────────────
    print("\n🏗  Creando schema en PostgreSQL (init_db)...")
    os.environ["DATABASE_URL"] = DATABASE_URL
    try:
        # Reset el flag para forzar re-inicialización
        from database import db_manager
        db_manager._initialized = False
        db_manager._conn = None
        db_manager._instance = None

        # Reconectar con la nueva URL
        from database import DatabaseManager
        fresh = DatabaseManager()
        fresh.init_db()
        print("   Schema creado correctamente")
    except Exception as e:
        print(f"❌ Error creando schema: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

    # ── Construir orden de migración ───────────────────────────
    ordered = [t for t in TABLE_ORDER if t in sqlite_tables]
    extra   = [t for t in sqlite_tables if t not in TABLE_ORDER]
    if extra:
        print(f"\n⚠  Tablas no en el orden definido (se migrarán al final): {', '.join(extra)}")
    ordered += extra

    # ── Migrar tabla por tabla ─────────────────────────────────
    print(f"\n🔄 Migrando {len(ordered)} tablas...\n")
    total_ok = total_skip = 0
    empty_tables = []
    failed_tables = []

    for table in ordered:
        if table not in sqlite_tables:
            continue

        # Obtener columnas de PostgreSQL para esta tabla
        pg_cols = get_pg_columns(pg_conn, table)
        if not pg_cols:
            print(f"  ⚠  {table}: tabla no existe en PostgreSQL (se omite)")
            failed_tables.append(table)
            continue

        try:
            ok, skipped = migrate_table(sqlite_conn, pg_conn, table, pg_cols)
            total_ok   += ok
            total_skip += skipped

            if ok == 0 and skipped == 0:
                empty_tables.append(table)
                print(f"  ·  {table}: vacía")
            elif skipped > 0:
                print(f"  ⚠  {table}: {ok} migradas, {skipped} omitidas")
            else:
                print(f"  ✅ {table}: {ok} filas")
        except Exception as e:
            print(f"  ❌ {table}: {e}")
            failed_tables.append(table)
            try:
                pg_conn.rollback()
            except Exception:
                pass

    # ── Reiniciar secuencias ───────────────────────────────────
    print("\n🔢 Reiniciando secuencias de auto-incremento...")
    try:
        reset_sequences(pg_conn)
    except Exception as e:
        print(f"  ⚠  No se pudieron reiniciar secuencias: {e}")

    # ── Resumen ────────────────────────────────────────────────
    sqlite_conn.close()
    pg_conn.close()

    print(f"\n{'='*60}")
    print("  RESUMEN DE MIGRACIÓN")
    print(f"{'='*60}")
    print(f"  ✅ Filas migradas exitosamente: {total_ok}")
    print(f"  ⚠  Filas omitidas (conflictos): {total_skip}")
    print(f"  ·  Tablas vacías              : {len(empty_tables)}")
    if failed_tables:
        print(f"  ❌ Tablas con errores         : {', '.join(failed_tables)}")
    print(f"{'='*60}")
    print(f"\n✅ Migración completada — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if failed_tables:
        print(f"\n⚠  Revisar tablas con errores: {', '.join(failed_tables)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
