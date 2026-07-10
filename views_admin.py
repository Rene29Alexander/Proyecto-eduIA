import re
"""
Vista de administrador - Plataforma Educativa IA
Gestión completa del sistema, usuarios, cursos y configuración
"""

import streamlit as st
import pandas as pd
import base64
import json
import time
import hashlib
import io
from datetime import datetime, date, timedelta
from database import db_manager, hash_password, verify_password
from utils_security import security
from utils_notifications import notification_manager

def check_admin_schema(conn):
    """Asegura que existan todas las columnas necesarias"""
    cursor = conn.cursor()
    
    # Lista de columnas a verificar/crear en usuarios
    user_columns = [
        ('first_name', 'TEXT'),
        ('last_name', 'TEXT'),
        ('full_name', 'TEXT'),
        ('user_code', 'TEXT UNIQUE'),
        ('bio', 'TEXT DEFAULT ""'),
        ('title', 'TEXT DEFAULT ""'),
        ('subjects', 'TEXT DEFAULT ""'),
        ('social_links', 'TEXT DEFAULT ""'),
        ('avatar', 'BLOB'),
        ('theme', 'TEXT DEFAULT "dark"'),
        ('force_reset', 'INTEGER DEFAULT 0'),
        ('join_date', 'DATE DEFAULT CURRENT_DATE'),
        ('last_login', 'TIMESTAMP'),
        ('is_active', 'INTEGER DEFAULT 1'),
        ('email', 'TEXT'),
        ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ]
    
    for column_name, column_type in user_columns:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
            conn.commit()
        except:
            pass
    
    # Verificar configuración del sistema
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Configuración por defecto
        default_settings = [
            ('site_name', 'Plataforma Educativa IA', 'Nombre del sitio'),
            ('site_description', 'Plataforma educativa con inteligencia artificial', 'Descripción del sitio'),
            ('allow_registrations', '1', 'Permitir nuevos registros'),
            ('default_theme', 'dark', 'Tema por defecto'),
            ('maintenance_mode', '0', 'Modo mantenimiento'),
            ('max_file_size_mb', '10', 'Tamaño máximo de archivos (MB)'),
            ('session_timeout_minutes', '120', 'Tiempo de expiración de sesión'),
            ('ai_enabled', '1', 'Habilitar funciones de IA'),
            ('backup_enabled', '1', 'Habilitar backups automáticos'),
            ('email_notifications', '1', 'Habilitar notificaciones por email'),
            ('logo_url', '', 'URL del logo del sitio'),
            ('footer_text', '© 2026 Plataforma Educativa IA', 'Texto del footer'),
            ('gym_block_paste', '1', 'Bloquear pegar código en el Gimnasio de Código'),
        ]
        
        for key, value, description in default_settings:
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO system_settings (key, value, description) VALUES (?, ?, ?)",
                    (key, value, description)
                )
            except:
                pass
        
        conn.commit()
    except Exception as e:
        print(f"Error configurando sistema: {e}")

def render_user_avatar(avatar_bytes, size=50):
    """Renderiza avatar del usuario"""
    if avatar_bytes:
        b64 = base64.b64encode(avatar_bytes).decode()
        src = f"data:image/png;base64,{b64}"
    else:
        src = "https://cdn-icons-png.flaticon.com/512/847/847969.png"
    
    return f'<img src="{src}" style="width:{size}px;height:{size}px;border-radius:50%;border:2px solid #58a6ff;object-fit:cover;vertical-align:middle;">'

def get_role_display(role):
    """Obtiene icono y texto para rol"""
    roles = {
        'admin': ('🛡️', 'Administrador'),
        'teacher': ('👨‍🏫', 'Docente'),
        'student': ('🎓', 'Estudiante')
    }
    return roles.get(role, ('👤', role.capitalize()))

def validate_user_data(username, password, role, first_name, last_name, email):
    """Valida datos del usuario"""
    # Validar usuario
    valid, msg = security.validate_username(username)
    if not valid:
        return False, msg
    
    # Validar contraseña
    valid, msg = security.validate_password(password)
    if not valid:
        return False, msg
    
    # Validar email si se proporciona
    if email:
        valid, msg = security.validate_email(email)
        if not valid:
            return False, msg
    
    # Validar nombre
    if not first_name or not last_name:
        return False, "Nombre y apellido son obligatorios"
    
    if len(first_name) < 2 or len(last_name) < 2:
        return False, "Nombre y apellido deben tener al menos 2 caracteres"
    
    return True, ""

def view_admin(conn):
    """Vista principal del administrador"""
    
    # Función helper para notificaciones contextuales
    def create_admin_usage_notification(feature_name, feature_description):
        """Crea notificación cuando el admin usa una función por primera vez"""
        u = st.session_state.user
        existing = conn.execute("""
            SELECT id FROM notifications 
            WHERE user_id = ? AND title LIKE ? AND type = 'feature'
        """, (u['username'], f"%{feature_name}%")).fetchone()
        
        if not existing:
            notification_manager.create_notification(
                user_id=u['username'],
                title=f"⚙️ Usaste: {feature_name}",
                message=f"¡Perfecto! {feature_description} Continúa administrando la plataforma.",
                notification_type='success'
            )
    
    # Inicializar estado
    if 'admin_mode' not in st.session_state:
        st.session_state.admin_mode = 'dashboard'
    if 'admin_filter' not in st.session_state:
        st.session_state.admin_filter = {}
    if 'admin_selected_user' not in st.session_state:
        st.session_state.admin_selected_user = None
    if 'admin_edit_course' not in st.session_state:
        st.session_state.admin_edit_course = None
    
    # Verificar esquema
    check_admin_schema(conn)
    
    # ==============================================================================
    # VISTA PRINCIPAL: DASHBOARD
    # ==============================================================================
    # Primero verificar si hay un chat abierto (tiene prioridad sobre todo)
    if st.session_state.get('admin_selected_chat'):
        chat_data = st.session_state.admin_selected_chat
        contact = chat_data['contact']
        conversation_id = chat_data['conversation_id']
        import html as _html
        u = st.session_state.user

        col_back, col_info, col_del = st.columns([1, 8, 2])
        with col_back:
            if st.button("← Volver", key="admin_chat_back"):
                st.session_state.pop('admin_selected_chat', None)
                st.session_state.pop('admin_confirm_delete_chat', None)
                st.rerun()
        with col_info:
            contact_name = f"{contact['first_name']} {contact['last_name']}"
            course_name  = contact.get('course_name', 'Sin curso')
            course_code  = contact.get('course_code', '')
            contact_user = contact.get('contact_id', contact.get('username', ''))
            role_map = {'student': '🎓 Estudiante', 'teacher': '👨‍🏫 Profesor'}
            role_lbl = role_map.get(contact.get('contact_role', contact.get('role', '')), '')
            st.markdown(f"### 💬 Chat con {contact_name}")
            st.caption(f"{role_lbl}  ·  📚 {course_name} ({course_code})  ·  Usuario: `{contact_user}`")
        with col_del:
            if st.button("🗑️ Borrar chat", key="admin_delete_chat", type="secondary", use_container_width=True):
                st.session_state['admin_confirm_delete_chat'] = True

        if st.session_state.get('admin_confirm_delete_chat'):
            st.warning(f"¿Borrar todos los mensajes con {contact_name}?")
            col_yes, col_no = st.columns(2)
            if col_yes.button("✅ Sí, borrar todo", key="admin_confirm_del_yes", type="primary"):
                try:
                    conn.execute("DELETE FROM private_messages WHERE conversation_id = ?", (conversation_id,))
                    conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
                    conn.commit()
                    st.session_state.pop('admin_selected_chat', None)
                    st.session_state.pop('admin_confirm_delete_chat', None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            if col_no.button("❌ Cancelar", key="admin_confirm_del_no"):
                st.session_state.pop('admin_confirm_delete_chat', None)
                st.rerun()

        st.markdown("---")

        try:
            conn.execute("""
                UPDATE private_messages SET is_read = 1, read_at = CURRENT_TIMESTAMP
                WHERE conversation_id = ? AND recipient_id = ? AND is_read = 0
            """, (conversation_id, u['username']))
            conn.commit()
        except Exception:
            pass

        try:
            msgs_rows = conn.execute("""
                SELECT pm.sender_id, pm.message_text, pm.sent_at,
                       u2.first_name || ' ' || u2.last_name AS sender_name
                FROM private_messages pm
                JOIN users u2 ON pm.sender_id = u2.username
                WHERE pm.conversation_id = ?
                ORDER BY pm.sent_at ASC
            """, (conversation_id,)).fetchall()
            messages = [dict(r) for r in msgs_rows]
        except Exception as e:
            messages = []
            st.error(f"Error: {e}")

        st.markdown("### 💬 Mensajes")
        with st.container(height=480):
            if messages:
                for msg in messages:
                    is_mine = msg['sender_id'] == u['username']
                    align = "flex-end" if is_mine else "flex-start"
                    bg    = "#2a4a7c" if is_mine else "#2a2a2a"
                    name  = "Tú" if is_mine else msg['sender_name']
                    try:
                        t = datetime.strptime(msg['sent_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m %H:%M')
                    except Exception:
                        t = ""
                    safe = _html.escape(msg['message_text'])
                    st.markdown(f"""
                    <div style="display:flex;justify-content:{align};margin-bottom:14px;">
                      <div style="background:{bg};padding:10px 15px;border-radius:12px;max-width:70%;word-wrap:break-word;">
                        <div style="font-weight:bold;font-size:0.85em;color:#58a6ff;margin-bottom:4px;">{name}</div>
                        <div style="color:#fff;font-size:0.95em;">{safe}</div>
                        <div style="font-size:0.72em;color:#888;margin-top:4px;text-align:right;">{t}</div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No hay mensajes aún.")

        st.markdown("---")
        st.markdown("### ✍️ Enviar Mensaje")
        if 'admin_msg_counter' not in st.session_state:
            st.session_state.admin_msg_counter = 0
        msg_text = st.text_area("Mensaje:", height=90,
            placeholder="Escribe tu mensaje...",
            key=f"admin_chat_msg_{st.session_state.admin_msg_counter}")
        col_send, _ = st.columns([1, 4])
        with col_send:
            if st.button("📤 Enviar", type="primary", use_container_width=True, key="admin_send_msg"):
                if msg_text.strip():
                    try:
                        conv_row = conn.execute(
                            "SELECT user1_id, user2_id FROM conversations WHERE id = ?",
                            (conversation_id,)).fetchone()
                        if conv_row:
                            rid = conv_row['user2_id'] if conv_row['user1_id'] == u['username'] else conv_row['user1_id']
                            conn.execute("""
                                INSERT INTO private_messages (conversation_id, sender_id, recipient_id, message_text)
                                VALUES (?, ?, ?, ?)
                            """, (conversation_id, u['username'], rid, msg_text.strip()))
                            conn.execute("UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
                            conn.commit()
                            st.session_state.admin_msg_counter += 1
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                else:
                    st.warning("⚠️ Escribe un mensaje")
        return

    elif st.session_state.admin_mode == 'dashboard':
        # Notificación de acceso al panel admin
        create_admin_usage_notification(
            "Panel de Control", 
            "Has accedido al panel de administración donde puedes gestionar usuarios, cursos y configuraciones del sistema."
        )
        
        # Header con foto de perfil y saludo
        u = st.session_state.user
        col1, col2 = st.columns([1, 8])
        
        with col1:
            # Mostrar avatar del administrador
            if u.get('avatar'):
                avatar_b64 = base64.b64encode(u['avatar']).decode()
                st.markdown(f"""
                <div style="display: flex; justify-content: center; margin-top: 10px;">
                    <img src="data:image/png;base64,{avatar_b64}" 
                         style="width: 80px; height: 80px; border-radius: 50%; 
                                border: 3px solid #58a6ff; object-fit: cover;">
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="display: flex; justify-content: center; margin-top: 10px;">
                    <img src="https://cdn-icons-png.flaticon.com/512/847/847969.png" 
                         style="width: 80px; height: 80px; border-radius: 50%; 
                                border: 3px solid #58a6ff; object-fit: cover;">
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.title("🛡️ Panel de Control del Administrador")
            st.caption(f"⚙️ Administrador: {u.get('full_name', 'Admin')} • Última actividad: {datetime.now().strftime('%d/%m/%Y')}")
        
        st.markdown("---")
        
        st.divider()
        
        active_tab = st.session_state.get('admin_tab', 'usuarios')
        
        def _tab_active(name):
            return active_tab == name
        
        # ----------------------------------------------------------------------
        # TAB 1: GESTIÓN DE USUARIOS
        # ----------------------------------------------------------------------
        if _tab_active('usuarios'):
            col_create, col_list = st.columns([1, 2])
            
            # --- COLUMNA IZQUIERDA: CREAR USUARIO ---
            with col_create:
                st.markdown("### ➕ Crear Nuevo Usuario")

                # Inicializar session_state para persistir valores entre rerenders
                _cu_defaults = {
                    'cu_role': 'student', 'cu_fname': '', 'cu_lname': '',
                    'cu_user': '', 'cu_email': '', 'cu_title': '', 'cu_bio': '',
                    'cu_active': True, 'cu_errors': {}, 'cu_form_ver': 0,
                }
                for k, v in _cu_defaults.items():
                    if k not in st.session_state:
                        st.session_state[k] = v

                errors = st.session_state.cu_errors

                def _err(field):
                    """Muestra mensaje de error rojo si hay error en el campo"""
                    if field in errors:
                        st.markdown(
                            f'<p style="color:#e05252;font-size:0.85em;margin:0 0 2px 0;">⚠️ {errors[field]}</p>',
                            unsafe_allow_html=True
                        )

                # Rol — si no es Kratos, no puede crear admins
                viewer_is_kratos_form = st.session_state.user['username'] == 'admin'
                role_options = ["student", "teacher", "admin"] if viewer_is_kratos_form else ["student", "teacher"]
                role_idx = role_options.index(st.session_state.cu_role) if st.session_state.cu_role in role_options else 0
                new_role = st.selectbox(
                    "Rol",
                    role_options,
                    index=role_idx,
                    format_func=lambda x: {"student": "🎓 Estudiante", "teacher": "👨‍🏫 Docente", "admin": "🛡️ Administrador"}[x],
                    key="cu_role_sel"
                )
                if not viewer_is_kratos_form:
                    st.caption("🔒 Solo Kratos puede crear administradores")

                col_name1, col_name2 = st.columns(2)
                with col_name1:
                    _err('cu_fname')
                    new_fname = st.text_input("Nombres *", value=st.session_state.cu_fname, placeholder="Juan")
                with col_name2:
                    _err('cu_lname')
                    new_lname = st.text_input("Apellidos *", value=st.session_state.cu_lname, placeholder="Pérez")

                _err('cu_user')
                new_user = st.text_input("Usuario *", value=st.session_state.cu_user, placeholder="juan.perez")

                _err('cu_pass')
                new_pass = st.text_input(
                    "Contraseña *", type="password",
                    placeholder="Mínimo 8 caracteres",
                    key=f"cu_pass_{st.session_state.cu_form_ver}"
                )

                _err('cu_confirm')
                confirm_pass = st.text_input(
                    "Confirmar Contraseña *", type="password",
                    key=f"cu_confirm_{st.session_state.cu_form_ver}"
                )

                _err('cu_email')
                new_email = st.text_input("Email (opcional)", value=st.session_state.cu_email, placeholder="ejemplo@correo.com")

                col_date, col_active = st.columns(2)
                new_date = col_date.date_input("Fecha de Ingreso", value=date.today(), min_value=date(2000, 1, 1), max_value=date.today())
                new_active = col_active.checkbox("Usuario Activo", value=st.session_state.cu_active)

                new_title = st.text_input("Título/Especialidad (opcional)", value=st.session_state.cu_title, placeholder="Ing. Sistemas")
                new_bio = st.text_area("Biografía (opcional)", value=st.session_state.cu_bio, placeholder="Breve descripción...", height=80)

                if st.button("📋 Registrar Usuario", type="primary", use_container_width=True, key="cu_submit_btn"):
                    # Persistir valores actuales antes de validar
                    st.session_state.cu_role   = new_role
                    st.session_state.cu_fname  = new_fname
                    st.session_state.cu_lname  = new_lname
                    st.session_state.cu_user   = new_user
                    st.session_state.cu_email  = new_email
                    st.session_state.cu_title  = new_title
                    st.session_state.cu_bio    = new_bio
                    st.session_state.cu_active = new_active

                    # Validar campo por campo
                    errs = {}
                    if not new_fname.strip():
                        errs['cu_fname'] = "El nombre es obligatorio"
                    if not new_lname.strip():
                        errs['cu_lname'] = "El apellido es obligatorio"
                    if not new_user.strip():
                        errs['cu_user'] = "El usuario es obligatorio"
                    if not new_pass:
                        errs['cu_pass'] = "La contraseña es obligatoria"
                    elif len(new_pass) < 8:
                        errs['cu_pass'] = "Mínimo 8 caracteres"
                    if not confirm_pass:
                        errs['cu_confirm'] = "Debes confirmar la contraseña"
                    elif new_pass and new_pass != confirm_pass:
                        errs['cu_confirm'] = "Las contraseñas no coinciden"
                    if new_email and '@' not in new_email:
                        errs['cu_email'] = "El email no es válido"

                    if not errs:
                        valid, msg = validate_user_data(new_user, new_pass, new_role, new_fname, new_lname, new_email)
                        if not valid:
                            msg_lower = msg.lower()
                            if 'usuario' in msg_lower or 'username' in msg_lower or 'existe' in msg_lower:
                                errs['cu_user'] = msg
                            elif 'contraseña' in msg_lower or 'password' in msg_lower:
                                errs['cu_pass'] = msg
                            elif 'email' in msg_lower or 'correo' in msg_lower:
                                errs['cu_email'] = msg
                            else:
                                errs['_general'] = msg

                    st.session_state.cu_errors = errs

                    if errs:
                        st.rerun()
                    else:
                        try:
                            user_code    = db_manager.generate_user_code(new_role)
                            password_hash = hash_password(new_pass)
                            full_name    = f"{new_fname.strip()} {new_lname.strip()}"

                            conn.execute("""
                                INSERT INTO users (
                                    username, password_hash, role, first_name, last_name, full_name,
                                    user_code, email, bio, title, join_date, is_active
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                new_user, password_hash, new_role,
                                new_fname.strip(), new_lname.strip(), full_name,
                                user_code,
                                new_email or None, new_bio or None,
                                new_title or None, new_date,
                                1 if new_active else 0
                            ))
                            conn.commit()

                            db_manager.log_activity(
                                user_id=st.session_state.user['username'],
                                action='user_created', entity_type='user', entity_id=new_user,
                                details={'role': new_role, 'by_admin': st.session_state.user['username']}
                            )

                            # Limpiar formulario: resetear todos los valores a default
                            st.session_state.cu_role     = 'student'
                            st.session_state.cu_fname    = ''
                            st.session_state.cu_lname    = ''
                            st.session_state.cu_user     = ''
                            st.session_state.cu_email    = ''
                            st.session_state.cu_title    = ''
                            st.session_state.cu_bio      = ''
                            st.session_state.cu_active   = True
                            st.session_state.cu_errors   = {}
                            # Incrementar versión → cambia keys de contraseña → navegador no autocompletará
                            st.session_state.cu_form_ver = st.session_state.get('cu_form_ver', 0) + 1
                            # Forzar que el selectbox también se reinicie
                            if 'cu_role_sel' in st.session_state:
                                del st.session_state['cu_role_sel']

                            st.success(f"✅ Usuario '{new_user}' creado exitosamente")
                            st.balloons()
                            time.sleep(1)
                            st.rerun()

                        except Exception as e:
                            st.session_state.cu_errors = {'_general': str(e)}
                            st.rerun()

                if errors.get('_general'):
                    st.error(f"❌ {errors['_general']}")

            # --- COLUMNA DERECHA: LISTA DE USUARIOS ---
            with col_list:
                st.markdown("### 📋 Directorio de Usuarios")
                
                # Filtros
                col_filter1, col_filter2, col_filter3 = st.columns(3)
                
                with col_filter1:
                    filter_role = st.selectbox(
                        "Filtrar por rol",
                        ["Todos", "admin", "teacher", "student"],
                        format_func=lambda x: {
                            "Todos": "👥 Todos",
                            "admin": "🛡️ Admin",
                            "teacher": "👨‍🏫 Docente",
                            "student": "🎓 Estudiante"
                        }[x]
                    )
                
                with col_filter2:
                    filter_status = st.selectbox(
                        "Filtrar por estado",
                        ["Todos", "Activos", "Inactivos"]
                    )
                
                with col_filter3:
                    search_term = st.text_input("🔍 Buscar...", placeholder="Nombre, usuario o email")
                
                # Construir consulta
                query = """
                    SELECT username, full_name, role, user_code, email, is_active, 
                           avatar, last_login, join_date, title
                    FROM users
                    WHERE 1=1
                """
                params = []
                
                if filter_role != "Todos":
                    query += " AND role = ?"
                    params.append(filter_role)
                
                if filter_status == "Activos":
                    query += " AND is_active = 1"
                elif filter_status == "Inactivos":
                    query += " AND is_active = 0"
                
                if search_term:
                    query += " AND (full_name LIKE ? OR username LIKE ? OR email LIKE ? OR user_code LIKE ?)"
                    search_pattern = f"%{search_term}%"
                    params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
                
                query += " ORDER BY role, full_name"
                
                # Ejecutar consulta y CONVERTIR A DICCIONARIOS (Corrección .get error)
                users_rows = conn.execute(query, params).fetchall()
                users = [dict(row) for row in users_rows]
                
                if not users:
                    st.info("📭 No se encontraron usuarios")
                else:
                    # Mostrar usuarios en contenedor desplazable
                    with st.container(height=500):
                        for user in users:
                            with st.container(border=True):
                                col_avatar, col_info, col_actions = st.columns([1, 3, 2])
                                
                                # Avatar
                                with col_avatar:
                                    st.markdown(render_user_avatar(user['avatar'], 50), unsafe_allow_html=True)
                                
                                # Información
                                with col_info:
                                    icon, role_text = get_role_display(user['role'])
                                    st.markdown(f"**{user['full_name']}**")
                                    st.caption(f"{icon} {role_text} | {user['user_code']}")
                                    
                                    if user['email']:
                                        st.caption(f"📧 {user['email']}")
                                    
                                    if user['title']:
                                        st.caption(f"🎓 {user['title']}")
                                    
                                    status_color = "🟢" if user['is_active'] else "🔴"
                                    st.caption(f"{status_color} {'Activo' if user['is_active'] else 'Inactivo'}")
                                
                                # Acciones
                                with col_actions:
                                    col_btn1, col_btn2, col_btn3 = st.columns(3)

                                    SUPERPROTECTED = {'admin'}  # username de Kratos
                                    is_kratos = user['username'] in SUPERPROTECTED
                                    is_self = user['username'] == st.session_state.user['username']
                                    viewer_is_kratos = st.session_state.user['username'] in SUPERPROTECTED
                                    target_is_admin = user['role'] == 'admin'

                                    # Ver perfil — siempre disponible
                                    if col_btn1.button("👁️ Ver", key=f"view_{user['username']}", help="Ver perfil"):
                                        st.session_state.profile_target = user['username']
                                        st.session_state.current_page = 'profile'
                                        st.rerun()

                                    # Editar — bloqueado si el target es admin y el viewer no es Kratos
                                    if target_is_admin and not viewer_is_kratos:
                                        col_btn2.markdown("🔒 Protegido")
                                    else:
                                        if col_btn2.button("✏️ Editar", key=f"edit_{user['username']}", help="Editar usuario"):
                                            st.session_state.admin_selected_user = dict(user)
                                            st.session_state.admin_mode = 'edit_user'
                                            st.rerun()

                                    # Eliminar — bloqueado para Kratos y para cualquier admin si viewer no es Kratos
                                    if is_kratos:
                                        col_btn3.markdown("🔒 Protegido")
                                    elif target_is_admin and not viewer_is_kratos:
                                        col_btn3.markdown("🔒 Protegido")
                                    elif not is_self:
                                        if col_btn3.button("🗑️ Eliminar", key=f"del_{user['username']}", help="Eliminar usuario"):
                                            st.session_state[f"pending_delete_{user['username']}"] = True

                                    # Confirmacion
                                    if st.session_state.get(f"pending_delete_{user['username']}", False):
                                        st.warning(f"¿Eliminar usuario **{user['username']}**? Esta accion lo desactivara del sistema.")
                                        col_yes, col_no = st.columns(2)
                                        if col_yes.button(f"✅ Si, eliminar {user['username']}", key=f"confirm_yes_{user['username']}", type='primary'):
                                            conn.execute("DELETE FROM users WHERE username = ?", (user['username'],))
                                            conn.commit()
                                            db_manager.log_activity(
                                                user_id=st.session_state.user['username'],
                                                action='user_deleted', entity_type='user',
                                                entity_id=user['username']
                                            )
                                            st.session_state.pop(f"pending_delete_{user['username']}", None)
                                            st.success(f"✅ Usuario {user['username']} eliminado correctamente")
                                            time.sleep(1)
                                            st.rerun()
                                        if col_no.button("❌ Cancelar", key=f"cancel_del_{user['username']}"):
                                            st.session_state.pop(f"pending_delete_{user['username']}", None)
                                            st.rerun()
        
        # ----------------------------------------------------------------------
        # TAB 2: GESTIÓN DE CURSOS
        # ----------------------------------------------------------------------
        if _tab_active('cursos'):
            st.markdown("### 📚 Gestión de Cursos")

            # Crear nuevo curso
            with st.expander("✨ Crear Nuevo Curso", expanded=False):

                # Inicializar session_state del formulario de curso
                _cc_defaults = {
                    'cc_name': '', 'cc_code': '', 'cc_teacher': None,
                    'cc_desc': '', 'cc_credits': 3, 'cc_semester': '',
                    'cc_status': 'active', 'cc_errors': {}, 'cc_form_ver': 0,
                }
                for k, v in _cc_defaults.items():
                    if k not in st.session_state:
                        st.session_state[k] = v

                cc_errors = st.session_state.cc_errors

                def _cc_err(field):
                    if field in cc_errors:
                        st.markdown(
                            f'<p style="color:#e05252;font-size:0.85em;margin:0 0 2px 0;">⚠️ {cc_errors[field]}</p>',
                            unsafe_allow_html=True
                        )

                # Profesores disponibles
                teachers_rows = conn.execute(
                    "SELECT username, full_name FROM users WHERE role = 'teacher' AND is_active = 1"
                ).fetchall()
                teachers = [dict(t) for t in teachers_rows]
                teacher_options = {f"👨‍🏫 {t['full_name']} ({t['username']})": t['username'] for t in teachers}
                teacher_options["❌ Sin asignar"] = None
                teacher_keys = list(teacher_options.keys())

                # Nombre del curso
                _cc_err('cc_name')
                cc_name = st.text_input(
                    "Nombre del Curso *",
                    value=st.session_state.cc_name,
                    placeholder="Programación Python Avanzada",
                    key=f"cc_name_inp_{st.session_state.cc_form_ver}"
                )

                # Código del curso (opcional)
                _cc_err('cc_code')
                cc_code = st.text_input(
                    "Código del Curso (opcional)",
                    value=st.session_state.cc_code,
                    placeholder="Se genera automáticamente si lo dejas vacío",
                    help="Si lo dejas vacío se genera como: primeras letras del nombre + número. Ej: 'Programación Avanzada' → PROG-001",
                    key=f"cc_code_inp_{st.session_state.cc_form_ver}"
                )

                # Profesor responsable
                teacher_idx = 0
                if st.session_state.cc_teacher:
                    for i, k in enumerate(teacher_keys):
                        if teacher_options[k] == st.session_state.cc_teacher:
                            teacher_idx = i
                            break
                cc_teacher = st.selectbox("Profesor Responsable", teacher_keys, index=teacher_idx,
                                          key=f"cc_teacher_sel_{st.session_state.cc_form_ver}")

                # Descripción *
                _cc_err('cc_desc')
                cc_desc = st.text_area(
                    "Descripción *",
                    value=st.session_state.cc_desc,
                    height=100,
                    placeholder="Descripción detallada del curso...",
                    key=f"cc_desc_inp_{st.session_state.cc_form_ver}"
                )

                # Horas / Semestre
                col_credits, col_semester = st.columns(2)
                _cc_err('cc_credits')
                cc_credits = col_credits.number_input(
                    "Horas semanales *",
                    min_value=1, max_value=40,
                    value=st.session_state.cc_credits,
                    key=f"cc_credits_inp_{st.session_state.cc_form_ver}"
                )
                _cc_err_semester = cc_errors.get('cc_semester')
                if _cc_err_semester:
                    col_semester.markdown(
                        f'<p style="color:#e05252;font-size:0.85em;margin:0 0 2px 0;">⚠️ {_cc_err_semester}</p>',
                        unsafe_allow_html=True
                    )
                cc_semester = col_semester.text_input(
                    "Semestre *",
                    value=st.session_state.cc_semester,
                    placeholder="2024-1",
                    key=f"cc_semester_inp_{st.session_state.cc_form_ver}"
                )

                # Estado
                status_opts = ["active", "archived", "draft"]
                status_idx = status_opts.index(st.session_state.cc_status) if st.session_state.cc_status in status_opts else 0
                cc_status = st.selectbox(
                    "Estado",
                    status_opts,
                    index=status_idx,
                    format_func=lambda x: {"active": "🟢 Activo", "archived": "📁 Archivado", "draft": "📝 Borrador"}[x]
                )

                # Imagen
                cc_image = st.file_uploader(
                    "Imagen de portada (opcional)",
                    type=['png', 'jpg', 'jpeg'],
                    key=f"cc_image_{st.session_state.cc_form_ver}"
                )

                if cc_errors.get('_general'):
                    st.error(f"❌ {cc_errors['_general']}")

                if st.button("🎯 Crear Curso", type="primary", use_container_width=True, key="cc_submit_btn"):
                    # Persistir valores
                    st.session_state.cc_name     = cc_name
                    st.session_state.cc_code     = cc_code
                    st.session_state.cc_teacher  = teacher_options[cc_teacher]
                    st.session_state.cc_desc     = cc_desc
                    st.session_state.cc_credits  = cc_credits
                    st.session_state.cc_semester = cc_semester
                    st.session_state.cc_status   = cc_status

                    # Validar
                    errs = {}
                    if not cc_name.strip():
                        errs['cc_name'] = "El nombre del curso es obligatorio"
                    if not cc_desc.strip():
                        errs['cc_desc'] = "La descripción es obligatoria"
                    if not cc_semester.strip():
                        errs['cc_semester'] = "El semestre es obligatorio"
                    if cc_credits < 1:
                        errs['cc_credits'] = "Las horas semanales deben ser al menos 1"

                    # Validar código personalizado único (si se ingresó)
                    if cc_code.strip():
                        dup = conn.execute("SELECT 1 FROM courses WHERE code=?", (cc_code.strip(),)).fetchone()
                        if dup:
                            errs['cc_code'] = f"El código '{cc_code.strip()}' ya existe"

                    st.session_state.cc_errors = errs

                    if errs:
                        st.rerun()
                    else:
                        try:
                            # Generar código automático si no se ingresó
                            final_code = cc_code.strip()
                            if not final_code:
                                words = [w for w in cc_name.upper().split() if len(w) > 2]
                                prefix = words[0][:4] if words else cc_name[:4].upper()
                                existing = conn.execute(
                                    "SELECT code FROM courses WHERE code LIKE ?", (f"{prefix}-%",)
                                ).fetchall()
                                next_num = len(existing) + 1
                                final_code = f"{prefix}-{next_num:03d}"
                                while conn.execute("SELECT 1 FROM courses WHERE code=?", (final_code,)).fetchone():
                                    next_num += 1
                                    final_code = f"{prefix}-{next_num:03d}"

                            image_blob = cc_image.getvalue() if cc_image else None
                            teacher_id = teacher_options[cc_teacher]

                            conn.execute("""
                                INSERT INTO courses (
                                    name, code, teacher_id, description, credits, semester,
                                    status, cover_image, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                cc_name.strip(), final_code, teacher_id, cc_desc,
                                cc_credits, cc_semester, cc_status, image_blob, datetime.now()
                            ))
                            conn.commit()

                            db_manager.log_activity(
                                user_id=st.session_state.user['username'],
                                action='course_created', entity_type='course', entity_id=final_code,
                                details={'name': cc_name, 'teacher': teacher_id}
                            )

                            # Limpiar formulario tras éxito
                            st.session_state.cc_name     = ''
                            st.session_state.cc_code     = ''
                            st.session_state.cc_teacher  = None
                            st.session_state.cc_desc     = ''
                            st.session_state.cc_credits  = 3
                            st.session_state.cc_semester = ''
                            st.session_state.cc_status   = 'active'
                            st.session_state.cc_errors   = {}
                            st.session_state.cc_form_ver = st.session_state.get('cc_form_ver', 0) + 1

                            st.success(f"✅ Curso '{cc_name.strip()}' creado con código **{final_code}**")
                            time.sleep(1)
                            st.rerun()

                        except Exception as e:
                            st.session_state.cc_errors = {'_general': str(e)}
                            st.rerun()

            st.divider()

            # Listar cursos
            st.markdown("### 📋 Lista de Cursos")

            # Filtros para cursos
            col_cfilter1, col_cfilter2 = st.columns(2)

            with col_cfilter1:
                course_status_filter = st.selectbox(
                    "Estado del curso",
                    ["Todos", "active", "archived", "draft"],
                    format_func=lambda x: {
                        "Todos": "📚 Todos",
                        "active": "🟢 Activos",
                        "archived": "📁 Archivados",
                        "draft": "📝 Borradores"
                    }[x]
                )
            
            with col_cfilter2:
                course_search = st.text_input("Buscar curso...", placeholder="Nombre, código o profesor")
            
            # Obtener cursos
            course_query = """
                SELECT c.*, u.full_name as teacher_name, 
                       COUNT(e.student_id) as student_count
                FROM courses c
                LEFT JOIN users u ON c.teacher_id = u.username
                LEFT JOIN enrollments e ON c.id = e.course_id
            """
            course_params = []
            
            where_clauses = []
            if course_status_filter != "Todos":
                where_clauses.append("c.status = ?")
                course_params.append(course_status_filter)
            
            if course_search:
                where_clauses.append("(c.name LIKE ? OR c.code LIKE ? OR u.full_name LIKE ?)")
                search_pattern = f"%{course_search}%"
                course_params.extend([search_pattern, search_pattern, search_pattern])
            
            if where_clauses:
                course_query += " WHERE " + " AND ".join(where_clauses)
            
            course_query += " GROUP BY c.id ORDER BY c.created_at DESC"
            
            courses_rows = conn.execute(course_query, course_params).fetchall()
            courses = [dict(c) for c in courses_rows]
            
            if not courses:
                st.info("📭 No se encontraron cursos")
            else:
                # Mostrar cursos en grid
                cols = st.columns(3)
                for i, course in enumerate(courses):
                    with cols[i % 3]:
                        with st.container(border=True):
                            # Imagen del curso
                            if course['cover_image']:
                                img_src = f"data:image/png;base64,{base64.b64encode(course['cover_image']).decode()}"
                            else:
                                img_src = "https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=400&h=200&fit=crop"
                            
                            st.markdown(f"""
                            <div style="border-radius: 8px; overflow: hidden; margin-bottom: 10px;">
                                <img src="{img_src}" style="width: 100%; height: 120px; object-fit: cover;">
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Información
                            status_icon = {
                                "active": "🟢",
                                "archived": "📁",
                                "draft": "📝"
                            }.get(course['status'], "❓")
                            
                            st.markdown(f"**{course['name']}**")
                            st.caption(f"{status_icon} {course['code']} | 👥 {course['student_count']} estudiantes")
                            
                            if course['teacher_name']:
                                st.caption(f"👨‍🏫 {course['teacher_name']}")
                            else:
                                st.caption("⚠️ Sin profesor asignado")
                            
                            # Botones de acción
                            col_btn1, col_btn2 = st.columns(2)
                            
                            if col_btn1.button("📝 Gestionar", key=f"manage_c_{course['id']}", width='stretch'):
                                st.session_state.admin_edit_course = dict(course)
                                st.session_state.admin_mode = 'edit_course'
                                st.rerun()
                            
                            if col_btn2.button("👥 Matricular", key=f"enroll_c_{course['id']}", width='stretch'):
                                st.session_state.admin_enroll_course = dict(course)
                                st.session_state.admin_mode = 'bulk_enroll'
                                st.rerun()
        
        # ----------------------------------------------------------------------
        # TAB 3: GESTIÓN DE NOTIFICACIONES
        # ----------------------------------------------------------------------
        if _tab_active('notificaciones'):
            render_notification_management(conn)
        
        # ----------------------------------------------------------------------
        # TAB 4: ESTADÍSTICAS
        # ----------------------------------------------------------------------
        if _tab_active('estadisticas'):
            st.markdown("### 📊 Estadísticas del Sistema")
            
            # Métricas principales
            col_metrics = st.columns(4)
            
            with col_metrics[0]:
                daily_active = conn.execute("""
                    SELECT COUNT(DISTINCT user_id) FROM activity_logs 
                    WHERE DATE(created_at) = DATE('now')
                """).fetchone()[0]
                st.metric("👥 Activos Hoy", daily_active)
            
            with col_metrics[1]:
                monthly_submissions = conn.execute("""
                    SELECT COUNT(*) FROM submissions 
                    WHERE strftime('%Y-%m', submission_date) = strftime('%Y-%m', 'now')
                """).fetchone()[0]
                st.metric("📝 Entregas Mes", monthly_submissions)
            
            with col_metrics[2]:
                avg_grades = conn.execute("""
                    SELECT AVG(final_grade) FROM submissions 
                    WHERE final_grade IS NOT NULL
                """).fetchone()[0]
                st.metric("📈 Prom. Calificación", f"{avg_grades:.1f}" if avg_grades else "0")
            
            with col_metrics[3]:
                storage_used = conn.execute("""
                    SELECT SUM(LENGTH(content_blob)) + SUM(LENGTH(avatar)) 
                    FROM course_materials, users
                """).fetchone()[0] or 0
                storage_mb = storage_used / (1024 * 1024)
                st.metric("💾 Almacenamiento", f"{storage_mb:.1f} MB")
            
            st.divider()
            
            # Gráficos y datos
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("#### 👥 Distribución por Rol")
                role_dist_rows = conn.execute("""
                    SELECT role, COUNT(*) as count FROM users 
                    WHERE is_active = 1 
                    GROUP BY role
                """).fetchall()
                role_dist = [dict(r) for r in role_dist_rows]
                
                if role_dist:
                    role_df = pd.DataFrame(role_dist)
                    st.dataframe(role_df, width='stretch', hide_index=True)
                else:
                    st.info("Sin datos de usuarios")
            
            with col_chart2:
                st.markdown("#### 📚 Cursos por Estado")
                course_stats_rows = conn.execute("""
                    SELECT status, COUNT(*) as count FROM courses 
                    GROUP BY status
                """).fetchall()
                course_stats = [dict(r) for r in course_stats_rows]
                
                if course_stats:
                    status_df = pd.DataFrame(course_stats)
                    st.dataframe(status_df, width='stretch', hide_index=True)
            
            # Actividad reciente
            st.markdown("#### 📈 Actividad Reciente")

            # Filtros de fecha
            col_desde, col_hasta = st.columns(2)
            with col_desde:
                fecha_desde = st.date_input(
                    "Desde",
                    value=date.today() - timedelta(days=7),
                    min_value=date(2020, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY",
                    key="act_fecha_desde"
                )
            with col_hasta:
                fecha_hasta = st.date_input(
                    "Hasta",
                    value=date.today(),
                    min_value=date(2020, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY",
                    key="act_fecha_hasta"
                )

            recent_activity_rows = conn.execute("""
                SELECT action, entity_type, user_id, created_at, details
                FROM activity_logs
                WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (str(fecha_desde), str(fecha_hasta))).fetchall()
            recent_activity = [dict(r) for r in recent_activity_rows]

            st.caption(f"Mostrando {len(recent_activity)} registros entre **{fecha_desde.strftime('%d/%m/%Y')}** y **{fecha_hasta.strftime('%d/%m/%Y')}**")

            if recent_activity:
                for activity in recent_activity:
                    try:
                        details = json.loads(activity['details']) if activity['details'] else {}
                    except:
                        details = {}

                    with st.container(border=True):
                        col_a1, col_a2 = st.columns([3, 1])
                        col_a1.markdown(f"**{activity['action'].replace('_', ' ').title()}**")
                        col_a1.caption(f"👤 {activity['user_id'] or 'Sistema'} | 📁 {activity['entity_type'] or 'N/A'}")

                        if details:
                            with col_a1.expander("Detalles"):
                                st.json(details, expanded=False)

                        col_a2.caption(
                            datetime.strptime(activity['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                            if activity['created_at'] else '—'
                        )
            else:
                st.info("No hay actividad registrada en el rango de fechas seleccionado")


        # ----------------------------------------------------------------------
        # TAB 5: CONFIGURACIÓN DEL SISTEMA
        # ----------------------------------------------------------------------
        if _tab_active('configuracion'):
            st.markdown("### ⚙️ Configuración del Sistema")
            
            # Obtener configuración actual
            settings = conn.execute("SELECT * FROM system_settings").fetchall()
            settings_dict = {s['key']: s['value'] for s in settings}
            
            # ========== SECCIÓN 1: ARCHIVOS (FUERA DEL FORM) ==========
            st.markdown("#### 🎨 Personalización del Login")
            st.caption("Configura el logo y el fondo que aparecerán en la pantalla de inicio de sesión")
            
            # Variables para almacenar los valores
            logo_url_final = settings_dict.get('logo_url', '')
            background_url_final = settings_dict.get('login_background_url', '')
            
            # ========== LOGO ==========
            st.markdown("##### 🖼️ Logo del Sistema")
            
            # Mostrar logo actual si existe
            current_logo = settings_dict.get('logo_url', '')
            if current_logo:
                with st.expander("👁️ Ver logo actual", expanded=False):
                    col_preview1, col_preview2, col_preview3 = st.columns([1, 2, 1])
                    with col_preview2:
                        try:
                            st.image(current_logo, caption="Logo actual en uso", width=150)
                        except:
                            st.warning("⚠️ No se pudo cargar la imagen del logo actual")
            
            logo_method = st.radio(
                "Método de configuración del logo:",
                ["URL de imagen", "Subir archivo", "Sin logo (usar icono predeterminado)"],
                help="Elige cómo quieres configurar el logo de la plataforma",
                key="logo_method"
            )
            
            if logo_method == "URL de imagen":
                logo_url_input = st.text_input(
                    "URL del Logo",
                    value=current_logo if current_logo and not current_logo.startswith('data:image') else '',
                    placeholder="https://ejemplo.com/logo.png",
                    help="Ingresa la URL completa de tu logo (debe ser accesible públicamente)",
                    key="logo_url_input"
                )
                if logo_url_input:
                    logo_url_final = logo_url_input
                    st.info("💡 **Consejo:** Asegúrate de que la URL sea accesible públicamente y termine en .png, .jpg o .svg")
                    
            elif logo_method == "Subir archivo":
                st.info("📏 **Tamaño recomendado:** 150x150px | **Formatos:** PNG (con transparencia), JPG, SVG")
                uploaded_logo = st.file_uploader(
                    "Selecciona tu logo",
                    type=['png', 'jpg', 'jpeg', 'svg'],
                    help="Arrastra tu archivo aquí o haz clic para seleccionar",
                    key="logo_uploader"
                )
                if uploaded_logo:
                    # Convertir a base64 para almacenar
                    logo_bytes = uploaded_logo.getvalue()
                    logo_b64 = base64.b64encode(logo_bytes).decode()
                    logo_url_final = f"data:image/{uploaded_logo.type.split('/')[-1]};base64,{logo_b64}"
                    
                    # Vista previa
                    st.success("✅ Archivo cargado correctamente")
                    with st.expander("👁️ Vista previa del nuevo logo", expanded=True):
                        col_prev1, col_prev2, col_prev3 = st.columns([1, 2, 1])
                        with col_prev2:
                            st.image(uploaded_logo, caption="Así se verá tu logo", width=150)
                elif current_logo and current_logo.startswith('data:image'):
                    # Mantener el logo actual si ya es un archivo subido
                    logo_url_final = current_logo
                    st.info("ℹ️ Se mantendrá el logo actual hasta que subas uno nuevo")
            else:
                # Sin logo
                logo_url_final = ""
                st.info("🎓 Se usará el icono predeterminado en la pantalla de login")
            
            st.divider()
            
            # ========== FONDO DEL LOGIN ==========
            st.markdown("##### 🌄 Fondo del Login")
            
            # Mostrar fondo actual si existe
            current_background = settings_dict.get('login_background_url', '')
            if current_background:
                with st.expander("👁️ Ver fondo actual", expanded=False):
                    try:
                        st.image(current_background, caption="Fondo actual en uso")
                    except:
                        st.warning("⚠️ No se pudo cargar la imagen del fondo actual")
            
            background_method = st.radio(
                "Método de configuración del fondo:",
                ["URL de imagen", "Subir archivo", "Gradiente azul predeterminado"],
                help="Elige cómo quieres configurar el fondo del login",
                key="background_method"
            )
            
            if background_method == "URL de imagen":
                background_url_input = st.text_input(
                    "URL del Fondo",
                    value=current_background if current_background and not current_background.startswith('data:image') else '',
                    placeholder="https://ejemplo.com/fondo.jpg",
                    help="Ingresa la URL completa de tu imagen de fondo",
                    key="background_url_input"
                )
                if background_url_input:
                    background_url_final = background_url_input
                    st.info("💡 **Consejo:** Usa imágenes de alta resolución (1920x1080 o superior) para mejor calidad")
                    
            elif background_method == "Subir archivo":
                st.info("📏 **Tamaño recomendado:** 1920x1080px o superior | **Formatos:** JPG, PNG")
                uploaded_background = st.file_uploader(
                    "Selecciona tu imagen de fondo",
                    type=['png', 'jpg', 'jpeg'],
                    help="Arrastra tu archivo aquí o haz clic para seleccionar",
                    key="background_uploader"
                )
                if uploaded_background:
                    # Convertir a base64 para almacenar
                    bg_bytes = uploaded_background.getvalue()
                    bg_b64 = base64.b64encode(bg_bytes).decode()
                    background_url_final = f"data:image/{uploaded_background.type.split('/')[-1]};base64,{bg_b64}"
                    
                    # Vista previa
                    st.success("✅ Archivo cargado correctamente")
                    with st.expander("👁️ Vista previa del nuevo fondo", expanded=True):
                        st.image(uploaded_background, caption="Así se verá tu fondo")
                elif current_background and current_background.startswith('data:image'):
                    # Mantener el fondo actual si ya es un archivo subido
                    background_url_final = current_background
                    st.info("ℹ️ Se mantendrá el fondo actual hasta que subas uno nuevo")
            else:
                # Gradiente predeterminado
                background_url_final = ""
                st.info("🎨 Se usará el gradiente azul predeterminado (como en la imagen de referencia)")
            
            st.divider()
            
            # ========== SECCIÓN 2: RESTO DE CONFIGURACIÓN (DENTRO DEL FORM) ==========
            with st.form("system_settings_form"):
                col_s1, col_s2 = st.columns(2)
                
                with col_s1:
                    site_name = st.text_input("Nombre del Sitio", 
                                            value=settings_dict.get('site_name', 'Plataforma Educativa IA'))
                    
                    default_theme = st.selectbox(
                        "Tema por Defecto",
                        ["dark", "light"],
                        format_func=lambda x: "🌙 Oscuro" if x == "dark" else "☀️ Claro",
                        index=0 if settings_dict.get('default_theme', 'dark') == 'dark' else 1
                    )
                    
                    allow_registrations = st.checkbox(
                        "Permitir Nuevos Registros",
                        value=settings_dict.get('allow_registrations', '1') == '1'
                    )
                    
                    maintenance_mode = st.checkbox(
                        "Modo Mantenimiento",
                        value=settings_dict.get('maintenance_mode', '0') == '1',
                        help="Bloquea el acceso a usuarios no administradores"
                    )
                
                with col_s2:
                    max_file_size = st.number_input(
                        "Tamaño Máximo de Archivos (MB)",
                        min_value=1,
                        max_value=100,
                        value=int(settings_dict.get('max_file_size_mb', 10))
                    )
                    
                    session_timeout = st.number_input(
                        "Timeout de Sesión (minutos)",
                        min_value=5,
                        max_value=480,
                        value=int(settings_dict.get('session_timeout_minutes', 120))
                    )
                    
                    ai_enabled = st.checkbox(
                        "Habilitar IA",
                        value=settings_dict.get('ai_enabled', '1') == '1',
                        help="Activar funciones de inteligencia artificial"
                    )
                    
                    backup_enabled = st.checkbox(
                        "Backups Automáticos",
                        value=settings_dict.get('backup_enabled', '1') == '1'
                    )
                
                # Configuración adicional
                site_description = st.text_area(
                    "Descripción del Sitio",
                    value=settings_dict.get('site_description', ''),
                    height=80
                )
                
                footer_text = st.text_input(
                    "Texto del Footer",
                    value=settings_dict.get('footer_text', '© 2026 Plataforma Educativa IA')
                )
                
                st.markdown("---")
                st.markdown("#### 🏋️ Gimnasio de Código")
                
                gym_block_paste = st.checkbox(
                    "Bloquear pegar código (Ctrl+V / clic derecho)",
                    value=settings_dict.get('gym_block_paste', '1') == '1',
                    help="Cuando está activo, los estudiantes no pueden pegar código en el editor del Gimnasio. Deben escribirlo a mano."
                )
                
                st.markdown("---")
                st.markdown("#### 🤖 Configuración de IA")
                
                # Obtener API key actual (primero de la BD, luego de secrets)
                current_api_key = settings_dict.get('gemini_api_key', '')
                if not current_api_key:
                    try:
                        current_api_key = st.secrets.get("GEMINI_API_KEY", "")
                    except:
                        current_api_key = ""
                
                # Mostrar solo los últimos 4 caracteres si existe
                display_key = ""
                if current_api_key:
                    display_key = "•" * (len(current_api_key) - 4) + current_api_key[-4:]
                
                col_key1, col_key2 = st.columns([3, 1])
                
                with col_key1:
                    gemini_api_key = st.text_input(
                        "API Key de Gemini",
                        value=current_api_key,
                        type="password",
                        help="Ingresa tu API key de Google Gemini para habilitar funciones de IA",
                        placeholder="AIzaSy..."
                    )
                
                with col_key2:
                    if current_api_key:
                        st.metric("Estado", "✅ Configurada")
                        st.caption(f"Key: {display_key}")
                    else:
                        st.metric("Estado", "❌ No configurada")
                
                st.caption("💡 Obtén tu API key gratis en: https://makersuite.google.com/app/apikey")
                
                if st.form_submit_button("💾 Guardar Configuración", type="primary"):
                    # Actualizar configuración (usando variables de fuera del form)
                    updates = [
                        ('site_name', site_name),
                        ('site_description', site_description),
                        ('default_theme', default_theme),
                        ('allow_registrations', '1' if allow_registrations else '0'),
                        ('maintenance_mode', '1' if maintenance_mode else '0'),
                        ('max_file_size_mb', str(max_file_size)),
                        ('session_timeout_minutes', str(session_timeout)),
                        ('ai_enabled', '1' if ai_enabled else '0'),
                        ('backup_enabled', '1' if backup_enabled else '0'),
                        ('logo_url', logo_url_final),
                        ('login_background_url', background_url_final),
                        ('footer_text', footer_text),
                        ('gemini_api_key', gemini_api_key),
                        ('gym_block_paste', '1' if gym_block_paste else '0'),
                    ]
                    
                    for key, value in updates:
                        conn.execute("""
                            INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                            VALUES (?, ?, ?)
                        """, (key, value, datetime.now()))
                    
                    conn.commit()
                    
                    # Actualizar variable de sesión
                    st.session_state.ai_available = ai_enabled
                    
                    # Actualizar archivo secrets.toml si cambió la API key
                    if gemini_api_key and gemini_api_key != current_api_key:
                        try:
                            import os
                            secrets_path = ".streamlit/secrets.toml"
                            os.makedirs(".streamlit", exist_ok=True)
                            
                            with open(secrets_path, 'w') as f:
                                f.write(f'# API Key de Gemini\n')
                                f.write(f'GEMINI_API_KEY = "{gemini_api_key}"\n')
                            
                            st.success("✅ Configuración guardada exitosamente")
                            st.info("🔄 Reinicia la aplicación para que los cambios de la API key surtan efecto")
                        except Exception as e:
                            st.warning(f"⚠️ Configuración guardada pero no se pudo actualizar secrets.toml: {e}")
                    else:
                        st.success("✅ Configuración guardada exitosamente")
                    
                    time.sleep(1)
                    st.rerun()
        
        # ----------------------------------------------------------------------
        # TAB 6: AUDITORÍA
        # ----------------------------------------------------------------------
        if _tab_active('seguridad'):
            st.markdown("### 🔍 Auditoría")

            # ── 1. Auditoría de archivos ──────────────────────────────────────
            st.markdown("#### 📁 Auditoría de Archivos")

            file_audit = conn.execute("""
                SELECT 
                    COUNT(*) as total_files,
                    SUM(LENGTH(content_blob)) as total_size,
                    AVG(LENGTH(content_blob)) as avg_size
                FROM course_materials 
                WHERE content_blob IS NOT NULL
            """).fetchone()

            if file_audit and file_audit['total_files'] > 0:
                total_mb = file_audit['total_size'] / (1024 * 1024)
                avg_kb   = file_audit['avg_size'] / 1024

                col_audit1, col_audit2, col_audit3 = st.columns(3)
                col_audit1.metric("📄 Archivos", file_audit['total_files'])
                col_audit2.metric("💾 Tamaño Total", f"{total_mb:.1f} MB")
                col_audit3.metric("📊 Promedio",     f"{avg_kb:.1f} KB")

                large_files_rows = conn.execute("""
                    SELECT title, LENGTH(content_blob) as size 
                    FROM course_materials 
                    WHERE content_blob IS NOT NULL 
                    ORDER BY size DESC 
                    LIMIT 5
                """).fetchall()
                large_files = [dict(f) for f in large_files_rows]

                if large_files:
                    with st.expander("📈 Archivos más grandes"):
                        for file in large_files:
                            size_mb = file['size'] / (1024 * 1024)
                            st.write(f"{file['title']}: {size_mb:.2f} MB")
            else:
                st.info("No hay archivos subidos")

            st.divider()

            # ── 2. Mantenimiento de logs ──────────────────────────────────────
            st.markdown("#### 🗑️ Mantenimiento de Logs")

            col_clean1, col_clean2 = st.columns(2)
            with col_clean1:
                days_keep = st.number_input("Conservar logs (días)", 7, 365, 30)
            with col_clean2:
                if st.button("🧹 Limpiar Logs Antiguos", type="secondary"):
                    cutoff_date = datetime.now() - timedelta(days=days_keep)
                    deleted = conn.execute("""
                        DELETE FROM activity_logs WHERE created_at < ?
                    """, (cutoff_date,)).rowcount
                    conn.commit()
                    st.success(f"✅ {deleted} registros eliminados")

            st.divider()

            # ── 3. Logs de actividad ──────────────────────────────────────────
            st.markdown("#### 📋 Registro de Actividad")

            security_logs_rows = conn.execute("""
                SELECT * FROM activity_logs 
                WHERE action IN ('login_failed', 'login_success', 'logout', 
                               'password_changed', 'user_created', 'user_deactivated')
                ORDER BY created_at DESC 
                LIMIT 20
            """).fetchall()
            security_logs = [dict(r) for r in security_logs_rows]

            if security_logs:
                for log in security_logs:
                    icon = {
                        'login_failed':     '❌',
                        'login_success':    '✅',
                        'logout':           '🚪',
                        'password_changed': '🔑',
                        'user_created':     '👤',
                        'user_deactivated': '🗑️'
                    }.get(log['action'], '📌')

                    with st.container(border=True):
                        col_l1, col_l2, col_l3 = st.columns([1, 3, 1])
                        col_l1.markdown(f"**{icon}**")
                        col_l2.markdown(f"**{log['action'].replace('_', ' ').title()}**")
                        col_l2.caption(f"👤 {log['user_id'] or 'Sistema'} | 🌐 {log['ip_address'] or 'N/A'}")
                        try:
                            t = datetime.strptime(log['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                        except Exception:
                            t = log['created_at'] or ''
                        col_l3.caption(t)
            else:
                st.info("No hay registros de actividad")

        # ----------------------------------------------------------------------
        # TAB 7: MANTENIMIENTO
        # ----------------------------------------------------------------------
        if _tab_active('mantenimiento'):
            st.markdown("### 🔧 Herramientas de Mantenimiento")
            
            from pathlib import Path
            import shutil
            
            BACKUP_DIR = Path('backups')
            BACKUP_DIR.mkdir(exist_ok=True)
            DB_FILE = Path('learning_platform.db')
            
            # -------------------------------------------------------------------
            # CONFIGURACIÓN AUTOMÁTICA
            # -------------------------------------------------------------------
            st.markdown("#### ⚙️ Configuración Automática")
            
            # Leer config guardada
            auto_backup_freq = conn.execute(
                "SELECT value FROM system_settings WHERE key='auto_backup_frequency'"
            ).fetchone()
            auto_optimize_freq = conn.execute(
                "SELECT value FROM system_settings WHERE key='auto_optimize_frequency'"
            ).fetchone()
            
            freq_options = ["Desactivado", "Cada inicio de sesión", "Diario", "Semanal", "Mensual"]
            
            col_cfg1, col_cfg2 = st.columns(2)
            
            with col_cfg1:
                st.markdown("**💾 Backup automático:**")
                cur_backup = auto_backup_freq['value'] if auto_backup_freq else "Semanal"
                sel_backup = st.selectbox("Frecuencia de backup:", freq_options,
                                          index=freq_options.index(cur_backup) if cur_backup in freq_options else 3,
                                          key="auto_backup_sel")
            
            with col_cfg2:
                st.markdown("**🔧 Optimización automática:**")
                cur_optimize = auto_optimize_freq['value'] if auto_optimize_freq else "Semanal"
                sel_optimize = st.selectbox("Frecuencia de optimización:", freq_options,
                                            index=freq_options.index(cur_optimize) if cur_optimize in freq_options else 3,
                                            key="auto_optimize_sel")
            
            if st.button("� Guardar Configuración", type="primary"):
                conn.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
                    VALUES ('auto_backup_frequency', ?, 'Frecuencia de backup automático', CURRENT_TIMESTAMP)
                """, (sel_backup,))
                conn.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
                    VALUES ('auto_optimize_frequency', ?, 'Frecuencia de optimización automática', CURRENT_TIMESTAMP)
                """, (sel_optimize,))
                conn.commit()
                st.success("✅ Configuración guardada")
            
            # Ejecutar automático si aplica
            if sel_backup != "Desactivado":
                last_backup_row = conn.execute(
                    "SELECT value FROM system_settings WHERE key='last_auto_backup'"
                ).fetchone()
                last_backup = last_backup_row['value'] if last_backup_row else None
                
                should_backup = False
                now = datetime.now()
                
                if not last_backup:
                    should_backup = True
                else:
                    try:
                        last_dt = datetime.fromisoformat(last_backup)
                        diff = now - last_dt
                        if sel_backup == "Cada inicio de sesión":
                            should_backup = True
                        elif sel_backup == "Diario" and diff.days >= 1:
                            should_backup = True
                        elif sel_backup == "Semanal" and diff.days >= 7:
                            should_backup = True
                        elif sel_backup == "Mensual" and diff.days >= 30:
                            should_backup = True
                    except Exception:
                        should_backup = True
                
                if should_backup and sel_backup != "Cada inicio de sesión":
                    try:
                        ts = now.strftime("%Y%m%d_%H%M%S")
                        dest = BACKUP_DIR / f"learning_platform_backup_{ts}.db"
                        shutil.copy2(DB_FILE, dest)
                        conn.execute("""
                            INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
                            VALUES ('last_auto_backup', ?, 'Último backup automático', CURRENT_TIMESTAMP)
                        """, (now.isoformat(),))
                        conn.commit()
                    except Exception:
                        pass
            
            st.divider()
            
            # -------------------------------------------------------------------
            # BACKUP MANUAL
            # -------------------------------------------------------------------
            st.markdown("#### 💾 Backup Manual")
            col_b1, col_b2 = st.columns([3, 1])
            with col_b1:
                st.info("Crea una copia de seguridad inmediata de la base de datos.")
            with col_b2:
                if st.button("📥 Crear Backup Ahora", type="primary", use_container_width=True):
                    try:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest = BACKUP_DIR / f"learning_platform_backup_{ts}.db"
                        shutil.copy2(DB_FILE, dest)
                        conn.execute("""
                            INSERT OR REPLACE INTO system_settings (key, value, description, updated_at)
                            VALUES ('last_auto_backup', ?, 'Último backup automático', CURRENT_TIMESTAMP)
                        """, (datetime.now().isoformat(),))
                        conn.commit()
                        st.success(f"✅ Backup creado: {dest.name}")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            
            st.divider()
            
            # -------------------------------------------------------------------
            # RESTAURAR BACKUP
            # -------------------------------------------------------------------
            st.markdown("#### � Restaurar Base de Datos")
            
            backups = sorted(BACKUP_DIR.glob("*.db"), reverse=True)
            
            if not backups:
                st.info("📭 No hay backups disponibles. Crea uno primero.")
            else:
                st.warning("⚠️ Restaurar reemplazará todos los datos actuales con los del backup seleccionado.")
                
                backup_names = [f.name for f in backups]
                selected_backup = st.selectbox(
                    "Selecciona el backup a restaurar:",
                    backup_names,
                    format_func=lambda x: f"📦 {x}"
                )
                
                # Mostrar fecha legible del backup seleccionado
                try:
                    parts = selected_backup.replace('learning_platform_backup_', '').replace('.db', '')
                    dt = datetime.strptime(parts, "%Y%m%d_%H%M%S")
                    st.caption(f"📅 Fecha del backup: {dt.strftime('%d/%m/%Y a las %H:%M:%S')}")
                except Exception:
                    pass
                
                col_r1, col_r2 = st.columns([3, 1])
                with col_r1:
                    confirm_restore = st.checkbox("✅ Confirmo que quiero restaurar este backup y entiendo que se perderán los datos actuales")
                with col_r2:
                    if st.button("� Restaurar Ahora", type="primary", use_container_width=True,
                                 disabled=not confirm_restore):
                        try:
                            # Crear backup de seguridad antes de restaurar
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            safety = BACKUP_DIR / f"pre_restore_backup_{ts}.db"
                            shutil.copy2(DB_FILE, safety)
                            
                            # Copiar el backup seleccionado
                            src = BACKUP_DIR / selected_backup
                            shutil.copy2(src, DB_FILE)
                            
                            st.success(f"✅ Base de datos restaurada desde '{selected_backup}'. Se creó backup de seguridad: '{safety.name}'. Reinicia la aplicación.")
                        except Exception as e:
                            st.error(f"❌ Error al restaurar: {e}")
            
            st.divider()
            
            # -------------------------------------------------------------------
            # OPTIMIZACIÓN MANUAL
            # -------------------------------------------------------------------
            st.markdown("#### 🛠️ Optimización Manual")
            col_o1, col_o2 = st.columns([3, 1])
            with col_o1:
                st.info("Compacta y optimiza la base de datos. Mejora el rendimiento si la app se siente lenta.")
            with col_o2:
                if st.button("🔧 Optimizar DB", type="secondary", use_container_width=True):
                    try:
                        conn.execute("VACUUM")
                        conn.execute("ANALYZE")
                        conn.commit()
                        st.success("✅ Base de datos optimizada")
                        db_manager.log_activity(
                            user_id=st.session_state.user['username'],
                            action='database_optimized', entity_type='system'
                        )
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
            
            st.divider()
            
            # -------------------------------------------------------------------
            # ZONA DE PELIGRO
            # -------------------------------------------------------------------
            st.markdown("#### ⚠️ Zona de Peligro")
            with st.expander("🔴 Acciones Irreversibles"):
                st.error("Estas acciones borran datos permanentemente y NO se pueden deshacer.")
                
                col_reset1, col_reset2 = st.columns(2)
                
                with col_reset1:
                    if st.button("🗑️ Borrar Logs de Actividad", type="secondary", use_container_width=True):
                        if st.checkbox("Confirmar borrado de todos los logs", key="confirm_logs"):
                            deleted = conn.execute("DELETE FROM activity_logs").rowcount
                            conn.commit()
                            st.success(f"✅ {deleted} registros eliminados")
                            time.sleep(1)
                            st.rerun()
                
                with col_reset2:
                    if st.button("📝 Reset Contraseñas", type="secondary", use_container_width=True):
                        if st.checkbox("Resetear todas las contraseñas a 'password123'", key="confirm_reset_pwd"):
                            new_hash = hash_password('password123')
                            updated = conn.execute(
                                "UPDATE users SET password_hash = ?, force_reset = 1", (new_hash,)
                            ).rowcount
                            conn.commit()
                            st.success(f"✅ {updated} contraseñas reseteadas")
                            time.sleep(1)
                            st.rerun()
    # ==============================================================================
    # VISTA 2: EDITAR USUARIO
    # ==============================================================================
    elif st.session_state.admin_mode == 'edit_user' and st.session_state.admin_selected_user:
        user = st.session_state.admin_selected_user
        
        st.title(f"✏️ Editando Usuario: {user['full_name']}")
        
        if st.button("← Volver al Panel"):
            st.session_state.admin_mode = 'dashboard'
            st.session_state.admin_selected_user = None
            st.rerun()
        
        # Obtener datos completos del usuario y convertir a dict
        user_data_row = conn.execute(
            "SELECT * FROM users WHERE username = ?", 
            (user['username'],)
        ).fetchone()
        
        if not user_data_row:
            st.error("Usuario no encontrado")
            return
            
        user_data = dict(user_data_row)
        
        # Tabs de edición
        tab_info, tab_security, tab_courses, tab_activity = st.tabs([
            "📝 Información",
            "🔐 Seguridad", 
            "📚 Cursos",
            "📈 Actividad"
        ])
        
        with tab_info:
            with st.form("edit_user_info_form"):
                col_fname, col_lname = st.columns(2)
                new_fname = col_fname.text_input("Nombres", value=user_data.get('first_name', ''))
                new_lname = col_lname.text_input("Apellidos", value=user_data.get('last_name', ''))
                
                new_email = st.text_input("Email", value=user_data.get('email', ''))
                new_title = st.text_input("Título/Especialidad", value=user_data.get('title', ''))
                new_bio = st.text_area("Biografía", value=user_data.get('bio', ''), height=100)
                
                col_role, col_status = st.columns(2)
                new_role = col_role.selectbox(
                    "Rol",
                    ["student", "teacher", "admin"],
                    index=["student", "teacher", "admin"].index(user_data['role']),
                    format_func=lambda x: {
                        "student": "🎓 Estudiante",
                        "teacher": "👨‍🏫 Docente", 
                        "admin": "🛡️ Administrador"
                    }[x]
                )
                
                new_active = col_status.checkbox("Usuario Activo", value=bool(user_data.get('is_active', 1)))
                
                new_subjects = st.text_input("Materias de interés", value=user_data.get('subjects', ''))
                new_social = st.text_input("Enlaces sociales", value=user_data.get('social_links', ''))
                
                # Avatar
                current_avatar = user_data.get('avatar')
                new_avatar = st.file_uploader("Cambiar avatar", type=['png', 'jpg', 'jpeg'])
                
                if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                    # Actualizar usuario
                    avatar_blob = new_avatar.getvalue() if new_avatar else current_avatar
                    full_name = f"{new_fname} {new_lname}"
                    
                    conn.execute("""
                        UPDATE users SET
                            first_name = ?, last_name = ?, full_name = ?,
                            email = ?, title = ?, bio = ?,
                            role = ?, is_active = ?, subjects = ?,
                            social_links = ?, avatar = ?, updated_at = ?
                        WHERE username = ?
                    """, (
                        new_fname, new_lname, full_name,
                        new_email or None, new_title or None, new_bio or None,
                        new_role, 1 if new_active else 0,
                        new_subjects or None, new_social or None,
                        avatar_blob, datetime.now(),
                        user_data['username']
                    ))
                    
                    conn.commit()
                    
                    # Registrar actividad
                    db_manager.log_activity(
                        user_id=st.session_state.user['username'],
                        action='user_updated',
                        entity_type='user',
                        entity_id=user_data['username'],
                        details={'updated_by': st.session_state.user['username']}
                    )
                    
                    st.success("✅ Usuario actualizado exitosamente")
                    
                    # Actualizar sesión si es el usuario actual
                    if user_data['username'] == st.session_state.user['username']:
                        st.session_state.user.update({
                            'first_name': new_fname,
                            'last_name': new_lname,
                            'full_name': full_name,
                            'role': new_role,
                            'avatar': avatar_blob
                        })
                    
                    time.sleep(1)
                    st.rerun()
        
        with tab_security:
            st.markdown("#### 🔐 Configuración de Seguridad")
            
            # Cambiar contraseña
            with st.form("change_password_admin_form"):
                st.markdown("##### Cambiar Contraseña")
                
                new_password = st.text_input("Nueva Contraseña", type="password")
                confirm_password = st.text_input("Confirmar Contraseña", type="password")
                
                if st.form_submit_button("🔄 Cambiar Contraseña", type="primary"):
                    if new_password and confirm_password:
                        if new_password == confirm_password:
                            # Validar contraseña
                            valid, msg = security.validate_password(new_password)
                            if not valid:
                                st.error(f"❌ {msg}")
                            else:
                                # Actualizar contraseña
                                password_hash = hash_password(new_password)
                                
                                conn.execute("""
                                    UPDATE users 
                                    SET password_hash = ?, force_reset = 1, updated_at = ?
                                    WHERE username = ?
                                """, (password_hash, datetime.now(), user_data['username']))
                                
                                conn.commit()
                                
                                # Registrar actividad
                                db_manager.log_activity(
                                    user_id=st.session_state.user['username'],
                                    action='password_changed_by_admin',
                                    entity_type='user',
                                    entity_id=user_data['username']
                                )
                                
                                st.success("✅ Contraseña actualizada exitosamente")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.error("❌ Las contraseñas no coinciden")
                    else:
                        st.error("⚠️ Completa ambos campos")
            
            st.divider()
            
            # Forzar reset de contraseña
            col_reset1, col_reset2 = st.columns(2)
            
            with col_reset1:
                if st.button("🔓 Forzar Reset en Próximo Login", type="secondary"):
                    conn.execute(
                        "UPDATE users SET force_reset = 1 WHERE username = ?",
                        (user_data['username'],)
                    )
                    conn.commit()
                    st.success("✅ Reset forzado configurado")
                    time.sleep(1)
                    st.rerun()
            
            with col_reset2:
                if st.button("📧 Enviar Email de Recuperación", type="secondary"):
                    st.info("Función de email en desarrollo")
        
        with tab_courses:
            st.markdown("#### 📚 Cursos Asociados")
            
            # Cursos como profesor
            if user_data['role'] == 'teacher':
                st.markdown("##### 👨‍🏫 Cursos como Profesor")
                teacher_courses_rows = conn.execute("""
                    SELECT * FROM courses WHERE teacher_id = ?
                """, (user_data['username'],)).fetchall()
                teacher_courses = [dict(c) for c in teacher_courses_rows]
                
                if teacher_courses:
                    for course in teacher_courses:
                        with st.container(border=True):
                            col_c1, col_c2 = st.columns([3, 1])
                            col_c1.write(f"**{course['name']}**")
                            col_c1.caption(f"{course['code']} | {course['status']}")
                            if col_c2.button("👁️", key=f"view_tc_{course['id']}"):
                                st.session_state.admin_edit_course = dict(course)
                                st.session_state.admin_mode = 'edit_course'
                                st.rerun()
                else:
                    st.info("No es profesor de ningún curso")
            
            # Cursos como estudiante
            if user_data['role'] == 'student':
                st.markdown("##### 🎓 Cursos como Estudiante")
                student_courses_rows = conn.execute("""
                    SELECT c.* FROM courses c
                    JOIN enrollments e ON c.id = e.course_id
                    WHERE e.student_id = ?
                """, (user_data['username'],)).fetchall()
                student_courses = [dict(c) for c in student_courses_rows]
                
                if student_courses:
                    for course in student_courses:
                        with st.container(border=True):
                            col_c1, col_c2, col_c3 = st.columns([3, 1, 1])
                            col_c1.write(f"**{course['name']}**")
                            col_c1.caption(f"{course['code']}")
                            
                            if col_c2.button("👁️", key=f"view_sc_{course['id']}"):
                                st.session_state.admin_edit_course = dict(course)
                                st.session_state.admin_mode = 'edit_course'
                                st.rerun()
                            
                            if col_c3.button("🗑️", key=f"remove_sc_{course['id']}"):
                                conn.execute(
                                    "DELETE FROM enrollments WHERE course_id = ? AND student_id = ?",
                                    (course['id'], user_data['username'])
                                )
                                conn.commit()
                                st.success("✅ Estudiante removido del curso")
                                time.sleep(1)
                                st.rerun()
                else:
                    st.info("No está inscrito en ningún curso")
            
            # Matricular en nuevo curso
            st.divider()
            st.markdown("##### ➕ Matricular en Nuevo Curso")
            
            available_courses_rows = conn.execute("""
                SELECT * FROM courses 
                WHERE id NOT IN (
                    SELECT course_id FROM enrollments 
                    WHERE student_id = ?
                )
                AND status = 'active'
            """, (user_data['username'],)).fetchall()
            available_courses = [dict(c) for c in available_courses_rows]
            
            if available_courses:
                course_options = {f"{c['code']} - {c['name']}": c['id'] for c in available_courses}
                selected_course = st.selectbox("Seleccionar Curso", list(course_options.keys()))
                
                if st.button("🎓 Matricular", type="primary"):
                    course_id = course_options[selected_course]
                    conn.execute(
                        "INSERT INTO enrollments (student_id, course_id, enrollment_date) VALUES (?, ?, ?)",
                        (user_data['username'], course_id, date.today())
                    )
                    conn.commit()
                    st.success("✅ Estudiante matriculado exitosamente")
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("No hay cursos disponibles para matricular")
        
        with tab_activity:
            st.markdown("#### 📈 Actividad del Usuario")
            
            user_activity_rows = conn.execute("""
                SELECT * FROM activity_logs 
                WHERE user_id = ?
                ORDER BY created_at DESC 
                LIMIT 20
            """, (user_data['username'],)).fetchall()
            user_activity = [dict(a) for a in user_activity_rows]
            
            if user_activity:
                for activity in user_activity:
                    with st.container(border=True):
                        col_a1, col_a2 = st.columns([3, 1])
                        col_a1.markdown(f"**{activity['action'].replace('_', ' ').title()}**")
                        if activity['entity_type']:
                            col_a1.caption(f"📁 {activity['entity_type']}")
                        col_a2.caption(
                            datetime.strptime(activity['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                            if activity['created_at'] else '—'
                        )
            else:
                st.info("No hay actividad registrada")
    
    # ==============================================================================
    # VISTA 3: EDITAR CURSO
    # ==============================================================================
    elif st.session_state.admin_mode == 'edit_course' and st.session_state.admin_edit_course:
        course = st.session_state.admin_edit_course
        
        st.title(f"📝 Editando Curso: {course['name']}")
        
        if st.button("← Volver al Panel"):
            st.session_state.admin_mode = 'dashboard'
            st.session_state.admin_edit_course = None
            st.rerun()
        
        # Tabs del curso
        tab_info, tab_students, tab_content, tab_stats = st.tabs([
            "📋 Información",
            "👥 Estudiantes",
            "📚 Contenido",
            "📊 Estadísticas"
        ])
        
        with tab_info:
            with st.form("edit_course_form"):
                col_name, col_code = st.columns(2)
                new_name = col_name.text_input("Nombre", value=course['name'])
                new_code = col_code.text_input("Código", value=course['code'])
                
                # Profesor
                teachers_rows = conn.execute(
                    "SELECT username, full_name FROM users WHERE role = 'teacher' AND is_active = 1"
                ).fetchall()
                teachers = [dict(t) for t in teachers_rows]
                
                teacher_options = {f"{t['full_name']} ({t['username']})": t['username'] for t in teachers}
                teacher_options["Sin asignar"] = None
                
                current_teacher_label = next(
                    (k for k, v in teacher_options.items() if v == course.get('teacher_id')), 
                    "Sin asignar"
                )
                
                new_teacher = st.selectbox(
                    "Profesor",
                    list(teacher_options.keys()),
                    index=list(teacher_options.keys()).index(current_teacher_label)
                )
                
                new_desc = st.text_area("Descripción", value=course.get('description', ''), height=100)
                
                col_credits, col_semester, col_status = st.columns(3)
                new_credits = col_credits.number_input("Horas semanales", min_value=1, max_value=40, value=course.get('credits', 3))
                new_semester = col_semester.text_input("Semestre", value=course.get('semester', ''))
                new_status = col_status.selectbox(
                    "Estado",
                    ["active", "archived", "draft"],
                    index=["active", "archived", "draft"].index(course.get('status', 'active')),
                    format_func=lambda x: {
                        "active": "🟢 Activo",
                        "archived": "📁 Archivado",
                        "draft": "📝 Borrador"
                    }[x]
                )
                
                # Imagen
                current_image = course.get('cover_image')
                new_image = st.file_uploader("Imagen de portada", type=['png', 'jpg', 'jpeg'])
                
                if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                    image_blob = new_image.getvalue() if new_image else current_image
                    teacher_id = teacher_options[new_teacher]
                    
                    conn.execute("""
                        UPDATE courses SET
                            name = ?, code = ?, teacher_id = ?, description = ?,
                            credits = ?, semester = ?, status = ?, cover_image = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        new_name, new_code, teacher_id, new_desc,
                        new_credits, new_semester, new_status, image_blob,
                        datetime.now(), course['id']
                    ))
                    
                    conn.commit()
                    
                    # Actualizar objeto en sesión
                    st.session_state.admin_edit_course.update({
                        'name': new_name,
                        'code': new_code,
                        'teacher_id': teacher_id,
                        'description': new_desc,
                        'credits': new_credits,
                        'semester': new_semester,
                        'status': new_status,
                        'cover_image': image_blob
                    })
                    
                    st.success("✅ Curso actualizado exitosamente")
                    time.sleep(1)
                    st.rerun()
        
        with tab_students:
            st.markdown("#### 👥 Estudiantes Inscritos")
            
            # Lista de estudiantes (convertir a diccionarios)
            students_rows = conn.execute("""
                SELECT u.*, e.enrollment_date 
                FROM users u
                JOIN enrollments e ON u.username = e.student_id
                WHERE e.course_id = ?
                ORDER BY u.full_name
            """, (course['id'],)).fetchall()
            students = [dict(s) for s in students_rows]
            
            if not students:
                st.info("📭 No hay estudiantes inscritos")
            else:
                # Estadísticas
                col_sstats = st.columns(3)
                col_sstats[0].metric("Total", len(students))
                
                # CORREGIDO: ahora `students` son diccionarios y .get() funciona
                active_students = len([s for s in students if s.get('is_active', 1) == 1])
                col_sstats[1].metric("Activos", active_students)
                
                # Tabla de estudiantes
                df_data = []
                for student in students:
                    df_data.append({
                        "Nombre": student['full_name'],
                        "Usuario": student['username'],
                        "Email": student.get('email', ''),
                        "Inscrito": student['enrollment_date'],
                        "Estado": "✅ Activo" if student.get('is_active', 1) == 1 else "❌ Inactivo"
                    })
                
                df = pd.DataFrame(df_data)
                st.dataframe(df, width='stretch', hide_index=True)
                
                # Comunicación y gestión de estudiantes
                st.markdown("##### � Comunicación y Gestión")

                for student in students:
                    with st.container(border=True):
                        col_info, col_actions = st.columns([3, 2])

                        with col_info:
                            has_email = bool(student.get('email'))
                            email_badge = f"📧 {student['email']}" if has_email else "⚠️ Sin email"
                            email_color = "color:#aaa" if has_email else "color:#e05252;font-weight:bold"
                            st.markdown(
                                f"**{student['full_name']}** — `{student['username']}`  \n"
                                f'<span style="{email_color};font-size:0.85em;">{email_badge}</span>',
                                unsafe_allow_html=True
                            )

                        with col_actions:
                            btn_key = f"action_{course['id']}_{student['username']}"
                            
                            # Verificar si se debe resetear el selectbox
                            reset_sel = st.session_state.get(f"reset_sel_{btn_key}", False)
                            if reset_sel:
                                st.session_state[f"sel_{btn_key}"] = "— Seleccionar —"
                                st.session_state.pop(f"reset_sel_{btn_key}", None)
                            
                            action_sel = st.selectbox(
                                "Acción",
                                ["— Seleccionar —", "✉️ Enviar mensaje", "🚫 Desmatricular"],
                                key=f"sel_{btn_key}",
                                label_visibility="collapsed"
                            )
                            
                            # Si se selecciona "Enviar mensaje", abrir directamente el panel
                            if action_sel == "✉️ Enviar mensaje":
                                st.session_state[f"show_action_{btn_key}"] = action_sel
                            
                            # Si se selecciona "Desmatricular", mostrar botón "Ejecutar"
                            elif action_sel == "🚫 Desmatricular":
                                if st.button("Ejecutar", key=f"exec_{btn_key}", type="primary"):
                                    st.session_state[f"show_action_{btn_key}"] = action_sel

                        # Panel de acción expandido
                        action_state = st.session_state.get(f"show_action_{btn_key}")
                        if action_state == "✉️ Enviar mensaje":
                            with st.container():
                                msg_text = st.text_area(
                                    "Mensaje:",
                                    height=80,
                                    placeholder="Escribe el mensaje para el estudiante...",
                                    key=f"msg_{btn_key}"
                                )
                                col_send, col_cancel = st.columns(2)
                                if col_send.button("📤 Enviar", key=f"send_{btn_key}", type="primary"):
                                    if msg_text.strip():
                                        try:
                                            admin_id = st.session_state.user['username']
                                            student_id = student['username']
                                            course_id = course['id']
                                            
                                            # Ordenar IDs para garantizar unicidad
                                            u1, u2 = sorted([admin_id, student_id])
                                            
                                            # Crear o obtener conversación directamente con conn
                                            existing = conn.execute("""
                                                SELECT id FROM conversations
                                                WHERE user1_id = ? AND user2_id = ? AND course_id = ?
                                            """, (u1, u2, course_id)).fetchone()
                                            
                                            if existing:
                                                conv_id = existing['id']
                                            else:
                                                cursor = conn.execute("""
                                                    INSERT INTO conversations (user1_id, user2_id, course_id)
                                                    VALUES (?, ?, ?)
                                                """, (u1, u2, course_id))
                                                conv_id = cursor.lastrowid
                                            
                                            # Insertar mensaje
                                            conn.execute("""
                                                INSERT INTO private_messages
                                                (conversation_id, sender_id, recipient_id, message_text)
                                                VALUES (?, ?, ?, ?)
                                            """, (conv_id, admin_id, student_id, msg_text.strip()))
                                            
                                            # Actualizar timestamp
                                            conn.execute("""
                                                UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?
                                            """, (conv_id,))
                                            conn.commit()
                                            
                                            st.session_state.pop(f"show_action_{btn_key}", None)
                                            st.session_state[f"reset_sel_{btn_key}"] = True
                                            st.success(f"✅ Mensaje enviado a {student['full_name']}")
                                            time.sleep(1)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error: {e}")
                                    else:
                                        st.warning("Escribe un mensaje antes de enviar")
                                if col_cancel.button("Cancelar", key=f"cancel_msg_{btn_key}"):
                                    st.session_state.pop(f"show_action_{btn_key}", None)
                                    st.session_state[f"reset_sel_{btn_key}"] = True
                                    st.rerun()

                        elif action_state == "🚫 Desmatricular":
                            st.warning(f"¿Desmatricular a **{student['full_name']}** de este curso?")
                            col_yes, col_no = st.columns(2)
                            if col_yes.button("✅ Confirmar", key=f"confirm_unenroll_{btn_key}", type="primary"):
                                conn.execute(
                                    "DELETE FROM enrollments WHERE course_id = ? AND student_id = ?",
                                    (course['id'], student['username'])
                                )
                                conn.commit()
                                st.session_state.pop(f"show_action_{btn_key}", None)
                                st.success(f"✅ {student['full_name']} desmatriculado")
                                time.sleep(1)
                                st.rerun()
                            if col_no.button("❌ Cancelar", key=f"cancel_unenroll_{btn_key}"):
                                st.session_state.pop(f"show_action_{btn_key}", None)
                                st.session_state[f"reset_sel_{btn_key}"] = True
                                st.rerun()
                                st.rerun()
        
        with tab_content:
            st.markdown("#### 📚 Contenido del Curso")
            
            # Módulos
            modules_rows = conn.execute("""
                SELECT * FROM modules 
                WHERE course_id = ?
                ORDER BY order_index
            """, (course['id'],)).fetchall()
            modules = [dict(m) for m in modules_rows]
            
            if not modules:
                st.info("📭 No hay módulos creados")
            else:
                for module in modules:
                    with st.expander(f"📌 {module['title']}"):
                        # Materiales
                        materials = conn.execute("""
                            SELECT * FROM course_materials 
                            WHERE module_id = ?
                        """, (module['id'],)).fetchall()
                        
                        # Tareas
                        tasks = conn.execute("""
                            SELECT * FROM tasks 
                            WHERE module_id = ?
                        """, (module['id'],)).fetchall()
                        
                        # Exámenes
                        exams = conn.execute("""
                            SELECT * FROM exams 
                            WHERE module_id = ?
                        """, (module['id'],)).fetchall()
                        
                        st.markdown(f"**📄 Materiales:** {len(materials)}")
                        st.markdown(f"**📝 Tareas:** {len(tasks)}")
                        st.markdown(f"**✅ Exámenes:** {len(exams)}")
                        
                        # Botón para eliminar módulo
                        if st.button("🗑️ Eliminar Módulo", key=f"del_mod_{module['id']}"):
                            conn.execute("DELETE FROM modules WHERE id = ?", (module['id'],))
                            conn.commit()
                            st.success("✅ Módulo eliminado")
                            time.sleep(1)
                            st.rerun()
        
        with tab_stats:
            st.markdown("#### 📊 Estadísticas del Curso")
            
            # Métricas del curso
            col_cstats = st.columns(3)
            
            with col_cstats[0]:
                submissions_count = conn.execute("""
                    SELECT COUNT(*) FROM submissions s
                    JOIN tasks t ON s.task_id = t.id
                    WHERE t.course_id = ?
                """, (course['id'],)).fetchone()[0]
                st.metric("📝 Entregas", submissions_count)
            
            with col_cstats[1]:
                avg_grade = conn.execute("""
                    SELECT AVG(s.final_grade) FROM submissions s
                    JOIN tasks t ON s.task_id = t.id
                    WHERE t.course_id = ? AND s.final_grade IS NOT NULL
                """, (course['id'],)).fetchone()[0]
                st.metric("📈 Promedio", f"{avg_grade:.1f}" if avg_grade else "0")
            
            with col_cstats[2]:
                exam_attempts = conn.execute("""
                    SELECT COUNT(*) FROM exam_attempts a
                    JOIN exams e ON a.exam_id = e.id
                    WHERE e.course_id = ?
                """, (course['id'],)).fetchone()[0]
                st.metric("✅ Exámenes", exam_attempts)
            
            st.divider()
            
            # Gráficos
            st.markdown("##### 📈 Distribución de Calificaciones")
            
            grades = conn.execute("""
                SELECT s.final_grade FROM submissions s
                JOIN tasks t ON s.task_id = t.id
                WHERE t.course_id = ? AND s.final_grade IS NOT NULL
            """, (course['id'],)).fetchall()
            
            if grades:
                grades_list = [g['final_grade'] for g in grades]
                grades_df = pd.DataFrame(grades_list, columns=['Calificación'])
                
                st.bar_chart(grades_df, width='stretch')
            else:
                st.info("No hay calificaciones registradas")
    
    # ==============================================================================
    # VISTA 4: MATRICULACIÓN MASIVA
    # ==============================================================================
    elif st.session_state.admin_mode == 'bulk_enroll' and st.session_state.get('admin_enroll_course'):
        course = st.session_state.admin_enroll_course
        
        st.title(f"🎓 Matriculación Masiva: {course['name']}")
        
        if st.button("← Volver al Panel"):
            st.session_state.admin_mode = 'dashboard'
            st.session_state.admin_enroll_course = None
            st.rerun()
        
        # Opciones de matriculación
        tab_single, tab_bulk, tab_csv = st.tabs([
            "👤 Individual",
            "👥 Múltiple", 
            "📄 CSV"
        ])
        
        with tab_single:
            st.markdown("#### 👤 Matricular Estudiante Individual")
            
            # --- CORRECCIÓN: Búsqueda FUERA del formulario para que sea interactiva ---
            search_student = st.text_input("Buscar estudiante...", placeholder="Nombre, usuario o email")
            
            if search_student:
                students_rows = conn.execute("""
                    SELECT username, full_name, email, user_code
                    FROM users 
                    WHERE role = 'student' 
                    AND is_active = 1
                    AND (full_name LIKE ? OR username LIKE ? OR email LIKE ? OR user_code LIKE ?)
                """, (f"%{search_student}%", f"%{search_student}%", f"%{search_student}%", f"%{search_student}%")).fetchall()
                students = [dict(s) for s in students_rows]
                
                if students:
                    # Formulario SOLO para la acción
                    with st.form("single_enroll_form"):
                        student_options = {f"{s['full_name']} ({s['username']}) - {s['user_code']}": s['username'] for s in students}
                        selected_student = st.selectbox("Seleccionar estudiante", list(student_options.keys()))
                        
                        # Botón INCONDICIONAL dentro del form
                        if st.form_submit_button("🎓 Matricular Estudiante", type="primary"):
                            student_id = student_options[selected_student]
                            
                            existing = conn.execute("""
                                SELECT 1 FROM enrollments 
                                WHERE course_id = ? AND student_id = ?
                            """, (course['id'], student_id)).fetchone()
                            
                            if existing:
                                st.warning("⚠️ Este estudiante ya está matriculado en el curso")
                            else:
                                conn.execute("""
                                    INSERT INTO enrollments (student_id, course_id, enrollment_date)
                                    VALUES (?, ?, ?)
                                """, (student_id, course['id'], date.today()))
                                
                                conn.commit()
                                
                                db_manager.log_activity(
                                    user_id=st.session_state.user['username'],
                                    action='student_enrolled',
                                    entity_type='course',
                                    entity_id=course['id'],
                                    details={'student_id': student_id, 'course_name': course['name']}
                                )
                                
                                notification_manager.create_notification(
                                    user_id=student_id,
                                    title="🎓 Nueva Matriculación",
                                    message=f"Has sido matriculado en el curso {course['name']}",
                                    notification_type='info',
                                    link=f"?course={course['id']}"
                                )
                                
                                st.success("✅ Estudiante matriculado exitosamente")
                                time.sleep(1)
                                st.rerun()
                else:
                    st.info("No se encontraron estudiantes")
            else:
                st.info("Ingresa un término de búsqueda")
        
        with tab_bulk:
            st.markdown("#### 👥 Matricular Múltiples Estudiantes")
            
            # Lista de todos los estudiantes
            all_students_rows = conn.execute("""
                SELECT username, full_name, email, user_code
                FROM users 
                WHERE role = 'student' AND is_active = 1
                ORDER BY full_name
            """).fetchall()
            all_students = [dict(s) for s in all_students_rows]
            
            if all_students:
                student_options = {f"{s['full_name']} ({s['username']})": s['username'] for s in all_students}
                selected_students = st.multiselect(
                    "Seleccionar estudiantes:",
                    list(student_options.keys()),
                    help="Puedes seleccionar múltiples estudiantes"
                )
                
                if selected_students:
                    if st.button("🎓 Matricular Seleccionados", type="primary"):
                        enrolled_count = 0
                        already_count = 0
                        
                        for student_label in selected_students:
                            student_id = student_options[student_label]
                            
                            existing = conn.execute("""
                                SELECT 1 FROM enrollments 
                                WHERE course_id = ? AND student_id = ?
                            """, (course['id'], student_id)).fetchone()
                            
                            if existing:
                                already_count += 1
                            else:
                                conn.execute("""
                                    INSERT INTO enrollments (student_id, course_id, enrollment_date)
                                    VALUES (?, ?, ?)
                                """, (student_id, course['id'], date.today()))
                                enrolled_count += 1
                        
                        if enrolled_count > 0:
                            conn.commit()
                            
                            db_manager.log_activity(
                                user_id=st.session_state.user['username'],
                                action='bulk_enrollment',
                                entity_type='course',
                                entity_id=course['id'],
                                details={'count': enrolled_count, 'course_name': course['name']}
                            )
                            
                            st.success(f"✅ {enrolled_count} estudiantes matriculados exitosamente")
                            if already_count > 0:
                                st.info(f"📝 {already_count} estudiantes ya estaban matriculados")
                            
                            time.sleep(2)
                            st.rerun()
                        elif already_count > 0:
                            st.warning(f"⚠️ Todos los estudiantes seleccionados ya están matriculados")
                else:
                    st.info("Selecciona al menos un estudiante")
            else:
                st.info("No hay estudiantes registrados en el sistema")
        
        with tab_csv:
            st.markdown("#### 📄 Importar desde CSV")
            
            st.info("""
            **Formato del CSV requerido:**
            - Columna 1: `username` (Nombre de usuario)
            - Columna 2: `full_name` (Nombre completo)
            - Columna 3: `email` (Correo electrónico, opcional)
            
            **Ejemplo:**
            ```
            username,full_name,email
            juan.perez,Juan Pérez,juan@email.com
            maria.gomez,Maria Gómez,maria@email.com
            ```
            """)
            
            csv_file = st.file_uploader("Subir archivo CSV", type=['csv'])
            
            if csv_file:
                import csv
                from io import StringIO
                
                # Leer CSV
                stringio = StringIO(csv_file.getvalue().decode("utf-8"))
                reader = csv.DictReader(stringio)
                
                rows = list(reader)
                
                if rows:
                    st.success(f"📄 Archivo cargado: {len(rows)} registros encontrados")
                    
                    # Mostrar vista previa
                    preview_df = pd.DataFrame(rows)
                    st.dataframe(preview_df.head(), width='stretch')
                    
                    if st.button("📤 Procesar Matriculaciones", type="primary"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        enrolled = 0
                        errors = 0
                        skipped = 0
                        
                        for i, row in enumerate(rows):
                            progress = (i + 1) / len(rows)
                            progress_bar.progress(progress)
                            status_text.text(f"Procesando {i+1} de {len(rows)}...")
                            
                            username = row.get('username', '').strip()
                            
                            if not username:
                                errors += 1
                                continue
                            
                            # Verificar si el usuario existe
                            user_exists = conn.execute(
                                "SELECT 1 FROM users WHERE username = ? AND role = 'student' AND is_active = 1",
                                (username,)
                            ).fetchone()
                            
                            if not user_exists:
                                # Crear usuario si no existe
                                full_name = row.get('full_name', username)
                                email = row.get('email', '')
                                
                                name_parts = full_name.split()
                                first_name = name_parts[0] if name_parts else username
                                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else username
                                
                                user_code = db_manager.generate_user_code('student')
                                password_hash = hash_password('password123')
                                
                                try:
                                    conn.execute("""
                                        INSERT INTO users (
                                            username, password_hash, role, first_name, last_name, full_name,
                                            user_code, email, is_active, join_date
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        username, password_hash, 'student', first_name, last_name, full_name,
                                        user_code, email if email else None, 1, date.today()
                                    ))
                                except Exception as e:
                                    errors += 1
                                    continue
                            
                            # Matricular
                            existing = conn.execute("""
                                SELECT 1 FROM enrollments 
                                WHERE course_id = ? AND student_id = ?
                            """, (course['id'], username)).fetchone()
                            
                            if existing:
                                skipped += 1
                            else:
                                try:
                                    conn.execute("""
                                        INSERT INTO enrollments (student_id, course_id, enrollment_date)
                                        VALUES (?, ?, ?)
                                    """, (username, course['id'], date.today()))
                                    enrolled += 1
                                except:
                                    errors += 1
                        
                        conn.commit()
                        progress_bar.empty()
                        status_text.empty()
                        
                        st.success(f"""
                        ✅ **Proceso completado:**
                        - 🎓 Nuevos matriculados: **{enrolled}**
                        - 📝 Ya estaban matriculados: **{skipped}**
                        - ❌ Errores: **{errors}**
                        """)
                        
                        time.sleep(2)
                        st.rerun()
                else:
                    st.error("❌ El archivo CSV está vacío o tiene formato incorrecto")

# Función de compatibilidad para main.py
def view_admin_main(conn):
    view_admin(conn)

def render_notification_management(conn):
    """Panel de gestión de notificaciones para administradores"""
    st.markdown("### 🔔 Gestión de Notificaciones")

    # Migración: agregar columna sent_by si no existe
    try:
        conn.execute("ALTER TABLE notifications ADD COLUMN sent_by TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        pass  # Ya existe

    TYPE_LABELS = {
        'comunicado_oficial':    '📢 Comunicado Oficial',
        'aviso_urgente':         '🚨 Aviso Urgente',
        'recordatorio_academico':'📅 Recordatorio Académico',
        'logistica_servicios':   '📋 Logística / Servicios',
        'actividades_eventos':   '🎉 Actividades / Eventos',
        'retroalimentacion':     '📊 Retroalimentación',
        'success': '✅ Éxito',
        'info':    'ℹ️ Info',
        'warning': '⚠️ Aviso',
        'error':   '❌ Error',
        'welcome': '👋 Bienvenida',
        'feature': '🔧 Función',
    }

    tab1, tab2, tab3 = st.tabs(["📤 Enviar Notificación", "📋 Historial", "🗑️ Limpiar"])

    # ── TAB 1: ENVIAR ────────────────────────────────────────────────────────
    with tab1:
        st.markdown("#### Enviar Notificación Masiva")
        with st.form("form_send_notif", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                target_role = st.selectbox("Destinatarios:", [
                    "Todos los usuarios", "Estudiantes", "Profesores", "Administradores"
                ], key="notif_target_role")
                notif_type = st.selectbox("Tipo:", [
                    "📢 comunicado_oficial", "🚨 aviso_urgente",
                    "📅 recordatorio_academico", "📋 logistica_servicios",
                    "🎉 actividades_eventos", "📊 retroalimentacion",
                ], format_func=lambda x: {
                    "📢 comunicado_oficial":    "📢 Comunicado Oficial",
                    "🚨 aviso_urgente":         "🚨 Aviso Urgente",
                    "📅 recordatorio_academico":"📅 Recordatorio Académico",
                    "📋 logistica_servicios":   "📋 Logística / Servicios",
                    "🎉 actividades_eventos":   "🎉 Actividades / Eventos",
                    "📊 retroalimentacion":     "📊 Retroalimentación",
                }.get(x, x), key="notif_type_sel")
            with col2:
                title   = st.text_input("Título:", key="notif_title")
                message = st.text_area("Mensaje:", height=100, key="notif_message")
            submitted = st.form_submit_button("📤 Enviar Notificación", type="primary")

        if submitted:
            notif_type_key = notif_type.split(" ", 1)[1] if " " in notif_type else notif_type
            if title and message:
                role_map = {"Estudiantes": "student", "Profesores": "teacher", "Administradores": "admin"}
                target   = role_map.get(target_role)
                users = conn.execute(
                    "SELECT username FROM users WHERE role=? AND is_active=1", (target,)
                ).fetchall() if target else conn.execute(
                    "SELECT username FROM users WHERE role IN ('student','teacher') AND is_active=1"
                ).fetchall()
                count = 0
                for user in users:
                    try:
                        conn.execute(
                            "INSERT INTO notifications (user_id,title,message,type,is_read,sent_by,created_at) "
                            "VALUES (?,?,?,?,0,?,CURRENT_TIMESTAMP)",
                            (user['username'], title, message, notif_type_key,
                             st.session_state.user['username']))
                        count += 1
                    except Exception:
                        pass
                conn.commit()
                st.success(f"✅ Notificación enviada a {count} usuarios")
            else:
                st.error("❌ Completa el título y el mensaje")

    # ── TAB 2: HISTORIAL AGRUPADO POR CATEGORÍA ───────────────────────────
    with tab2:
        st.markdown("#### 📋 Historial por Categoría")
        st.caption("Toca una categoría para ver todas las notificaciones enviadas")

        cats = conn.execute(
            "SELECT type, COUNT(*) as n FROM notifications "
            "WHERE type IN ('comunicado_oficial','aviso_urgente','recordatorio_academico',"
            "'logistica_servicios','actividades_eventos','retroalimentacion') "
            "GROUP BY type ORDER BY n DESC"
        ).fetchall()

        if not cats:
            st.info("No hay notificaciones registradas")
        else:
            for cat in cats:
                tipo  = cat['type'] or 'otros'
                count = cat['n']
                label = TYPE_LABELS.get(tipo, tipo)

                with st.expander(f"{label}  —  {count} notificaciones"):
                    rows = conn.execute(
                        "SELECT n.user_id, n.title, n.message, n.is_read, n.created_at, "
                        "COALESCE(u.full_name, n.sent_by, 'Sistema') AS admin_name "
                        "FROM notifications n "
                        "LEFT JOIN users u ON n.sent_by = u.username "
                        "WHERE n.type=? ORDER BY n.created_at DESC",
                        (tipo,)).fetchall()
                    for row in rows:
                        row = dict(row)
                        try:
                            fecha = datetime.strptime(
                                row['created_at'], '%Y-%m-%d %H:%M:%S'
                            ).strftime('%d/%m/%Y %H:%M')
                        except Exception:
                            fecha = row['created_at'] or ''
                        estado = "✅" if row['is_read'] else "📬"
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([4, 2, 1])
                            c1.markdown(f"**{row['title']}**")
                            c1.caption(row['message'][:100] + ('…' if len(row['message']) > 100 else ''))
                            c2.caption(f"👤 Para: {row['user_id']}")
                            c2.caption(f"🛡️ Enviado por: **{row['admin_name']}**")
                            c2.caption(f"📅 {fecha}")
                            c3.markdown(estado)

    # ── TAB 3: LIMPIAR ────────────────────────────────────────────────────
    with tab3:
        st.markdown("#### 🗑️ Limpiar Notificaciones")
        st.warning("⚠️ Estas acciones son irreversibles")

        # Por categoría
        st.markdown("##### Por categoría")
        cat_rows = conn.execute(
            "SELECT type, COUNT(*) as n FROM notifications "
            "WHERE type IN ('comunicado_oficial','aviso_urgente','recordatorio_academico',"
            "'logistica_servicios','actividades_eventos','retroalimentacion') "
            "GROUP BY type ORDER BY n DESC"
        ).fetchall()

        if cat_rows:
            for cat in cat_rows:
                tipo  = cat['type'] or 'sin_tipo'
                label = TYPE_LABELS.get(tipo, tipo)
                col_a, col_b = st.columns([4, 1])
                col_a.markdown(f"**{label}** — {cat['n']} notificaciones")
                if col_b.button("🗑️ Eliminar", key=f"clean_cat_{tipo}", use_container_width=True):
                    st.session_state[f'confirm_clean_{tipo}'] = True

                if st.session_state.get(f'confirm_clean_{tipo}'):
                    st.warning(f"¿Eliminar todas las de **{label}**?")
                    cy, cn = st.columns(2)
                    if cy.button("✅ Sí", key=f"yes_clean_{tipo}", type="primary"):
                        deleted = conn.execute(
                            "DELETE FROM notifications WHERE type=?", (tipo,)).rowcount
                        conn.commit()
                        st.session_state.pop(f'confirm_clean_{tipo}', None)
                        st.success(f"✅ {deleted} notificaciones eliminadas")
                    if cn.button("❌ Cancelar", key=f"no_clean_{tipo}"):
                        st.session_state.pop(f'confirm_clean_{tipo}', None)
                        st.rerun()
        else:
            st.info("No hay notificaciones para limpiar")

        st.divider()

        # Borrar todo
        st.markdown("##### Borrar todo")
        if st.button("🔴 Eliminar TODAS las notificaciones", use_container_width=True, type="secondary"):
            st.session_state['confirm_delete_all_notifs'] = True

        if st.session_state.get('confirm_delete_all_notifs'):
            st.error("¿Eliminar **TODAS** las notificaciones del sistema?")
            ca2, cb2 = st.columns(2)
            if ca2.button("✅ Confirmar", key="del_all_yes", type="primary"):
                deleted = conn.execute("DELETE FROM notifications").rowcount
                conn.commit()
                st.session_state.pop('confirm_delete_all_notifs', None)
                st.success(f"✅ {deleted} notificaciones eliminadas")
            if cb2.button("❌ Cancelar", key="del_all_no"):
                st.session_state.pop('confirm_delete_all_notifs', None)
                st.rerun()



# ==============================================================================
# CHAT EXCLUSIVO ENTRE ADMINISTRADORES
# ==============================================================================

def _ensure_admin_chat_tables(conn):
    """Crea las tablas necesarias para el chat de admins si no existen."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS admin_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            message_text TEXT NOT NULL DEFAULT '',
            is_read_by TEXT DEFAULT '[]',
            has_attachment INTEGER DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS admin_message_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_content BLOB NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES admin_messages(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS admin_direct_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            message_text TEXT NOT NULL DEFAULT '',
            is_read INTEGER DEFAULT 0,
            has_attachment INTEGER DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (recipient_id) REFERENCES users(username) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS admin_direct_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_content BLOB NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES admin_direct_messages(id) ON DELETE CASCADE
        );
    """)
    for migration in ["ALTER TABLE admin_messages ADD COLUMN has_attachment INTEGER DEFAULT 0"]:
        try:
            conn.execute(migration)
        except Exception:
            pass
    conn.commit()


def _render_admin_bubble(msg, u, files):
    """Renderiza burbuja de mensaje con archivos adjuntos."""
    import html as _html
    is_mine = msg['sender_id'] == u['username']
    align  = "flex-end" if is_mine else "flex-start"
    bg     = "linear-gradient(135deg,rgba(59,130,246,0.3),rgba(59,130,246,0.2))" if is_mine else "rgba(11,18,32,0.8)"
    border = "1px solid rgba(59,130,246,0.25)" if is_mine else "1px solid rgba(255,255,255,0.07)"
    name   = "Tú" if is_mine else _html.escape(msg.get('sender_name', msg['sender_id']))
    try:
        t = datetime.strptime(msg['sent_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
    except Exception:
        t = str(msg['sent_at'] or "")
    safe_text = _html.escape(msg['message_text']) if msg['message_text'] else ""
    files_html = ""
    for f in files:
        ftype = (f['file_type'] or '').lower()
        fname = _html.escape(f['file_name'])
        fsize = f"{f['file_size']//1024} KB" if f['file_size'] > 1024 else f"{f['file_size']} B"
        if ftype.startswith('image/'):
            b64 = base64.b64encode(f['file_content']).decode()
            files_html += f'<div style="margin-top:8px;"><img src="data:{ftype};base64,{b64}" style="max-width:260px;max-height:200px;border-radius:8px;border:1px solid rgba(255,255,255,0.1);"><div style="font-size:0.70em;color:#64748B;margin-top:2px;">{fname}</div></div>'
        else:
            icon = "📕" if 'pdf' in ftype else ("📦" if 'zip' in ftype or 'rar' in ftype else ("🎬" if 'video' in ftype else ("🎵" if 'audio' in ftype else "📄")))
            files_html += f'<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;gap:8px;"><span style="font-size:1.2rem;">{icon}</span><div><div style="font-size:0.82em;color:#F8FAFC;">{fname}</div><div style="font-size:0.70em;color:#64748B;">{fsize}</div></div></div>'
    text_block = f'<div style="color:#F8FAFC;font-size:0.92em;line-height:1.4;">{safe_text}</div>' if safe_text else ""
    st.markdown(f"""
    <div style="display:flex;justify-content:{align};margin-bottom:12px;">
      <div style="background:{bg};padding:12px 16px;border-radius:14px;max-width:75%;word-wrap:break-word;border:{border};">
        <div style="font-weight:600;font-size:0.82em;color:#60A5FA;margin-bottom:4px;">{name}</div>
        {text_block}{files_html}
        <div style="font-size:0.70em;color:#475569;margin-top:6px;text-align:right;">{t}</div>
      </div>
    </div>""", unsafe_allow_html=True)


def view_admin_chat(conn):
    """Chat de grupo exclusivo entre administradores con soporte de archivos."""
    import json as _json
    u = st.session_state.user
    _ensure_admin_chat_tables(conn)

    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("← Volver", key="admin_chat_back_main"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
    with col_title:
        st.markdown("## 💬 Chat de Administradores")
        st.caption("Espacio privado exclusivo · Todos los administradores")
    st.divider()

    try:
        for m in conn.execute("SELECT id, is_read_by FROM admin_messages WHERE sender_id != ?", (u['username'],)).fetchall():
            leidos = _json.loads(m['is_read_by'] or '[]')
            if u['username'] not in leidos:
                leidos.append(u['username'])
                conn.execute("UPDATE admin_messages SET is_read_by=? WHERE id=?", (_json.dumps(leidos), m['id']))
        conn.commit()
    except Exception:
        pass

    try:
        messages = [dict(r) for r in conn.execute("""
            SELECT am.id, am.sender_id, am.message_text, am.sent_at, am.has_attachment,
                   u.first_name || ' ' || u.last_name AS sender_name
            FROM admin_messages am JOIN users u ON am.sender_id = u.username
            ORDER BY am.sent_at ASC
        """).fetchall()]
    except Exception as e:
        messages = []; st.error(f"Error: {e}")

    try:
        admins = [dict(r) for r in conn.execute("SELECT username, full_name, avatar FROM users WHERE role='admin' AND is_active=1").fetchall()]
    except Exception:
        admins = []

    col_chat, col_admins = st.columns([4, 1])
    with col_admins:
        st.markdown("**👥 Admins**")
        for adm in admins:
            is_me = adm['username'] == u['username']
            av_src = ("data:image/png;base64," + base64.b64encode(adm['avatar']).decode() if adm['avatar'] else "https://cdn-icons-png.flaticon.com/512/847/847969.png")
            st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;padding:8px;border-radius:10px;background:{'rgba(59,130,246,0.1)' if is_me else 'rgba(255,255,255,0.04)'};border:1px solid {'rgba(59,130,246,0.3)' if is_me else 'rgba(255,255,255,0.07)'};">
                <img src="{av_src}" style="width:28px;height:28px;border-radius:50%;object-fit:cover;">
                <div style="font-size:0.78rem;color:{'#60A5FA' if is_me else '#94A3B8'};">{adm['full_name']}{' (tú)' if is_me else ''}</div></div>""", unsafe_allow_html=True)

    with col_chat:
        with st.container(height=400):
            if messages:
                for msg in messages:
                    files = []
                    if msg['has_attachment']:
                        try:
                            files = [dict(r) for r in conn.execute("SELECT * FROM admin_message_files WHERE message_id=?", (msg['id'],)).fetchall()]
                        except Exception:
                            pass
                    _render_admin_bubble(msg, u, files)
            else:
                st.markdown('<div style="text-align:center;padding:60px;color:#475569;"><div style="font-size:2.5rem;">💬</div><div style="margin-top:8px;">No hay mensajes aún</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if 'achat_counter' not in st.session_state:
            st.session_state.achat_counter = 0
        msg_input = st.text_area("Mensaje", placeholder="Escribe un mensaje...", height=120,
            key=f"achat_input_{st.session_state.achat_counter}", label_visibility="collapsed")
        uploaded_file = st.file_uploader("📎 Adjuntar archivo", type=None, key=f"achat_file_{st.session_state.achat_counter}")

        col_send, col_clear = st.columns([3, 1])
        with col_send:
            if st.button("📤 Enviar", type="primary", use_container_width=True, key="achat_send"):
                if msg_input.strip() or uploaded_file:
                    try:
                        cur = conn.execute("INSERT INTO admin_messages (sender_id,message_text,is_read_by,has_attachment) VALUES (?,?,?,?)",
                            (u['username'], msg_input.strip(), _json.dumps([u['username']]), 1 if uploaded_file else 0))
                        if uploaded_file:
                            conn.execute("INSERT INTO admin_message_files (message_id,file_name,file_type,file_size,file_content) VALUES (?,?,?,?,?)",
                                (cur.lastrowid, uploaded_file.name, uploaded_file.type or 'application/octet-stream', uploaded_file.size, uploaded_file.getvalue()))
                        conn.commit(); st.session_state.achat_counter += 1; st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Escribe un mensaje o adjunta un archivo")
        with col_clear:
            if u['username'] == 'admin':
                if st.button("🗑️ Limpiar", use_container_width=True, key="achat_clear"):
                    st.session_state['achat_confirm_clear'] = True
        if st.session_state.get('achat_confirm_clear'):
            st.warning("¿Borrar todo el historial?")
            c1, c2 = st.columns(2)
            if c1.button("✅ Sí", type="primary", key="achat_yes"):
                conn.execute("DELETE FROM admin_message_files WHERE message_id IN (SELECT id FROM admin_messages)")
                conn.execute("DELETE FROM admin_messages"); conn.commit()
                st.session_state.pop('achat_confirm_clear', None); st.rerun()
            if c2.button("❌ Cancelar", key="achat_no"):
                st.session_state.pop('achat_confirm_clear', None); st.rerun()




def view_admin_dm(conn):
    """Mensajes directos entre admins — estilo Telegram."""
    import html as _hl
    u = st.session_state.user
    _ensure_admin_chat_tables(conn)

    # ── CSS burbujas estilo Telegram ─────────────────────────────────────────
    st.markdown("""<style>
    .tg-out{display:flex;justify-content:flex-end;margin-bottom:5px}
    .tg-in {display:flex;justify-content:flex-start;margin-bottom:5px}
    .tg-out>div{background:#2b5278;color:#e8f1fb;padding:9px 13px;
        border-radius:16px 16px 4px 16px;max-width:72%;font-size:.88rem;
        line-height:1.5;word-wrap:break-word}
    .tg-in>div{background:#182533;color:#e8edf2;padding:9px 13px;
        border-radius:16px 16px 16px 4px;max-width:72%;font-size:.88rem;
        line-height:1.5;word-wrap:break-word;border:1px solid rgba(255,255,255,.05)}
    .tg-time{font-size:.62rem;color:rgba(255,255,255,.3);text-align:right;margin-top:3px}
    .tg-datesep{text-align:center;margin:10px 0}
    .tg-datesep span{background:rgba(255,255,255,.06);color:#64748B;
        font-size:.70rem;padding:3px 12px;border-radius:10px}
    </style>""", unsafe_allow_html=True)

    # Cargar otros admins
    try:
        otros = [dict(r) for r in conn.execute(
            "SELECT username, full_name, avatar FROM users "
            "WHERE role='admin' AND is_active=1 AND username!=?",
            (u['username'],)).fetchall()]
    except Exception:
        otros = []

    if not otros:
        st.info("No hay otros administradores registrados.")
        return

    # Enriquecer con preview / unread
    palette = ['#4F46E5','#7C3AED','#0EA5E9','#10B981','#F59E0B','#EF4444']
    for i, adm in enumerate(otros):
        adm['color']   = palette[i % len(palette)]
        adm['initial'] = (adm['full_name'] or '?')[0].upper()
        try:
            adm['unread'] = conn.execute(
                "SELECT COUNT(*) FROM admin_direct_messages "
                "WHERE sender_id=? AND recipient_id=? AND is_read=0",
                (adm['username'], u['username'])).fetchone()[0]
        except Exception:
            adm['unread'] = 0
        try:
            last = conn.execute(
                "SELECT message_text, sent_at FROM admin_direct_messages "
                "WHERE (sender_id=? AND recipient_id=?) "
                "   OR (sender_id=? AND recipient_id=?) "
                "ORDER BY sent_at DESC LIMIT 1",
                (u['username'], adm['username'],
                 adm['username'], u['username'])).fetchone()
            if last:
                txt = last['message_text'] or '📎 Archivo'
                adm['preview']   = txt[:36]+'...' if len(txt)>36 else txt
                adm['last_time'] = last['sent_at'][11:16] if last['sent_at'] else ''
            else:
                adm['preview'] = 'Sin mensajes'; adm['last_time'] = ''
        except Exception:
            adm['preview'] = 'Sin mensajes'; adm['last_time'] = ''

    target_id = st.session_state.get('admin_dm_target')
    col_list, col_chat = st.columns([1, 2])

    # ══════════════════ LISTA DE CONTACTOS ═══════════════════════════════════
    with col_list:
        st.markdown("### 💬 Mensajes")
        for adm in otros:
            is_sel = target_id == adm['username']

            # Fila: avatar | info | badge
            ca, cb = st.columns([1, 4])
            with ca:
                if adm['avatar']:
                    b64 = base64.b64encode(adm['avatar']).decode()
                    st.markdown(
                        f'<img src="data:image/png;base64,{b64}" '
                        f'style="width:46px;height:46px;border-radius:50%;'
                        f'object-fit:cover;margin-top:4px;">',
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div style="width:46px;height:46px;border-radius:50%;'
                        f'background:{adm["color"]};display:flex;align-items:center;'
                        f'justify-content:center;font-size:1.2rem;font-weight:700;'
                        f'color:#fff;margin-top:4px;">{adm["initial"]}</div>',
                        unsafe_allow_html=True)
            with cb:
                name_e    = _hl.escape(adm['full_name'])
                preview_e = _hl.escape(adm['preview'])
                time_e    = _hl.escape(adm['last_time'])
                st.markdown(
                    f'<div style="padding:4px 0">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<b style="font-size:.9rem;color:#F8FAFC">{name_e}</b>'
                    f'<span style="font-size:.68rem;color:#475569">{time_e}</span>'
                    f'</div>'
                    f'<div style="font-size:.76rem;color:#64748B;margin-top:2px">{preview_e}</div>'
                    f'</div>',
                    unsafe_allow_html=True)

            # Botón abrir + badge de no leídos
            bc1, bc2 = st.columns([3, 1])
            with bc1:
                if st.button("✓ Abierto" if is_sel else "Abrir",
                             key=f"adm_dm_{adm['username']}",
                             use_container_width=True,
                             type="primary" if is_sel else "secondary"):
                    st.session_state.admin_dm_target = adm['username']
                    st.rerun()
            with bc2:
                if adm['unread'] > 0:
                    st.markdown(
                        f'<div style="background:#818CF8;color:#fff;font-size:.7rem;'
                        f'font-weight:700;padding:4px 8px;border-radius:12px;'
                        f'text-align:center;margin-top:6px">{adm["unread"]}</div>',
                        unsafe_allow_html=True)

            st.markdown('<hr style="margin:6px 0;border-color:rgba(255,255,255,.05)">', unsafe_allow_html=True)

    # ══════════════════ CONVERSACIÓN ═════════════════════════════════════════
    with col_chat:
        if not target_id:
            st.markdown(
                '<div style="text-align:center;padding:100px 20px;color:#475569;">'
                '<div style="font-size:3rem;margin-bottom:12px">💬</div>'
                '<div style="font-size:.95rem;color:#64748B">Selecciona una conversación</div>'
                '</div>', unsafe_allow_html=True)
            return

        target = next((a for a in otros if a['username'] == target_id), None)
        if not target:
            st.error("Admin no encontrado"); return

        # Marcar como leídos
        try:
            conn.execute(
                "UPDATE admin_direct_messages SET is_read=1 "
                "WHERE sender_id=? AND recipient_id=? AND is_read=0",
                (target_id, u['username']))
            conn.commit()
        except Exception:
            pass

        # Topbar
        tc1, tc2 = st.columns([8, 1])
        with tc1:
            if target['avatar']:
                av_b64 = base64.b64encode(target['avatar']).decode()
                av_html = (f'<img src="data:image/png;base64,{av_b64}" '
                           f'style="width:38px;height:38px;border-radius:50%;'
                           f'object-fit:cover;border:2px solid rgba(59,130,246,.5)">')
            else:
                av_html = (f'<div style="width:38px;height:38px;border-radius:50%;'
                           f'background:{target["color"]};display:flex;align-items:center;'
                           f'justify-content:center;font-size:1rem;font-weight:700;color:#fff;">'
                           f'{target["initial"]}</div>')

            name_e = _hl.escape(target['full_name'])
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 16px;'
                f'background:rgba(15,22,33,.95);border-radius:12px 12px 0 0;'
                f'border:1px solid rgba(255,255,255,.07);border-bottom:none;">'
                f'{av_html}'
                f'<div><div style="font-weight:700;color:#F8FAFC;font-size:.92rem">{name_e}</div>'
                f'<div style="font-size:.70rem;color:#10B981">🛡️ Administrador</div></div>'
                f'</div>',
                unsafe_allow_html=True)
        with tc2:
            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
            if st.button("✕", key="adm_dm_close", help="Cerrar conversación"):
                st.session_state.pop('admin_dm_target', None)
                st.rerun()

        # Cargar mensajes
        try:
            msgs = [dict(r) for r in conn.execute(
                "SELECT m.id,m.sender_id,m.message_text,m.sent_at,m.has_attachment "
                "FROM admin_direct_messages m "
                "WHERE (m.sender_id=? AND m.recipient_id=?) "
                "   OR (m.sender_id=? AND m.recipient_id=?) "
                "ORDER BY m.sent_at ASC",
                (u['username'], target_id, target_id, u['username'])).fetchall()]
        except Exception as e:
            msgs = []; st.error(f"Error: {e}")

        # Burbujas
        with st.container(height=380):
            if not msgs:
                st.markdown(
                    f'<div style="text-align:center;padding:60px;color:#475569;">'
                    f'<div style="font-size:2rem;margin-bottom:8px">👋</div>'
                    f'<div>Escribe el primer mensaje a <b style="color:#60A5FA">{name_e}</b></div>'
                    f'</div>', unsafe_allow_html=True)
            else:
                prev_date = None
                for msg in msgs:
                    is_mine = msg['sender_id'] == u['username']
                    try:
                        dt = datetime.strptime(msg['sent_at'], '%Y-%m-%d %H:%M:%S')
                        msg_date = dt.strftime('%d/%m/%Y')
                        msg_time = dt.strftime('%H:%M')
                    except Exception:
                        msg_date = ''; msg_time = ''

                    if msg_date and msg_date != prev_date:
                        st.markdown(f'<div class="tg-datesep"><span>{msg_date}</span></div>',
                                    unsafe_allow_html=True)
                        prev_date = msg_date

                    # Adjuntos
                    att_html = ''
                    if msg['has_attachment']:
                        try:
                            for f in conn.execute(
                                "SELECT * FROM admin_direct_files WHERE message_id=?",
                                (msg['id'],)).fetchall():
                                ftype = (f['file_type'] or '').lower()
                                fname = _hl.escape(f['file_name'])
                                fsize = (f"{f['file_size']//1024} KB"
                                         if f['file_size'] > 1024
                                         else f"{f['file_size']} B")
                                if ftype.startswith('image/'):
                                    fb64 = base64.b64encode(f['file_content']).decode()
                                    att_html += (
                                        f'<br><img src="data:{ftype};base64,{fb64}" '
                                        f'style="max-width:200px;max-height:150px;'
                                        f'border-radius:8px;margin-top:4px">')
                                else:
                                    icon = ('📕' if 'pdf' in ftype else
                                            '📦' if 'zip' in ftype or 'rar' in ftype else
                                            '🎬' if 'video' in ftype else '📄')
                                    att_html += (
                                        f'<div style="display:flex;gap:6px;align-items:center;'
                                        f'margin-top:5px;padding:5px 8px;'
                                        f'background:rgba(255,255,255,.06);border-radius:6px">'
                                        f'<span>{icon}</span>'
                                        f'<div><div style="font-size:.78rem">{fname}</div>'
                                        f'<div style="font-size:.65rem;opacity:.55">{fsize}</div>'
                                        f'</div></div>')
                        except Exception:
                            pass

                    safe_txt = _hl.escape(msg['message_text']) if msg['message_text'] else ''
                    tick = ' <span style="font-size:.6rem;opacity:.4">✓✓</span>' if is_mine else ''
                    cls  = 'tg-out' if is_mine else 'tg-in'

                    st.markdown(
                        f'<div class="{cls}"><div>'
                        f'{safe_txt}{att_html}'
                        f'<div class="tg-time">{msg_time}{tick}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True)

        # Input
        if 'adm_dm_counter' not in st.session_state:
            st.session_state.adm_dm_counter = 0

        ci, cf, cs = st.columns([5, 2, 1])
        with ci:
            dm_text = st.text_area("",
                placeholder=f"Escribe a {target['full_name']}...",
                height=120,
                key=f"adm_dm_text_{st.session_state.adm_dm_counter}",
                label_visibility="collapsed")
        with cf:
            dm_file = st.file_uploader("📎", type=None,
                key=f"adm_dm_file_{st.session_state.adm_dm_counter}",
                label_visibility="collapsed")
        with cs:
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
            if st.button("➤", key="adm_dm_send", type="primary", use_container_width=True):
                if dm_text.strip() or dm_file:
                    try:
                        cur = conn.execute(
                            "INSERT INTO admin_direct_messages "
                            "(sender_id,recipient_id,message_text,has_attachment) VALUES (?,?,?,?)",
                            (u['username'], target_id, dm_text.strip(), 1 if dm_file else 0))
                        if dm_file:
                            conn.execute(
                                "INSERT INTO admin_direct_files "
                                "(message_id,file_name,file_type,file_size,file_content) "
                                "VALUES (?,?,?,?,?)",
                                (cur.lastrowid, dm_file.name,
                                 dm_file.type or 'application/octet-stream',
                                 dm_file.size, dm_file.getvalue()))
                        conn.commit()
                        st.session_state.adm_dm_counter += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Escribe algo o adjunta un archivo")


def view_admin_teacher_chat(conn):
    """Chat de admins con docentes — visible para todos los administradores."""
    import html as _hl
    import json as _json
    u = st.session_state.user

    # Crear tabla si no existe
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS admin_teacher_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                teacher_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '',
                is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) REFERENCES users(username) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS admin_teacher_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_content BLOB NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES admin_teacher_messages(id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    except Exception:
        pass

    # CSS reutilizado del DM
    st.markdown("""<style>
    .tc-out{display:flex;justify-content:flex-end;margin-bottom:5px}
    .tc-in {display:flex;justify-content:flex-start;margin-bottom:5px}
    .tc-out>div{background:#2b5278;color:#e8f1fb;padding:9px 13px;
        border-radius:16px 16px 4px 16px;max-width:72%;font-size:.88rem;
        line-height:1.5;word-wrap:break-word}
    .tc-in>div{background:#182533;color:#e8edf2;padding:9px 13px;
        border-radius:16px 16px 16px 4px;max-width:72%;font-size:.88rem;
        line-height:1.5;word-wrap:break-word;border:1px solid rgba(255,255,255,.05)}
    .tc-time{font-size:.62rem;color:rgba(255,255,255,.3);text-align:right;margin-top:3px}
    .tc-datesep{text-align:center;margin:10px 0}
    .tc-datesep span{background:rgba(255,255,255,.06);color:#64748B;
        font-size:.70rem;padding:3px 12px;border-radius:10px}
    </style>""", unsafe_allow_html=True)

    # Cargar docentes
    try:
        teachers = [dict(r) for r in conn.execute(
            "SELECT username, full_name, avatar FROM users WHERE role='teacher' AND is_active=1"
        ).fetchall()]
    except Exception:
        teachers = []

    palette = ['#0EA5E9','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899']
    for i, t in enumerate(teachers):
        t['color']   = palette[i % len(palette)]
        t['initial'] = (t['full_name'] or '?')[0].upper()
        try:
            last = conn.execute(
                "SELECT message_text, sent_at FROM admin_teacher_messages "
                "WHERE teacher_id=? ORDER BY sent_at DESC LIMIT 1",
                (t['username'],)).fetchone()
            if last:
                txt = last['message_text'] or '📎 Archivo'
                t['preview']   = txt[:36]+'...' if len(txt)>36 else txt
                t['last_time'] = last['sent_at'][11:16] if last['sent_at'] else ''
            else:
                t['preview'] = 'Sin mensajes'; t['last_time'] = ''
        except Exception:
            t['preview'] = 'Sin mensajes'; t['last_time'] = ''

    if not teachers:
        st.info("No hay docentes registrados en el sistema.")
        return

    target_id = st.session_state.get('admin_tc_target')
    col_list, col_chat = st.columns([1, 2])

    # ══════════════ LISTA DE DOCENTES ════════════════════════════════════════
    with col_list:
        st.markdown("### 👨‍🏫 Docentes")
        for t in teachers:
            is_sel = target_id == t['username']
            if t['avatar']:
                b64 = base64.b64encode(t['avatar']).decode()
                av_html = f'<img src="data:image/png;base64,{b64}" style="width:44px;height:44px;border-radius:50%;object-fit:cover;margin-top:4px;">'
            else:
                av_html = f'<div style="width:44px;height:44px;border-radius:50%;background:{t["color"]};display:flex;align-items:center;justify-content:center;font-size:1.1rem;font-weight:700;color:#fff;margin-top:4px;">{t["initial"]}</div>'

            ca, cb = st.columns([1, 4])
            with ca:
                st.markdown(av_html, unsafe_allow_html=True)
            with cb:
                name_e    = _hl.escape(t['full_name'])
                preview_e = _hl.escape(t['preview'])
                time_e    = _hl.escape(t['last_time'])
                st.markdown(
                    f'<div style="padding:4px 0">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<b style="font-size:.9rem;color:#F8FAFC">{name_e}</b>'
                    f'<span style="font-size:.68rem;color:#475569">{time_e}</span>'
                    f'</div>'
                    f'<div style="font-size:.76rem;color:#64748B;margin-top:2px">{preview_e}</div>'
                    f'</div>',
                    unsafe_allow_html=True)

            if st.button("✓ Abierto" if is_sel else "Abrir",
                         key=f"tc_open_{t['username']}",
                         use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state.admin_tc_target = t['username']
                st.rerun()

            st.markdown('<hr style="margin:6px 0;border-color:rgba(255,255,255,.05)">', unsafe_allow_html=True)

    # ══════════════ CONVERSACIÓN ══════════════════════════════════════════════
    with col_chat:
        if not target_id:
            st.markdown(
                '<div style="text-align:center;padding:100px 20px;color:#475569;">'
                '<div style="font-size:3rem;margin-bottom:12px">👨‍🏫</div>'
                '<div style="font-size:.95rem;color:#64748B">Selecciona un docente</div>'
                '<div style="font-size:.80rem;color:#334155;margin-top:6px">Todos los admins pueden ver estas conversaciones</div>'
                '</div>', unsafe_allow_html=True)
            return

        target = next((t for t in teachers if t['username'] == target_id), None)
        if not target:
            st.error("Docente no encontrado"); return

        # Marcar como leídos para este admin
        try:
            msgs_unread = conn.execute(
                "SELECT id, is_read_by FROM admin_teacher_messages WHERE teacher_id=? AND sender_id != ?",
                (target_id, u['username'])).fetchall()
            for m in msgs_unread:
                leidos = _json.loads(m['is_read_by'] or '[]')
                if u['username'] not in leidos:
                    leidos.append(u['username'])
                    conn.execute("UPDATE admin_teacher_messages SET is_read_by=? WHERE id=?",
                                 (_json.dumps(leidos), m['id']))
            conn.commit()
        except Exception:
            pass

        # Topbar
        if target['avatar']:
            av_b64 = base64.b64encode(target['avatar']).decode()
            av_top = f'<img src="data:image/png;base64,{av_b64}" style="width:38px;height:38px;border-radius:50%;object-fit:cover;border:2px solid rgba(14,165,233,.5)">'
        else:
            av_top = f'<div style="width:38px;height:38px;border-radius:50%;background:{target["color"]};display:flex;align-items:center;justify-content:center;font-size:1rem;font-weight:700;color:#fff;">{target["initial"]}</div>'

        name_e = _hl.escape(target['full_name'])
        tc1, tc2 = st.columns([8, 1])
        with tc1:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 16px;'
                f'background:rgba(15,22,33,.95);border-radius:12px 12px 0 0;'
                f'border:1px solid rgba(255,255,255,.07);border-bottom:none;">'
                f'{av_top}'
                f'<div><div style="font-weight:700;color:#F8FAFC;font-size:.92rem">{name_e}</div>'
                f'<div style="font-size:.70rem;color:#0EA5E9">👨‍🏫 Docente</div></div>'
                f'<div style="margin-left:auto;font-size:.70rem;color:#475569;background:rgba(255,255,255,.04);'
                f'padding:3px 8px;border-radius:8px;">Visible para todos los admins 👁️</div>'
                f'</div>',
                unsafe_allow_html=True)
        with tc2:
            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
            if st.button("✕", key="tc_close", help="Cerrar conversación"):
                st.session_state.pop('admin_tc_target', None)
                st.rerun()

        # Cargar mensajes
        try:
            msgs = [dict(r) for r in conn.execute(
                "SELECT m.id, m.sender_id, m.message_text, m.sent_at, m.has_attachment, "
                "u.first_name || ' ' || u.last_name AS sender_name "
                "FROM admin_teacher_messages m JOIN users u ON m.sender_id = u.username "
                "WHERE m.teacher_id=? ORDER BY m.sent_at ASC",
                (target_id,)).fetchall()]
        except Exception as e:
            msgs = []; st.error(f"Error: {e}")

        # Burbujas
        with st.container(height=360):
            if not msgs:
                st.markdown(
                    f'<div style="text-align:center;padding:60px;color:#475569;">'
                    f'<div style="font-size:2rem;margin-bottom:8px">💬</div>'
                    f'<div>Inicia la conversación con <b style="color:#60A5FA">{name_e}</b></div>'
                    f'</div>', unsafe_allow_html=True)
            else:
                prev_date = None
                for msg in msgs:
                    is_mine = msg['sender_id'] == u['username']
                    try:
                        dt = datetime.strptime(msg['sent_at'], '%Y-%m-%d %H:%M:%S')
                        msg_date = dt.strftime('%d/%m/%Y')
                        msg_time = dt.strftime('%H:%M')
                    except Exception:
                        msg_date = ''; msg_time = ''

                    if msg_date and msg_date != prev_date:
                        st.markdown(f'<div class="tc-datesep"><span>{msg_date}</span></div>', unsafe_allow_html=True)
                        prev_date = msg_date

                    # Nombre del admin que envió (para que todos sepan quién escribió)
                    sender_label = 'Tú' if is_mine else _hl.escape(msg['sender_name'])

                    att_html = ''
                    if msg['has_attachment']:
                        try:
                            for f in conn.execute("SELECT * FROM admin_teacher_files WHERE message_id=?", (msg['id'],)).fetchall():
                                ftype = (f['file_type'] or '').lower()
                                fname = _hl.escape(f['file_name'])
                                fsize = f"{f['file_size']//1024} KB" if f['file_size'] > 1024 else f"{f['file_size']} B"
                                if ftype.startswith('image/'):
                                    fb64 = base64.b64encode(f['file_content']).decode()
                                    att_html += f'<br><img src="data:{ftype};base64,{fb64}" style="max-width:200px;max-height:150px;border-radius:8px;margin-top:4px">'
                                else:
                                    icon = '📕' if 'pdf' in ftype else ('📦' if 'zip' in ftype else ('🎬' if 'video' in ftype else '📄'))
                                    att_html += f'<div style="display:flex;gap:6px;align-items:center;margin-top:5px;padding:5px 8px;background:rgba(255,255,255,.06);border-radius:6px"><span>{icon}</span><div><div style="font-size:.78rem">{fname}</div><div style="font-size:.65rem;opacity:.55">{fsize}</div></div></div>'
                        except Exception:
                            pass

                    safe_txt = _hl.escape(msg['message_text']) if msg['message_text'] else ''
                    tick = ' <span style="font-size:.6rem;opacity:.4">✓✓</span>' if is_mine else ''
                    cls  = 'tc-out' if is_mine else 'tc-in'
                    # Mostrar quién envió si no es el usuario actual
                    sender_header = '' if is_mine else f'<div style="font-size:.72rem;color:#0EA5E9;margin-bottom:3px;font-weight:600">{sender_label}</div>'

                    st.markdown(
                        f'<div class="{cls}"><div>'
                        f'{sender_header}{safe_txt}{att_html}'
                        f'<div class="tc-time">{msg_time}{tick}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True)

        # Input
        if 'tc_counter' not in st.session_state:
            st.session_state.tc_counter = 0

        ci, cf, cs = st.columns([5, 2, 1])
        with ci:
            tc_text = st.text_area("", placeholder=f"Escribe a {target['full_name']}...",
                height=120,
                key=f"tc_text_{st.session_state.tc_counter}",
                label_visibility="collapsed")
        with cf:
            tc_file = st.file_uploader("📎", type=None,
                key=f"tc_file_{st.session_state.tc_counter}",
                label_visibility="collapsed")
        with cs:
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
            if st.button("➤", key="tc_send", type="primary", use_container_width=True):
                if tc_text.strip() or tc_file:
                    try:
                        cur = conn.execute(
                            "INSERT INTO admin_teacher_messages "
                            "(sender_id, teacher_id, message_text, has_attachment, is_read_by) "
                            "VALUES (?,?,?,?,?)",
                            (u['username'], target_id, tc_text.strip(),
                             1 if tc_file else 0, _json.dumps([u['username']])))
                        if tc_file:
                            conn.execute(
                                "INSERT INTO admin_teacher_files "
                                "(message_id,file_name,file_type,file_size,file_content) VALUES (?,?,?,?,?)",
                                (cur.lastrowid, tc_file.name,
                                 tc_file.type or 'application/octet-stream',
                                 tc_file.size, tc_file.getvalue()))
                        conn.commit()
                        st.session_state.tc_counter += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Escribe algo o adjunta un archivo")


# ==============================================================================
# CHAT ADMINISTRACIÓN — VISTA PARA DOCENTES Y ESTUDIANTES
# ==============================================================================

def _ensure_admin_user_chat_tables(conn):
    """Crea tablas para chat usuario→administración."""
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS admin_student_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                message_text TEXT NOT NULL DEFAULT '',
                is_read_by TEXT DEFAULT '[]',
                has_attachment INTEGER DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS admin_student_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_content BLOB NOT NULL,
                FOREIGN KEY (message_id) REFERENCES admin_student_messages(id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    except Exception:
        pass


def _render_user_admin_chat(conn, u, table_msg, table_files, user_field, counter_key, back_page):
    """Renderiza el chat usuario↔administración (reutilizable para docente y estudiante)."""
    import html as _hl
    import json as _json

    _ensure_admin_user_chat_tables(conn)
    if table_msg == 'admin_teacher_messages':
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS admin_teacher_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT NOT NULL,
                    teacher_id TEXT NOT NULL,
                    message_text TEXT NOT NULL DEFAULT '',
                    is_read_by TEXT DEFAULT '[]',
                    has_attachment INTEGER DEFAULT 0,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS admin_teacher_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_content BLOB NOT NULL
                );
            """)
            conn.commit()
        except Exception:
            pass

    # CSS burbujas
    st.markdown("""<style>
    .ua-out{display:flex;justify-content:flex-end;margin-bottom:5px}
    .ua-in {display:flex;justify-content:flex-start;margin-bottom:5px}
    .ua-out>div{background:#2b5278;color:#e8f1fb;padding:9px 13px;
        border-radius:16px 16px 4px 16px;max-width:72%;font-size:.88rem;
        line-height:1.5;word-wrap:break-word}
    .ua-in>div{background:#182533;color:#e8edf2;padding:9px 13px;
        border-radius:16px 16px 16px 4px;max-width:72%;font-size:.88rem;
        line-height:1.5;word-wrap:break-word;border:1px solid rgba(255,255,255,.05)}
    .ua-time{font-size:.62rem;color:rgba(255,255,255,.3);text-align:right;margin-top:3px}
    .ua-datesep{text-align:center;margin:10px 0}
    .ua-datesep span{background:rgba(255,255,255,.06);color:#64748B;
        font-size:.70rem;padding:3px 12px;border-radius:10px}
    </style>""", unsafe_allow_html=True)

    # Header
    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("← Volver", key=f"ua_back_{counter_key}"):
            st.session_state.current_page = back_page
            st.rerun()
    with col_title:
        st.markdown("## 🏛️ Chat Administración")
        st.caption("Cualquier administrador puede responder tu mensaje")
    st.divider()

    # Marcar los mensajes del admin como leídos por el usuario
    try:
        msgs_unread = conn.execute(
            f"SELECT id, is_read_by FROM {table_msg} "
            f"WHERE {user_field}=? AND sender_id != ?",
            (u['username'], u['username'])).fetchall()
        for m in msgs_unread:
            leidos = _json.loads(m['is_read_by'] or '[]')
            if u['username'] not in leidos:
                leidos.append(u['username'])
                conn.execute(f"UPDATE {table_msg} SET is_read_by=? WHERE id=?",
                             (_json.dumps(leidos), m['id']))
        conn.commit()
    except Exception:
        pass

    # Cargar mensajes
    try:
        msgs = [dict(r) for r in conn.execute(
            f"SELECT m.id, m.sender_id, m.message_text, m.sent_at, m.has_attachment, "
            f"u.first_name || ' ' || u.last_name AS sender_name, u.role AS sender_role "
            f"FROM {table_msg} m JOIN users u ON m.sender_id = u.username "
            f"WHERE m.{user_field}=? ORDER BY m.sent_at ASC",
            (u['username'],)).fetchall()]
    except Exception as e:
        msgs = []; st.error(f"Error: {e}")

    # Área de mensajes
    with st.container(height=430):
        if not msgs:
            st.markdown(
                '<div style="text-align:center;padding:80px 20px;color:#475569;">'
                '<div style="font-size:3rem;margin-bottom:12px">🏛️</div>'
                '<div style="font-size:.95rem;color:#64748B;font-weight:500">Escribe tu mensaje</div>'
                '<div style="font-size:.80rem;color:#334155;margin-top:6px">'
                'Un administrador responderá a la brevedad</div>'
                '</div>', unsafe_allow_html=True)
        else:
            prev_date = None
            for msg in msgs:
                is_mine = msg['sender_id'] == u['username']
                try:
                    dt = datetime.strptime(msg['sent_at'], '%Y-%m-%d %H:%M:%S')
                    msg_date = dt.strftime('%d/%m/%Y')
                    msg_time = dt.strftime('%H:%M')
                except Exception:
                    msg_date = ''; msg_time = ''

                if msg_date and msg_date != prev_date:
                    st.markdown(f'<div class="ua-datesep"><span>{msg_date}</span></div>',
                                unsafe_allow_html=True)
                    prev_date = msg_date

                # Quién responde (si es admin muestra "Administración")
                if is_mine:
                    sender_label = ''
                elif msg['sender_role'] == 'admin':
                    sender_label = '<div style="font-size:.72rem;color:#818CF8;margin-bottom:3px;font-weight:600">🏛️ Administración</div>'
                else:
                    sender_label = f'<div style="font-size:.72rem;color:#60A5FA;margin-bottom:3px;font-weight:600">{_hl.escape(msg["sender_name"])}</div>'

                att_html = ''
                if msg['has_attachment']:
                    try:
                        for f in conn.execute(
                                f"SELECT * FROM {table_files} WHERE message_id=?",
                                (msg['id'],)).fetchall():
                            ftype = (f['file_type'] or '').lower()
                            fname = _hl.escape(f['file_name'])
                            fsize = f"{f['file_size']//1024} KB" if f['file_size'] > 1024 else f"{f['file_size']} B"
                            if ftype.startswith('image/'):
                                fb64 = base64.b64encode(f['file_content']).decode()
                                att_html += f'<br><img src="data:{ftype};base64,{fb64}" style="max-width:200px;max-height:150px;border-radius:8px;margin-top:4px">'
                            else:
                                icon = '📕' if 'pdf' in ftype else ('📦' if 'zip' in ftype else ('🎬' if 'video' in ftype else '📄'))
                                att_html += f'<div style="display:flex;gap:6px;align-items:center;margin-top:5px;padding:5px 8px;background:rgba(255,255,255,.06);border-radius:6px"><span>{icon}</span><div><div style="font-size:.78rem">{fname}</div><div style="font-size:.65rem;opacity:.55">{fsize}</div></div></div>'
                    except Exception:
                        pass

                safe_txt = _hl.escape(msg['message_text']) if msg['message_text'] else ''
                tick = ' <span style="font-size:.6rem;opacity:.4">✓✓</span>' if is_mine else ''
                cls  = 'ua-out' if is_mine else 'ua-in'

                st.markdown(
                    f'<div class="{cls}"><div>'
                    f'{sender_label}{safe_txt}{att_html}'
                    f'<div class="ua-time">{msg_time}{tick}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True)

    # Input
    if counter_key not in st.session_state:
        st.session_state[counter_key] = 0

    ci, cf, cs = st.columns([5, 2, 1])
    with ci:
        txt = st.text_area("Mensaje:", placeholder="Escribe tu mensaje a la administración...",
            height=120,
            key=f"ua_txt_{counter_key}_{st.session_state[counter_key]}",
            label_visibility="collapsed")
    with cf:
        ufile = st.file_uploader("📎", type=None,
            key=f"ua_file_{counter_key}_{st.session_state[counter_key]}",
            label_visibility="collapsed")
    with cs:
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        if st.button("➤", key=f"ua_send_{counter_key}", type="primary", use_container_width=True):
            if txt.strip() or ufile:
                try:
                    cur = conn.execute(
                        f"INSERT INTO {table_msg} "
                        f"(sender_id, {user_field}, message_text, has_attachment, is_read_by) "
                        f"VALUES (?,?,?,?,?)",
                        (u['username'], u['username'], txt.strip(),
                         1 if ufile else 0, _json.dumps([u['username']])))
                    if ufile:
                        conn.execute(
                            f"INSERT INTO {table_files} "
                            f"(message_id,file_name,file_type,file_size,file_content) VALUES (?,?,?,?,?)",
                            (cur.lastrowid, ufile.name,
                             ufile.type or 'application/octet-stream',
                             ufile.size, ufile.getvalue()))
                    conn.commit()
                    st.session_state[counter_key] += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Escribe algo o adjunta un archivo")


def view_teacher_admin_chat(conn):
    """Chat del docente con la administración."""
    u = st.session_state.user
    _render_user_admin_chat(
        conn, u,
        table_msg='admin_teacher_messages',
        table_files='admin_teacher_files',
        user_field='teacher_id',
        counter_key='tc_user_counter',
        back_page='dashboard'
    )


def view_student_admin_chat(conn):
    """Chat del estudiante con la administración."""
    u = st.session_state.user
    _render_user_admin_chat(
        conn, u,
        table_msg='admin_student_messages',
        table_files='admin_student_files',
        user_field='student_id',
        counter_key='stu_adm_counter',
        back_page='dashboard'
    )


def _render_admin_reply_chat(conn, u, table_msg, table_files, user_field, user_role_label, counter_key):
    """Panel admin: lista de usuarios con mensajes + conversación para responder."""
    import html as _hl
    import json as _json

    role_filter = 'teacher' if user_field == 'teacher_id' else 'student'
    icon_role   = '👨‍🏫' if role_filter == 'teacher' else '🎓'

    # Cargar usuarios que tienen conversación
    try:
        all_users = [dict(r) for r in conn.execute(
            "SELECT DISTINCT u.username, u.full_name, u.avatar "
            f"FROM {table_msg} m JOIN users u ON m.{user_field} = u.username "
            "ORDER BY u.full_name").fetchall()]
    except Exception:
        all_users = []

    palette = ['#0EA5E9','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899']
    for i, usr in enumerate(all_users):
        usr['color']   = palette[i % len(palette)]
        usr['initial'] = (usr['full_name'] or '?')[0].upper()
        try:
            last = conn.execute(
                f"SELECT message_text, sent_at FROM {table_msg} "
                f"WHERE {user_field}=? ORDER BY sent_at DESC LIMIT 1",
                (usr['username'],)).fetchone()
            usr['preview']   = (last['message_text'][:36]+'...' if last and len(last['message_text'])>36
                                 else (last['message_text'] if last else 'Sin mensajes'))
            usr['last_time'] = last['sent_at'][11:16] if last and last['sent_at'] else ''
            # Contar no leídos para este admin
            unread_count = conn.execute(
                f"SELECT COUNT(*) FROM {table_msg} "
                f"WHERE {user_field}=? AND sender_id != ? AND (is_read_by NOT LIKE ?)",
                (usr['username'], u['username'], f'%"{u["username"]}"%')).fetchone()[0]
            usr['unread'] = unread_count
        except Exception:
            usr['preview'] = 'Sin mensajes'; usr['last_time'] = ''; usr['unread'] = 0

    target_id = st.session_state.get(f'admin_reply_target_{user_field}')
    col_list, col_chat = st.columns([1, 2])

    with col_list:
        st.markdown(f"### {icon_role} {user_role_label}")
        if not all_users:
            st.markdown("""
            <div style="text-align:center;padding:40px 16px;color:#475569;">
                <div style="font-size:2.5rem;margin-bottom:10px">📭</div>
                <div style="font-size:.85rem;font-weight:500">Sin conversaciones</div>
                <div style="font-size:.75rem;margin-top:4px;color:#334155">
                    Aparecerán aquí cuando alguien escriba
                </div>
            </div>""", unsafe_allow_html=True)
        for usr in all_users:
            is_sel = target_id == usr['username']
            if usr['avatar']:
                b64 = base64.b64encode(usr['avatar']).decode()
                av_html = f'<img src="data:image/png;base64,{b64}" style="width:44px;height:44px;border-radius:50%;object-fit:cover;margin-top:4px;">'
            else:
                av_html = f'<div style="width:44px;height:44px;border-radius:50%;background:{usr["color"]};display:flex;align-items:center;justify-content:center;font-size:1.1rem;font-weight:700;color:#fff;margin-top:4px;">{usr["initial"]}</div>'

            ca, cb = st.columns([1, 4])
            with ca:
                st.markdown(av_html, unsafe_allow_html=True)
            with cb:
                name_e    = _hl.escape(usr['full_name'])
                preview_e = _hl.escape(usr['preview'])
                time_e    = _hl.escape(usr['last_time'])
                st.markdown(
                    f'<div style="padding:4px 0">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<b style="font-size:.9rem;color:#F8FAFC">{name_e}</b>'
                    f'<span style="font-size:.68rem;color:#475569">{time_e}</span>'
                    f'</div>'
                    f'<div style="font-size:.76rem;color:#64748B;margin-top:2px">{preview_e}</div>'
                    f'</div>',
                    unsafe_allow_html=True)

            bc1, bc2 = st.columns([3, 1])
            with bc1:
                if st.button("✓ Abierto" if is_sel else "Abrir",
                             key=f"ar_{user_field}_{usr['username']}",
                             use_container_width=True,
                             type="primary" if is_sel else "secondary"):
                    st.session_state[f'admin_reply_target_{user_field}'] = usr['username']
                    st.rerun()
            with bc2:
                if usr['unread'] > 0:
                    st.markdown(
                        f'<div style="background:#818CF8;color:#fff;font-size:.7rem;'
                        f'font-weight:700;padding:4px 8px;border-radius:12px;'
                        f'text-align:center;margin-top:6px">{usr["unread"]}</div>',
                        unsafe_allow_html=True)

            st.markdown('<hr style="margin:6px 0;border-color:rgba(255,255,255,.05)">', unsafe_allow_html=True)

    with col_chat:
        if not target_id:
            st.markdown(
                f'<div style="text-align:center;padding:100px 20px;color:#475569;">'
                f'<div style="font-size:3rem;margin-bottom:12px">{icon_role}</div>'
                f'<div style="font-size:.95rem;color:#64748B">Selecciona un {user_role_label[:-1].lower()}</div>'
                f'</div>', unsafe_allow_html=True)
            return

        target = next((usr for usr in all_users if usr['username'] == target_id), None)
        if not target:
            st.error("Usuario no encontrado"); return

        # Marcar como leídos
        try:
            for m in conn.execute(
                    f"SELECT id, is_read_by FROM {table_msg} "
                    f"WHERE {user_field}=? AND sender_id != ?",
                    (target_id, u['username'])).fetchall():
                leidos = _json.loads(m['is_read_by'] or '[]')
                if u['username'] not in leidos:
                    leidos.append(u['username'])
                    conn.execute(f"UPDATE {table_msg} SET is_read_by=? WHERE id=?",
                                 (_json.dumps(leidos), m['id']))
            conn.commit()
        except Exception:
            pass

        # Topbar
        if target['avatar']:
            av_b64 = base64.b64encode(target['avatar']).decode()
            av_top = f'<img src="data:image/png;base64,{av_b64}" style="width:38px;height:38px;border-radius:50%;object-fit:cover;">'
        else:
            av_top = f'<div style="width:38px;height:38px;border-radius:50%;background:{target["color"]};display:flex;align-items:center;justify-content:center;font-size:1rem;font-weight:700;color:#fff;">{target["initial"]}</div>'

        name_e = _hl.escape(target['full_name'])
        tc1, tc2, tc3 = st.columns([7, 1, 1])
        with tc1:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 16px;'
                f'background:rgba(15,22,33,.95);border-radius:12px 12px 0 0;'
                f'border:1px solid rgba(255,255,255,.07);border-bottom:none;">'
                f'{av_top}'
                f'<div><div style="font-weight:700;color:#F8FAFC;font-size:.92rem">{name_e}</div>'
                f'<div style="font-size:.70rem;color:#0EA5E9">{icon_role} {user_role_label[:-1]}</div></div>'
                f'<div style="margin-left:auto;font-size:.70rem;color:#475569;background:rgba(255,255,255,.04);'
                f'padding:3px 8px;border-radius:8px;">Visible para todos los admins 👁️</div>'
                f'</div>',
                unsafe_allow_html=True)
        with tc2:
            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
            if st.button("🗑️", key=f"ar_del_{user_field}", help="Eliminar este chat"):
                st.session_state[f'ar_confirm_del_{user_field}'] = True
        with tc3:
            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
            if st.button("✕", key=f"ar_close_{user_field}", help="Cerrar"):
                st.session_state.pop(f'admin_reply_target_{user_field}', None)
                st.rerun()

        # Confirmar eliminación
        if st.session_state.get(f'ar_confirm_del_{user_field}'):
            st.warning(f"¿Eliminar todo el chat con **{target['full_name']}**? No se puede deshacer.")
            cd1, cd2 = st.columns(2)
            if cd1.button("✅ Sí, eliminar", key=f"ar_del_yes_{user_field}", type="primary"):
                try:
                    msg_ids = [r[0] for r in conn.execute(
                        f"SELECT id FROM {table_msg} WHERE {user_field}=?", (target_id,)).fetchall()]
                    for mid in msg_ids:
                        conn.execute(f"DELETE FROM {table_files} WHERE message_id=?", (mid,))
                    conn.execute(f"DELETE FROM {table_msg} WHERE {user_field}=?", (target_id,))
                    conn.commit()
                    st.session_state.pop(f'ar_confirm_del_{user_field}', None)
                    st.session_state.pop(f'admin_reply_target_{user_field}', None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            if cd2.button("❌ Cancelar", key=f"ar_del_no_{user_field}"):
                st.session_state.pop(f'ar_confirm_del_{user_field}', None)
                st.rerun()

        # Mensajes
        try:
            msgs = [dict(r) for r in conn.execute(
                f"SELECT m.id, m.sender_id, m.message_text, m.sent_at, m.has_attachment, "
                f"u2.first_name || ' ' || u2.last_name AS sender_name, u2.role AS sender_role "
                f"FROM {table_msg} m JOIN users u2 ON m.sender_id = u2.username "
                f"WHERE m.{user_field}=? ORDER BY m.sent_at ASC",
                (target_id,)).fetchall()]
        except Exception as e:
            msgs = []; st.error(f"Error: {e}")

        with st.container(height=360):
            if not msgs:
                st.markdown(
                    f'<div style="text-align:center;padding:60px;color:#475569;">'
                    f'<div style="font-size:2rem;margin-bottom:8px">💬</div>'
                    f'<div>Inicia la conversación con <b style="color:#60A5FA">{name_e}</b></div>'
                    f'</div>', unsafe_allow_html=True)
            else:
                prev_date = None
                for msg in msgs:
                    is_mine = msg['sender_id'] == u['username']
                    try:
                        dt = datetime.strptime(msg['sent_at'], '%Y-%m-%d %H:%M:%S')
                        msg_date = dt.strftime('%d/%m/%Y')
                        msg_time = dt.strftime('%H:%M')
                    except Exception:
                        msg_date = ''; msg_time = ''
                    if msg_date and msg_date != prev_date:
                        st.markdown(f'<div class="ua-datesep"><span>{msg_date}</span></div>', unsafe_allow_html=True)
                        prev_date = msg_date

                    if is_mine:
                        sender_label = ''
                    elif msg['sender_role'] == 'admin':
                        sender_label = f'<div style="font-size:.72rem;color:#818CF8;margin-bottom:3px;font-weight:600">🛡️ {_hl.escape(msg["sender_name"])}</div>'
                    else:
                        sender_label = f'<div style="font-size:.72rem;color:#60A5FA;margin-bottom:3px;font-weight:600">{_hl.escape(msg["sender_name"])}</div>'

                    att_html = ''
                    if msg['has_attachment']:
                        try:
                            for f in conn.execute(f"SELECT * FROM {table_files} WHERE message_id=?", (msg['id'],)).fetchall():
                                ftype = (f['file_type'] or '').lower()
                                fname = _hl.escape(f['file_name'])
                                fsize = f"{f['file_size']//1024} KB" if f['file_size'] > 1024 else f"{f['file_size']} B"
                                if ftype.startswith('image/'):
                                    fb64 = base64.b64encode(f['file_content']).decode()
                                    att_html += f'<br><img src="data:{ftype};base64,{fb64}" style="max-width:200px;max-height:150px;border-radius:8px;margin-top:4px">'
                                else:
                                    icon = '📕' if 'pdf' in ftype else ('📦' if 'zip' in ftype else '📄')
                                    att_html += f'<div style="display:flex;gap:6px;align-items:center;margin-top:5px;padding:5px 8px;background:rgba(255,255,255,.06);border-radius:6px"><span>{icon}</span><div><div style="font-size:.78rem">{fname}</div><div style="font-size:.65rem;opacity:.55">{fsize}</div></div></div>'
                        except Exception:
                            pass

                    safe_txt = _hl.escape(msg['message_text']) if msg['message_text'] else ''
                    tick = ' <span style="font-size:.6rem;opacity:.4">✓✓</span>' if is_mine else ''
                    cls  = 'ua-out' if is_mine else 'ua-in'
                    st.markdown(
                        f'<div class="{cls}"><div>{sender_label}{safe_txt}{att_html}'
                        f'<div class="ua-time">{msg_time}{tick}</div></div></div>',
                        unsafe_allow_html=True)

        # Input respuesta
        if counter_key not in st.session_state:
            st.session_state[counter_key] = 0

        ci, cf, cs = st.columns([5, 2, 1])
        with ci:
            rep_txt = st.text_area("", placeholder=f"Responde a {target['full_name']}...",
                height=120,
                key=f"ar_txt_{counter_key}_{st.session_state[counter_key]}",
                label_visibility="collapsed")
        with cf:
            rep_file = st.file_uploader("📎", type=None,
                key=f"ar_file_{counter_key}_{st.session_state[counter_key]}",
                label_visibility="collapsed")
        with cs:
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
            if st.button("➤", key=f"ar_send_{counter_key}", type="primary", use_container_width=True):
                if rep_txt.strip() or rep_file:
                    try:
                        cur = conn.execute(
                            f"INSERT INTO {table_msg} "
                            f"(sender_id, {user_field}, message_text, has_attachment, is_read_by) "
                            f"VALUES (?,?,?,?,?)",
                            (u['username'], target_id, rep_txt.strip(),
                             1 if rep_file else 0, _json.dumps([u['username']])))
                        if rep_file:
                            conn.execute(
                                f"INSERT INTO {table_files} "
                                f"(message_id,file_name,file_type,file_size,file_content) VALUES (?,?,?,?,?)",
                                (cur.lastrowid, rep_file.name,
                                 rep_file.type or 'application/octet-stream',
                                 rep_file.size, rep_file.getvalue()))
                        conn.commit()
                        st.session_state[counter_key] += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Escribe algo o adjunta un archivo")


def view_admin_teacher_chat(conn):
    """Panel admin: conversa con docentes."""
    u = st.session_state.user
    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("← Volver", key="atc_back"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
    with col_title:
        st.markdown("## 👨‍🏫 Chat con Docentes")
        st.caption("Todos los administradores pueden ver y responder estas conversaciones")
    st.divider()
    _render_admin_reply_chat(conn, u,
        table_msg='admin_teacher_messages',
        table_files='admin_teacher_files',
        user_field='teacher_id',
        user_role_label='Docentes',
        counter_key='atc_counter')


def view_admin_student_chat(conn):
    """Panel admin: conversa con estudiantes."""
    u = st.session_state.user
    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("← Volver", key="asc_back"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
    with col_title:
        st.markdown("## 🎓 Chat con Estudiantes")
        st.caption("Todos los administradores pueden ver y responder estas conversaciones")
    st.divider()
    _render_admin_reply_chat(conn, u,
        table_msg='admin_student_messages',
        table_files='admin_student_files',
        user_field='student_id',
        user_role_label='Estudiantes',
        counter_key='asc_counter')
