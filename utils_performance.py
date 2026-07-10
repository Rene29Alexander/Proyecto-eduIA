"""
Utilidades de rendimiento y optimización
"""

import time
import functools
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
import os

# Imports opcionales
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil no disponible - algunas funciones de monitoreo estarán deshabilitadas")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL no disponible - optimización de imágenes deshabilitada")

# ============================================================================
# DECORADORES DE RENDIMIENTO
# ============================================================================

def measure_time(func):
    """Decorador para medir tiempo de ejecución"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        elapsed = end - start
        
        if elapsed > 1.0:  # Solo mostrar si tarda más de 1 segundo
            print(f"⏱️ {func.__name__} tardó {elapsed:.2f}s")
        
        return result
    return wrapper

def cache_result(ttl_seconds=300):
    """Decorador para cachear resultados de funciones"""
    def decorator(func):
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Crear clave de cache
            key = str(args) + str(kwargs)
            
            # Verificar si está en cache y no ha expirado
            if key in cache:
                result, timestamp = cache[key]
                if time.time() - timestamp < ttl_seconds:
                    return result
            
            # Ejecutar función y guardar en cache
            result = func(*args, **kwargs)
            cache[key] = (result, time.time())
            
            # Limpiar cache antiguo
            if len(cache) > 100:
                oldest_key = min(cache.keys(), key=lambda k: cache[k][1])
                del cache[oldest_key]
            
            return result
        
        return wrapper
    return decorator

# ============================================================================
# MONITOR DE RECURSOS
# ============================================================================

class ResourceMonitor:
    """Monitor de recursos del sistema"""
    
    @staticmethod
    def get_memory_usage():
        """Obtiene uso de memoria del proceso"""
        if not PSUTIL_AVAILABLE:
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0, 'available': False}
        
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': process.memory_percent(),
                'available': True
            }
        except Exception as e:
            print(f"Error obteniendo uso de memoria: {e}")
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0, 'available': False}
    
    @staticmethod
    def get_cpu_usage():
        """Obtiene uso de CPU"""
        if not PSUTIL_AVAILABLE:
            return {'percent': 0, 'count': 0, 'available': False}
        
        try:
            return {
                'percent': psutil.cpu_percent(interval=0.1),
                'count': psutil.cpu_count(),
                'available': True
            }
        except Exception as e:
            print(f"Error obteniendo uso de CPU: {e}")
            return {'percent': 0, 'count': 0, 'available': False}
    
    @staticmethod
    def get_disk_usage():
        """Obtiene uso de disco"""
        if not PSUTIL_AVAILABLE:
            return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0, 'available': False}
        
        try:
            disk = psutil.disk_usage('.')
            return {
                'total_gb': disk.total / (1024 ** 3),
                'used_gb': disk.used / (1024 ** 3),
                'free_gb': disk.free / (1024 ** 3),
                'percent': disk.percent,
                'available': True
            }
        except Exception as e:
            print(f"Error obteniendo uso de disco: {e}")
            return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0, 'available': False}
    
    @staticmethod
    def get_system_stats():
        """Obtiene estadísticas completas del sistema"""
        return {
            'memory': ResourceMonitor.get_memory_usage(),
            'cpu': ResourceMonitor.get_cpu_usage(),
            'disk': ResourceMonitor.get_disk_usage(),
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def display_stats():
        """Muestra estadísticas en Streamlit"""
        if not PSUTIL_AVAILABLE:
            st.warning("⚠️ Monitoreo de recursos no disponible (instala psutil)")
            return
        
        stats = ResourceMonitor.get_system_stats()
        
        if not stats.get('memory', {}).get('available', False):
            st.warning("⚠️ No se pudieron obtener estadísticas del sistema")
            return
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Memoria",
                f"{stats['memory']['rss_mb']:.1f} MB",
                f"{stats['memory']['percent']:.1f}%"
            )
        
        with col2:
            st.metric(
                "CPU",
                f"{stats['cpu']['percent']:.1f}%",
                f"{stats['cpu']['count']} cores"
            )
        
        with col3:
            st.metric(
                "Disco",
                f"{stats['disk']['used_gb']:.1f} GB",
                f"{stats['disk']['percent']:.1f}%"
            )

# ============================================================================
# OPTIMIZACIÓN DE QUERIES
# ============================================================================

class QueryOptimizer:
    """Optimizador de consultas de base de datos"""
    
    @staticmethod
    def batch_insert(conn, table, columns, data, batch_size=100):
        """Inserta datos en lotes para mejor rendimiento"""
        placeholders = ','.join(['?' for _ in columns])
        query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            conn.executemany(query, batch)
        
        conn.commit()
    
    @staticmethod
    def batch_update(conn, table, set_column, where_column, data, batch_size=100):
        """Actualiza datos en lotes"""
        query = f"UPDATE {table} SET {set_column} = ? WHERE {where_column} = ?"
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            conn.executemany(query, batch)
        
        conn.commit()
    
    @staticmethod
    def explain_query(conn, query, params=None):
        """Analiza plan de ejecución de una query"""
        explain_query = f"EXPLAIN QUERY PLAN {query}"
        
        if params:
            result = conn.execute(explain_query, params).fetchall()
        else:
            result = conn.execute(explain_query).fetchall()
        
        return result

# ============================================================================
# LIMPIEZA DE CACHE
# ============================================================================

class CacheCleaner:
    """Limpiador de archivos de cache"""
    
    @staticmethod
    def clean_old_files(directory, days=7):
        """Elimina archivos más antiguos que X días"""
        directory = Path(directory)
        if not directory.exists():
            return 0
        
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0
        
        for file in directory.rglob('*'):
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        file.unlink()
                        deleted += 1
                    except Exception as e:
                        print(f"Error eliminando {file}: {e}")
        
        return deleted
    
    @staticmethod
    def get_directory_size(directory):
        """Obtiene tamaño total de un directorio"""
        directory = Path(directory)
        if not directory.exists():
            return 0
        
        total = 0
        for file in directory.rglob('*'):
            if file.is_file():
                total += file.stat().st_size
        
        return total / (1024 * 1024)  # MB
    
    @staticmethod
    def clean_cache_directory(cache_dir='.cache', max_size_mb=100):
        """Limpia directorio de cache si excede tamaño máximo"""
        size = CacheCleaner.get_directory_size(cache_dir)
        
        if size > max_size_mb:
            # Eliminar archivos más antiguos primero
            deleted = CacheCleaner.clean_old_files(cache_dir, days=1)
            return deleted
        
        return 0

# ============================================================================
# OPTIMIZACIÓN DE IMÁGENES
# ============================================================================

class ImageOptimizer:
    """Optimizador de imágenes"""
    
    @staticmethod
    def compress_image(image_bytes, max_size_kb=500, quality=85):
        """Comprime imagen si excede tamaño máximo"""
        if not PIL_AVAILABLE:
            print("⚠️ PIL no disponible - retornando imagen original")
            return image_bytes
        
        try:
            import io
            
            # Cargar imagen
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convertir a RGB si es necesario
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Comprimir
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            compressed = output.getvalue()
            
            # Si aún es muy grande, reducir calidad
            if len(compressed) > max_size_kb * 1024 and quality > 50:
                return ImageOptimizer.compress_image(image_bytes, max_size_kb, quality - 10)
            
            return compressed
        except Exception as e:
            print(f"Error comprimiendo imagen: {e}")
            return image_bytes
    
    @staticmethod
    def resize_image(image_bytes, max_width=1920, max_height=1080):
        """Redimensiona imagen manteniendo aspecto"""
        if not PIL_AVAILABLE:
            print("⚠️ PIL no disponible - retornando imagen original")
            return image_bytes
        
        try:
            import io
            
            img = Image.open(io.BytesIO(image_bytes))
            
            # Calcular nuevo tamaño
            ratio = min(max_width / img.width, max_height / img.height)
            if ratio < 1:
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Guardar
            output = io.BytesIO()
            img.save(output, format=img.format or 'JPEG', quality=90)
            return output.getvalue()
        except Exception as e:
            print(f"Error redimensionando imagen: {e}")
            return image_bytes

# ============================================================================
# INSTANCIAS GLOBALES
# ============================================================================

resource_monitor = ResourceMonitor()
query_optimizer = QueryOptimizer()
cache_cleaner = CacheCleaner()
image_optimizer = ImageOptimizer()
