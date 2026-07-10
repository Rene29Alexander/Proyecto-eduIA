with open('views_student.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the _total_attempts query and use a simple fixed key per user
# The key invalidation happens via _refresh_recs_gym button which deletes the key

old_gym = (
    '        _total_attempts = conn.execute(\n'
    '            "SELECT COUNT(*) FROM daily_challenge_attempts WHERE user_id=?",\n'
    '            (u["username"],)\n'
    '        ).fetchone()[0]\n'
    '        _rkey = f"cached_recs_gym_{u[\'username\']}_{_total_attempts}"\n'
    '        if _refresh_recs_gym:\n'
    '            with st.spinner("\U0001f916 Generando retos con IA..."):\n'
    '                try:\n'
    '                    _new_recs = get_content_recommendations(\n'
    '                        student_id=u["username"],\n'
    '                        db_connection=conn,\n'
    '                        limit=3,\n'
    '                        model=model,\n'
    '                    )\n'
    '                    st.session_state[_rkey] = _new_recs\n'
    '                except Exception as _ge:\n'
    '                    st.warning(f"\u26a0\ufe0f No se pudieron generar: {_ge}")\n'
)

new_gym = (
    '        _rkey = f"cached_recs_gym_{u[\'username\']}"\n'
    '        if _refresh_recs_gym:\n'
    '            # Limpiar cache anterior para forzar regeneracion\n'
    '            if _rkey in st.session_state:\n'
    '                del st.session_state[_rkey]\n'
    '            with st.spinner("\U0001f916 Generando retos personalizados con IA..."):\n'
    '                try:\n'
    '                    _new_recs = get_content_recommendations(\n'
    '                        student_id=u["username"],\n'
    '                        db_connection=conn,\n'
    '                        limit=3,\n'
    '                        model=model,\n'
    '                    )\n'
    '                    st.session_state[_rkey] = _new_recs\n'
    '                    st.rerun()\n'
    '                except Exception as _ge:\n'
    '                    st.warning(f"\u26a0\ufe0f No se pudieron generar: {_ge}")\n'
)

old_daily = (
    '        _total_attempts_d = conn.execute(\n'
    '            "SELECT COUNT(*) FROM daily_challenge_attempts WHERE user_id=?",\n'
    '            (user["username"],)\n'
    '        ).fetchone()[0]\n'
    '        _rkey = f"cached_recs_daily_{user[\'username\']}_{_total_attempts_d}"\n'
    '        if _refresh_recs_daily:\n'
    '            with st.spinner("\U0001f916 Generando retos con IA..."):\n'
    '                try:\n'
    '                    _new_recs = get_content_recommendations(\n'
    '                        student_id=user["username"],\n'
    '                        db_connection=conn,\n'
    '                        limit=3,\n'
    '                        model=model,\n'
    '                    )\n'
    '                    st.session_state[_rkey] = _new_recs\n'
    '                except Exception as _ge:\n'
    '                    st.warning(f"\u26a0\ufe0f No se pudieron generar: {_ge}")\n'
)

new_daily = (
    '        _rkey = f"cached_recs_daily_{user[\'username\']}"\n'
    '        if _refresh_recs_daily:\n'
    '            if _rkey in st.session_state:\n'
    '                del st.session_state[_rkey]\n'
    '            with st.spinner("\U0001f916 Generando retos personalizados con IA..."):\n'
    '                try:\n'
    '                    _new_recs = get_content_recommendations(\n'
    '                        student_id=user["username"],\n'
    '                        db_connection=conn,\n'
    '                        limit=3,\n'
    '                        model=model,\n'
    '                    )\n'
    '                    st.session_state[_rkey] = _new_recs\n'
    '                    st.rerun()\n'
    '                except Exception as _ge:\n'
    '                    st.warning(f"\u26a0\ufe0f No se pudieron generar: {_ge}")\n'
)

n1 = content.count(old_gym)
n2 = content.count(old_daily)
print(f'gym: {n1}, daily: {n2}')

content = content.replace(old_gym, new_gym)
content = content.replace(old_daily, new_daily)

with open('views_student.py', 'w', encoding='utf-8') as f:
    f.write(content)

import subprocess
r = subprocess.run(['python', '-m', 'py_compile', 'views_student.py'],
                   capture_output=True, text=True, encoding='utf-8')
print('Syntax:', 'OK' if r.returncode == 0 else r.stderr[:400])
