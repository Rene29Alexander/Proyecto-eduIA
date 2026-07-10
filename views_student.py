import streamlit as st
import json
import base64
import time
import re  # Necesario para limpiar el HTML roto
import html # Necesario para seguridad
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pandas as pd
from utils_ai import ai_evaluator, get_socratic_hint, display_pdf, ai_grade_open_question
from utils_notifications import notification_manager
from utils_recommendation import get_content_recommendations

# Importar sistema completo de curso IA
from ai_course_functions import (
    render_course_sections,
    render_course_progress,
    render_final_exam,
    render_course_settings
)

# ============================================================================
# FUNCIONES CACHEADAS PARA OPTIMIZAR RENDIMIENTO AL CAMBIAR DE PESTAÑA
# ============================================================================

@st.cache_data(ttl=60, show_spinner=False)  # Aumentado a 60 segundos para mejor rendimiento
def get_cached_ai_course(_conn, course_id):
    """Obtiene curso IA con caché de 60 segundos"""
    cursor = _conn.execute("""
        SELECT id, student_id, language, level, status, 
               progress_percentage, created_at, completed_at
        FROM ai_courses 
        WHERE id = ?
    """, (course_id,))
    row = cursor.fetchone()
    if row:
        return {
            'id': row[0], 'student_id': row[1], 'language': row[2],
            'level': row[3], 'status': row[4], 'progress_percentage': row[5],
            'created_at': row[6], 'completed_at': row[7]
        }
    return None

@st.cache_data(ttl=60, show_spinner=False)  # Aumentado a 60 segundos para mejor rendimiento
def get_cached_ai_sections(_conn, course_id):
    """Obtiene secciones del curso IA con caché de 60 segundos"""
    cursor = _conn.execute("""
        SELECT * FROM ai_course_topics 
        WHERE ai_course_id = ?
        ORDER BY topic_number
    """, (course_id,))
    # Devolver como lista de diccionarios para compatibilidad
    columns = [desc[0] for desc in cursor.description]
    sections = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # Verificar duplicados (debugging)
    topic_numbers = [s['topic_number'] for s in sections]
    if len(topic_numbers) != len(set(topic_numbers)):
        # Si hay duplicados, eliminarlos manteniendo el primero
        seen = set()
        unique_sections = []
        for section in sections:
            if section['topic_number'] not in seen:
                seen.add(section['topic_number'])
                unique_sections.append(section)
        return unique_sections
    
    return sections

# ============================================================================

def check_database_schema(conn):
    """Verifica y actualiza esquema de base de datos"""
    try:
        conn.execute("SELECT file_name FROM submissions LIMIT 1")
    except:
        try:
            conn.execute("ALTER TABLE submissions ADD COLUMN file_name TEXT")
            conn.commit()
        except:
            pass
    
    try:
        conn.execute("SELECT details_json FROM exam_attempts LIMIT 1")
    except:
        try:
            conn.execute("ALTER TABLE exam_attempts ADD COLUMN details_json TEXT")
            conn.commit()
        except:
            pass
    
    # Agregar campo de estado de visualización para cursos regulares
    try:
        conn.execute("SELECT display_status FROM enrollments LIMIT 1")
    except:
        try:
            conn.execute("ALTER TABLE enrollments ADD COLUMN display_status TEXT DEFAULT 'active'")
            conn.commit()
        except:
            pass
    
    # Agregar campo de estado de visualización para cursos IA
    try:
        conn.execute("SELECT display_status FROM ai_courses LIMIT 1")
    except:
        try:
            conn.execute("ALTER TABLE ai_courses ADD COLUMN display_status TEXT DEFAULT 'active'")
            conn.commit()
        except:
            pass

def clean_bad_html(text):
    """
    Función de limpieza profunda para el foro.
    Elimina etiquetas HTML basura (<div>) que se guardaron por error en la base de datos.
    """
    if not text:
        return ""
    text = str(text)
    
    # 1. Si el texto contiene divs anidados rotos (el error específico de tu imagen)
    # Intenta extraer solo el contenido dentro de los tags
    if "</div>" in text or "<div" in text:
        # Eliminar todas las etiquetas HTML usando Expresiones Regulares
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text.strip()
        
    return text

def render_avatar(avatar_bytes, size=50):
    """Renderiza avatar de usuario"""
    if avatar_bytes:
        b64 = base64.b64encode(avatar_bytes).decode()
        src = f"data:image/png;base64,{b64}"
    else:
        src = "https://cdn-icons-png.flaticon.com/512/847/847969.png"
    return f'<div style="display:flex; justify-content:center; margin-bottom:5px;"><img src="{src}" style="width:{size}px;height:{size}px;border-radius:50%;border:2px solid #58a6ff;object-fit:cover;"></div>'

def render_pending_tasks_panel(conn, user):
    """Renderiza panel lateral con tareas pendientes y valoraciones recientes"""
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #444;
        margin-top: 20px;
    ">
        <h3 style="color: #58a6ff; margin: 0 0 15px 0; font-size: 1.3em;">📋 Por hacer</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Tareas pendientes: solo las creadas en la última semana O cuya fecha de entrega aún no ha vencido
    pending_tasks = conn.execute("""
        SELECT t.id, t.title, t.description, t.due_date, t.points,
               c.name as course_name, c.code as course_code, c.id as course_id
        FROM tasks t
        JOIN courses c ON t.course_id = c.id
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ? 
        AND t.id NOT IN (
            SELECT task_id FROM submissions 
            WHERE student_id = ?
        )
        AND t.due_date >= date('now')
        AND (
            t.due_date >= date('now')
            OR t.created_at >= datetime('now', '-7 days')
        )
        ORDER BY t.due_date ASC
        LIMIT 10
    """, (user['username'], user['username'])).fetchall()
    
    # Exámenes pendientes: solo los de la última semana o que aún no vencen
    pending_exams = conn.execute("""
        SELECT ex.id, ex.title, ex.start_date, ex.end_date, ex.duration_minutes,
               c.name as course_name, c.code as course_code, c.id as course_id,
               ex.module_id
        FROM exams ex
        JOIN courses c ON ex.course_id = c.id
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ?
        AND ex.is_published = 1
        AND ex.id NOT IN (
            SELECT exam_id FROM exam_attempts 
            WHERE student_id = ? AND status IN ('completed', 'graded')
        )
        AND (ex.end_date IS NULL OR ex.end_date >= datetime('now'))
        ORDER BY ex.start_date ASC
        LIMIT 5
    """, (user['username'], user['username'])).fetchall()
    
    tasks = [dict(t) for t in pending_tasks]
    exams = [dict(e) for e in pending_exams]
    
    if not tasks and not exams:
        st.markdown("""
        <div style="background:rgba(16,185,129,0.1);padding:15px;border-radius:8px;border-left:4px solid #10b981;margin-top:10px;">
            <p style="color:#10b981;margin:0;font-size:0.95em;">✅ No tienes tareas pendientes</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Mostrar tareas con botón de ir al curso
        for task in tasks:
            try:
                due_date = datetime.strptime(task['due_date'], '%Y-%m-%d %H:%M:%S') if ' ' in (task['due_date'] or '') else datetime.strptime(task['due_date'], '%Y-%m-%d')
            except Exception:
                due_date = datetime.now() + timedelta(days=7)
            
            days_left = (due_date - datetime.now()).days
            border_color = "#ef4444" if days_left <= 1 else "#f59e0b" if days_left <= 3 else "#3b82f6"
            urgency_text = "¡Urgente!" if days_left <= 1 else "Próximo" if days_left <= 3 else ""
            
            st.markdown(f"""
            <div style="background:rgba(30,30,30,0.8);padding:12px;border-radius:8px;border-left:4px solid {border_color};margin-top:10px;">
                <div style="display:flex;align-items:center;margin-bottom:6px;">
                    <span style="font-size:1.1em;margin-right:6px;">📝</span>
                    <h4 style="color:#58a6ff;margin:0;font-size:0.95em;flex:1;">{task['title'][:40]}{'...' if len(task['title']) > 40 else ''}</h4>
                </div>
                <p style="color:#aaa;margin:3px 0;font-size:0.82em;">📚 {task['course_name']} | {task['course_code']}</p>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
                    <span style="color:#888;font-size:0.78em;">🎯 {task['points']} pts</span>
                    <span style="color:{border_color};font-size:0.78em;font-weight:bold;">📅 {due_date.strftime('%d/%m %H:%M')}</span>
                </div>
                {f'<div style="margin-top:6px;padding:3px 7px;background:{border_color};border-radius:4px;display:inline-block;"><span style="color:white;font-size:0.72em;font-weight:bold;">{urgency_text}</span></div>' if urgency_text else ''}
            </div>
            """, unsafe_allow_html=True)
            
            # Botón para ir al curso
            if st.button(f"→ Ir a la tarea", key=f"goto_task_{task['id']}", use_container_width=True):
                # Obtener datos del curso para navegar
                course_row = conn.execute("SELECT * FROM courses WHERE id = ?", (task['course_id'],)).fetchone()
                if course_row:
                    st.session_state.active_course = dict(course_row)
                    st.session_state.view_mode = 'course'
                    st.session_state.active_task_id = task['id']     # Para resaltar la tarea
                    st.session_state.active_tab_index = 1            # Tab "Tareas" (índice 1)
                    st.rerun()
        
        # Mostrar exámenes con botón de ir al curso
        for exam in exams:
            try:
                start_time = datetime.strptime(exam['start_date'], '%Y-%m-%d %H:%M:%S') if exam.get('start_date') else None
                days_left = (start_time - datetime.now()).days if start_time else 99
                date_label = start_time.strftime('%d/%m %H:%M') if start_time else "Sin fecha límite"
            except Exception:
                days_left = 99
                date_label = "Sin fecha límite"
            
            border_color = "#ef4444" if days_left <= 1 else "#f59e0b" if days_left <= 3 else "#8b5cf6"
            urgency_text = "¡Mañana!" if days_left <= 1 else "Esta semana" if days_left <= 3 else ""
            duration = exam.get('duration_minutes') or '?'
            
            st.markdown(f"""
            <div style="background:rgba(139,92,246,0.1);padding:12px;border-radius:8px;border-left:4px solid {border_color};margin-top:10px;">
                <div style="display:flex;align-items:center;margin-bottom:6px;">
                    <span style="font-size:1.1em;margin-right:6px;">✅</span>
                    <h4 style="color:#a78bfa;margin:0;font-size:0.95em;flex:1;">{exam['title'][:40]}{'...' if len(exam['title']) > 40 else ''}</h4>
                </div>
                <p style="color:#aaa;margin:3px 0;font-size:0.82em;">📚 {exam['course_name']} | {exam['course_code']}</p>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
                    <span style="color:#888;font-size:0.78em;">⏱️ {duration} min</span>
                    <span style="color:{border_color};font-size:0.78em;font-weight:bold;">📅 {date_label}</span>
                </div>
                {f'<div style="margin-top:6px;padding:3px 7px;background:{border_color};border-radius:4px;display:inline-block;"><span style="color:white;font-size:0.72em;font-weight:bold;">{urgency_text}</span></div>' if urgency_text else ''}
            </div>
            """, unsafe_allow_html=True)
            
            # Botón para ir al curso
            if st.button(f"→ Ir al examen", key=f"goto_exam_{exam['id']}", use_container_width=True):
                course_row = conn.execute("SELECT * FROM courses WHERE id = ?", (exam['course_id'],)).fetchone()
                if course_row:
                    st.session_state.active_course = dict(course_row)
                    st.session_state.view_mode = 'course'
                    st.rerun()
    
    # Sección de valoración reciente
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #444;
        margin-top: 20px;
    ">
        <h4 style="color: #58a6ff; margin: 0 0 10px 0; font-size: 1.1em;">⭐ Valoración reciente</h4>
    </div>
    """, unsafe_allow_html=True)
    
    # Obtener tareas calificadas en los últimos 7 días (exactamente, se quitan después)
    recent_graded = conn.execute("""
        SELECT s.id, s.final_grade as score, s.graded_date as graded_at, s.teacher_feedback as feedback,
               t.title as task_title, t.points as max_points,
               c.name as course_name, c.code as course_code
        FROM submissions s
        JOIN tasks t ON s.task_id = t.id
        JOIN courses c ON t.course_id = c.id
        WHERE s.student_id = ?
        AND s.graded_date IS NOT NULL
        AND s.graded_date >= datetime('now', '-7 days')
        ORDER BY s.graded_date DESC
        LIMIT 5
    """, (user['username'],)).fetchall()
    
    # Obtener exámenes calificados en los últimos 7 días (exactamente, se quitan después)
    recent_exams = conn.execute("""
        SELECT ea.id, ea.score, ea.end_time as completed_at,
               ex.title as exam_title, ea.max_score as max_points,
               c.name as course_name, c.code as course_code
        FROM exam_attempts ea
        JOIN exams ex ON ea.exam_id = ex.id
        JOIN courses c ON ex.course_id = c.id
        WHERE ea.student_id = ?
        AND ea.score IS NOT NULL
        AND ea.end_time IS NOT NULL
        AND ea.end_time >= datetime('now', '-7 days')
        ORDER BY ea.end_time DESC
        LIMIT 5
    """, (user['username'],)).fetchall()
    
    graded_tasks = [dict(g) for g in recent_graded]
    graded_exams = [dict(e) for e in recent_exams]
    
    if not graded_tasks and not graded_exams:
        st.markdown("""
        <div style="
            padding: 10px;
            margin-top: 10px;
        ">
            <p style="color: #888; margin: 0; font-size: 0.9em;">Nada por ahora</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Mostrar tareas calificadas
        for task in graded_tasks:
            score = task['score'] or 0
            max_points = task['max_points'] or 100
            percentage = (score / max_points * 100) if max_points > 0 else 0
            
            # Color según calificación
            if percentage >= 90:
                color = "#10b981"  # Verde
                emoji = "🌟"
            elif percentage >= 70:
                color = "#3b82f6"  # Azul
                emoji = "✅"
            elif percentage >= 60:
                color = "#f59e0b"  # Amarillo
                emoji = "⚠️"
            else:
                color = "#ef4444"  # Rojo
                emoji = "❌"
            
            # Parsear fecha de calificación
            try:
                graded_date = datetime.strptime(task['graded_at'], '%Y-%m-%d %H:%M:%S')
                date_str = graded_date.strftime('%d de %b')
            except:
                date_str = "Reciente"
            
            st.markdown(f"""
            <div style="
                background: rgba(30, 30, 30, 0.8);
                padding: 12px;
                border-radius: 8px;
                border-left: 4px solid {color};
                margin-top: 10px;
            ">
                <div style="display: flex; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 1.1em; margin-right: 8px;">{emoji}</span>
                    <h5 style="color: #58a6ff; margin: 0; font-size: 0.95em; flex: 1;">
                        {task['task_title'][:35]}{'...' if len(task['task_title']) > 35 else ''}
                    </h5>
                </div>
                <p style="color: #aaa; margin: 3px 0; font-size: 0.8em;">
                    📚 {task['course_name']}
                </p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                    <span style="color: {color}; font-size: 0.85em; font-weight: bold;">
                        {score:.1f}/{max_points} ({percentage:.0f}%)
                    </span>
                    <span style="color: #888; font-size: 0.75em;">
                        📅 {date_str}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Mostrar exámenes calificados
        for exam in graded_exams:
            score = exam['score'] or 0
            max_points = exam['max_points'] or 100
            percentage = (score / max_points * 100) if max_points > 0 else 0
            
            # Color según calificación
            if percentage >= 90:
                color = "#10b981"
                emoji = "🌟"
            elif percentage >= 70:
                color = "#3b82f6"
                emoji = "✅"
            elif percentage >= 60:
                color = "#f59e0b"
                emoji = "⚠️"
            else:
                color = "#ef4444"
                emoji = "❌"
            
            # Parsear fecha de finalización
            try:
                completed_date = datetime.strptime(exam['completed_at'], '%Y-%m-%d %H:%M:%S')
                date_str = completed_date.strftime('%d de %b')
            except:
                date_str = "Reciente"
            
            st.markdown(f"""
            <div style="
                background: rgba(139, 92, 246, 0.1);
                padding: 12px;
                border-radius: 8px;
                border-left: 4px solid {color};
                margin-top: 10px;
            ">
                <div style="display: flex; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 1.1em; margin-right: 8px;">{emoji}</span>
                    <h5 style="color: #a78bfa; margin: 0; font-size: 0.95em; flex: 1;">
                        {exam['exam_title'][:35]}{'...' if len(exam['exam_title']) > 35 else ''}
                    </h5>
                </div>
                <p style="color: #aaa; margin: 3px 0; font-size: 0.8em;">
                    📚 {exam['course_name']}
                </p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                    <span style="color: {color}; font-size: 0.85em; font-weight: bold;">
                        {score:.1f}/{max_points} ({percentage:.0f}%)
                    </span>
                    <span style="color: #888; font-size: 0.75em;">
                        📅 {date_str}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_hamburger_menu(conn, user):
    """Renderiza modal con todos los cursos cuando el botón está activo"""
    if not st.session_state.get('show_courses_modal', False):
        return

    # Obtener todos los cursos regulares
    all_regular_courses = conn.execute("""
        SELECT c.*, u.full_name as teacher_name, e.display_status
        FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        LEFT JOIN users u ON c.teacher_id = u.username
        WHERE e.student_id = ?
        ORDER BY c.name
    """, (user['username'],)).fetchall()

    # Obtener todos los cursos IA
    all_ai_courses = conn.execute("""
        SELECT id, language, level, status, progress_percentage, display_status
        FROM ai_courses
        WHERE student_id = ?
        ORDER BY language
    """, (user['username'],)).fetchall()

    regular_courses = [dict(r) for r in all_regular_courses]
    ai_courses = [dict(r) for r in all_ai_courses]

    # Agrupar por estado (usar 'display_status' para ambos tipos de cursos)
    active_regular = [c for c in regular_courses if c.get('display_status', 'active') == 'active']
    paused_regular = [c for c in regular_courses if c.get('display_status') == 'paused']
    completed_regular = [c for c in regular_courses if c.get('display_status') == 'completed']

    active_ai = [c for c in ai_courses if c.get('display_status', 'active') == 'active']
    paused_ai = [c for c in ai_courses if c.get('display_status') == 'paused']
    completed_ai = [c for c in ai_courses if c.get('display_status') == 'completed']

    # Modal con todos los cursos
    st.markdown("### 📚 Gestión de Cursos")

    if st.button("✖️ Cerrar", key="close_courses_modal"):
        st.session_state.show_courses_modal = False
        st.rerun()

    st.markdown("---")

    # Cursos Activos
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 15px;
        text-align: center;
    ">
        <h3 style="color: white; margin: 0;">🟢 Cursos Activos</h3>
    </div>
    """, unsafe_allow_html=True)

    if active_regular or active_ai:
        for course in active_regular:
            col1, col2, col3 = st.columns([4, 1, 2])
            with col1:
                st.markdown(f"**📖 {course['name']}**")
                st.caption(f"👨‍🏫 {course.get('teacher_name', 'Sin profesor')}")
            with col2:
                if st.button("👁️", key=f"view_reg_{course['id']}", help="Ver curso", use_container_width=True):
                    st.session_state.active_course = course
                    st.session_state.view_mode = 'course'
                    st.session_state.show_courses_modal = False
                    st.rerun()
            with col3:
                # Cursos regulares: solo mostrar estado (no editable por estudiantes)
                st.markdown(f"<div style='text-align: center; padding: 8px; background: #2a2a2a; border-radius: 5px;'>🟢 Activo</div>", unsafe_allow_html=True)
            st.markdown("---")

        for course in active_ai:
            col1, col2, col3 = st.columns([4, 1, 2])
            with col1:
                st.markdown(f"**🤖 {course['language']} - {course['level']}**")
                st.caption(f"📊 Progreso: {course.get('progress_percentage', 0):.0f}%")
            with col2:
                if st.button("👁️", key=f"view_ai_{course['id']}", help="Ver curso", use_container_width=True):
                    st.session_state.ai_course_id = course['id']
                    st.session_state.view_mode = 'ai_course'
                    st.session_state.show_courses_modal = False
                    st.rerun()
            with col3:
                # Cursos IA: estudiante puede cambiar estado
                new_status = st.selectbox("Estado", ["Activo", "Pausado", "Terminado"],
                                    key=f"status_ai_{course['id']}",
                                    label_visibility="collapsed")
                if new_status != "Activo":
                    status_map = {'Pausado': 'paused', 'Terminado': 'completed'}
                    conn.execute("UPDATE ai_courses SET display_status = ? WHERE id = ?",
                               (status_map[new_status], course['id']))
                    conn.commit()
                    st.rerun()
            st.markdown("---")
    else:
        st.info("No hay cursos activos")

    # Cursos Pausados
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        padding: 10px;
        border-radius: 8px;
        margin: 15px 0;
        text-align: center;
    ">
        <h3 style="color: white; margin: 0;">⏸️ Cursos Pausados</h3>
    </div>
    """, unsafe_allow_html=True)

    if paused_regular or paused_ai:
        for course in paused_regular:
            col1, col2, col3 = st.columns([4, 1, 2])
            with col1:
                st.markdown(f"**📖 {course['name']}**")
                st.caption(f"👨‍🏫 {course.get('teacher_name', 'Sin profesor')}")
            with col2:
                if st.button("👁️", key=f"view_paused_reg_{course['id']}", help="Ver curso", use_container_width=True):
                    st.session_state.active_course = course
                    st.session_state.view_mode = 'course'
                    st.session_state.show_courses_modal = False
                    st.rerun()
            with col3:
                # Cursos regulares: solo mostrar estado (no editable por estudiantes)
                st.markdown(f"<div style='text-align: center; padding: 8px; background: #2a2a2a; border-radius: 5px;'>⏸️ Pausado</div>", unsafe_allow_html=True)
            st.markdown("---")

        for course in paused_ai:
            col1, col2, col3 = st.columns([4, 1, 2])
            with col1:
                st.markdown(f"**🤖 {course['language']} - {course['level']}**")
                st.caption(f"📊 Progreso: {course.get('progress_percentage', 0):.0f}%")
            with col2:
                if st.button("👁️", key=f"view_paused_ai_{course['id']}", help="Ver curso", use_container_width=True):
                    st.session_state.ai_course_id = course['id']
                    st.session_state.view_mode = 'ai_course'
                    st.session_state.show_courses_modal = False
                    st.rerun()
            with col3:
                # Cursos IA: estudiante puede cambiar estado
                new_status = st.selectbox("Estado", ["Pausado", "Activo", "Terminado"],
                                    key=f"status_paused_ai_{course['id']}",
                                    label_visibility="collapsed")
                if new_status != "Pausado":
                    status_map = {'Activo': 'active', 'Terminado': 'completed'}
                    conn.execute("UPDATE ai_courses SET display_status = ? WHERE id = ?",
                               (status_map[new_status], course['id']))
                    conn.commit()
                    st.rerun()
            st.markdown("---")
    else:
        st.info("No hay cursos pausados")

    # Cursos Terminados
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 10px;
        border-radius: 8px;
        margin: 15px 0;
        text-align: center;
    ">
        <h3 style="color: white; margin: 0;">✅ Cursos Terminados</h3>
    </div>
    """, unsafe_allow_html=True)

    if completed_regular or completed_ai:
        for course in completed_regular:
            col1, col2, col3 = st.columns([4, 1, 2])
            with col1:
                st.markdown(f"**📖 {course['name']}**")
                st.caption(f"👨‍🏫 {course.get('teacher_name', 'Sin profesor')}")
            with col2:
                if st.button("👁️", key=f"view_completed_reg_{course['id']}", help="Ver curso", use_container_width=True):
                    st.session_state.active_course = course
                    st.session_state.view_mode = 'course'
                    st.session_state.show_courses_modal = False
                    st.rerun()
            with col3:
                # Cursos regulares: solo mostrar estado (no editable por estudiantes)
                st.markdown(f"<div style='text-align: center; padding: 8px; background: #2a2a2a; border-radius: 5px;'>✅ Terminado</div>", unsafe_allow_html=True)
            st.markdown("---")

        for course in completed_ai:
            col1, col2, col3 = st.columns([4, 1, 2])
            with col1:
                st.markdown(f"**🤖 {course['language']} - {course['level']}**")
                st.caption(f"📊 Progreso: {course.get('progress_percentage', 0):.0f}%")
            with col2:
                if st.button("👁️", key=f"view_completed_ai_{course['id']}", help="Ver curso", use_container_width=True):
                    st.session_state.active_ai_course = course['id']  # Usar active_ai_course en lugar de ai_course_id
                    st.session_state.view_mode = 'ai_course'
                    st.session_state.show_courses_modal = False
                    st.rerun()
            with col3:
                # Cursos IA: estudiante puede cambiar estado
                new_status = st.selectbox("Estado", ["Terminado", "Activo", "Pausado"],
                                    key=f"status_completed_ai_{course['id']}",
                                    label_visibility="collapsed")
                if new_status != "Terminado":
                    status_map = {'Activo': 'active', 'Pausado': 'paused'}
                    conn.execute("UPDATE ai_courses SET display_status = ? WHERE id = ?",
                               (status_map[new_status], course['id']))
                    conn.commit()
                    st.rerun()
            st.markdown("---")
    else:
        st.info("No hay cursos terminados")



def render_simple_notifications(conn, user):
    """Renderiza notificaciones de manera simple en la parte superior derecha"""
    unread_count = conn.execute("""
        SELECT COUNT(*) FROM notifications 
        WHERE user_id = ? AND is_read = 0
    """, (user['username'],)).fetchone()[0]
    
    with st.expander(f"🔔 Notificaciones ({unread_count})", expanded=False):
        notifications = conn.execute("""
            SELECT * FROM notifications 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (user['username'],)).fetchall()
        
        if notifications:
            if unread_count > 0:
                if st.button("✓ Marcar todas como leídas", key="mark_all_notif_simple", use_container_width=True):
                    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user['username'],))
                    conn.commit()
                    st.rerun()
            
            for idx, notif in enumerate(notifications):
                notif_dict = dict(notif)
                bg_color = "#2a2a2a" if not notif_dict['is_read'] else "#1a1a1a"
                
                # Iconos por tipo
                icon_map = {
                    'welcome': '🎉', 'feature': '⭐', 'assignment': '📝',
                    'exam': '✅', 'tip': '💡', 'achievement': '🏆',
                    'update': '🆕', 'info': '🔔', 'success': '✅', 'warning': '⚠️'
                }
                icon = icon_map.get(notif_dict.get('type', 'info'), '🔔')
                
                st.markdown(f"""
                <div style="
                    background: {bg_color};
                    padding: 10px;
                    border-radius: 8px;
                    margin-bottom: 8px;
                    border-left: 3px solid #58a6ff;
                ">
                    <div style="font-weight: bold; font-size: 0.9em; color: #fff;">
                        {icon} {notif_dict['title']}
                    </div>
                    <div style="font-size: 0.85em; color: #ccc; margin-top: 5px;">
                        {notif_dict['message']}
                    </div>
                    <div style="font-size: 0.75em; color: #888; margin-top: 5px;">
                        {notif_dict['created_at']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if not notif_dict['is_read']:
                    if st.button("Marcar como leída", key=f"read_notif_simple_{notif_dict['id']}_{idx}", use_container_width=True):
                        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_dict['id'],))
                        conn.commit()
                        st.rerun()
        else:
            st.info("No hay notificaciones")

# ==============================================================================
# MEJORAS IMPLEMENTADAS: SISTEMA DE ENTREGA MEJORADO PARA ESTUDIANTES
# ==============================================================================
def validate_exam_time(conn, exam_id, student_id):
    """Valida si un estudiante puede entregar un examen"""
    try:
        # Obtener datos del examen
        exam_row = conn.execute("""
            SELECT e.*, m.title as module_title
            FROM exams e 
            LEFT JOIN modules m ON e.module_id = m.id 
            WHERE e.id = ?
        """, (exam_id,)).fetchone()
        
        if not exam_row:
            return False, "❌ Examen no encontrado"
        
        exam = dict(exam_row)
        
        # Verificar si ya hay intento previo
        attempt_row = conn.execute("""
            SELECT score FROM exam_attempts 
            WHERE exam_id = ? AND student_id = ?
        """, (exam_id, student_id)).fetchone()
        
        if attempt_row:
            return False, "⚠️ Ya has realizado este examen"
        
        # Verificar si el examen está publicado
        if exam.get('is_published', 0) == 0:
            return False, "📭 Este examen no está disponible aún"
        
        return True, "✅ Puedes iniciar el examen"
        
    except Exception as e:
        return False, f"❌ Error de validación: {str(e)}"

def validate_task_submission(conn, task_id, student_id):
    """Valida si un estudiante puede entregar una tarea"""
    try:
        # Obtener datos de la tarea
        task_row = conn.execute("""
            SELECT t.*, m.title as module_title
            FROM tasks t 
            LEFT JOIN modules m ON t.module_id = m.id 
            WHERE t.id = ?
        """, (task_id,)).fetchone()
        
        if not task_row:
            return False, "❌ Tarea no encontrada"
        
        task = dict(task_row)
        
        # Verificar entregas previas
        submission_row = conn.execute("""
            SELECT * FROM submissions 
            WHERE task_id = ? AND student_id = ?
        """, (task_id, student_id)).fetchone()
        
        if submission_row:
            submission = dict(submission_row)
            if submission.get('status') == 'graded':
                return False, "✅ Ya calificado - No se pueden hacer más entregas"
            
            # Verificar intentos máximos
            max_attempts = task.get('max_attempts', 1)
            attempts_count = conn.execute("""
                SELECT COUNT(*) FROM submissions 
                WHERE task_id = ? AND student_id = ?
            """, (task_id, student_id)).fetchone()[0]
            
            if attempts_count >= max_attempts:
                return False, f"⛔ Límite de {max_attempts} intento(s) alcanzado"
        
        # Verificar fecha de entrega
        due_date = task.get('due_date')
        if due_date:
            if isinstance(due_date, str):
                try:
                    due_date = datetime.strptime(due_date, '%Y-%m-%d')
                except:
                    due_date = datetime.now()
            
            if datetime.now().date() > due_date.date():
                allow_late = task.get('allow_late_submissions', 1)
                if allow_late == 0:
                    return False, "⏰ Tiempo de entrega vencido - No se permiten entregas tardías"
        
        return True, "✅ Puedes entregar esta tarea"
        
    except Exception as e:
        return False, f"❌ Error de validación: {str(e)}"

def show_submission_progress(message="Enviando..."):
    """Muestra indicador de progreso para envíos"""
    progress_container = st.empty()
    progress_container.info(f"⏳ {message}")
    return progress_container

def show_time_expired_message():
    """Muestra mensaje cuando el tiempo ha vencido"""
    st.markdown("""
    <div style="
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    ">
        <h4 style="margin:0; color:#c62828;">⏰ Tiempo de entrega agotado</h4>
        <p style="margin:8px 0 0 0; color:#555;">
            El plazo para enviar esta actividad ha finalizado. 
            Si crees que esto es un error, contacta a tu docente.
        </p>
    </div>
    """, unsafe_allow_html=True)

def show_submission_success(message="¡Entrega exitosa!"):
    """Muestra mensaje de envío exitoso"""
    st.balloons()
    st.success(f"✅ {message}")

def show_submission_error(message="Error al enviar"):
    """Muestra mensaje de error en envío"""
    st.error(f"❌ {message}")

def render_exam_interface(conn, es, u, c, model):
    """Renderiza la interfaz del examen activo"""
    # Obtener información del examen
    exam_info = conn.execute("SELECT title FROM exams WHERE id = ?", (es['id'],)).fetchone()
    exam_title = exam_info[0] if exam_info else "Examen"
    
    # Header minimalista del examen
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        text-align: center;
        border: 2px solid #444;
    ">
        <h2 style="margin: 0; color: #58a6ff;">📝 {exam_title}</h2>
        <p style="margin: 5px 0 0 0; color: #aaa; font-size: 0.9em;">
            ⚠️ Modo Examen Activo - No cierres esta ventana ni recargues la página
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    now = datetime.now()
    end_time = es['start'] + timedelta(minutes=es['dur'])
    seconds_left = max(0, int((end_time - now).total_seconds()))
    
    # Función para finalizar examen
    def finish_exam():
        st.session_state.exam_finishing = True
        progress_bar = show_submission_progress("Enviando examen...")
        
        try:
            qs_final_rows = conn.execute(
                "SELECT * FROM exam_questions WHERE exam_id = ?",
                (es['id'],)
            ).fetchall()
            qs_final = [dict(r) for r in qs_final_rows]
            
            total_score = 0
            details_list = []
            
            progress_bar.progress(0.3, text="📊 Procesando respuestas...")
            
            # Calificar solo preguntas de opción múltiple automáticamente
            for idx, q in enumerate(qs_final):
                key_name = f"ans_{es['id']}_{q['id']}"
                student_ans = st.session_state.get(key_name, None)
                qtype = q.get('question_type', 'multiple_choice')
                
                if qtype == 'multiple_choice':
                    earned = 0
                    feedback = "Respuesta incorrecta"
                    try:
                        opts = json.loads(q['options_json'])
                        if student_ans and opts.index(student_ans) == q['correct_index']:
                            earned = q['points']
                            feedback = "¡Correcto!"
                    except:
                        pass
                    total_score += earned
                    details_list.append({
                        "q_id": q['id'],
                        "question": q['question'],
                        "type": "multiple_choice",
                        "answer": student_ans,
                        "score": earned,
                        "max_points": q['points'],
                        "ai_feedback": feedback,
                        "graded": True
                    })
                elif qtype == 'open_text':
                    # Guardar respuesta sin calificar (pendiente para el docente)
                    details_list.append({
                        "q_id": q['id'],
                        "question": q['question'],
                        "type": "open_text",
                        "answer": student_ans if student_ans else "Sin respuesta",
                        "score": 0,  # Pendiente de calificación
                        "max_points": q['points'],
                        "ai_feedback": "Pendiente de calificación por el docente",
                        "graded": False  # Marca como no calificada
                    })
            
            progress_bar.progress(0.8, text="💾 Guardando resultados...")
            
            json_details = json.dumps(details_list)
            conn.execute("""
                INSERT INTO exam_attempts 
                (exam_id, student_id, score, start_time, end_time, details_json) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (es['id'], u['username'], total_score, es['start'], datetime.now(), json_details))
            conn.commit()
            
            del st.session_state.exam_session
            if 'exam_finishing' in st.session_state:
                del st.session_state.exam_finishing
            if 'show_exam_only' in st.session_state:
                del st.session_state.show_exam_only
            
            # Contar preguntas pendientes de calificación
            pending_count = sum(1 for d in details_list if not d.get('graded', True))
            
            show_submission_success("¡Examen Enviado!")
            
            if pending_count > 0:
                st.info(f"📝 {pending_count} pregunta(s) de texto abierto pendiente(s) de calificación por el docente")
                st.markdown(f"### 📊 Puntuación Parcial: **{total_score}** puntos")
                st.caption("La calificación final se actualizará cuando el docente revise las preguntas de texto abierto")
            else:
                st.markdown(f"### 📊 Puntuación Final: **{total_score}** puntos")
            
            st.session_state.exam_results = {
                'score': total_score,
                'details': details_list,
                'exam_title': exam_title,
                'show_details': False,
                'has_pending': pending_count > 0
            }
            
            st.rerun()
            
        except Exception as e:
            progress_bar.empty()
            show_submission_error(f"Error al enviar examen: {str(e)}")
            time.sleep(3)
            st.rerun()
    
    # Temporizador
    if seconds_left <= 0:
        st.error("⏰ ¡TIEMPO AGOTADO! Enviando respuestas...")
        finish_exam()
        st.stop()
    
    minutes = seconds_left // 60
    seconds = seconds_left % 60
    timer_color = "#ff4b4b" if minutes < 5 else "#f0ad4e" if minutes < 15 else "#5cb85c"
    
    st.markdown(f"""
    <div style="
        font-family: 'Courier New', monospace;
        color: {timer_color};
        text-align: center;
        font-size: 28px;
        font-weight: bold;
        border: 3px solid #444;
        border-radius: 15px;
        padding: 20px;
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        margin-bottom: 20px;
    ">
        ⏱️ TIEMPO RESTANTE: {minutes:02d}:{seconds:02d}
    </div>
    """, unsafe_allow_html=True)
    
    # Preguntas del examen
    qs_rows = conn.execute(
        "SELECT * FROM exam_questions WHERE exam_id = ?",
        (es['id'],)
    ).fetchall()
    qs = [dict(r) for r in qs_rows]
    
    # Aleatorizar preguntas
    import random
    import hashlib
    seed_string = f"{es['id']}_{u['username']}"
    seed_value = int(hashlib.md5(seed_string.encode()).hexdigest(), 16) % (10 ** 8)
    random.seed(seed_value)
    random.shuffle(qs)
    
    for q in qs:
        if q.get('question_type') == 'multiple_choice':
            try:
                opts = json.loads(q['options_json'])
                correct_idx = q.get('correct_index', 0)
                indices = list(range(len(opts)))
                random.shuffle(indices)
                new_opts = [opts[i] for i in indices]
                new_correct_idx = indices.index(correct_idx)
                q['options_json'] = json.dumps(new_opts)
                q['correct_index'] = new_correct_idx
            except:
                pass
    
    random.seed()
    
    answered_count = sum(1 for q in qs if st.session_state.get(f"ans_{es['id']}_{q['id']}"))
    
    st.markdown(f"""
    <div style="
        background: #2a2a2a;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 15px;
        text-align: center;
    ">
        📝 <strong>{len(qs)} Preguntas</strong> | 
        ✅ <strong>{answered_count} Respondidas</strong> | 
        ⏳ <strong>{len(qs) - answered_count} Pendientes</strong>
    </div>
    """, unsafe_allow_html=True)
    
    for i, q in enumerate(qs):
        is_answered = bool(st.session_state.get(f"ans_{es['id']}_{q['id']}"))
        status_icon = "✅" if is_answered else "⏳"
        
        with st.container(border=True):
            st.markdown(f"#### {status_icon} Pregunta {i+1} de {len(qs)} **({q['points']} puntos)**")
            st.markdown(f"**{q['question']}**")
            
            qtype = q.get('question_type', 'multiple_choice')
            
            if qtype == 'open_text':
                st.text_area("✍️ Tu respuesta:", 
                           key=f"ans_{es['id']}_{q['id']}",
                           height=150,
                           placeholder="Escribe tu respuesta aquí de forma clara y completa...")
            else:
                try:
                    opts = json.loads(q['options_json'])
                    st.radio("Selecciona la opción correcta:",
                           opts,
                           key=f"ans_{es['id']}_{q['id']}",
                           index=None)
                except:
                    st.error("Error cargando opciones de la pregunta")
    
    st.markdown("---")
    
    col_submit, col_progress, col_emergency = st.columns([2, 1, 1])
    
    with col_submit:
        if st.button("✅ Terminar y Enviar Examen", 
                   type="primary", 
                   use_container_width=True):
            finish_exam()
    
    with col_progress:
        progress_percentage = (answered_count / len(qs)) * 100 if len(qs) > 0 else 0
        st.metric("Progreso", f"{progress_percentage:.0f}%")
    
    with col_emergency:
        if st.button("🚨 Salir (Emergencia)", 
                   type="secondary", 
                   use_container_width=True):
            if st.session_state.get('confirm_exit_exam'):
                del st.session_state.exam_session
                if 'confirm_exit_exam' in st.session_state:
                    del st.session_state.confirm_exit_exam
                if 'show_exam_only' in st.session_state:
                    del st.session_state.show_exam_only
                st.warning("⚠️ Has salido del examen. El progreso se ha perdido.")
                time.sleep(2)
                st.rerun()
            else:
                st.session_state.confirm_exit_exam = True
                st.error("⚠️ Haz clic nuevamente para confirmar que quieres salir del examen")

def view_student(conn, model):
    """Vista principal del estudiante"""
    check_database_schema(conn)
    u = st.session_state.user
    
    # ============================================================================
    # ENGAGEMENT SIDEBAR - Mostrar en todas las vistas
    # ============================================================================
    try:
        from engagement import (
            StreakManager, PointsManager, ChallengeManager,
            NotificationManager, LeaderboardManager, DailyQuestionManager
        )
        
        # Sidebar de engagement
        st.sidebar.markdown("---")
        st.sidebar.subheader("🎮 Tu Progreso")
        
        # Racha
        streak_info = StreakManager.get_streak_info(u['username'])
        if streak_info['is_at_risk'] and streak_info['current_streak'] > 0:
            st.sidebar.warning(f"⚠️ Racha en riesgo: {streak_info['current_streak']} días")
        else:
            st.sidebar.success(f"🔥 Racha: {streak_info['current_streak']} días")

        # Top 3 rachas
        try:
            top_streaks = StreakManager.get_top_streaks(3)
            if top_streaks:
                medals = ["🥇", "🥈", "🥉"]
                top_lines = []
                for i, entry in enumerate(top_streaks):
                    medal = medals[i] if i < len(medals) else f"{i+1}."
                    name = entry['display_name']
                    # Truncar nombre largo
                    name_short = name[:18] + "…" if len(name) > 18 else name
                    is_me = entry['user_id'] == u['username']
                    days = entry['current_streak']
                    marker = " ◀" if is_me else ""
                    top_lines.append(f"{medal} **{name_short}** — {days}d{marker}")
                st.sidebar.markdown("**🏅 Top Rachas:**")
                for line in top_lines:
                    st.sidebar.markdown(line)
        except Exception:
            pass
        
        # Pregunta diaria - Widget compacto
        has_answered = DailyQuestionManager.has_answered_today(u['username'])
        if not has_answered and streak_info['current_streak'] > 0:
            st.sidebar.error("❗ Responde la pregunta diaria para mantener tu racha")
            if st.sidebar.button("📝 Responder Pregunta", use_container_width=True, type="primary"):
                st.session_state.current_page = 'daily_question'
                st.rerun()
        elif not has_answered:
            if st.sidebar.button("📝 Pregunta del Día", use_container_width=True):
                st.session_state.current_page = 'daily_question'
                st.rerun()
        else:
            st.sidebar.success("✅ Pregunta diaria completada")
        
        # Nivel y Puntos
        points_info = PointsManager.get_user_points_info(u['username'])
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("⭐ Nivel", points_info['level'])
        with col2:
            coins_data = PointsManager.get_user_coins(u['username'])
            st.metric("💰 Monedas", coins_data['total_coins'])
        
        st.sidebar.progress(points_info['progress_percentage'] / 100)
        st.sidebar.caption(f"{points_info['experience_points']}/{points_info['points_to_next_level']} XP")
        
        # Ranking
        rank = LeaderboardManager.get_user_rank(u['username'], 'weekly')
        st.sidebar.metric("🏆 Ranking Semanal", f"#{rank}")
        
        # Botón de Tienda
        coins_data = PointsManager.get_user_coins(u['username'])
        if st.sidebar.button(f"🛒 Tienda ({coins_data['total_coins']} 🪙)", use_container_width=True):
            st.session_state.current_page = 'shop'
            st.rerun()
        
        # Desafío del día
        challenge = ChallengeManager.get_today_challenge('Python')
        if challenge:
            status = ChallengeManager.get_user_challenge_status(challenge['id'], u['username'])
            if status['completed']:
                st.sidebar.success("✅ Desafío completado")
            else:
                if st.sidebar.button("💪 Ver Desafío del Día"):
                    st.session_state.current_page = 'daily_challenge'
                    st.rerun()
        
        # Notificaciones de engagement
        notifs = NotificationManager.get_unread_notifications(u['username'], 3)
        if notifs:
            with st.sidebar.expander(f"🔔 Notificaciones ({len(notifs)})"):
                for notif in notifs:
                    st.write(f"**{notif['title']}**")
                    st.caption(notif['message'])
                    if st.button("✓", key=f"notif_{notif['id']}"):
                        NotificationManager.mark_as_read(notif['id'])
                        st.rerun()
    except Exception as e:
        # Si hay error en engagement, no romper la app
        print(f"Error en engagement sidebar: {e}")
    
    # ============================================================================
    
    # Función helper para notificaciones contextuales
    def create_usage_notification(feature_name, feature_description):
        """Crea notificación cuando el usuario usa una función por primera vez"""
        # Verificar si ya se notificó sobre esta función
        existing = conn.execute("""
            SELECT id FROM notifications 
            WHERE user_id = ? AND title LIKE ? AND type = 'feature'
        """, (u['username'], f"%{feature_name}%")).fetchone()
        
        if not existing:
            notification_manager.create_notification(
                user_id=u['username'],
                title=f"🎉 Usaste: {feature_name}",
                message=f"¡Excelente! {feature_description} Revisa tus notificaciones para más consejos.",
                notification_type='success'
            )
    
    # ==============================================================================
    # VISTAS DE CURSO (PRIORIDAD ALTA)
    # ==============================================================================
    
    # Vista de curso IA
    if st.session_state.view_mode == 'ai_course':
        render_ai_course_simple(conn, u, model)
        return
    
    # Vista de configuración de curso IA
    if st.session_state.view_mode == 'ai_course_config':
        render_ai_course_config_only(conn, u, model)
        return
    
    # Vista de perfil de usuario
    if st.session_state.view_mode == 'profile':
        render_user_profile(conn, u)
        return
    
    # ==============================================================================
    # PÁGINAS AUXILIARES
    # ==============================================================================
    if st.session_state.current_page == 'chat':
        # Vista de chat privado (solo cuenta completa)
        if u.get('account_type') == 'free':
            st.warning("💬 El chat privado no está disponible en cuentas gratuitas.")
            st.session_state.current_page = 'dashboard'
            st.rerun()
        render_chat_interface(conn, u['username'], u['role'])
        return
    
    # Página de Desafío Diario
    if st.session_state.current_page == 'daily_challenge':
        render_daily_challenge_page(conn, u, model)
        return
    
    # Página de Pregunta Diaria
    if st.session_state.current_page == 'daily_question':
        render_daily_question_page(conn, u)
        return
    
    # Página de Tienda
    if st.session_state.current_page == 'shop':
        render_shop_page(conn, u)
        return
    
    if st.session_state.current_page == 'tutor':
        # Notificación de uso del tutor IA
        create_usage_notification(
            "Tutor Inteligente IA", 
            "Has accedido al tutor IA que puede evaluar código, ayudar con errores y generar soluciones."
        )
        
        st.title("🤖 Tutor Inteligente IA")
        st.markdown("### Tu profesor personal de programación con IA de Gemini")
        
        # Tabs para diferentes funciones del tutor
        tab1, tab2, tab3 = st.tabs(["📝 Evaluación Directa", "💡 Ayuda con Errores", "✅ Solicitar Solución"])
        
        with tab1:
            st.markdown("#### Evalúa tu código directamente con la IA")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                lang = st.selectbox("Lenguaje de Programación", 
                                  ["Python", "Java", "C++", "JavaScript", "SQL", "NoSQL", "HTML/CSS"],
                                  key="eval_lang")
                
                st.info("""
                ### 🎯 Evaluación Directa
                La IA evaluará tu código como un profesor real:
                - ✅ Puntuación del 1-10
                - 📝 Retroalimentación detallada
                - 🔍 Detección de errores
                - 💡 Sugerencias de mejora
                """)
            
            with col2:
                exercise_context = st.text_area("📋 Contexto del Ejercicio", 
                                              height=120,
                                              placeholder="Describe el problema que estás resolviendo...\nEjemplo: 'Crear una función que calcule el factorial de un número'",
                                              help="Proporciona el contexto del ejercicio para una evaluación precisa",
                                              key="eval_context")
                
                student_code = st.text_area("💻 Tu Código", 
                                          height=200,
                                          placeholder="Pega aquí tu código...",
                                          help="El código que quieres que evalúe la IA",
                                          key="eval_code")
                
                col_buttons = st.columns(2)
                with col_buttons[0]:
                    if st.button("🎯 Evaluar Código", type="primary", use_container_width=True):
                        if student_code.strip() and exercise_context.strip():
                            # Notificación de uso de evaluación
                            notification_manager.create_notification(
                                user_id=u['username'],
                                title="🎯 Código Evaluado",
                                message=f"Has usado el evaluador IA para {lang}. ¡Excelente forma de mejorar tu código!",
                                notification_type='success'
                            )
                            
                            # Verificar logros
                            from utils_notifications import check_and_create_achievements
                            check_and_create_achievements(u['username'])
                            
                            with st.spinner("🤖 La IA está evaluando tu código..."):
                                # Usar la IA directamente para evaluación
                                prompt = f"""
                                Eres un profesor experto en {lang}. DEBES analizar este código con MÁXIMO DETALLE.

                                EJERCICIO/CONTEXTO:
                                {exercise_context}

                                CÓDIGO DEL ESTUDIANTE:
                                {student_code}

                                INSTRUCCIONES OBLIGATORIAS PARA {lang}:
                                1. Examina CADA LÍNEA del código individualmente
                                2. Identifica TODOS los errores sin excepción (sintaxis, lógica, tipos)
                                3. Verifica que los métodos existan para los tipos de datos usados
                                4. Comprueba acceso correcto a estructuras de datos
                                5. Lista TODOS los aspectos positivos
                                6. Explica si cada línea funciona o no
                                7. Proporciona correcciones específicas
                                8. Evalúa si cumple el objetivo del ejercicio

                                ERRORES CRÍTICOS A BUSCAR EN {lang}:
                                - Métodos que no existen para el tipo de dato (ej: .remove() en dict)
                                - Funciones con argumentos incorrectos (ej: range() con dict)
                                - Acceso incorrecto a elementos (ej: string[0] cuando es clave)
                                - Tipos inconsistentes (ej: pasar int cuando espera string)
                                - Variables o elementos que no existen

                                FORMATO OBLIGATORIO (NO OMITAS NINGUNA SECCIÓN):

                                ## 📊 Puntuación: X/10

                                ## 🔍 Análisis Línea por Línea:
                                Línea 1: [código] - [análisis específico - funciona/error y por qué]
                                Línea 2: [código] - [análisis específico - funciona/error y por qué]
                                [Continúa con TODAS las líneas importantes]

                                ## ✅ Aspectos Correctos Identificados:
                                - [Lista CADA cosa que está bien]
                                - [Menciona sintaxis correcta]
                                - [Reconoce lógica válida]
                                - [Identifica buenas prácticas]

                                ## ❌ Errores Específicos Detectados:
                                - Error 1: [ubicación exacta] - [descripción detallada] - [por qué es error en {lang}]
                                - Error 2: [ubicación exacta] - [descripción detallada] - [por qué es error en {lang}]
                                [Lista TODOS los errores encontrados - NO OMITAS NINGUNO]

                                ## � Correcciones Específicas:
                                - Para error 1: [corrección exacta en {lang}]
                                - Para error 2: [corrección exacta en {lang}]
                                [Corrección para cada error]

                                ## 🎯 ¿Funciona el Código?:
                                [Respuesta clara: SÍ/NO y por qué específicamente]

                                ## 💡 Recomendaciones Específicas:
                                - [Mejora específica 1 para {lang}]
                                - [Mejora específica 2 para {lang}]

                                REGLAS CRÍTICAS PARA {lang}:
                                - Si el código NO PUEDE EJECUTARSE por errores de sintaxis/métodos: máximo 4/10
                                - Si funciona perfectamente sin errores: 10/10
                                - Si funciona con errores menores: 7-9/10
                                - SÉ ESPECÍFICO en cada punto
                                - NO OMITAS ningún error o aspecto positivo
                                - DETECTA todos los errores de tipos de datos y métodos
                                """
                                
                                try:
                                    # Usar el sistema de evaluación mejorado integrado
                                    from utils_ai import AIManager
                                    ai_manager = AIManager()
                                    
                                    # Usar el evaluador integrado que detecta errores específicos
                                    score, feedback, correctness, suggestions, concepts = ai_manager.evaluate_code(
                                        student_code, exercise_context, lang
                                    )
                                    
                                    # Mostrar puntuación
                                    st.success("### 📊 Evaluación de la IA")
                                    
                                    # Puntuación
                                    col_score = st.columns([1, 3])
                                    with col_score[0]:
                                        st.metric("Puntuación", f"{score}/10")
                                    
                                    # Análisis detallado
                                    with st.expander("🔍 Análisis Detallado", expanded=True):
                                        if feedback and feedback.strip():
                                            st.markdown(feedback)
                                        else:
                                            st.info("La IA está procesando tu código...")
                                    
                                    # Sugerencias de mejora
                                    if suggestions and len(suggestions) > 0:
                                        with st.expander("💡 Sugerencias de Mejora", expanded=True):
                                            for suggestion in suggestions:
                                                st.info(f"• {suggestion}")
                                    
                                    # Conceptos relevantes
                                    if concepts and len(concepts) > 0:
                                        with st.expander("📚 Conceptos Relevantes"):
                                            st.write(", ".join(concepts))
                                    
                                    # Estado del código
                                    st.markdown("---")
                                    if correctness == "correcto":
                                        st.success(f"🎯 **Estado:** CORRECTO - Tu código funciona correctamente. ¡Excelente trabajo!")
                                    elif correctness == "parcial":
                                        st.warning(f"🎯 **Estado:** PARCIAL - Tu código tiene algunos aspectos que mejorar.")
                                    else:
                                        st.error(f"🎯 **Estado:** INCORRECTO - Tu código necesita correcciones importantes.")
                                    
                                    st.caption(f"*Evaluación realizada con el sistema de detección avanzada que analiza errores de sintaxis, lógica y tipos de datos específicos para {lang}.*")
                                    
                                except Exception as e:
                                    # Fallback al método anterior si hay problemas
                                    st.error(f"Error en evaluación avanzada: {str(e)}")
                                    try:
                                        response = model.generate_content(prompt)
                                        st.success("### � Evaluación de la IA")
                                        st.markdown(response.text)
                                    except Exception as e2:
                                        st.error(f"Error al evaluar: {str(e2)}")
                        else:
                            st.warning("Por favor, proporciona tanto el contexto del ejercicio como tu código.")
                
                with col_buttons[1]:
                    if st.button("🔄 Limpiar", use_container_width=True):
                        st.rerun()
        
        with tab2:
            st.markdown("#### Obtén pistas para resolver errores por ti mismo")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                lang_help = st.selectbox("Lenguaje", 
                                       ["Python", "Java", "C++", "JavaScript", "SQL", "NoSQL", "HTML/CSS"],
                                       key="help_lang")
                
                st.info("""
                ### 💡 Ayuda con Pistas
                La IA te ayudará a:
                - Identificar errores
                - Darte pistas (no soluciones)
                - Sugerir qué estudiar
                - Hacerte preguntas guía
                
                **No te dará la respuesta directa**, 
                te ayudará a descubrirla por ti mismo.
                """)
            
            with col2:
                problem_context_help = st.text_area("📋 ¿Qué estás intentando hacer? (opcional)", 
                                                 height=80,
                                                 placeholder="Ejemplo: 'Estoy tratando de calcular el promedio de una lista de números'",
                                                 key="help_problem")
                
                code_with_error = st.text_area("💻 Tu código con errores", 
                                             height=200,
                                             placeholder="Pega aquí tu código que tiene errores...",
                                             key="help_code")
                
                if st.button("💡 Obtener Pistas", type="primary", use_container_width=True):
                    if code_with_error.strip():
                        # Notificación de uso
                        notification_manager.create_notification(
                            user_id=u['username'],
                            title="💡 Pistas Solicitadas",
                            message=f"Has pedido pistas para tu código en {lang_help}. ¡Excelente forma de aprender!",
                            notification_type='info'
                        )
                        
                        with st.spinner("🤔 La IA está analizando tu código y preparando pistas..."):
                            try:
                                from utils_ai import analyze_code_with_hints, AIManager
                                ai_manager = AIManager()
                                
                                # Analizar código y obtener pistas
                                result = analyze_code_with_hints(
                                    ai_manager.model,
                                    code_with_error,
                                    lang_help,
                                    problem_context_help if problem_context_help.strip() else None
                                )
                                
                                st.success("### 💡 Análisis y Pistas del Tutor IA")
                                
                                # Mostrar si hay errores o no
                                if result['has_errors']:
                                    st.warning("🔍 **He encontrado algunos aspectos que puedes revisar**")
                                else:
                                    st.success("✅ **¡Tu código se ve bien!** No he detectado errores obvios.")
                                
                                # Errores encontrados
                                if result['errors_found']:
                                    with st.expander("❌ Errores Detectados", expanded=True):
                                        for i, error in enumerate(result['errors_found'], 1):
                                            st.error(f"**Error {i}:**")
                                            st.write(f"📍 **Ubicación:** Línea {error['line']}")
                                            st.write(f"🏷️ **Tipo:** {error['error_type']}")
                                            st.write(f"📝 **Descripción:** {error['description']}")
                                            st.markdown("---")
                                
                                # Pistas para resolver
                                if result['hints']:
                                    with st.expander("💡 Pistas para Resolver", expanded=True):
                                        st.info("**Recuerda:** Estas son pistas, no soluciones. Piensa en cada una antes de hacer cambios.")
                                        for i, hint in enumerate(result['hints'], 1):
                                            st.markdown(f"### Pista {i}")
                                            st.write(f"**Para:** {hint['for_error']}")
                                            st.write(f"💭 **Pista:** {hint['hint']}")
                                            st.write(f"❓ **Pregunta guía:** {hint['guiding_question']}")
                                            st.markdown("---")
                                
                                # Áreas de estudio
                                if result['areas_to_study']:
                                    with st.expander("📚 Áreas que Deberías Repasar"):
                                        for i, area in enumerate(result['areas_to_study'], 1):
                                            st.markdown(f"### {i}. {area['topic']}")
                                            st.write(f"**Por qué:** {area['reason']}")
                                            st.write(f"**Qué estudiar:** {area['resources']}")
                                            st.markdown("---")
                                
                                # Mensaje motivacional
                                st.success(f"🌟 **{result['encouragement']}**")
                                
                                st.markdown("---")
                                st.caption("💡 **Consejo:** Usa estas pistas para intentar corregir tu código por ti mismo. ¡Aprender haciendo es la mejor forma!")
                                
                            except Exception as e:
                                st.error(f"Error al analizar el código: {str(e)}")
                                st.info("Por favor, verifica que tu código esté completo e intenta nuevamente.")
                    else:
                        st.warning("Por favor, pega tu código para que pueda analizarlo y darte pistas.")
        
        with tab3:
            st.markdown("#### Solicita el código corregido con explicación de cambios")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                lang_solution = st.selectbox("Lenguaje", 
                                           ["Python", "Java", "C++", "JavaScript", "SQL", "NoSQL", "HTML/CSS"],
                                           key="solution_lang")
                
                st.warning("""
                ### ⚠️ Uso Responsable
                - Úsalo solo después de intentar
                - Lee CADA cambio explicado
                - Entiende POR QUÉ se hizo
                - Practica el concepto después
                """)
                
                st.info("""
                ### ✅ Obtendrás:
                - 💻 Código corregido funcional
                - 🔄 Lista de cambios realizados
                - 📝 Explicación de cada cambio
                - 🎯 Conceptos clave aprendidos
                - � Tips adicionales
                """)
            
            with col2:
                problem_context_solution = st.text_area("📋 ¿Qué estás intentando hacer? (opcional)", 
                                                  height=80,
                                                  placeholder="Ejemplo: 'Crear un programa que calcule el factorial de un número'",
                                                  key="solution_context")
                
                code_to_correct = st.text_area("� Tu código con errores", 
                                          height=200,
                                          placeholder="Pega aquí tu código que necesita corrección...",
                                          key="solution_code")
                
                if st.button("✅ Obtener Código Corregido", type="primary", use_container_width=True):
                    if code_to_correct.strip():
                        # Notificación de uso
                        notification_manager.create_notification(
                            user_id=u['username'],
                            title="✅ Solución Solicitada",
                            message=f"Has solicitado el código corregido en {lang_solution}. ¡Estudia cada cambio!",
                            notification_type='success'
                        )
                        
                        with st.spinner("🧠 La IA está corrigiendo tu código y preparando explicaciones..."):
                            try:
                                from utils_ai import provide_corrected_code_with_explanation, AIManager
                                ai_manager = AIManager()
                                
                                # Obtener código corregido con explicaciones
                                result = provide_corrected_code_with_explanation(
                                    ai_manager.model,
                                    code_to_correct,
                                    lang_solution,
                                    problem_context_solution if problem_context_solution.strip() else None
                                )
                                
                                st.success("### ✅ Código Corregido con Explicaciones")
                                
                                # Código corregido
                                with st.expander("💻 Código Corregido Completo", expanded=True):
                                    st.code(result['corrected_code'], language=lang_solution.lower())
                                    st.caption("💡 Copia este código, ejecútalo y compáralo con tu versión original.")
                                
                                # Cambios realizados
                                if result['changes_made']:
                                    with st.expander("� Cambios Realizados (Lee Cada Uno)", expanded=True):
                                        st.info("**Importante:** Cada cambio está explicado para que entiendas POR QUÉ era necesario.")
                                        
                                        for change in result['changes_made']:
                                            st.markdown(f"### Cambio #{change['change_number']}")
                                            
                                            col_before, col_after = st.columns(2)
                                            with col_before:
                                                st.markdown("**❌ Antes (Incorrecto):**")
                                                st.code(change['original'], language=lang_solution.lower())
                                            
                                            with col_after:
                                                st.markdown("**✅ Después (Corregido):**")
                                                st.code(change['corrected'], language=lang_solution.lower())
                                            
                                            st.markdown(f"**📝 Por qué se hizo este cambio:**")
                                            st.write(change['reason'])
                                            
                                            st.markdown(f"**🎯 Concepto relacionado:** {change['concept']}")
                                            st.markdown("---")
                                
                                # Por qué funciona
                                with st.expander("🎯 Por Qué Funciona Esta Solución"):
                                    st.markdown(result['why_it_works'])
                                
                                # Puntos clave de aprendizaje
                                if result['learning_points']:
                                    with st.expander("📚 Puntos Clave que Debes Recordar", expanded=True):
                                        for i, point in enumerate(result['learning_points'], 1):
                                            st.success(f"**{i}.** {point}")
                                
                                # Tips adicionales
                                if result['additional_tips']:
                                    with st.expander("💡 Tips Adicionales para Mejorar"):
                                        for i, tip in enumerate(result['additional_tips'], 1):
                                            st.info(f"**Tip {i}:** {tip}")
                                
                                st.markdown("---")
                                st.warning("""
                                ### 🎓 Siguiente Paso Importante:
                                1. **Compara** tu código original con el corregido
                                2. **Lee** cada explicación de cambio
                                3. **Entiende** por qué cada cambio era necesario
                                4. **Practica** escribiendo código similar desde cero
                                5. **Aplica** estos conceptos en otros ejercicios
                                """)
                                
                            except Exception as e:
                                st.error(f"Error al generar código corregido: {str(e)}")
                                st.info("Por favor, verifica que tu código esté completo e intenta nuevamente.")
                    else:
                        st.warning("Por favor, pega tu código para que pueda corregirlo y explicarte los cambios.")
        
        return

    if st.session_state.current_page == 'challenges':
        # Notificación de uso de desafíos
        create_usage_notification(
            "Gimnasio de Código IA", 
            "Has accedido al gimnasio donde puedes generar desafíos personalizados y practicar programación."
        )
        
        st.title("🚀 Gimnasio de Código IA")
        st.markdown("### Entrena con desafíos evaluados por IA de Gemini")
        
        # Inicializar estado si no existe
        if 'gym_show_solution' not in st.session_state:
            st.session_state.gym_show_solution = False
        if 'gym_evaluation_result' not in st.session_state:
            st.session_state.gym_evaluation_result = None
        
        # Layout principal: Configuración + Desafío + Solución
        col_config, col_main = st.columns([1, 3])
        
        with col_config:
            st.markdown("### ⚙️ Configuración")
            
            lang = st.selectbox("Lenguaje", 
                              ["Python", "JavaScript", "Java", "C++", "C#", "C", "Ruby", "PHP", 
                               "Go", "Rust", "Swift", "Kotlin", "TypeScript", "SQL", "NoSQL", 
                               "HTML/CSS", "R", "MATLAB"],
                              key="gym_lang")
            
            diff = st.selectbox("Dificultad", 
                              ["Principiante", "Intermedio", "Avanzado"],
                              key="gym_diff")
            
            st.markdown("---")
            
            if st.button("🎲 Generar Nuevo Desafío", type="primary", use_container_width=True, key="generate_challenge_btn"):
                # Limpiar estado anterior
                st.session_state.gym_show_solution = False
                st.session_state.gym_evaluation_result = None
                if 'gym_solution' in st.session_state:
                    del st.session_state['gym_solution']
                if 'gym_approach' in st.session_state:
                    del st.session_state['gym_approach']
                
                # Notificación
                notification_manager.create_notification(
                    user_id=u['username'],
                    title="🎲 Desafío Generado",
                    message=f"Has generado un desafío de {lang} nivel {diff}. ¡Perfecto para practicar!",
                    notification_type='success'
                )
                
                # Verificar logros
                from utils_notifications import check_and_create_achievements
                check_and_create_achievements(u['username'])
                
                with st.spinner("🧠 La IA está creando tu desafío personalizado..."):
                    # Definir complejidad según dificultad
                    complexity_map = {
                        "Principiante": {
                            "desc": "conceptos básicos y sintaxis fundamental",
                            "lines": "5-15 líneas",
                            "concepts": "variables, condicionales simples, bucles básicos"
                        },
                        "Intermedio": {
                            "desc": "estructuras de datos y algoritmos intermedios",
                            "lines": "15-30 líneas",
                            "concepts": "funciones, arrays/listas, diccionarios, manipulación de datos"
                        },
                        "Avanzado": {
                            "desc": "algoritmos complejos y optimización",
                            "lines": "30-50 líneas",
                            "concepts": "clases, recursión, algoritmos de ordenamiento, estructuras avanzadas"
                        }
                    }
                    
                    complexity = complexity_map[diff]
                    
                    prompt = f"""Genera un desafío de programación en {lang} de nivel {diff}.

REQUISITOS ESPECÍFICOS:
- Lenguaje: {lang}
- Dificultad: {diff} ({complexity['desc']})
- Longitud esperada: {complexity['lines']}
- Conceptos a usar: {complexity['concepts']}

FORMATO OBLIGATORIO (usa markdown):

## 🎯 [Título del Desafío]

**Descripción:**
[Descripción clara y específica del problema a resolver. Debe ser un problema práctico y realista.]

**Entrada:**
[Especifica qué datos recibirá el programa]

**Salida:**
[Especifica qué debe retornar o imprimir el programa]

**Ejemplo 1:**
```
Entrada: [ejemplo concreto]
Salida: [resultado esperado]
```

**Ejemplo 2:**
```
Entrada: [otro ejemplo]
Salida: [resultado esperado]
```

**Restricciones:**
- [Restricción técnica 1 específica para {lang}]
- [Restricción técnica 2]
- [Complejidad temporal esperada si aplica]

**💡 Pista:**
[Una pista útil sin revelar la solución]

IMPORTANTE: 
- El desafío debe ser ESPECÍFICO para {lang}
- Debe usar características propias de {lang}
- Debe ser RESOLUBLE en {complexity['lines']}
- Debe ser apropiado para nivel {diff}
"""
                    
                    try:
                        response = model.generate_content(prompt)
                        st.session_state.current_challenge = response.text
                        st.session_state.challenge_lang = lang
                        st.session_state.challenge_diff = diff
                        st.success("✅ ¡Desafío generado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al generar desafío: {str(e)}")
            
            st.markdown("---")
            
            st.info("""
            ### 🎯 Características
            - 🧠 Generados por IA
            - 🎲 Siempre diferentes
            - 📊 Evaluación detallada
            - 💡 Pistas y soluciones
            """)
        
        with col_main:
            if 'current_challenge' in st.session_state and st.session_state.current_challenge:
                # Mostrar desafío
                st.markdown("### 📋 Tu Desafío")
                with st.container(border=True):
                    st.markdown(st.session_state.current_challenge)
                
                st.markdown("---")
                
                # Editor de código
                st.markdown("### 💻 Tu Solución")
                
                # Leer configuración de bloqueo de paste desde la BD
                _block_paste = False
                try:
                    _bp_row = conn.execute(
                        "SELECT value FROM system_settings WHERE key='gym_block_paste'"
                    ).fetchone()
                    _block_paste = (_bp_row['value'] == '1') if _bp_row else True
                except:
                    _block_paste = True
                
                if _block_paste:
                    st.warning("⌨️ **Modo escritura manual activo** — el código debe escribirse a mano. Pegar está deshabilitado.")
                    
                    from streamlit_ace import st_ace
                    _lang_placeholder = st.session_state.get('challenge_lang', 'Python')
                    # Mapa de lenguajes a modos de Ace Editor
                    _ace_lang_map = {
                        "Python": "python", "JavaScript": "javascript",
                        "Java": "java", "C++": "c_cpp", "C#": "csharp",
                        "C": "c_cpp", "Ruby": "ruby", "PHP": "php",
                        "Go": "golang", "Rust": "rust", "Swift": "swift",
                        "Kotlin": "kotlin", "TypeScript": "typescript",
                        "SQL": "sql", "NoSQL": "javascript",
                        "HTML/CSS": "html", "R": "r", "MATLAB": "matlab",
                    }
                    _ace_mode = _ace_lang_map.get(_lang_placeholder, "text")
                    
                    student_solution = st_ace(
                        placeholder=f"// Escribe tu solución en {_lang_placeholder}...",
                        language=_ace_mode,
                        theme="monokai",
                        height=300,
                        font_size=14,
                        tab_size=4,
                        show_gutter=True,
                        show_print_margin=False,
                        wrap=False,
                        auto_update=True,
                        readonly=False,
                        key="gym_ace_editor",
                    )
                    # st_ace no tiene opción nativa de disable_paste en la versión 0.1.1,
                    # pero sí bloquea a través de key_bindings. Lo complementamos detectando
                    # el delta de longitud al evaluar (el paste aparece en el valor enviado).
                    if student_solution is None:
                        student_solution = ''
                
                else:
                    student_solution = st.text_area(
                        "Escribe tu código aquí",
                        height=300,
                        placeholder=f"// Escribe tu solución en {st.session_state.get('challenge_lang', 'el lenguaje seleccionado')}...",
                        key="gym_solution"
                    )
                
                approach = st.text_area(
                    "Explica tu enfoque (opcional)", 
                    height=100,
                    placeholder="¿Cómo planeas resolver este problema?",
                    key="gym_approach"
                )
                
                # Botones de acción
                col_btn1, col_btn2, col_btn3 = st.columns(3)
                
                with col_btn1:
                    if st.button("🎯 Evaluar con IA", type="primary", use_container_width=True, key="eval_btn"):
                        if student_solution.strip():
                            with st.spinner("🤖 La IA está evaluando tu solución..."):
                                try:
                                    challenge_lang = st.session_state.get('challenge_lang', 'Python')
                                    # Mapa completo de lenguajes del gimnasio a identificadores de bloque de código
                                    _lang_map = {
                                        "Python": "python", "JavaScript": "javascript",
                                        "Java": "java", "C++": "cpp", "C#": "csharp",
                                        "C": "c", "Ruby": "ruby", "PHP": "php",
                                        "Go": "go", "Rust": "rust", "Swift": "swift",
                                        "Kotlin": "kotlin", "TypeScript": "typescript",
                                        "SQL": "sql", "NoSQL": "javascript",
                                        "HTML/CSS": "html", "R": "r", "MATLAB": "matlab",
                                    }
                                    lang_block = _lang_map.get(challenge_lang, challenge_lang.lower())

                                    # Evaluacion directa con Gemini — soporta cualquier lenguaje
                                    _eval_prompt = f"""Eres un evaluador experto en {challenge_lang}. Evalúa este código de forma precisa.

DESAFÍO:
{st.session_state.current_challenge[:800]}

CÓDIGO DEL ESTUDIANTE EN {challenge_lang}:
```{lang_block}
{student_solution}
```

INSTRUCCIONES CRÍTICAS:
1. Evalúa según las reglas y convenciones de {challenge_lang}
2. NO penalices por diferencias con Python u otros lenguajes
3. Si el código resuelve correctamente el problema, score debe ser 8-10
4. Solo da score bajo si hay errores reales de lógica o el código no resuelve el problema

Responde SOLO con JSON:
{{"score": <0-10>, "feedback": "<explicación detallada>", "correctness": "<correcto|parcial|incorrecto>", "suggestions": ["sugerencia1"], "concepts": ["concepto1"]}}"""

                                    try:
                                        from google.generativeai.types import RequestOptions
                                        _resp = model.generate_content(
                                            _eval_prompt,
                                            generation_config={"temperature": 0.2, "max_output_tokens": 500},
                                            request_options=RequestOptions(timeout=25)
                                        )
                                        _txt = _resp.text if _resp and hasattr(_resp, 'text') else ""
                                        _s = _txt.find('{'); _e = _txt.rfind('}')
                                        if _s != -1 and _e != -1:
                                            import json as _json
                                            _parsed = _json.loads(_txt[_s:_e+1])
                                            score = max(0, min(10, float(_parsed.get('score', 5))))
                                            feedback = _parsed.get('feedback', 'Evaluado por IA')
                                            correctness = _parsed.get('correctness', 'parcial')
                                            suggestions = _parsed.get('suggestions', [])
                                            concepts = _parsed.get('concepts', [])
                                        else:
                                            raise ValueError("No JSON in response")
                                    except Exception as _eval_err:
                                        # Fallback: usar ai_evaluator con el lenguaje correcto
                                        from utils_ai import ai_evaluator
                                        score, feedback, correctness, suggestions, concepts = ai_evaluator(
                                            model, student_solution, st.session_state.current_challenge, challenge_lang
                                        )
                                    
                                    # Guardar resultado en session_state
                                    st.session_state.gym_evaluation_result = {
                                        'score': score,
                                        'feedback': feedback,
                                        'correctness': correctness,
                                        'suggestions': suggestions,
                                        'concepts': concepts
                                    }
                                    

                                    # Guardar ejercicio del gimnasio en BD para mejorar recomendaciones
                                    try:
                                        _gym_lang = st.session_state.get("challenge_lang", "Python")
                                        _gym_diff_raw = st.session_state.get("challenge_diff", "Principiante")
                                        _diff_map = {"Principiante": "easy", "Intermedio": "medium", "Avanzado": "hard"}
                                        _gym_diff = _diff_map.get(_gym_diff_raw, "easy")
                                        _gym_title = (st.session_state.current_challenge or "Reto")[:80].split("\n")[0].strip("# ").strip() or "Reto sin título"
                                        _gym_desc = (st.session_state.current_challenge or "")[:500]
                                        _raw_score = score if score is not None else 0
                                        _gym_score_pct = float(_raw_score) * 10 if float(_raw_score) <= 10 else float(_raw_score)
                                        _gym_completed = 1 if str(correctness) == "correcto" or float(_raw_score) >= 7 else 0
                                        # Insertar o reusar challenge en daily_challenges
                                        _existing = conn.execute(
                                            "SELECT id FROM daily_challenges WHERE title=? AND language=? AND difficulty=?",
                                            (_gym_title, _gym_lang, _gym_diff)
                                        ).fetchone()
                                        if _existing:
                                            _gym_challenge_id = _existing["id"]
                                        else:
                                            conn.execute(
                                                "INSERT INTO daily_challenges (challenge_date, language, difficulty, title, description, points, bonus_points) VALUES (date('now'), ?, ?, ?, ?, 30, 10)",
                                                (_gym_lang, _gym_diff, _gym_title, _gym_desc)
                                            )
                                            conn.commit()
                                            _gym_challenge_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                                        # Registrar intento siempre (no solo si completo)
                                        conn.execute(
                                            "INSERT INTO daily_challenge_attempts (challenge_id, user_id, submitted_code, score, completed, feedback) VALUES (?, ?, ?, ?, ?, ?)",
                                            (_gym_challenge_id, u["username"], student_solution or "", _gym_score_pct, _gym_completed, str(feedback or "")[:500])
                                        )
                                        conn.commit()
                                    except Exception as _save_err:
                                        st.caption(f"⚠️ No se pudo guardar el intento: {_save_err}")

                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"Error en evaluación: {str(e)}")
                        else:
                            st.warning("⚠️ Escribe tu solución primero.")
                
                with col_btn2:
                    if st.button("💡 Pista", use_container_width=True, key="hint_btn"):
                        with st.spinner("🤔 Generando pista..."):
                            hint_prompt = f"""
                            Un estudiante está trabajando en este desafío:
                            {st.session_state.current_challenge}

                            Su código actual:
                            {student_solution if student_solution.strip() else "Aún no ha empezado"}

                            Proporciona UNA pista útil y específica sin dar la solución completa. 
                            Guía al estudiante hacia la dirección correcta.
                            Sé breve y directo (máximo 3 líneas).
                            """
                            
                            try:
                                hint = model.generate_content(hint_prompt)
                                st.info(f"💡 **Pista:** {hint.text}")
                            except Exception as e:
                                st.error(f"Error al generar pista: {str(e)}")
                
                with col_btn3:
                    if st.button("🧠 Ver Solución", use_container_width=True, key="solution_btn"):
                        st.session_state.gym_show_solution = not st.session_state.gym_show_solution
                        st.rerun()
                
                # Mostrar resultado de evaluación si existe
                if st.session_state.gym_evaluation_result:
                    result = st.session_state.gym_evaluation_result
                    
                    st.markdown("---")
                    st.markdown("### 🎓 Evaluación del Profesor IA")
                    
                    # Puntuación con color
                    score_color = "#10b981" if result['score'] >= 8 else "#f59e0b" if result['score'] >= 6 else "#ef4444"
                    
                    col_score, col_status = st.columns([1, 2])
                    with col_score:
                        st.markdown(f"""
                        <div style="text-align: center; padding: 20px; background: {score_color}; border-radius: 10px;">
                            <h1 style="color: white; margin: 0;">{result['score']}/10</h1>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_status:
                        status_emoji = "✅" if result['correctness'] == "correcto" else "⚠️" if result['correctness'] == "parcial" else "❌"
                        st.markdown(f"""
                        <div style="padding: 20px; background: rgba(255,255,255,0.05); border-radius: 10px;">
                            <h3 style="margin: 0;">{status_emoji} Estado: {result['correctness'].upper()}</h3>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Feedback detallado
                    with st.expander("📝 Retroalimentación Detallada", expanded=True):
                        st.markdown(result['feedback'])
                    
                    # Sugerencias
                    if result['suggestions']:
                        with st.expander("💡 Sugerencias de Mejora"):
                            for suggestion in result['suggestions']:
                                st.markdown(f"- {suggestion}")
                    
                    # Conceptos
                    if result['concepts']:
                        with st.expander("📚 Conceptos Relevantes"):
                            for concept in result['concepts']:
                                st.markdown(f"- {concept}")
                
                # Mostrar solución si se solicitó
                if st.session_state.gym_show_solution:
                    st.markdown("---")
                    st.markdown("### ✅ Solución de Referencia")
                    
                    with st.spinner("🔧 Generando solución..."):
                        solution_prompt = f"""
                        Proporciona una solución completa y bien explicada para este desafío:

                        {st.session_state.current_challenge}

                        FORMATO:

                        ## 💻 Código Completo:
                        ```{st.session_state.get('challenge_lang', 'text').lower()}
                        [código funcional completo con comentarios]
                        ```

                        ## 📝 Explicación:
                        [Explica la lógica paso a paso de forma clara y concisa]

                        ## 🎯 Conceptos Clave:
                        - [Concepto 1]
                        - [Concepto 2]

                        Asegúrate de que el código sea funcional y esté bien comentado.
                        """
                        
                        try:
                            solution = model.generate_content(solution_prompt)
                            with st.container(border=True):
                                st.markdown(solution.text)
                            
                            st.info("💡 **Consejo**: Estudia esta solución, entiende cada línea, y luego intenta resolver problemas similares por tu cuenta.")
                        except Exception as e:
                            st.error(f"Error al generar solución: {str(e)}")
            
            else:
                # Estado inicial: sin desafío
                st.markdown("""
                <div style="text-align: center; padding: 60px 20px;">
                    <h2 style="color: #58a6ff;">👈 Genera un desafío para comenzar</h2>
                    <p style="color: #888; font-size: 1.1em;">
                        Selecciona un lenguaje y dificultad, luego haz clic en "Generar Nuevo Desafío"
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Mostrar estadísticas o información adicional
                st.markdown("---")
                st.markdown("### 📊 ¿Cómo funciona?")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("""
                    **1️⃣ Genera**
                    
                    Selecciona lenguaje y dificultad. La IA creará un desafío único adaptado a tu nivel.
                    """)
                
                with col2:
                    st.markdown("""
                    **2️⃣ Resuelve**
                    
                    Escribe tu código en el editor. Puedes pedir pistas si te atascas.
                    """)
                
                with col3:
                    st.markdown("""
                    **3️⃣ Aprende**
                    
                    La IA evaluará tu código y te dará feedback detallado para mejorar.
                    """)
        

        # ── Recomendaciones personalizadas (TF-IDF + Coseno) ──────────────
        st.markdown("---")
        # ── Retos Recomendados (lazy: solo al presionar Actualizar) ──
        _col_rec_title, _col_rec_btn = st.columns([5, 1])
        with _col_rec_title:
            st.markdown("### 🎯 Retos Recomendados para ti")
        with _col_rec_btn:
            _refresh_recs_gym = st.button("🔄 Actualizar",
                key="refresh_recs_gym",
                help="Genera nuevos retos personalizados con IA",
                use_container_width=True)
        _sc_user = u["username"]
        _sc = conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT dc.language, dc.title FROM daily_challenge_attempts dca JOIN daily_challenges dc ON dca.challenge_id = dc.id WHERE dca.user_id=?)",
            (_sc_user,)
        ).fetchone()[0]
        if _sc > 0:
            st.caption(f"🧠 Perfil basado en {_sc} reto(s) · IA genera retos personalizados")
        else:
            st.caption("💡 Presiona Actualizar para recibir retos recomendados por IA")
        _rkey = f"cached_recs_gym_{u['username']}"
        if _refresh_recs_gym:
            # Limpiar cache anterior para forzar regeneracion
            if _rkey in st.session_state:
                del st.session_state[_rkey]
            with st.spinner("🤖 Generando retos personalizados con IA..."):
                try:
                    _new_recs = get_content_recommendations(
                        student_id=u["username"],
                        db_connection=conn,
                        limit=3,
                        model=model,
                    )
                    st.session_state[_rkey] = _new_recs
                    st.rerun()
                except Exception as _ge:
                    st.warning(f"⚠️ No se pudieron generar: {_ge}")
        _recs = st.session_state.get(_rkey, [])
        if _recs:
            _dc_map = {"easy": "#4caf50", "medium": "#ff9800", "hard": "#f44336"}
            _dn_map = {"easy": "FÁCIL", "medium": "MEDIO", "hard": "DIFÍCIL"}
            _rc = st.columns(len(_recs))
            for _rcol, _reto in zip(_rc, _recs):
                with _rcol:
                    _dc = _dc_map.get(_reto.get("difficulty",""),"#888")
                    _dn = _dn_map.get(_reto.get("difficulty",""),_reto.get("difficulty","").upper())
                    st.markdown(
                        f'<div style="border:1px solid #333;border-radius:10px;padding:14px;background:#1e1e1e;min-height:150px;">'
                        f'<div style="color:{_dc};font-size:0.72rem;font-weight:bold;margin-bottom:5px;">{_dn} &middot; {_reto.get("language","")}</div>'
                        f'<div style="color:white;font-size:0.92rem;font-weight:bold;margin-bottom:8px;">{_reto.get("title","Reto")}</div>'
                        f'<div style="color:#aaa;font-size:0.78rem;">💡 {_reto.get("recommendation_reason","")}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    _rid = str(_reto.get("id", id(_reto)))
                    if st.button("▶️ Hacer este reto", key=f"lr_gym_{_rid}", use_container_width=True, type="primary"):
                        _desc = _reto.get("description","")
                        st.session_state.current_challenge = f"# {_reto.get('title','Reto')}\n\n{_desc}"
                        st.session_state.challenge_lang = _reto.get("language","Python")
                        st.session_state.challenge_diff = _reto.get("difficulty","medium")
                        st.session_state.gym_evaluation_result = None
                        st.session_state.gym_show_solution = False
                        st.rerun()
        elif not _refresh_recs_gym:
            st.info("🤖 Presiona **Actualizar** para que la IA genere retos personalizados.")


        return

    if st.session_state.current_page == 'grades':
        # Notificación de uso de calificaciones
        create_usage_notification(
            "Historial de Calificaciones", 
            "Has accedido a tu historial académico donde puedes revisar todas tus calificaciones y progreso."
        )
        
        st.title(" Mis Calificaciones")
        st.markdown("### Historial de calificaciones por curso")
        
        # Obtener cursos del estudiante
        courses_rows = conn.execute("""
            SELECT c.id, c.name, c.code 
            FROM courses c 
            JOIN enrollments e ON c.id = e.course_id 
            WHERE e.student_id = ?
        """, (u['username'],)).fetchall()
        courses = [dict(r) for r in courses_rows]
        
        if not courses:
            st.info("📚 No estás inscrito en ningún curso todavía.")
            return
        
        st.title("📊 Mis Calificaciones")
        st.markdown("### Historial de calificaciones por curso")
        
        # Mostrar por curso
        for course in courses:
            with st.expander(f"📘 {course['name']} ({course['code']})", expanded=True):
                # Calificaciones de tareas
                tasks_grades_rows = conn.execute("""
                    SELECT t.title, s.final_grade, t.points, s.submission_date,
                           CASE 
                               WHEN s.final_grade >= t.points * 0.9 THEN 'Excelente'
                               WHEN s.final_grade >= t.points * 0.7 THEN 'Bueno'
                               WHEN s.final_grade >= t.points * 0.6 THEN 'Regular'
                               ELSE 'Necesita Mejorar'
                           END as performance
                    FROM tasks t 
                    LEFT JOIN submissions s ON t.id = s.task_id AND s.student_id = ? 
                    WHERE t.course_id = ?
                    ORDER BY t.due_date DESC
                """, (u['username'], course['id'])).fetchall()
                tasks_grades = [dict(r) for r in tasks_grades_rows]
                
                # Calificaciones de exámenes
                exam_grades_rows = conn.execute("""
                    SELECT e.title, a.score, 
                           (SELECT SUM(points) FROM exam_questions WHERE exam_id = e.id) as total,
                           a.end_time
                    FROM exams e 
                    LEFT JOIN exam_attempts a ON e.id = a.exam_id AND a.student_id = ? 
                    WHERE e.course_id = ?
                """, (u['username'], course['id'])).fetchall()
                exam_grades = [dict(r) for r in exam_grades_rows]
                
                # Crear DataFrame
                data = []
                
                for task in tasks_grades:
                    grade = task['final_grade'] if task.get('final_grade') is not None else 0
                    data.append({
                        "Actividad": task['title'],
                        "Tipo": "📝 Tarea",
                        "Nota": f"{grade:.1f} / {task['points']}",
                        "Porcentaje": f"{(grade/task['points']*100):.1f}%" if task['points'] > 0 else "0%",
                        "Estado": task['performance'] if task.get('final_grade') is not None else "Pendiente",
                        "Fecha": task['submission_date']
                    })
                
                for exam in exam_grades:
                    score = exam['score'] if exam.get('score') is not None else 0
                    total = exam['total'] if exam.get('total') else 0
                    percentage = (score/total*100) if total > 0 else 0
                    
                    status = "✅ Completado" if exam.get('score') is not None else "⏳ Pendiente"
                    
                    data.append({
                        "Actividad": exam['title'],
                        "Tipo": "✅ Examen",
                        "Nota": f"{score:.1f} / {total}",
                        "Porcentaje": f"{percentage:.1f}%",
                        "Estado": status,
                        "Fecha": exam['end_time']
                    })
                
                if data:
                    df = pd.DataFrame(data)
                    st.dataframe(df, width='stretch', hide_index=True)
                    
                    # Estadísticas
                    if len(data) > 0:
                        col_stats = st.columns(4)
                        completed = sum(1 for d in data if "Pendiente" not in d["Estado"])
                        avg_grade = sum(float(d["Porcentaje"].replace('%', '')) for d in data if d["Porcentaje"] != "0%") / len(data)
                        
                        col_stats[0].metric("📊 Total Actividades", len(data))
                        col_stats[1].metric("✅ Completadas", completed)
                        col_stats[2].metric("📈 Promedio", f"{avg_grade:.1f}%")
                        col_stats[3].metric("🎯 Rendimiento", 
                                          "Excelente" if avg_grade >= 90 else 
                                          "Bueno" if avg_grade >= 70 else 
                                          "Regular" if avg_grade >= 60 else "Bajo")
                else:
                    st.caption("Sin calificaciones registradas para este curso.")
        
        return

    if st.session_state.current_page == 'academy':
        # Notificación de uso de academia personal
        create_usage_notification(
            "Academia Personal IA", 
            "Has accedido a la academia personal donde puedes crear cursos adaptados a tu nivel con IA."
        )
        
        render_personal_academy(conn, u, model)
        return

    # ==============================================================================
    # VISTA PRINCIPAL: DASHBOARD
    # ==============================================================================
    if st.session_state.view_mode == 'dashboard':
        # Mostrar modal de cursos si está activo
        if st.session_state.get('show_courses_modal', False):
            render_hamburger_menu(conn, u)
            return
        
        # Layout con columnas: contenido principal (70%) y panel lateral (30%)
        col_main, col_sidebar = st.columns([7, 3])
        
        with col_main:
            # Header simple con saludo
            st.title(f"👋 ¡Hola, {u['full_name']}!")
            st.caption(f"🎓 Estudiante • Última actividad: {datetime.now().strftime('%d/%m/%Y')}")
            
            st.markdown("---")
            st.markdown("### 📚 Mis Cursos Activos")
        
        with col_sidebar:
            # Panel lateral "Por hacer"
            render_pending_tasks_panel(conn, u)
        
        with col_main:
            # Verificar si es estudiante gratuito
            is_free_student = u.get('account_type') == 'free'
            
            if is_free_student:
                # Estudiantes gratuitos solo ven herramientas IA
                st.info("🤖 Tu cuenta gratuita te da acceso a todas las herramientas de IA. Los cursos con profesor requieren inscripción por parte de un administrador.")
                st.markdown("**Herramientas disponibles para ti:**")
                st.markdown("- 🤖 Tutor IA")
                st.markdown("- 💪 Gimnasio de Código")
                st.markdown("- 🎓 Academia Personal IA")
                st.markdown("- 📅 Pregunta Diaria")
                st.markdown("- 🏆 Desafíos y Logros")
                regular_courses = []
                ai_courses_rows = conn.execute("""
                    SELECT id, language, level, status, progress_percentage, created_at, last_activity,
                           difficulty_setting, assessment_score, display_status
                    FROM ai_courses 
                    WHERE student_id = ? AND status != 'completed' 
                    AND (display_status IS NULL OR display_status = 'active')
                    ORDER BY last_activity DESC
                """, (u['username'],)).fetchall()
                ai_courses = [dict(r) for r in ai_courses_rows]
                all_courses = ai_courses
            else:
                # Obtener solo cursos regulares ACTIVOS del estudiante
                courses_rows = conn.execute("""
                    SELECT c.*, u.full_name as teacher_name, e.display_status
                    FROM courses c 
                    JOIN enrollments e ON c.id = e.course_id 
                    LEFT JOIN users u ON c.teacher_id = u.username 
                    WHERE e.student_id = ? AND (e.display_status IS NULL OR e.display_status = 'active')
                    ORDER BY c.name
                """, (u['username'],)).fetchall()
                regular_courses = [dict(r) for r in courses_rows]
                
                # Obtener solo cursos IA ACTIVOS del estudiante
                ai_courses_rows = conn.execute("""
                    SELECT id, language, level, status, progress_percentage, created_at, last_activity,
                           difficulty_setting, assessment_score, display_status
                    FROM ai_courses 
                    WHERE student_id = ? AND status != 'completed' 
                    AND (display_status IS NULL OR display_status = 'active')
                    ORDER BY last_activity DESC
                """, (u['username'],)).fetchall()
                ai_courses = [dict(r) for r in ai_courses_rows]
                
                # Combinar cursos activos
                all_courses = regular_courses + ai_courses
            
            if not all_courses:
                if is_free_student:
                    st.markdown("---")
                    st.info("🎓 Aún no tienes cursos IA. Ve a **Academia Personal IA** para crear uno.")
                else:
                    st.info("🎓 No tienes cursos inscritos aún.")
                    st.markdown("**💡 Opciones disponibles:**")
                    st.markdown("- Contacta a tu administrador para inscribirte en cursos regulares")
                    st.markdown("- Usa **🎓 Academia Personal IA** para crear cursos personalizados")
                    
                    # Botón para crear datos de prueba
                    if st.button("🧪 Crear Curso de Prueba", help="Crea un curso de ejemplo para probar la funcionalidad"):
                        if create_sample_course_data(conn, u):
                            st.success("✅ Curso de prueba creado")
                            st.rerun()
                        else:
                            st.error("❌ Error creando curso de prueba")
            else:
                # Mostrar cursos en grid
                cols = st.columns(3)
                course_index = 0
                
                # Mostrar cursos regulares
                for course in regular_courses:
                    with cols[course_index % 3]:
                        render_regular_course_card(course, course_index)
                    course_index += 1
                
                # Mostrar cursos IA
                for ai_course in ai_courses:
                    with cols[course_index % 3]:
                        render_ai_course_card(conn, ai_course, course_index, u)
                    course_index += 1
                
                st.markdown("---")
                
                # Estadísticas con diseño mejorado
                st.markdown("""
                <div style="text-align: center; margin: 30px 0 20px 0;">
                    <h2 style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        font-size: 2em;
                        font-weight: bold;
                    ">📊 Resumen de Cursos</h2>
                </div>
                """, unsafe_allow_html=True)
                
                col_stats = st.columns(4)
                
                with col_stats[0]:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:25px;border-radius:15px;text-align:center;box-shadow:0 8px 16px rgba(102,126,234,0.3);">
                        <div style="font-size:3em;margin-bottom:10px;">📚</div>
                        <div style="color:white;font-size:2.5em;font-weight:bold;margin-bottom:5px;">{len(all_courses)}</div>
                        <div style="color:rgba(255,255,255,0.9);font-size:1em;">Total Cursos</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_stats[1]:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#4facfe,#00f2fe);padding:25px;border-radius:15px;text-align:center;box-shadow:0 8px 16px rgba(79,172,254,0.3);">
                        <div style="font-size:3em;margin-bottom:10px;">👨‍🏫</div>
                        <div style="color:white;font-size:2.5em;font-weight:bold;margin-bottom:5px;">{len(regular_courses)}</div>
                        <div style="color:rgba(255,255,255,0.9);font-size:1em;">Cursos Regulares</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_stats[2]:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#fa709a,#fee140);padding:25px;border-radius:15px;text-align:center;box-shadow:0 8px 16px rgba(250,112,154,0.3);">
                        <div style="font-size:3em;margin-bottom:10px;">🤖</div>
                        <div style="color:white;font-size:2.5em;font-weight:bold;margin-bottom:5px;">{len(ai_courses)}</div>
                        <div style="color:rgba(255,255,255,0.9);font-size:1em;">Cursos IA</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_stats[3]:
                    active_ai = len([c for c in ai_courses if c['status'] == 'active'])
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#43e97b,#38f9d7);padding:25px;border-radius:15px;text-align:center;box-shadow:0 8px 16px rgba(67,233,123,0.3);">
                        <div style="font-size:3em;margin-bottom:10px;">🟢</div>
                        <div style="color:white;font-size:2.5em;font-weight:bold;margin-bottom:5px;">{active_ai}</div>
                        <div style="color:rgba(255,255,255,0.9);font-size:1em;">IA Activos</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("<div style='margin: 40px 0;'></div>", unsafe_allow_html=True)
            
            # Métricas principales del usuario con diseño mejorado
            st.markdown("""
            <div style="text-align: center; margin: 30px 0 20px 0;">
                <h2 style="
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    font-size: 2em;
                    font-weight: bold;
                ">📈 Tu Actividad</h2>
            </div>
            """, unsafe_allow_html=True)
            
            col_info = st.columns(3)
            
            with col_info[0]:
                cursos_count = conn.execute("""
                    SELECT COUNT(*) FROM enrollments WHERE student_id = ?
                """, (u['username'],)).fetchone()[0]
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 30px;
                    border-radius: 15px;
                    text-align: center;
                    box-shadow: 0 8px 16px rgba(102, 126, 234, 0.3);
                ">
                    <div style="font-size: 3.5em; margin-bottom: 15px;">📚</div>
                    <div style="color: white; font-size: 3em; font-weight: bold; margin-bottom: 10px;">{cursos_count}</div>
                    <div style="color: rgba(255, 255, 255, 0.9); font-size: 1.2em;">Cursos Inscritos</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_info[1]:
                tareas_pendientes = conn.execute("""
                    SELECT COUNT(*) FROM tasks t
                    LEFT JOIN submissions s ON t.id = s.task_id AND s.student_id = ?
                    WHERE t.course_id IN (
                        SELECT course_id FROM enrollments WHERE student_id = ?
                    ) AND (s.id IS NULL OR s.status != 'graded')
                """, (u['username'], u['username'])).fetchone()[0]
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    padding: 30px;
                    border-radius: 15px;
                    text-align: center;
                    box-shadow: 0 8px 16px rgba(240, 147, 251, 0.3);
                ">
                    <div style="font-size: 3.5em; margin-bottom: 15px;">📝</div>
                    <div style="color: white; font-size: 3em; font-weight: bold; margin-bottom: 10px;">{tareas_pendientes}</div>
                    <div style="color: rgba(255, 255, 255, 0.9); font-size: 1.2em;">Tareas Pendientes</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_info[2]:
                notificaciones = conn.execute("""
                    SELECT COUNT(*) FROM notifications 
                    WHERE user_id = ? AND is_read = 0
                """, (u['username'],)).fetchone()[0]
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                    padding: 30px;
                    border-radius: 15px;
                    text-align: center;
                    box-shadow: 0 8px 16px rgba(250, 112, 154, 0.3);
                ">
                    <div style="font-size: 3.5em; margin-bottom: 15px;">🔔</div>
                    <div style="color: white; font-size: 3em; font-weight: bold; margin-bottom: 10px;">{notificaciones}</div>
                    <div style="color: rgba(255, 255, 255, 0.9); font-size: 1.2em;">Notificaciones</div>
                </div>
                """, unsafe_allow_html=True)
        
        # Mostrar modal de configuración si está activo
        # if st.session_state.get('show_ai_course_config'):
        #     ai_course_id = st.session_state.get('ai_course_config')
        #     if ai_course_id:
        #         # Buscar el curso IA específico
        #         ai_course_data = conn.execute("""
        #             SELECT * FROM ai_courses WHERE id = ? AND student_id = ?
        #         """, (ai_course_id, u['username'])).fetchone()
        #         
        #         if ai_course_data:
        #             ai_course_dict = dict(ai_course_data)
        #             st.markdown("---")
        #             render_ai_course_config_modal(conn, ai_course_dict, u)
        #             st.markdown("---")

    # ==============================================================================
    # VISTA 2: DENTRO DEL CURSO
    # ==============================================================================
    if st.session_state.view_mode == 'course':
        c = st.session_state.active_course
        
        # Verificación de seguridad
        if c is None:
            st.error("❌ No hay curso seleccionado")
            if st.button("🏠 Volver al Dashboard"):
                st.session_state.view_mode = 'dashboard'
                st.rerun()
            return
        
        # --- VERIFICAR SI HAY EXAMEN ACTIVO - MOSTRAR SOLO EL EXAMEN ---
        if st.session_state.get('exam_session') and st.session_state.exam_session.get('course_id') == c['id']:
            # OCULTAR SIDEBAR COMPLETAMENTE
            st.markdown("""
            <style>
                [data-testid="stSidebar"] {
                    display: none !important;
                }
                .main .block-container {
                    padding-left: 1rem !important;
                    padding-right: 1rem !important;
                    max-width: 100% !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
            es = st.session_state.exam_session
            
            # Verificar si el examen sigue válido
            is_valid, validation_msg = validate_exam_time(conn, es['id'], u['username'])
            if not is_valid:
                st.error(validation_msg)
                del st.session_state.exam_session
                if 'show_exam_only' in st.session_state:
                    del st.session_state.show_exam_only
                time.sleep(2)
                st.rerun()
                return
            
            # Renderizar interfaz del examen
            render_exam_interface(conn, es, u, c, model)
            return
        
        # Limpiar flag si no hay examen activo
        if 'show_exam_only' in st.session_state:
            del st.session_state.show_exam_only
        
        # Header del curso
        if c.get('cover_image'):
            b64_img = base64.b64encode(c['cover_image']).decode()
            st.markdown(f"""
            <div style="
                width: 100%;
                height: 200px;
                overflow: hidden;
                border-radius: 12px;
                margin-bottom: 20px;
            ">
                <img src="data:image/png;base64,{b64_img}" 
                     style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            """, unsafe_allow_html=True)
        
        st.title(f"📚 {c['name']}")
        st.caption(f"📌 Código: {c['code']} | 📖 {re.sub(r'<[^>]+>', '', c.get('description', 'Sin descripción')).strip()}")
        
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.session_state.pop('active_task_id', None)
            st.rerun()
        
        # Si llegó desde "Ir a la tarea", activar tab de Tareas con JS
        if st.session_state.get('active_task_id'):
            import streamlit.components.v1 as _sc
            _sc.html("""<script>
            setTimeout(function(){
                var tabs=window.parent.document.querySelectorAll('[data-baseweb="tab"]');
                if(tabs&&tabs.length>1){tabs[1].click();}
            },400);
            </script>""", height=0)
        
        # Tabs del curso
        tabs = st.tabs([
            "📚 Módulos", 
            "📝 Tareas", 
            "✅ Exámenes", 
            "💬 Foro", 
            "👥 Personas", 
            "📊 Mis Notas"
        ])

        with tabs[0]:  # Módulos
            st.subheader("📁 Contenido del Curso")
            
            # Obtener módulos
            modules_rows = conn.execute("""
                SELECT * FROM modules 
                WHERE course_id = ? 
                ORDER BY order_index, id
            """, (c['id'],)).fetchall()
            modules = [dict(r) for r in modules_rows]
            
            if not modules:
                st.info("📭 El profesor aún no ha publicado contenido.")
            else:
                for module in modules:
                    module_id = module['id']
                    with st.expander(f"📌 {module['title']}", expanded=True):
                        if module.get('description'):
                            st.markdown(module['description'])
                        
                        # Verificar si el módulo tiene chat IA configurado
                        from utils_chat_ai import ModuleChatManager
                        chat_manager = ModuleChatManager(conn, model)
                        chat_content = chat_manager.get_chat_content(module_id)
                        has_chat = chat_content is not None
                        
                        # Botón para abrir chat IA (solo si está configurado)
                        if has_chat:
                            col_chat1, col_chat2 = st.columns(2)
                            with col_chat1:
                                if st.button("🤖 Chat IA del Módulo", key=f"open_chat_{module_id}", use_container_width=True, type="primary"):
                                    st.session_state[f'show_chat_{module_id}'] = True
                                    st.session_state[f'show_group_chat_{module_id}'] = False
                                    st.rerun()
                            with col_chat2:
                                if st.button("👥 Chat Grupal IA", key=f"open_group_chat_{module_id}", use_container_width=True, type="secondary"):
                                    st.session_state[f'show_group_chat_{module_id}'] = True
                                    st.session_state[f'show_chat_{module_id}'] = False
                                    st.rerun()
                            
                            # Mostrar chat individual si está activado
                            if st.session_state.get(f'show_chat_{module_id}'):
                                render_module_chat_interface(conn, module_id, u['username'], module['title'], model)
                                
                                if st.button("❌ Cerrar chat", key=f"close_chat_{module_id}"):
                                    st.session_state[f'show_chat_{module_id}'] = False
                                    st.rerun()
                                
                                st.markdown("---")

                            # Mostrar chat grupal si está activado
                            if st.session_state.get(f'show_group_chat_{module_id}'):
                                render_group_chat_interface(conn, module_id, u['username'], 'student', module['title'], model)

                                if st.button("❌ Cerrar chat grupal", key=f"close_group_chat_{module_id}"):
                                    st.session_state[f'show_group_chat_{module_id}'] = False
                                    st.rerun()

                                st.markdown("---")
                    
                        # Materiales del módulo
                        materials_rows = conn.execute("""
                            SELECT * FROM course_materials 
                            WHERE module_id = ? 
                            ORDER BY order_index
                        """, (module['id'],)).fetchall()
                        materials = [dict(r) for r in materials_rows]
                    
                        if not materials:
                            st.info("📄 Sin materiales disponibles")
                        else:
                            for material in materials:
                                with st.container(border=True):
                                    col_icon, col_content, col_action = st.columns([0.5, 4, 1])
                                
                                    # Icono según tipo
                                    icon = {
                                        'pdf': '📄',
                                        'video': '🎬',
                                        'text': '📝',
                                        'link': '🔗',
                                        'quiz': '❓'
                                    }.get(material.get('type'), '📁')
                                
                                    col_icon.markdown(f"## {icon}")
                                    col_content.markdown(f"**{material['title']}**")
                                
                                    if material.get('content_blob'):
                                        file_name = material.get('file_name') or f"material_{material['id']}"
                                        col_action.download_button(
                                            "⬇️",
                                            material['content_blob'],
                                            file_name,
                                            key=f"dl_{material['id']}",
                                            help="Descargar"
                                        )
                                    
                                        if material.get('type') == 'pdf':
                                            if col_action.checkbox("👁️", key=f"v_{material['id']}", help="Ver PDF"):
                                                display_pdf(material['content_blob'])

        with tabs[1]:  # Tareas
            st.subheader("� Lista de Tareas")
        
            all_tasks_rows = conn.execute("""
                SELECT t.*, m.title as module_title
                FROM tasks t 
                LEFT JOIN modules m ON t.module_id = m.id 
                WHERE t.course_id = ? 
                ORDER BY t.due_date DESC
            """, (c['id'],)).fetchall()
            all_tasks = [dict(r) for r in all_tasks_rows]
        
            if not all_tasks:
                st.info("🎯 No hay tareas asignadas en este curso.")
            else:
                for task in all_tasks:
                    # Validar si puede entregar
                    is_valid, validation_msg = validate_task_submission(conn, task['id'], u['username'])
                
                    # Verificar entrega
                    submission_row = conn.execute("""
                        SELECT * FROM submissions 
                        WHERE task_id = ? AND student_id = ?
                    """, (task['id'], u['username'])).fetchone()
                    submission = dict(submission_row) if submission_row else None
                
                    status_msg = ""
                    status_color = ""
                    if submission:
                        if submission.get('status') == 'graded':
                            status_msg = f"✅ Calificado: {submission.get('final_grade', 0)}/{task.get('points', 0)}"
                            status_color = "success"
                        else:
                            status_msg = "📩 Entregado (pendiente de calificación)"
                            status_color = "info"
                    else:
                        if is_valid:
                            status_msg = "⚠️ Pendiente"
                            status_color = "warning"
                        else:
                            status_msg = f"⛔ {validation_msg}"
                            status_color = "error"
                
                    module_tag = f"[{task.get('module_title', 'General')}]"
                    
                    # Si el usuario llegó desde "Ir a la tarea", abrir este expander automáticamente
                    target_task_id = st.session_state.get('active_task_id')
                    is_target = (target_task_id == task['id'])
                    if is_target:
                        # Limpiar el estado para que no quede activo en recargas futuras
                        st.session_state.pop('active_task_id', None)
                    
                    with st.expander(f"{module_tag} {task.get('title', 'Sin título')} | {status_msg}", expanded=is_target):
                        st.caption(f"📅 Vence: {task.get('due_date', 'No especificada')} | 💯 Puntos: {task.get('points', 0)}")
                        if task.get('description'):
                            st.markdown(task['description'])
                    
                        if task.get('criteria'):
                            with st.expander("📋 Criterios de evaluación"):
                                st.markdown(task['criteria'])
                    
                        st.divider()
                    
                        if submission:
                            # Mostrar información de la entrega
                            col_info, col_actions = st.columns([2, 1])
                        
                            with col_info:
                                st.success(f"📤 Entregado el: {submission.get('submission_date', 'No especificado')}")
                            
                                if submission.get('teacher_feedback'):
                                    st.info(f"💬 Feedback del profesor: {submission['teacher_feedback']}")
                            
                                if submission.get('ai_feedback'):
                                    st.info(f"🤖 Feedback IA: {submission['ai_feedback']}")
                        
                            # Mostrar archivo descargable
                            if submission.get('file_blob'):
                                file_name = submission.get('file_name') or 'entrega.bin'
                                st.download_button(
                                    f"📥 Descargar mi entrega ({file_name})",
                                    submission['file_blob'],
                                    file_name,
                                    key=f"dl_sub_{task['id']}"
                                )
                        
                            # Mostrar código si es tipo código
                            if submission.get('code') and task.get('submission_type') == 'code':
                                with st.expander("👁️ Ver código entregado"):
                                    st.code(submission['code'], language='python')
                        else:
                            # Mostrar mensaje si no puede entregar
                            if not is_valid:
                                if "Tiempo de entrega vencido" in validation_msg:
                                    show_time_expired_message()
                                else:
                                    st.error(f"**{validation_msg}**")
                            else:
                                # Formulario de entrega con validaciones
                                with st.form(f"submit_task_{task['id']}", clear_on_submit=False):
                                    st.markdown("### 📤 Entregar Tarea")
                                
                                    code_text = None
                                    file_data = None
                                    file_name = None
                                
                                    if task.get('submission_type') == 'code':
                                        code_text = st.text_area(
                                            "📝 Código",
                                            height=200,
                                            placeholder="Pega tu código aquí...",
                                            key=f"code_{task['id']}",
                                            help="Escribe o pega tu código fuente"
                                        )
                                    else:
                                        uploaded_file = st.file_uploader(
                                            "📎 Subir archivo",
                                            type=['pdf', 'txt', 'py', 'java', 'cpp', 'js', 'zip', 'doc', 'docx'],
                                            key=f"file_{task['id']}",
                                            help="Sube tu archivo de entrega"
                                        )
                                        if uploaded_file:
                                            file_data = uploaded_file.getvalue()
                                            file_name = uploaded_file.name
                                
                                    col_submit, col_cancel = st.columns([2, 1])
                                
                                    submitted = col_submit.form_submit_button(
                                        "🚀 Enviar Tarea", 
                                        type="primary",
                                        disabled=not is_valid,
                                        help="Enviar tu tarea para calificación"
                                    )
                                
                                    if submitted:
                                        # Validar que haya contenido
                                        if (task.get('submission_type') == 'code' and not code_text.strip()) or \
                                           (task.get('submission_type') != 'code' and not file_data):
                                            show_submission_error("Por favor, completa la entrega según el tipo solicitado.")
                                        else:
                                            # Mostrar progreso
                                            progress_bar = show_submission_progress("Enviando tarea...")
                                        
                                            try:
                                                conn.execute("""
                                                    INSERT INTO submissions 
                                                    (task_id, student_id, code, file_blob, file_name, status, submission_date)
                                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                                """, (
                                                    task['id'],
                                                    u['username'],
                                                    code_text,
                                                    file_data,
                                                    file_name,
                                                    'submitted',
                                                    datetime.now()
                                                ))
                                                conn.commit()
                                                
                                                # ENGAGEMENT: Dar puntos por enviar tarea
                                                try:
                                                    from engagement import PointsManager, StatisticsManager
                                                    points = 30  # Puntos por enviar tarea
                                                    PointsManager.add_points(
                                                        u['username'], 
                                                        points, 
                                                        'task_submission',
                                                        f'Tarea enviada: {task["title"]}'
                                                    )
                                                    StatisticsManager.update_activity_calendar(
                                                        u['username'],
                                                        exercises=1,
                                                        points=points
                                                    )
                                                except Exception as e:
                                                    print(f"Error dando puntos: {e}")
                                            
                                                progress_bar.empty()
                                                show_submission_success("¡Tarea enviada exitosamente! +30 puntos")
                                                st.rerun()
                                            except Exception as e:
                                                progress_bar.empty()
                                                show_submission_error(f"Error al enviar: {str(e)}")

        with tabs[2]:  # Exámenes
            st.subheader("✅ Exámenes del Curso")
        
            all_exams_rows = conn.execute("""
                SELECT e.*, m.title as module_title
                FROM exams e 
                LEFT JOIN modules m ON e.module_id = m.id 
                WHERE e.course_id = ?
                ORDER BY e.created_at DESC
            """, (c['id'],)).fetchall()
            all_exams = [dict(r) for r in all_exams_rows]
        
            if not all_exams:
                st.info("� No hay exámenes programados.")
            else:
                for exam in all_exams:
                    module_tag = f"[{exam.get('module_title', 'General')}]"
                
                    # Verificar intentos previos y validación
                    attempt_row = conn.execute("""
                        SELECT score FROM exam_attempts 
                        WHERE exam_id = ? AND student_id = ?
                    """, (exam['id'], u['username'])).fetchone()
                    attempt = dict(attempt_row) if attempt_row else None
                
                    # Validar si puede tomar el examen
                    is_valid, validation_msg = validate_exam_time(conn, exam['id'], u['username'])
                
                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])
                    
                        col1.markdown(f"**{module_tag} {exam.get('title', 'Sin título')}**")
                        col1.caption(f"⏱️ Duración: {exam.get('duration_minutes', 0)} minutos")
                    
                        if exam.get('description'):
                            with col1.expander("📖 Descripción"):
                                st.markdown(exam['description'])
                    
                        if attempt:
                            col2.success(f"📊 Nota: {attempt.get('score', 0)}")
                        else:
                            # Botón de inicio con validación
                            if is_valid:
                                if col2.button("▶️ Iniciar", key=f"start_exam_{exam['id']}", type="primary"):
                                    st.session_state.exam_session = {
                                        'id': exam['id'],
                                        'start': datetime.now(),
                                        'dur': exam.get('duration_minutes', 60),
                                        'course_id': c['id']
                                    }
                                    st.rerun()
                            else:
                                col2.error("No disponible")
                                col1.caption(f"ℹ️ {validation_msg}")

        with tabs[3]:  # Foro (CORREGIDO: Limpia HTML roto)
            st.markdown("#### 💬 Foro de Discusión")
        
            # Publicar mensaje
            with st.form("student_post_form"):
                message = st.text_area("Escribe tu pregunta o comentario:", height=100)
            
                if st.form_submit_button("📤 Publicar"):
                    if message.strip():
                        # Guardamos el mensaje limpiando cualquier intento de inyección HTML
                        import html
                        safe_msg = html.escape(message.strip())
                        conn.execute("""
                            INSERT INTO forum_posts (course_id, user_id, message, date)
                            VALUES (?, ?, ?, ?)
                        """, (c['id'], u['username'], safe_msg, datetime.now()))
                        conn.commit()
                        st.success("✅ Mensaje publicado")
                        st.rerun()
                    else:
                        st.warning("Escribe un mensaje antes de publicar.")
        
            st.divider()
        
            # Mostrar mensajes
            posts_rows = conn.execute("""
                SELECT f.*, u.full_name, u.avatar, u.role 
                FROM forum_posts f 
                JOIN users u ON f.user_id = u.username 
                WHERE f.course_id = ? 
                ORDER BY f.date DESC 
                LIMIT 50
            """, (c['id'],)).fetchall()
            posts = [dict(r) for r in posts_rows]
        
            if not posts:
                st.info("💭 No hay mensajes en el foro. ¡Sé el primero en publicar!")
            else:
                for post in posts:
                    # Avatar
                    if post.get('avatar'):
                        b64_av = base64.b64encode(post['avatar']).decode()
                        img_html = f'<img src="data:image/png;base64,{b64_av}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;">'
                    else:
                        img_html = '<img src="https://cdn-icons-png.flaticon.com/512/847/847969.png" style="width:40px;height:40px;border-radius:50%;">'
                
                    # Estilo según si es propio o profesor
                    is_own = post['user_id'] == u['username']
                    is_teacher = post.get('role') == 'teacher'
                
                    bg_color = "#2b2d42" if is_own else "#2a2a2a" if is_teacher else "#1e1e1e"
                    border_style = "border-left: 4px solid #58a6ff;" if is_own else "border-left: 4px solid #ffc107;" if is_teacher else ""
                
                    # Limpiar y mostrar mensaje
                    import html as html_module
                    raw_msg = post.get('message', '')
                
                    # Eliminar etiquetas HTML (incluyendo multilinea)
                    clean_msg = re.sub(r'<[^>]*>', '', raw_msg, flags=re.DOTALL)
                    clean_msg = html_module.unescape(clean_msg)
                    display_msg = html_module.escape(clean_msg.strip()).replace('\n', '<br>')
                
                    badge = "👨‍🏫 Profe" if is_teacher else "Tú" if is_own else ""
                    badge_html = f'<span style="background:#444; padding:2px 6px; border-radius:4px; font-size:0.7em; margin-left:8px;">{badge}</span>' if badge else ""

                    post_html = (
                        f'<div style="display:flex;gap:10px;margin-top:10px;padding:15px;background:{bg_color};border-radius:10px;align-items:flex-start;{border_style}">'
                        f'{img_html}'
                        f'<div style="flex-grow:1;">'
                        f'<div style="font-weight:bold;font-size:0.9rem;color:#ddd;">'
                        f'{post.get("full_name","Usuario")} {badge_html}'
                        f'<span style="color:#aaa;font-weight:normal;font-size:0.8rem;float:right;">{post.get("date","")}</span>'
                        f'</div>'
                        f'<div style="margin-top:8px;font-size:0.95rem;line-height:1.5;color:#fff;">{display_msg}</div>'
                        f'</div></div>'
                    )
                    st.markdown(post_html, unsafe_allow_html=True)

        with tabs[4]:  # Personas
            # Profesor
            teacher_row = conn.execute("""
                SELECT u.* FROM courses c 
                JOIN users u ON c.teacher_id = u.username 
                WHERE c.id = ?
            """, (c['id'],)).fetchone()
            teacher = dict(teacher_row) if teacher_row else None
            
            if teacher:
                st.markdown("### 👨‍🏫 Profesor del Curso")
                with st.container(border=True):
                    col_avatar, col_info, col_action = st.columns([1, 3, 1])
                    
                    col_avatar.markdown(render_avatar(teacher.get('avatar'), 80), unsafe_allow_html=True)
                    
                    col_info.subheader(teacher.get('full_name', 'Sin nombre'))
                    if teacher.get('title'):
                        col_info.markdown(f"**{teacher['title']}**")
                    
                    if teacher.get('bio'):
                        col_info.markdown(teacher['bio'])
                    
                    # Botón para ver perfil completo
                    if col_action.button("👤 Ver Perfil", key=f"view_teacher_{teacher['username']}", type="secondary"):
                        st.session_state.profile_target = teacher.get('username')
                        st.session_state.profile_return_to = 'course'  # Guardar de dónde viene
                        st.session_state.view_mode = 'profile'
                        st.rerun()
            
            # Compañeros
            st.markdown("### 👥 Compañeros del Curso")
            
            classmates_rows = conn.execute("""
                SELECT u.* FROM enrollments e 
                JOIN users u ON e.student_id = u.username 
                WHERE e.course_id = ? 
                AND u.role = 'student'
                AND u.username != ?
                ORDER BY u.full_name
            """, (c['id'], u['username'])).fetchall()
            classmates = [dict(r) for r in classmates_rows]
            
            if not classmates:
                st.info("👤 Eres el único estudiante en este curso por ahora.")
            else:
                cols = st.columns(4)
                for i, classmate in enumerate(classmates):
                    with cols[i % 4]:
                        with st.container(border=True):
                            st.markdown(render_avatar(classmate.get('avatar')), unsafe_allow_html=True)
                            st.markdown(f"<div style='text-align: center; font-size: 0.9em;'>{classmate.get('full_name', 'Sin nombre')}</div>", 
                                      unsafe_allow_html=True)
                            
                            # Botón para ver perfil
                            if st.button("👤", key=f"view_classmate_{classmate['username']}", 
                                       help="Ver perfil", use_container_width=True):
                                st.session_state.profile_target = classmate.get('username')
                                st.session_state.profile_return_to = 'course'  # Guardar de dónde viene
                                st.session_state.view_mode = 'profile'
                                st.rerun()

        with tabs[5]:  # Notas
            st.subheader("📊 Mis Calificaciones en este Curso")
        
            # Calificaciones de tareas
            task_grades_rows = conn.execute("""
                SELECT t.title, s.final_grade, t.points, s.submission_date
                FROM tasks t 
                LEFT JOIN submissions s ON t.id = s.task_id AND s.student_id = ?
                WHERE t.course_id = ?
                ORDER BY t.due_date DESC
            """, (u['username'], c['id'])).fetchall()
            task_grades = [dict(r) for r in task_grades_rows]
        
            # Calificaciones de exámenes
            exam_grades_rows = conn.execute("""
                SELECT e.title, a.score, 
                       (SELECT SUM(points) FROM exam_questions WHERE exam_id = e.id) as total
                FROM exams e 
                LEFT JOIN exam_attempts a ON e.id = a.exam_id AND a.student_id = ?
                WHERE e.course_id = ?
            """, (u['username'], c['id'])).fetchall()
            exam_grades = [dict(r) for r in exam_grades_rows]
        
            # Crear tabla
            data = []
            for task in task_grades:
                grade = task.get('final_grade')
                points = task.get('points', 0)
                data.append({
                    "Actividad": task.get('title', 'Sin título'),
                    "Tipo": "📝 Tarea",
                    "Nota": f"{grade:.1f} / {points}" if grade is not None else f"0 / {points}",
                    "Porcentaje": f"{(grade/points*100):.1f}%" if grade is not None and points > 0 else "0%",
                    "Fecha": task.get('submission_date', '')
                })
        
            for exam in exam_grades:
                score = exam.get('score')
                total = exam.get('total', 0)
                data.append({
                    "Actividad": exam.get('title', 'Sin título'),
                    "Tipo": "✅ Examen",
                    "Nota": f"{score:.1f} / {total}" if score is not None else f"0 / {total}",
                    "Porcentaje": f"{(score/total*100):.1f}%" if score is not None and total > 0 else "0%",
                    "Fecha": ""
                })
        
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
            
                # Estadísticas
                if len(data) > 0:
                    col_stats = st.columns(4)
                    completed = sum(1 for d in data if "0 /" not in d["Nota"])
                    avg_grade = sum(float(d["Porcentaje"].replace('%', '')) for d in data if d["Porcentaje"] != "0%") / len(data) if len(data) > 0 else 0
                
                    col_stats[0].metric("📊 Total Actividades", len(data))
                    col_stats[1].metric("✅ Completadas", completed)
                    col_stats[2].metric("📈 Promedio", f"{avg_grade:.1f}%")
                    col_stats[3].metric("🎯 Rendimiento", 
                                      "Excelente" if avg_grade >= 90 else 
                                      "Bueno" if avg_grade >= 70 else 
                                      "Regular" if avg_grade >= 60 else "Bajo")
            else:
                st.info("📊 No hay calificaciones registradas aún.")
    
    # Fin del bloque de pestañas (solo si NO hay examen activo)
    return

def render_regular_course_card(course, index):
    """Renderiza tarjeta de curso regular"""
    # Descripción truncada
    desc = course.get('description', 'Sin descripción')
    # Limpiar HTML: primera pasada directa, segunda despues de decodificar entidades
    desc = re.sub(r'<[^>]+>', '', desc).strip()
    desc = desc.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    desc = re.sub(r'<[^>]+>', '', desc).strip()
    if len(desc) > 100:
        desc = desc[:100] + '...'
    
    # Imagen del curso
    if course.get('cover_image'):
        img_src = f"data:image/png;base64,{base64.b64encode(course['cover_image']).decode()}"
    else:
        img_src = "https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=400&h=200&fit=crop"
    
    # Nombre del profesor
    t_name = course['teacher_name'] if course.get('teacher_name') else "Sin asignar"
    
    # Tarjeta del curso
    st.markdown(f"""
    <div style="
        border: 1px solid #444;
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 15px;
        background-color: #1e1e1e;
        height: 320px;
        display: flex;
        flex-direction: column;
        transition: transform 0.3s ease;
    ">
        <div style="height: 140px; overflow: hidden; background: #000;">
            <img src="{img_src}" 
                 style="width: 100%; height: 100%; object-fit: cover; opacity: 0.8;">
        </div>
        <div style="padding: 15px; flex-grow: 1;">
            <div style="color: #58a6ff; font-size: 0.75rem; font-weight: bold;">
                👨‍🏫 {course['code']}
            </div>
            <h4 style="margin: 5px 0; color: white; font-size: 1rem;">
                {course['name']}
            </h4>
            <div style="color: #aaa; font-size: 0.85rem; margin-bottom: 10px;">
                👨‍🏫 {t_name}
            </div>
            <p style="font-size: 0.8rem; color: #888; line-height: 1.4;">
                {desc}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button(f"🚀 Entrar al Curso", 
               key=f"go_regular_{course['id']}_{index}", 
               use_container_width=True, 
               type="secondary"):
        st.session_state.active_course = dict(course)
        st.session_state.view_mode = 'course'
        st.rerun()

def render_ai_course_card(conn, ai_course, index, user):
    """Renderiza tarjeta de curso IA"""
    language = ai_course['language']
    level = ai_course['level']
    progress = ai_course['progress_percentage'] or 0
    
    # Emojis por lenguaje
    lang_emojis = {
        'Python': '🐍', 'JavaScript': '🟨', 'Java': '☕', 'C++': '⚡',
        'SQL': '🗃️', 'NoSQL': '📊', 'HTML/CSS': '🎨', 'C#': '💜',
        'PHP': '🐘', 'Ruby': '💎'
    }
    
    # Emojis por nivel
    level_emojis = {"principiante": "🌱", "intermedio": "🌿", "avanzado": "🌳"}
    
    # Color por estado
    status_colors = {"active": "#28a745", "paused": "#ffc107", "completed": "#17a2b8"}
    status_text = {"active": "Activo", "paused": "Pausado", "completed": "Completado"}
    
    # Imagen por lenguaje
    lang_images = {
        'Python': 'https://images.unsplash.com/photo-1526379095098-d400fd0bf935?w=400&h=200&fit=crop',
        'JavaScript': 'https://images.unsplash.com/photo-1627398242454-45a1465c2479?w=400&h=200&fit=crop',
        'Java': 'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?w=400&h=200&fit=crop',
        'default': 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400&h=200&fit=crop'
    }
    
    img_src = lang_images.get(language, lang_images['default'])
    
    # Tarjeta del curso IA
    st.markdown(f"""
    <div style="
        border: 2px solid #ff6b6b;
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 15px;
        background: linear-gradient(135deg, #1e1e1e 0%, #2d1b69 100%);
        height: 320px;
        display: flex;
        flex-direction: column;
        transition: transform 0.3s ease;
        position: relative;
    ">
        <div style="position: absolute; top: 10px; right: 10px; background: rgba(255,107,107,0.9); color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: bold;">
            🤖 IA
        </div>
        <div style="height: 140px; overflow: hidden; background: #000;">
            <img src="{img_src}" 
                 style="width: 100%; height: 100%; object-fit: cover; opacity: 0.7;">
        </div>
        <div style="padding: 15px; flex-grow: 1;">
            <div style="color: #ff6b6b; font-size: 0.75rem; font-weight: bold;">
                🤖 CURSO IA • {level_emojis.get(level, '📊')} {level.upper()}
            </div>
            <h4 style="margin: 5px 0; color: white; font-size: 1rem;">
                {lang_emojis.get(language, '💻')} {language}
            </h4>
            <div style="color: #aaa; font-size: 0.85rem; margin-bottom: 8px;">
                📊 Progreso: {progress:.1f}%
            </div>
            <div style="background: #333; border-radius: 10px; height: 6px; margin-bottom: 8px;">
                <div style="background: linear-gradient(90deg, #ff6b6b, #4ecdc4); height: 100%; border-radius: 10px; width: {progress}%;"></div>
            </div>
            <div style="color: #ccc; font-size: 0.8rem;">
                🎯 Evaluación: {ai_course.get('assessment_score', 0):.1f}%<br>
                📅 Creado: {ai_course['created_at'][:10]}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Botones de acción
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(f"🚀 Entrar", 
                   key=f"go_ai_{ai_course['id']}_{index}", 
                   use_container_width=True, 
                   type="primary"):
            st.cache_data.clear()  # Limpiar caché al entrar al curso
            # Limpiar estado del examen final al cambiar de curso
            exam_keys = ['final_exam', 'final_exam_started', 'exam_responses', 'exam_page', 'temp_responses']
            for key in exam_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.active_ai_course = ai_course['id']
            st.session_state.view_mode = 'ai_course'
            st.rerun()
    
    with col2:
        if st.button(f"⚙️ Config", 
                   key=f"config_ai_{ai_course['id']}_{index}", 
                   use_container_width=True):
            st.cache_data.clear()  # Limpiar caché al entrar a configuración
            # Limpiar estado del examen final al cambiar de curso
            exam_keys = ['final_exam', 'final_exam_started', 'exam_responses', 'exam_page', 'temp_responses']
            for key in exam_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.active_ai_course = ai_course['id']
            st.session_state.view_mode = 'ai_course_config'  # Vista especial de configuración
            st.rerun()


def render_regular_course_card(course, index):
    """Renderiza tarjeta de curso regular"""
    # Descripción truncada
    desc = course.get('description', 'Sin descripción')
    # Limpiar HTML: primera pasada directa, segunda despues de decodificar entidades
    desc = re.sub(r'<[^>]+>', '', desc).strip()
    desc = desc.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    desc = re.sub(r'<[^>]+>', '', desc).strip()
    if len(desc) > 100:
        desc = desc[:100] + '...'
    
    # Imagen del curso
    if course.get('cover_image'):
        img_src = f"data:image/png;base64,{base64.b64encode(course['cover_image']).decode()}"
    else:
        img_src = "https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=400&h=200&fit=crop"
    
    # Nombre del profesor
    t_name = course['teacher_name'] if course.get('teacher_name') else "Sin asignar"
    
    # Tarjeta del curso
    st.markdown(f"""
    <div style="
        border: 1px solid #444;
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 15px;
        background-color: #1e1e1e;
        height: 320px;
        display: flex;
        flex-direction: column;
        transition: transform 0.3s ease;
    ">
        <div style="height: 140px; overflow: hidden; background: #000;">
            <img src="{img_src}" 
                 style="width: 100%; height: 100%; object-fit: cover; opacity: 0.8;">
        </div>
        <div style="padding: 15px; flex-grow: 1;">
            <div style="color: #58a6ff; font-size: 0.75rem; font-weight: bold;">
                👨‍🏫 {course['code']}
            </div>
            <h4 style="margin: 5px 0; color: white; font-size: 1rem;">
                {course['name']}
            </h4>
            <div style="color: #aaa; font-size: 0.85rem; margin-bottom: 10px;">
                👨‍🏫 {t_name}
            </div>
            <p style="font-size: 0.8rem; color: #888; line-height: 1.4;">
                {desc}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button(f"🚀 Entrar al Curso", 
               key=f"go_regular_{course['id']}_{index}", 
               use_container_width=True, 
               type="secondary"):
        st.session_state.active_course = dict(course)
        st.session_state.view_mode = 'course'
        st.rerun()

    # ==============================================================================
    # VISTA 2: DENTRO DEL CURSO
    # ==============================================================================
    if st.session_state.view_mode == 'course':
        c = st.session_state.active_course
        
        # Verificación de seguridad
        if c is None:
            st.error("❌ No hay curso seleccionado")
            if st.button("🏠 Volver al Dashboard"):
                st.session_state.view_mode = 'dashboard'
                st.rerun()
            return
        
        # --- MODO EXAMEN ACTIVO - PANTALLA COMPLETA REAL ---
        if st.session_state.get('exam_session') and st.session_state.exam_session.get('course_id') == c['id']:
            # OCULTAR SIDEBAR COMPLETAMENTE
            st.markdown("""
            <style>
                [data-testid="stSidebar"] {
                    display: none !important;
                }
                .main .block-container {
                    padding-left: 1rem !important;
                    padding-right: 1rem !important;
                    max-width: 100% !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
            es = st.session_state.exam_session
            
            # Verificar si el examen sigue válido
            is_valid, validation_msg = validate_exam_time(conn, es['id'], u['username'])
            if not is_valid:
                st.error(validation_msg)
                del st.session_state.exam_session
                time.sleep(2)
                st.rerun()
                return
            
            # Obtener información del examen
            exam_info = conn.execute("SELECT title FROM exams WHERE id = ?", (es['id'],)).fetchone()
            exam_title = exam_info[0] if exam_info else "Examen"
            
            # Header minimalista del examen
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 20px;
                text-align: center;
                border: 2px solid #444;
            ">
                <h2 style="margin: 0; color: #58a6ff;">📝 {exam_title}</h2>
                <p style="margin: 5px 0 0 0; color: #aaa; font-size: 0.9em;">
                    ⚠️ Modo Examen Activo - No cierres esta ventana ni recargues la página
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            now = datetime.now()
            end_time = es['start'] + timedelta(minutes=es['dur'])
            seconds_left = max(0, int((end_time - now).total_seconds()))
            
            # Función para finalizar examen con mejoras
            def finish_exam():
                st.session_state.exam_finishing = True
                
                # Mostrar indicador de progreso
                progress_bar = show_submission_progress("Enviando examen... Por favor espera.")
                
                try:
                    # Obtener preguntas
                    qs_final_rows = conn.execute(
                        "SELECT * FROM exam_questions WHERE exam_id = ?",
                        (es['id'],)
                    ).fetchall()
                    qs_final = [dict(r) for r in qs_final_rows]
                    
                    total_score = 0
                    details_list = []
                    
                    # Barra de progreso para calificación
                    progress_bar.progress(0, text="📊 Calificando respuestas...")
                    
                    for idx, q in enumerate(qs_final):
                        progress = (idx + 1) / len(qs_final)
                        progress_bar.progress(progress, text=f"Pregunta {idx + 1} de {len(qs_final)}")
                        
                        key_name = f"ans_{es['id']}_{q['id']}"
                        student_ans = st.session_state.get(key_name, None)
                        
                        qtype = q.get('question_type', 'multiple_choice')
                        
                        # Calificación múltiple choice
                        if qtype == 'multiple_choice':
                            earned = 0
                            feedback = "Respuesta incorrecta"
                            try:
                                opts = json.loads(q['options_json'])
                                if student_ans and opts.index(student_ans) == q['correct_index']:
                                    earned = q['points']
                                    feedback = "¡Correcto!"
                            except:
                                pass
                            total_score += earned
                            details_list.append({
                                "q_id": q['id'],
                                "question": q['question'],
                                "type": "multiple_choice",
                                "answer": student_ans,
                                "score": earned,
                                "max_points": q['points'],
                                "ai_feedback": feedback
                            })
                        
                        # Calificación texto abierto con IA
                        elif qtype == 'open_text':
                            earned, feedback = ai_grade_open_question(
                                model, 
                                q['question'], 
                                student_ans, 
                                q['points']
                            )
                            total_score += earned
                            details_list.append({
                                "q_id": q['id'],
                                "question": q['question'],
                                "type": "open_text",
                                "answer": student_ans,
                                "score": earned,
                                "max_points": q['points'],
                                "ai_feedback": feedback
                            })
                    
                    progress_bar.empty()
                    
                    # Guardar intento
                    json_details = json.dumps(details_list)
                    conn.execute("""
                        INSERT INTO exam_attempts 
                        (exam_id, student_id, score, start_time, end_time, details_json) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (es['id'], u['username'], total_score, es['start'], datetime.now(), json_details))
                    conn.commit()
                    
                    # Limpiar sesión de examen
                    del st.session_state.exam_session
                    if 'exam_finishing' in st.session_state:
                        del st.session_state.exam_finishing
                    
                    # Obtener título del examen
                    exam_info = conn.execute("SELECT title FROM exams WHERE id = ?", (es['id'],)).fetchone()
                    exam_title = exam_info[0] if exam_info else "Examen"
                    
                    # Mostrar resultados
                    show_submission_success("¡Examen Finalizado!")
                    st.markdown(f"### 📊 Puntuación Obtenida: **{total_score}**")
                    
                    # Guardar detalles en session_state para mostrar persistentemente
                    st.session_state.exam_results = {
                        'score': total_score,
                        'details': details_list,
                        'exam_title': exam_title,
                        'show_details': False
                    }
                    
                    st.rerun()
                    
                except Exception as e:
                    progress_bar.empty()
                    show_submission_error(f"Error al enviar examen: {str(e)}")
                    time.sleep(3)
                    st.rerun()

            # Temporizador que se actualiza automáticamente
            if seconds_left <= 0:
                st.error("⏰ ¡TIEMPO AGOTADO! Enviando respuestas...")
                finish_exam()
                st.stop()

            # Display timer que se actualiza automáticamente
            minutes = seconds_left // 60
            seconds = seconds_left % 60
            
            # Color del temporizador según tiempo restante
            timer_color = "#ff4b4b" if minutes < 5 else "#f0ad4e" if minutes < 15 else "#5cb85c"
            
            # Timer con auto-refresh usando JavaScript
            timer_html = f"""
            <div id="exam-timer" style="
                font-family: 'Courier New', monospace;
                color: {timer_color};
                text-align: center;
                font-size: 28px;
                font-weight: bold;
                border: 3px solid #444;
                border-radius: 15px;
                padding: 20px;
                background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
                margin-bottom: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            ">
                ⏱️ TIEMPO RESTANTE: <span id="timer-display">{minutes:02d}:{seconds:02d}</span>
            </div>
            
            <script>
            let timeLeft = {seconds_left};
            let warningShown = false;
            
            function updateTimer() {{
                if (timeLeft <= 0) {{
                    document.getElementById('timer-display').innerHTML = '00:00';
                    alert('⏰ ¡Tiempo agotado! El examen se enviará automáticamente.');
                    // Buscar y hacer clic en el botón de enviar
                    const submitButtons = document.querySelectorAll('button');
                    submitButtons.forEach(button => {{
                        if (button.textContent.includes('Terminar y Enviar')) {{
                            button.click();
                        }}
                    }});
                    return;
                }}
                
                const minutes = Math.floor(timeLeft / 60);
                const seconds = timeLeft % 60;
                const display = minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
                
                const timerElement = document.getElementById('timer-display');
                if (timerElement) {{
                    timerElement.innerHTML = display;
                    
                    // Cambiar color según tiempo restante
                    const timerContainer = document.getElementById('exam-timer');
                    if (timerContainer) {{
                        if (minutes < 5) {{
                            timerContainer.style.color = '#ff4b4b';
                        }} else if (minutes < 15) {{
                            timerContainer.style.color = '#f0ad4e';
                        }} else {{
                            timerContainer.style.color = '#5cb85c';
                        }}
                    }}
                }}
                
                // Advertencia a 5 minutos
                if (timeLeft <= 300 && !warningShown) {{
                    warningShown = true;
                    alert('⚠️ ¡Solo quedan 5 minutos para terminar el examen!');
                }}
                
                timeLeft--;
            }}
            
            // Actualizar cada segundo
            const timerInterval = setInterval(updateTimer, 1000);
            
            // Limpiar interval al salir
            window.addEventListener('beforeunload', () => {{
                clearInterval(timerInterval);
            }});
            </script>
            """
            
            st.markdown(timer_html, unsafe_allow_html=True)
            
            # Forzar actualización cada 30 segundos para sincronizar con el servidor
            if 'last_sync' not in st.session_state:
                st.session_state.last_sync = time.time()
            
            if time.time() - st.session_state.last_sync > 30:
                st.session_state.last_sync = time.time()
                st.rerun()
            
            # Preguntas del examen en contenedor limpio
            qs_rows = conn.execute(
                "SELECT * FROM exam_questions WHERE exam_id = ?",
                (es['id'],)
            ).fetchall()
            qs = [dict(r) for r in qs_rows]
            
            # NUEVO: Aleatorizar preguntas para cada estudiante
            # Usar el ID del estudiante como semilla para que siempre vea el mismo orden
            import random
            import hashlib
            
            # Crear semilla única basada en exam_id + student_id
            seed_string = f"{es['id']}_{user['username']}"
            seed_value = int(hashlib.md5(seed_string.encode()).hexdigest(), 16) % (10 ** 8)
            
            # Aleatorizar preguntas con la semilla
            random.seed(seed_value)
            random.shuffle(qs)
            
            # También aleatorizar opciones de cada pregunta de opción múltiple
            for q in qs:
                if q.get('question_type') == 'multiple_choice':
                    try:
                        opts = json.loads(q['options_json'])
                        correct_idx = q.get('correct_index', 0)
                        
                        # Crear lista de índices y mezclar
                        indices = list(range(len(opts)))
                        random.shuffle(indices)
                        
                        # Reordenar opciones
                        new_opts = [opts[i] for i in indices]
                        
                        # Encontrar nuevo índice de la respuesta correcta
                        new_correct_idx = indices.index(correct_idx)
                        
                        # Actualizar en el diccionario
                        q['options_json'] = json.dumps(new_opts)
                        q['correct_index'] = new_correct_idx
                    except:
                        pass  # Si hay error, mantener orden original
            
            # Restaurar semilla aleatoria
            random.seed()
            
            # Información del progreso
            answered_count = sum(1 for q in qs if st.session_state.get(f"ans_{es['id']}_{q['id']}"))
            
            st.markdown(f"""
            <div style="
                background: #2a2a2a;
                padding: 10px;
                border-radius: 8px;
                margin-bottom: 15px;
                text-align: center;
            ">
                📝 <strong>{len(qs)} Preguntas</strong> | 
                ✅ <strong>{answered_count} Respondidas</strong> | 
                ⏳ <strong>{len(qs) - answered_count} Pendientes</strong>
            </div>
            """, unsafe_allow_html=True)
            
            # Preguntas del examen
            for i, q in enumerate(qs):
                # Indicador de pregunta respondida
                is_answered = bool(st.session_state.get(f"ans_{es['id']}_{q['id']}"))
                status_icon = "✅" if is_answered else "⏳"
                
                with st.container(border=True):
                    st.markdown(f"#### {status_icon} Pregunta {i+1} de {len(qs)} **({q['points']} puntos)**")
                    st.markdown(f"**{q['question']}**")
                    
                    qtype = q.get('question_type', 'multiple_choice')
                    
                    if qtype == 'open_text':
                        st.text_area("✍️ Tu respuesta:", 
                                   key=f"ans_{es['id']}_{q['id']}",
                                   height=150,
                                   placeholder="Escribe tu respuesta aquí de forma clara y completa...",
                                   help="Responde de forma clara y completa")
                    else:
                        try:
                            opts = json.loads(q['options_json'])
                            st.radio("Selecciona la opción correcta:",
                                   opts,
                                   key=f"ans_{es['id']}_{q['id']}",
                                   index=None,
                                   help="Elige una opción")
                        except:
                            st.error("Error cargando opciones de la pregunta")
            
            st.markdown("---")
            
            # Botones de acción del examen
            col_submit, col_progress, col_emergency = st.columns([2, 1, 1])
            
            with col_submit:
                if st.button("✅ Terminar y Enviar Examen", 
                           type="primary", 
                           width='stretch',
                           help="Haz clic para enviar tu examen"):
                    finish_exam()
            
            with col_progress:
                progress_percentage = (answered_count / len(qs)) * 100 if len(qs) > 0 else 0
                st.metric("Progreso", f"{progress_percentage:.0f}%")
            
            with col_emergency:
                if st.button("🚨 Salir (Emergencia)", 
                           type="secondary", 
                           width='stretch',
                           help="Solo usar en caso de emergencia - perderás el progreso"):
                    if st.session_state.get('confirm_exit_exam'):
                        del st.session_state.exam_session
                        if 'confirm_exit_exam' in st.session_state:
                            del st.session_state.confirm_exit_exam
                        st.warning("⚠️ Has salido del examen. El progreso se ha perdido.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.session_state.confirm_exit_exam = True
                        st.error("⚠️ Haz clic nuevamente para confirmar que quieres salir del examen")
            
            return  # Importante: no mostrar nada más durante el examen

        # --- VISTA NORMAL DEL CURSO ---
        if st.button("← Volver al Dashboard", type="tertiary"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        
        # --- MOSTRAR RESULTADOS DE EXAMEN SI EXISTEN ---
        if st.session_state.get('exam_results'):
            results = st.session_state.exam_results
            
            st.success(f"✅ Examen '{results['exam_title']}' completado")
            st.markdown(f"### 📊 Puntuación Obtenida: **{results['score']}**")
            
            col_details, col_close = st.columns([3, 1])
            
            with col_details:
                if st.button("📋 Ver/Ocultar Detalles de Respuestas", type="secondary"):
                    st.session_state.exam_results['show_details'] = not st.session_state.exam_results.get('show_details', False)
                    st.rerun()
            
            with col_close:
                if st.button("❌ Cerrar Resultados", type="tertiary"):
                    del st.session_state.exam_results
                    st.rerun()
            
            # Mostrar detalles si está activado
            if st.session_state.exam_results.get('show_details', False):
                with st.container(border=True):
                    st.markdown("#### 📋 Detalles de las Respuestas")
                    for i, detail in enumerate(results['details']):
                        with st.expander(f"Pregunta {i+1}: {detail['score']}/{detail['max_points']} puntos", expanded=False):
                            st.markdown(f"**Pregunta:** {detail['question']}")
                            st.markdown(f"**Tu respuesta:** {detail['answer'] or 'Sin responder'}")
                            st.markdown(f"**Puntos obtenidos:** {detail['score']}/{detail['max_points']}")
                            st.markdown(f"**Feedback:** {detail['ai_feedback']}")
            
            st.markdown("---")
        
        # Header del curso
        if c.get('cover_image'):
            b64_img = base64.b64encode(c['cover_image']).decode()
            st.markdown(f"""
            <div style="
                width: 100%;
                height: 200px;
                overflow: hidden;
                border-radius: 12px;
                margin-bottom: 20px;
            ">
                <img src="data:image/png;base64,{b64_img}" 
                     style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            """, unsafe_allow_html=True)
        
        st.title(f"📚 {c['name']}")
        st.caption(f"🔖 Código: {c['code']} | 📖 {re.sub(r'<[^>]+>', '', c.get('description', 'Sin descripción')).strip()}")
        
        # Tabs del curso
        tabs = st.tabs([
            "📚 Módulos", 
            "📝 Tareas", 
            "✅ Exámenes", 
            "💬 Foro", 
            "👥 Personas", 
            "📊 Mis Notas"
        ])

        with tabs[0]:  # Módulos
            st.subheader("📁 Contenido del Curso")
            
            # Obtener módulos
            modules_rows = conn.execute("""
                SELECT * FROM modules 
                WHERE course_id = ? 
                ORDER BY order_index, id
            """, (c['id'],)).fetchall()
            modules = [dict(r) for r in modules_rows]
            
            if not modules:
                st.info("📭 El profesor aún no ha publicado contenido.")
            else:
                for module in modules:
                    with st.expander(f"📌 {module['title']}", expanded=True):
                        if module.get('description'):
                            st.markdown(module['description'])
                        
                        # Materiales del módulo
                        materials_rows = conn.execute("""
                            SELECT * FROM course_materials 
                            WHERE module_id = ? 
                            ORDER BY order_index
                        """, (module['id'],)).fetchall()
                        materials = [dict(r) for r in materials_rows]
                        
                        for material in materials:
                            with st.container(border=True):
                                col_icon, col_content, col_action = st.columns([0.5, 4, 1])
                                
                                # Icono según tipo
                                icon = {
                                    'pdf': '📄',
                                    'video': '🎬',
                                    'text': '📝',
                                    'link': '🔗',
                                    'quiz': '❓'
                                }.get(material.get('type'), '📁')
                                
                                col_icon.markdown(f"## {icon}")
                                col_content.markdown(f"**{material['title']}**")
                                
                                if material.get('content_blob'):
                                    file_name = material.get('file_name') or f"material_{material['id']}"
                                    col_action.download_button(
                                        "⬇️ Descargar",
                                        material['content_blob'],
                                        file_name,
                                        key=f"dl_{material['id']}"
                                    )
                                    
                                    if material.get('type') == 'pdf':
                                        if col_action.checkbox("👁️", key=f"v_{material['id']}"):
                                            display_pdf(material['content_blob'])

        with tabs[1]:  # Tareas
            st.subheader("📋 Lista de Tareas")
            
            all_tasks_rows = conn.execute("""
                SELECT t.*, m.title as module_title
                FROM tasks t 
                LEFT JOIN modules m ON t.module_id = m.id 
                WHERE t.course_id = ? 
                ORDER BY t.due_date DESC
            """, (c['id'],)).fetchall()
            all_tasks = [dict(r) for r in all_tasks_rows]
            
            if not all_tasks:
                st.info("🎯 No hay tareas asignadas en este curso.")
            else:
                for task in all_tasks:
                    # Validar si puede entregar
                    is_valid, validation_msg = validate_task_submission(conn, task['id'], u['username'])
                    
                    # Verificar entrega
                    submission_row = conn.execute("""
                        SELECT * FROM submissions 
                        WHERE task_id = ? AND student_id = ?
                    """, (task['id'], u['username'])).fetchone()
                    submission = dict(submission_row) if submission_row else None
                    
                    status_msg = ""
                    status_color = ""
                    if submission:
                        if submission.get('status') == 'graded':
                            status_msg = f"✅ Calificado: {submission.get('final_grade', 0)}/{task.get('points', 0)}"
                            status_color = "success"
                        else:
                            status_msg = "📩 Entregado (pendiente de calificación)"
                            status_color = "info"
                    else:
                        if is_valid:
                            status_msg = "⚠️ Pendiente"
                            status_color = "warning"
                        else:
                            status_msg = f"⛔ {validation_msg}"
                            status_color = "error"
                    
                    module_tag = f"[{task.get('module_title', 'General')}]"
                    
                    with st.expander(f"{module_tag} {task.get('title', 'Sin título')} | {status_msg}"):
                        st.caption(f"📅 Vence: {task.get('due_date', 'No especificada')} | 💯 Puntos: {task.get('points', 0)}")
                        if task.get('description'):
                            st.markdown(task['description'])
                        
                        if task.get('criteria'):
                            with st.expander("📋 Criterios de evaluación"):
                                st.markdown(task['criteria'])
                        
                        st.divider()
                        
                        if submission:
                            # Verificar si puede editar la entrega
                            can_edit = False
                            edit_reason = ""
                            
                            # Solo puede editar si no está calificada
                            if submission.get('status') == 'graded':
                                edit_reason = "La tarea ya fue calificada por el profesor"
                            else:
                                # Verificar si no ha vencido el plazo
                                due_date = task.get('due_date')
                                if due_date:
                                    if isinstance(due_date, str):
                                        try:
                                            due_date = datetime.strptime(due_date, '%Y-%m-%d')
                                        except:
                                            due_date = datetime.now()
                                    
                                    if datetime.now().date() > due_date.date():
                                        edit_reason = "El plazo de entrega ha vencido"
                                    else:
                                        can_edit = True
                                else:
                                    can_edit = True  # Si no hay fecha límite, puede editar
                            
                            # Mostrar información de la entrega
                            col_info, col_actions = st.columns([2, 1])
                            
                            with col_info:
                                st.success(f"📤 Entregado el: {submission.get('submission_date', 'No especificado')}")
                                
                                if submission.get('teacher_feedback'):
                                    st.info(f"💬 Feedback del profesor: {submission['teacher_feedback']}")
                                
                                if submission.get('ai_feedback'):
                                    st.info(f"🤖 Feedback IA: {submission['ai_feedback']}")
                            
                            with col_actions:
                                if can_edit:
                                    if st.button("✏️ Editar Entrega", key=f"edit_{task['id']}", type="secondary"):
                                        st.session_state[f"editing_task_{task['id']}"] = True
                                        st.rerun()
                                    
                                    if st.button("🗑️ Eliminar Entrega", key=f"delete_{task['id']}", type="secondary"):
                                        if st.session_state.get(f"confirm_delete_{task['id']}"):
                                            # Confirmar eliminación
                                            try:
                                                conn.execute("DELETE FROM submissions WHERE task_id = ? AND student_id = ?", 
                                                           (task['id'], u['username']))
                                                conn.commit()
                                                st.success("✅ Entrega eliminada correctamente")
                                                del st.session_state[f"confirm_delete_{task['id']}"]
                                                time.sleep(1)
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Error al eliminar: {str(e)}")
                                        else:
                                            st.session_state[f"confirm_delete_{task['id']}"] = True
                                            st.warning("⚠️ Haz clic nuevamente para confirmar la eliminación")
                                else:
                                    st.caption(f"🔒 No se puede editar: {edit_reason}")
                            
                            # Mostrar archivo descargable
                            if submission.get('file_blob'):
                                file_name = submission.get('file_name') or 'entrega.bin'
                                st.download_button(
                                    f"📥 Descargar mi entrega ({file_name})",
                                    submission['file_blob'],
                                    file_name,
                                    key=f"dl_sub_{task['id']}"
                                )
                            
                            # Mostrar código si es tipo código
                            if submission.get('code') and task.get('submission_type') == 'code':
                                with st.expander("👁️ Ver código entregado"):
                                    st.code(submission['code'], language='python')
                            
                            # Mostrar información adicional de la entrega
                            with st.expander("📊 Detalles de la entrega"):
                                col_det1, col_det2 = st.columns(2)
                                with col_det1:
                                    st.write(f"**📅 Fecha de entrega:** {submission.get('submission_date', 'No especificado')}")
                                    st.write(f"**📋 Estado:** {submission.get('status', 'Enviado').title()}")
                                    if submission.get('final_grade') is not None:
                                        st.write(f"**📊 Calificación:** {submission.get('final_grade', 0)}/{task.get('points', 0)}")
                                
                                with col_det2:
                                    if submission.get('file_name'):
                                        st.write(f"**📎 Archivo:** {submission['file_name']}")
                                    if submission.get('code'):
                                        lines_count = len(submission['code'].split('\n'))
                                        st.write(f"**💻 Líneas de código:** {lines_count}")
                                    
                                    # Mostrar si puede editar o no
                                    if can_edit:
                                        st.success("✅ Puedes editar esta entrega")
                                    else:
                                        st.warning(f"🔒 {edit_reason}")
                            
                            # Formulario de edición si está en modo edición
                            if st.session_state.get(f"editing_task_{task['id']}", False):
                                st.markdown("---")
                                st.markdown("### ✏️ Editar Entrega")
                                
                                with st.form(f"edit_task_{task['id']}", clear_on_submit=False):
                                    new_code_text = None
                                    new_file_data = None
                                    new_file_name = None
                                    
                                    if task.get('submission_type') == 'code':
                                        new_code_text = st.text_area(
                                            "📝 Nuevo Código",
                                            value=submission.get('code', ''),
                                            height=200,
                                            key=f"edit_code_{task['id']}",
                                            help="Modifica tu código aquí"
                                        )
                                    else:
                                        st.info(f"📎 Archivo actual: {submission.get('file_name', 'Sin nombre')}")
                                        new_uploaded_file = st.file_uploader(
                                            "📎 Subir nuevo archivo (opcional - deja vacío para mantener el actual)",
                                            type=['pdf', 'txt', 'py', 'java', 'cpp', 'js', 'zip', 'doc', 'docx'],
                                            key=f"edit_file_{task['id']}",
                                            help="Sube un nuevo archivo o deja vacío para mantener el actual"
                                        )
                                        if new_uploaded_file:
                                            new_file_data = new_uploaded_file.getvalue()
                                            new_file_name = new_uploaded_file.name
                                    
                                    col_save, col_cancel = st.columns([1, 1])
                                    
                                    if col_save.form_submit_button("💾 Guardar Cambios", type="primary"):
                                        try:
                                            # Actualizar la entrega
                                            if task.get('submission_type') == 'code':
                                                conn.execute("""
                                                    UPDATE submissions 
                                                    SET code = ?, submission_date = ?
                                                    WHERE task_id = ? AND student_id = ?
                                                """, (new_code_text, datetime.now(), task['id'], u['username']))
                                            else:
                                                # Solo actualizar archivo si se subió uno nuevo
                                                if new_file_data:
                                                    conn.execute("""
                                                        UPDATE submissions 
                                                        SET file_blob = ?, file_name = ?, submission_date = ?
                                                        WHERE task_id = ? AND student_id = ?
                                                    """, (new_file_data, new_file_name, datetime.now(), task['id'], u['username']))
                                                else:
                                                    # Solo actualizar fecha de modificación
                                                    conn.execute("""
                                                        UPDATE submissions 
                                                        SET submission_date = ?
                                                        WHERE task_id = ? AND student_id = ?
                                                    """, (datetime.now(), task['id'], u['username']))
                                            
                                            conn.commit()
                                            st.success("✅ Entrega actualizada correctamente")
                                            del st.session_state[f"editing_task_{task['id']}"]
                                            time.sleep(1)
                                            st.rerun()
                                            
                                        except Exception as e:
                                            st.error(f"Error al actualizar: {str(e)}")
                                    
                                    if col_cancel.form_submit_button("❌ Cancelar", type="secondary"):
                                        del st.session_state[f"editing_task_{task['id']}"]
                                        st.rerun()
                        else:
                            # Mostrar mensaje si no puede entregar
                            if not is_valid:
                                if "Tiempo de entrega vencido" in validation_msg:
                                    show_time_expired_message()
                                else:
                                    st.error(f"**{validation_msg}**")
                            else:
                                # Formulario de entrega con validaciones
                                with st.form(f"submit_task_{task['id']}", clear_on_submit=False):
                                    st.markdown("### 📤 Entregar Tarea")
                                    
                                    code_text = None
                                    file_data = None
                                    file_name = None
                                    
                                    if task.get('submission_type') == 'code':
                                        code_text = st.text_area(
                                            "📝 Código",
                                            height=200,
                                            placeholder="Pega tu código aquí...",
                                            key=f"code_{task['id']}",
                                            help="Escribe o pega tu código fuente"
                                        )
                                    else:
                                        uploaded_file = st.file_uploader(
                                            "📎 Subir archivo",
                                            type=['pdf', 'txt', 'py', 'java', 'cpp', 'js', 'zip', 'doc', 'docx'],
                                            key=f"file_{task['id']}",
                                            help="Sube tu archivo de entrega"
                                        )
                                        if uploaded_file:
                                            file_data = uploaded_file.getvalue()
                                            file_name = uploaded_file.name
                                    
                                    col_submit, col_cancel = st.columns([2, 1])
                                    
                                    submitted = col_submit.form_submit_button(
                                        "🚀 Enviar Tarea", 
                                        type="primary",
                                        width='stretch',
                                        disabled=not is_valid,
                                        help="Enviar tu tarea para calificación"
                                    )
                                    
                                    if col_cancel.form_submit_button("❌ Cancelar", type="secondary", width='stretch'):
                                        st.rerun()
                                    
                                    if submitted:
                                        # Validar que haya contenido
                                        if (task.get('submission_type') == 'code' and not code_text.strip()) or \
                                           (task.get('submission_type') != 'code' and not file_data):
                                            show_submission_error("Por favor, completa la entrega según el tipo solicitado.")
                                        else:
                                            # Mostrar progreso
                                            progress_bar = show_submission_progress("Enviando tarea...")
                                            
                                            try:
                                                conn.execute("""
                                                    INSERT INTO submissions 
                                                    (task_id, student_id, code, file_blob, file_name, status, submission_date)
                                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                                """, (
                                                    task['id'],
                                                    u['username'],
                                                    code_text,
                                                    file_data,
                                                    file_name,
                                                    'submitted',
                                                    datetime.now()
                                                ))
                                                conn.commit()
                                                
                                                # ENGAGEMENT: Dar puntos por enviar tarea
                                                try:
                                                    from engagement import PointsManager, StatisticsManager
                                                    points = 30  # Puntos por enviar tarea
                                                    PointsManager.add_points(
                                                        u['username'], 
                                                        points, 
                                                        'task_submission',
                                                        f'Tarea enviada: {task["title"]}'
                                                    )
                                                    StatisticsManager.update_activity_calendar(
                                                        u['username'],
                                                        exercises=1,
                                                        points=points
                                                    )
                                                except Exception as e:
                                                    print(f"Error dando puntos: {e}")
                                                
                                                progress_bar.empty()
                                                show_submission_success("¡Tarea enviada exitosamente!")
                                                time.sleep(2)
                                                st.rerun()
                                            except Exception as e:
                                                progress_bar.empty()
                                                show_submission_error(f"Error al enviar: {str(e)}")

        with tabs[2]:  # Exámenes
            st.subheader("✅ Exámenes del Curso")
            
            all_exams_rows = conn.execute("""
                SELECT e.*, m.title as module_title
                FROM exams e 
                LEFT JOIN modules m ON e.module_id = m.id 
                WHERE e.course_id = ?
                ORDER BY e.created_at DESC
            """, (c['id'],)).fetchall()
            all_exams = [dict(r) for r in all_exams_rows]
            
            if not all_exams:
                st.info("📝 No hay exámenes programados.")
            else:
                for exam in all_exams:
                    module_tag = f"[{exam.get('module_title', 'General')}]"
                    
                    # Verificar intentos previos y validación
                    attempt_row = conn.execute("""
                        SELECT score FROM exam_attempts 
                        WHERE exam_id = ? AND student_id = ?
                    """, (exam['id'], u['username'])).fetchone()
                    attempt = dict(attempt_row) if attempt_row else None
                    
                    # Validar si puede tomar el examen
                    is_valid, validation_msg = validate_exam_time(conn, exam['id'], u['username'])
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])
                        
                        col1.markdown(f"**{module_tag} {exam.get('title', 'Sin título')}**")
                        col1.caption(f"⏱️ Duración: {exam.get('duration_minutes', 0)} minutos")
                        
                        if exam.get('description'):
                            with col1.expander("📖 Descripción"):
                                st.markdown(exam['description'])
                        
                        if attempt:
                            col2.success(f"📊 Nota: {attempt.get('score', 0)}")
                        else:
                            # Botón de inicio con validación
                            if is_valid:
                                if col2.button("▶️ Iniciar", key=f"start_exam_{exam['id']}", type="primary", width='stretch'):
                                    st.session_state.exam_session = {
                                        'id': exam['id'],
                                        'start': datetime.now(),
                                        'dur': exam.get('duration_minutes', 60),
                                        'course_id': c['id']
                                    }
                                    st.rerun()
                            else:
                                col2.error("No disponible")
                                col1.caption(f"ℹ️ {validation_msg}")

        with tabs[3]:  # Foro (CORREGIDO: Limpia HTML roto)
            st.markdown("#### 💬 Foro de Discusión")
            
            # Publicar mensaje
            with st.form("student_post_form"):
                message = st.text_area("Escribe tu pregunta o comentario:", height=100)
                
                if st.form_submit_button("📤 Publicar"):
                    if message.strip():
                        # Guardamos el mensaje limpiando cualquier intento de inyección HTML
                        safe_msg = html.escape(message.strip())
                        conn.execute("""
                            INSERT INTO forum_posts (course_id, user_id, message, date)
                            VALUES (?, ?, ?, ?)
                        """, (c['id'], u['username'], safe_msg, datetime.now()))
                        conn.commit()
                        st.success("✅ Mensaje publicado")
                        st.rerun()
                    else:
                        st.warning("Escribe un mensaje antes de publicar.")
            
            st.divider()
            
            # Mostrar mensajes
            posts_rows = conn.execute("""
                SELECT f.*, u.full_name, u.avatar, u.role 
                FROM forum_posts f 
                JOIN users u ON f.user_id = u.username 
                WHERE f.course_id = ? 
                ORDER BY f.date DESC 
                LIMIT 50
            """, (c['id'],)).fetchall()
            posts = [dict(r) for r in posts_rows]
            
            if not posts:
                st.info("💭 No hay mensajes en el foro. ¡Sé el primero en publicar!")
            else:
                for post in posts:
                    # Avatar
                    if post.get('avatar'):
                        b64_av = base64.b64encode(post['avatar']).decode()
                        img_html = f'<img src="data:image/png;base64,{b64_av}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;">'
                    else:
                        img_html = '<img src="https://cdn-icons-png.flaticon.com/512/847/847969.png" style="width:40px;height:40px;border-radius:50%;">'
                    
                    # Estilo según si es propio o profesor
                    is_own = post['user_id'] == u['username']
                    is_teacher = post.get('role') == 'teacher'
                    
                    bg_color = "#2b2d42" if is_own else "#2a2a2a" if is_teacher else "#1e1e1e"
                    border_style = "border-left: 4px solid #58a6ff;" if is_own else "border-left: 4px solid #ffc107;" if is_teacher else ""
                    
                    # Limpiar y mostrar mensaje
                    import html as html_module
                    raw_msg = post.get('message', '')
                    
                    # Eliminar etiquetas HTML (incluyendo multilinea)
                    clean_msg = re.sub(r'<[^>]*>', '', raw_msg, flags=re.DOTALL)
                    clean_msg = html_module.unescape(clean_msg)
                    display_msg = html_module.escape(clean_msg.strip()).replace('\n', '<br>')
                    
                    badge = "👨‍🏫 Profe" if is_teacher else "Tú" if is_own else ""
                    badge_html = f'<span style="background:#444; padding:2px 6px; border-radius:4px; font-size:0.7em; margin-left:8px;">{badge}</span>' if badge else ""

                    post_html = (
                        f'<div style="display:flex;gap:10px;margin-top:10px;padding:15px;background:{bg_color};border-radius:10px;align-items:flex-start;{border_style}">'
                        f'{img_html}'
                        f'<div style="flex-grow:1;">'
                        f'<div style="font-weight:bold;font-size:0.9rem;color:#ddd;">'
                        f'{post.get("full_name","Usuario")} {badge_html}'
                        f'<span style="color:#aaa;font-weight:normal;font-size:0.8rem;float:right;">{post.get("date","")}</span>'
                        f'</div>'
                        f'<div style="margin-top:8px;font-size:0.95rem;line-height:1.5;color:#fff;">{display_msg}</div>'
                        f'</div></div>'
                    )
                    st.markdown(post_html, unsafe_allow_html=True)

        with tabs[4]:  # Personas
            # Profesor
            teacher_row = conn.execute("""
                SELECT u.* FROM courses c 
                JOIN users u ON c.teacher_id = u.username 
                WHERE c.id = ?
            """, (c['id'],)).fetchone()
            teacher = dict(teacher_row) if teacher_row else None
            
            if teacher:
                st.markdown("### 👨‍🏫 Profesor del Curso")
                with st.container(border=True):
                    col_avatar, col_info = st.columns([1, 4])
                    
                    col_avatar.markdown(render_avatar(teacher.get('avatar'), 80), unsafe_allow_html=True)
                    
                    col_info.subheader(teacher.get('full_name', 'Sin nombre'))
                    if teacher.get('title'):
                        col_info.markdown(f"**{teacher['title']}**")
                    
                    if teacher.get('bio'):
                        col_info.markdown(teacher['bio'])
                    
                    if st.button("👤 Ver Perfil Completo", key="view_teacher_profile"):
                        st.session_state.profile_target = teacher.get('username')
                        st.session_state.current_page = 'profile'
                        st.rerun()
            
            # Compañeros
            st.markdown("### 👥 Compañeros del Curso")
            
            classmates_rows = conn.execute("""
                SELECT u.* FROM enrollments e 
                JOIN users u ON e.student_id = u.username 
                WHERE e.course_id = ? 
                AND u.role = 'student'
                AND u.username != ?
                ORDER BY u.full_name
            """, (c['id'], u['username'])).fetchall()
            classmates = [dict(r) for r in classmates_rows]
            
            if not classmates:
                st.info("👤 Eres el único estudiante en este curso por ahora.")
            else:
                cols = st.columns(4)
                for i, classmate in enumerate(classmates):
                    with cols[i % 4]:
                        with st.container(border=True):
                            st.markdown(render_avatar(classmate.get('avatar')), unsafe_allow_html=True)
                            st.markdown(f"<div style='text-align: center; font-size: 0.9em;'>{classmate.get('full_name', 'Sin nombre')}</div>", 
                                      unsafe_allow_html=True)
                            
                            if st.button("👤 Perfil", 
                                       key=f"mate_{classmate.get('username', '')}", 
                                       width='stretch'):
                                st.session_state.profile_target = classmate.get('username')
                                st.session_state.current_page = 'profile'
                                st.rerun()

        with tabs[5]:  # Notas
            st.subheader("📊 Mis Calificaciones en este Curso")
            
            # Calificaciones de tareas
            task_grades_rows = conn.execute("""
                SELECT t.title, s.final_grade, t.points, s.submission_date
                FROM tasks t 
                LEFT JOIN submissions s ON t.id = s.task_id AND s.student_id = ?
                WHERE t.course_id = ?
                ORDER BY t.due_date DESC
            """, (u['username'], c['id'])).fetchall()
            task_grades = [dict(r) for r in task_grades_rows]
            
            # Calificaciones de exámenes
            exam_grades_rows = conn.execute("""
                SELECT e.title, a.score, 
                       (SELECT SUM(points) FROM exam_questions WHERE exam_id = e.id) as total
                FROM exams e 
                LEFT JOIN exam_attempts a ON e.id = a.exam_id AND a.student_id = ?
                WHERE e.course_id = ?
            """, (u['username'], c['id'])).fetchall()
            exam_grades = [dict(r) for r in exam_grades_rows]
            
            # Crear tabla
            data = []
            for task in task_grades:
                grade = task.get('final_grade')
                points = task.get('points', 0)
                data.append({
                    "Actividad": task.get('title', 'Sin título'),
                    "Tipo": "📝 Tarea",
                    "Nota": f"{grade:.1f} / {points}" if grade is not None else f"0 / {points}",
                    "Porcentaje": f"{(grade/points*100):.1f}%" if grade is not None and points > 0 else "0%",
                    "Fecha": task.get('submission_date', '')
                })
            
            for exam in exam_grades:
                score = exam.get('score')
                total = exam.get('total', 0)
                data.append({
                    "Actividad": exam.get('title', 'Sin título'),
                    "Tipo": "✅ Examen",
                    "Nota": f"{score:.1f} / {total}" if score is not None else f"0 / {total}",
                    "Porcentaje": f"{(score/total*100):.1f}%" if score is not None and total > 0 else "0%",
                    "Fecha": ""
                })
            
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, width='stretch', hide_index=True)
                
                # Calcular promedio
                if len(data) > 0:
                    total_percentage = 0
                    count_percentage = 0
                    for d in data:
                        if d["Porcentaje"] != "0%" and d["Porcentaje"] != "0.0%":
                            try:
                                perc_value = float(d["Porcentaje"].replace('%', ''))
                                total_percentage += perc_value
                                count_percentage += 1
                            except:
                                pass
                    
                    avg_percentage = total_percentage / count_percentage if count_percentage > 0 else 0
                    
                    col_avg1, col_avg2, col_avg3 = st.columns(3)
                    col_avg1.metric("📊 Total Actividades", len(data))
                    col_avg2.metric("📈 Promedio del Curso", f"{avg_percentage:.1f}%")
                    
                    # Evaluación cualitativa
                    if avg_percentage >= 90:
                        performance = "🎖️ Excelente"
                    elif avg_percentage >= 70:
                        performance = "👍 Bueno"
                    elif avg_percentage >= 60:
                        performance = "⚠️ Regular"
                    else:
                        performance = "📉 Necesita mejorar"
                    
                    col_avg3.metric("🏆 Rendimiento", performance)
            else:
                st.info("📭 Aún no tienes calificaciones en este curso.")

# ==============================================================================
# ACADEMIA PERSONAL IA - NUEVA FUNCIONALIDAD
# ==============================================================================

def render_personal_academy(conn, user, model):
    """Renderiza la Academia Personal IA - Solo evaluación inicial"""
    st.title("🎓 Academia Personal IA")
    st.markdown("### Evalúa tus conocimientos y crea cursos personalizados")
    
    # Verificar si ya tiene cursos IA activos
    existing_courses = conn.execute("""
        SELECT language, level, status, progress_percentage, created_at
        FROM ai_courses 
        WHERE student_id = ? AND status != 'completed'
        ORDER BY last_activity DESC
    """, (user['username'],)).fetchall()
    
    if existing_courses:
        st.markdown("### 📚 Tus Cursos IA Activos")
        st.info("Tus cursos IA aparecen en la sección **'Mis Cursos'** junto con los cursos regulares.")
        
        for course in existing_courses:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    level_emoji = {"principiante": "🌱", "intermedio": "🌿", "avanzado": "🌳"}
                    st.write(f"**{course['language']}** {level_emoji.get(course['level'], '📊')} {course['level'].title()}")
                    st.caption(f"Creado: {course['created_at'][:10]}")
                
                with col2:
                    progress = course['progress_percentage'] or 0
                    st.metric("Progreso", f"{progress:.1f}%")
                    st.progress(progress / 100)
                
                with col3:
                    status_emoji = {"active": "🟢", "paused": "⏸️", "completed": "✅"}
                    st.write(f"{status_emoji.get(course['status'], '📊')} {course['status'].title()}")
        
        st.markdown("---")
    
    # Sección de evaluación para nuevos cursos
    st.markdown("### 🎯 Crear Nuevo Curso IA")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Selecciona un Lenguaje")
        
        languages = ["Python", "JavaScript", "Java", "C++", "SQL", "NoSQL", "HTML/CSS", "C#", "PHP", "Ruby"]
        # Detectar cambio de lenguaje en tiempo real
        previous_lang = st.session_state.get('previous_selected_lang')
        selected_lang = st.selectbox(
            "Lenguaje de Programación:",
            languages,
            key="new_course_language"
        )
        
        # Si cambió el lenguaje, limpiar estado
        if previous_lang and previous_lang != selected_lang:
            keys_to_clear = ['comprehensive_questions', 'evaluation_language', 'user_responses', 
                           'current_question', 'start_time', 'evaluation_completed', 'evaluation_responses']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
        
        # También agregar botón para forzar regeneración
        if st.button("🔄 Regenerar Evaluación", help="Fuerza la regeneración de preguntas para este lenguaje"):
            # Limpiar TODO el estado relacionado con evaluaciones Y exámenes
            keys_to_clear = [
                'comprehensive_questions', 'evaluation_language', 'user_responses', 
                'current_question', 'start_time', 'evaluation_completed', 'evaluation_responses',
                'academy_step', 'selected_language',
                # Limpiar también el examen final
                'final_exam', 'final_exam_started', 'exam_responses', 'exam_page', 'temp_responses'
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.success(f"✅ Estado limpiado. Listo para evaluar {selected_lang}")
            st.rerun()
        
        st.info(f"""
        ### 📋 Evaluación Completa de {selected_lang}
        
        **¿Qué incluye?**
        - ✅ **15+ preguntas** especializadas
        - 🎯 **Evaluación profunda** de conocimientos
        - 📊 **Análisis detallado** de fortalezas y debilidades
        - 🎓 **Curso personalizado** basado en resultados
        
        **Temas evaluados:**
        - Sintaxis y conceptos básicos
        - Estructuras de control y datos
        - Funciones y programación avanzada
        - Debugging y mejores prácticas
        - Conceptos específicos de {selected_lang}
        """)
        
        # Verificar si ya tiene un curso de este lenguaje
        existing_course = conn.execute("""
            SELECT id FROM ai_courses 
            WHERE student_id = ? AND language = ? AND status != 'completed'
        """, (user['username'], selected_lang)).fetchone()
        
        if existing_course:
            st.warning(f"⚠️ Ya tienes un curso activo de {selected_lang}. Puedes encontrarlo en 'Mis Cursos'.")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔄 Crear Nuevo Curso", type="primary", use_container_width=True):
                    # Limpiar estados previos
                    keys_to_delete = [
                        'evaluation_completed', 'evaluation_responses', 'user_responses', 
                        'current_question', 'start_time', 'comprehensive_questions',
                        'selected_language', 'academy_step', 'assessment_questions',
                        'creating_ai_course', 'selected_sections', 'replace_course_confirmed',
                        'evaluation_language',  # Agregar lenguaje de evaluación
                        # Limpiar también el examen final
                        'final_exam', 'final_exam_started', 'exam_responses', 'exam_page', 'temp_responses'
                    ]
                    for key in keys_to_delete:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    # Iniciar nueva evaluación
                    st.session_state.selected_language = selected_lang
                    st.session_state.academy_step = 'taking_comprehensive_assessment'
                    st.rerun()
            
            with col_btn2:
                if st.button("📚 Ver Curso Actual", type="secondary", use_container_width=True):
                    st.cache_data.clear()  # Limpiar caché al ver curso
                    # Limpiar estado del examen final al cambiar de curso
                    exam_keys = ['final_exam', 'final_exam_started', 'exam_responses', 'exam_page', 'temp_responses']
                    for key in exam_keys:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.session_state.active_ai_course = existing_course['id']
                    st.session_state.view_mode = 'ai_course'
                    st.rerun()
        else:
            if st.button(f"🚀 Evaluar {selected_lang}", type="primary", use_container_width=True):
                # Limpiar estados previos antes de iniciar
                keys_to_delete = [
                    'evaluation_completed', 'evaluation_responses', 'user_responses', 
                    'current_question', 'start_time', 'comprehensive_questions',
                    'academy_step', 'assessment_questions', 'creating_ai_course', 
                    'selected_sections', 'replace_course_confirmed', 'evaluation_language',
                    # Limpiar también el examen final
                    'final_exam', 'final_exam_started', 'exam_responses', 'exam_page', 'temp_responses'
                ]
                for key in keys_to_delete:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.session_state.selected_language = selected_lang
                st.session_state.academy_step = 'taking_comprehensive_assessment'
                st.rerun()
    
    with col2:
        if st.session_state.get('academy_step') == 'taking_comprehensive_assessment':
            render_comprehensive_assessment(conn, user, model, st.session_state.selected_language)
        else:
            st.markdown("### 🎓 ¿Cómo Funciona la Academia IA?")
            
            st.markdown("""
            #### 1️⃣ **Evaluación Inteligente**
            - Realizas una evaluación completa del lenguaje seleccionado
            - La IA analiza tus respuestas y determina tu nivel exacto
            - Se identifican tus fortalezas y áreas de mejora
            
            #### 2️⃣ **Curso Personalizado**
            - Se crea automáticamente un curso adaptado a tu nivel
            - El curso aparece en **"Mis Cursos"** como una materia más
            - Incluye videos, tutoriales, ejercicios y recursos específicos
            
            #### 3️⃣ **Aprendizaje Interactivo**
            - **Chat con IA**: Pregunta sobre cualquier tema del curso
            - **Materiales Personalizados**: Videos y recursos según tu nivel
            - **Ejercicios Progresivos**: Práctica adaptada a tu progreso
            
            #### 4️⃣ **Evaluación Final**
            - Cuando te sientas preparado, toma el examen final
            - Si apruebas, obtienes certificación del curso
            - Puedes ajustar la dificultad en configuración del curso
            
            #### 5️⃣ **Gestión Flexible**
            - **Configurar Dificultad**: Fácil, Normal, Difícil
            - **Pausar/Reanudar**: Control total sobre tu aprendizaje
            - **Eliminar Curso**: Si ya no lo necesitas
            """)
            
            st.markdown("---")
            st.markdown("### 📊 Historial de Evaluaciones")
            
            # Mostrar evaluaciones previas
            assessments = conn.execute("""
                SELECT language, level, percentage, created_at 
                FROM language_assessments 
                WHERE student_id = ? 
                ORDER BY created_at DESC
                LIMIT 5
            """, (user['username'],)).fetchall()
            
            if assessments:
                for assessment in assessments:
                    with st.container(border=True):
                        col_lang, col_level, col_score, col_date = st.columns([2, 2, 2, 2])
                        
                        with col_lang:
                            st.write(f"**{assessment['language']}**")
                        with col_level:
                            level_emoji = {"principiante": "🌱", "intermedio": "🌿", "avanzado": "🌳"}
                            st.write(f"{level_emoji.get(assessment['level'], '📊')} {assessment['level'].title()}")
                        with col_score:
                            st.write(f"**{assessment['percentage']:.1f}%**")
                        with col_date:
                            date_str = assessment['created_at'][:10]
                            st.write(f"📅 {date_str}")
            else:
                st.info("👈 Selecciona un lenguaje y realiza tu primera evaluación")

def render_comprehensive_assessment(conn, user, model, language):
    """Renderiza la evaluación completa y robusta"""
    st.markdown(f"### 📝 Evaluación Completa de {language}")
    st.markdown("*Esta evaluación determinará tu nivel exacto y creará un curso personalizado*")
    
    # FORZAR regeneración si el lenguaje cambió
    current_language = st.session_state.get('evaluation_language')
    if (current_language != language or 'comprehensive_questions' not in st.session_state):
        # Limpiar estado anterior si existe
        if current_language and current_language != language:
            st.info(f"🔄 Cambiando de {current_language} a {language}...")
            # Limpiar preguntas anteriores
            for key in ['comprehensive_questions', 'user_responses', 'current_question', 'start_time']:
                if key in st.session_state:
                    del st.session_state[key]
        
        with st.spinner(f"🧠 Generando evaluación completa de {language}..."):
            from utils_ai import generate_level_assessment
            questions = generate_level_assessment(model, language)
            st.session_state.comprehensive_questions = questions
            st.session_state.evaluation_language = language  # Guardar el lenguaje actual
            st.session_state.current_question = 0
            st.session_state.user_responses = []
            st.session_state.start_time = time.time()
            st.rerun()  # Forzar recarga para mostrar nuevas preguntas
    
    questions = st.session_state.comprehensive_questions
    current_q = st.session_state.current_question
    
    if current_q < len(questions):
        question = questions[current_q]
        
        # Mostrar progreso detallado
        progress = (current_q + 1) / len(questions)
        st.progress(progress, text=f"Pregunta {current_q + 1} de {len(questions)} • {question.get('level', 'general').title()} • {question.get('topic', 'general').title()}")
        
        # Timer en tiempo real que siempre corre - CORREGIDO DEFINITIVAMENTE
        if 'start_time' not in st.session_state:
            st.session_state.start_time = time.time()
        
        elapsed_time = time.time() - st.session_state.start_time
        
        # Timer HTML con JavaScript mejorado y forzado
        timer_html = f"""
        <div id="assessment-timer" style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px 25px;
            border-radius: 12px;
            margin: 15px 0;
            text-align: center;
            color: white;
            font-family: 'Courier New', monospace;
            font-size: 20px;
            font-weight: bold;
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            border: 2px solid rgba(255,255,255,0.2);
        ">
            ⏱️ Tiempo: <span id="elapsed-timer" style="color: #FFD700;">{int(elapsed_time//60):02d}:{int(elapsed_time%60):02d}</span>
            <span style="margin-left: 30px;">📊 Promedio: <span id="avg-timer" style="color: #90EE90;">--:--</span></span>
        </div>
        
        <script>
        // Limpiar cualquier timer anterior para evitar conflictos
        if (window.assessmentTimerInterval) {{
            clearInterval(window.assessmentTimerInterval);
            window.assessmentTimerInterval = null;
        }}
        
        // Variables globales del timer
        const startTime = {st.session_state.start_time};
        const currentQuestion = {current_q + 1};
        
        function updateAssessmentTimer() {{
            try {{
                const now = Date.now() / 1000;
                const elapsed = Math.max(0, now - startTime);
                
                // Calcular tiempo transcurrido
                const elapsedMinutes = Math.floor(elapsed / 60);
                const elapsedSeconds = Math.floor(elapsed % 60);
                const elapsedDisplay = elapsedMinutes.toString().padStart(2, '0') + ':' + elapsedSeconds.toString().padStart(2, '0');
                
                // Calcular promedio por pregunta
                let avgDisplay = '--:--';
                if (currentQuestion > 0) {{
                    const avgTime = elapsed / currentQuestion;
                    const avgMinutes = Math.floor(avgTime / 60);
                    const avgSeconds = Math.floor(avgTime % 60);
                    avgDisplay = avgMinutes.toString().padStart(2, '0') + ':' + avgSeconds.toString().padStart(2, '0');
                }}
                
                // Actualizar elementos DOM
                const elapsedElement = document.getElementById('elapsed-timer');
                const avgElement = document.getElementById('avg-timer');
                
                if (elapsedElement) {{
                    elapsedElement.textContent = elapsedDisplay;
                    elapsedElement.style.color = '#FFD700';
                }}
                
                if (avgElement) {{
                    avgElement.textContent = avgDisplay;
                    avgElement.style.color = '#90EE90';
                }}
                
            }} catch (error) {{
                console.error('Error en timer:', error);
            }}
        }}
        
        // Actualizar inmediatamente
        updateAssessmentTimer();
        
        // Configurar interval principal (cada segundo)
        window.assessmentTimerInterval = setInterval(updateAssessmentTimer, 1000);
        
        // Interval de respaldo cada 2 segundos para garantizar actualización
        setTimeout(function() {{
            setInterval(updateAssessmentTimer, 2000);
        }}, 500);
        
        // Forzar actualización cada 5 segundos
        setInterval(function() {{
            try {{
                updateAssessmentTimer();
            }} catch (e) {{
                console.log('Forced update error:', e);
            }}
        }}, 5000);
        
        // Limpiar al salir
        window.addEventListener('beforeunload', function() {{
            if (window.assessmentTimerInterval) {{
                clearInterval(window.assessmentTimerInterval);
            }}
        }});
        
        // Actualización adicional después de 100ms para asegurar renderizado
        setTimeout(updateAssessmentTimer, 100);
        setTimeout(updateAssessmentTimer, 500);
        setTimeout(updateAssessmentTimer, 1000);
        </script>
        """
        
        # Mostrar el timer
        st.markdown(timer_html, unsafe_allow_html=True)
        
        # Tiempo estimado restante (solo mostrar si hay preguntas respondidas)
        if current_q > 0:
            avg_time_per_question = elapsed_time / current_q
            remaining_questions = len(questions) - current_q
            estimated_remaining = avg_time_per_question * remaining_questions
            
            # Mostrar estimación con mejor formato
            est_minutes = int(estimated_remaining // 60)
            est_seconds = int(estimated_remaining % 60)
            
            st.info(f"📈 **Estimación:** Te quedan aproximadamente **{est_minutes}:{est_seconds:02d}** minutos para completar las {remaining_questions} preguntas restantes")
        else:
            st.info("📝 **Primera pregunta** - El timer comenzará a calcular promedios después de responder")
        
        # Mostrar pregunta con más detalle
        st.markdown(f"#### {current_q + 1}. {question['question']}")
        
        # Mostrar código de ejemplo si existe
        if question.get('code_example'):
            st.code(question['code_example'], language=language.lower())
        
        # Mostrar opciones
        selected_option = st.radio(
            "Selecciona tu respuesta:",
            question['options'],
            key=f"comprehensive_q_{current_q}"
        )
        
        # Información adicional sobre la pregunta
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            level_emoji = {"principiante": "🌱", "intermedio": "🌿", "avanzado": "🌳"}
            st.caption(f"📊 Nivel: {level_emoji.get(question.get('level', 'general'), '📊')} {question.get('level', 'General').title()}")
        with col_info2:
            st.caption(f"🎯 Tema: {question.get('topic', 'General').title()}")
        
        # Navegación
        col_prev, col_next = st.columns(2)
        
        with col_prev:
            if current_q > 0:
                if st.button("⬅️ Pregunta Anterior", use_container_width=True):
                    st.session_state.current_question -= 1
                    st.rerun()
        
        with col_next:
            button_text = "➡️ Siguiente Pregunta" if current_q < len(questions) - 1 else "✅ Finalizar Evaluación"
            if st.button(button_text, type="primary", use_container_width=True):
                
                # Guardar respuesta detallada
                selected_index = question['options'].index(selected_option)
                is_correct = selected_index == question['correct_index']
                
                response = {
                    'question': question['question'],
                    'selected_option': selected_option,
                    'selected_index': selected_index,
                    'correct_index': question['correct_index'],
                    'is_correct': is_correct,
                    'level': question.get('level', 'principiante'),
                    'topic': question.get('topic', 'general'),
                    'explanation': question.get('explanation', ''),
                    'code_example': question.get('code_example', ''),
                    'points': question.get('points', 1)
                }
                
                # Actualizar o agregar respuesta
                if current_q < len(st.session_state.user_responses):
                    st.session_state.user_responses[current_q] = response
                else:
                    st.session_state.user_responses.append(response)
                
                if current_q < len(questions) - 1:
                    st.session_state.current_question += 1
                    st.rerun()
                else:
                    # Finalizar evaluación - activar creación automática de curso
                    st.session_state.evaluation_completed = True
                    st.session_state.evaluation_responses = st.session_state.user_responses
                    st.session_state.selected_sections = 8  # Establecer secciones fijas
                    st.session_state.creating_ai_course = True  # Activar creación inmediata
                    st.rerun()
    else:
        st.success("✅ Evaluación completada!")
        
    # Mostrar creación de curso si la evaluación está completada
    if st.session_state.get('evaluation_completed', False):
        create_ai_course_from_assessment(conn, user, model, language, st.session_state.evaluation_responses)

def create_ai_course_from_assessment(conn, user, model, language, responses):
    """Crea un curso IA basado en los resultados de la evaluación con estructura por temas"""
    
    st.markdown("### 🎓 Creando tu Curso Personalizado")
    
    # Verificar si ya existe un curso activo para este lenguaje
    existing_course = conn.execute("""
        SELECT id FROM ai_courses 
        WHERE student_id = ? AND language = ? AND status = 'active'
        ORDER BY created_at DESC LIMIT 1
    """, (user['username'], language)).fetchone()
    
    # Si existe un curso y no se ha confirmado el reemplazo, preguntar
    if existing_course and not st.session_state.get('replace_course_confirmed', False):
        st.warning(f"⚠️ Ya tienes un curso activo de {language}")
        st.info("Si creas un nuevo curso, el anterior seguirá disponible en 'Mis Cursos'")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Crear Nuevo Curso", type="primary", use_container_width=True):
                st.session_state.replace_course_confirmed = True
                st.rerun()
        with col2:
            if st.button("❌ Cancelar", use_container_width=True):
                # Limpiar todo el estado de evaluación
                for key in ['evaluation_completed', 'evaluation_responses', 'user_responses', 
                           'current_question', 'start_time', 'comprehensive_questions',
                           'selected_language', 'academy_step', 'evaluation_language',
                           'creating_ai_course', 'selected_sections']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        return
    
    # Verificar si se debe crear el curso automáticamente
    if st.session_state.get('creating_ai_course', False):
        # Crear el curso automáticamente
        sections_count = st.session_state.get('selected_sections', 8)
        
        # Animación de carga mejorada
        st.markdown("""
        <style>
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.05); }
        }
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        @keyframes slideIn {
            from { transform: translateY(-20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        .loading-container {
            animation: slideIn 0.5s ease-out;
        }
        .loading-icon {
            animation: rotate 2s linear infinite;
            display: inline-block;
            font-size: 3em;
        }
        .loading-text {
            animation: pulse 2s ease-in-out infinite;
        }
        </style>
        
        <div class="loading-container" style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 50px;
            border-radius: 25px;
            text-align: center;
            margin: 30px 0;
            box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4);
        ">
            <div class="loading-icon">🎓</div>
            <h1 class="loading-text" style="
                color: white;
                margin: 20px 0;
                font-size: 2.5em;
                font-weight: bold;
            ">Creando tu Curso Personalizado</h1>
            <p style="
                color: rgba(255, 255, 255, 0.95);
                font-size: 1.3em;
                margin: 10px 0;
            ">Por favor espera mientras generamos tu contenido...</p>
            <div style="
                margin-top: 30px;
                padding: 20px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                backdrop-filter: blur(10px);
            ">
                <p style="color: white; font-size: 1.1em; margin: 0;">
                    ⚡ Analizando tu nivel<br>
                    📚 Generando estructura de temas<br>
                    🎯 Personalizando contenido<br>
                    ✨ Preparando materiales
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        from utils_ai import (
            evaluate_level_from_responses, 
            generate_course_topics_structure,
            generate_topic_materials_spanish,
            generate_topic_exercises
        )
        
        # Evaluar nivel
        level, percentage, recommendations = evaluate_level_from_responses(model, language, responses)
        
        # Verificar consistencia del nivel
        if percentage >= 80:
            level = "avanzado"
        elif percentage >= 60:
            level = "intermedio" 
        else:
            level = "principiante"
        
        st.success(f"📊 Nivel asignado: {level} (Puntuación: {percentage:.1f}%)")
        
        # Guardar evaluación
        conn.execute("""
            INSERT INTO language_assessments 
            (student_id, language, level, score, max_score, percentage, assessment_data, recommendations)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user['username'], language, level, 
            sum(1 for r in responses if r['is_correct']), len(responses), percentage,
            json.dumps(responses), recommendations
        ))
        
        # Verificar si ya existe un curso para este estudiante y lenguaje
        existing_course = conn.execute("""
            SELECT id FROM ai_courses 
            WHERE student_id = ? AND language = ?
        """, (user['username'], language)).fetchone()
        
        if existing_course:
            # Actualizar el curso existente en lugar de crear uno nuevo
            conn.execute("""
                UPDATE ai_courses 
                SET level = ?, assessment_score = ?, assessment_data = ?, 
                    status = 'active', total_topics = ?, sections_count = ?,
                    completed_topics = 0, progress_percentage = 0
                WHERE student_id = ? AND language = ?
            """, (level, percentage, json.dumps(responses), 
                  sections_count, sections_count,
                  user['username'], language))
            conn.commit()
            ai_course_id = existing_course['id']
            # Eliminar temas anteriores para regenerarlos
            conn.execute("DELETE FROM ai_course_topics WHERE ai_course_id = ?", (ai_course_id,))
            conn.commit()
        else:
            # Crear nuevo curso IA
            cursor = conn.execute("""
                INSERT INTO ai_courses 
                (student_id, language, level, assessment_score, assessment_data, status, 
                 total_topics, completed_topics, sections_count)
                VALUES (?, ?, ?, ?, ?, 'active', ?, 0, ?)
            """, (user['username'], language, level, percentage, json.dumps(responses), 
                  sections_count, sections_count))
            conn.commit()
            ai_course_id = cursor.lastrowid
        
        # Crear contenedor de progreso visual
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 20px;
            margin: 20px 0;
            text-align: center;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        ">
            <h2 style="color: white; margin: 0 0 10px 0; font-size: 2em;">
                🎓 Creando tu Curso Personalizado
            </h2>
            <p style="color: rgba(255, 255, 255, 0.9); margin: 0; font-size: 1.2em;">
                Por favor espera mientras generamos tu contenido...
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Contenedor para mensajes de progreso
        progress_container = st.empty()
        status_container = st.empty()
        
        # Barra de progreso
        progress_bar = st.progress(0)
        
        # Paso 1: Generar estructura de temas
        progress_container.markdown("""
        <div style="
            background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
            padding: 20px;
            border-radius: 15px;
            border-left: 5px solid #667eea;
            margin: 10px 0;
        ">
            <h3 style="color: #667eea; margin: 0 0 10px 0;">📚 Paso 1: Generando estructura de temas</h3>
            <p style="color: #d0d0d0; margin: 0;">Creando la estructura del curso con temas progresivos...</p>
        </div>
        """, unsafe_allow_html=True)
        progress_bar.progress(10)
        
        topics_structure = generate_course_topics_structure(model, language, level, sections_count)
        
        progress_bar.progress(20)
        status_container.success(f"✅ Estructura creada: {len(topics_structure)} temas generados")
        
        # Crear temas en la base de datos con progreso detallado
        total_topics = len(topics_structure)
        
        for idx, topic_data in enumerate(topics_structure, 1):
            # Calcular progreso (20% ya usado, 80% restante dividido entre temas)
            base_progress = 20
            topic_progress = int(base_progress + (idx / total_topics) * 80)
            
            # Mostrar tema actual
            progress_container.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1a2332 0%, #0f1923 100%);
                padding: 20px;
                border-radius: 15px;
                border-left: 5px solid #0066cc;
                margin: 10px 0;
            ">
                <h3 style="color: #4da6ff; margin: 0 0 10px 0;">
                    📖 Tema {idx}/{total_topics}: {topic_data['title']}
                </h3>
                <p style="color: #b3d9ff; margin: 0;">Generando contenido para este tema...</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Asegurar que objectives sea un string
            objectives = topic_data.get('objectives', '')
            if isinstance(objectives, list):
                objectives = '. '.join(objectives)
            elif not isinstance(objectives, str):
                objectives = str(objectives)
            
            topic_cursor = conn.execute("""
                INSERT INTO ai_course_topics 
                (ai_course_id, topic_number, title, description, objectives, 
                 estimated_hours, order_index, is_unlocked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ai_course_id, topic_data['topic_number'], topic_data['title'],
                topic_data['description'], objectives,
                topic_data['estimated_hours'], topic_data['order_index'],
                1  # Todas las secciones desbloqueadas desde el inicio
            ))
            
            topic_id = topic_cursor.lastrowid
            
            # PRIORIDAD 1: Generar contenido de la lección PRIMERO
            status_container.info(f"📖 Generando contenido de la lección: {topic_data['title']}")
            
            from utils_ai import generate_lesson_content
            lesson_content = generate_lesson_content(
                model,
                language,
                topic_data['title'],
                topic_data.get('description', ''),
                level
            )
            
            # Guardar contenido de la lección
            if lesson_content:
                conn.execute("""
                    INSERT INTO ai_course_materials 
                    (ai_course_id, topic_id, type, title, description, url, 
                     order_index, estimated_minutes, difficulty_level, language_content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ai_course_id, topic_id, 'tutorial',
                    f"Lección: {topic_data['title']}", lesson_content,
                    '#', 0, 30, 1, 'es'
                ))
                status_container.success(f"✅ Contenido de lección generado")
            
            # PRIORIDAD 2: Generar materiales complementarios
            status_container.info(f"🎥 Generando materiales educativos para: {topic_data['title']}")
            progress_bar.progress(topic_progress)
            
            topic_materials = generate_topic_materials_spanish(
                model, language, topic_data['title'], topic_data['description'], level
            )
            
            for material in topic_materials:
                conn.execute("""
                    INSERT INTO ai_course_materials 
                    (ai_course_id, topic_id, type, title, description, url, 
                     order_index, estimated_minutes, difficulty_level, language_content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ai_course_id, topic_id, material['type'], material['title'],
                    material['description'], material.get('url', '#'),
                    material['order_index'], material['estimated_minutes'],
                    material['difficulty_level'], material['language_content']
                ))
            
            status_container.success(f"✅ Materiales generados: {len(topic_materials)} recursos")
            
            # NOTA: Los ejercicios se generarán on-demand cuando el estudiante vea el tema
            # Esto previene errores durante la creación del curso
            
            status_container.success(f"✅ Tema {idx}/{total_topics} completado: {topic_data['title']}")
        
        # Finalizar
        progress_bar.progress(100)
        progress_container.markdown("""
        <div style="
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            margin: 20px 0;
            box-shadow: 0 10px 30px rgba(67, 233, 123, 0.3);
        ">
            <h2 style="color: white; margin: 0 0 10px 0; font-size: 2em;">
                ✅ ¡Curso Creado Exitosamente!
            </h2>
            <p style="color: rgba(255, 255, 255, 0.95); margin: 0; font-size: 1.1em;">
                Tu curso personalizado está listo para comenzar
            </p>
        </div>
        """, unsafe_allow_html=True)
        status_container.success(f"🎉 Curso completo con {total_topics} temas y materiales educativos")
        
        st.info("💡 Los ejercicios se generarán automáticamente cuando visites cada tema")
        
        conn.commit()
        
        # Limpiar TODOS los estados relacionados con evaluación y creación
        keys_to_delete = [
            'creating_ai_course', 'selected_sections', 'evaluation_completed', 
            'evaluation_responses', 'user_responses', 'current_question', 
            'start_time', 'comprehensive_questions', 'selected_language',
            'academy_step', 'assessment_questions', 'replace_course_confirmed',
            'evaluation_language',  # Agregar lenguaje de evaluación
            # Limpiar también el examen final
            'final_exam', 'final_exam_started', 'exam_responses', 'exam_page', 'temp_responses'
        ]
        
        for key in keys_to_delete:
            if key in st.session_state:
                del st.session_state[key]
        
        st.success("✅ ¡Curso creado exitosamente!")
        st.balloons()
        
        # Redirigir al curso
        st.cache_data.clear()  # Limpiar caché al crear curso
        st.session_state.active_ai_course = ai_course_id
        st.session_state.view_mode = 'ai_course'
        time.sleep(1)
        st.rerun()
    
    else:
        # Número de secciones fijo en 8
        sections_count = 8
        
        st.markdown("#### 📚 Personaliza tu curso")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**Tu curso tendrá {sections_count} temas progresivos** 📈")
            
            st.markdown("#### 📋 Tu curso incluirá:")
            st.markdown(f"""
            - 📚 **{sections_count} temas** estructurados
            - 🎥 **Materiales educativos** adaptados
            - 💪 **Ejercicios prácticos** por tema
            - 📊 **Evaluaciones** de progreso
            - 🤖 **Chat con IA** para dudas
            - 🏆 **Examen final** integrador
            """)
        
        with col2:
            st.markdown("#### 🎯 Tu Nivel")
            
            correct_answers = sum(1 for r in responses if r.get('is_correct', False))
            percentage = (correct_answers / len(responses)) * 100
            
            if percentage >= 80:
                level_preview, emoji, desc = "avanzado", "🌳", "Contenido experto"
            elif percentage >= 60:
                level_preview, emoji, desc = "intermedio", "🌿", "Conceptos avanzados"
            else:
                level_preview, emoji, desc = "principiante", "🌱", "Fundamentos básicos"
            
            st.info(f"""
            **Nivel:** {emoji} {level_preview.title()}
            **Puntuación:** {percentage:.1f}%
            **Contenido:** {desc}
            """)
        
        # Botón para crear curso
        if st.button("🚀 Crear Curso con Temas", type="primary", use_container_width=True, 
                    key=f"create_course_{hash(str(responses))}"):
            st.session_state.selected_sections = sections_count
            st.session_state.creating_ai_course = True
            st.rerun()

def render_regular_course_simple(conn, user, model):
    """Renderiza vista simple de curso regular"""
    
    c = st.session_state.active_course
    
    # Verificación de seguridad
    if c is None:
        st.error("❌ No hay curso seleccionado")
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    # Verificar que el curso tenga los datos necesarios
    if not isinstance(c, dict) or 'id' not in c:
        st.error("❌ Datos del curso inválidos")
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    # Header del curso
    col1, col2 = st.columns([1, 8])
    
    with col1:
        # Mostrar imagen del curso o icono por defecto
        if c.get('cover_image'):
            img_b64 = base64.b64encode(c['cover_image']).decode()
            st.markdown(f"""
            <div style="display: flex; justify-content: center; margin-top: 10px;">
                <img src="data:image/png;base64,{img_b64}" 
                     style="width: 80px; height: 80px; border-radius: 10px; 
                            border: 2px solid #58a6ff; object-fit: cover;">
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="display: flex; justify-content: center; margin-top: 10px; font-size: 4em;">
                📚
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.title(f"📚 {c['name']}")
        st.caption(f"🔖 Código: {c['code']} • 👨‍🏫 Profesor: {c.get('teacher_name', 'Sin asignar')}")
        if c.get('description'):
            st.markdown(f"*{re.sub(chr(60) + '[^' + chr(62) + ']+' + chr(62), '', c['description']).strip()}*")
    
    if st.button("🏠 Volver al Dashboard"):
        st.session_state.view_mode = 'dashboard'
        st.rerun()
    
    st.markdown("---")
    
    # Tabs del curso
    tab1, tab2, tab3, tab4 = st.tabs(["📚 Módulos", "📝 Tareas", "✅ Exámenes", "💬 Foro"])
    
    with tab1:
        st.markdown("### 📁 Contenido del Curso")
        
        # Obtener módulos
        modules_rows = conn.execute("""
            SELECT * FROM modules 
            WHERE course_id = ? 
            ORDER BY order_index, id
        """, (c['id'],)).fetchall()
        modules = [dict(r) for r in modules_rows]
        
        if not modules:
            st.info("📭 El profesor aún no ha publicado contenido.")
        else:
            for module in modules:
                module_id = module['id']
                with st.expander(f"📌 {module['title']}", expanded=True):
                    if module.get('description'):
                        st.markdown(module['description'])
                    
                    # Verificar si el módulo tiene chat IA configurado
                    from utils_chat_ai import ModuleChatManager
                    chat_manager = ModuleChatManager(conn, model)
                    chat_content = chat_manager.get_chat_content(module_id)
                    has_chat = chat_content is not None
                    
                    # DEBUG: Mostrar si hay chat configurado
                    if has_chat:
                        st.success(f"✅ Chat IA disponible para {module['title']}")
                    else:
                        st.info(f"ℹ️ Chat IA no configurado para {module['title']}")
                    
                    # Botón para abrir chat IA (solo si está configurado)
                    if has_chat:
                        col_chat1, col_chat2 = st.columns(2)
                        with col_chat1:
                            if st.button("🤖 Chat IA del Módulo", key=f"open_chat_{module_id}", use_container_width=True, type="primary"):
                                st.session_state[f'show_chat_{module_id}'] = True
                                st.session_state[f'show_group_chat_{module_id}'] = False
                                st.rerun()
                        with col_chat2:
                            if st.button("👥 Chat Grupal IA", key=f"open_group_chat_{module_id}", use_container_width=True, type="secondary"):
                                st.session_state[f'show_group_chat_{module_id}'] = True
                                st.session_state[f'show_chat_{module_id}'] = False
                                st.rerun()

                        # Mostrar chat individual si está activado
                        if st.session_state.get(f'show_chat_{module_id}'):
                            render_module_chat_interface(conn, module_id, user['username'], module['title'], model)
                            
                            if st.button("❌ Cerrar chat", key=f"close_chat_{module_id}"):
                                st.session_state[f'show_chat_{module_id}'] = False
                                st.rerun()
                            
                            st.markdown("---")

                        # Mostrar chat grupal si está activado
                        if st.session_state.get(f'show_group_chat_{module_id}'):
                            render_group_chat_interface(conn, module_id, user['username'], 'student', module['title'], model)

                            if st.button("❌ Cerrar chat grupal", key=f"close_group_chat_{module_id}"):
                                st.session_state[f'show_group_chat_{module_id}'] = False
                                st.rerun()

                            st.markdown("---")
                    
                    # Materiales del módulo
                    materials_rows = conn.execute("""
                        SELECT * FROM course_materials 
                        WHERE module_id = ? 
                        ORDER BY order_index
                    """, (module['id'],)).fetchall()
                    materials = [dict(r) for r in materials_rows]
                    
                    if not materials:
                        st.info("📄 Sin materiales disponibles")
                    else:
                        for material in materials:
                            with st.container(border=True):
                                col_icon, col_content, col_action = st.columns([0.5, 4, 1])
                                
                                # Icono según tipo
                                icon = {
                                    'pdf': '📄',
                                    'video': '🎬',
                                    'text': '📝',
                                    'link': '🔗',
                                    'quiz': '❓'
                                }.get(material.get('type'), '📁')
                                
                                col_icon.markdown(f"## {icon}")
                                col_content.markdown(f"**{material['title']}**")
                                
                                if material.get('content_blob'):
                                    file_name = material.get('file_name') or f"material_{material['id']}"
                                    col_action.download_button(
                                        "⬇️",
                                        material['content_blob'],
                                        file_name,
                                        key=f"dl_{material['id']}",
                                        help="Descargar"
                                    )
                                    
                                    if material.get('type') == 'pdf':
                                        if col_action.checkbox("👁️", key=f"v_{material['id']}", help="Ver PDF"):
                                            display_pdf(material['content_blob'])
    
    with tab2:
        st.markdown("### 📝 Tareas del Curso")
        
        # Obtener tareas
        tasks_rows = conn.execute("""
            SELECT t.*, m.title as module_title
            FROM tasks t 
            LEFT JOIN modules m ON t.module_id = m.id 
            WHERE t.course_id = ? 
            ORDER BY t.due_date DESC
        """, (c['id'],)).fetchall()
        
        if not tasks_rows:
            st.info("📭 No hay tareas disponibles")
        else:
            for task_row in tasks_rows:
                task = dict(task_row)
                
                # Estado de la tarea
                submission = conn.execute("""
                    SELECT * FROM submissions 
                    WHERE task_id = ? AND student_id = ?
                """, (task['id'], user['username'])).fetchone()
                
                if submission:
                    submission = dict(submission)  # Convertir a diccionario
                    status_icon = "✅" if submission['status'] == 'graded' else "📤"
                    status_text = "Calificada" if submission['status'] == 'graded' else "Enviada"
                else:
                    status_icon = "📝"
                    status_text = "Pendiente"
                
                with st.expander(f"{status_icon} {task['title']} - {status_text}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Descripción:** {task.get('description', 'Sin descripción')}")
                        if task.get('module_title'):
                            st.markdown(f"**Módulo:** {task['module_title']}")
                        if task.get('due_date'):
                            st.markdown(f"**Fecha límite:** {task['due_date']}")
                    
                    with col2:
                        if submission:
                            if submission['status'] == 'graded':
                                st.success(f"Calificación: {submission.get('grade', 'N/A')}")
                            else:
                                st.info("Enviada - Esperando calificación")
                        else:
                            st.warning("Pendiente de envío")
    
    with tab3:
        st.markdown("### ✅ Exámenes del Curso")
        
        # Obtener exámenes
        exams_rows = conn.execute("""
            SELECT e.*, m.title as module_title
            FROM exams e 
            LEFT JOIN modules m ON e.module_id = m.id 
            WHERE e.course_id = ?
            ORDER BY e.created_at DESC
        """, (c['id'],)).fetchall()
        
        if not exams_rows:
            st.info("📭 No hay exámenes disponibles")
        else:
            for exam_row in exams_rows:
                exam = dict(exam_row)
                
                # Verificar si ya realizó el examen
                attempt = conn.execute("""
                    SELECT * FROM exam_attempts 
                    WHERE exam_id = ? AND student_id = ?
                """, (exam['id'], user['username'])).fetchone()
                
                if attempt:
                    attempt = dict(attempt)  # Convertir a diccionario
                    status_icon = "✅"
                    status_text = f"Completado - Puntuación: {attempt['score']}"
                else:
                    status_icon = "📝"
                    status_text = "Disponible"
                
                with st.expander(f"{status_icon} {exam['title']} - {status_text}"):
                    st.markdown(f"**Descripción:** {exam.get('description', 'Sin descripción')}")
                    if exam.get('module_title'):
                        st.markdown(f"**Módulo:** {exam['module_title']}")
                    
                    if attempt:
                        st.success(f"✅ Examen completado con puntuación: {attempt['score']}")
                    else:
                        if exam.get('is_published', 0) == 1:
                            if st.button(f"🚀 Iniciar Examen", key=f"start_exam_{exam['id']}", type="primary"):
                                st.info("Funcionalidad de examen en desarrollo")
                        else:
                            st.info("📭 Examen no publicado aún")
    
    with tab4:
        st.markdown("### 💬 Foro del Curso")
        st.info("💡 Funcionalidad de foro en desarrollo")
        st.markdown("Aquí podrás:")
        st.markdown("- 💬 Participar en discusiones")
        st.markdown("- ❓ Hacer preguntas al profesor")
        st.markdown("- 🤝 Colaborar con otros estudiantes")

def render_user_profile(conn, current_user):
    """Renderiza el perfil de un usuario con modo lectura/edición"""
    target_username = st.session_state.get('profile_target')
    
    if not target_username:
        st.error("❌ No se especificó un usuario")
        if st.button("🏠 Volver"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    # Obtener información del usuario
    user_row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (target_username,)
    ).fetchone()
    
    if not user_row:
        st.error("❌ Usuario no encontrado")
        if st.button("🏠 Volver"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    user = dict(user_row)
    is_own_profile = current_user['username'] == target_username
    
    # Inicializar modo de edición en session_state
    if 'profile_edit_mode' not in st.session_state:
        st.session_state.profile_edit_mode = False
    
    # Botón para volver
    return_to = st.session_state.get('profile_return_to', 'dashboard')
    
    col_back, col_edit = st.columns([1, 4])
    with col_back:
        if st.button("← Volver", type="secondary"):
            if return_to == 'course':
                st.session_state.view_mode = 'course'
            else:
                st.session_state.view_mode = 'dashboard'
            
            # Limpiar variables de perfil
            if 'profile_target' in st.session_state:
                del st.session_state.profile_target
            if 'profile_return_to' in st.session_state:
                del st.session_state.profile_return_to
            if 'profile_edit_mode' in st.session_state:
                del st.session_state.profile_edit_mode
            st.rerun()
    
    with col_edit:
        if is_own_profile:
            if not st.session_state.profile_edit_mode:
                if st.button("✏️ Editar Perfil", type="primary"):
                    st.session_state.profile_edit_mode = True
                    st.rerun()
            else:
                if st.button("❌ Cancelar Edición", type="secondary"):
                    st.session_state.profile_edit_mode = False
                    st.rerun()
    
    st.markdown("---")
    
    # MODO LECTURA
    if not st.session_state.profile_edit_mode:
        # Header del perfil
        col_avatar, col_info = st.columns([1, 3])
        
        with col_avatar:
            # Verificar cosméticos activos
            cosmetic_frame = ""
            cosmetic_badges = []
            try:
                from engagement import ShopManager
                cosmetics = ShopManager.get_active_cosmetics(user['username'])
                if cosmetics:
                    for cosmetic in cosmetics:
                        # Marcos
                        if 'frame' in cosmetic['key']:
                            metadata = cosmetic.get('metadata', {})
                            frame_color = metadata.get('frame_color', 'default')
                            
                            frame_styles = {
                                'gold': "border: 5px solid #FFD700; box-shadow: 0 0 20px #FFD700;",
                                'rainbow': "border: 5px solid transparent; background: linear-gradient(white, white) padding-box, linear-gradient(45deg, red, orange, yellow, green, blue, indigo, violet) border-box; box-shadow: 0 0 20px rgba(255,255,255,0.5);",
                                'fire': "border: 5px solid #ff4500; box-shadow: 0 0 20px #ff4500;",
                                'ice': "border: 5px solid #00ffff; box-shadow: 0 0 20px #00ffff;"
                            }
                            cosmetic_frame = frame_styles.get(frame_color, "")
                        
                        # Avatares especiales (mantener compatibilidad)
                        elif 'avatar_1' in cosmetic['key']:
                            cosmetic_frame = "border: 5px solid #ff6b6b; box-shadow: 0 0 20px #ff6b6b;"
                            cosmetic_badges.append("🥷 Ninja")
                        elif 'avatar_2' in cosmetic['key']:
                            cosmetic_frame = "border: 5px solid #4ecdc4; box-shadow: 0 0 20px #4ecdc4;"
                            cosmetic_badges.append("🤖 Robot")
                        
                        # Badges
                        elif 'badge' in cosmetic['key']:
                            metadata = cosmetic.get('metadata', {})
                            badge_type = metadata.get('badge_type', '')
                            
                            badge_emojis = {
                                'star': '⭐',
                                'crown': '👑',
                                'fire': '🔥',
                                'diamond': '💎'
                            }
                            emoji = badge_emojis.get(badge_type, '🏅')
                            cosmetic_badges.append(f"{emoji} {cosmetic['name'].split(':')[1].strip() if ':' in cosmetic['name'] else cosmetic['name']}")
            except:
                pass
            
            # Mostrar avatar con marco
            if user.get('avatar'):
                import base64
                b64 = base64.b64encode(user['avatar']).decode()
                st.markdown(f'<img src="data:image/png;base64,{b64}" style="width:150px;height:150px;border-radius:50%;{cosmetic_frame if cosmetic_frame else "border:3px solid #4a8fd8"};object-fit:cover">', unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="width: 150px; height: 150px; border-radius: 50%; background: linear-gradient(135deg, #4a8fd8 0%, #7e22ce 100%); 
                            display: flex; align-items: center; justify-content: center; font-size: 70px; {cosmetic_frame if cosmetic_frame else "border: 3px solid #4a8fd8"};">
                    👤
                </div>
                """, unsafe_allow_html=True)
            
            # Mostrar badges de cosméticos equipados
            if cosmetic_badges:
                for badge in cosmetic_badges:
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 5px 10px;
                        border-radius: 15px;
                        text-align: center;
                        margin-top: 5px;
                        font-size: 0.85em;
                        color: white;
                        font-weight: bold;
                    ">
                        {badge}
                    </div>
                    """, unsafe_allow_html=True)
        
        with col_info:
            st.title(user.get('full_name', 'Sin nombre'))
            
            # Mostrar título especial si tiene uno equipado
            title_text = ""
            try:
                from engagement import ShopManager
                cosmetics = ShopManager.get_active_cosmetics(user['username'])
                for cosmetic in cosmetics:
                    if 'title' in cosmetic['key']:
                        metadata = cosmetic.get('metadata', {})
                        title = metadata.get('title', '')
                        color = metadata.get('color', 'gold')
                        color_map = {
                            'gold': '#FFD700',
                            'blue': '#4a8fd8',
                            'purple': '#a78bfa'
                        }
                        title_color = color_map.get(color, '#FFD700')
                        title_text = f'<span style="color: {title_color}; font-weight: bold; font-size: 0.9em;">🏆 {title}</span>'
                        break
            except:
                pass
            
            # Badge de rol
            role_badge = {
                'student': '🎓 Estudiante',
                'teacher': '👨‍🏫 Profesor',
                'admin': '⚙️ Administrador'
            }.get(user.get('role'), '👤 Usuario')
            
            if title_text:
                st.markdown(f"{title_text}", unsafe_allow_html=True)
            st.markdown(f"### {role_badge}")
            
            if user.get('title'):
                st.markdown(f"**{user['title']}**")
            
            if user.get('bio'):
                st.markdown(f"*{user['bio']}*")
            else:
                st.caption("_Sin biografía_")
        
        st.markdown("---")
        
        # Información adicional
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📧 Información de Contacto")
            st.markdown(f"**Email:** {user.get('username', 'N/A')}")
        
        with col2:
            st.markdown("### 📊 Estadísticas")
            
            if user.get('role') == 'student':
                # Estadísticas de estudiante
                enrolled_count = conn.execute(
                    "SELECT COUNT(*) FROM enrollments WHERE student_id = ?",
                    (user['username'],)
                ).fetchone()[0]
                
                st.metric("📚 Cursos Inscritos", enrolled_count)
                
                # Mostrar racha si es estudiante
                try:
                    from engagement import StreakManager, PointsManager
                    
                    streak_info = StreakManager.get_streak_info(user['username'])
                    points_info = PointsManager.get_user_points_info(user['username'])
                    coins_info = PointsManager.get_user_coins(user['username'])
                    
                    st.markdown("---")
                    st.markdown("### 🎮 Progreso de Engagement")
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("🔥 Racha Actual", f"{streak_info['current_streak']} días")
                        st.caption(f"Récord: {streak_info['longest_streak']} días")
                    with col_b:
                        st.metric("⭐ Puntos", points_info['total_points'])
                        st.caption(f"Nivel {points_info['level']}")
                    with col_c:
                        st.metric("🪙 Monedas", coins_info['total_coins'])
                        st.caption(f"Ganadas: {coins_info['total_earned']}")
                except:
                    pass
                
            elif user.get('role') == 'teacher':
                # Estadísticas de profesor
                courses_count = conn.execute(
                    "SELECT COUNT(*) FROM courses WHERE teacher_id = ?",
                    (user['username'],)
                ).fetchone()[0]
                
                st.metric("📚 Cursos Impartidos", courses_count)
        
        st.markdown("---")
        
        # Cursos en común (si es estudiante viendo a otro estudiante)
        if current_user.get('role') == 'student' and user.get('role') == 'student' and current_user['username'] != user['username']:
            st.markdown("### 🤝 Cursos en Común")
            
            common_courses_rows = conn.execute("""
                SELECT DISTINCT c.* FROM courses c
                JOIN enrollments e1 ON c.id = e1.course_id
                JOIN enrollments e2 ON c.id = e2.course_id
                WHERE e1.student_id = ? AND e2.student_id = ?
            """, (current_user['username'], user['username'])).fetchall()
            
            common_courses = [dict(r) for r in common_courses_rows]
            
            if common_courses:
                for course in common_courses:
                    st.markdown(f"- 📚 **{course['name']}** ({course['code']})")
            else:
                st.info("No tienen cursos en común")
        
        # Cursos del profesor (si es profesor)
        if user.get('role') == 'teacher':
            st.markdown("### 📚 Cursos que Imparte")
            
            teacher_courses_rows = conn.execute(
                "SELECT * FROM courses WHERE teacher_id = ? ORDER BY name",
                (user['username'],)
            ).fetchall()
            
            teacher_courses = [dict(r) for r in teacher_courses_rows]
            
            if teacher_courses:
                for course in teacher_courses:
                    with st.container(border=True):
                        st.markdown(f"**{course['name']}**")
                        st.caption(f"📌 {course['code']} | {re.sub(r'<[^>]+>', '', course.get('description', 'Sin descripción')).strip()[:100]}")
            else:
                st.info("No imparte cursos actualmente")
    
    # MODO EDICIÓN (solo para perfil propio)
    else:
        st.title("✏️ Editar Perfil")
        
        with st.form("edit_profile_form"):
            # Foto de perfil
            st.subheader("📸 Foto de Perfil")
            col_current, col_upload = st.columns([1, 2])
            
            with col_current:
                st.markdown("**Foto actual:**")
                st.markdown(render_avatar(user.get('avatar'), 100), unsafe_allow_html=True)
            
            with col_upload:
                new_avatar = st.file_uploader(
                    "Subir nueva foto",
                    type=['png', 'jpg', 'jpeg'],
                    help="Límite: 2MB | Formatos: PNG, JPG, JPEG"
                )
            
            st.markdown("---")
            
            # Información básica
            st.subheader("👤 Información Básica")
            
            new_name = st.text_input("Nombre Completo", value=user.get('full_name', ''))
            new_title = st.text_input("Título / Carrera", value=user.get('title', ''))
            new_bio = st.text_area("Biografía", value=user.get('bio', ''), height=100)
            
            st.markdown("---")
            
            # Botones
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
            with col2:
                cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
            
            if submit:
                # Actualizar información
                try:
                    # Procesar avatar si se subió uno nuevo
                    avatar_data = user.get('avatar')
                    if new_avatar:
                        avatar_data = new_avatar.read()
                    
                    # Actualizar en BD
                    conn.execute("""
                        UPDATE users 
                        SET full_name = ?, title = ?, bio = ?, avatar = ?
                        WHERE username = ?
                    """, (new_name, new_title, new_bio, avatar_data, user['username']))
                    conn.commit()
                    
                    st.success("✅ Perfil actualizado exitosamente")
                    st.session_state.profile_edit_mode = False
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar perfil: {e}")
            
            if cancel:
                st.session_state.profile_edit_mode = False
                st.rerun()

def render_ai_course_simple(conn, user, model):
    """Renderiza vista completa de curso IA - NUEVA IMPLEMENTACIÓN OPTIMIZADA"""
    
    # Alias para compatibilidad
    u = user
    
    # Obtener información del curso IA
    ai_course_id = st.session_state.get('active_ai_course')
    if not ai_course_id:
        st.error("❌ No se encontró el curso IA")
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    # Usar función cacheada para obtener el curso (más rápido)
    ai_course = get_cached_ai_course(conn, ai_course_id)
    
    if not ai_course or ai_course.get('student_id') != user['username']:
        st.error("❌ Curso IA no encontrado")
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    # Verificar si el curso está pausado
    if ai_course.get('status') == 'paused':
        st.warning("⏸️ Este curso está pausado")
        if st.button("▶️ Reanudar Curso"):
            conn.execute("UPDATE ai_courses SET status = 'active' WHERE id = ?", (ai_course_id,))
            conn.commit()
            # Limpiar caché
            get_cached_ai_course.clear()
            st.rerun()
        return
    
    # Header del curso IA
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px; margin-bottom: 20px;">
        <h1 style="color: white; margin: 0;">🤖 {ai_course['language']} - Nivel {ai_course['level'].title()}</h1>
        <p style="color: #e0e0e0; margin: 10px 0 0 0;">Curso personalizado con IA • Progreso: {ai_course.get('progress_percentage', 0):.0f}%</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Botón volver
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
    with col2:
        if st.button("🔄 Limpiar Caché"):
            # Limpiar caché de funciones
            get_cached_ai_course.clear()
            get_cached_ai_sections.clear()
            st.success("✅ Caché limpiado")
            st.rerun()
    
    st.markdown("---")
    
    # Obtener todas las secciones del curso (usando caché para velocidad)
    sections_rows = get_cached_ai_sections(conn, ai_course_id)
    
    # Si no hay secciones, mostrar botón para generar
    if not sections_rows:
        st.info("📭 El contenido del curso aún no ha sido generado")
        
        if st.button("🚀 Generar Contenido Completo del Curso con IA", type="primary", use_container_width=True):
            with st.spinner("🤖 La IA está creando tu curso personalizado..."):
                try:
                    from utils_ai import generate_course_topics_structure, generate_topic_materials_spanish
                    
                    # Generar estructura basada en el nivel evaluado
                    st.info("📚 Generando estructura personalizada...")
                    topics_structure = generate_course_topics_structure(
                        model, 
                        ai_course['language'], 
                        ai_course['level'], 
                        8  # Generar 8 secciones completas
                    )
                    
                    if not topics_structure:
                        st.error("❌ Error al generar estructura")
                        return
                    
                    # Mensaje de inicio
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total_sections = len(topics_structure)
                    
                    status_text.info(f"🤖 Generando curso completo con IA... Esto tomará unos minutos.")
                    
                    # Crear cada sección Y generar su contenido
                    for idx, topic_data in enumerate(topics_structure, 1):
                        progress = idx / total_sections
                        progress_bar.progress(progress)
                        status_text.info(f"📝 Sección {idx}/{total_sections}: {topic_data['title']}")
                        
                        # Asegurar que objectives sea un string
                        objectives = topic_data.get('objectives', '')
                        if isinstance(objectives, list):
                            objectives = '. '.join(objectives)
                        elif not isinstance(objectives, str):
                            objectives = str(objectives)
                        
                        # Insertar sección
                        topic_cursor = conn.execute("""
                            INSERT INTO ai_course_topics 
                            (ai_course_id, topic_number, title, description, objectives, 
                             estimated_hours, order_index, is_unlocked, is_completed)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            ai_course_id,
                            topic_data['topic_number'],
                            topic_data['title'],
                            topic_data['description'],
                            objectives,
                            topic_data.get('estimated_hours', 3),
                            topic_data.get('order_index', 0),
                            1,  # Todas las secciones desbloqueadas desde el inicio
                            0
                        ))
                        
                        topic_id = topic_cursor.lastrowid
                        
                        # GENERAR CONTENIDO DE LA LECCIÓN CON IA
                        status_text.info(f"🎓 Generando contenido educativo para: {topic_data['title']}")
                        from utils_ai import generate_lesson_content
                        lesson_content = generate_lesson_content(
                            model,
                            ai_course['language'],
                            topic_data['title'],
                            topic_data.get('description', ''),
                            ai_course['level']
                        )
                        
                        # Guardar contenido en la base de datos
                        if lesson_content:
                            conn.execute("""
                                INSERT INTO ai_course_materials 
                                (ai_course_id, topic_id, type, title, description, url, 
                                 order_index, estimated_minutes, difficulty_level, language_content)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                ai_course_id, topic_id, 'tutorial',  # Usar 'tutorial' en lugar de 'lesson_content'
                                f"Lección: {topic_data['title']}", lesson_content, 
                                '#', 0, 30, 1, 'es'
                            ))
                        
                        # Las preguntas ahora se cargan del banco pre-generado
                        # No es necesario generar preguntas aquí
                        
                        # Generar materiales adicionales
                        status_text.info(f"📚 Generando materiales complementarios...")
                        topic_materials = generate_topic_materials_spanish(
                            model, 
                            ai_course['language'], 
                            topic_data['title'], 
                            topic_data['description'], 
                            ai_course['level']
                        )
                        
                        if topic_materials:
                            for material in topic_materials:
                                # Validar que el tipo sea uno de los permitidos
                                valid_types = ['video', 'website', 'tutorial', 'documentation', 'exercise']
                                material_type = material.get('type', 'website')
                                if material_type not in valid_types:
                                    material_type = 'website'  # Fallback a website si el tipo no es válido
                                
                                conn.execute("""
                                    INSERT INTO ai_course_materials 
                                    (ai_course_id, topic_id, type, title, description, url, 
                                     order_index, estimated_minutes, difficulty_level, language_content)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    ai_course_id, topic_id, material_type, 
                                    material.get('title', ''), material.get('description', ''), 
                                    material.get('url', '#'), material.get('order_index', 1), 
                                    material.get('estimated_minutes', 30),
                                    material.get('difficulty_level', 1), 
                                    material.get('language_content', 'es')
                                ))
                    
                    conn.commit()
                    progress_bar.progress(1.0)
                    status_text.success("✅ ¡Curso generado completamente!")
                    
                    # Notificar
                    from utils_notifications import notification_manager
                    notification_manager.notify_ai_course_enrollment(
                        student_id=u['username'],
                        course_title=f"{ai_course['language']} - Nivel {ai_course['level']}"
                    )
                    
                    st.success("✅ ¡Curso generado exitosamente!")
                    st.balloons()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        return
    
    # Navegación con apariencia de tabs pero renderizado condicional
    # Esto evita que se ejecuten todos los tabs a la vez
    
    # CSS para hacer que los radio buttons parezcan tabs
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        padding: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Inicializar tab seleccionado
    if 'selected_course_tab' not in st.session_state:
        st.session_state['selected_course_tab'] = 0
    
    # Crear botones que parecen tabs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📚 Secciones del Curso", use_container_width=True, 
                     type="primary" if st.session_state['selected_course_tab'] == 0 else "secondary"):
            st.session_state['selected_course_tab'] = 0
    
    with col2:
        if st.button("📊 Mi Progreso", use_container_width=True,
                     type="primary" if st.session_state['selected_course_tab'] == 1 else "secondary"):
            st.session_state['selected_course_tab'] = 1
    
    with col3:
        if st.button("🎓 Examen Final", use_container_width=True,
                     type="primary" if st.session_state['selected_course_tab'] == 2 else "secondary"):
            st.session_state['selected_course_tab'] = 2
    
    with col4:
        if st.button("⚙️ Configuración", use_container_width=True,
                     type="primary" if st.session_state['selected_course_tab'] == 3 else "secondary"):
            st.session_state['selected_course_tab'] = 3
    
    st.markdown("---")
    
    # Renderizar SOLO el contenido del tab seleccionado
    if st.session_state['selected_course_tab'] == 0:
        render_course_sections(conn, u, model, ai_course, sections_rows)
    elif st.session_state['selected_course_tab'] == 1:
        render_course_progress(conn, u, ai_course, sections_rows)
    elif st.session_state['selected_course_tab'] == 2:
        render_final_exam(conn, u, model, ai_course, sections_rows)
    elif st.session_state['selected_course_tab'] == 3:
        render_course_settings(conn, u, model, ai_course, ai_course_id)

def render_ai_course_config_only(conn, user, model):
    """Renderiza SOLO la configuración del curso IA"""
    
    # Alias para compatibilidad
    u = user
    
    # Obtener información del curso IA
    ai_course_id = st.session_state.get('active_ai_course')
    if not ai_course_id:
        st.error("❌ No se encontró el curso IA")
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    # Buscar el curso IA
    ai_course_row = conn.execute("""
        SELECT * FROM ai_courses 
        WHERE id = ? AND student_id = ?
    """, (ai_course_id, user['username'])).fetchone()
    
    if not ai_course_row:
        st.error("❌ Curso IA no encontrado")
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
        return
    
    ai_course = dict(ai_course_row)
    
    # Header del curso IA
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px; margin-bottom: 20px;">
        <h1 style="color: white; margin: 0;">⚙️ Configuración - {ai_course['language']} ({ai_course['level'].title()})</h1>
        <p style="color: #e0e0e0; margin: 10px 0 0 0;">Ajustes del curso personalizado con IA</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Botones de navegación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏠 Volver al Dashboard", use_container_width=True):
            st.session_state.view_mode = 'dashboard'
            st.rerun()
    
    with col2:
        if st.button("📚 Ir al Curso", use_container_width=True, type="primary"):
            st.session_state.view_mode = 'ai_course'
            st.rerun()
    
    st.markdown("---")
    
    # Renderizar configuración
    from ai_course_functions import render_course_settings
    render_course_settings(conn, u, model, ai_course, ai_course_id)

def create_sample_course_data(conn, user):
    """Crea datos de prueba para cursos si no existen"""
    try:
        # Verificar si ya hay cursos
        existing_courses = conn.execute("""
            SELECT COUNT(*) FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.student_id = ?
        """, (user['username'],)).fetchone()[0]
        
        if existing_courses == 0:
            # Crear un curso de prueba
            conn.execute("""
                INSERT OR IGNORE INTO courses 
                (name, code, description, teacher_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "Curso de Prueba - Programación Básica",
                "PROG101", 
                "Curso introductorio de programación con conceptos fundamentales",
                "admin",  # Asumiendo que admin existe
                "active",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            course_id = conn.lastrowid
            
            # Inscribir al estudiante
            conn.execute("""
                INSERT OR IGNORE INTO enrollments (student_id, course_id, enrollment_date)
                VALUES (?, ?, ?)
            """, (user['username'], course_id, datetime.now().strftime('%Y-%m-%d')))
            
            # Crear un módulo de prueba
            conn.execute("""
                INSERT OR IGNORE INTO modules 
                (course_id, title, description, order_index, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                course_id,
                "Módulo 1: Introducción",
                "Conceptos básicos de programación",
                1,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error creando datos de prueba: {e}")
        return False
    
    return False


# ========== FUNCIÓN PARA CHAT IA SEMANAL ==========

def render_group_chat_interface(conn, module_id, user_id, user_role, module_title, model):
    """
    Renderiza el chat grupal IA del módulo.
    Todos los alumnos y profesores pueden preguntar y ver las respuestas de todos.
    """
    from utils_chat_ai import GroupChatManager
    import html as html_module

    chat_manager = GroupChatManager(conn, model)

    # Verificar que hay contexto configurado
    content = chat_manager.get_chat_content(module_id)
    if not content:
        st.info("💬 El chat grupal no está disponible. El profesor debe configurar el material del módulo primero.")
        return

    st.markdown(f"### 👥 Chat Grupal IA: {module_title}")
    st.caption("Todos los alumnos y el profesor pueden preguntar y ver las respuestas")

    # Preguntas sugeridas (reutiliza las del chat individual)
    from utils_chat_ai import ModuleChatManager
    individual_manager = ModuleChatManager(conn, model)
    suggested_questions = individual_manager.get_suggested_questions(module_id)

    if suggested_questions:
        st.markdown("**💡 Preguntas sugeridas:**")
        cols = st.columns(2)
        for i, q in enumerate(suggested_questions):
            with cols[i % 2]:
                if st.button(q['question_text'], key=f"grp_suggested_{module_id}_{q['id']}_{user_id}", use_container_width=True):
                    with st.spinner("🤖 La IA está respondiendo..."):
                        result = chat_manager.send_message(module_id, user_id, user_role, q['question_text'])
                    if result['success']:
                        st.rerun()
                    else:
                        st.error(f"❌ {result.get('error', 'Error al enviar')}")

    st.markdown("---")

    # Historial de mensajes grupales
    messages = chat_manager.get_messages(module_id, limit=100)

    chat_container = st.container(height=450)
    with chat_container:
        if not messages:
            st.info("🗨️ Aún no hay mensajes. ¡Sé el primero en preguntar!")
        else:
            for msg in messages:
                # Desescapar primero por si fue guardado con html.escape(), luego re-escapar para el HTML
                safe_message = html_module.escape(html_module.unescape(str(msg['message'])))
                safe_response = html_module.escape(html_module.unescape(str(msg['response'])))
                timestamp = re.sub(r'<[^>]+>', '', str(msg.get('created_at', ''))).strip()
                display_name = html_module.escape(str(msg.get('display_name', msg['user_id'])))
                role_icon = "👨‍🏫" if msg['user_role'] == 'teacher' else "🧑‍🎓"
                role_label = "Profesor" if msg['user_role'] == 'teacher' else display_name
                is_me = msg['user_id'] == user_id

                # Burbuja del usuario (derecha si es el usuario actual, izquierda si es otro)
                align = "flex-end" if is_me else "flex-start"
                bg_user = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" if is_me else "linear-gradient(135deg, #2d6a4f 0%, #40916c 100%)"
                border_radius_user = "18px 18px 4px 18px" if is_me else "18px 18px 18px 4px"

                st.markdown(f"""
                <div style="display:flex; justify-content:{align}; margin-bottom:6px;">
                    <div style="background:{bg_user}; color:white; padding:10px 14px;
                                border-radius:{border_radius_user}; max-width:72%;
                                box-shadow:0 2px 6px rgba(0,0,0,0.15);">
                        <div style="font-size:0.8em; opacity:0.85; margin-bottom:3px;">
                            {role_icon} {role_label}
                        </div>
                        <div style="white-space:pre-wrap; word-wrap:break-word; line-height:1.4;">
                            {safe_message}
                        </div>
                        <div style="font-size:0.72em; opacity:0.65; text-align:right; margin-top:3px;">
                            {timestamp}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Respuesta de la IA (siempre a la izquierda)
                st.markdown(f"""
                <div style="display:flex; justify-content:flex-start; margin-bottom:14px; padding-left:10px;">
                    <div style="background:#1e1e2e; color:#e0e0e0; padding:10px 14px;
                                border-radius:4px 18px 18px 18px; max-width:80%;
                                border-left:3px solid #667eea;
                                box-shadow:0 2px 6px rgba(0,0,0,0.2);">
                        <div style="font-size:0.8em; color:#667eea; margin-bottom:3px;">🤖 IA</div>
                        <div style="white-space:pre-wrap; word-wrap:break-word; line-height:1.5;">
                            {safe_response}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # Input para nueva pregunta
    with st.form(key=f"group_chat_form_{module_id}_{user_id}", clear_on_submit=True):
        new_message = st.text_input(
            "Tu pregunta:",
            placeholder="Escribe tu pregunta sobre el módulo...",
            key=f"group_chat_input_{module_id}_{user_id}"
        )
        submitted = st.form_submit_button("📤 Enviar", type="primary", use_container_width=True)

        if submitted and new_message.strip():
            with st.spinner("🤖 La IA está respondiendo..."):
                result = chat_manager.send_message(module_id, user_id, user_role, new_message)
            if result['success']:
                st.rerun()
            else:
                st.error(f"❌ {result.get('error', 'Error al enviar')}")

    # Opción para el profesor de limpiar el chat
    if user_role == 'teacher':
        st.markdown("---")
        if st.button("🗑️ Limpiar todos los mensajes del chat grupal", key=f"clear_group_{module_id}", type="secondary"):
            chat_manager.delete_all_messages(module_id)
            st.success("Chat grupal limpiado")
            st.rerun()


def render_module_chat_interface(conn, module_id, student_id, module_title, model):
    """
    Renderiza la interfaz de chat IA para un módulo
    Se integra en la vista de módulos del estudiante
    """
    from utils_chat_ai import ModuleChatManager

    ai_manager = model  # El model ya es una instancia de AIManager
    chat_manager = ModuleChatManager(conn, ai_manager)
    
    # Verificar si el chat está configurado
    content = chat_manager.get_chat_content(module_id)
    
    if not content:
        st.info("💬 El chat IA no está disponible para este módulo aún")
        return
    
    st.markdown(f"### 🤖 Chat IA: {module_title}")
    st.caption("Haz preguntas sobre el material de este módulo")
    
    # Obtener preguntas sugeridas
    suggested_questions = chat_manager.get_suggested_questions(module_id)
    
    if suggested_questions:
        st.markdown("**💡 Preguntas sugeridas:**")
        cols = st.columns(2)
        for i, q in enumerate(suggested_questions):
            with cols[i % 2]:
                if st.button(
                    q['question_text'],
                    key=f"suggested_{module_id}_{q['id']}",
                    use_container_width=True
                ):
                    # Enviar la pregunta automáticamente
                    with st.spinner("🤖 La IA está pensando..."):
                        result = chat_manager.send_message(module_id, student_id, q['question_text'])
                    
                    if result['success']:
                        st.success("✅ Respuesta recibida")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Error: {result.get('error', 'No se pudo obtener respuesta')}")
                        time.sleep(2)
    
    st.markdown("---")
    
    # Historial de conversación
    history = chat_manager.get_conversation_history(module_id, student_id, limit=50)
    
    if history:
        st.markdown("**📜 Historial de conversación:**")
        
        # Contenedor con scroll para el historial
        chat_container = st.container(height=400)
        
        with chat_container:
            for conv in history:
                # Escapar HTML para evitar problemas (solo el contenido del mensaje)
                import html as html_module
                safe_message = html_module.escape(html_module.unescape(conv['message']))
                safe_response = html_module.escape(html_module.unescape(conv['response']))
                # Limpiar completamente el timestamp de cualquier HTML
                timestamp_raw = str(conv.get('created_at', ''))
                # Remover todas las etiquetas HTML
                timestamp = re.sub(r'<[^>]+>', '', timestamp_raw).strip()
                
                # Mensaje del estudiante (alineado a la derecha, estilo WhatsApp)
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
                    <div style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 12px 16px;
                        border-radius: 18px 18px 4px 18px;
                        max-width: 70%;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                    ">
                        <div style="font-weight: 500; margin-bottom: 4px; font-size: 0.85em; opacity: 0.9;">
                            🧑‍🎓 Tú
                        </div>
                        <div style="line-height: 1.4; white-space: pre-wrap; word-wrap: break-word;">
                            {safe_message}
                        </div>
                        <div style="text-align: right; font-size: 0.75em; margin-top: 4px; opacity: 0.7;">
                            {timestamp}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Respuesta de la IA (alineada a la izquierda, estilo WhatsApp)
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-start; margin-bottom: 15px;">
                    <div style="
                        background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
                        color: #e2e8f0;
                        padding: 12px 16px;
                        border-radius: 18px 18px 18px 4px;
                        max-width: 70%;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                        border-left: 3px solid #4299e1;
                    ">
                        <div style="font-weight: 500; margin-bottom: 4px; font-size: 0.85em; color: #4299e1;">
                            🤖 Asistente IA
                        </div>
                        <div style="line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;">
                            {safe_response}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("💬 No hay conversaciones previas. ¡Haz tu primera pregunta!")
    
    st.markdown("---")
    
    # Input para nueva pregunta
    st.markdown("**✍️ Haz una pregunta:**")
    
    # Usar session state para el input
    if f'chat_input_{module_id}' not in st.session_state:
        st.session_state[f'chat_input_{module_id}'] = ""
    
    question = st.text_area(
        "Tu pregunta:",
        value=st.session_state[f'chat_input_{module_id}'],
        height=100,
        placeholder="Escribe tu pregunta sobre el material del módulo...",
        max_chars=1000,
        key=f'question_input_{module_id}'
    )
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        send_button = st.button(
            "📤 Enviar pregunta",
            type="primary",
            use_container_width=True,
            disabled=not question.strip()
        )
    
    with col2:
        if st.button("🗑️ Limpiar", use_container_width=True):
            st.session_state[f'chat_input_{module_id}'] = ""
            st.rerun()
    
    if send_button and question.strip():
        # Rate limiting check
        last_message_key = f'last_message_time_{student_id}_{module_id}'
        current_time = time.time()
        
        if last_message_key in st.session_state:
            time_diff = current_time - st.session_state[last_message_key]
            if time_diff < 6:  # 10 mensajes por minuto = 1 cada 6 segundos
                st.warning(f"⏳ Por favor espera {int(6 - time_diff)} segundos antes de enviar otro mensaje")
                return
        
        with st.spinner("🤖 La IA está pensando..."):
            result = chat_manager.send_message(module_id, student_id, question)
        
        if result['success']:
            st.session_state[last_message_key] = current_time
            st.session_state[f'chat_input_{module_id}'] = ""
            st.success("✅ Respuesta recibida")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"❌ Error: {result.get('error', 'No se pudo obtener respuesta')}")



# ==============================================================================
# SISTEMA DE DESAFÍO DIARIO - ENGAGEMENT
# ==============================================================================
# PÁGINA DE PREGUNTA DIARIA
# ==============================================================================

def render_daily_question_page(conn, user):
    """Renderiza la página de pregunta diaria para mantener la racha"""
    try:
        from engagement import DailyQuestionManager, StreakManager, PointsManager
        
        st.title("📝 Pregunta del Día")
        st.markdown("Responde correctamente para mantener tu racha activa")
        
        # Verificar si ya respondió hoy
        has_answered = DailyQuestionManager.has_answered_today(user['username'])
        
        if has_answered:
            st.success("✅ ¡Ya respondiste la pregunta de hoy!")
            st.info("🔥 Tu racha está segura. Vuelve mañana para una nueva pregunta.")
            
            # Mostrar estado de racha
            streak_info = StreakManager.get_streak_info(user['username'])
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🔥 Racha Actual", f"{streak_info['current_streak']} días")
            with col2:
                st.metric("🏆 Récord", f"{streak_info['longest_streak']} días")
            with col3:
                st.metric("❄️ Congeladores", streak_info['freeze_count'])
            
            if st.button("← Volver al Dashboard", key="back_answered"):
                st.session_state.current_page = 'dashboard'
                st.rerun()
            return
        
        # Obtener o generar pregunta del día
        question = DailyQuestionManager.get_or_create_today_question()
        
        if not question:
            st.error("❌ No se pudo generar la pregunta del día. Intenta más tarde.")
            if st.button("← Volver al Dashboard", key="back_no_question"):
                st.session_state.current_page = 'dashboard'
                st.rerun()
            return
        
        # Mostrar información de racha
        streak_info = StreakManager.get_streak_info(user['username'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔥 Racha Actual", f"{streak_info['current_streak']} días")
        with col2:
            st.metric("🎯 Tema", question['topic'])
        with col3:
            st.metric("❄️ Congeladores", streak_info['freeze_count'])
        
        if streak_info['current_streak'] > 0:
            st.warning("⚠️ Responde correctamente para mantener tu racha activa")
        else:
            st.info("💡 Responde correctamente para comenzar tu racha")
        
        st.markdown("---")
        
        # Mostrar pregunta
        st.subheader(question['question_text'])
        
        # Opciones de respuesta
        options = {
            'A': question['option_a'],
            'B': question['option_b'],
            'C': question['option_c'],
            'D': question['option_d']
        }
        
        # Radio buttons para seleccionar respuesta
        selected_answer = st.radio(
            "Selecciona tu respuesta:",
            options=['A', 'B', 'C', 'D'],
            format_func=lambda x: f"{x}. {options[x]}",
            key="daily_question_answer"
        )
        
        # Botón de envío
        col1, col2 = st.columns([1, 3])
        with col1:
            submit_button = st.button("✅ Enviar Respuesta", type="primary", use_container_width=True, key="submit_answer_btn")
        
        with col2:
            if streak_info['freeze_count'] > 0:
                if st.button("❄️ Usar Congelador (Saltar Hoy)", use_container_width=True, key="use_freeze_btn"):
                    success, message = StreakManager.use_freeze(user['username'])
                    if success:
                        st.success("❄️ Congelador usado. Tu racha está protegida por hoy.")
                        time.sleep(1)
                        st.session_state.current_page = 'dashboard'
                        st.rerun()
                    else:
                        st.error(message)
        
        # Procesar respuesta
        if submit_button:
            with st.spinner("Verificando respuesta..."):
                is_correct, message = DailyQuestionManager.submit_answer(
                    user['username'],
                    question['id'],
                    selected_answer
                )
                
                if is_correct:
                    st.success(f"🎉 {message}")
                    st.balloons()
                    
                    # Mostrar explicación
                    with st.expander("📚 Explicación", expanded=True):
                        st.write(question['explanation'])
                    
                    # Actualizar racha
                    new_streak = StreakManager.get_streak_info(user['username'])
                    st.success(f"🔥 Racha actualizada: {new_streak['current_streak']} días")
                    
                    time.sleep(2)
                    st.session_state.current_page = 'dashboard'
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
                    
                    # Mostrar explicación
                    with st.expander("📚 Explicación", expanded=True):
                        st.write(question['explanation'])
                    
                    st.warning("💡 Intenta de nuevo mañana")
                    
                    if st.button("← Volver al Dashboard", key="back_incorrect"):
                        st.session_state.current_page = 'dashboard'
                        st.rerun()
        
        # Botón para volver
        st.markdown("---")
        if st.button("← Volver al Dashboard", key="back_main"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
            
    except Exception as e:
        st.error(f"Error cargando pregunta diaria: {e}")
        import traceback
        st.error(traceback.format_exc())
        if st.button("← Volver al Dashboard", key="back_error"):
            st.session_state.current_page = 'dashboard'
            st.rerun()

# ==============================================================================
# PÁGINA DE DESAFÍO DIARIO
# ==============================================================================

def render_daily_challenge_page(conn, user, model):
    """Renderiza la página del desafío diario"""
    try:
        from engagement import ChallengeManager, PointsManager, StatisticsManager
        from utils_ai import ai_evaluator
        
        st.title("💪 Desafío del Día")
        
        # Botón para regenerar desafío (solo para testing/admin)
        col_title, col_regen = st.columns([4, 1])
        with col_regen:
            if st.button("🔄 Nuevo Desafío", help="Genera un desafío completamente nuevo"):
                if ChallengeManager.delete_today_challenge('Python'):
                    st.success("✅ Generando nuevo desafío...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Error al regenerar desafío")
        
        # Obtener desafío del día
        challenge = ChallengeManager.get_today_challenge('Python')
        
        if not challenge:
            st.info("📅 No hay desafío disponible hoy. ¡Vuelve mañana!")
            if st.button("← Volver al Dashboard"):
                st.session_state.current_page = 'dashboard'
                st.rerun()
            return
        
        # Información del desafío
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💻 Lenguaje", challenge['language'])
        with col2:
            difficulty_colors = {'easy': '🟢', 'medium': '🟡', 'hard': '🔴'}
            difficulty_names = {'easy': 'FÁCIL', 'medium': 'MEDIO', 'hard': 'DIFÍCIL'}
            st.metric("Dificultad", f"{difficulty_colors.get(challenge['difficulty'], '⚪')} {difficulty_names.get(challenge['difficulty'], challenge['difficulty'].upper())}")
        with col3:
            st.metric("Puntos Base", challenge['points'])
        with col4:
            st.metric("Bonus 1er Intento", challenge['bonus_points'])
        
        # Título y descripción del desafío
        st.markdown(f"## 🎯 {challenge['title']}")
        
        # Parsear descripción si viene en formato JSON
        description = challenge['description']
        try:
            # Intentar parsear como JSON por si viene estructurado
            import json
            desc_data = json.loads(description)
            if isinstance(desc_data, dict):
                # Mostrar descripción estructurada
                st.markdown(f"**Descripción:** {desc_data.get('description', description)}")
                
                if desc_data.get('input_description'):
                    st.markdown(f"**Entrada:** {desc_data['input_description']}")
                
                if desc_data.get('output_description'):
                    st.markdown(f"**Salida:** {desc_data['output_description']}")
                
                # Ejemplos
                if desc_data.get('example_1_input'):
                    st.markdown("**Ejemplo 1:**")
                    st.code(f"Entrada: {desc_data['example_1_input']}\nSalida: {desc_data['example_1_output']}")
                
                if desc_data.get('example_2_input'):
                    st.markdown("**Ejemplo 2:**")
                    st.code(f"Entrada: {desc_data['example_2_input']}\nSalida: {desc_data['example_2_output']}")
                
                # Restricciones
                if desc_data.get('restrictions'):
                    st.markdown("**Restricciones:**")
                    for restriction in desc_data['restrictions']:
                        st.markdown(f"- {restriction}")
                
                # Pista
                if desc_data.get('hint'):
                    with st.expander("💡 Pista"):
                        st.info(desc_data['hint'])
            else:
                st.write(description)
        except:
            # Si no es JSON, mostrar como texto normal
            st.write(description)
        
        # Mostrar resultado de último intento si existe
        if 'last_challenge_result' in st.session_state and st.session_state.last_challenge_result:
            result_data = st.session_state.last_challenge_result
            
            # Mostrar estado: CORRECTO o INCORRECTO
            if result_data.get('is_correct', result_data.get('completed', False)):
                st.success("✅ **CORRECTO** - Tu código resuelve el problema correctamente")
                st.success(f"💰 Ganaste {result_data['points']} puntos")
            else:
                st.error("❌ **INCORRECTO** - Tu código necesita correcciones")
            
            # Mostrar aspectos positivos
            if result_data.get('positive_aspects'):
                with st.expander("✨ Aspectos Positivos de tu Código", expanded=True):
                    for aspect in result_data['positive_aspects']:
                        st.success(f"✓ {aspect}")
            
            # Mostrar aspectos a mejorar (solo si existen)
            if result_data.get('improvements'):
                with st.expander("🔧 Aspectos a Mejorar", expanded=True):
                    for improvement in result_data['improvements']:
                        st.warning(f"• {improvement}")
            
            # Mostrar explicación
            with st.expander("📝 Explicación Detallada", expanded=True):
                st.info(result_data.get('explanation', result_data.get('feedback', 'Evaluación completada')))
            
            # Limpiar resultado después de mostrarlo
            if st.button("✓ Entendido, continuar", key="clear_result_btn"):
                st.session_state.last_challenge_result = None
                st.rerun()
        
        # Estado del usuario
        status = ChallengeManager.get_user_challenge_status(challenge['id'], user['username'])
        
        if status['completed']:
            st.success(f"✅ ¡Completado! Puntos ganados: {status['total_points']}")
            st.info(f"Intentos: {status['attempts_count']} | Mejor puntuación: {status['best_score']}")
        else:
            if status['attempted']:
                st.info(f"Intentos realizados: {status['attempts_count']}")
        
        # Editor de código
        st.subheader("Tu Solución")
        code = st.text_area(
            "Escribe tu código aquí:",
            value=challenge['exercise_code'] if challenge['exercise_code'] else "",
            height=300,
            key="daily_challenge_code"
        )
        
        col1, col2 = st.columns([1, 3])
        with col1:
            submit_button = st.button("🚀 Enviar Solución", type="primary", key="submit_challenge_btn")
        
        with col2:
            hint_button = st.button("💡 Ver Pista", key="hint_challenge_btn")
        
        # Procesar envío de solución
        if submit_button:
            if not code or not code.strip():
                st.error("⚠️ Escribe tu código antes de enviar")
            else:
                with st.spinner("Evaluando tu código..."):
                    try:
                        from utils_ai import evaluate_challenge_code_clear
                        import google.generativeai as genai
                        
                        # Obtener API key
                        api_key = st.secrets.get("GEMINI_API_KEY", "")
                        if not api_key:
                            st.error("API key no configurada")
                            st.stop()
                        
                        # Configurar modelo (actualizado a Gemini 3.1)
                        genai.configure(api_key=api_key)
                        ai_model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
                        
                        # Evaluar código con el nuevo sistema
                        evaluation = evaluate_challenge_code_clear(
                            ai_model,
                            challenge['title'],
                            challenge['description'],
                            code,
                            challenge.get('solution_code')
                        )
                        
                        # Determinar puntuación para el sistema de puntos
                        # (solo para tracking interno, no se muestra al usuario)
                        score_100 = 100 if evaluation['is_correct'] else 40
                        completed = evaluation['is_correct']
                        
                        # Registrar intento
                        result = ChallengeManager.submit_challenge_attempt(
                            challenge['id'], 
                            user['username'], 
                            code, 
                            score_100, 
                            completed,
                            feedback=evaluation['explanation'],
                            time_spent=0
                        )
                        
                        # Guardar resultado en session_state para mostrarlo después del rerun
                        st.session_state.last_challenge_result = {
                            'is_correct': evaluation['is_correct'],
                            'positive_aspects': evaluation['positive_aspects'],
                            'improvements': evaluation['improvements'],
                            'explanation': evaluation['explanation'],
                            'completed': completed,
                            'points': result['points_earned']
                        }
                        
                        # Actualizar estadísticas si completó
                        if completed:
                            StatisticsManager.update_activity_calendar(
                                user['username'],
                                exercises=0,
                                challenges=1,
                                points=result['points_earned']
                            )
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al evaluar: {e}")
                        import traceback
                        st.error(traceback.format_exc())
        
        # Procesar pista
        if hint_button:
            st.info("💡 Pista: Revisa la sintaxis y asegúrate de seguir las buenas prácticas de Python")
        
        # Leaderboard del desafío
        st.subheader("🏆 Top 10 del Desafío")
        leaderboard = ChallengeManager.get_challenge_leaderboard(challenge['id'], 10)
        
        if leaderboard:
            for entry in leaderboard:
                medal = "🥇" if entry['rank'] == 1 else "🥈" if entry['rank'] == 2 else "🥉" if entry['rank'] == 3 else "  "
                st.write(f"{medal} {entry['rank']}. {entry['full_name']} - {entry['score']:.0f} pts ({entry['attempts']} intentos)")
        else:
            st.info("Sé el primero en completar este desafío!")
        

        # ── Recomendaciones personalizadas (TF-IDF + Coseno) ──────────────
        st.markdown("---")
        # ── Retos Recomendados (lazy: solo al presionar Actualizar) ──
        _col_rec_title, _col_rec_btn = st.columns([5, 1])
        with _col_rec_title:
            st.markdown("### 🎯 Retos Recomendados para ti")
        with _col_rec_btn:
            _refresh_recs_daily = st.button("🔄 Actualizar",
                key="refresh_recs_daily",
                help="Genera nuevos retos personalizados con IA",
                use_container_width=True)
        _sc = conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT dc.language, dc.title FROM daily_challenge_attempts dca JOIN daily_challenges dc ON dca.challenge_id = dc.id WHERE dca.user_id=?)",
            (user["username"],)
        ).fetchone()[0]
        if _sc > 0:
            st.caption(f"🧠 Perfil basado en {_sc} reto(s) · IA genera retos personalizados")
        else:
            st.caption("💡 Presiona Actualizar para recibir retos recomendados por IA")
        _rkey = f"cached_recs_daily_{user['username']}"
        if _refresh_recs_daily:
            if _rkey in st.session_state:
                del st.session_state[_rkey]
            with st.spinner("🤖 Generando retos personalizados con IA..."):
                try:
                    _new_recs = get_content_recommendations(
                        student_id=user["username"],
                        db_connection=conn,
                        limit=3,
                        model=model,
                    )
                    st.session_state[_rkey] = _new_recs
                    st.rerun()
                except Exception as _ge:
                    st.warning(f"⚠️ No se pudieron generar: {_ge}")
        _recs = st.session_state.get(_rkey, [])
        if _recs:
            _dc_map = {"easy": "#4caf50", "medium": "#ff9800", "hard": "#f44336"}
            _dn_map = {"easy": "FÁCIL", "medium": "MEDIO", "hard": "DIFÍCIL"}
            _rc = st.columns(len(_recs))
            for _rcol, _reto in zip(_rc, _recs):
                with _rcol:
                    _dc = _dc_map.get(_reto.get("difficulty",""),"#888")
                    _dn = _dn_map.get(_reto.get("difficulty",""),_reto.get("difficulty","").upper())
                    st.markdown(
                        f'<div style="border:1px solid #333;border-radius:10px;padding:14px;background:#1e1e1e;min-height:150px;">'
                        f'<div style="color:{_dc};font-size:0.72rem;font-weight:bold;margin-bottom:5px;">{_dn} &middot; {_reto.get("language","")}</div>'
                        f'<div style="color:white;font-size:0.92rem;font-weight:bold;margin-bottom:8px;">{_reto.get("title","Reto")}</div>'
                        f'<div style="color:#aaa;font-size:0.78rem;">💡 {_reto.get("recommendation_reason","")}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    _rid = str(_reto.get("id", id(_reto)))
                    if st.button("▶️ Hacer este reto", key=f"lr_daily_{_rid}", use_container_width=True, type="primary"):
                        _desc = _reto.get("description","")
                        st.session_state.current_challenge = f"# {_reto.get('title','Reto')}\n\n{_desc}"
                        st.session_state.challenge_lang = _reto.get("language","Python")
                        st.session_state.challenge_diff = _reto.get("difficulty","medium")
                        st.session_state.gym_evaluation_result = None
                        st.session_state.gym_show_solution = False
                        st.rerun()
        elif not _refresh_recs_daily:
            st.info("🤖 Presiona **Actualizar** para que la IA genere retos personalizados.")


        # Botón para volver
        if st.button("← Volver al Dashboard"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
            
    except Exception as e:
        st.error(f"Error cargando desafío: {e}")
        if st.button("← Volver al Dashboard"):
            st.session_state.current_page = 'dashboard'
            st.rerun()

# ==============================================================================
# SISTEMA DE CHAT PRIVADO
# ==============================================================================

def render_chat_interface(conn, user_id: str, user_role: str):
    """
    Renderiza la interfaz principal del chat privado.
    
    Layout:
        - Columna izquierda (30%): Lista de contactos
        - Columna derecha (70%): Ventana de conversación
    """
    from utils_chat import chat_manager, format_timestamp
    
    st.title("💬 Chat Privado")
    st.markdown("Comunícate directamente con tus compañeros y profesores")
    
    # Inicializar session state para chat
    if 'selected_contact' not in st.session_state:
        st.session_state.selected_contact = None
    if 'selected_conversation_id' not in st.session_state:
        st.session_state.selected_conversation_id = None
    if 'chat_course_filter' not in st.session_state:
        st.session_state.chat_course_filter = None
    
    # Layout de dos columnas
    col_contacts, col_chat = st.columns([3, 7])
    
    with col_contacts:
        render_contact_list(conn, user_id, user_role)
    
    with col_chat:
        if st.session_state.selected_conversation_id:
            render_conversation_window(conn, st.session_state.selected_conversation_id, user_id)
        else:
            st.info("👈 Selecciona un contacto para iniciar una conversación")
            st.markdown("""
            ### 💡 Cómo usar el chat
            
            1. **Selecciona un contacto** de la lista de la izquierda
            2. **Escribe tu mensaje** en el campo de texto
            3. **Adjunta archivos** si lo necesitas (PDF, imágenes, documentos)
            4. **Envía** y recibe respuestas en tiempo real
            
            #### 📋 Características:
            - ✅ Mensajes privados entre 2 personas
            - 📎 Adjuntar archivos (hasta 10 MB)
            - 🔔 Notificaciones de nuevos mensajes
            - 📊 Contador de mensajes no leídos
            - 🔍 Búsqueda de contactos
            """)


def render_contact_list(conn, user_id: str, user_role: str):
    """
    Renderiza la lista de contactos con búsqueda y filtros.
    Usa conn directamente para evitar problemas con instancias singleton.
    """
    st.markdown("### 👥 Contactos")
    
    # Obtener cursos del usuario para filtro
    if user_role == 'student':
        courses = conn.execute("""
            SELECT c.id, c.name FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.student_id = ?
            ORDER BY c.name
        """, (user_id,)).fetchall()
    else:  # teacher
        courses = conn.execute("""
            SELECT id, name FROM courses
            WHERE teacher_id = ?
            ORDER BY name
        """, (user_id,)).fetchall()
    
    # Filtro por curso
    course_options = ["Todos los cursos"] + [c['name'] for c in courses]
    selected_course_name = st.selectbox("📚 Filtrar por curso:", course_options, key="chat_course_select")
    
    course_filter = None
    if selected_course_name != "Todos los cursos":
        for c in courses:
            if c['name'] == selected_course_name:
                course_filter = c['id']
                break
    
    # Campo de búsqueda
    search_term = st.text_input("🔍 Buscar contacto:", placeholder="Nombre del contacto...", key="chat_search")

    # -------------------------------------------------------------------------
    # Obtener todas las conversaciones de este usuario directamente con conn
    # -------------------------------------------------------------------------
    try:
        raw = conn.execute("""
            SELECT
                c.id        AS conv_id,
                CASE WHEN c.user1_id = ? THEN c.user2_id ELSE c.user1_id END AS contact_id,
                c.last_message_at,
                c.course_id,
                co.name     AS course_name,
                co.code     AS course_code,
                u2.first_name, u2.last_name, u2.role AS contact_role
            FROM conversations c
            JOIN courses co ON c.course_id = co.id
            JOIN users u2 ON u2.username =
                CASE WHEN c.user1_id = ? THEN c.user2_id ELSE c.user1_id END
            WHERE (c.user1_id = ? OR c.user2_id = ?)
            ORDER BY c.last_message_at DESC
        """, (user_id, user_id, user_id, user_id)).fetchall()
        all_convs = [dict(r) for r in raw]
    except Exception:
        all_convs = []

    # Enriquecer con no-leídos y preview
    contacts = []
    for c in all_convs:
        # Aplicar filtro de curso
        if course_filter and c['course_id'] != course_filter:
            continue
        # Verificar que hay mensajes
        try:
            msg_count = conn.execute(
                "SELECT COUNT(*) FROM private_messages WHERE conversation_id = ?",
                (c['conv_id'],)
            ).fetchone()[0]
        except Exception:
            msg_count = 0
        if msg_count == 0:
            continue
        # No leídos
        try:
            unread = conn.execute("""
                SELECT COUNT(*) FROM private_messages
                WHERE conversation_id = ? AND recipient_id = ? AND is_read = 0
            """, (c['conv_id'], user_id)).fetchone()[0]
        except Exception:
            unread = 0
        # Último mensaje
        try:
            last = conn.execute("""
                SELECT message_text, sender_id FROM private_messages
                WHERE conversation_id = ?
                ORDER BY sent_at DESC LIMIT 1
            """, (c['conv_id'],)).fetchone()
            preview = (last['message_text'][:60] + '...') if last and len(last['message_text']) > 60 else (last['message_text'] if last else '')
            if last and last['sender_id'] == user_id:
                preview = f"Tú: {preview}"
        except Exception:
            preview = ''
        # Aplicar búsqueda
        full_name = f"{c['first_name']} {c['last_name']}"
        if search_term and search_term.lower() not in full_name.lower():
            continue
        contacts.append({
            'username': c['contact_id'],
            'first_name': c['first_name'],
            'last_name': c['last_name'],
            'role': c['contact_role'],
            'conversation_id': c['conv_id'],
            'course_name': c['course_name'],
            'course_code': c['course_code'],
            'unread_count': unread,
            'last_message_preview': preview,
            'last_message_at': c['last_message_at'],
        })

    # Separar Admin vs Cursos
    admin_contacts  = [c for c in contacts if c['role'] == 'admin']
    course_contacts = [c for c in contacts if c['role'] != 'admin']

    total = len(contacts)
    st.markdown(f"**{total}** contacto{'s' if total != 1 else ''}")

    # Sección Administración
    if admin_contacts:
        st.markdown("---")
        st.markdown("### 🛡️ Administración")
        for contact in admin_contacts:
            render_contact_card(conn, contact, user_id)

    # Sección Cursos
    if course_contacts:
        st.markdown("---")
        st.markdown("### 📚 Cursos")
        for contact in course_contacts:
            render_contact_card(conn, contact, user_id)

    # Acordeón para iniciar nuevos chats
    if course_filter:
        st.markdown("---")
        with st.expander("👀 Ver todos los integrantes del curso"):
            teacher = conn.execute("""
                SELECT u.username, u.first_name, u.last_name, u.avatar, u.role
                FROM users u
                JOIN courses c ON u.username = c.teacher_id
                WHERE c.id = ?
            """, (course_filter,)).fetchone()
            
            students = conn.execute("""
                SELECT u.username, u.first_name, u.last_name, u.avatar, u.role
                FROM users u
                JOIN enrollments e ON u.username = e.student_id
                WHERE e.course_id = ?
                ORDER BY u.last_name, u.first_name
            """, (course_filter,)).fetchall()
            
            if teacher:
                st.markdown("#### 👨‍🏫 Docente")
                render_all_members_card(conn, dict(teacher), user_id, course_filter)
            
            if students:
                st.markdown(f"#### 👨‍🎓 Estudiantes ({len(students)})")
                for student in students:
                    if student['username'] != user_id:
                        render_all_members_card(conn, dict(student), user_id, course_filter)

    if not contacts:
        st.info("No hay contactos disponibles. Usa el acordeón arriba para iniciar un chat con alguien del curso.")
        return


def render_all_members_card(conn, member: dict, user_id: str, course_id: int):
    """Renderiza una tarjeta de miembro del curso para iniciar chat"""
    from utils_chat import chat_manager
    import base64
    
    full_name = f"{member['first_name']} {member['last_name']}"
    role_badge = "👨‍🏫 Profesor" if member['role'] == 'teacher' else "👨‍🎓 Estudiante"
    
    # Avatar
    if member.get('avatar'):
        avatar_b64 = base64.b64encode(member['avatar']).decode('utf-8')
        avatar_html = f'<img src="data:image/png;base64,{avatar_b64}" style="width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 2px solid #58a6ff;">'
    else:
        initial = member['first_name'][0].upper() if member['first_name'] else 'U'
        color_hash = sum(ord(c) for c in full_name) % 6
        avatar_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F']
        avatar_color = avatar_colors[color_hash]
        avatar_html = f'<div style="width: 48px; height: 48px; border-radius: 50%; background-color: {avatar_color}; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 20px; color: white; border: 2px solid #58a6ff;">{initial}</div>'
    
    # Contenedor
    col1, col2, col3 = st.columns([1, 4, 2])
    
    with col1:
        st.markdown(avatar_html, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"**{full_name}**")
        st.caption(role_badge)
    
    with col3:
        if st.button("💬 Chatear", key=f"chat_member_{member['username']}", use_container_width=True):
            # Crear o obtener conversación
            conversation_id = chat_manager.create_or_get_conversation(
                user_id,
                member['username'],
                course_id
            )
            
            if conversation_id:
                # Configurar el estado correctamente
                st.session_state.selected_conversation_id = conversation_id
                st.session_state.selected_contact = member
                st.rerun()
            else:
                st.error("Error al iniciar conversación")
    
    st.markdown("---")


def render_contact_card(conn, contact: dict, user_id: str):
    """Renderiza una tarjeta de contacto individual"""
    from utils_chat import chat_manager, format_timestamp
    import base64
    
    # Determinar si hay mensajes no leídos
    has_unread = contact.get('unread_count', 0) > 0
    
    # Obtener inicial y color del avatar
    contact_name = f"{contact['first_name']} {contact['last_name']}"
    initial = contact['first_name'][0].upper() if contact.get('first_name') else 'U'
    
    # Generar color del avatar basado en el nombre (consistente)
    color_hash = sum(ord(c) for c in contact_name) % 6
    avatar_colors = [
        '#FF6B6B',  # Rojo
        '#4ECDC4',  # Turquesa
        '#45B7D1',  # Azul
        '#FFA07A',  # Naranja
        '#98D8C8',  # Verde agua
        '#F7DC6F'   # Amarillo
    ]
    avatar_color = avatar_colors[color_hash]
    
    # Crear contenedor con estilo
    with st.container():
        # Avatar y nombre en columnas
        col_avatar, col_info = st.columns([1, 5])
        
        with col_avatar:
            # Verificar si tiene foto de perfil
            if contact.get('avatar'):
                # Mostrar foto de perfil
                avatar_b64 = base64.b64encode(contact['avatar']).decode()
                st.markdown(f"""
                <div style="
                    width: 48px;
                    height: 48px;
                    border-radius: 50%;
                    overflow: hidden;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    margin: 0 auto;
                ">
                    <img src="data:image/png;base64,{avatar_b64}" 
                         style="width: 100%; height: 100%; object-fit: cover;">
                </div>
                """, unsafe_allow_html=True)
            else:
                # Mostrar avatar circular con inicial
                st.markdown(f"""
                <div style="
                    width: 48px;
                    height: 48px;
                    border-radius: 50%;
                    background-color: {avatar_color};
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-size: 20px;
                    color: white;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    margin: 0 auto;
                ">
                    {initial}
                </div>
                """, unsafe_allow_html=True)
        
        with col_info:
            # Nombre y badge de no leídos
            role_emoji = "👨‍🏫" if contact['role'] == 'teacher' else "👤"
            role_label = "Profesor" if contact['role'] == 'teacher' else "Estudiante"
            
            if has_unread:
                st.markdown(f"**🔴 {contact_name}** ({contact['unread_count']})")
            else:
                st.markdown(f"**{contact_name}**")
            
            # Mostrar curso y rol
            course_name = contact.get('course_name', 'Curso desconocido')
            st.caption(f"📚 {course_name} • {role_emoji} {role_label}")
            
            # Preview del último mensaje
            if contact.get('last_message_preview'):
                st.caption(f"💬 {contact['last_message_preview'][:40]}...")
            
            # Timestamp
            if contact.get('last_message_at'):
                st.caption(f"🕒 {format_timestamp(contact['last_message_at'])}")
        
        # Botones para abrir chat y borrar
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button(f"💬 Abrir chat", key=f"contact_{contact['username']}", use_container_width=True, type="primary" if has_unread else "secondary"):
                # Crear o obtener conversación
                if contact.get('conversation_id'):
                    st.session_state.selected_conversation_id = contact['conversation_id']
                else:
                    # Crear nueva conversación - necesitamos un course_id
                    # Obtener el primer curso en común
                    if st.session_state.user['role'] == 'student':
                        common_course = conn.execute("""
                            SELECT course_id FROM enrollments
                            WHERE student_id = ?
                            LIMIT 1
                        """, (user_id,)).fetchone()
                    else:
                        common_course = conn.execute("""
                            SELECT id as course_id FROM courses
                            WHERE teacher_id = ?
                            LIMIT 1
                        """, (user_id,)).fetchone()
                    
                    if common_course:
                        conv_id = chat_manager.create_or_get_conversation(
                            user_id, 
                            contact['username'], 
                            common_course['course_id']
                        )
                        st.session_state.selected_conversation_id = conv_id
                
                st.session_state.selected_contact = contact
                st.rerun()
        
        with col_btn2:
            if st.button(f"🗑️ Borrar", key=f"delete_{contact['username']}", use_container_width=True, type="secondary"):
                if contact.get('conversation_id'):
                    # Confirmar eliminación
                    if st.session_state.get(f'confirm_delete_{contact["username"]}'):
                        # Eliminar conversación
                        if chat_manager.delete_conversation(contact['conversation_id'], user_id):
                            # Limpiar estado de confirmación
                            if f'confirm_delete_{contact["username"]}' in st.session_state:
                                del st.session_state[f'confirm_delete_{contact["username"]}']
                            st.success("Chat eliminado")
                            st.rerun()
                        else:
                            st.error("Error al eliminar chat")
                    else:
                        # Solicitar confirmación
                        st.session_state[f'confirm_delete_{contact["username"]}'] = True
                        st.warning("⚠️ Haz clic nuevamente para confirmar")
                        st.rerun()
        
        st.markdown("---")


def render_conversation_window(conn, conversation_id: int, user_id: str):
    """
    Renderiza la ventana de conversación activa.
    Usa conn directamente para evitar problemas con instancias singleton.
    """
    import html as html_mod
    
    # Obtener información del contacto
    contact = st.session_state.get('selected_contact')
    if not contact:
        st.error("Error: No se pudo cargar la conversación")
        return
    
    # Header con nombre del contacto
    col1, col2 = st.columns([4, 1])
    with col1:
        contact_name = f"{contact['first_name']} {contact['last_name']}"
        role_map = {'teacher': 'Profesor', 'admin': '🛡️ Administrador', 'student': 'Estudiante'}
        role_label = role_map.get(contact.get('role', ''), contact.get('role', ''))
        course_info = contact.get('course_name', '')
        course_code = contact.get('course_code', '')
        st.markdown(f"### 💬 {contact_name}")
        st.caption(f"{role_label}" + (f" · {course_info} ({course_code})" if course_info else ""))
    
    with col2:
        if st.button("✖️ Cerrar", key="close_chat"):
            st.session_state.selected_conversation_id = None
            st.session_state.selected_contact = None
            st.rerun()
    
    st.markdown("---")
    
    # Marcar mensajes como leídos
    try:
        conn.execute("""
            UPDATE private_messages SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE conversation_id = ? AND recipient_id = ? AND is_read = 0
        """, (conversation_id, user_id))
        conn.commit()
    except Exception:
        pass
    
    # Obtener historial de mensajes
    try:
        msgs_rows = conn.execute("""
            SELECT pm.id, pm.sender_id, pm.recipient_id, pm.message_text,
                   pm.is_read, pm.sent_at,
                   u.first_name || ' ' || u.last_name AS sender_name
            FROM private_messages pm
            JOIN users u ON pm.sender_id = u.username
            WHERE pm.conversation_id = ?
            ORDER BY pm.sent_at ASC
        """, (conversation_id,)).fetchall()
        messages = [dict(r) for r in msgs_rows]
    except Exception:
        messages = []
    
    # Área de mensajes con scroll
    st.markdown("### 💬 Mensajes")
    with st.container(height=420):
        if not messages:
            st.info("No hay mensajes aún. ¡Inicia la conversación!")
        else:
            for msg in messages:
                is_own = msg['sender_id'] == user_id
                align = "flex-end" if is_own else "flex-start"
                bg = "#2a4a7c" if is_own else "#2a2a2a"
                name = "Tú" if is_own else msg['sender_name']
                try:
                    t = datetime.strptime(msg['sent_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m %H:%M')
                except Exception:
                    t = msg.get('sent_at', '')
                safe_text = html_mod.escape(msg['message_text'])
                st.markdown(f"""
                <div style="display:flex;justify-content:{align};margin-bottom:12px;">
                  <div style="background:{bg};padding:10px 14px;border-radius:12px;
                              max-width:70%;word-wrap:break-word;">
                    <div style="font-weight:bold;font-size:0.82em;color:#58a6ff;margin-bottom:4px;">{name}</div>
                    <div style="color:#fff;font-size:0.95em;">{safe_text}</div>
                    <div style="font-size:0.72em;color:#888;margin-top:4px;text-align:right;">{t}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### ✍️ Escribir mensaje")
    
    # Inicializar contador para limpiar el campo después de enviar
    if 'message_counter' not in st.session_state:
        st.session_state.message_counter = 0
    
    col_input, col_send = st.columns([4, 1])
    
    with col_input:
        message_text = st.text_area(
            "Mensaje:",
            height=100,
            placeholder="Escribe tu mensaje aquí...",
            key=f"chat_message_input_{st.session_state.message_counter}",
            label_visibility="collapsed"
        )
    
    # Adjuntar archivo
    uploaded_file = st.file_uploader(
        "📎 Adjuntar archivo (PDF, imágenes, documentos - máx 10MB)",
        type=['pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'txt'],
        key="chat_file_upload"
    )
    
    with col_send:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📤 Enviar", type="primary", use_container_width=True, key="send_message_btn"):
            if not message_text or not message_text.strip():
                st.error("⚠️ Escribe un mensaje antes de enviar")
            else:
                try:
                    # Obtener destinatario
                    conv_row = conn.execute("""
                        SELECT user1_id, user2_id FROM conversations WHERE id = ?
                    """, (conversation_id,)).fetchone()
                    if conv_row:
                        recipient_id = conv_row['user2_id'] if conv_row['user1_id'] == user_id else conv_row['user1_id']
                        conn.execute("""
                            INSERT INTO private_messages
                            (conversation_id, sender_id, recipient_id, message_text)
                            VALUES (?, ?, ?, ?)
                        """, (conversation_id, user_id, recipient_id, message_text.strip()))
                        conn.execute("""
                            UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?
                        """, (conversation_id,))
                        conn.commit()
                        st.session_state.message_counter += 1
                        st.rerun()
                    else:
                        st.error("Error: conversación no encontrada")
                except Exception as e:
                    st.error(f"Error al enviar: {e}")


def render_message_bubble(message: dict, is_own_message: bool):
    """
    Renderiza una burbuja de mensaje individual con estilo WhatsApp.
    """
    from utils_chat import format_timestamp, chat_manager
    import html as html_module
    import base64
    
    # Escapar el texto del mensaje para prevenir inyección HTML
    message_text = html_module.escape(message['message_text']) if message['message_text'] else ""
    timestamp = format_timestamp(message['sent_at'])
    
    # Obtener inicial del nombre del remitente
    sender_name = message.get('sender_name', 'Usuario')
    initial = sender_name[0].upper() if sender_name else 'U'
    
    # Generar color del avatar basado en el nombre (consistente)
    color_hash = sum(ord(c) for c in sender_name) % 6
    avatar_colors = [
        '#FF6B6B',  # Rojo
        '#4ECDC4',  # Turquesa
        '#45B7D1',  # Azul
        '#FFA07A',  # Naranja
        '#98D8C8',  # Verde agua
        '#F7DC6F'   # Amarillo
    ]
    avatar_color = avatar_colors[color_hash]
    
    # Colores y alineación según remitente
    if is_own_message:
        # Mensajes propios: morado, alineados a la derecha
        bg_gradient = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
        align = "flex-end"
        flex_direction = "row-reverse"
        avatar_margin = "0 0 0 10px"
    else:
        # Mensajes recibidos: gris oscuro, alineados a la izquierda
        bg_gradient = "linear-gradient(135deg, #2c3e50 0%, #34495e 100%)"
        align = "flex-start"
        flex_direction = "row"
        avatar_margin = "0 10px 0 0"
    
    # Crear HTML del avatar (foto o inicial)
    try:
        if message.get('sender_avatar') and message['sender_avatar']:
            # Tiene foto de perfil
            avatar_b64 = base64.b64encode(message['sender_avatar']).decode('utf-8')
            avatar_content = f'<img src="data:image/png;base64,{avatar_b64}" style="width: 100%; height: 100%; object-fit: cover;">'
        else:
            # Sin foto, mostrar inicial
            avatar_content = f'<div style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; font-weight: bold; font-size: 16px; color: white;">{initial}</div>'
    except Exception as e:
        # Si hay error, usar inicial
        avatar_content = f'<div style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; font-weight: bold; font-size: 16px; color: white;">{initial}</div>'
    
    # Generar HTML de adjuntos si existen
    attachments_html = ""
    if message.get('has_attachment') and message.get('attachments'):
        user_id = st.session_state.user['username']
        for attachment in message['attachments']:
            file_data = chat_manager.get_attachment(attachment['id'], user_id)
            if file_data:
                file_type = attachment['file_type']
                
                # Imágenes: mostrar miniatura inline
                if file_type in ['image/png', 'image/jpeg', 'image/gif']:
                    try:
                        img_b64 = base64.b64encode(file_data['file_content']).decode('utf-8')
                        attachments_html += f'<div style="margin-top: 8px;"><img src="data:{file_type};base64,{img_b64}" style="max-width: 200px; max-height: 200px; border-radius: 8px; display: block; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.3);" onclick="window.open(this.src, \'_blank\')"></div>'
                    except:
                        pass
                else:
                    # Otros archivos: mostrar icono y nombre con enlace de descarga
                    file_icon = {
                        'application/pdf': '📄',
                        'text/plain': '📃',
                        'application/msword': '📝',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📝'
                    }.get(file_type, '📎')
                    
                    size_mb = attachment['file_size'] / (1024 * 1024)
                    size_str = f"{size_mb:.2f} MB" if size_mb >= 1 else f"{attachment['file_size'] / 1024:.0f} KB"
                    file_name_short = attachment['file_name'][:30] + "..." if len(attachment['file_name']) > 30 else attachment['file_name']
                    
                    # Crear data URI para descarga
                    file_b64 = base64.b64encode(file_data['file_content']).decode('utf-8')
                    data_uri = f"data:{file_type};base64,{file_b64}"
                    
                    attachments_html += f'<a href="{data_uri}" download="{attachment["file_name"]}" style="text-decoration: none; color: inherit;"><div style="margin-top: 8px; padding: 8px 12px; background: rgba(255,255,255,0.1); border-radius: 8px; display: inline-block; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background=\'rgba(255,255,255,0.2)\'" onmouseout="this.style.background=\'rgba(255,255,255,0.1)\'"><div style="font-size: 13px;">{file_icon} {file_name_short}</div><div style="font-size: 11px; opacity: 0.7; margin-top: 2px;">{size_str} • Click para descargar</div></div></a>'
    
    # HTML del mensaje con avatar y adjuntos integrados (TODO EN UNA LÍNEA para evitar problemas)
    bubble_html = f'<div style="display: flex; justify-content: {align}; margin-bottom: 15px;"><div style="display: flex; flex-direction: {flex_direction}; align-items: flex-end; max-width: 75%;"><div style="width: 36px; height: 36px; border-radius: 50%; background-color: {avatar_color}; overflow: hidden; flex-shrink: 0; margin: {avatar_margin}; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">{avatar_content}</div><div style="background: {bg_gradient}; color: white; padding: 12px 16px; border-radius: 18px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); word-wrap: break-word;"><div style="font-size: 14px; line-height: 1.4; margin-bottom: 5px;">{message_text}</div>{attachments_html}<div style="font-size: 11px; opacity: 0.7; text-align: right; margin-top: 5px;">{timestamp}</div></div></div></div>'
    
    st.markdown(bubble_html, unsafe_allow_html=True)



# ==============================================================================
# PÁGINA DE TIENDA DE RECOMPENSAS
# ==============================================================================

def render_shop_page(conn, user):
    """Renderiza la página de la tienda de recompensas"""
    try:
        from engagement import ShopManager, PointsManager
        
        st.title("🎁 Tienda de Recompensas")
        st.caption("Canjea tus monedas por recompensas exclusivas")
        
        # Mostrar saldo del usuario
        coins_data = PointsManager.get_user_coins(user['username'])
        points_data = PointsManager.get_user_points_info(user['username'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🪙 Monedas", coins_data['total_coins'])
        with col2:
            st.metric("⭐ Puntos", points_data['total_points'])
        with col3:
            st.metric("📊 Nivel", points_data['level'])
        
        st.markdown("---")
        
        # Obtener items de la tienda
        items = ShopManager.get_shop_items()
        
        if not items:
            st.info("📦 La tienda está vacía. ¡Vuelve pronto para ver nuevos items!")
            if st.button("← Volver al Dashboard"):
                st.session_state.current_page = 'dashboard'
                st.rerun()
            return
        
        # Agrupar items por tipo
        items_by_type = {}
        for item in items:
            item_type = item['type']
            if item_type not in items_by_type:
                items_by_type[item_type] = []
            items_by_type[item_type].append(item)
        
        # Mapeo de tipos a nombres y emojis
        type_names = {
            'content': '📚 Contenido Premium',
            'certificate': '🎓 Certificados',
            'cosmetic': '🎨 Cosméticos',
            'feature': '⚡ Funciones Especiales'
        }
        
        # Mostrar items por categoría
        for item_type, type_items in items_by_type.items():
            st.subheader(type_names.get(item_type, item_type.capitalize()))
            
            # Crear columnas para mostrar items (3 por fila)
            cols = st.columns(3)
            for idx, item in enumerate(type_items):
                with cols[idx % 3]:
                    # Card del item
                    with st.container():
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            padding: 20px;
                            border-radius: 12px;
                            margin-bottom: 20px;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                        ">
                            <h3 style="color: white; margin: 0 0 10px 0;">{item['name']}</h3>
                            <p style="color: #f0f0f0; margin: 0 0 15px 0; font-size: 0.9em;">{item['description']}</p>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: #ffd700; font-size: 1.2em; font-weight: bold;">🪙 {item['cost_coins']}</span>
                                <span style="color: #f0f0f0; font-size: 0.85em;">Stock: {'∞' if item['stock'] == -1 else item['stock']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Botón de canje o equipar
                        can_afford = coins_data['total_coins'] >= item['cost_coins']
                        in_stock = item['stock'] == -1 or item['stock'] > 0
                        
                        # Verificar si ya tiene este cosmético
                        already_owned = False
                        is_equipped = False
                        if item['type'] == 'cosmetic':
                            try:
                                # Obtener todos los cosméticos del usuario (activos e inactivos)
                                conn_check = conn
                                owned_items = conn_check.execute('''
                                    SELECT is_active FROM user_active_items
                                    WHERE user_id = ? AND item_key = ?
                                ''', (user['username'], item['key'])).fetchone()
                                
                                if owned_items:
                                    already_owned = True
                                    is_equipped = owned_items[0] == 1
                            except:
                                pass
                        
                        if already_owned:
                            if is_equipped:
                                if st.button("✅ Equipado", key=f"equipped_{item['id']}", disabled=True, use_container_width=True):
                                    pass
                            else:
                                if st.button("🎨 Equipar", key=f"equip_{item['id']}", type="primary", use_container_width=True):
                                    success, message = ShopManager.equip_cosmetic(user['username'], item['key'])
                                    if success:
                                        st.success(f"✅ {message}")
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                        elif can_afford and in_stock:
                            if st.button(f"🎁 Canjear", key=f"buy_{item['id']}", type="primary", use_container_width=True):
                                success, message = ShopManager.purchase_item(user['username'], item['id'])
                                if success:
                                    st.success(f"✅ {message}")
                                    st.balloons()
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                        elif not in_stock:
                            st.button("❌ Agotado", key=f"sold_out_{item['id']}", disabled=True, use_container_width=True)
                        else:
                            st.button(f"🔒 Faltan {item['cost_coins'] - coins_data['total_coins']} 🪙", 
                                    key=f"cant_afford_{item['id']}", disabled=True, use_container_width=True)
            
            st.markdown("---")
        
        # Historial de canjes
        st.subheader("📜 Historial de Canjes")
        purchases = ShopManager.get_user_purchases(user['username'])
        
        if purchases:
            for purchase in purchases[:10]:  # Mostrar últimos 10 canjes
                col1, col2, col3 = st.columns([3, 1, 2])
                with col1:
                    st.write(f"**{purchase['name']}**")
                with col2:
                    st.write(f"🪙 {purchase['coins_spent']}")
                with col3:
                    st.write(f"📅 {purchase['purchased_at'][:10]}")
        else:
            st.info("No has canjeado recompensas aún")
        
        # Botón para volver
        st.markdown("---")
        if st.button("← Volver al Dashboard"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
            
    except Exception as e:
        st.error(f"Error cargando tienda: {e}")
        import traceback
        st.error(traceback.format_exc())
        if st.button("← Volver al Dashboard"):
            st.session_state.current_page = 'dashboard'
            st.rerun()