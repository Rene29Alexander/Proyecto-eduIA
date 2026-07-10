"""
Configuración centralizada de la plataforma educativa
"""

import os
from pathlib import Path

# ============================================================================
# CONFIGURACIÓN GENERAL
# ============================================================================

# Modo de ejecución
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
DEVELOPMENT = os.getenv('DEVELOPMENT', 'false').lower() == 'true'
TESTING = os.getenv('TESTING', 'false').lower() == 'true'

# Rutas
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'learning_platform.db'
BACKUP_DIR = BASE_DIR / 'backups'
CACHE_DIR = BASE_DIR / '.cache'
LOGS_DIR = BASE_DIR / 'logs'

# Crear directorios si no existen
BACKUP_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ============================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# ============================================================================

DB_CONFIG = {
    'check_same_thread': False,
    'timeout': 30.0,
    'isolation_level': None,  # Autocommit mode
}

# Optimizaciones de SQLite
DB_PRAGMAS = {
    'journal_mode': 'WAL',
    'synchronous': 'NORMAL',
    'cache_size': -2000,  # 2MB
    'foreign_keys': 'ON',
    'temp_store': 'MEMORY',
}

# ============================================================================
# CONFIGURACIÓN DE CACHE
# ============================================================================

CACHE_CONFIG = {
    'max_size': 100,  # Número máximo de entradas
    'ttl_hours': 24,  # Tiempo de vida en horas
    'max_memory_mb': 50,  # Tamaño máximo en MB
}

# ============================================================================
# CONFIGURACIÓN DE SEGURIDAD
# ============================================================================

SECURITY_CONFIG = {
    'max_login_attempts': 5,
    'lockout_duration_minutes': 15,
    'session_timeout_minutes': 120,
    'password_min_length': 8,
    'password_require_uppercase': True,
    'password_require_lowercase': True,
    'password_require_digit': True,
    'password_require_special': False,
}

# ============================================================================
# CONFIGURACIÓN DE ARCHIVOS
# ============================================================================

FILE_CONFIG = {
    'max_file_size_mb': 10,
    'allowed_extensions': ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.py', '.java', '.cpp', '.js', '.docx', '.xlsx'],
    'image_extensions': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
    'document_extensions': ['.pdf', '.docx', '.xlsx', '.txt'],
    'code_extensions': ['.py', '.java', '.cpp', '.js', '.html', '.css', '.sql'],
}

# ============================================================================
# CONFIGURACIÓN DE IA
# ============================================================================

AI_CONFIG = {
    'default_model': 'models/gemini-3.1-flash-lite-preview',
    'fallback_models': [
        'models/gemini-2.5-flash-lite',
        'models/gemini-3-flash',
        'models/gemini-2.5-flash',
        'models/gemini-2-flash',
        'models/gemini-2-flash-lite',
        'models/gemma-4-26b-a4b-it',
        'models/gemma-4-31b-it',
        'models/gemma-3-27b-it',
        'models/gemma-3-12b-it',
        'models/gemma-3-4b-it',
        'models/gemma-3-2b-it',
        'models/gemma-3-1b-it',
    ],
    'max_retries': 3,
    'retry_delay_seconds': 1,
    'rate_limit_per_minute': 60,
    'generation_config': {
        'temperature': 0.7,
        'top_p': 0.9,
        'top_k': 40,
        'max_output_tokens': 8000,
    },
}

# ============================================================================
# CONFIGURACIÓN DE NOTIFICACIONES
# ============================================================================

NOTIFICATION_CONFIG = {
    'max_notifications_per_user': 100,
    'auto_delete_read_after_days': 30,
    'batch_size': 50,
}

# ============================================================================
# CONFIGURACIÓN DE BACKUPS
# ============================================================================

BACKUP_CONFIG = {
    'auto_backup': True,
    'max_backups': 10,
    'compress_threshold_mb': 50,
    'backup_on_critical_operations': True,
}

# ============================================================================
# CONFIGURACIÓN DE LOGS
# ============================================================================

LOG_CONFIG = {
    'level': 'INFO' if not DEBUG else 'DEBUG',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'max_file_size_mb': 10,
    'backup_count': 5,
}

# ============================================================================
# CONFIGURACIÓN DE UI
# ============================================================================

UI_CONFIG = {
    'default_theme': 'dark',
    'items_per_page': 20,
    'max_table_rows': 100,
    'enable_animations': True,
    'show_debug_info': DEBUG,
}

# ============================================================================
# CONFIGURACIÓN DE RENDIMIENTO
# ============================================================================

PERFORMANCE_CONFIG = {
    'enable_caching': True,
    'lazy_loading': True,
    'batch_operations': True,
    'optimize_images': True,
    'compress_responses': True,
}

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def get_config(section: str) -> dict:
    """Obtiene configuración de una sección específica"""
    configs = {
        'db': DB_CONFIG,
        'cache': CACHE_CONFIG,
        'security': SECURITY_CONFIG,
        'file': FILE_CONFIG,
        'ai': AI_CONFIG,
        'notification': NOTIFICATION_CONFIG,
        'backup': BACKUP_CONFIG,
        'log': LOG_CONFIG,
        'ui': UI_CONFIG,
        'performance': PERFORMANCE_CONFIG,
    }
    return configs.get(section, {})

def is_production() -> bool:
    """Verifica si está en modo producción"""
    return not (DEBUG or DEVELOPMENT or TESTING)

def get_db_path() -> Path:
    """Obtiene la ruta de la base de datos"""
    return DB_PATH

def get_backup_dir() -> Path:
    """Obtiene el directorio de backups"""
    return BACKUP_DIR

def get_cache_dir() -> Path:
    """Obtiene el directorio de cache"""
    return CACHE_DIR

def get_logs_dir() -> Path:
    """Obtiene el directorio de logs"""
    return LOGS_DIR

# ============================================================================
# VALIDACIÓN DE CONFIGURACIÓN
# ============================================================================

def validate_config():
    """Valida que la configuración sea correcta"""
    errors = []
    
    # Validar rutas
    if not BASE_DIR.exists():
        errors.append(f"Directorio base no existe: {BASE_DIR}")
    
    # Validar configuración de seguridad
    if SECURITY_CONFIG['password_min_length'] < 8:
        errors.append("La longitud mínima de contraseña debe ser al menos 8")
    
    # Validar configuración de archivos
    if FILE_CONFIG['max_file_size_mb'] < 1:
        errors.append("El tamaño máximo de archivo debe ser al menos 1MB")
    
    # Validar configuración de cache
    if CACHE_CONFIG['max_size'] < 10:
        errors.append("El tamaño máximo de cache debe ser al menos 10 entradas")
    
    if errors:
        raise ValueError(f"Errores de configuración:\n" + "\n".join(errors))
    
    return True

# Validar configuración al importar
if not TESTING:
    validate_config()
