"""
Aplicación principal de plataforma educativa con IA
Versión Final: Fix Perfil Propio vs Perfil Docente
"""
import streamlit as st
import pandas as pd
import base64
import time
import os
import json
from datetime import datetime
import traceback

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA (PRIMERO)
# ==========================================
st.set_page_config(
    page_title="Plataforma Educativa IA",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'About': 'Plataforma Educativa v2.0 - IA Integrada'
    }
)

# ==========================================
# 2. IMPORTS
# ==========================================
try:
    from database import db_manager, init_db, hash_password, verify_password, generate_user_code
    from styles import inject_custom_css
    from utils_ai import ai_manager, configure_ai
    from utils_security import security
    from utils_notifications import notification_manager
    from views_admin import view_admin, view_admin_chat, view_admin_dm, view_admin_teacher_chat
    from views_teacher import view_teacher
    from views_student import view_student
except ImportError as e:
    st.error(f"Error crítico importando módulos: {e}")
    st.stop()

# Configuración de entorno
os.environ['STREAMLIT_SERVER_ENABLE_CORS'] = 'false'
os.environ['STREAMLIT_SERVER_ENABLE_XSRF'] = 'true'

# ==========================================
# 3. GESTIÓN DE ESTADO
# ==========================================

def init_session_state():
    """Inicializa variables de sesión"""
    defaults = {
        'logged_in': False,
        'user': None,
        'theme': 'dark',
        'current_page': 'dashboard',
        'view_mode': 'dashboard',
        'active_course': None,
        'profile_target': None,
        'ai_available': False,
        'last_activity': datetime.now(),
        'login_attempts': 0,
        'show_password_reset': False,
        'edit_mode': False,
        'show_notifications': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Inicializar DB
try:
    conn = init_db()
except Exception as e:
    st.error(f"Error BD: {e}")
    st.stop()

# Inicializar IA
try:
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if api_key:
        configure_ai(api_key)
        st.session_state.ai_available = True
except:
    st.session_state.ai_available = False

inject_custom_css()

# ==========================================
# 4. FUNCIONES DE LOGIN Y SESIÓN
# ==========================================

def check_session_timeout():
    """Cierra sesión tras 2 horas de inactividad (simplificado)"""
    if not st.session_state.logged_in: return
    
    elapsed = datetime.now() - st.session_state.last_activity
    if elapsed.total_seconds() > 7200: # 120 minutos
        st.session_state.logged_in = False
        st.session_state.user = None
        st.warning("⚠️ Sesión expirada por inactividad")
        st.rerun()

def update_activity():
    st.session_state.last_activity = datetime.now()

def perform_logout():
    if st.session_state.user:
        db_manager.log_activity(st.session_state.user['username'], 'logout')
    
    # Reset completo
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.current_page = 'dashboard'
    st.session_state.profile_target = None # Limpiar target
    st.session_state.show_notifications = False
    
    keys_del = ['active_course', 'exam_session', 'edit_mode',
                'current_challenge', 'challenge_lang', 'challenge_diff',
                'gym_evaluation_result', 'gym_show_solution',
                'gym_solution', 'gym_approach']
    for k in keys_del:
        if k in st.session_state: del st.session_state[k]
    
    # Limpiar cualquier clave de recomendaciones cacheadas
    rec_keys = [k for k in st.session_state.keys() if k.startswith('rec_') or k.startswith('load_rec_')]
    for k in rec_keys:
        del st.session_state[k]
    
    st.rerun()

def process_login_logic(username, password):
    """
    Valida credenciales.
    IMPORTANTE: NO hace st.rerun() aquí para evitar error de formulario.
    Retorna True si es exitoso.
    """
    if not username or not password:
        st.error("⚠️ Complete todos los campos")
        return False
    
    # Validar tipos
    if not isinstance(username, str) or not isinstance(password, str):
        st.error("⚠️ Datos inválidos")
        return False
    
    # Seguridad
    ci = security.get_client_info()
    ip = ci.get('ip', 'unknown')
    
    ok, msg = security.check_brute_force(username, ip)
    if not ok:
        st.error(msg)
        return False

    # Buscar usuario
    try:
        u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    except Exception as e:
        st.error(f"❌ Error de base de datos: {str(e)}")
        return False
    
    if not u:
        st.error("❌ Usuario no encontrado")
        db_manager.log_activity(username, 'login_failed_user', ip=ip)
        return False

    # Verificar Pass
    if verify_password(password, u['password_hash']):
        # ÉXITO: Guardar en sesión
        st.session_state.logged_in = True
        st.session_state.user = dict(u)
        st.session_state.theme = u['theme']
        st.session_state.last_activity = datetime.now()
        
        # Actualizar DB
        try:
            conn.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE username=?", (username,))
            conn.commit()
            db_manager.log_activity(username, 'login_success', ip=ip)
        except Exception as e:
            print(f"Error actualizando último login: {e}")
        
        # ENGAGEMENT: Inicializar sistema de engagement para estudiantes
        if u['role'] == 'student':
            try:
                from engagement import StreakManager, PointsManager
                # Actualizar racha
                StreakManager.update_streak(username)
                # Inicializar puntos si no existen
                PointsManager.initialize_user_points(username)
            except Exception as e:
                print(f"Error inicializando engagement: {e}")
        
        # Verificar si es el primer login (crear notificaciones de bienvenida)
        try:
            login_count = conn.execute(
                "SELECT COUNT(*) FROM activity_logs WHERE user_id=? AND action='login_success'", 
                (username,)
            ).fetchone()[0]
            
            if login_count <= 1:  # Primer o segundo login
                # Crear notificaciones de bienvenida con todas las funciones
                notification_manager.create_welcome_notifications(username, u['role'])
                
                # Notificaciones adicionales específicas por rol
                if u['role'] == 'teacher':
                    notification_manager.create_notification(
                        username, "🎓 Bienvenido Profesor", 
                        f"¡Hola {u['full_name']}! Tu panel docente está listo. Explora las herramientas de enseñanza disponibles.", 
                        "welcome"
                    )
                elif u['role'] == 'admin':
                    notification_manager.create_notification(
                        username, "⚙️ Bienvenido Administrador", 
                        f"¡Hola {u['full_name']}! Tienes acceso completo al sistema. Revisa las funciones de administración.", 
                        "welcome"
                    )
            else:
                # Notificación simple de inicio de sesión
                notification_manager.create_notification(
                    username, "🔐 Inicio de Sesión", f"Bienvenido de vuelta, {u['full_name']}", "success"
                )
        except Exception as e:
            print(f"Error creando notificaciones de bienvenida: {e}")
        
        return True
    else:
        st.error("❌ Contraseña incorrecta")
        db_manager.log_activity(username, 'login_failed_pwd', ip=ip)
        return False

def get_logo_config():
    """Obtiene la configuración del logo desde la base de datos"""
    try:
        # Intentar obtener de system_settings primero
        logo_data = conn.execute(
            "SELECT value FROM system_settings WHERE key = 'logo_url'"
        ).fetchone()
        
        if not logo_data:
            # Intentar de settings
            logo_data = conn.execute(
                "SELECT value FROM settings WHERE key = 'logo_url'"
            ).fetchone()
        
        if logo_data and logo_data[0]:
            return logo_data[0]
        
        # Si no hay logo configurado, retornar None
        return None
    except:
        return None

def get_background_config():
    """Obtiene la configuración del fondo del login desde la base de datos"""
    try:
        # Intentar obtener de system_settings primero
        bg_data = conn.execute(
            "SELECT value FROM system_settings WHERE key = 'login_background_url'"
        ).fetchone()
        
        if not bg_data:
            # Intentar de settings
            bg_data = conn.execute(
                "SELECT value FROM settings WHERE key = 'login_background_url'"
            ).fetchone()
        
        if bg_data and bg_data[0]:
            return bg_data[0]
        
        # Si no hay fondo configurado, retornar None (usará gradiente por defecto)
        return None
    except:
        return None

def render_register_form():
    """Formulario de auto-registro para estudiantes gratuitos"""
    st.markdown("""
    <style>
        /* Separador visual del formulario de registro */
        .register-header {
            text-align: center;
            padding: 18px 0 10px 0;
        }
    </style>
    <div style="
        border-top: 1px solid rgba(192,132,252,0.3);
        margin-top: 8px;
        padding-top: 20px;
        text-align: center;
    ">
        <div style="font-size: 28px; margin-bottom: 6px;">✨</div>
        <h4 style="color: #c084fc; margin: 0 0 4px 0; font-size: 16px; font-weight: 700; letter-spacing: 0.3px;">
            Crear cuenta gratuita
        </h4>
        <p style="color: #6e7681; font-size: 12px; margin: 0 0 18px 0;">
            Tutor IA · Gimnasio de Código · Academia Personal IA · y más
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("register_form", clear_on_submit=False):
        reg_first = st.text_input("Nombre", placeholder="Tu nombre")
        reg_last  = st.text_input("Apellido", placeholder="Tu apellido")
        reg_email = st.text_input("Correo electrónico", placeholder="ejemplo@correo.com")
        reg_user  = st.text_input("Usuario", placeholder="Elige un nombre de usuario único")
        reg_pwd   = st.text_input("Contraseña", type="password", placeholder="Mínimo 6 caracteres")
        reg_pwd2  = st.text_input("Confirmar contraseña", type="password", placeholder="Repite la contraseña")

        submitted = st.form_submit_button("🚀 Crear cuenta", type="primary", use_container_width=True)
        cancelled = st.form_submit_button("Cancelar", use_container_width=True)

        if cancelled:
            st.session_state.show_register_form = False
            st.rerun()

        if submitted:
            import re
            if not all([reg_first, reg_last, reg_email, reg_user, reg_pwd, reg_pwd2]):
                st.error("⚠️ Completa todos los campos.")
            elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', reg_email):
                st.error("⚠️ Ingresa un correo electrónico válido.")
            elif len(reg_user) < 3:
                st.error("⚠️ El usuario debe tener al menos 3 caracteres.")
            elif len(reg_pwd) < 6:
                st.error("⚠️ La contraseña debe tener al menos 6 caracteres.")
            elif reg_pwd != reg_pwd2:
                st.error("⚠️ Las contraseñas no coinciden.")
            else:
                existing_user = conn.execute(
                    "SELECT 1 FROM users WHERE username = ?", (reg_user,)
                ).fetchone()
                existing_email = conn.execute(
                    "SELECT 1 FROM users WHERE email = ?", (reg_email.strip().lower(),)
                ).fetchone()

                if existing_user:
                    st.error("⚠️ Ese nombre de usuario ya está en uso. Elige otro.")
                elif existing_email:
                    st.error("⚠️ Ese correo ya está registrado. Usa otro o inicia sesión.")
                else:
                    try:
                        pwd_hash = hash_password(reg_pwd)
                        user_code = generate_user_code('student')
                        full_name = f"{reg_first.strip()} {reg_last.strip()}"
                        conn.execute("""
                            INSERT INTO users
                            (username, password_hash, role, first_name, last_name, full_name, user_code, email, account_type)
                            VALUES (?, ?, 'student', ?, ?, ?, ?, ?, 'free')
                        """, (reg_user, pwd_hash, reg_first.strip(), reg_last.strip(), full_name, user_code, reg_email.strip().lower()))
                        conn.commit()
                        # Auto-login inmediato
                        new_user = conn.execute("SELECT * FROM users WHERE username=?", (reg_user,)).fetchone()
                        st.session_state.logged_in = True
                        st.session_state.user = dict(new_user)
                        st.session_state.theme = new_user['theme']
                        st.session_state.last_activity = datetime.now()
                        st.session_state.show_register_form = False
                        conn.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE username=?", (reg_user,))
                        conn.commit()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al crear la cuenta: {e}")


def render_login_screen():
    """Pantalla de Login elegante con logo y fondo personalizables - Estilo imagen de referencia"""
    
    # Obtener logo y fondo configurados
    logo_url = get_logo_config()
    background_url = get_background_config()
    
    # Determinar el estilo del fondo
    if background_url and len(background_url) > 0:
        # Validar que sea una URL de imagen válida
        valid_image_url = False
        
        # Si es una URL normal, verificar que termine en extensión de imagen
        if background_url.startswith('http'):
            valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
            if any(background_url.lower().endswith(ext) for ext in valid_extensions):
                valid_image_url = True
                background_style = f"""
                    background-image: url('{background_url}');
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                """
        # Si es base64, es válido
        elif background_url.startswith('data:image'):
            valid_image_url = True
            background_style = f"""
                background-image: url("{background_url}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            """
        
        # Si no es válida, usar gradiente
        if not valid_image_url:
            background_style = "background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e22ce 100%);"
    else:
        # Fondo azul por defecto (como en la imagen de referencia)
        background_style = "background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e22ce 100%);"
    
    st.markdown(f"""
    <style>
        /* Ocultar elementos de Streamlit */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        [data-testid="stSidebar"] {{display: none;}}
        
        /* Fondo personalizable */
        .stApp {{
            {background_style}
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding-top: 80px !important;
        }}
        
        /* Contenedor principal - MÁS ANCHO */
        .main .block-container {{
            max-width: 650px !important;
            padding: 2rem 1rem !important;
            margin-top: -40px !important;
        }}
        
        /* Contenedor del formulario - MÁS ANCHO Y COMPACTO */
        [data-testid="stVerticalBlock"] {{
            background: rgba(40, 40, 40, 0.98) !important;
            border-radius: 8px !important;
            padding: 35px 50px !important;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6) !important;
            max-width: 580px;
            margin: 0 auto;
        }}
        
        /* Inputs - ESTILO OSCURO Y COMPACTO */
        .stTextInput input {{
            background-color: rgba(30, 30, 30, 0.95) !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            color: #ffffff !important;
            border-radius: 4px !important;
            padding: 8px 12px !important;
            font-size: 14px !important;
        }}
        
        .stTextInput input::placeholder {{
            color: rgba(255, 255, 255, 0.4) !important;
        }}
        
        .stTextInput input:focus {{
            border-color: #4a8fd8 !important;
            box-shadow: 0 0 0 1px #4a8fd8 !important;
        }}
        
        .stTextInput label {{
            color: #d0d0d0 !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            margin-bottom: 4px !important;
        }}
        
        .stTextInput {{
            margin-bottom: 12px !important;
        }}
        
        /* Botón principal - AZUL DESTACADO Y COMPACTO */
        .stButton button[kind="primary"] {{
            background: linear-gradient(135deg, #4a8fd8 0%, #3a7fc8 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 4px !important;
            padding: 9px 20px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            width: 100% !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            margin-top: 8px !important;
        }}
        
        .stButton button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #3a7fc8 0%, #2a6fb8 100%) !important;
            box-shadow: 0 4px 12px rgba(74, 143, 216, 0.4) !important;
        }}
        
        /* Botones secundarios - MÁS PEQUEÑOS */
        .stButton button:not([kind="primary"]) {{
            background: transparent !important;
            color: #8b949e !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 4px !important;
            padding: 6px 12px !important;
            font-size: 12px !important;
        }}
        
        .stButton button:not([kind="primary"]):hover {{
            background: rgba(255, 255, 255, 0.05) !important;
            border-color: rgba(255, 255, 255, 0.2) !important;
        }}
        
        /* Botón de registro - estilo especial */
        div[data-testid="stButton"]:has(button[key="btn_open_register"]) button,
        button[key="btn_open_register"] {{
            background: linear-gradient(135deg, rgba(126,34,206,0.25) 0%, rgba(74,143,216,0.25) 100%) !important;
            color: #c084fc !important;
            border: 1px solid rgba(192, 132, 252, 0.5) !important;
            border-radius: 6px !important;
            padding: 10px 20px !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            letter-spacing: 0.3px !important;
            transition: all 0.2s ease !important;
        }}
        
        div[data-testid="stButton"]:has(button[key="btn_open_register"]) button:hover,
        button[key="btn_open_register"]:hover {{
            background: linear-gradient(135deg, rgba(126,34,206,0.45) 0%, rgba(74,143,216,0.45) 100%) !important;
            border-color: rgba(192, 132, 252, 0.8) !important;
            box-shadow: 0 4px 15px rgba(126, 34, 206, 0.3) !important;
        }}
        
        /* Botones del formulario de registro - tamaño correcto */
        [data-testid="stForm"] .stFormSubmitButton button {{
            width: 100% !important;
            padding: 10px 20px !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
            white-space: nowrap !important;
            height: auto !important;
            min-height: 42px !important;
        }}
        
        /* Cancelar - estilo sutil */
        [data-testid="stForm"] .stFormSubmitButton:last-child button {{
            background: transparent !important;
            color: #6e7681 !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            font-weight: 400 !important;
        }}
        [data-testid="stForm"] .stFormSubmitButton:last-child button:hover {{
            background: rgba(255,255,255,0.05) !important;
            color: #8b949e !important;
        }}
        
        /* Divider */
        hr {{
            border-color: rgba(255, 255, 255, 0.1) !important;
            margin: 15px 0 12px 0 !important;
        }}
        
        /* Ocultar el borde del container */
        [data-testid="stVerticalBlock"] > div {{
            border: none !important;
        }}
    </style>
    """, unsafe_allow_html=True)
    
    # Logo centrado - UN POCO MÁS GRANDE
    if logo_url:
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 18px;">
            <img src="{logo_url}" alt="Logo" style="max-width: 130px; max-height: 130px; object-fit: contain;">
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; font-size: 70px; margin-bottom: 18px;">🎓</div>
        """, unsafe_allow_html=True)
    
    # Título - MÁS COMPACTO
    st.markdown('<h2 style="text-align: center; color: #ffffff; font-size: 19px; font-weight: 600; margin-bottom: 22px; margin-top: 0;">Portal del Estudiante</h2>', unsafe_allow_html=True)
    
    # Formulario de login
    with st.form("login_form"):
        user = st.text_input(
            "Carnet",
            placeholder="Ingresa tu usuario",
            label_visibility="visible"
        )
        
        pwd = st.text_input(
            "Contraseña",
            type="password",
            placeholder="Ingresa tu contraseña",
            label_visibility="visible"
        )
        
        sub = st.form_submit_button(
            "🔐 INICIAR SESIÓN",
            type="primary",
            use_container_width=True
        )
        
        if sub:
            if process_login_logic(user, pwd):
                st.success("✅ Acceso correcto. Cargando...")
                time.sleep(0.5) 
                st.rerun()
    
    # Divider - MÁS COMPACTO
    st.markdown('<hr style="margin: 15px 0 12px 0;">', unsafe_allow_html=True)
    
    # Botones de ayuda - MÁS COMPACTOS
    col1, col2 = st.columns(2)
    with col1:
        if st.button("❓ Ayuda", use_container_width=True):
            st.info("💡 Contacta al administrador para obtener tus credenciales.")
    
    with col2:
        if st.button("🔑 Recuperar", use_container_width=True):
            st.info("📧 admin@plataforma.edu")
    
    # Botón de registro
    st.markdown('<hr style="margin: 12px 0;">', unsafe_allow_html=True)
    st.markdown("""
    <style>
        div[data-testid="stButton"]:has(button[kind="secondary"]#reg_btn) button {
            width: 100% !important;
        }
        .register-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }
    </style>
    <p style="text-align: center; color: #8b949e; font-size: 13px; margin: 0 0 10px 0;">
        ¿No tienes cuenta? Accede gratis a todas las herramientas IA
    </p>
    """, unsafe_allow_html=True)
    if st.button("✨ Regístrate gratis", use_container_width=True, key="btn_open_register"):
        st.session_state.show_register_form = True
    
    # Formulario de registro (se muestra cuando se presiona el botón)
    if st.session_state.get('show_register_form', False):
        render_register_form()
    
    # Footer compacto
    st.markdown("""
    <div style="text-align: center; color: #6e7681; font-size: 11px; margin-top: 25px;">
        <p style="margin: 0;">© 2026 Plataforma Educativa IA</p>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 5. VISTAS COMUNES (Perfil, Notificaciones)
# ==========================================

def view_profile():
    """Vista de perfil con modo lectura/edición y racha"""
    
    # Inicializar modo de edición
    if 'profile_edit_mode' not in st.session_state:
        st.session_state.profile_edit_mode = False
    
    u = st.session_state.user
    target = st.session_state.profile_target or u['username']
    
    # Obtener datos frescos
    data = conn.execute("SELECT * FROM users WHERE username=?", (target,)).fetchone()
    if not data:
        st.error("Usuario no encontrado")
        return

    is_me = (target == u['username'])
    
    # Botón volver y editar
    col_back, col_edit = st.columns([1, 4])
    with col_back:
        if st.button("← Volver al Dashboard"):
            st.session_state.current_page = 'dashboard'
            st.session_state.profile_target = None
            if 'profile_edit_mode' in st.session_state:
                del st.session_state.profile_edit_mode
            st.rerun()
    
    with col_edit:
        if is_me:  # Solo mostrar botón de editar si es el perfil propio
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
        st.title("👤 Mi Perfil" if is_me else f"👤 Perfil de {data['full_name']}")
        
        c1, c2 = st.columns([1, 3])
        with c1:
            # Verificar cosméticos activos
            cosmetic_frame = ""
            cosmetic_badges = []
            try:
                from engagement import ShopManager
                cosmetics = ShopManager.get_active_cosmetics(data['username'])
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
            
            if data['avatar']:
                b64 = base64.b64encode(data['avatar']).decode()
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
                
        with c2:
            st.subheader(data['full_name'])
            
            # Mostrar título especial si tiene uno equipado
            title_text = ""
            try:
                from engagement import ShopManager
                cosmetics = ShopManager.get_active_cosmetics(data['username'])
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
            
            role_label = {
                'student': '🎓 Estudiante',
                'teacher': '👨‍🏫 Docente',
                'admin': '🛡️ Administrador'
            }.get(data['role'], data['role'])
            
            caption_text = f"@{data['username']} | {role_label}"
            if title_text:
                st.markdown(f"{title_text}", unsafe_allow_html=True)
            st.caption(caption_text)
            
            if data['title']:
                st.markdown(f"**{data['title']}**")
            
            if data['bio']:
                st.markdown(f"*{data['bio']}*")
            else:
                st.caption("_Sin biografía_")
        
        st.markdown("---")
        
        # Información adicional
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📧 Información de Contacto")
            if data['email']:
                st.markdown(f"**Email:** {data['email']}")
            else:
                st.markdown(f"**Email:** {data['username']}")
        
        with col2:
            if data['role'] == 'student':
                st.markdown("### 📊 Estadísticas")
                # Estadísticas de estudiante
                enrolled_count = conn.execute(
                    "SELECT COUNT(*) FROM enrollments WHERE student_id = ?",
                    (data['username'],)
                ).fetchone()[0]
                
                st.metric("📚 Cursos Inscritos", enrolled_count)
        
        # Mostrar racha SIEMPRE para estudiantes (fuera de col2)
        if data['role'] == 'student':
            try:
                from engagement import StreakManager, PointsManager, ShopManager
                
                streak_info = StreakManager.get_streak_info(data['username'])
                points_info = PointsManager.get_user_points_info(data['username'])
                coins_info = PointsManager.get_user_coins(data['username'])
                
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
                    st.caption(f"Disponibles: {coins_info['total_coins']}")
                
                # Mostrar items activos canjeados
                active_items = ShopManager.get_user_active_items(data['username'])
                if active_items:
                    st.markdown("---")
                    st.markdown("### 🎁 Items Activos")
                    
                    # Agrupar por tipo
                    items_by_type = {}
                    for item in active_items:
                        item_type = item['type']
                        if item_type not in items_by_type:
                            items_by_type[item_type] = []
                        items_by_type[item_type].append(item)
                    
                    # Mostrar items por tipo
                    for item_type, items in items_by_type.items():
                        type_emoji = {
                            'content': '📚',
                            'certificate': '🎓',
                            'cosmetic': '🎨',
                            'feature': '⚡'
                        }.get(item_type, '🎁')
                        
                        st.markdown(f"**{type_emoji} {item_type.capitalize()}**")
                        for item in items:
                            st.markdown(f"- {item['name']}")
                
            except Exception as e:
                st.warning(f"No se pudo cargar información de engagement: {e}")
        
        # Estadísticas de profesor — ocultas (solo se muestran para estudiantes)
        # if data['role'] == 'teacher': ...
    
    # MODO EDICIÓN (solo para perfil propio)
    elif is_me:
        st.title("✏️ Editar Mi Perfil")
        
        with st.form("edit_profile_form"):
            # Foto de perfil
            st.subheader("📸 Foto de Perfil")
            col_current, col_upload = st.columns([1, 2])
            
            with col_current:
                st.markdown("**Foto actual:**")
                if data['avatar']:
                    b64 = base64.b64encode(data['avatar']).decode()
                    st.markdown(f'<img src="data:image/png;base64,{b64}" style="width:100px;border-radius:50%">', unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="width: 100px; height: 100px; border-radius: 50%; background: linear-gradient(135deg, #4a8fd8 0%, #7e22ce 100%); 
                                display: flex; align-items: center; justify-content: center; font-size: 50px;">
                        👤
                    </div>
                    """, unsafe_allow_html=True)
            
            with col_upload:
                av = st.file_uploader(
                    "Subir nueva foto",
                    type=['png', 'jpg', 'jpeg'],
                    help="Límite: 2MB | Formatos: PNG, JPG, JPEG"
                )
            
            st.markdown("---")
            
            # Información básica
            st.subheader("👤 Información Básica")
            
            fn = st.text_input("Nombre", data['first_name'])
            ln = st.text_input("Apellido", data['last_name'])
            email = st.text_input("Email", data['email'] or "")
            tit = st.text_input("Título / Carrera", data['title'] or "")
            bi = st.text_area("Biografía", data['bio'] or "", height=100)
            
            st.markdown("---")
            
            # Botones
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
            with col2:
                cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
            
            if submit:
                try:
                    new_blob = av.getvalue() if av else data['avatar']
                    new_full = f"{fn} {ln}"
                    
                    conn.execute("""
                        UPDATE users SET first_name=?, last_name=?, full_name=?, email=?, title=?, bio=?, avatar=?
                        WHERE username=?
                    """, (fn, ln, new_full, email, tit, bi, new_blob, target))
                    conn.commit()
                    
                    # Actualizar Sesión Local
                    st.session_state.user.update({
                        'first_name': fn, 'last_name': ln, 
                        'full_name': new_full, 'email': email, 
                        'title': tit, 'bio': bi, 'avatar': new_blob
                    })
                    st.success("✅ Perfil actualizado exitosamente")
                    st.session_state.profile_edit_mode = False
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar perfil: {e}")
            
            if cancel:
                st.session_state.profile_edit_mode = False
                st.rerun()
        
        # Gestión de Cosméticos (fuera del formulario)
        if data['role'] == 'student':
            try:
                from engagement import ShopManager
                
                st.markdown("---")
                st.subheader("🎨 Gestionar Cosméticos")
                st.caption("Equipa o desequipa los cosméticos que has canjeado")
                
                # Obtener cosméticos canjeados (owned)
                owned_cosmetics = ShopManager.get_user_active_items(data['username'], 'cosmetic')
                
                if not owned_cosmetics:
                    st.info("No tienes cosméticos canjeados. ¡Visita la tienda para conseguir algunos!")
                else:
                    # Agrupar por tipo
                    frames = [c for c in owned_cosmetics if 'frame' in c['key']]
                    badges = [c for c in owned_cosmetics if 'badge' in c['key']]
                    titles = [c for c in owned_cosmetics if 'title' in c['key']]
                    avatars = [c for c in owned_cosmetics if 'avatar' in c['key']]
                    
                    # Marcos
                    if frames:
                        st.markdown("**🖼️ Marcos de Avatar**")
                        for frame in frames:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(frame['name'])
                            with col2:
                                if st.button("❌ Desequipar", key=f"unequip_frame_{frame['key']}"):
                                    ShopManager.unequip_cosmetic(data['username'], frame['key'])
                                    st.success("Desequipado")
                                    time.sleep(0.5)
                                    st.rerun()
                    
                    # Avatares especiales
                    if avatars:
                        st.markdown("**👤 Avatares Especiales**")
                        for avatar in avatars:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(avatar['name'])
                            with col2:
                                if st.button("❌ Desequipar", key=f"unequip_avatar_{avatar['key']}"):
                                    ShopManager.unequip_cosmetic(data['username'], avatar['key'])
                                    st.success("Desequipado")
                                    time.sleep(0.5)
                                    st.rerun()
                    
                    # Badges
                    if badges:
                        st.markdown("**🏅 Badges**")
                        for badge in badges:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(badge['name'])
                            with col2:
                                if st.button("❌ Desequipar", key=f"unequip_badge_{badge['key']}"):
                                    ShopManager.unequip_cosmetic(data['username'], badge['key'])
                                    st.success("Desequipado")
                                    time.sleep(0.5)
                                    st.rerun()
                    
                    # Títulos
                    if titles:
                        st.markdown("**🏆 Títulos Especiales**")
                        for title in titles:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(title['name'])
                            with col2:
                                if st.button("❌ Desequipar", key=f"unequip_title_{title['key']}"):
                                    ShopManager.unequip_cosmetic(data['username'], title['key'])
                                    st.success("Desequipado")
                                    time.sleep(0.5)
                                    st.rerun()
                    
                    st.info("💡 Los cosméticos desequipados siguen siendo tuyos. Puedes volver a equiparlos cuando quieras desde la tienda.")
                    
            except Exception as e:
                st.error(f"Error cargando cosméticos: {e}")

def view_notifications_page(conn=None):
    st.title("🔔 Notificaciones")

    if conn is None:
        st.error("❌ Sin conexión a BD. Reinicia la aplicación.")
        if st.button("← Volver"):
            st.session_state.current_page = 'dashboard'
            st.rerun()
        return

    if st.button("← Volver"):
        st.session_state.current_page = 'dashboard'
        st.rerun()

    username = st.session_state.user['username']

    # Marcar todas como leídas automáticamente al entrar
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (username,))
        conn.commit()
    except Exception:
        pass

    try:
        ns_rows = conn.execute("""
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (username,)).fetchall()
        ns = [dict(r) for r in ns_rows]
    except Exception as e:
        st.error(f"Error cargando notificaciones: {e}")
        ns = []

    if not ns:
        st.info("Sin notificaciones")
    else:
        # Botón eliminar todas
        col_titulo, col_del = st.columns([6, 1])
        col_titulo.caption(f"{len(ns)} notificaciones")
        if col_del.button("🗑️ Eliminar todas", key="del_all_notifs", use_container_width=True):
            st.session_state['confirm_del_all_notifs_user'] = True

        if st.session_state.get('confirm_del_all_notifs_user'):
            st.warning("¿Eliminar todas tus notificaciones?")
            c1, c2 = st.columns(2)
            if c1.button("✅ Sí", key="confirm_del_notifs_yes", type="primary"):
                conn.execute("DELETE FROM notifications WHERE user_id=?", (username,))
                conn.commit()
                st.session_state.pop('confirm_del_all_notifs_user', None)
                st.rerun()
            if c2.button("❌ Cancelar", key="confirm_del_notifs_no"):
                st.session_state.pop('confirm_del_all_notifs_user', None)
                st.rerun()

        icon_map = {
            'welcome': '🎉', 'feature': '⭐', 'assignment': '📝',
            'exam': '✅', 'tip': '💡', 'achievement': '🏆',
            'update': '🆕', 'info': '🔔', 'success': '✅',
            'warning': '⚠️', 'error': '❌',
            'comunicado_oficial': '📢', 'aviso_urgente': '🚨',
            'recordatorio_academico': '📅', 'logistica_servicios': '📋',
            'actividades_eventos': '🎉', 'retroalimentacion': '📊',
        }
        for n in ns:
            icon = icon_map.get(n.get('type', 'info'), '🔔')
            try:
                fecha = datetime.strptime(n['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
            except Exception:
                fecha = n['created_at'] or ''
            col_msg, col_btn = st.columns([10, 1])
            with col_msg:
                st.markdown(f"""
                <div style="background:#1e1e1e;padding:12px;border-radius:8px;
                            margin-bottom:4px;border-left:3px solid #444;">
                    <div style="font-weight:bold;color:#fff;">{icon} {n['title']}</div>
                    <div style="color:#ccc;margin-top:4px;font-size:0.9em;">{n['message']}</div>
                    <div style="color:#888;margin-top:4px;font-size:0.75em;">📅 {fecha}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
                if st.button("✕", key=f"del_notif_{n['id']}", help="Eliminar esta notificación"):
                    conn.execute("DELETE FROM notifications WHERE id=? AND user_id=?", (n['id'], username))
                    conn.commit()
                    st.rerun()

# ==========================================
# 6. SIDEBAR COMPLETO
# ==========================================

def render_sidebar():
    u = st.session_state.user
    # conn es la variable global del módulo main.py, inicializada en el startup
    with st.sidebar:
        # Mostrar foto de perfil
        if u.get('avatar'):
            # Si tiene avatar, mostrarlo
            import base64
            b64 = base64.b64encode(u['avatar']).decode()
            st.markdown(f"""
            <div style="text-align: center; margin-bottom: 15px;">
                <img src="data:image/png;base64,{b64}" 
                     style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 3px solid #4a8fd8;">
            </div>
            """, unsafe_allow_html=True)
        else:
            # Si no tiene avatar, mostrar icono por defecto
            st.markdown("""
            <div style="text-align: center; margin-bottom: 15px;">
                <div style="width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #4a8fd8 0%, #7e22ce 100%); 
                            display: flex; align-items: center; justify-content: center; margin: 0 auto; font-size: 40px;">
                    👤
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Mostrar nombre de usuario
        st.markdown(f"<h3 style='text-align: center; margin-top: 0;'>👋 {u['first_name']}</h3>", unsafe_allow_html=True)
        role_label = {
            'student': 'Estudiante',
            'teacher': 'Docente', 
            'admin': 'Administrador'
        }.get(u['role'], u['role'])
        st.markdown(f"<p style='text-align: center; color: #888; margin-top: -10px;'>Rol: {role_label}</p>", unsafe_allow_html=True)
        
        st.divider()
        
        # Función helper para limpiar estados al cambiar de página
        def clear_page_states():
            """Limpia todos los estados relacionados con páginas específicas"""
            states_to_clear = [
                'active_course', 'exam_session', 'edit_mode', 'show_courses_modal',
                'final_exam', 'final_exam_started', 'exam_responses', 'exam_finishing',
                'current_challenge', 'challenge_code', 'challenge_output',
                'comprehensive_questions', 'comprehensive_responses', 'evaluation_language',
                'show_evaluation_result', 'tutor_messages', 'tutor_input'
            ]
            for state in states_to_clear:
                if state in st.session_state:
                    del st.session_state[state]
        
        if u['role'] != 'admin':
            if st.button("📊 Dashboard", use_container_width=True):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.current_page = 'dashboard'
                st.session_state.view_mode = 'dashboard'
                st.rerun()
            
        # Menú según rol
        if u['role'] == 'student':
            if st.button("🤖 Tutor IA", use_container_width=True):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.current_page = 'tutor'
                st.rerun()
            if st.button("🚀 Retos Code", use_container_width=True):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.current_page = 'challenges'
                st.rerun()
            if st.button("🎓 Academia Personal IA", use_container_width=True):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.current_page = 'academy'
                st.rerun()
            if st.button("📑 Notas", use_container_width=True):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.current_page = 'grades'
                st.rerun()
            
            # Chat privado (solo para estudiantes con cuenta completa)
            if u.get('account_type') != 'free':
                try:
                    chat_unread = conn.execute("""
                        SELECT COUNT(*) FROM private_messages
                        WHERE recipient_id = ? AND is_read = 0
                    """, (u['username'],)).fetchone()[0]
                except Exception:
                    chat_unread = 0
                chat_label = f"💬 Chat ({chat_unread})" if chat_unread > 0 else "💬 Chat"
                if st.button(chat_label, use_container_width=True):
                    clear_page_states()
                    st.cache_data.clear()
                    st.session_state.current_page = 'chat'
                    st.rerun()
            
            # Notificaciones
            try:
                notif_unread = conn.execute("""
                    SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0
                """, (u['username'],)).fetchone()[0]
            except Exception:
                notif_unread = 0
            notif_label = f"🔔 Notificaciones ({notif_unread})" if notif_unread > 0 else "🔔 Notificaciones"
            if st.button(notif_label, use_container_width=True):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.current_page = 'notifications_full'
                st.rerun()
            
            # Botón de gestión de cursos
            if st.button("📚 Todos mis Cursos", use_container_width=True, type="secondary"):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.show_courses_modal = True
                st.session_state.current_page = 'dashboard'
                st.rerun()

            # Chat con administración
            try:
                stu_admin_unread = conn.execute("""
                    SELECT COUNT(*) FROM admin_student_messages
                    WHERE student_id = ? AND sender_id != ? AND (is_read_by NOT LIKE ?)
                """, (u['username'], u['username'], f'%"{u["username"]}"%')).fetchone()[0]
            except Exception:
                stu_admin_unread = 0
            stu_adm_label = f"🏛️ Chat Administración ({stu_admin_unread})" if stu_admin_unread > 0 else "🏛️ Chat Administración"
            if st.button(stu_adm_label, key="student_admin_chat_btn", use_container_width=True,
                         type="primary" if st.session_state.current_page == 'student_admin_chat' else "secondary"):
                st.session_state.current_page = 'student_admin_chat'
                st.rerun()
                
        elif u['role'] == 'teacher':
            
            # Chat privado para profesores
            try:
                chat_unread = conn.execute("""
                    SELECT COUNT(*) FROM private_messages
                    WHERE recipient_id = ? AND is_read = 0
                """, (u['username'],)).fetchone()[0]
            except Exception:
                chat_unread = 0
            chat_label = f"💬 Chat ({chat_unread})" if chat_unread > 0 else "💬 Chat"
            if st.button(chat_label, use_container_width=True):
                clear_page_states()
                st.cache_data.clear()
                st.session_state.current_page = 'chat'
                st.rerun()

            # Chat con administración
            try:
                admin_reply_unread = conn.execute("""
                    SELECT COUNT(*) FROM admin_teacher_messages
                    WHERE teacher_id = ? AND sender_id != ? AND (is_read_by NOT LIKE ?)
                """, (u['username'], u['username'], f'%"{u["username"]}"%')).fetchone()[0]
            except Exception:
                admin_reply_unread = 0
            adm_label = f"🏛️ Chat Administración ({admin_reply_unread})" if admin_reply_unread > 0 else "🏛️ Chat Administración"
            if st.button(adm_label, key="teacher_admin_chat_btn", use_container_width=True,
                         type="primary" if st.session_state.current_page == 'teacher_admin_chat' else "secondary"):
                st.session_state.current_page = 'teacher_admin_chat'
                st.rerun()
            
            # Notificaciones para profesores
            try:
                if conn:
                    notif_unread = conn.execute("""
                        SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0
                    """, (u['username'],)).fetchone()[0]
                else:
                    notif_unread = 0
            except Exception:
                notif_unread = 0
            notif_label = f"🔔 Notificaciones ({notif_unread})" if notif_unread > 0 else "🔔 Notificaciones"
            if st.button(notif_label, key="teacher_notif_btn", use_container_width=True):
                st.session_state.current_page = 'notifications_full'
                st.rerun()
                
        elif u['role'] == 'admin':
            # Panel Admin menu - aparece primero para admin
            if 'admin_tab' not in st.session_state:
                st.session_state.admin_tab = 'usuarios'
            
            admin_menu_items = [
                ('usuarios',       '👥', 'Gestión de Usuarios'),
                ('cursos',         '📚', 'Gestión de Cursos'),
                ('notificaciones', '🔔', 'Notificaciones'),
                ('estadisticas',   '📊', 'Estadísticas'),
                ('configuracion',  '⚙️', 'Configuración'),
                ('seguridad',      '🔍', 'Auditoría'),
                ('mantenimiento',  '🔄', 'Mantenimiento'),
            ]
            st.markdown("### 🗂️ Panel Admin")
            for key, icon, label in admin_menu_items:
                is_active = st.session_state.admin_tab == key
                if st.button(f"{icon} {label}", key=f"admin_menu_{key}",
                             use_container_width=True,
                             type="primary" if is_active else "secondary"):
                    st.session_state.admin_tab = key
                    st.session_state.current_page = 'dashboard'
                    st.rerun()

            st.divider()

            # ── Sección CHATS ──────────────────────────────────────────────
            st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#475569;padding:4px 0 6px 0;">💬 Chats</div>', unsafe_allow_html=True)

            # Chat grupal de admins
            try:
                admin_unread = conn.execute("""
                    SELECT COUNT(*) FROM admin_messages
                    WHERE sender_id != ? AND (is_read_by NOT LIKE ?)
                """, (u['username'], f'%"{u["username"]}"%')).fetchone()[0]
            except Exception:
                admin_unread = 0
            grp_label = f"👥 Chat Grupal ({admin_unread})" if admin_unread > 0 else "👥 Chat Grupal"
            if st.button(grp_label, key="admin_chat_btn", use_container_width=True,
                         type="primary" if st.session_state.current_page == 'admin_chat' else "secondary"):
                st.session_state.current_page = 'admin_chat'
                st.rerun()

            # Mensajes directos entre admins
            try:
                dm_unread = conn.execute("""
                    SELECT COUNT(*) FROM admin_direct_messages
                    WHERE recipient_id = ? AND is_read = 0
                """, (u['username'],)).fetchone()[0]
            except Exception:
                dm_unread = 0
            dm_label = f"🔒 Mensajes Directos ({dm_unread})" if dm_unread > 0 else "🔒 Mensajes Directos"
            if st.button(dm_label, key="admin_dm_btn", use_container_width=True,
                         type="primary" if st.session_state.current_page == 'admin_dm' else "secondary"):
                st.session_state.current_page = 'admin_dm'
                st.rerun()

            # Chat con docentes (visible para todos los admins)
            try:
                teacher_unread = conn.execute("""
                    SELECT COUNT(*) FROM admin_teacher_messages
                    WHERE sender_id != ? AND (is_read_by NOT LIKE ?)
                """, (u['username'], f'%"{u["username"]}"%')).fetchone()[0]
            except Exception:
                teacher_unread = 0
            tc_label = f"👨‍🏫 Chat Docentes ({teacher_unread})" if teacher_unread > 0 else "👨‍🏫 Chat Docentes"
            if st.button(tc_label, key="admin_teacher_chat_btn", use_container_width=True,
                         type="primary" if st.session_state.current_page == 'admin_teacher_chat' else "secondary"):
                st.session_state.current_page = 'admin_teacher_chat'
                st.rerun()

            # Chat con estudiantes (visible para todos los admins)
            try:
                stu_unread = conn.execute("""
                    SELECT COUNT(*) FROM admin_student_messages
                    WHERE sender_id != ? AND (is_read_by NOT LIKE ?)
                """, (u['username'], f'%"{u["username"]}"%')).fetchone()[0]
            except Exception:
                stu_unread = 0
            stu_label = f"🎓 Chat Estudiantes ({stu_unread})" if stu_unread > 0 else "🎓 Chat Estudiantes"
            if st.button(stu_label, key="admin_student_chat_btn", use_container_width=True,
                         type="primary" if st.session_state.current_page == 'admin_student_chat' else "secondary"):
                st.session_state.current_page = 'admin_student_chat'
                st.rerun()

            st.divider()
        
        st.divider()
        
        # Al hacer clic en "Mi Perfil", forzamos profile_target a None
        if st.button("👤 Mi Perfil", use_container_width=True):
            clear_page_states()
            st.cache_data.clear()
            st.session_state.current_page = 'profile'
            st.session_state.profile_target = None
            st.rerun()
        
        st.divider()
        
        if st.button("🚪 Salir", type="primary", use_container_width=True):
            perform_logout()

# ==========================================
# 7. ROUTER PRINCIPAL
# ==========================================

def main():
    # 1. Login Check
    check_session_timeout()
    update_activity()
    
    if not st.session_state.logged_in:
        render_login_screen()
        return

    # 2. Interfaz Principal
    render_sidebar()
    
    pg = st.session_state.current_page
    rol = st.session_state.user['role']
    
    with st.container():
        # Páginas globales
        if pg == 'profile':
            view_profile()
            return
        elif pg == 'notifications_full':
            view_notifications_page(conn)
            return
            
        # Páginas por Rol
        elif rol == 'admin':
            if pg == 'admin_chat':
                view_admin_chat(conn)
            elif pg == 'admin_dm':
                view_admin_dm(conn)
            elif pg == 'admin_teacher_chat':
                view_admin_teacher_chat(conn)
            elif pg == 'admin_student_chat':
                from views_admin import view_admin_student_chat
                view_admin_student_chat(conn)
            else:
                view_admin(conn)
            
        elif rol == 'teacher':
            if pg == 'teacher_admin_chat':
                from views_admin import view_teacher_admin_chat
                view_teacher_admin_chat(conn)
            else:
                view_teacher(conn, ai_manager.model)
            
        elif rol == 'student':
            if pg == 'student_admin_chat':
                from views_admin import view_student_admin_chat
                view_student_admin_chat(conn)
            else:
                view_student(conn, ai_manager.model)
            
        else:
            st.error(f"Rol desconocido: {rol}")

if __name__ == "__main__":
    main()