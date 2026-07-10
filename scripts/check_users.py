from database import db_manager

conn = db_manager.get_connection()
users = conn.execute('SELECT username, full_name, role FROM users WHERE role="student"').fetchall()

print("Usuarios estudiantes:")
for u in users:
    print(f"  - {u[0]} | {u[1]} | {u[2]}")
