# -*- coding: utf-8 -*-
"""
Gestor de base de datos con soporte dual SQLite / PostgreSQL.

- Si DATABASE_URL está definida → usa PostgreSQL (producción / Supabase)
- Si no → usa SQLite (desarrollo local)

No requiere cambios en ningún otro archivo del proyecto.
"""

import os
import random
import string
import bcrypt
import json
from datetime import datetime, timedelta
from pathlib import Path

# Import opcional de streamlit (no disponible en scripts/tests)
try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

# ── Detección de motor ────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES  = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    print(f"[DB] Usando PostgreSQL: {DATABASE_URL[:40]}...")
else:
    import sqlite3
    print("[DB] Usando SQLite local")


def parse_dt(value, fmt='%Y-%m-%d %H:%M:%S') -> datetime | None:
    """
    Convierte un valor de timestamp a datetime.datetime de forma segura.

    - Si ya es datetime (PostgreSQL lo devuelve así) → lo retorna directamente
    - Si es string (SQLite) → lo parsea con el formato dado
    - Si es None o vacío → retorna None

    Uso:
        dt = parse_dt(row['created_at'])
        label = dt.strftime('%d/%m/%Y %H:%M') if dt else '—'
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Intentar formatos comunes
        for f in (fmt, '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(value, f)
            except ValueError:
                continue
    return None


def fmt_date(value, fmt='%Y-%m-%d') -> str:
    """
    Formatea un campo de fecha/timestamp de BD a string de forma segura.
    Compatible con objetos datetime (PostgreSQL) y strings (SQLite).

    Uso:
        label = fmt_date(row['created_at'])           # '2026-08-09'
        label = fmt_date(row['sent_at'], '%d/%m/%Y')  # '09/08/2026'
    """
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime(fmt)
    s = str(value).strip()
    # Para slices [:10] — devolver solo los primeros 10 chars si es YYYY-MM-DD...
    if fmt == '%Y-%m-%d' and len(s) >= 10:
        return s[:10]
    dt = parse_dt(s)
    return dt.strftime(fmt) if dt else s


def bytes_to_b64(value) -> str | None:
    """
    Convierte un campo binario de BD a base64 string de forma segura.
    Maneja bytes (SQLite) y memoryview (PostgreSQL BYTEA).

    Uso:
        b64 = bytes_to_b64(row['avatar'])
        if b64:
            src = f"data:image/png;base64,{b64}"
    """
    if value is None:
        return None
    import base64
    try:
        if isinstance(value, memoryview):
            return base64.b64encode(bytes(value)).decode('utf-8')
        if isinstance(value, (bytes, bytearray)):
            return base64.b64encode(value).decode('utf-8')
        # psycopg2 puede devolver un objeto Binary wrapper
        raw = bytes(value)
        return base64.b64encode(raw).decode('utf-8')
    except Exception:
        return None


def to_bytes(value) -> bytes | None:
    """
    Convierte cualquier valor binario de BD a bytes puros.
    Necesario para st.download_button y operaciones que requieren bytes reales.
    Maneja bytes (SQLite) y memoryview (PostgreSQL BYTEA).

    Uso:
        data = to_bytes(row['file_blob'])
        if data:
            st.download_button("Descargar", data, file_name)
    """
    if value is None:
        return None
    try:
        if isinstance(value, bytes):
            return value
        if isinstance(value, (memoryview, bytearray)):
            return bytes(value)
        return bytes(value)
    except Exception:
        return None


def to_date(value):
    """
    Convierte un campo de fecha de BD a datetime.date de forma segura.
    - datetime.datetime → .date()
    - datetime.date → devuelve directamente
    - string → parsea y extrae .date()
    - None → None

    Uso:
        d = to_date(row['due_date'])
        if d and datetime.now().date() > d:
            ...
    """
    from datetime import date as _date, datetime as _datetime
    if value is None:
        return None
    if isinstance(value, _datetime):
        return value.date()
    if isinstance(value, _date):
        return value
    if isinstance(value, str):
        dt = parse_dt(value.strip()[:10], '%Y-%m-%d')
        return dt.date() if dt else None
    return None


def _fix_sql_for_pg(sql: str) -> str:
    """
    Convierte SQL escrito para SQLite a SQL compatible con PostgreSQL:
    - ? → %s
    - datetime('now', '-N days') → (NOW() - INTERVAL 'N days')
    - date('now', ...) → CURRENT_DATE ± INTERVAL
    - strftime('%Y-%m-%d', col) → TO_CHAR(col, 'YYYY-MM-DD')
    Solo se usa cuando USE_POSTGRES es True.
    """
    import re

    # 1. Marcadores de posición
    # Escapar % literales (usados en LIKE '%texto%') → %% para psycopg2
    # antes de convertir ? → %s, para que no interfieran
    sql = sql.replace('%', '%%')   # escapar todos los % existentes
    sql = sql.replace("?", "%s")   # convertir ? a placeholder psycopg2

    # 2. datetime('now', '-N unit')
    def replace_datetime(m):
        modifier = m.group(1).strip().strip("'\"")
        sm = re.match(r"([+-]?\d+)\s+(\w+)", modifier)
        if sm:
            num, unit = sm.group(1), sm.group(2)
            if num.startswith('-'):
                return f"(NOW() - INTERVAL '{num[1:]} {unit}')"
            return f"(NOW() + INTERVAL '{num} {unit}')"
        return "NOW()"

    sql = re.sub(r"datetime\(\s*'now'\s*,\s*([^)]+)\)", replace_datetime, sql, flags=re.IGNORECASE)
    sql = re.sub(r"datetime\(\s*'now'\s*\)", "NOW()", sql, flags=re.IGNORECASE)

    # 3. date('now', '-N unit')
    def replace_date(m):
        modifier = m.group(1).strip().strip("'\"")
        sm = re.match(r"([+-]?\d+)\s+(\w+)", modifier)
        if sm:
            num, unit = sm.group(1), sm.group(2)
            if num.startswith('-'):
                return f"(CURRENT_DATE - INTERVAL '{num[1:]} {unit}')"
            return f"(CURRENT_DATE + INTERVAL '{num} {unit}')"
        return "CURRENT_DATE"

    sql = re.sub(r"date\(\s*'now'\s*,\s*([^)]+)\)", replace_date, sql, flags=re.IGNORECASE)
    sql = re.sub(r"date\(\s*'now'\s*\)", "CURRENT_DATE", sql, flags=re.IGNORECASE)

    # 4a-4e. strftime('FMT', col_or_now) → TO_CHAR(col_or_NOW(), 'PG_FMT')
    STRFTIME_MAP = {
        '%Y-%m-%d': 'YYYY-MM-DD',
        '%Y-%m':    'YYYY-MM',
        '%Y':       'YYYY',
        '%m':       'MM',
        '%d':       'DD',
        '%H:%M:%S': 'HH24:MI:SS',
        '%H:%M':    'HH24:MI',
    }

    def _strftime_to_tochar(m):
        fmt_sqlite = m.group(1).strip().strip("'\"")
        col        = m.group(2).strip()
        fmt_pg     = STRFTIME_MAP.get(fmt_sqlite, 'YYYY-MM-DD')
        # 'now' → NOW(), otros strings que parezcan literales → CURRENT_DATE
        if re.match(r"^['\"]?now['\"]?$", col, re.IGNORECASE):
            col = 'NOW()'
        elif re.match(r"^'[^']*'$", col) or re.match(r'^"[^"]*"$', col):
            # Otro string literal desconocido → usar NOW() como fallback
            col = 'NOW()'
        return f"TO_CHAR({col}, '{fmt_pg}')"

    sql = re.sub(
        r"strftime\(\s*'([^']+)'\s*,\s*([^)]+)\)",
        _strftime_to_tochar,
        sql, flags=re.IGNORECASE
    )

    # 5. INSERT OR IGNORE INTO → INSERT INTO ... ON CONFLICT DO NOTHING
    if re.search(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', sql, flags=re.IGNORECASE):
        sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', sql, flags=re.IGNORECASE)
        if 'ON CONFLICT' not in sql.upper():
            sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'

    # 6. INSERT OR REPLACE INTO → upsert
    # system_settings usa (key) como PK → ON CONFLICT (key) DO UPDATE
    if re.search(r'\bINSERT\s+OR\s+REPLACE\s+INTO\s+system_settings\b', sql, flags=re.IGNORECASE):
        sql = re.sub(r'\bINSERT\s+OR\s+REPLACE\s+INTO\s+system_settings\b',
                     'INSERT INTO system_settings', sql, flags=re.IGNORECASE)
        if 'ON CONFLICT' not in sql.upper():
            sql = (sql.rstrip().rstrip(';') +
                   ' ON CONFLICT (key) DO UPDATE SET'
                   ' value=EXCLUDED.value,'
                   ' updated_at=COALESCE(EXCLUDED.updated_at, CURRENT_TIMESTAMP)')
    else:
        # Resto de OR REPLACE → ignorar conflicto
        if re.search(r'\bINSERT\s+OR\s+REPLACE\s+INTO\b', sql, flags=re.IGNORECASE):
            sql = re.sub(r'\bINSERT\s+OR\s+REPLACE\s+INTO\b', 'INSERT INTO', sql, flags=re.IGNORECASE)
            if 'ON CONFLICT' not in sql.upper():
                sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'

    # 7. Inyectar columnas NOT NULL sin DEFAULT en tablas de chat de módulo
    # Estas columnas existen en PG con NOT NULL sin DEFAULT y el código antiguo no las incluye.
    # Patrón: INSERT INTO tabla (cols) VALUES (...) → agregar role y content si faltan
    _CHAT_TABLES_NOT_NULL = {
        'module_ai_group_chat': {'role': "'user'", 'content': "''"},
    }
    for tbl, defaults in _CHAT_TABLES_NOT_NULL.items():
        pat = re.compile(
            r'(INSERT\s+INTO\s+"?' + re.escape(tbl) + r'"?\s*\()([^)]+)(\)\s*VALUES\s*\()([^)]+)(\))',
            re.IGNORECASE | re.DOTALL
        )
        def _inject_defaults(m, _tbl=tbl, _defs=defaults):
            cols_str  = m.group(2)
            vals_str  = m.group(4)
            cols = [c.strip().strip('"') for c in cols_str.split(',')]
            vals = [v.strip() for v in vals_str.split(',')]
            for col, default in _defs.items():
                if col not in cols:
                    cols.append(f'"{col}"')
                    vals.append(default)
            return (m.group(1) +
                    ', '.join(cols) + m.group(3) +
                    ', '.join(vals) + m.group(5))
        sql = pat.sub(_inject_defaults, sql)

    return sql

# ── Adaptador de conexión ─────────────────────────────────────────────────────

class _PgConnection:
    """
    Wrapper que hace que una conexión psycopg2 se comporte como sqlite3.Connection.
    - Convierte marcadores ? → %s en todas las queries
    - Emula row_factory con RealDictCursor
    - Expone .execute(), .cursor(), .commit(), .rollback(), .close()
    """

    def __init__(self, dsn: str):
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = False

    # ── Conversión de marcadores ──────────────────────────────────────────────
    @staticmethod
    def _fix(sql: str) -> str:
        """Delega a la función global de conversión SQL."""
        return _fix_sql_for_pg(sql)

    # ── Cursor con dict-rows ──────────────────────────────────────────────────
    def cursor(self):
        return _PgCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    # ── Métodos de conveniencia ───────────────────────────────────────────────
    def execute(self, sql: str, params=None):
        # Recuperación automática de transacciones abortadas (InFailedSqlTransaction)
        try:
            import psycopg2.extensions as _ext
            if self._conn.get_transaction_status() == _ext.TRANSACTION_STATUS_INERROR:
                self._conn.rollback()
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
        cur = self.cursor()
        try:
            cur.execute(sql, params)
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def executemany(self, sql: str, seq_params):
        cur = self.cursor()
        cur.executemany(sql, seq_params)
        return cur

    def close(self):
        self._conn.close()

class _Row(dict):
    """
    Fila de resultado que se comporta como dict Y como tupla indexada por posición.
    Esto permite tanto row['col'] como row[0], igual que sqlite3.Row.
    Además convierte automáticamente memoryview → bytes para compatibilidad
    con st.download_button y base64.b64encode.
    """

    @staticmethod
    def _normalize(value):
        """Convierte memoryview a bytes para compatibilidad con Streamlit y base64."""
        if isinstance(value, memoryview):
            return bytes(value)
        return value

    def __init__(self, data):
        super().__init__({k: _Row._normalize(v) for k, v in data.items()})

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, int):
            try:
                return list(self.values())[key]
            except IndexError:
                return default
        return super().get(key, default)


class _PgCursor:
    """
    Wrapper sobre RealDictCursor que emula la interfaz de sqlite3.Cursor.
    - Convierte ? → %s antes de ejecutar
    - Retorna filas como _Row (compatible con sqlite3.Row: acceso por clave Y por índice)
    - Expone .fetchone(), .fetchall(), .lastrowid, .rowcount, .description
    """

    def __init__(self, pg_cursor):
        self._cur = pg_cursor

    @staticmethod
    def _fix(sql: str) -> str:
        """Convierte SQL SQLite → PostgreSQL usando la función global."""
        return _fix_sql_for_pg(sql)

    def execute(self, sql: str, params=None):
        fixed = self._fix(sql)
        # Convertir bool → int para columnas INTEGER de PostgreSQL
        if params:
            params = tuple(
                int(p) if isinstance(p, bool) else p
                for p in params
            )
        # Recuperación automática si la transacción está abortada (InFailedSqlTransaction)
        try:
            import psycopg2.extensions as _pgext
            if self._cur.connection.get_transaction_status() == _pgext.TRANSACTION_STATUS_INERROR:
                self._cur.connection.rollback()
        except Exception:
            try:
                self._cur.connection.rollback()
            except Exception:
                pass
        try:
            if params:
                self._cur.execute(fixed, params)
            else:
                self._cur.execute(fixed)
        except Exception:
            try:
                self._cur.connection.rollback()
            except Exception:
                pass
            raise
        return self

    def executemany(self, sql: str, seq_params):
        fixed = self._fix(sql)
        # Convertir bool → int en cada fila
        seq_params = [
            tuple(int(p) if isinstance(p, bool) else p for p in row)
            for row in seq_params
        ]
        self._cur.executemany(fixed, seq_params)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _Row(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [_Row(r) for r in rows]

    @property
    def lastrowid(self):
        try:
            self._cur.execute("SELECT lastval()")
            result = self._cur.fetchone()
            if result:
                return list(result.values())[0]
        except Exception:
            pass
        return None

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def __iter__(self):
        return iter(self.fetchall())


# ── Función de conexión unificada ─────────────────────────────────────────────

def _make_connection():
    """Crea y retorna una conexión al motor configurado."""
    if USE_POSTGRES:
        return _PgConnection(DATABASE_URL)
    else:
        conn = sqlite3.connect(
            str(Path(__file__).parent / 'learning_platform.db'),
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -2000")
        return conn


def _adapt_sql(sql: str) -> str:
    """
    Adapta SQL de SQLite a PostgreSQL cuando es necesario:
    - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
    - BLOB → BYTEA
    - INTEGER DEFAULT 0/1 → SMALLINT (no necesario pero aceptable)
    Solo se aplica en modo PostgreSQL.
    """
    if not USE_POSTGRES:
        return sql
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    sql = sql.replace("BLOB", "BYTEA")
    # PostgreSQL no soporta IF NOT EXISTS en ALTER TABLE igual que SQLite
    # Se maneja con try/except en el código de migración
    return sql


# =============================================================================
# DatabaseManager — Singleton con soporte dual SQLite / PostgreSQL
# =============================================================================

class DatabaseManager:
    """Gestor de base de datos compatible con SQLite y PostgreSQL."""

    _instance = None
    _conn = None
    _initialized = False   # ← evita re-ejecutar init_db en cada rerun

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._conn is None:
            self._init_connection()

    def _init_connection(self):
        """Inicializa la conexión al motor activo."""
        self._conn = _make_connection()
        if not USE_POSTGRES:
            self._create_indexes_sqlite()

    def _create_indexes_sqlite(self):
        """Crea índices en SQLite (PostgreSQL los recibe en init_db)."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_courses_teacher ON courses(teacher_id)",
            "CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_course ON tasks(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
            "CREATE INDEX IF NOT EXISTS idx_submissions_task_student ON submissions(task_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_exam_attempts_exam_student ON exam_attempts(exam_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_materials_course_module ON course_materials(course_id, module_id)",
            "CREATE INDEX IF NOT EXISTS idx_forum_course_date ON forum_posts(course_id, date)",
            "CREATE INDEX IF NOT EXISTS idx_ai_courses_student ON ai_courses(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_topics_course ON ai_course_topics(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_topic_exercises_course ON ai_topic_exercises(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_exercise_attempts_student ON ai_exercise_attempts(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_topic_evaluations_student ON ai_topic_evaluations(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_chat_course ON ai_course_chat(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_final_exams_course ON ai_course_final_exams(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_user1 ON conversations(user1_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_user2 ON conversations(user2_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON private_messages(conversation_id, sent_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread ON private_messages(recipient_id, is_read)",
        ]
        for idx in indexes:
            try:
                self._conn.execute(idx)
            except Exception:
                pass
        self._conn.commit()

    def get_connection(self):
        """Retorna la conexión activa."""
        if self._conn is None:
            self._init_connection()
        return self._conn

    def init_db(self):
        """Crea todas las tablas. Compatible con SQLite y PostgreSQL.
        Solo ejecuta el schema completo la primera vez por proceso."""
        if self._initialized:
            return self._conn
        self._initialized = True

        c = self._conn.cursor()

        tables = [
            # ── Usuarios ──────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                user_code TEXT UNIQUE,
                bio TEXT DEFAULT '',
                title TEXT DEFAULT '',
                subjects TEXT DEFAULT '',
                social_links TEXT DEFAULT '',
                avatar BLOB,
                theme TEXT DEFAULT 'dark',
                force_reset INTEGER DEFAULT 0,
                join_date DATE DEFAULT CURRENT_DATE,
                last_login TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                email TEXT,
                account_type TEXT DEFAULT 'full',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            # ── Cursos ────────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                teacher_id TEXT,
                description TEXT,
                cover_image BLOB,
                status TEXT DEFAULT 'active' CHECK(status IN ('active','archived','draft')),
                credits INTEGER DEFAULT 3,
                semester TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES users(username) ON DELETE SET NULL
            )""",
            # ── Módulos ───────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                order_index INTEGER DEFAULT 0,
                start_date DATE,
                end_date DATE,
                is_published INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            )""",
        ]

        for ddl in tables:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        tables2 = [
            # ── Tareas ────────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                module_id INTEGER,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                criteria TEXT,
                language TEXT DEFAULT 'python',
                submission_type TEXT DEFAULT 'code' CHECK(submission_type IN ('code','file','text')),
                points INTEGER DEFAULT 10,
                created_by TEXT NOT NULL,
                due_date DATE NOT NULL,
                max_attempts INTEGER DEFAULT 1,
                allow_late INTEGER DEFAULT 0,
                late_penalty REAL DEFAULT 0.0,
                is_published INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(username)
            )""",
            # ── Entregas ──────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                code TEXT,
                file_blob BLOB,
                file_name TEXT,
                file_size INTEGER,
                file_type TEXT,
                ai_feedback TEXT,
                ai_grade REAL,
                final_grade REAL,
                teacher_feedback TEXT,
                status TEXT DEFAULT 'submitted' CHECK(status IN ('submitted','graded','returned','late')),
                attempt_number INTEGER DEFAULT 1,
                submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                graded_date TIMESTAMP,
                graded_by TEXT,
                is_late INTEGER DEFAULT 0,
                late_days INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Matrículas ────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS enrollments (
                student_id TEXT NOT NULL,
                course_id INTEGER NOT NULL,
                enrollment_date DATE DEFAULT CURRENT_DATE,
                status TEXT DEFAULT 'active' CHECK(status IN ('active','dropped','completed')),
                final_grade REAL,
                PRIMARY KEY (student_id, course_id),
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            )""",
            # ── Materiales ────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS course_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                module_id INTEGER,
                title TEXT NOT NULL,
                type TEXT DEFAULT 'pdf' CHECK(type IN ('pdf','video','text','link','quiz')),
                content_text TEXT,
                content_blob BLOB,
                file_name TEXT,
                file_size INTEGER,
                url TEXT,
                order_index INTEGER DEFAULT 0,
                is_published INTEGER DEFAULT 1,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL
            )""",
        ]
        for ddl in tables2:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        tables3 = [
            # ── Foro ─────────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS forum_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                parent_id INTEGER,
                message TEXT NOT NULL,
                is_question INTEGER DEFAULT 0,
                is_resolved INTEGER DEFAULT 0,
                upvotes INTEGER DEFAULT 0,
                attachments TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                edited_at TIMESTAMP,
                is_edited INTEGER DEFAULT 0,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Exámenes ──────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                module_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 60,
                passing_score REAL DEFAULT 60.0,
                max_attempts INTEGER DEFAULT 1,
                shuffle_questions INTEGER DEFAULT 1,
                show_results INTEGER DEFAULT 1,
                is_published INTEGER DEFAULT 1,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL
            )""",
            # ── Preguntas de examen ───────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS exam_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                question_type TEXT DEFAULT 'multiple_choice' CHECK(question_type IN ('multiple_choice','true_false','short_answer','essay','open_text')),
                options_json TEXT,
                correct_index INTEGER,
                correct_answer TEXT,
                points INTEGER DEFAULT 1,
                explanation TEXT,
                order_index INTEGER DEFAULT 0,
                FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
            )""",
            # ── Intentos de examen ────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS exam_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                score REAL,
                max_score REAL,
                percentage REAL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration_seconds INTEGER,
                status TEXT DEFAULT 'in_progress' CHECK(status IN ('in_progress','completed','graded','expired')),
                details_json TEXT,
                graded_by TEXT,
                graded_at TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Respuestas de examen ──────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS exam_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                student_answer TEXT,
                selected_index INTEGER,
                points_earned REAL DEFAULT 0,
                feedback TEXT,
                is_correct INTEGER DEFAULT 0,
                FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES exam_questions(id) ON DELETE CASCADE
            )""",
        ]
        for ddl in tables3:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        tables4 = [
            # ── Notificaciones ────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT DEFAULT 'info',
                is_read INTEGER DEFAULT 0,
                link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Logs de actividad ─────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE SET NULL
            )""",
            # ── Configuración ─────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            # ── Cursos IA ─────────────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT 'Curso IA',
                description TEXT,
                topic TEXT,
                difficulty TEXT DEFAULT 'intermediate',
                language TEXT DEFAULT 'python',
                level TEXT,
                total_topics INTEGER DEFAULT 0,
                completed_topics INTEGER DEFAULT 0,
                sections_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active' CHECK(status IN ('active','completed','paused')),
                progress_percentage REAL DEFAULT 0.0,
                last_activity TIMESTAMP,
                difficulty_setting TEXT DEFAULT 'normal',
                assessment_score REAL DEFAULT 0.0,
                assessment_data TEXT,
                display_status TEXT DEFAULT 'active',
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Temas de cursos IA ────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_course_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                content TEXT,
                objectives TEXT,
                topic_number INTEGER DEFAULT 0,
                order_index INTEGER DEFAULT 0,
                estimated_hours REAL DEFAULT 1.0,
                is_completed INTEGER DEFAULT 0,
                is_unlocked INTEGER DEFAULT 0,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE
            )""",
        ]
        for ddl in tables4:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        tables5 = [
            # ── Materiales de cursos IA ───────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_course_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_course_id INTEGER NOT NULL,
                topic_id INTEGER,
                title TEXT NOT NULL,
                type TEXT DEFAULT 'text',
                content TEXT,
                description TEXT,
                url TEXT,
                order_index INTEGER DEFAULT 0,
                estimated_minutes INTEGER DEFAULT 30,
                difficulty_level INTEGER DEFAULT 1,
                language_content TEXT DEFAULT 'es',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE
            )""",
            # ── Materiales por tema IA ────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_topic_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_course_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                type TEXT DEFAULT 'text',
                content TEXT,
                url TEXT,
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE CASCADE
            )""",
            # ── Ejercicios por tema IA ────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_topic_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_course_id INTEGER,
                topic_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                question TEXT,
                options TEXT,
                correct_index INTEGER,
                explanation TEXT,
                exercise_type TEXT DEFAULT 'coding',
                difficulty TEXT DEFAULT 'medium',
                difficulty_level INTEGER DEFAULT 1,
                topic_area TEXT DEFAULT 'general',
                language TEXT DEFAULT 'python',
                starter_code TEXT,
                solution_code TEXT,
                code_example TEXT,
                test_cases TEXT,
                hints TEXT,
                points INTEGER DEFAULT 10,
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE SET NULL
            )""",
            # ── Intentos de ejercicios IA ─────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_exercise_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                ai_course_id INTEGER,
                code TEXT,
                submitted_answer TEXT,
                output TEXT,
                feedback TEXT,
                score REAL DEFAULT 0,
                max_score REAL DEFAULT 10,
                is_correct INTEGER DEFAULT 0,
                attempt_number INTEGER DEFAULT 1,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exercise_id) REFERENCES ai_topic_exercises(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Evaluaciones de temas IA ──────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_topic_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_course_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                score REAL DEFAULT 0,
                max_score REAL DEFAULT 100,
                percentage REAL DEFAULT 0,
                details_json TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
        ]
        for ddl in tables5:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        tables6 = [
            # ── Chat de cursos IA ─────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_course_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                content TEXT NOT NULL,
                topic_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE SET NULL
            )""",
            # ── Exámenes finales de cursos IA ─────────────────────────────────
            """CREATE TABLE IF NOT EXISTS ai_course_final_exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                questions_json TEXT,
                questions_data TEXT,
                answers_json TEXT,
                responses_data TEXT,
                score REAL,
                max_score REAL,
                percentage REAL,
                passed INTEGER DEFAULT 0,
                attempt_number INTEGER DEFAULT 1,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Evaluaciones de idioma ────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS language_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                language TEXT NOT NULL,
                level TEXT,
                score REAL,
                max_score REAL DEFAULT 100,
                percentage REAL,
                assessment_data TEXT,
                recommendations TEXT,
                details_json TEXT,
                assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Ejercicios personales ─────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS personal_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                language TEXT DEFAULT 'python',
                difficulty TEXT DEFAULT 'medium',
                starter_code TEXT,
                solution_code TEXT,
                hints TEXT,
                tags TEXT,
                is_public INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Intentos de ejercicios personales ────────────────────────────
            """CREATE TABLE IF NOT EXISTS personal_exercise_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exercise_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                code TEXT,
                output TEXT,
                feedback TEXT,
                score REAL DEFAULT 0,
                is_correct INTEGER DEFAULT 0,
                attempt_number INTEGER DEFAULT 1,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exercise_id) REFERENCES personal_exercises(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
        ]
        for ddl in tables6:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        tables7 = [
            # ── Progreso de aprendizaje ───────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS learning_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                course_id INTEGER,
                ai_course_id INTEGER,
                module_id INTEGER,
                topic_id INTEGER,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                progress_percentage REAL DEFAULT 0,
                time_spent_minutes INTEGER DEFAULT 0,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Recursos de aprendizaje ───────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS learning_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                type TEXT DEFAULT 'article',
                url TEXT,
                content TEXT,
                tags TEXT,
                language TEXT,
                difficulty TEXT DEFAULT 'beginner',
                is_public INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(username) ON DELETE SET NULL
            )""",
            # ── Logros de estudiantes ─────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS student_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                achievement_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                icon TEXT,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details_json TEXT,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Contenido de chat IA de módulo ────────────────────────────────
            """CREATE TABLE IF NOT EXISTS module_ai_chat_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                course_id INTEGER,
                content_type TEXT DEFAULT 'summary',
                content TEXT,
                content_text TEXT,
                file_name TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
            )""",
            # ── Preguntas sugeridas del chat IA ───────────────────────────────
            """CREATE TABLE IF NOT EXISTS module_ai_chat_suggested_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                course_id INTEGER,
                question TEXT NOT NULL,
                question_text TEXT,
                category TEXT DEFAULT 'general',
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
            )""",
        ]
        for ddl in tables7:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        tables8 = [
            # ── Conversaciones del chat IA de módulo ──────────────────────────
            """CREATE TABLE IF NOT EXISTS module_ai_chat_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                course_id INTEGER,
                user_id TEXT,
                student_id TEXT,
                role TEXT DEFAULT 'user',
                content TEXT DEFAULT '',
                message TEXT,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Chat grupal IA de módulo ──────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS module_ai_group_chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                course_id INTEGER,
                user_id TEXT NOT NULL,
                user_role TEXT DEFAULT 'student',
                role TEXT DEFAULT 'user',
                content TEXT DEFAULT '',
                message TEXT,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Conversaciones privadas ───────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                course_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user1_id, user2_id),
                FOREIGN KEY (user1_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (user2_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Mensajes privados ─────────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS private_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                content TEXT,
                message_text TEXT,
                is_read INTEGER DEFAULT 0,
                read_at TIMESTAMP,
                has_attachment INTEGER DEFAULT 0,
                is_deleted_sender INTEGER DEFAULT 0,
                is_deleted_recipient INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            # ── Adjuntos de mensajes ──────────────────────────────────────────
            """CREATE TABLE IF NOT EXISTS message_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER,
                file_type TEXT,
                file_blob BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES private_messages(id) ON DELETE CASCADE
            )""",
            # ── Mensajes de administración (broadcast/anuncios) ───────────────
            """CREATE TABLE IF NOT EXISTS admin_broadcast_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                recipient_id TEXT,
                subject TEXT,
                content TEXT NOT NULL,
                type TEXT DEFAULT 'announcement',
                is_read INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES users(username) ON DELETE SET NULL
            )""",
            # ── Configuración del sistema (usada por views_admin.py) ──────────
            """CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            # ── Chat exclusivo entre administradores ──────────────────────────
            """CREATE TABLE IF NOT EXISTS admin_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '',
                is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS admin_message_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_content BLOB NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES admin_messages(id) ON DELETE CASCADE
            )""",
            # ── Mensajes directos admin↔admin ─────────────────────────────────
            """CREATE TABLE IF NOT EXISTS admin_direct_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '',
                is_read INTEGER DEFAULT 0,
                has_attachment INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS admin_direct_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_content BLOB NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES admin_direct_messages(id) ON DELETE CASCADE
            )""",
            # ── Chat usuario (estudiante/docente) ↔ administración ────────────
            """CREATE TABLE IF NOT EXISTS admin_student_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '',
                is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS admin_student_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_content BLOB NOT NULL,
                FOREIGN KEY (message_id) REFERENCES admin_student_messages(id) ON DELETE CASCADE
            )""",
            # ── Chat docente ↔ administración ─────────────────────────────────
            """CREATE TABLE IF NOT EXISTS admin_teacher_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                teacher_id TEXT,
                student_id TEXT,
                message_text TEXT NOT NULL DEFAULT '',
                is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS admin_teacher_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_content BLOB NOT NULL,
                FOREIGN KEY (message_id) REFERENCES admin_teacher_messages(id) ON DELETE CASCADE
            )""",
        ]
        for ddl in tables8:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla: {e}")
        self._conn.commit()

        # ── Tablas de Engagement ──────────────────────────────────────────────
        tables_engagement = [
            """CREATE TABLE IF NOT EXISTS user_streaks (
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
            )""",
            """CREATE TABLE IF NOT EXISTS daily_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_date DATE NOT NULL,
                language TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                exercise_code TEXT,
                solution_code TEXT,
                test_cases TEXT,
                points INTEGER DEFAULT 50,
                bonus_points INTEGER DEFAULT 20,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(challenge_date, language)
            )""",
            """CREATE TABLE IF NOT EXISTS daily_challenge_attempts (
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
            )""",
            """CREATE TABLE IF NOT EXISTS user_points (
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
            )""",
            """CREATE TABLE IF NOT EXISTS point_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                points INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                source TEXT NOT NULL,
                description TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                badge_key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT,
                category TEXT,
                requirement_type TEXT NOT NULL,
                requirement_value INTEGER,
                points_reward INTEGER DEFAULT 0,
                rarity TEXT DEFAULT 'common',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS user_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                badge_id INTEGER NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                progress INTEGER DEFAULT 0,
                is_displayed INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE,
                UNIQUE(user_id, badge_id)
            )""",
            """CREATE TABLE IF NOT EXISTS user_coins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                total_coins INTEGER DEFAULT 0,
                coins_earned INTEGER DEFAULT 0,
                coins_spent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
                UNIQUE(user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS reward_shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                item_type TEXT NOT NULL,
                cost_coins INTEGER NOT NULL,
                cost_points INTEGER DEFAULT 0,
                stock INTEGER DEFAULT -1,
                is_available INTEGER DEFAULT 1,
                image_url TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS user_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                coins_spent INTEGER NOT NULL,
                points_spent INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed',
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                redeemed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES reward_shop_items(id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS user_active_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                item_key TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )""",
            """CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                period TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                rank_position INTEGER,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
                UNIQUE(user_id, period, period_start)
            )""",
            """CREATE TABLE IF NOT EXISTS teams (
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
            )""",
            """CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                points_contributed INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
                UNIQUE(team_id, user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS code_duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenger_id TEXT NOT NULL,
                opponent_id TEXT NOT NULL,
                challenge_id INTEGER,
                status TEXT DEFAULT 'pending',
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
            )""",
            """CREATE TABLE IF NOT EXISTS activity_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                activity_date DATE NOT NULL,
                exercises_completed INTEGER DEFAULT 0,
                time_spent_minutes INTEGER DEFAULT 0,
                points_earned INTEGER DEFAULT 0,
                challenges_completed INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
                UNIQUE(user_id, activity_date)
            )""",
            """CREATE TABLE IF NOT EXISTS user_statistics (
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
            )""",
            """CREATE TABLE IF NOT EXISTS push_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
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
            )""",
            """CREATE TABLE IF NOT EXISTS notification_preferences (
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
            )""",
            """CREATE TABLE IF NOT EXISTS live_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                instructor_id TEXT,
                max_participants INTEGER DEFAULT 100,
                current_participants INTEGER DEFAULT 0,
                event_url TEXT,
                scheduled_start TIMESTAMP NOT NULL,
                scheduled_end TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'scheduled',
                points_reward INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (instructor_id) REFERENCES users(username) ON DELETE SET NULL
            )""",
            """CREATE TABLE IF NOT EXISTS event_participants (
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
            )""",
            """CREATE TABLE IF NOT EXISTS daily_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_date DATE NOT NULL UNIQUE,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                difficulty TEXT DEFAULT 'medium',
                topic TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS daily_question_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                user_answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username),
                FOREIGN KEY (question_id) REFERENCES daily_questions(id),
                UNIQUE(user_id, question_id)
            )""",
        ]
        for ddl in tables_engagement:
            try:
                c.execute(_adapt_sql(ddl))
            except Exception as e:
                print(f"[DB] Error creando tabla engagement: {e}")
        self._conn.commit()

        # ── Semilla: configuración por defecto ───────────────────────────────
        default_settings = [
            ('site_name', 'Plataforma Educativa IA', 'Nombre del sitio'),
            ('site_description', 'Plataforma educativa con inteligencia artificial', 'Descripción del sitio'),
            ('allow_registrations', '0', 'Permitir registro público'),
            ('max_file_size_mb', '10', 'Tamaño máximo de archivo en MB'),
            ('default_language', 'python', 'Lenguaje de programación por defecto'),
            ('ai_enabled', '1', 'Habilitar funcionalidades de IA'),
            ('maintenance_mode', '0', 'Modo de mantenimiento'),
            ('smtp_enabled', '0', 'Habilitar envío de correos'),
            ('default_theme', 'dark', 'Tema por defecto'),
            ('session_timeout_minutes', '120', 'Tiempo de expiración de sesión'),
            ('backup_enabled', '1', 'Habilitar backups automáticos'),
            ('logo_url', '', 'URL del logo del sitio'),
            ('login_background_url', '', 'URL del fondo del login'),
            ('footer_text', '© 2026 Plataforma Educativa IA', 'Texto del footer'),
            ('gym_block_paste', '1', 'Bloquear pegar código en el Gimnasio'),
        ]
        for key, value, desc in default_settings:
            try:
                c.execute(
                    "INSERT INTO settings (key, value, description) VALUES (?, ?, ?)"
                    " ON CONFLICT(key) DO NOTHING",
                    (key, value, desc)
                )
            except Exception:
                try:
                    c.execute(
                        "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)" if not USE_POSTGRES
                        else "INSERT INTO settings (key, value, description) VALUES (%s, %s, %s) ON CONFLICT (key) DO NOTHING",
                        (key, value, desc)
                    )
                except Exception:
                    pass

        # ── Semilla: usuario administrador ────────────────────────────────────
        try:
            existing = c.execute(
                "SELECT username FROM users WHERE role = 'admin' LIMIT 1"
            ).fetchone()
            if not existing:
                admin_hash = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
                if USE_POSTGRES:
                    c.execute(
                        """INSERT INTO users
                           (username, password_hash, role, first_name, last_name,
                            full_name, user_code, is_active)
                           VALUES (%s, %s, 'admin', 'Admin', 'Sistema',
                                   'Admin Sistema', 'ADM000001', 1)
                           ON CONFLICT (username) DO NOTHING""",
                        ('admin', admin_hash)
                    )
                else:
                    c.execute(
                        """INSERT OR IGNORE INTO users
                           (username, password_hash, role, first_name, last_name,
                            full_name, user_code, is_active)
                           VALUES (?, ?, 'admin', 'Admin', 'Sistema',
                                   'Admin Sistema', 'ADM000001', 1)""",
                        ('admin', admin_hash)
                    )
        except Exception as e:
            print(f"[DB] Error creando admin: {e}")

        self._conn.commit()

        # ── Migraciones: columnas añadidas después del schema inicial ─────────
        self._run_migrations()

        # ── Índices para PostgreSQL ────────────────────────────────────────────
        if USE_POSTGRES:
            self._create_indexes_postgres(c)

        # ── Semilla de engagement (badges y shop items) ───────────────────────
        try:
            from database_engagement import insert_default_badges, insert_default_shop_items
            insert_default_badges()
            insert_default_shop_items()
        except Exception as _e:
            print(f"[DB] Semilla engagement (no crítico): {_e}")

        print("[DB] Base de datos inicializada correctamente.")
        return self._conn

    def _create_indexes_postgres(self, c):
        """Crea índices en PostgreSQL usando IF NOT EXISTS."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_courses_teacher ON courses(teacher_id)",
            "CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_course ON tasks(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
            "CREATE INDEX IF NOT EXISTS idx_submissions_task_student ON submissions(task_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_exam_attempts_exam_student ON exam_attempts(exam_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_materials_course_module ON course_materials(course_id, module_id)",
            "CREATE INDEX IF NOT EXISTS idx_forum_course_date ON forum_posts(course_id, date)",
            "CREATE INDEX IF NOT EXISTS idx_ai_courses_student ON ai_courses(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_topics_course ON ai_course_topics(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_topic_exercises_course ON ai_topic_exercises(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_exercise_attempts_student ON ai_exercise_attempts(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_topic_evaluations_student ON ai_topic_evaluations(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_chat_course ON ai_course_chat(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_final_exams_course ON ai_course_final_exams(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_user1 ON conversations(user1_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_user2 ON conversations(user2_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON private_messages(conversation_id, sent_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread ON private_messages(recipient_id, is_read)",
            "CREATE INDEX IF NOT EXISTS idx_activity_logs_user ON activity_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON activity_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)",
        ]
        for idx in indexes:
            try:
                c.execute(idx)
            except Exception:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
        self._conn.commit()

    def _run_migrations(self):
        """
        Agrega columnas que fueron añadidas al schema después de la creación inicial
        de la base de datos. Seguro de ejecutar múltiples veces (idempotente).
        """
        # Columnas a agregar: (tabla, columna, tipo_sql)
        migrations = [
            ("ai_courses",       "level",             "TEXT"),
            ("ai_courses",       "last_activity",      "TIMESTAMP"),
            ("ai_courses",       "difficulty_setting", "TEXT DEFAULT 'normal'"),
            ("ai_courses",       "assessment_score",   "REAL DEFAULT 0.0"),
            ("ai_courses",       "assessment_data",    "TEXT"),
            ("ai_courses",       "display_status",     "TEXT DEFAULT 'active'"),
            ("ai_courses",       "sections_count",     "INTEGER DEFAULT 0"),
            ("enrollments",      "display_status",     "TEXT DEFAULT 'active'"),
            ("admin_messages",   "has_attachment",     "INTEGER DEFAULT 0"),
            ("admin_messages",   "message_text",       "TEXT NOT NULL DEFAULT ''"),
            ("admin_messages",   "is_read_by",         "TEXT DEFAULT '[]'"),
            # courses — columnas añadidas por check_teacher_schema
            ("courses",          "level",              "TEXT DEFAULT 'Básico'"),
            ("courses",          "updated_at",         "TIMESTAMP"),
            # submissions — columnas que usa el código
            ("submissions",      "teacher_feedback",   "TEXT"),
            ("submissions",      "file_name",          "TEXT"),
            # tasks — columnas extra
            ("tasks",            "allow_late_submissions", "INTEGER DEFAULT 1"),
            # exams — columnas extra
            ("exams",            "is_published",       "INTEGER DEFAULT 0"),
            ("exams",            "passing_score",      "REAL DEFAULT 60"),
            # ai_course_topics — columnas faltantes
            ("ai_course_topics",   "objectives",       "TEXT"),
            ("ai_course_topics",   "topic_number",     "INTEGER DEFAULT 0"),
            ("ai_course_topics",   "estimated_hours",  "REAL DEFAULT 1.0"),
            ("ai_course_topics",   "is_unlocked",      "INTEGER DEFAULT 0"),
            # ai_topic_exercises — columnas faltantes
            ("ai_topic_exercises",   "question",         "TEXT"),
            ("ai_topic_exercises",   "options",          "TEXT"),
            ("ai_topic_exercises",   "correct_index",    "INTEGER"),
            ("ai_topic_exercises",   "explanation",      "TEXT"),
            ("ai_topic_exercises",   "difficulty_level", "INTEGER DEFAULT 1"),
            ("ai_topic_exercises",   "topic_area",       "TEXT DEFAULT 'general'"),
            ("ai_topic_exercises",   "code_example",     "TEXT"),
            # ai_exercise_attempts — columnas faltantes
            ("ai_exercise_attempts", "submitted_answer", "TEXT"),
            ("ai_exercise_attempts", "max_score",        "REAL DEFAULT 10"),
            # conversations — course_id añadido después
            ("conversations",        "course_id",        "INTEGER"),
            # private_messages — message_text como alias de content + has_attachment
            ("private_messages",     "message_text",     "TEXT"),
            ("private_messages",     "has_attachment",   "INTEGER DEFAULT 0"),
            # message_attachments — uploaded_at como alias de created_at
            ("message_attachments",          "uploaded_at",    "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            # module_ai_chat_content — columnas del código
            ("module_ai_chat_content",       "content_text",   "TEXT"),
            ("module_ai_chat_content",       "file_name",      "TEXT"),
            ("module_ai_chat_content",       "updated_at",     "TIMESTAMP"),
            # module_ai_chat_suggested_questions — question_text
            ("module_ai_chat_suggested_questions", "question_text", "TEXT"),
            # module_ai_chat_conversations — student_id, message, response
            ("module_ai_chat_conversations", "student_id",     "TEXT"),
            ("module_ai_chat_conversations", "message",        "TEXT"),
            ("module_ai_chat_conversations", "response",       "TEXT"),
            # admin_teacher_messages — teacher_id es el nombre real en el código
            ("admin_teacher_messages", "teacher_id", "TEXT"),
            ("module_ai_group_chat",         "user_role",      "TEXT DEFAULT 'student'"),
            ("module_ai_group_chat",         "message",        "TEXT"),
            ("module_ai_group_chat",         "response",       "TEXT"),
            # ai_courses — columnas faltantes usadas en el código
            ("ai_courses",             "completed_at",       "TIMESTAMP"),
            # ai_course_final_exams — columnas faltantes
            ("ai_course_final_exams",  "questions_data",     "TEXT"),
            ("ai_course_final_exams",  "responses_data",     "TEXT"),
            ("ai_course_final_exams",  "attempt_number",     "INTEGER DEFAULT 1"),
            # ai_course_materials — columnas faltantes
            ("ai_course_materials",    "is_completed",       "INTEGER DEFAULT 0"),
            ("ai_course_materials",    "topic_id",           "INTEGER"),
            ("ai_course_materials",    "description",        "TEXT"),
            ("ai_course_materials",    "estimated_minutes",  "INTEGER DEFAULT 30"),
            ("ai_course_materials",    "difficulty_level",   "INTEGER DEFAULT 1"),
            ("ai_course_materials",    "language_content",   "TEXT DEFAULT 'es'"),
            # message_attachments — file_content para archivos de chat
            ("message_attachments",    "file_content",       "BYTEA"),
            # module_ai_chat_content — created_at
            ("module_ai_chat_content", "created_at",         "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            # language_assessments — columnas extra usadas en código
            ("language_assessments", "percentage",       "REAL"),
            ("language_assessments", "max_score",        "REAL DEFAULT 100"),
            ("language_assessments", "assessment_data",  "TEXT"),
            ("language_assessments", "recommendations",  "TEXT"),
            ("language_assessments", "created_at",       "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]

        # Tablas de chat que pueden no existir en BDs migradas antes de este schema
        missing_tables = [
            ("admin_student_messages",
             """CREATE TABLE IF NOT EXISTS admin_student_messages (
                id SERIAL PRIMARY KEY, sender_id TEXT NOT NULL, student_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '', is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE)"""),
            ("admin_student_files",
             """CREATE TABLE IF NOT EXISTS admin_student_files (
                id SERIAL PRIMARY KEY, message_id INTEGER NOT NULL, file_name TEXT NOT NULL,
                file_type TEXT NOT NULL, file_size INTEGER NOT NULL, file_content BYTEA NOT NULL,
                FOREIGN KEY (message_id) REFERENCES admin_student_messages(id) ON DELETE CASCADE)"""),
            ("admin_teacher_messages",
             """CREATE TABLE IF NOT EXISTS admin_teacher_messages (
                id SERIAL PRIMARY KEY, sender_id TEXT NOT NULL, student_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '', is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE)"""),
            ("admin_teacher_files",
             """CREATE TABLE IF NOT EXISTS admin_teacher_files (
                id SERIAL PRIMARY KEY, message_id INTEGER NOT NULL, file_name TEXT NOT NULL,
                file_type TEXT NOT NULL, file_size INTEGER NOT NULL, file_content BYTEA NOT NULL,
                FOREIGN KEY (message_id) REFERENCES admin_teacher_messages(id) ON DELETE CASCADE)"""),
            ("admin_direct_messages",
             """CREATE TABLE IF NOT EXISTS admin_direct_messages (
                id SERIAL PRIMARY KEY, sender_id TEXT NOT NULL, recipient_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '', is_read INTEGER DEFAULT 0,
                has_attachment INTEGER DEFAULT 0, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES users(username) ON DELETE CASCADE)"""),
            ("admin_direct_files",
             """CREATE TABLE IF NOT EXISTS admin_direct_files (
                id SERIAL PRIMARY KEY, message_id INTEGER NOT NULL, file_name TEXT NOT NULL,
                file_type TEXT NOT NULL, file_size INTEGER NOT NULL, file_content BYTEA NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES admin_direct_messages(id) ON DELETE CASCADE)"""),
            ("admin_messages",
             """CREATE TABLE IF NOT EXISTS admin_messages (
                id SERIAL PRIMARY KEY, sender_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '', is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE)"""),
            ("admin_message_files",
             """CREATE TABLE IF NOT EXISTS admin_message_files (
                id SERIAL PRIMARY KEY, message_id INTEGER NOT NULL, file_name TEXT NOT NULL,
                file_type TEXT NOT NULL, file_size INTEGER NOT NULL, file_content BYTEA NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES admin_messages(id) ON DELETE CASCADE)"""),
        ]
        if USE_POSTGRES:
            for tname, ddl in missing_tables:
                try:
                    self._conn.execute(ddl)
                    self._conn.commit()
                except Exception as e:
                    print(f"[DB] Migración tabla {tname}: {e}")
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass

        for table, column, col_type in migrations:
            try:
                if USE_POSTGRES:
                    # En PostgreSQL usamos DO $$ ... $$ para ignorar si ya existe
                    self._conn.execute(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name = '{table}' AND column_name = '{column}'
                            ) THEN
                                ALTER TABLE {table} ADD COLUMN {column} {col_type};
                            END IF;
                        END;
                        $$;
                    """)
                    self._conn.commit()
                else:
                    # En SQLite intentamos añadir y capturamos el error si ya existe
                    try:
                        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                        self._conn.commit()
                    except Exception:
                        pass  # La columna ya existe
            except Exception as e:
                print(f"[DB] Migración {table}.{column}: {e}")
                try:
                    self._conn.rollback()
                except Exception:
                    pass

    # ── Métodos de utilidad ───────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Genera un hash bcrypt de la contraseña."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verifica una contraseña contra su hash bcrypt."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False

    def generate_user_code(self, role: str) -> str:
        """
        Genera un código único de usuario con formato:
        STU/TCH/ADM + 6 dígitos (e.g. STU001234).
        """
        prefix_map = {'student': 'STU', 'teacher': 'TCH', 'admin': 'ADM'}
        prefix = prefix_map.get(role, 'USR')
        conn = self.get_connection()
        for _ in range(50):
            digits = ''.join(random.choices(string.digits, k=6))
            code = f"{prefix}{digits}"
            try:
                row = conn.execute(
                    "SELECT username FROM users WHERE user_code = ?", (code,)
                ).fetchone()
                if not row:
                    return code
            except Exception:
                return code
        # Fallback con timestamp si todos los intentos fallan
        return f"{prefix}{datetime.now().strftime('%H%M%S')}"

    def create_backup(self) -> str | None:
        """
        Copia la base de datos SQLite a la carpeta backups/.
        No hace nada en modo PostgreSQL.
        Retorna la ruta del backup o None.
        """
        if USE_POSTGRES:
            print("[DB] Backup omitido (PostgreSQL).")
            return None

        db_path = Path(__file__).parent / 'learning_platform.db'
        if not db_path.exists():
            print("[DB] Archivo de base de datos no encontrado.")
            return None

        backup_dir = Path(__file__).parent / 'backups'
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"learning_platform_backup_{timestamp}.db"

        import shutil
        try:
            shutil.copy2(str(db_path), str(backup_path))
            print(f"[DB] Backup creado: {backup_path}")
            return str(backup_path)
        except Exception as e:
            print(f"[DB] Error creando backup: {e}")
            return None

    def log_activity(
        self,
        user_id: str,
        action: str,
        entity_type: str = None,
        entity_id=None,
        details=None,
        ip: str = None,
        user_agent: str = None,
    ):
        """Registra una entrada en activity_logs."""
        try:
            conn = self.get_connection()
            details_str = json.dumps(details) if isinstance(details, (dict, list)) else details
            conn.execute(
                """INSERT INTO activity_logs
                   (user_id, action, entity_type, entity_id, details, ip_address, user_agent)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, action, entity_type, str(entity_id) if entity_id is not None else None,
                 details_str, ip, user_agent),
            )
            conn.commit()
        except Exception as e:
            print(f"[DB] Error registrando actividad: {e}")

    def close(self):
        """Cierra la conexión y resetea el singleton."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        DatabaseManager._instance = None


# =============================================================================
# Funciones de conveniencia a nivel de módulo
# =============================================================================

db_manager = DatabaseManager()


def get_db_connection():
    """Retorna la conexión activa del gestor global."""
    return db_manager.get_connection()


def init_db():
    """Inicializa la base de datos usando el gestor global.
    En entorno Streamlit usa cache_resource para no re-ejecutar en cada rerun."""
    return db_manager.init_db()


def hash_password(password: str) -> str:
    """Hash bcrypt de la contraseña."""
    return db_manager.hash_password(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verifica contraseña contra hash bcrypt."""
    return db_manager.verify_password(password, hashed)


def generate_user_code(role: str) -> str:
    """Genera un código único de usuario."""
    return db_manager.generate_user_code(role)


# Exportar parse_dt y fmt_date para uso en vistas
__all__ = [
    'db_manager', 'get_db_connection', 'init_db',
    'hash_password', 'verify_password', 'generate_user_code',
    'USE_POSTGRES', 'parse_dt', 'fmt_date', 'bytes_to_b64', 'to_bytes', 'to_date',
]
