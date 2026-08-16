# -*- coding: utf-8 -*-
"""
Script de prueba del nuevo database.py con soporte dual SQLite/PostgreSQL.
Ejecutar con:
    python scripts/test_database.py                          # SQLite
    $env:DATABASE_URL="postgresql://..."; python scripts/test_database.py  # PostgreSQL
"""
import os, sys

# Solo borra DATABASE_URL si no estaba ya definida
_db_url = os.environ.get('DATABASE_URL', '')
os.environ['TESTING'] = 'true'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IS_PG = bool(_db_url)
PASS = "✅ PASS"
FAIL = "❌ FAIL"
errors = []

def check(name, condition, detail=""):
    if condition:
        print(f"{PASS}  {name}")
    else:
        print(f"{FAIL}  {name} {detail}")
        errors.append(name)

print("=" * 55)
print(f"  Test: database.py ({'PostgreSQL' if IS_PG else 'SQLite'})")
print("=" * 55)

# TEST 1: Importacion
print("\n── Importacion ──")
try:
    from database import (
        db_manager, init_db, hash_password,
        verify_password, generate_user_code, get_db_connection
    )
    check("Importacion de database.py", True)
except Exception as e:
    check("Importacion de database.py", False, str(e))
    print("No se puede continuar")
    sys.exit(1)

# TEST 2: Conexion
print("\n── Conexion ──")
try:
    conn = db_manager.get_connection()
    check("get_connection() retorna objeto", conn is not None)
    check("get_db_connection() funciona", get_db_connection() is not None)
except Exception as e:
    check("get_connection()", False, str(e))

# TEST 3: init_db
print("\n── init_db() ──")
try:
    result = init_db()
    check("init_db() sin excepciones", True)
    check("init_db() retorna conexion", result is not None)
except Exception as e:
    check("init_db()", False, str(e))

# TEST 4: Tablas creadas
print("\n── Tablas ──")
try:
    if IS_PG:
        rows = conn.execute(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    table_names = [r['name'] if isinstance(r, dict) else r[0] for r in rows]
    expected = ['users', 'courses', 'modules', 'tasks', 'submissions',
                'enrollments', 'exams', 'notifications', 'settings', 'activity_logs']
    for t in expected:
        check(f"Tabla '{t}' existe", t in table_names)
    print(f"     Total tablas: {len(table_names)}")
except Exception as e:
    check("Consulta de tablas", False, str(e))

# TEST 5: Usuario admin
print("\n── Usuario admin ──")
try:
    admin = conn.execute(
        "SELECT username, role FROM users WHERE username='admin'"
    ).fetchone()
    admin_dict = dict(admin) if admin else None
    check("Usuario admin existe", admin_dict is not None)
    if admin_dict:
        check("Rol es admin", admin_dict.get('role') == 'admin')
except Exception as e:
    check("Usuario admin", False, str(e))

# TEST 6: Passwords
print("\n── Passwords ──")
try:
    h = hash_password('test_password_123')
    check("hash_password retorna string", isinstance(h, str))
    check("hash_password genera bcrypt", h.startswith('$2b$'))
    check("verify_password correcto", verify_password('test_password_123', h))
    check("verify_password incorrecto", not verify_password('wrong_pass', h))
except Exception as e:
    check("hash/verify_password", False, str(e))

# TEST 7: Codigos de usuario
print("\n── Codigos de usuario ──")
try:
    for role, prefix in [('student', 'STU'), ('teacher', 'TCH'), ('admin', 'ADM')]:
        code = generate_user_code(role)
        check(f"generate_user_code('{role}') = {code}",
              code.startswith(prefix) and len(code) == 9)
except Exception as e:
    check("generate_user_code", False, str(e))

# TEST 8: log_activity
print("\n── log_activity ──")
try:
    db_manager.log_activity('admin', 'test_db_script', 'script', '1', {'test': True})
    log = conn.execute(
        "SELECT * FROM activity_logs WHERE action='test_db_script'"
    ).fetchone()
    check("log_activity inserta registro", log is not None)
except Exception as e:
    check("log_activity", False, str(e))

# TEST 9: create_backup
print("\n── create_backup ──")
try:
    backup = db_manager.create_backup()
    if IS_PG:
        check("create_backup retorna None en PostgreSQL (correcto)", backup is None)
    else:
        check("create_backup retorna ruta", backup is not None)
        check("Archivo de backup existe", backup and os.path.exists(backup))
except Exception as e:
    check("create_backup", False, str(e))

# TEST 10: CRUD
print("\n── Operaciones CRUD ──")
try:
    h2 = hash_password('test123')
    if IS_PG:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, first_name, last_name, full_name) "
            "VALUES (%s, %s, 'student', 'Test', 'User', 'Test User') "
            "ON CONFLICT (username) DO NOTHING",
            ('test_user_db_script', h2)
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO users "
            "(username, password_hash, role, first_name, last_name, full_name) "
            "VALUES (?, ?, 'student', 'Test', 'User', 'Test User')",
            ('test_user_db_script', h2)
        )
    conn.commit()
    user = conn.execute(
        "SELECT username, role FROM users WHERE username=?",
        ('test_user_db_script',)
    ).fetchone()
    user_dict = dict(user) if user else None
    check("INSERT usuario de prueba", user_dict is not None)
    check("SELECT usuario de prueba", user_dict and user_dict.get('role') == 'student')
    conn.execute("DELETE FROM users WHERE username=?", ('test_user_db_script',))
    conn.commit()
    check("DELETE usuario de prueba", True)
except Exception as e:
    check("Operaciones CRUD", False, str(e))

# RESUMEN
print()
print("=" * 55)
total_checks = 28 if IS_PG else 30
passed = total_checks - len(errors)
print(f"  Resultado: {passed}/{total_checks} tests pasaron, {len(errors)} fallaron")
if errors:
    print(f"  Fallaron: {errors}")
print("=" * 55)
sys.exit(0 if not errors else 1)
