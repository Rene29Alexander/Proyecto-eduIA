"""
Módulo de seguridad mejorado con validaciones y protección
"""

import re
import json
import hashlib
import string
from datetime import datetime, timedelta
import streamlit as st
from database import db_manager

class SecurityManager:
    """Gestor de seguridad y validaciones"""
    
    @staticmethod
    def validate_username(username):
        """Valida formato de nombre de usuario"""
        if not username or len(username) < 3:
            return False, "El nombre de usuario debe tener al menos 3 caracteres"
        
        if len(username) > 50:
            return False, "El nombre de usuario no puede exceder 50 caracteres"
        
        # Solo letras, números, guiones bajos y puntos
        if not re.match(r'^[a-zA-Z0-9_.]+$', username):
            return False, "Solo se permiten letras, números, guiones bajos y puntos"
        
        return True, ""
    
    @staticmethod
    def validate_password(password):
        """Valida fortaleza de contraseña"""
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres"
        
        if len(password) > 100:
            return False, "La contraseña es demasiado larga"
        
        # Verificar complejidad
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in string.punctuation for c in password)
        
        if not (has_upper and has_lower and has_digit):
            return False, "Debe incluir mayúsculas, minúsculas y números"
        
        return True, ""
    
    @staticmethod
    def validate_email(email):
        """Valida formato de email"""
        if not email:
            return True, ""  # Email opcional
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Formato de email inválido"
        
        return True, ""
    
    @staticmethod
    def sanitize_input(text, max_length=1000):
        """Limpia y sanitiza input de usuario"""
        if not text:
            return text
        
        # Limitar longitud
        text = str(text)[:max_length]
        
        # Remover caracteres peligrosos para SQL injection
        dangerous = ["'", '"', ';', '--', '/*', '*/', 'xp_']
        for char in dangerous:
            text = text.replace(char, '')
        
        # Remover scripts maliciosos
        text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    @staticmethod
    def validate_file_upload(file, allowed_types=None, max_size_mb=10):
        """Valida archivos subidos con verificación de contenido"""
        if not file:
            return True, ""
        
        if allowed_types is None:
            allowed_types = ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.py', '.java', '.cpp', '.js', '.docx', '.xlsx']
        
        # Validar tamaño
        max_size = max_size_mb * 1024 * 1024  # Convertir a bytes
        file_size = len(file.getvalue())
        
        if file_size > max_size:
            return False, f"El archivo es demasiado grande (máximo {max_size_mb}MB)"
        
        if file_size == 0:
            return False, "El archivo está vacío"
        
        # Validar tipo por extensión
        file_name = file.name.lower()
        if not any(file_name.endswith(ext) for ext in allowed_types):
            return False, f"Tipo de archivo no permitido. Permitidos: {', '.join(allowed_types)}"
        
        # Validación adicional por contenido (magic numbers)
        file_content = file.getvalue()
        
        # Verificar archivos ejecutables peligrosos
        dangerous_signatures = [
            b'\x4d\x5a',  # PE executable
            b'\x7f\x45\x4c\x46',  # ELF executable
            b'\xca\xfe\xba\xbe',  # Java class file
        ]
        
        for signature in dangerous_signatures:
            if file_content.startswith(signature):
                return False, "Tipo de archivo no permitido por seguridad"
        
        return True, ""
    
    @staticmethod
    def check_brute_force(username, ip_address):
        """Protección contra ataques de fuerza bruta"""
        try:
            conn = db_manager.get_connection()
            
            # Contar intentos fallidos en los últimos 15 minutos
            fifteen_minutes_ago = datetime.now() - timedelta(minutes=15)
            
            count = conn.execute('''
                SELECT COUNT(*) FROM activity_logs 
                WHERE user_id = ? AND action = 'login_failed' 
                AND created_at > ? AND ip_address = ?
            ''', (username, fifteen_minutes_ago, ip_address)).fetchone()[0]
            
            if count >= 5:
                return False, "Demasiados intentos fallidos. Espere 15 minutos."
            
            return True, ""
        except Exception as e:
            print(f"Error en check_brute_force: {e}")
            return True, ""  # En caso de error, permitir acceso
    
    @staticmethod
    def get_client_info():
        """Obtiene información del cliente (Mejorado para nuevas versiones de Streamlit)"""
        try:
            # Intentar obtener información real del cliente
            import streamlit.web.server.websocket_headers as wsh
            headers = wsh.get_websocket_headers()
            client_ip = headers.get('X-Forwarded-For', headers.get('X-Real-IP', 'unknown'))
            user_agent = headers.get('User-Agent', 'unknown')
        except ImportError:
            try:
                # Fallback usando query params
                query_params = st.query_params
                client_ip = query_params.get('client_ip', 'unknown')
                user_agent = query_params.get('user_agent', 'unknown')
            except Exception:
                # Fallback final
                client_ip = 'unknown'
                user_agent = 'unknown'
        except Exception:
            # Fallback final
            client_ip = 'unknown'
            user_agent = 'unknown'

        return {'ip': client_ip, 'user_agent': user_agent}
    
    @staticmethod
    def generate_csrf_token():
        """Genera token CSRF"""
        import secrets
        token = secrets.token_hex(32)
        st.session_state.csrf_token = token
        return token
    
    @staticmethod
    def validate_csrf_token(token):
        """Valida token CSRF"""
        return token == st.session_state.get('csrf_token')

# Instancia global
security = SecurityManager()