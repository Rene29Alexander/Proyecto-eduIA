# -*- coding: utf-8 -*-
"""
Módulo de IA mejorado - Plataforma Educativa
Versión Final: Sistema de Evaluación Inteligente y Preciso
CORRECCIÓN: Lógica impecable, evaluación justa y detección precisa de errores
"""

import google.generativeai as genai
from google.generativeai.types import RequestOptions
import re
import json
import base64
import streamlit as st
import io
import time
import warnings
import hashlib
import pickle
import ast
from datetime import datetime, timedelta
import os

# Ignorar advertencias
warnings.filterwarnings("ignore")

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PdfReader = None
    PDF_AVAILABLE = False

class AICache:
    """Cache para respuestas de IA con límite de memoria"""
    def __init__(self, max_size=100, ttl_hours=24, max_memory_mb=50):
        self.max_size = max_size
        self.ttl_hours = ttl_hours
        self.max_memory_mb = max_memory_mb
        self.cache = {}
        self.cache_file = "ai_cache.pkl"
        self.hit_count = 0
        self.miss_count = 0
        self._load_cache()
    
    def _load_cache(self):
        """Carga cache desde archivo"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
                # Limpiar entradas expiradas al cargar
                self._clean_expired()
            except Exception as e:
                print(f"Error cargando cache: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Guarda cache a archivo con manejo de errores"""
        try:
            # Verificar tamaño antes de guardar
            cache_size_mb = len(pickle.dumps(self.cache)) / (1024 * 1024)
            if cache_size_mb > self.max_memory_mb:
                self._reduce_cache_size()
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            print(f"[WARNING] Error guardando cache: {e}")
            # Don't break the main flow on cache save errors
    
    def _clean_expired(self):
        """Elimina entradas expiradas"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if self._is_expired(entry)
        ]
        for key in expired_keys:
            del self.cache[key]
    
    def _is_expired(self, entry):
        """Check if cache entry is expired"""
        if not entry or 'timestamp' not in entry:
            return True
        
        age = datetime.now() - entry['timestamp']
        return age >= timedelta(hours=self.ttl_hours)
    
    def _reduce_cache_size(self):
        """Reduce el tamaño del cache eliminando entradas antiguas (LRU)"""
        if len(self.cache) <= self.max_size // 2:
            return
        
        # Ordenar por timestamp y eliminar las más antiguas
        sorted_items = sorted(self.cache.items(), key=lambda x: x[1].get('timestamp', datetime.min))
        items_to_remove = len(sorted_items) - (self.max_size // 2)
        
        for i in range(items_to_remove):
            del self.cache[sorted_items[i][0]]
    
    def get_key(self, prompt, model_name):
        """Genera clave única para el cache"""
        content = f"{model_name}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, prompt, model_name):
        """Obtiene respuesta del cache si existe y no ha expirado"""
        try:
            key = self.get_key(prompt, model_name)
            if key in self.cache:
                entry = self.cache[key]
                
                # Check expiration
                if self._is_expired(entry):
                    del self.cache[key]
                    self.miss_count += 1
                    return None
                
                # Cache hit
                self.hit_count += 1
                return entry['response']
            
            # Cache miss
            self.miss_count += 1
            return None
        except Exception as e:
            print(f"[WARNING] Error reading from cache: {e}")
            self.miss_count += 1
            return None
    
    def set(self, prompt, model_name, response):
        """Guarda respuesta en el cache con manejo de errores"""
        try:
            # Verificar límite de tamaño
            if len(self.cache) >= self.max_size:
                self._reduce_cache_size()
            
            key = self.get_key(prompt, model_name)
            self.cache[key] = {
                'response': response,
                'timestamp': datetime.now(),
                'model': model_name,
                'prompt_hash': key
            }
            self._save_cache()
        except Exception as e:
            print(f"[WARNING] Error writing to cache: {e}")
            # Don't break the main flow on cache errors
    
    def clear(self):
        """Limpia todo el cache"""
        self.cache = {}
        self.hit_count = 0
        self.miss_count = 0
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except Exception as e:
                print(f"[WARNING] Error removing cache file: {e}")
    
    def get_cache_health(self):
        """Get cache health metrics"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        miss_rate = (self.miss_count / total_requests * 100) if total_requests > 0 else 0
        
        cache_size_mb = 0
        avg_entry_size = 0
        oldest_entry_age = None
        
        if self.cache:
            try:
                cache_size_mb = len(pickle.dumps(self.cache)) / (1024 * 1024)
                avg_entry_size = cache_size_mb / len(self.cache)
                
                # Find oldest entry
                oldest_timestamp = min(entry.get('timestamp', datetime.now()) for entry in self.cache.values())
                oldest_entry_age = (datetime.now() - oldest_timestamp).total_seconds() / 3600  # hours
            except Exception as e:
                print(f"[WARNING] Error calculating cache metrics: {e}")
        
        return {
            'entries': len(self.cache),
            'max_size': self.max_size,
            'size_mb': round(cache_size_mb, 2),
            'max_memory_mb': self.max_memory_mb,
            'hit_rate': round(hit_rate, 2),
            'miss_rate': round(miss_rate, 2),
            'total_requests': total_requests,
            'avg_entry_size_mb': round(avg_entry_size, 4),
            'oldest_entry_hours': round(oldest_entry_age, 2) if oldest_entry_age else None
        }
    
    def get_stats(self):
        """Obtiene estadísticas del cache (backward compatibility)"""
        health = self.get_cache_health()
        return {
            'entries': health['entries'],
            'max_size': health['max_size'],
            'size_mb': health['size_mb'],
            'max_memory_mb': health['max_memory_mb']
        }

class ResponseValidator:
    """Validator for AI-generated course structures"""
    
    def validate_course_structure(self, structure, expected_topics, language, level):
        """
        Validate course structure completeness and correctness.
        
        Args:
            structure: Parsed course structure (dict or list)
            expected_topics: Expected number of topics
            language: Programming language
            level: Difficulty level
            
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Handle both dict with 'topics' key and direct list
        if isinstance(structure, dict):
            if 'topics' not in structure:
                errors.append("Structure missing 'topics' key")
                return False, errors
            topics = structure['topics']
        elif isinstance(structure, list):
            topics = structure
        else:
            errors.append(f"Invalid structure type: {type(structure)}")
            return False, errors
        
        # Validate topic count
        topic_count_error = self._validate_topic_count(topics, expected_topics)
        if topic_count_error:
            errors.append(topic_count_error)
        
        # Validate each topic
        for i, topic in enumerate(topics):
            topic_errors = self._validate_topic_fields(topic)
            for error in topic_errors:
                errors.append(f"Topic {i+1}: {error}")
            
            type_errors = self._validate_field_types(topic)
            for error in type_errors:
                errors.append(f"Topic {i+1}: {error}")
            
            quality_errors = self._validate_content_quality(topic, language, level)
            for error in quality_errors:
                errors.append(f"Topic {i+1}: {error}")
        
        return len(errors) == 0, errors
    
    def _validate_topic_count(self, topics, expected):
        """Validate correct number of topics (±1 tolerance)"""
        if not isinstance(topics, list):
            return "Topics is not a list"
        
        actual = len(topics)
        if abs(actual - expected) > 1:
            return f"Expected {expected} topics (±1), got {actual}"
        
        return None
    
    def _validate_topic_fields(self, topic):
        """Validate required fields in each topic"""
        errors = []
        
        if not isinstance(topic, dict):
            errors.append("Topic is not a dictionary")
            return errors
        
        # Required fields
        required_fields = {
            'title': str,
            'description': str,
            'order': (int, float),  # Accept both
            'estimated_hours': (int, float)
        }
        
        for field, expected_type in required_fields.items():
            if field not in topic:
                errors.append(f"Missing required field: {field}")
            elif not isinstance(topic[field], expected_type):
                errors.append(f"Field '{field}' has wrong type: expected {expected_type}, got {type(topic[field])}")
        
        # Field constraints
        if 'title' in topic:
            if not topic['title'] or len(str(topic['title']).strip()) == 0:
                errors.append("Title is empty")
        
        if 'description' in topic:
            desc = str(topic['description'])
            if len(desc.strip()) < 20:
                errors.append(f"Description too short: {len(desc)} chars (min 20)")
        
        if 'order' in topic:
            try:
                order = int(topic['order'])
                if order < 0:
                    errors.append("Order must be non-negative")
            except (ValueError, TypeError):
                errors.append("Order must be a number")
        
        if 'estimated_hours' in topic:
            try:
                hours = float(topic['estimated_hours'])
                if hours <= 0:
                    errors.append("Estimated hours must be positive")
                elif hours > 20:
                    errors.append(f"Estimated hours unreasonable: {hours} (max 20)")
            except (ValueError, TypeError):
                errors.append("Estimated hours must be a number")
        
        return errors
    
    def _validate_field_types(self, topic):
        """Validate field data types"""
        errors = []
        
        if not isinstance(topic, dict):
            return errors
        
        # Check specific type requirements
        if 'topic_number' in topic:
            if not isinstance(topic['topic_number'], (int, float)):
                errors.append(f"topic_number must be numeric, got {type(topic['topic_number'])}")
        
        if 'order_index' in topic:
            if not isinstance(topic['order_index'], (int, float)):
                errors.append(f"order_index must be numeric, got {type(topic['order_index'])}")
        
        return errors
    
    def _validate_content_quality(self, topic, language, level):
        """Validate content appropriateness for language/level"""
        errors = []
        
        if not isinstance(topic, dict):
            return errors
        
        # Check title relevance
        if 'title' in topic and language:
            title = str(topic['title']).lower()
            # Very basic check - title should not be generic placeholder
            generic_terms = ['tema', 'topic', 'section', 'module', 'placeholder', 'example']
            if any(term in title for term in generic_terms) and len(title) < 15:
                errors.append("Title appears to be a generic placeholder")
        
        # Check description quality
        if 'description' in topic:
            desc = str(topic['description']).lower()
            # Check for placeholder text
            placeholder_terms = ['lorem ipsum', 'placeholder', 'todo', 'tbd', 'pending']
            if any(term in desc for term in placeholder_terms):
                errors.append("Description contains placeholder text")
        
        return errors

class AIManager:
    """Gestor de funcionalidades de IA"""
    
    def __init__(self, api_key=None):
        # Intentar obtener API key en este orden:
        # 1. Parámetro directo
        # 2. Base de datos (configuración del admin)
        # 3. st.secrets (archivo secrets.toml)
        if api_key:
            self.api_key = api_key
        else:
            try:
                # Intentar leer de la base de datos primero
                from database import db_manager
                conn = db_manager.get_connection()
                result = conn.execute(
                    "SELECT value FROM system_settings WHERE key = 'gemini_api_key'"
                ).fetchone()
                
                if result and result[0]:
                    self.api_key = result[0]
                else:
                    # Si no está en BD, usar secrets.toml
                    self.api_key = st.secrets.get("GEMINI_API_KEY", "")
            except Exception as e:
                print(f"Error obteniendo API key de BD: {e}")
                # Fallback a secrets.toml
                try:
                    self.api_key = st.secrets.get("GEMINI_API_KEY", "")
                except Exception as e:
                    print(f"Error obteniendo API key de secrets: {e}")
                    self.api_key = ""
        
        self.model = None
        self.cache = AICache()
        self.rate_limit_remaining = 60
        self.rate_limit_reset = datetime.now()
        self.available_models = []
        self.current_model_name = ""
        self.repair_cache = {}  # Cache for JSON repair attempts
        
        # Inicializar evaluador integrado
        from evaluacion.evaluador_integrado import Evaluador_Integrado
        self.evaluador_integrado = Evaluador_Integrado(self)
        
        if self.api_key:
            self._configure()
    
    def _validate_question_has_code(self, question_text, language):
        """
        Valida que una pregunta contenga un bloque de código.
        
        Args:
            question_text: Texto de la pregunta
            language: Lenguaje de programación
        
        Returns:
            bool: True si contiene código, False en caso contrario
        """
        if not question_text or not isinstance(question_text, str):
            return False
        
        # Buscar bloques de código markdown con formato ```lenguaje\n...\n```
        code_block_pattern = r'```[\w]*\n.*?\n```'
        has_code_block = re.search(code_block_pattern, question_text, re.DOTALL)
        
        return has_code_block is not None
    
    def _count_code_lines(self, question_text):
        """
        Cuenta las líneas de código en un bloque markdown.
        
        Args:
            question_text: Texto de la pregunta con bloque de código
        
        Returns:
            int: Número de líneas de código (excluyendo vacías y comentarios de tabla SQL)
        """
        if not question_text or not isinstance(question_text, str):
            return 0
        
        # Extraer el bloque de código
        code_block_pattern = r'```[\w]*\n(.*?)\n```'
        match = re.search(code_block_pattern, question_text, re.DOTALL)
        
        if not match:
            return 0
        
        code = match.group(1)
        lines = code.split('\n')
        
        # Contar líneas excluyendo:
        # - Líneas vacías
        # - Comentarios de tabla SQL (líneas que empiezan con --)
        code_lines = 0
        sql_table_comments = 0
        
        for line in lines:
            stripped = line.strip()
            # Excluir líneas vacías
            if not stripped:
                continue
            # Contar comentarios de tabla SQL por separado
            if stripped.startswith('--') and '|' in stripped:
                sql_table_comments += 1
                continue
            code_lines += 1
        
        # Para SQL: si hay comentarios de tabla (datos de ejemplo), 
        # el código es válido incluso con 1-2 líneas de SQL real
        if sql_table_comments > 0 and code_lines >= 1:
            return code_lines + sql_table_comments  # Contar todo junto para validación
        
        return code_lines
    
    def _validate_generation_config(self, config):
        """
        Validate generation configuration parameters.
        
        Args:
            config: Dictionary with generation parameters
            
        Returns:
            (is_valid, error_message)
        """
        errors = []
        
        # Validate temperature (0.0 to 2.0)
        if 'temperature' in config:
            temp = config['temperature']
            if not isinstance(temp, (int, float)):
                errors.append("temperature must be a number")
            elif temp < 0.0 or temp > 2.0:
                errors.append(f"temperature must be between 0.0 and 2.0, got {temp}")
        
        # Validate top_p (0.0 to 1.0)
        if 'top_p' in config:
            top_p = config['top_p']
            if not isinstance(top_p, (int, float)):
                errors.append("top_p must be a number")
            elif top_p < 0.0 or top_p > 1.0:
                errors.append(f"top_p must be between 0.0 and 1.0, got {top_p}")
        
        # Validate top_k (positive integer)
        if 'top_k' in config:
            top_k = config['top_k']
            if not isinstance(top_k, int):
                errors.append("top_k must be an integer")
            elif top_k < 1:
                errors.append(f"top_k must be positive, got {top_k}")
        
        # Validate max_output_tokens (positive integer, reasonable max)
        if 'max_output_tokens' in config:
            max_tokens = config['max_output_tokens']
            if not isinstance(max_tokens, int):
                errors.append("max_output_tokens must be an integer")
            elif max_tokens < 1:
                errors.append(f"max_output_tokens must be positive, got {max_tokens}")
            elif max_tokens > 32000:
                errors.append(f"max_output_tokens too large: {max_tokens} (max 32000)")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, None
    def _validate_question_has_code(self, question_text, language):
        """
        Valida que una pregunta contenga un bloque de código.

        Args:
            question_text: Texto de la pregunta
            language: Lenguaje de programación

        Returns:
            bool: True si contiene código, False en caso contrario
        """
        if not question_text or not isinstance(question_text, str):
            return False

        # Buscar bloques de código markdown con formato ```lenguaje\n...\n```
        code_block_pattern = r'```[\w]*\n.*?\n```'
        has_code_block = re.search(code_block_pattern, question_text, re.DOTALL)

        return has_code_block is not None

    def _count_code_lines(self, question_text):
        """
        Cuenta las líneas de código en un bloque markdown.

        Args:
            question_text: Texto de la pregunta con bloque de código

        Returns:
            int: Número de líneas de código (excluyendo vacías y comentarios de tabla SQL)
        """
        if not question_text or not isinstance(question_text, str):
            return 0

        # Extraer el bloque de código
        code_block_pattern = r'```[\w]*\n(.*?)\n```'
        match = re.search(code_block_pattern, question_text, re.DOTALL)

        if not match:
            return 0

        code = match.group(1)
        lines = code.split('\n')

        # Contar líneas excluyendo:
        # - Líneas vacías
        # - Comentarios de tabla SQL (líneas que empiezan con --)
        code_lines = 0
        for line in lines:
            stripped = line.strip()
            # Excluir líneas vacías
            if not stripped:
                continue
            # Excluir comentarios de tabla SQL (formato: -- | col1 | col2 |)
            if stripped.startswith('--') and '|' in stripped:
                continue
            code_lines += 1

        return code_lines

    
    def _configure(self):
        try:
            genai.configure(api_key=self.api_key)
            
            # Modelos disponibles en orden de prioridad (2026)
            # Solo modelos de texto con cuota disponible
            models_to_try = [
                'gemini-3.1-flash-lite-preview',   # Principal: 15 RPM
                'gemini-2.5-flash-lite',            # 10 RPM
                'gemini-3-flash',                   # 5 RPM
                'gemini-2.5-flash',                 # 5 RPM
                'gemini-2-flash',                   # fallback
                'gemini-2-flash-lite',              # fallback
                'gemma-4-26b-a4b-it',               # Gemma 4 MoE: 15 RPM
                'gemma-4-31b-it',                   # Gemma 4 Dense: 15 RPM
                'gemma-3-27b-it',                   # Gemma 3 27B: 30 RPM
                'gemma-3-12b-it',                   # Gemma 3 12B: 30 RPM
                'gemma-3-4b-it',                    # Gemma 3 4B: 30 RPM
                'gemma-3-2b-it',                    # Gemma 3 2B: 30 RPM
                'gemma-3-1b-it',                    # Gemma 3 1B: 30 RPM
            ]
            
            self.model = None
            self.available_models = []
            
            # Probar modelos en orden de preferencia
            for model_name in models_to_try:
                try:
                    test_model = genai.GenerativeModel(model_name)
                    # NO hacer prueba real para no gastar cuota
                    self.available_models.append((model_name, test_model))
                    if not self.model:  # Usar el primero como principal
                        self.model = test_model
                        self.current_model_name = model_name
                        print(f"[INFO] Usando modelo: {model_name}")
                except Exception as e:
                    print(f"[WARNING] Modelo {model_name} no disponible: {e}")
                    continue
            
            if not self.model:
                st.error("[ERROR] No se pudo configurar ningún modelo de IA")
                st.session_state.ai_available = False
                return
            
            # Configuración optimizada para generación de contenido educativo
            self.generation_config = {
                'temperature': 0.7,  # Aumentado para más variabilidad
                'top_p': 0.9,
                'top_k': 40,
                'max_output_tokens': 8000,  # Aumentado significativamente para contenido completo
            }
            
            # Validate initial configuration
            is_valid, error_msg = self._validate_generation_config(self.generation_config)
            if not is_valid:
                print(f"[WARNING] Invalid generation config: {error_msg}")
                # Use safe defaults
                self.generation_config = {
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'top_k': 40,
                    'max_output_tokens': 8000,
                }
            
            st.session_state.ai_available = True
            
        except Exception as e:
            st.error(f"[ERROR] Error configurando IA: {str(e)}")
            st.session_state.ai_available = False
            self.model = None
    
    def _check_rate_limit(self):
        if datetime.now() > self.rate_limit_reset:
            self.rate_limit_remaining = 60
            self.rate_limit_reset = datetime.now() + timedelta(minutes=1)
        return self.rate_limit_remaining > 0
    
    def _update_rate_limit(self):
        self.rate_limit_remaining -= 1
    
    def _get_timeout_for_operation(self, operation_type):
        """Get appropriate timeout based on operation type"""
        timeouts = {
            'course_generation': 60,
            'topic_materials': 45,
            'exercise_generation': 30,
            'evaluation': 20,
            'json_repair': 15,
            'default': 30
        }
        return timeouts.get(operation_type, timeouts['default'])
    
    def _handle_api_error(self, error, attempt, model_name):
        """
        Classify error and determine retry strategy.
        
        Returns:
            (should_retry, error_message)
        """
        error_str = str(error).lower()
        
        # Quota errors - rotate model immediately
        if any(keyword in error_str for keyword in ['429', 'quota', 'resource_exhausted']):
            return True, f"Quota exhausted on {model_name}, rotating to next model"
        
        # Timeout errors - retry with increased timeout
        if any(keyword in error_str for keyword in ['timeout', 'timed out', 'deadline']):
            return True, f"Timeout on attempt {attempt}, retrying"
        
        # Network errors - exponential backoff
        if any(keyword in error_str for keyword in ['connection', 'network', 'unavailable']):
            return True, f"Network error on attempt {attempt}, retrying with backoff"
        
        # Invalid response - retry with same model
        if any(keyword in error_str for keyword in ['empty', 'no text', 'blocked']):
            return True, f"Invalid response on attempt {attempt}, retrying"
        
        # Auth errors - no retry
        if any(keyword in error_str for keyword in ['401', '403', 'unauthorized', 'forbidden']):
            return False, f"Authentication failed: {error}"
        
        # Unknown errors - retry once
        if attempt < 1:
            return True, f"Unknown error on attempt {attempt}: {error}"
        
        return False, f"Unrecoverable error: {error}"
    
    def get_model_status(self):
        """Get current status of all models in pool"""
        return {
            'current_model': self.current_model_name,
            'available_models': [name for name, _ in self.available_models],
            'total_models': len(self.available_models)
        }
    
    def call_with_retry(self, prompt, max_retries=3, use_cache=False, max_output_tokens=None, temperature=None, timeout=30, operation_type='default'):
        if not self.model: 
            return "Error: IA no disponible - Modelo no inicializado"
        
        if timeout == 30 and operation_type != 'default':
            timeout = self._get_timeout_for_operation(operation_type)
        
        config = self.generation_config.copy()
        if max_output_tokens:
            config['max_output_tokens'] = max_output_tokens
        if temperature is not None:
            config['temperature'] = temperature
        
        excluded_models = set()
        last_error = None
        
        for attempt in range(max_retries):
            try:
                request_options = RequestOptions(timeout=timeout)
                response = self.model.generate_content(
                    prompt, 
                    generation_config=config,
                    request_options=request_options
                )
                if response and hasattr(response, 'text') and response.text:
                    return response.text
                else:
                    last_error = "Respuesta vacía o sin texto"
                    
            except TimeoutError as te:
                last_error = f"Timeout: {str(te)}"
                timeout = min(timeout * 1.5, 120)
                    
            except Exception as e:
                last_error = str(e)
                error_str = str(e)
                
                # Para 429/quota: rotar modelo INMEDIATAMENTE sin reintentar el actual
                if any(k in error_str for k in ['429', 'quota', 'resource_exhausted', 'RESOURCE_EXHAUSTED']):
                    excluded_models.add(self.current_model_name)
                    print(f"[INFO] 429 en {self.current_model_name}, rotando modelo...")
                    rotated = self._try_rotate_model(prompt, config, excluded_models)
                    if rotated is not None:
                        return rotated
                    # Si no hay más modelos, esperar y reintentar
                    last_error = error_str
                    if attempt < max_retries - 1:
                        time.sleep(5)
                    continue
                
                should_retry, error_msg = self._handle_api_error(e, attempt, self.current_model_name)
                if not should_retry:
                    return f"Error: {error_msg}"
                
                if attempt < max_retries - 1:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue
        
        return f"Error de IA después de {max_retries} intentos: {last_error}"
    
    def _try_rotate_model(self, prompt, config=None, excluded_models=None):
        """Rotate to next available model, tracking excluded models. Returns None if all exhausted."""
        if not hasattr(self, 'available_models') or len(self.available_models) <= 1:
            return None
        
        if config is None:
            config = self.generation_config
        if excluded_models is None:
            excluded_models = set()
        
        for model_name, model_instance in self.available_models:
            if model_name == self.current_model_name or model_name in excluded_models:
                continue
            try:
                response = model_instance.generate_content(prompt, generation_config=config)
                if response and response.text:
                    self.model = model_instance
                    self.current_model_name = model_name
                    print(f"[INFO] Rotado a modelo: {model_name}")
                    return response.text
            except Exception as e:
                error_str = str(e)
                if any(k in error_str for k in ['429', 'quota', 'resource_exhausted', 'RESOURCE_EXHAUSTED']):
                    excluded_models.add(model_name)
                continue
        
        return None
    
    def _validate_repair(self, repaired_json, original_json):
        """Validate that repair preserved essential content"""
        if not repaired_json or not original_json:
            return False
        
        try:
            # Check that repaired JSON is parseable
            if isinstance(repaired_json, str):
                json.loads(repaired_json)
            
            # Basic validation: check length similarity (within 50% difference)
            len_diff = abs(len(str(repaired_json)) - len(original_json))
            if len_diff > len(original_json) * 0.5:
                return False
            
            return True
        except:
            return False
    
    def _repair_json_with_ai(self, broken_json_text):
        """
        Attempt to repair malformed JSON using AI with caching and validation.
        
        Args:
            broken_json_text: The malformed JSON string
            
        Returns:
            Parsed JSON object or None if repair fails
        """
        if not broken_json_text:
            return None
        
        # Check repair cache first
        cache_key = hashlib.md5(broken_json_text.encode()).hexdigest()
        if cache_key in self.repair_cache:
            return self.repair_cache[cache_key]
        
        try:
            # Build repair prompt with explicit instructions
            prompt = f"""
            Repair the following broken JSON and return ONLY valid JSON.
            
            CRITICAL RULES:
            - Return ONLY the repaired JSON
            - NO markdown formatting (no ```json or ```)
            - NO explanations or additional text
            - Preserve all original content
            - Fix syntax errors only
            
            BROKEN JSON:
            {broken_json_text}
            
            REPAIRED JSON:
            """
            
            # Call AI with low temperature for deterministic repair
            repaired = self.call_with_retry(
                prompt, 
                max_retries=1, 
                use_cache=False,
                temperature=0.3,
                timeout=15
            )
            
            if not repaired or "Error" in repaired:
                self.repair_cache[cache_key] = None
                return None
            
            # Clean the response
            cleaned = self._clean_markdown(repaired.strip())
            
            # Validate repair preserved content
            if not self._validate_repair(cleaned, broken_json_text):
                self.repair_cache[cache_key] = None
                return None
            
            # Try to parse the repaired JSON
            try:
                result = json.loads(cleaned)
                self.repair_cache[cache_key] = result
                return result
            except json.JSONDecodeError:
                # Try with quote normalization
                try:
                    fixed = cleaned.replace("'", '"')
                    fixed = self._normalize_json(fixed)
                    result = json.loads(fixed)
                    self.repair_cache[cache_key] = result
                    return result
                except:
                    self.repair_cache[cache_key] = None
                    return None
        except Exception as e:
            print(f"[ERROR] JSON repair failed: {e}")
            self.repair_cache[cache_key] = None
            return None

    def _clean_markdown(self, text):
        """Remove markdown code block formatting"""
        if not text:
            return text
        
        # Remove ```json, ```, ``` patterns
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.replace("'''json", "").replace("'''", "")
        
        return text.strip()
    
    def _find_json_boundaries(self, text, start_char, end_char):
        """Find matching brackets/braces with depth tracking"""
        start_idx = text.find(start_char)
        if start_idx == -1:
            return -1, -1
        
        # Track depth to handle nested structures
        depth = 0
        end_idx = -1
        
        for i in range(start_idx, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        
        if end_idx == -1:
            # Fallback: find last occurrence
            end_idx = text.rfind(end_char)
        
        return start_idx, end_idx
    
    def _normalize_json(self, text):
        """Normalize JSON formatting (quotes, commas, whitespace)"""
        if not text:
            return text
        
        # Remove trailing commas before } and ]
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)
        
        # Clean excessive whitespace but preserve structure
        text = re.sub(r"\n\s*\n", "\n", text)
        
        return text
    
    def extract_json_from_response(self, text, expected_structure=None):
        """
        Extract JSON using multiple strategies:
        1. Standard JSON parsing
        2. Markdown code block extraction
        3. Bracket/brace matching with depth tracking
        4. Quote normalization (single to double)
        5. Trailing comma removal
        6. AST literal_eval for Python-like syntax
        7. AI-powered repair (last resort)
        
        Args:
            text: Raw AI response text
            expected_structure: 'dict', 'list', or None for auto-detect
            
        Returns:
            Parsed JSON object or None if all strategies fail
        """
        if not text:
            return None
        
        # Strategy 1: Clean markdown formatting
        text_clean = self._clean_markdown(text.strip())
        
        # Strategy 2: Identify delimiters (auto-detect if not specified)
        target_start = '{'
        target_end = '}'
        
        if expected_structure == 'list':
            target_start = '['
            target_end = ']'
        elif expected_structure is None:
            # Auto-detect based on first occurrence
            idx_obj = text_clean.find('{')
            idx_arr = text_clean.find('[')
            
            if idx_obj == -1 and idx_arr == -1:
                return None
            
            if idx_obj != -1 and (idx_arr == -1 or idx_obj < idx_arr):
                target_start = '{'
                target_end = '}'
            else:
                target_start = '['
                target_end = ']'
        
        # Strategy 3: Find JSON boundaries with depth tracking
        start_idx, end_idx = self._find_json_boundaries(text_clean, target_start, target_end)
        
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return None
        
        candidate = text_clean[start_idx:end_idx + 1]
        
        # Strategy 4: Try standard JSON parsing with normalization
        try:
            normalized = self._normalize_json(candidate)
            return json.loads(normalized)
        except json.JSONDecodeError:
            pass
        
        # Strategy 5: Try with quote normalization (single to double)
        try:
            fixed = candidate.replace("'", '"')
            normalized = self._normalize_json(fixed)
            return json.loads(normalized)
        except json.JSONDecodeError:
            pass
        
        # Strategy 6: Try AST literal_eval (supports True/False, single quotes)
        try:
            return ast.literal_eval(candidate)
        except:
            pass
        
        # Strategy 7: AI-powered repair (last resort)
        try:
            repaired = self._repair_json_with_ai(candidate)
            if repaired:
                return repaired
        except:
            pass
        
        return None
    
    # ========== FUNCIONES EDUCATIVAS ==========
    
    def evaluate_code(self, code, criteria, language="Python"):
        """
        Evalúa código usando el sistema de evaluación integrado mejorado.

        Args:
            code: Código del estudiante
            criteria: Contexto del ejercicio
            language: Lenguaje de programación

        Returns:
            Tuple: (score, feedback, correctness, suggestions, concepts)
        """
        # Usar el nuevo evaluador integrado
        result = self.evaluador_integrado.evaluar_codigo(code, criteria, language)

        # Convertir a formato antiguo para compatibilidad con código existente
        return (
            result.score,
            result.feedback,
            result.correctness,
            result.suggestions,
            result.concepts
        )

    
    def _ensure_list(self, value):
        """Asegura que el valor sea una lista, convirtiendo strings si es necesario"""
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            # Si es un string, intentar dividirlo en elementos lógicos
            if value.strip():
                # Si contiene saltos de línea, dividir por líneas
                if '\n' in value:
                    items = [item.strip().lstrip('- ').lstrip('• ') for item in value.split('\n') if item.strip()]
                    return [item for item in items if item]
                # Si contiene comas, dividir por comas
                elif ',' in value:
                    items = [item.strip().lstrip('- ').lstrip('• ') for item in value.split(',') if item.strip()]
                    return [item for item in items if item]
                # Si es un string simple, devolverlo como lista de un elemento
                else:
                    return [value.strip().lstrip('- ').lstrip('• ')]
            else:
                return []
        else:
            return []
    
    def _evaluate_code_manually_improved(self, code, criteria, language="Python"):
        """Evaluación manual mejorada para casos donde la IA falla"""
        code_lower = code.lower().strip()
        criteria_lower = criteria.lower()
        
        # Detectar texto aleatorio o código completamente inválido
        if len(code) < 20 and not any(char in code for char in '(){}[]=+-*/'):
            return 0, f"Texto aleatorio detectado. No es código de {language}.", "incorrecto", [f"Escribir código real en {language}"], ["programación"]
        
        # Detectar errores de sintaxis críticos específicos por lenguaje
        critical_syntax_errors = []
        
        if language == "Python":
            if 'def ' in code and ':' not in code:
                critical_syntax_errors.append("Falta ':' en definición de función")
            if 'if ' in code and not any(':' in line for line in code.split('\n') if 'if ' in line):
                critical_syntax_errors.append("Falta ':' después de 'if'")
        elif language == "Java":
            if 'public class' in code and '{' not in code:
                critical_syntax_errors.append("Falta '{' en definición de clase")
        elif language == "C++":
            if '#include' in code and ';' not in code:
                critical_syntax_errors.append("Falta ';' en declaraciones")
        elif language == "JavaScript":
            if 'function' in code and '{' not in code:
                critical_syntax_errors.append("Falta '{' en definición de función")
        elif language == "SQL":
            if 'selec ' in code_lower and 'select ' not in code_lower:
                critical_syntax_errors.append("Error de sintaxis: 'SELEC' debería ser 'SELECT'")
            if 'select' in code_lower and 'from' not in code_lower:
                critical_syntax_errors.append("Consulta SQL incompleta - falta FROM")
        elif language == "NoSQL":
            if 'db.' not in code:
                critical_syntax_errors.append("Código NoSQL debe contener operaciones de base de datos (db.)")
            if 'stock == 10' in code:
                critical_syntax_errors.append("Error de operador: usar {stock: 10} en lugar de 'stock == 10'")
            if 'nombre: Paracetamol' in code and 'nombre: "Paracetamol"' not in code:
                critical_syntax_errors.append("Error de sintaxis: valores string deben estar entre comillas")
        
        # Verificar paréntesis balanceados para lenguajes que los usan
        if language not in ["SQL", "NoSQL"] and code.count('(') != code.count(')'):
            critical_syntax_errors.append("Paréntesis no balanceados")
        
        # Si hay errores críticos, puntuación baja
        if critical_syntax_errors:
            return 2, f"Errores de sintaxis críticos en {language}: {', '.join(critical_syntax_errors)}", "incorrecto", [f"Corregir sintaxis de {language}"], ["sintaxis"]
        
        # Evaluación positiva para código que parece resolver el problema
        score = 7  # Puntuación base
        feedback = f"Código de {language} evaluado manualmente."
        suggestions = [f"Revisar lógica específica de {language}"]
        concepts = [f"programación en {language}"]
        
        # Verificar si el código parece resolver el problema específico
        problem_keywords = criteria_lower.split()
        code_matches = 0
        
        for keyword in problem_keywords:
            if keyword in code_lower:
                code_matches += 1
        
        # Si el código contiene muchas palabras clave del problema
        if code_matches >= len(problem_keywords) * 0.3:  # 30% de coincidencia
            score = 10  # Código que claramente resuelve el problema
            feedback = f"El código de {language} parece resolver el problema planteado correctamente y de forma completa."
            suggestions = [f"Agregar comentarios en {language}", "Considerar casos edge"]
            concepts = ["lógica", "resolución de problemas", f"{language.lower()}"]
        
        # Bonificaciones adicionales para código que claramente es correcto
        if language == "Python":
            # Si tiene def, return y print, probablemente es una función válida
            if 'def ' in code_lower and 'return ' in code_lower:
                score = min(10, score + 1)
                feedback = f"El código de {language} implementa correctamente una función con entrada y salida."
                concepts.append("funciones")
        elif language == "NoSQL":
            # Si tiene operaciones MongoDB válidas y sintaxis correcta
            if 'db.' in code and 'find(' in code and '{' in code and '}' in code:
                score = min(10, score + 1)
                feedback = f"El código NoSQL implementa operaciones MongoDB válidas."
                concepts.append("consultas NoSQL")
        elif language == "SQL":
            # Si tiene SELECT, FROM y WHERE correctos
            if 'select' in code_lower and 'from' in code_lower:
                score = min(10, score + 1)
                feedback = f"El código SQL implementa una consulta válida."
                concepts.append("consultas SQL")
        
        # Bonificaciones por buenas prácticas específicas por lenguaje
        if language == "Python":
            if 'def ' in code_lower:
                score = min(10, score + 0.5)
                concepts.append("funciones")
        elif language == "Java":
            if 'public class' in code_lower:
                score = min(10, score + 0.5)
                concepts.append("clases")
        elif language == "JavaScript":
            if 'function' in code_lower or '=>' in code:
                score = min(10, score + 0.5)
                concepts.append("funciones")
        elif language == "SQL":
            if any(keyword in code_lower for keyword in ['select', 'insert', 'update', 'delete']):
                score = min(10, score + 0.5)
                concepts.append("consultas")
        elif language == "NoSQL":
            if any(keyword in code_lower for keyword in ['find', 'insert', 'update', 'aggregate']):
                score = min(10, score + 0.5)
                concepts.append("operaciones")
        
        # Bonificaciones generales
        if 'if ' in code_lower or 'else' in code_lower:
            score = min(10, score + 0.3)
            concepts.append("condicionales")
        
        if 'for ' in code_lower or 'while ' in code_lower:
            score = min(10, score + 0.3)
            concepts.append("bucles")
        
        # Asegurar que esté en rango
        score = min(10, max(0, score))
        
        return int(round(score)), feedback, "correcto" if score >= 8 else "parcial", suggestions, concepts
    
    def _validate_code_relevance(self, code, criteria, language):
            """
            Calcula score de relevancia (0.0 - 1.0) comparando código vs criterios.

            Args:
                code: Código del estudiante
                criteria: Contexto del ejercicio
                language: Lenguaje de programación

            Returns:
                float: Score de relevancia entre 0.0 y 1.0
            """
            code_lower = code.lower().strip()
            criteria_lower = criteria.lower()

            # 1. Extraer palabras clave del contexto_ejercicio (tokenización)
            # Filtrar palabras comunes y muy cortas
            stop_words = {
                'para', 'que', 'con', 'una', 'del', 'las', 'los', 'debe', 'ser', 
                'este', 'esta', 'como', 'por', 'en', 'de', 'la', 'el', 'y', 'o', 
                'a', 'crear', 'hacer', 'usar', 'todos', 'contexto', 'ejercicio', 
                'descripción', 'problema', 'requisitos', 'código', 'programa',
                'the', 'and', 'for', 'with', 'from', 'that', 'this', 'are', 'was'
            }

            words = criteria_lower.split()
            keywords = [w for w in words if len(w) > 4 and w not in stop_words]

            # Limitar a las primeras 10 palabras clave más relevantes
            keywords = keywords[:10]

            if not keywords:
                # Si no hay keywords, usar relevancia media
                return 0.5

            # 2. Contar coincidencias en el código (case-insensitive)
            matches = sum(1 for keyword in keywords if keyword in code_lower)

            # 3. Calcular ratio: coincidencias / total_palabras_clave
            base_relevance = matches / len(keywords) if keywords else 0.0

            # 4. Aplicar bonificaciones por estructuras relevantes
            structure_bonus = 0.0

            if language == "Python":
                # Bonificación por elementos de programación Python
                python_elements = [
                    'def ' in code_lower,
                    'class ' in code_lower,
                    'import ' in code_lower or 'from ' in code_lower,
                    'if ' in code_lower or 'elif ' in code_lower,
                    'for ' in code_lower or 'while ' in code_lower,
                    'print(' in code_lower,
                    'input(' in code_lower,
                    'return ' in code_lower,
                    '=' in code and code.count('=') > code.count('==')
                ]
                structure_bonus = sum(python_elements) * 0.05  # 5% por cada elemento

            elif language == "SQL":
                # Bonificación por comandos SQL (incluso mal escritos)
                sql_commands = [
                    'select' in code_lower or 'selec' in code_lower,
                    'from' in code_lower or 'fro' in code_lower,
                    'where' in code_lower,
                    'insert' in code_lower,
                    'update' in code_lower,
                    'delete' in code_lower,
                    'join' in code_lower or 'joi' in code_lower,
                    'order by' in code_lower,
                    'group by' in code_lower
                ]
                structure_bonus = sum(sql_commands) * 0.05

            elif language == "NoSQL":
                # Bonificación por operaciones NoSQL/MongoDB
                nosql_operations = [
                    'db.' in code,
                    'find(' in code_lower,
                    'aggregate(' in code_lower,
                    'insert' in code_lower,
                    'update' in code_lower,
                    'delete' in code_lower,
                    '$match' in code,
                    '$group' in code,
                    '$project' in code,
                    '$sort' in code
                ]
                structure_bonus = sum(nosql_operations) * 0.05

            elif language == "JavaScript":
                # Bonificación por elementos JavaScript
                js_elements = [
                    'function' in code_lower or '=>' in code,
                    'const ' in code_lower or 'let ' in code_lower or 'var ' in code_lower,
                    'if ' in code_lower or 'else' in code_lower,
                    'for ' in code_lower or 'while ' in code_lower,
                    'return ' in code_lower,
                    '.map(' in code or '.filter(' in code or '.reduce(' in code,
                    'console.log' in code_lower
                ]
                structure_bonus = sum(js_elements) * 0.05

            elif language == "Java":
                # Bonificación por elementos Java
                java_elements = [
                    'public class' in code_lower,
                    'public static' in code_lower,
                    'void ' in code_lower or 'int ' in code_lower or 'String ' in code_lower,
                    'if ' in code_lower or 'else' in code_lower,
                    'for ' in code_lower or 'while ' in code_lower,
                    'return ' in code_lower,
                    'System.out.println' in code
                ]
                structure_bonus = sum(java_elements) * 0.05

            elif language == "C++":
                # Bonificación por elementos C++
                cpp_elements = [
                    '#include' in code,
                    'int main' in code_lower or 'void main' in code_lower,
                    'cout' in code_lower or 'cin' in code_lower,
                    'if ' in code_lower or 'else' in code_lower,
                    'for ' in code_lower or 'while ' in code_lower,
                    'return ' in code_lower
                ]
                structure_bonus = sum(cpp_elements) * 0.05

            elif language == "HTML/CSS":
                # Bonificación por elementos HTML/CSS
                html_css_elements = [
                    '<html' in code_lower or '<!doctype' in code_lower,
                    '<head' in code_lower or '<body' in code_lower,
                    '<div' in code_lower or '<span' in code_lower,
                    'class=' in code_lower or 'id=' in code_lower,
                    '<style' in code_lower or '.css' in code_lower,
                    '{' in code and '}' in code and ':' in code  # CSS rules
                ]
                structure_bonus = sum(html_css_elements) * 0.05

            # 5. Calcular score final
            final_score = base_relevance + structure_bonus

            # Asegurar que esté en rango [0.0, 1.0]
            return min(1.0, max(0.0, final_score))


    
    def _validate_consistency(self, score, feedback, code, criteria, language):
        """Valida consistencia entre puntuación y retroalimentación"""
        feedback_lower = feedback.lower()
        
        # Indicadores de retroalimentación completamente positiva
        positive_indicators = [
            "correcto", "excelente", "perfecto", "bien estructurado", 
            "lógica clara", "cumple todos los requisitos", "implementación correcta",
            "funciona correctamente", "solución válida", "código correcto",
            "eficiente", "directa", "válida y funcional", "sintaxis correcta"
        ]
        
        # Indicadores de problemas (más específicos para evitar falsos positivos)
        negative_indicators = [
            "error de", "incorrecto", "problema con", "falta de", "debería ser", "mejorar el",
            "no funciona", "inválido", "malformado", "inconsistente", "falla en",
            "sintaxis incorrecta", "lógica incorrecta", "no resuelve"
        ]
        
        # Frases que parecen negativas pero son positivas
        false_negatives = [
            "no hay errores", "no tiene errores", "sin errores", "no presenta problemas",
            "no hay ineficiencias", "sin ineficiencias", "no hay problemas"
        ]
        
        # Primero, verificar frases que parecen negativas pero son positivas
        for false_neg in false_negatives:
            if false_neg in feedback_lower:
                positive_indicators.append(false_neg)
        
        # Contar indicadores positivos y negativos (excluyendo falsos negativos)
        positive_count = sum(1 for indicator in positive_indicators if indicator in feedback_lower)
        
        # Para negativos, verificar que no sean parte de frases positivas
        negative_count = 0
        for indicator in negative_indicators:
            if indicator in feedback_lower:
                # Verificar que no sea parte de una frase positiva
                is_false_negative = any(false_neg in feedback_lower and indicator in false_neg for false_neg in false_negatives)
                if not is_false_negative:
                    negative_count += 1
        
        # Casos específicos de inconsistencia
        
        # Caso 1: Retroalimentación completamente positiva pero puntuación < 10
        if positive_count >= 3 and negative_count == 0 and score < 10:
            return 10, f"Ajustado a 10/10: retroalimentación completamente positiva ({positive_count} indicadores positivos, 0 negativos)"
        
        # Caso 2: Retroalimentación muy positiva pero puntuación baja
        if positive_count >= 4 and negative_count <= 1 and score < 8:
            return 9, f"Ajustado a 9/10: retroalimentación mayormente positiva ({positive_count} positivos vs {negative_count} negativos)"
        
        # Caso 3: Retroalimentación negativa pero puntuación alta
        if negative_count >= 2 and positive_count <= 1 and score >= 9:
            return 6, f"Ajustado a 6/10: retroalimentación indica problemas ({negative_count} indicadores negativos)"
        
        # Caso 4: Validación específica para el problema reportado
        # Si la retroalimentación habla de características que no están en el código
        if self._feedback_mentions_missing_features(feedback, code, criteria):
            return 3, "Ajustado a 3/10: la retroalimentación menciona características que no están presentes en el código"
        
        return score, None  # Sin ajuste necesario
    
    def _feedback_mentions_missing_features(self, feedback, code, criteria):
        """Detecta si la retroalimentación menciona características que no están en el código"""
        feedback_lower = feedback.lower()
        code_lower = code.lower()
        
        # Características mencionadas en retroalimentación que deberían estar en el código
        feature_checks = [
            ("jsonpath", ["jsonpath", "$."], "JSONPath"),
            ("manejo de errores", ["try", "catch", "error"], "manejo de errores"),
            ("pipeline", ["pipeline", "aggregate"], "pipeline de datos"),
            ("número 67", ["67"], "número 67"),
            ("timestamp", ["timestamp", "date"], "timestamp"),
            ("hashtag", ["hashtag", "#"], "hashtag")
        ]
        
        missing_features = 0
        for feedback_term, code_terms, feature_name in feature_checks:
            if feedback_term in feedback_lower:
                if not any(term in code_lower for term in code_terms):
                    missing_features += 1
        
        # Si menciona 2 o más características que no están en el código
        return missing_features >= 2
    
    def _log_consistency_adjustment(self, original_score, corrected_score, feedback, reason, language):
        """Registra ajustes de consistencia para monitoreo"""
        try:
            adjustment_log = {
                'timestamp': datetime.now().isoformat(),
                'language': language,
                'original_score': original_score,
                'corrected_score': corrected_score,
                'reason': reason,
                'feedback_snippet': feedback[:100] + "..." if len(feedback) > 100 else feedback
            }
            
            # En un sistema real, esto se guardaría en base de datos
            # Por ahora, solo lo registramos en memoria para debugging
            if not hasattr(self, 'consistency_adjustments'):
                self.consistency_adjustments = []
            
            self.consistency_adjustments.append(adjustment_log)
            
            # Limitar a últimos 100 ajustes para evitar uso excesivo de memoria
            if len(self.consistency_adjustments) > 100:
                self.consistency_adjustments = self.consistency_adjustments[-100:]
                
        except Exception as e:
            # No fallar la evaluación por problemas de logging
            pass
    
    def generate_exam(self, text, n_questions=4, q_type="multiple_choice", n_options=4):
        # Forzar 4 preguntas de opción múltiple (no de programación)
        n_questions = 4
        q_type = "multiple_choice"
        
        if not self.model:
            return self._generate_fallback_questions(text, n_questions)
        
        try:
            # Prompt mejorado para generar preguntas teóricas de opción múltiple
            prompt = f"""
            Basándote en el siguiente texto, crea EXACTAMENTE {n_questions} preguntas de opción múltiple (NO de programación).
            
            TEXTO:
            {text[:800]}
            
            REQUISITOS:
            - {n_questions} preguntas teóricas sobre conceptos, definiciones o comprensión
            - NO incluir preguntas de código o programación
            - Cada pregunta debe tener {n_options} opciones
            - Las opciones deben ser claras y diferenciables
            - Solo UNA opción correcta por pregunta
            
            FORMATO JSON OBLIGATORIO:
            [
                {{
                    "question": "¿Pregunta teórica sobre el contenido?",
                    "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
                    "correct_index": 0,
                    "points": 5,
                    "type": "multiple_choice"
                }}
            ]
            
            Responde SOLO con el JSON de las {n_questions} preguntas:
            """
            
            response = self.call_with_retry(
                prompt, 
                max_retries=2,
                operation_type='default'
            )
            
            if "Error" in response or "Cuota" in response or "agotada" in response:
                st.warning("[!] Cuota de IA agotada. Generando preguntas básicas...")
                return self._generate_fallback_questions(text, n_questions)
            
            result = self.extract_json_from_response(response, 'list')
            
            if isinstance(result, list) and len(result) > 0:
                # Asegurar que tengamos exactamente n_questions preguntas
                result = result[:n_questions]
                
                # Completar si faltan preguntas
                while len(result) < n_questions:
                    result.append({
                        "question": f"Pregunta {len(result) + 1} sobre el contenido",
                        "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
                        "correct_index": 0,
                        "points": 5,
                        "type": "multiple_choice"
                    })
                
                # Validar y completar campos faltantes
                for q in result:
                    if 'type' not in q: 
                        q['type'] = "multiple_choice"
                    if 'options' not in q or len(q['options']) < n_options: 
                        q['options'] = [f"Opción {chr(65+i)}" for i in range(n_options)]
                    if 'points' not in q: 
                        q['points'] = 5
                    if 'correct_index' not in q: 
                        q['correct_index'] = 0
                    # Asegurar que correct_index esté en rango válido
                    if q['correct_index'] >= len(q['options']):
                        q['correct_index'] = 0
                
                return result
            else:
                return self._generate_fallback_questions(text, n_questions)
                
        except Exception as e:
            print(f"[ERROR] Error generando examen: {e}")
            return self._generate_fallback_questions(text, n_questions)
    
    def _generate_fallback_questions(self, text, n_questions=4):
        """Genera preguntas básicas cuando la IA no está disponible"""
        st.info("[INFO] Generando preguntas básicas (sin IA) debido a límites de cuota")
        
        fallback_questions = []
        
        # Extraer algunas palabras del texto para hacer preguntas más relevantes
        words = [w for w in text.split() if len(w) > 4][:10]
        
        for i in range(n_questions):
            if i < len(words):
                keyword = words[i]
                question_text = f"¿Cuál de las siguientes opciones está relacionada con '{keyword}' según el contenido?"
            else:
                question_text = f"Pregunta {i+1} sobre el contenido proporcionado"
            
            question = {
                "question": question_text,
                "options": [
                    "Revisar el contenido proporcionado",
                    "Estudiar el material completo", 
                    "Consultar fuentes adicionales",
                    "Analizar el contexto dado"
                ],
                "correct_index": 0,
                "points": 5,
                "type": "multiple_choice"
            }
            fallback_questions.append(question)
        
        return fallback_questions

    def ai_generate_exam_from_text(self, ctx, nq, no):
        return self.generate_exam(ctx, nq, "multiple_choice", no)
    
    # ========== MÉTODOS PARA ACADEMIA PERSONAL IA ==========
    
    def generate_level_assessment(self, language, level="mixed"):
        """Genera un examen de evaluación de nivel usando el banco de preguntas"""
        try:
            # Intentar usar el banco de preguntas primero
            from utils_question_bank import QuestionBank, generate_level_assessment_from_bank
            
            question_bank = QuestionBank()
            question_bank.load()
            
            # Generar 10 preguntas del banco
            questions = generate_level_assessment_from_bank(language, question_bank)
            
            if questions and len(questions) >= 10:
                print(f"✅ Generadas {len(questions)} preguntas del banco para {language}")
                return questions
            else:
                print(f"⚠️ Solo se generaron {len(questions)} preguntas del banco, usando fallback")
                return self._generate_comprehensive_fallback_assessment(language)
                
        except Exception as e:
            print(f"❌ Error generando evaluación del banco: {e}")
            # Si falla, usar el método anterior con IA
            if not self.model:
                return self._generate_fallback_assessment(language)
            
            try:
                prompt = f"""
                Crea un examen COMPLETO de evaluación de nivel para {language}.
                
                REQUISITOS OBLIGATORIOS:
                - EXACTAMENTE 10 preguntas ÚNICAS Y DIFERENTES
                - Distribución: 3-4 principiante, 3-4 intermedio, 3 avanzado
                - Cubrir TODOS estos temas obligatorios para {language}:
                  * Sintaxis básica y variables
                  * Estructuras de control (if, for, while)
                  * Funciones y parámetros
                  * Estructuras de datos (arrays, objetos, etc.)
                  * Conceptos avanzados específicos del lenguaje
                
                FORMATO JSON OBLIGATORIO:
                [
                    {{
                        "question": "Pregunta específica y detallada sobre {language}",
                        "options": ["Opción A detallada", "Opción B detallada", "Opción C detallada", "Opción D detallada"],
                        "correct_index": 0,
                        "level": "principiante|intermedio|avanzado",
                        "topic": "sintaxis|variables|funciones|estructuras|control",
                        "explanation": "Explicación detallada",
                        "points": 1,
                        "code_example": "Código de ejemplo si aplica"
                    }}
                ]
                
                IMPORTANTE: 
                - Cada pregunta debe ser ESPECÍFICA para {language}
                - Incluir ejemplos de código reales cuando sea relevante
                - NO REPETIR PREGUNTAS NI CONCEPTOS
                """
                
                response = self.call_with_retry(prompt)
                result = self.extract_json_from_response(response, 'list')
                
                if isinstance(result, list) and len(result) >= 10:
                    # Tomar solo las primeras 10 preguntas
                    return result[:10]
                else:
                    return self._generate_comprehensive_fallback_assessment(language)
                    
            except Exception as e2:
                print(f"❌ Error generando con IA: {e2}")
                return self._generate_comprehensive_fallback_assessment(language)
    
    def _generate_comprehensive_fallback_assessment(self, language):
        """Genera evaluación completa cuando la IA no está disponible"""
        assessments = {
            "Python": [
                # Nivel Principiante (5 preguntas)
                {
                    "question": "?Cuál es la sintaxis correcta para definir una función en Python?",
                    "options": ["def mi_funcion():", "function mi_funcion():", "func mi_funcion():", "define mi_funcion():"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "funciones",
                    "explanation": "En Python se usa 'def' seguido del nombre de la función y dos puntos",
                    "points": 1,
                    "code_example": "def saludar():\n    print('Hola')"
                },
                {
                    "question": "?Qué tipo de dato es [1, 2, 3] en Python?",
                    "options": ["Tupla", "Lista", "Diccionario", "Set"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "estructuras",
                    "explanation": "Los corchetes [] definen listas en Python, que son mutables y ordenadas",
                    "points": 1,
                    "code_example": "mi_lista = [1, 2, 3]"
                },
                {
                    "question": "?Cómo se declara una variable en Python?",
                    "options": ["var nombre = 'Juan'", "nombre = 'Juan'", "string nombre = 'Juan'", "declare nombre = 'Juan'"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "Python usa tipado dinámico, solo se asigna el valor directamente",
                    "points": 1,
                    "code_example": "nombre = 'Juan'\nedad = 25"
                },
                {
                    "question": "?Cuál es la salida de: print(len('Python'))?",
                    "options": ["5", "6", "7", "Error"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "len() cuenta los caracteres en la cadena 'Python', que tiene 6 letras",
                    "points": 1,
                    "code_example": "print(len('Python'))  # Salida: 6"
                },
                {
                    "question": "?Cómo se escribe un comentario en Python?",
                    "options": ["// Comentario", "/* Comentario */", "# Comentario", "<!-- Comentario -->"],
                    "correct_index": 2,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "En Python los comentarios de línea se escriben con #",
                    "points": 1,
                    "code_example": "# Este es un comentario\nprint('Hola')  # Comentario al final"
                },
                
                # Nivel Intermedio (5 preguntas)
                {
                    "question": "?Qué hace el siguiente código?\nfor i in range(3):\n    print(i)",
                    "options": ["Imprime 1, 2, 3", "Imprime 0, 1, 2", "Imprime 3 veces 'i'", "Da error"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "control",
                    "explanation": "range(3) genera números del 0 al 2 (no incluye el 3)",
                    "points": 1,
                    "code_example": "for i in range(3):\n    print(i)\n# Salida: 0, 1, 2"
                },
                {
                    "question": "?Cuál es la diferencia entre '==' y 'is' en Python?",
                    "options": ["No hay diferencia", "'==' compara valores, 'is' compara identidad", "'is' compara valores, '==' compara identidad", "Ambos son obsoletos"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "'==' compara si los valores son iguales, 'is' compara si son el mismo objeto en memoria",
                    "points": 1,
                    "code_example": "a = [1, 2]\nb = [1, 2]\nprint(a == b)  # True\nprint(a is b)  # False"
                },
                {
                    "question": "?Qué es una list comprehension en Python?",
                    "options": ["Una función especial", "Una forma concisa de crear listas", "Un tipo de bucle", "Un método de las listas"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "estructuras",
                    "explanation": "Las list comprehensions permiten crear listas de forma concisa en una sola línea",
                    "points": 1,
                    "code_example": "cuadrados = [x**2 for x in range(5)]\n# Resultado: [0, 1, 4, 9, 16]"
                },
                {
                    "question": "?Cómo se maneja una excepción en Python?",
                    "options": ["catch/throw", "try/except", "handle/error", "attempt/fail"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "debugging",
                    "explanation": "Python usa try/except para manejar excepciones",
                    "points": 1,
                    "code_example": "try:\n    resultado = 10/0\nexcept ZeroDivisionError:\n    print('No se puede dividir por cero')"
                },
                {
                    "question": "?Qué hace el método .append() en una lista?",
                    "options": ["Elimina el último elemento", "Añade un elemento al final", "Ordena la lista", "Crea una nueva lista"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "estructuras",
                    "explanation": ".append() añade un elemento al final de la lista, modificándola in-place",
                    "points": 1,
                    "code_example": "lista = [1, 2, 3]\nlista.append(4)\nprint(lista)  # [1, 2, 3, 4]"
                },
                
                # Nivel Avanzado (5 preguntas)
                {
                    "question": "?Qué es un decorador en Python?",
                    "options": ["Una función que modifica otra función", "Un tipo de variable", "Un método especial", "Una librería externa"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los decoradores son funciones que modifican el comportamiento de otras funciones",
                    "points": 1,
                    "code_example": "@mi_decorador\ndef mi_funcion():\n    pass"
                },
                {
                    "question": "?Cuál es la diferencia entre *args y **kwargs?",
                    "options": ["No hay diferencia", "*args para argumentos posicionales, **kwargs para argumentos con nombre", "**kwargs para listas, *args para diccionarios", "Son sinónimos"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "funciones",
                    "explanation": "*args captura argumentos posicionales variables, **kwargs captura argumentos con nombre variables",
                    "points": 1,
                    "code_example": "def funcion(*args, **kwargs):\n    print(args, kwargs)\nfuncion(1, 2, nombre='Juan')"
                },
                {
                    "question": "?Qué es el GIL (Global Interpreter Lock) en Python?",
                    "options": ["Un tipo de variable", "Un mecanismo que permite solo un hilo ejecutar código Python a la vez", "Una librería de threading", "Un error común"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "El GIL es un mutex que protege el acceso a objetos Python, limitando la ejecución a un hilo a la vez",
                    "points": 1,
                    "code_example": "# El GIL afecta el rendimiento en aplicaciones multi-hilo"
                },
                {
                    "question": "?Qué hace yield en Python?",
                    "options": ["Termina la función", "Crea un generador", "Importa un módulo", "Define una clase"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "yield convierte una función en un generador, pausando la ejecución y devolviendo un valor",
                    "points": 1,
                    "code_example": "def contador():\n    for i in range(3):\n        yield i\nfor num in contador():\n    print(num)"
                },
                {
                    "question": "?Cuál es la complejidad temporal de buscar un elemento en un diccionario Python?",
                    "options": ["O(n)", "O(log n)", "O(1) promedio", "O(n²)"],
                    "correct_index": 2,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los diccionarios en Python usan hash tables, dando acceso O(1) en promedio",
                    "points": 1,
                    "code_example": "# Acceso rápido por clave\ndiccionario = {'clave': 'valor'}\nvalor = diccionario['clave']  # O(1)"
                }
            ],
            
            "JavaScript": [
                # Principiante
                {
                    "question": "?Cuál es la sintaxis correcta para declarar una variable en JavaScript?",
                    "options": ["var nombre;", "variable nombre;", "declare nombre;", "name nombre;"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "En JavaScript se usa 'var', 'let' o 'const' para declarar variables",
                    "points": 1,
                    "code_example": "var nombre = 'Juan';\nlet edad = 25;\nconst PI = 3.14;"
                },
                {
                    "question": "?Cómo se define una función en JavaScript?",
                    "options": ["def function() {}", "function nombre() {}", "func nombre() {}", "define nombre() {}"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "funciones",
                    "explanation": "Las funciones en JavaScript se definen con la palabra clave 'function'",
                    "points": 1,
                    "code_example": "function saludar() {\n    console.log('Hola');\n}"
                },
                            ],
            
            "HTML/CSS": [
                # Principiante
                {
                    "question": "?Cuál es la estructura básica de un documento HTML?",
                    "options": ["<html><head></head><body></body></html>", "<document><header></header><content></content></document>", "<page><top></top><main></main></page>", "<web><title></title><text></text></web>"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "La estructura básica HTML incluye las etiquetas html, head y body",
                    "points": 1,
                    "code_example": "<!DOCTYPE html>\n<html>\n<head><title>Mi página</title></head>\n<body><h1>Hola</h1></body>\n</html>"
                },
                {
                    "question": "?Cómo se aplica CSS a un elemento HTML?",
                    "options": ["<p css='color: red'>Texto</p>", "<p style='color: red'>Texto</p>", "<p color='red'>Texto</p>", "<p design='color: red'>Texto</p>"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "El atributo 'style' se usa para aplicar CSS inline a elementos HTML",
                    "points": 1,
                    "code_example": "<p style='color: red; font-size: 16px;'>Texto rojo</p>"
                },
                {
                    "question": "?Qué etiqueta se usa para crear un enlace en HTML?",
                    "options": ["<link>", "<a>", "<url>", "<href>"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "estructuras",
                    "explanation": "La etiqueta <a> con el atributo href se usa para crear enlaces",
                    "points": 1,
                    "code_example": "<a href='https://ejemplo.com'>Visitar sitio</a>"
                },
                {
                    "question": "?Cómo se define una clase CSS?",
                    "options": [".mi-clase { }", "#mi-clase { }", "mi-clase { }", "class mi-clase { }"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "Las clases CSS se definen con un punto (.) seguido del nombre de la clase",
                    "points": 1,
                    "code_example": ".mi-clase {\n    color: blue;\n    font-size: 18px;\n}"
                },
                {
                    "question": "?Qué propiedad CSS se usa para cambiar el color de fondo?",
                    "options": ["color", "background-color", "bg-color", "back-color"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "La propiedad background-color establece el color de fondo de un elemento",
                    "points": 1,
                    "code_example": "div {\n    background-color: #f0f0f0;\n}"
                },
                
                # Intermedio
                {
                    "question": "?Qué es Flexbox en CSS?",
                    "options": ["Un tipo de imagen", "Un sistema de layout unidimensional", "Una librería JavaScript", "Un framework CSS"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Flexbox es un método de layout que permite organizar elementos en una dimensión (fila o columna)",
                    "points": 1,
                    "code_example": ".container {\n    display: flex;\n    justify-content: center;\n    align-items: center;\n}"
                },
                {
                    "question": "?Cuál es la diferencia entre margin y padding?",
                    "options": ["No hay diferencia", "Margin es espacio exterior, padding es espacio interior", "Padding es espacio exterior, margin es espacio interior", "Ambos son obsoletos"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "estructuras",
                    "explanation": "Margin crea espacio fuera del elemento, padding crea espacio dentro del elemento",
                    "points": 1,
                    "code_example": ".elemento {\n    margin: 20px;    /* Espacio exterior */\n    padding: 10px;   /* Espacio interior */\n}"
                },
                {
                    "question": "?Qué hace la propiedad CSS 'position: absolute'?",
                    "options": ["Posiciona relativo al padre", "Posiciona relativo al viewport", "Posiciona relativo al ancestro posicionado más cercano", "No hace nada"],
                    "correct_index": 2,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "position: absolute posiciona el elemento relativo al ancestro posicionado más cercano",
                    "points": 1,
                    "code_example": ".absoluto {\n    position: absolute;\n    top: 10px;\n    left: 20px;\n}"
                },
                {
                    "question": "?Cómo se hace una consulta de medios (media query) en CSS?",
                    "options": ["@media (max-width: 768px) { }", "@query (max-width: 768px) { }", "@screen (max-width: 768px) { }", "@responsive (max-width: 768px) { }"],
                    "correct_index": 0,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "@media se usa para aplicar estilos según características del dispositivo",
                    "points": 1,
                    "code_example": "@media (max-width: 768px) {\n    .container { width: 100%; }\n}"
                },
                {
                    "question": "?Qué es CSS Grid?",
                    "options": ["Un framework", "Un sistema de layout bidimensional", "Una librería", "Un preprocesador"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "CSS Grid es un sistema de layout que permite crear diseños complejos en dos dimensiones",
                    "points": 1,
                    "code_example": ".grid {\n    display: grid;\n    grid-template-columns: 1fr 2fr 1fr;\n    gap: 20px;\n}"
                },
                
                # Avanzado
                {
                    "question": "?Qué son las Custom Properties (variables CSS)?",
                    "options": ["Propiedades inventadas", "Variables que se pueden reutilizar en CSS", "Propiedades de JavaScript", "Atributos HTML"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Las Custom Properties permiten definir variables reutilizables en CSS",
                    "points": 1,
                    "code_example": ":root {\n    --color-primario: #007bff;\n}\n.boton { color: var(--color-primario); }"
                },
                {
                    "question": "?Qué es el Critical Rendering Path?",
                    "options": ["Una ruta de archivos", "El proceso de renderizado inicial de una página", "Un framework CSS", "Una técnica de animación"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Es la secuencia de pasos que el navegador sigue para renderizar una página web",
                    "points": 1,
                    "code_example": "<!-- CSS crítico inline para mejorar rendimiento -->"
                },
                {
                    "question": "?Qué es CSS-in-JS?",
                    "options": ["CSS dentro de archivos JavaScript", "Una técnica para escribir CSS con JavaScript", "Un error de sintaxis", "Un preprocesador"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "CSS-in-JS permite escribir estilos CSS usando JavaScript, común en React",
                    "points": 1,
                    "code_example": "const estilos = { color: 'red', fontSize: '16px' };"
                },
                {
                    "question": "?Qué es el Box Model en CSS?",
                    "options": ["Un tipo de contenedor", "El modelo que describe cómo se calculan las dimensiones de los elementos", "Una técnica de layout", "Un framework"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "El Box Model define cómo se calculan el ancho y alto total de un elemento (content + padding + border + margin)",
                    "points": 1,
                    "code_example": "/* Total width = width + padding + border + margin */"
                },
                {
                    "question": "?Qué hace 'transform: translateZ(0)' en CSS?",
                    "options": ["No hace nada", "Fuerza aceleración por hardware", "Mueve el elemento", "Cambia la opacidad"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "translateZ(0) fuerza al navegador a usar aceleración por hardware para mejorar el rendimiento",
                    "points": 1,
                    "code_example": ".optimizado {\n    transform: translateZ(0);\n    /* Activa aceleración GPU */\n}"
                }
            ],
            
            "Java": [
                # Principiante
                {
                    "question": "?Cuál es la sintaxis correcta para el método main en Java?",
                    "options": ["public static void main(String[] args)", "public void main(String args)", "static void main(String[] args)", "public main(String[] args)"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "El método main debe ser public, static, void y recibir String[] args",
                    "points": 1,
                    "code_example": "public class MiClase {\n    public static void main(String[] args) {\n        System.out.println(\"Hola\");\n    }\n}"
                },
                {
                    "question": "?Cómo se declara una variable entera en Java?",
                    "options": ["int numero;", "integer numero;", "var numero;", "number numero;"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "En Java se usa 'int' para declarar variables enteras",
                    "points": 1,
                    "code_example": "int edad = 25;\nint contador = 0;"
                },
                {
                    "question": "?Qué palabra clave se usa para crear una clase en Java?",
                    "options": ["class", "Class", "define", "create"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "La palabra clave 'class' se usa para definir clases en Java",
                    "points": 1,
                    "code_example": "public class Persona {\n    private String nombre;\n    private int edad;\n}"
                },
                {
                    "question": "?Cómo se imprime texto en la consola en Java?",
                    "options": ["print(\"texto\");", "System.out.println(\"texto\");", "console.log(\"texto\");", "echo \"texto\";"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "System.out.println() es el método estándar para imprimir en Java",
                    "points": 1,
                    "code_example": "System.out.println(\"Hola Mundo\");\nSystem.out.print(\"Sin salto de línea\");"
                },
                {
                    "question": "?Cuál es el modificador de acceso más restrictivo en Java?",
                    "options": ["public", "protected", "private", "default"],
                    "correct_index": 2,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "private es el modificador más restrictivo, solo accesible dentro de la misma clase",
                    "points": 1,
                    "code_example": "public class Ejemplo {\n    private int valor;  // Solo accesible aquí\n}"
                },
                
                # Intermedio
                {
                    "question": "?Qué es la herencia en Java?",
                    "options": ["Una forma de crear objetos", "Un mecanismo donde una clase adquiere propiedades de otra", "Un tipo de variable", "Un método especial"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "La herencia permite que una clase herede atributos y métodos de otra clase",
                    "points": 1,
                    "code_example": "class Animal { }\nclass Perro extends Animal { }"
                },
                {
                    "question": "?Cuál es la diferencia entre == y .equals() en Java?",
                    "options": ["No hay diferencia", "== compara referencias, .equals() compara contenido", ".equals() compara referencias, == compara contenido", "Ambos son obsoletos"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "== compara referencias de objetos, .equals() compara el contenido",
                    "points": 1,
                    "code_example": "String a = new String(\"hola\");\nString b = new String(\"hola\");\nSystem.out.println(a == b);      // false\nSystem.out.println(a.equals(b)); // true"
                },
                {
                    "question": "?Qué es un constructor en Java?",
                    "options": ["Un método que destruye objetos", "Un método especial que inicializa objetos", "Una variable especial", "Un tipo de clase"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "funciones",
                    "explanation": "Un constructor es un método especial que se ejecuta al crear una instancia de la clase",
                    "points": 1,
                    "code_example": "public class Persona {\n    public Persona(String nombre) {\n        this.nombre = nombre;\n    }\n}"
                },
                {
                    "question": "?Qué hace la palabra clave 'static' en Java?",
                    "options": ["Hace que la variable sea constante", "Hace que el miembro pertenezca a la clase, no a la instancia", "Hace que la clase sea inmutable", "No hace nada"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "static hace que el miembro pertenezca a la clase y se pueda acceder sin crear una instancia",
                    "points": 1,
                    "code_example": "class Contador {\n    static int total = 0;  // Compartido por todas las instancias\n}"
                },
                {
                    "question": "?Cómo se maneja una excepción en Java?",
                    "options": ["try/catch", "handle/error", "attempt/fail", "check/fix"],
                    "correct_index": 0,
                    "level": "intermedio",
                    "topic": "debugging",
                    "explanation": "Java usa bloques try/catch para manejar excepciones",
                    "points": 1,
                    "code_example": "try {\n    int resultado = 10/0;\n} catch (ArithmeticException e) {\n    System.out.println(\"Error: \" + e.getMessage());\n}"
                },
                
                # Avanzado
                {
                    "question": "?Qué es el polimorfismo en Java?",
                    "options": ["Tener múltiples constructores", "La capacidad de un objeto de tomar múltiples formas", "Usar múltiples clases", "Tener múltiples métodos"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "El polimorfismo permite que objetos de diferentes clases sean tratados como objetos de una clase base común",
                    "points": 1,
                    "code_example": "Animal animal = new Perro();  // Polimorfismo\nanimal.hacerSonido();  // Llama al método de Perro"
                },
                {
                    "question": "?Qué es una interfaz en Java?",
                    "options": ["Una clase especial", "Un contrato que define qué métodos debe implementar una clase", "Un tipo de variable", "Un método abstracto"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Una interfaz define un contrato con métodos que las clases implementadoras deben definir",
                    "points": 1,
                    "code_example": "interface Volador {\n    void volar();\n}\nclass Pajaro implements Volador {\n    public void volar() { }\n}"
                },
                {
                    "question": "?Qué son los Generics en Java?",
                    "options": ["Métodos genéricos", "Una forma de crear código reutilizable con tipos parametrizados", "Variables especiales", "Clases abstractas"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los Generics permiten escribir código que funciona con diferentes tipos de datos de forma segura",
                    "points": 1,
                    "code_example": "List<String> lista = new ArrayList<String>();\nMap<String, Integer> mapa = new HashMap<>();"
                },
                {
                    "question": "?Qué es el Garbage Collector en Java?",
                    "options": ["Un recolector de basura automático que libera memoria", "Un método para limpiar código", "Una herramienta de debugging", "Un tipo de excepción"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "El Garbage Collector automáticamente libera memoria de objetos que ya no son referenciados",
                    "points": 1,
                    "code_example": "// El GC libera automáticamente objetos sin referencias\nObject obj = new Object();\nobj = null;  // Elegible para GC"
                },
                {
                    "question": "?Qué es una clase abstracta en Java?",
                    "options": ["Una clase que no se puede instanciar directamente", "Una clase sin métodos", "Una interfaz especial", "Una clase privada"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Una clase abstracta no puede ser instanciada y puede contener métodos abstractos que deben ser implementados por las subclases",
                    "points": 1,
                    "code_example": "abstract class Forma {\n    abstract void dibujar();\n}\nclass Circulo extends Forma {\n    void dibujar() { }\n}"
                }
            ],
            
            "SQL": [
                # Principiante
                {
                    "question": "?Cuál es la sintaxis correcta para seleccionar todos los registros de una tabla?",
                    "options": ["SELECT * FROM tabla;", "GET * FROM tabla;", "FETCH * FROM tabla;", "RETRIEVE * FROM tabla;"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "SELECT * FROM es la sintaxis estándar para seleccionar todos los registros",
                    "points": 1,
                    "code_example": "SELECT * FROM usuarios;"
                },
                {
                    "question": "?Cómo se filtran registros en SQL?",
                    "options": ["FILTER", "WHERE", "IF", "WHEN"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "WHERE se usa para filtrar registros basado en condiciones",
                    "points": 1,
                    "code_example": "SELECT * FROM usuarios WHERE edad > 18;"
                },
                {
                    "question": "?Qué comando se usa para insertar datos en una tabla?",
                    "options": ["ADD", "INSERT", "PUT", "CREATE"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "INSERT INTO se usa para agregar nuevos registros a una tabla",
                    "points": 1,
                    "code_example": "INSERT INTO usuarios (nombre, edad) VALUES ('Juan', 25);"
                },
                {
                    "question": "?Cómo se ordenan los resultados en SQL?",
                    "options": ["SORT BY", "ORDER BY", "ARRANGE BY", "ORGANIZE BY"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "ORDER BY se usa para ordenar los resultados de una consulta",
                    "points": 1,
                    "code_example": "SELECT * FROM usuarios ORDER BY nombre ASC;"
                },
                {
                    "question": "?Qué comando se usa para actualizar registros existentes?",
                    "options": ["MODIFY", "CHANGE", "UPDATE", "ALTER"],
                    "correct_index": 2,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "UPDATE se usa para modificar registros existentes en una tabla",
                    "points": 1,
                    "code_example": "UPDATE usuarios SET edad = 26 WHERE nombre = 'Juan';"
                },
                
                # Intermedio
                {
                    "question": "?Qué es un JOIN en SQL?",
                    "options": ["Una función matemática", "Una operación para combinar datos de múltiples tablas", "Un tipo de índice", "Una restricción"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "JOIN permite combinar registros de dos o más tablas basado en una relación",
                    "points": 1,
                    "code_example": "SELECT u.nombre, p.titulo FROM usuarios u JOIN posts p ON u.id = p.usuario_id;"
                },
                {
                    "question": "?Cuál es la diferencia entre INNER JOIN y LEFT JOIN?",
                    "options": ["No hay diferencia", "INNER JOIN devuelve solo coincidencias, LEFT JOIN incluye todos los registros de la tabla izquierda", "LEFT JOIN es más rápido", "INNER JOIN es obsoleto"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "INNER JOIN solo devuelve registros que coinciden en ambas tablas, LEFT JOIN incluye todos los de la tabla izquierda",
                    "points": 1,
                    "code_example": "-- INNER JOIN: solo coincidencias\nSELECT * FROM usuarios u INNER JOIN pedidos p ON u.id = p.usuario_id;\n-- LEFT JOIN: todos los usuarios, con o sin pedidos\nSELECT * FROM usuarios u LEFT JOIN pedidos p ON u.id = p.usuario_id;"
                },
                {
                    "question": "?Qué hace la función COUNT() en SQL?",
                    "options": ["Suma valores", "Cuenta el número de registros", "Calcula el promedio", "Encuentra el máximo"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "funciones",
                    "explanation": "COUNT() cuenta el número de registros que cumplen una condición",
                    "points": 1,
                    "code_example": "SELECT COUNT(*) FROM usuarios WHERE edad > 18;"
                },
                {
                    "question": "?Para qué se usa GROUP BY?",
                    "options": ["Para ordenar resultados", "Para agrupar registros con valores similares", "Para filtrar datos", "Para unir tablas"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "GROUP BY agrupa registros que tienen valores iguales en columnas especificadas",
                    "points": 1,
                    "code_example": "SELECT ciudad, COUNT(*) FROM usuarios GROUP BY ciudad;"
                },
                {
                    "question": "?Qué es una subconsulta (subquery)?",
                    "options": ["Una consulta dentro de otra consulta", "Una consulta rápida", "Una consulta con errores", "Una consulta simple"],
                    "correct_index": 0,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Una subconsulta es una consulta SQL anidada dentro de otra consulta",
                    "points": 1,
                    "code_example": "SELECT * FROM usuarios WHERE edad > (SELECT AVG(edad) FROM usuarios);"
                },
                
                # Avanzado
                {
                    "question": "?Qué es un índice en bases de datos?",
                    "options": ["Una tabla especial", "Una estructura que mejora la velocidad de consultas", "Un tipo de JOIN", "Una función agregada"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Un índice es una estructura de datos que mejora la velocidad de las operaciones de consulta",
                    "points": 1,
                    "code_example": "CREATE INDEX idx_nombre ON usuarios(nombre);"
                },
                {
                    "question": "?Qué es una transacción en SQL?",
                    "options": ["Una consulta compleja", "Un grupo de operaciones que se ejecutan como una unidad", "Un tipo de tabla", "Una función especial"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Una transacción es un conjunto de operaciones que se ejecutan completamente o no se ejecutan en absoluto",
                    "points": 1,
                    "code_example": "BEGIN TRANSACTION;\nUPDATE cuenta SET saldo = saldo - 100 WHERE id = 1;\nUPDATE cuenta SET saldo = saldo + 100 WHERE id = 2;\nCOMMIT;"
                },
                {
                    "question": "?Qué son las propiedades ACID en bases de datos?",
                    "options": ["Tipos de consultas", "Atomicidad, Consistencia, Aislamiento, Durabilidad", "Funciones matemáticas", "Tipos de índices"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "ACID son las propiedades que garantizan la confiabilidad de las transacciones en bases de datos",
                    "points": 1,
                    "code_example": "-- Atomicidad: todo o nada\n-- Consistencia: estado válido\n-- Aislamiento: transacciones independientes\n-- Durabilidad: cambios permanentes"
                },
                {
                    "question": "?Qué es la normalización de bases de datos?",
                    "options": ["Hacer que los datos sean normales", "Organizar datos para reducir redundancia", "Acelerar consultas", "Crear índices"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "La normalización organiza los datos para minimizar la redundancia y mejorar la integridad",
                    "points": 1,
                    "code_example": "-- 1NF: Eliminar grupos repetitivos\n-- 2NF: Eliminar dependencias parciales\n-- 3NF: Eliminar dependencias transitivas"
                },
                {
                    "question": "?Qué es un procedimiento almacenado?",
                    "options": ["Una consulta guardada", "Un conjunto de instrucciones SQL precompiladas", "Una tabla temporal", "Un tipo de índice"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Un procedimiento almacenado es un conjunto de instrucciones SQL que se almacenan y ejecutan en el servidor",
                    "points": 1,
                    "code_example": "CREATE PROCEDURE ObtenerUsuario(@id INT)\nAS\nBEGIN\n    SELECT * FROM usuarios WHERE id = @id;\nEND"
                }
            ],
            
            "NoSQL": [
                # Principiante
                {
                    "question": "?Qué significa NoSQL?",
                    "options": ["No SQL permitido", "Not Only SQL", "New SQL", "No Structure Query Language"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "NoSQL significa 'Not Only SQL' y se refiere a bases de datos no relacionales",
                    "points": 1,
                    "code_example": "// NoSQL incluye documentos, clave-valor, columnas, grafos"
                },
                {
                    "question": "?Cómo se inserta un documento en MongoDB?",
                    "options": ["db.collection.insert()", "db.collection.insertOne()", "db.collection.add()", "db.collection.create()"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "insertOne() es el método moderno para insertar un documento en MongoDB",
                    "points": 1,
                    "code_example": "db.usuarios.insertOne({ nombre: 'Juan', edad: 25 })"
                },
                {
                    "question": "?Cómo se buscan documentos en MongoDB?",
                    "options": ["db.collection.search()", "db.collection.find()", "db.collection.get()", "db.collection.select()"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "find() es el método principal para buscar documentos en MongoDB",
                    "points": 1,
                    "code_example": "db.usuarios.find({ edad: { $gt: 18 } })"
                },
                {
                    "question": "?Qué formato usan los documentos en MongoDB?",
                    "options": ["XML", "JSON/BSON", "CSV", "SQL"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "estructuras",
                    "explanation": "MongoDB almacena documentos en formato BSON (Binary JSON)",
                    "points": 1,
                    "code_example": "{ _id: ObjectId('...'), nombre: 'Juan', edad: 25, activo: true }"
                },
                {
                    "question": "?Cómo se actualiza un documento en MongoDB?",
                    "options": ["db.collection.modify()", "db.collection.updateOne()", "db.collection.change()", "db.collection.edit()"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "updateOne() actualiza un documento que coincida con el filtro",
                    "points": 1,
                    "code_example": "db.usuarios.updateOne({ nombre: 'Juan' }, { $set: { edad: 26 } })"
                },
                
                # Intermedio
                {
                    "question": "?Qué es el pipeline de agregación en MongoDB?",
                    "options": ["Una tubería de datos", "Una secuencia de operaciones para procesar documentos", "Un tipo de índice", "Una función especial"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "El pipeline de agregación permite procesar documentos a través de múltiples etapas",
                    "points": 1,
                    "code_example": "db.usuarios.aggregate([\n  { $match: { edad: { $gte: 18 } } },\n  { $group: { _id: '$ciudad', total: { $sum: 1 } } }\n])"
                },
                {
                    "question": "?Qué hace el operador $match en MongoDB?",
                    "options": ["Une documentos", "Filtra documentos", "Ordena documentos", "Cuenta documentos"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "$match filtra documentos basado en condiciones, similar a WHERE en SQL",
                    "points": 1,
                    "code_example": "{ $match: { edad: { $gte: 21, $lt: 65 } } }"
                },
                {
                    "question": "?Qué es un índice en MongoDB?",
                    "options": ["Un documento especial", "Una estructura que mejora el rendimiento de consultas", "Un tipo de colección", "Una función agregada"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Los índices en MongoDB mejoran la velocidad de las consultas",
                    "points": 1,
                    "code_example": "db.usuarios.createIndex({ nombre: 1, edad: -1 })"
                },
                {
                    "question": "?Qué hace el operador $group en agregaciones?",
                    "options": ["Filtra documentos", "Agrupa documentos por un campo y aplica operaciones", "Ordena documentos", "Limita resultados"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "$group agrupa documentos por valores de campo y permite operaciones como sum, avg, count",
                    "points": 1,
                    "code_example": "{ $group: { _id: '$departamento', salarioPromedio: { $avg: '$salario' } } }"
                },
                {
                    "question": "?Qué es el sharding en MongoDB?",
                    "options": ["Un tipo de consulta", "Distribución horizontal de datos across múltiples servidores", "Un método de backup", "Un tipo de índice"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Sharding distribuye datos across múltiples máquinas para manejar grandes volúmenes",
                    "points": 1,
                    "code_example": "// Sharding permite escalar horizontalmente\nsh.shardCollection('miDB.usuarios', { _id: 'hashed' })"
                },
                
                # Avanzado
                {
                    "question": "?Qué es la replicación en MongoDB?",
                    "options": ["Copiar consultas", "Mantener múltiples copias de datos para alta disponibilidad", "Duplicar índices", "Repetir operaciones"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "La replicación mantiene copias idénticas de datos en múltiples servidores para redundancia",
                    "points": 1,
                    "code_example": "// Replica Set con primary y secondary nodes\nrs.initiate()"
                },
                {
                    "question": "?Qué es el patrón Embedded vs Referenced en MongoDB?",
                    "options": ["Tipos de consultas", "Estrategias para modelar relaciones entre documentos", "Tipos de índices", "Métodos de agregación"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Embedded incluye datos relacionados en el mismo documento, Referenced los mantiene separados",
                    "points": 1,
                    "code_example": "// Embedded\n{ usuario: 'Juan', direcciones: [{ calle: '123 Main' }] }\n// Referenced\n{ usuario: 'Juan', direccion_ids: [ObjectId('...')] }"
                },
                {
                    "question": "?Qué es el Write Concern en MongoDB?",
                    "options": ["Un tipo de error", "Nivel de confirmación requerido para operaciones de escritura", "Una función de validación", "Un método de consulta"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Write Concern especifica el nivel de confirmación requerido para operaciones de escritura",
                    "points": 1,
                    "code_example": "db.usuarios.insertOne(\n  { nombre: 'Juan' },\n  { writeConcern: { w: 'majority', j: true } }\n)"
                },
                {
                    "question": "?Qué son las transacciones ACID en MongoDB?",
                    "options": ["No existen en MongoDB", "Operaciones que garantizan consistencia across múltiples documentos", "Solo para colecciones individuales", "Un tipo de agregación"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "MongoDB 4.0+ soporta transacciones ACID multi-documento para garantizar consistencia",
                    "points": 1,
                    "code_example": "session.startTransaction()\ntry {\n  db.cuentas.updateOne({ _id: 1 }, { $inc: { saldo: -100 } })\n  db.cuentas.updateOne({ _id: 2 }, { $inc: { saldo: 100 } })\n  session.commitTransaction()\n} catch (error) {\n  session.abortTransaction()\n}"
                },
                {
                    "question": "?Qué es el GridFS en MongoDB?",
                    "options": ["Un tipo de índice", "Sistema para almacenar archivos grandes", "Una función de agregación", "Un método de consulta"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "GridFS permite almacenar archivos que exceden el límite de 16MB de documentos BSON",
                    "points": 1,
                    "code_example": "// GridFS divide archivos grandes en chunks\nmongoimport --db miDB --collection fs.files --file archivo.json"
                }
            ],
            
            "C++": [
                # Principiante
                {
                    "question": "?Cuál es la sintaxis correcta para incluir una librería en C++?",
                    "options": ["#include <iostream>", "#import <iostream>", "#using <iostream>", "#require <iostream>"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "#include se usa para incluir librerías en C++",
                    "points": 1,
                    "code_example": "#include <iostream>\n#include <vector>\n#include <string>"
                },
                {
                    "question": "?Cómo se declara una variable entera en C++?",
                    "options": ["int numero;", "integer numero;", "var numero;", "number numero;"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "En C++ se usa 'int' para declarar variables enteras",
                    "points": 1,
                    "code_example": "int edad = 25;\nint contador = 0;"
                },
                {
                    "question": "?Cuál es la función principal en un programa C++?",
                    "options": ["start()", "main()", "begin()", "run()"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "main() es la función principal donde comienza la ejecución del programa",
                    "points": 1,
                    "code_example": "int main() {\n    std::cout << \"Hola Mundo\";\n    return 0;\n}"
                },
                {
                    "question": "?Cómo se imprime texto en la consola en C++?",
                    "options": ["print(\"texto\");", "std::cout << \"texto\";", "console.log(\"texto\");", "echo \"texto\";"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "std::cout se usa para imprimir en la consola en C++",
                    "points": 1,
                    "code_example": "std::cout << \"Hola \" << \"Mundo\" << std::endl;"
                },
                {
                    "question": "?Qué significa el operador :: en C++?",
                    "options": ["Asignación", "Operador de resolución de ámbito", "Comparación", "Concatenación"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": ":: es el operador de resolución de ámbito, usado para acceder a miembros de namespace o clase",
                    "points": 1,
                    "code_example": "std::cout  // std es el namespace\nClase::metodo()  // metodo de Clase"
                },
                
                # Intermedio
                {
                    "question": "?Qué es un puntero en C++?",
                    "options": ["Un tipo de variable", "Una variable que almacena la dirección de memoria de otra variable", "Una función especial", "Un operador"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Un puntero almacena la dirección de memoria donde se encuentra otra variable",
                    "points": 1,
                    "code_example": "int x = 10;\nint* ptr = &x;  // ptr apunta a x\nstd::cout << *ptr;  // imprime 10"
                },
                {
                    "question": "?Cuál es la diferencia entre new y malloc en C++?",
                    "options": ["No hay diferencia", "new es de C++, malloc es de C", "malloc es más rápido", "new no existe en C++"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "new es el operador de C++ que llama constructores, malloc es la función de C que solo asigna memoria",
                    "points": 1,
                    "code_example": "int* arr1 = new int[10];     // C++\nint* arr2 = (int*)malloc(10 * sizeof(int));  // C"
                },
                {
                    "question": "?Qué es la sobrecarga de funciones en C++?",
                    "options": ["Un error", "Definir múltiples funciones con el mismo nombre pero diferentes parámetros", "Una función muy larga", "Una función recursiva"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "funciones",
                    "explanation": "La sobrecarga permite definir múltiples funciones con el mismo nombre pero diferentes tipos o número de parámetros",
                    "points": 1,
                    "code_example": "void print(int x);\nvoid print(double x);\nvoid print(string x);"
                },
                {
                    "question": "?Qué hace el destructor en C++?",
                    "options": ["Crea objetos", "Libera recursos cuando un objeto es destruido", "Inicializa variables", "Imprime valores"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "El destructor se llama automáticamente cuando un objeto sale de ámbito para liberar recursos",
                    "points": 1,
                    "code_example": "class MiClase {\npublic:\n    ~MiClase() {  // Destructor\n        // Liberar recursos\n    }\n};"
                },
                {
                    "question": "?Qué es la herencia en C++?",
                    "options": ["Copiar código", "Un mecanismo donde una clase deriva de otra", "Una función especial", "Un tipo de variable"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "La herencia permite que una clase derive propiedades y métodos de otra clase",
                    "points": 1,
                    "code_example": "class Animal { };\nclass Perro : public Animal { };"
                },
                
                # Avanzado
                {
                    "question": "?Qué son los templates en C++?",
                    "options": ["Plantillas para crear código genérico", "Archivos de configuración", "Tipos de variables", "Funciones especiales"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los templates permiten escribir código genérico que funciona con diferentes tipos de datos",
                    "points": 1,
                    "code_example": "template<typename T>\nT maximo(T a, T b) {\n    return (a > b) ? a : b;\n}"
                },
                {
                    "question": "?Qué es RAII en C++?",
                    "options": ["Un tipo de error", "Resource Acquisition Is Initialization", "Una librería", "Un compilador"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "RAII es un patrón donde los recursos se adquieren en el constructor y se liberan en el destructor",
                    "points": 1,
                    "code_example": "class FileHandler {\n    FILE* file;\npublic:\n    FileHandler(const char* name) { file = fopen(name, \"r\"); }\n    ~FileHandler() { if(file) fclose(file); }\n};"
                },
                {
                    "question": "?Qué es un smart pointer en C++?",
                    "options": ["Un puntero inteligente que maneja memoria automáticamente", "Un puntero rápido", "Un puntero grande", "Un tipo de variable"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los smart pointers manejan automáticamente la memoria, evitando memory leaks",
                    "points": 1,
                    "code_example": "std::unique_ptr<int> ptr = std::make_unique<int>(42);\nstd::shared_ptr<int> shared = std::make_shared<int>(10);"
                },
                {
                    "question": "?Qué es el polimorfismo virtual en C++?",
                    "options": ["Un error de compilación", "Permite que funciones derivadas sobrescriban funciones base en tiempo de ejecución", "Una función rápida", "Un tipo de herencia"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Las funciones virtuales permiten polimorfismo dinámico, donde la función correcta se llama en tiempo de ejecución",
                    "points": 1,
                    "code_example": "class Base {\npublic:\n    virtual void metodo() { }\n};\nclass Derivada : public Base {\npublic:\n    void metodo() override { }\n};"
                },
                {
                    "question": "?Qué es la STL en C++?",
                    "options": ["Standard Template Library", "Simple Type Library", "System Tool Library", "Static Template Library"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "STL es la librería estándar de templates que incluye contenedores, algoritmos e iteradores",
                    "points": 1,
                    "code_example": "std::vector<int> vec = {1, 2, 3};\nstd::map<string, int> mapa;\nstd::sort(vec.begin(), vec.end());"
                }
            ],
            
            "C#": [
                # Principiante
                {
                    "question": "?Cuál es la sintaxis correcta para el método Main en C#?",
                    "options": ["static void Main(string[] args)", "public main(String[] args)", "void Main(string args)", "static Main(string[] args)"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "El método Main debe ser static void y recibir string[] args",
                    "points": 1,
                    "code_example": "class Program {\n    static void Main(string[] args) {\n        Console.WriteLine(\"Hola\");\n    }\n}"
                },
                {
                    "question": "?Cómo se declara una variable string en C#?",
                    "options": ["string nombre;", "String nombre;", "var nombre;", "text nombre;"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "En C# se usa 'string' (minúscula) para declarar cadenas de texto",
                    "points": 1,
                    "code_example": "string nombre = \"Juan\";\nstring apellido = \"Pérez\";"
                },
                {
                    "question": "?Cómo se imprime texto en la consola en C#?",
                    "options": ["print(\"texto\");", "Console.WriteLine(\"texto\");", "System.out.println(\"texto\");", "echo \"texto\";"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "Console.WriteLine() es el método estándar para imprimir en C#",
                    "points": 1,
                    "code_example": "Console.WriteLine(\"Hola Mundo\");\nConsole.Write(\"Sin salto de línea\");"
                },
                {
                    "question": "?Qué palabra clave se usa para crear una clase en C#?",
                    "options": ["class", "Class", "define", "create"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "La palabra clave 'class' se usa para definir clases en C#",
                    "points": 1,
                    "code_example": "public class Persona {\n    public string Nombre { get; set; }\n    public int Edad { get; set; }\n}"
                },
                {
                    "question": "?Cuál es el modificador de acceso por defecto para miembros de clase en C#?",
                    "options": ["public", "protected", "private", "internal"],
                    "correct_index": 2,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "Los miembros de clase son private por defecto en C#",
                    "points": 1,
                    "code_example": "class Ejemplo {\n    int valor;  // private por defecto\n    public int Publico;\n}"
                },
                
                # Intermedio
                {
                    "question": "?Qué son las propiedades (properties) en C#?",
                    "options": ["Variables especiales", "Métodos que actúan como campos", "Atributos de clase", "Funciones privadas"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Las propiedades proporcionan acceso controlado a campos privados usando get y set",
                    "points": 1,
                    "code_example": "public class Persona {\n    private string _nombre;\n    public string Nombre {\n        get { return _nombre; }\n        set { _nombre = value; }\n    }\n}"
                },
                {
                    "question": "?Qué es LINQ en C#?",
                    "options": ["Una base de datos", "Language Integrated Query", "Una librería gráfica", "Un framework web"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "LINQ permite realizar consultas sobre colecciones usando sintaxis similar a SQL",
                    "points": 1,
                    "code_example": "var adultos = personas.Where(p => p.Edad >= 18).Select(p => p.Nombre);"
                },
                {
                    "question": "?Qué hace la palabra clave 'var' en C#?",
                    "options": ["Crea variables dinámicas", "Permite inferencia de tipos", "Define constantes", "Crea arrays"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "variables",
                    "explanation": "var permite que el compilador infiera automáticamente el tipo de la variable",
                    "points": 1,
                    "code_example": "var numero = 10;        // int\nvar texto = \"hola\";     // string\nvar lista = new List<int>();  // List<int>"
                },
                {
                    "question": "?Qué es un delegate en C#?",
                    "options": ["Una clase especial", "Un tipo que representa referencias a métodos", "Una interfaz", "Un namespace"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Un delegate es un tipo que puede contener referencias a métodos estáticos o de instancia",
                    "points": 1,
                    "code_example": "public delegate void MiDelegate(string mensaje);\nMiDelegate del = Console.WriteLine;\ndel(\"Hola\");"
                },
                {
                    "question": "?Cómo se maneja una excepción en C#?",
                    "options": ["try/catch", "handle/error", "attempt/fail", "check/fix"],
                    "correct_index": 0,
                    "level": "intermedio",
                    "topic": "debugging",
                    "explanation": "C# usa bloques try/catch/finally para manejar excepciones",
                    "points": 1,
                    "code_example": "try {\n    int resultado = 10 / 0;\n} catch (DivideByZeroException ex) {\n    Console.WriteLine($\"Error: {ex.Message}\");\n}"
                },
                
                # Avanzado
                {
                    "question": "?Qué son los Generics en C#?",
                    "options": ["Clases genéricas", "Tipos parametrizados que permiten reutilización de código", "Métodos especiales", "Interfaces avanzadas"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los Generics permiten definir clases y métodos con tipos parametrizados para mayor reutilización",
                    "points": 1,
                    "code_example": "public class Lista<T> {\n    private T[] items;\n    public void Agregar(T item) { }\n}\nLista<int> numeros = new Lista<int>();"
                },
                {
                    "question": "?Qué es async/await en C#?",
                    "options": ["Palabras reservadas", "Patrón para programación asíncrona", "Tipos de variables", "Modificadores de acceso"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "async/await permite escribir código asíncrono de forma más legible y mantenible",
                    "points": 1,
                    "code_example": "public async Task<string> ObtenerDatosAsync() {\n    var resultado = await cliente.GetStringAsync(url);\n    return resultado;\n}"
                },
                {
                    "question": "?Qué es el Garbage Collector en C#?",
                    "options": ["Un recolector automático de memoria", "Un método de limpieza", "Una herramienta de debugging", "Un tipo de excepción"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "El GC automáticamente libera memoria de objetos que ya no son referenciados",
                    "points": 1,
                    "code_example": "// El GC maneja automáticamente la memoria\nObject obj = new Object();\nobj = null;  // Elegible para GC"
                },
                {
                    "question": "?Qué son las Expression Trees en C#?",
                    "options": ["Árboles de datos", "Representaciones de código como estructuras de datos", "Algoritmos de búsqueda", "Patrones de diseño"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Expression Trees representan código como estructuras de datos que pueden ser analizadas y modificadas",
                    "points": 1,
                    "code_example": "Expression<Func<int, bool>> expr = x => x > 5;\n// Se puede analizar la estructura de la expresión"
                },
                {
                    "question": "?Qué es Reflection en C#?",
                    "options": ["Un patrón de diseño", "Capacidad de inspeccionar y manipular tipos en tiempo de ejecución", "Una técnica de optimización", "Un framework"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Reflection permite examinar metadatos de tipos y ejecutar código dinámicamente",
                    "points": 1,
                    "code_example": "Type tipo = typeof(string);\nMethodInfo[] metodos = tipo.GetMethods();\nObject instancia = Activator.CreateInstance(tipo);"
                }
            ],
            
            "PHP": [
                # Principiante
                {
                    "question": "?Cómo se inicia un script PHP?",
                    "options": ["<php>", "<?php", "<script php>", "<?start"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "Los scripts PHP comienzan con la etiqueta <?php",
                    "points": 1,
                    "code_example": "<?php\necho \"Hola Mundo\";\n?>"
                },
                {
                    "question": "?Cómo se declara una variable en PHP?",
                    "options": ["var $nombre;", "$nombre = valor;", "variable nombre;", "declare $nombre;"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "En PHP las variables comienzan con $ y se asignan directamente",
                    "points": 1,
                    "code_example": "$nombre = \"Juan\";\n$edad = 25;\n$activo = true;"
                },
                {
                    "question": "?Cómo se imprime texto en PHP?",
                    "options": ["print(\"texto\");", "echo \"texto\";", "console.log(\"texto\");", "write(\"texto\");"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "echo es la forma más común de imprimir texto en PHP",
                    "points": 1,
                    "code_example": "echo \"Hola Mundo\";\nprint \"También funciona\";\nprintf(\"Formato: %s\", $nombre);"
                },
                {
                    "question": "?Cómo se define una función en PHP?",
                    "options": ["function nombre() { }", "def nombre() { }", "func nombre() { }", "define nombre() { }"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "funciones",
                    "explanation": "Las funciones en PHP se definen con la palabra clave 'function'",
                    "points": 1,
                    "code_example": "function saludar($nombre) {\n    return \"Hola \" . $nombre;\n}\necho saludar(\"Juan\");"
                },
                {
                    "question": "?Cómo se escribe un comentario de línea en PHP?",
                    "options": ["/* comentario */", "// comentario", "# comentario", "Tanto // como #"],
                    "correct_index": 3,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "PHP acepta tanto // como # para comentarios de línea",
                    "points": 1,
                    "code_example": "// Este es un comentario\n# Este también es un comentario\n/* Comentario de bloque */"
                },
                
                # Intermedio
                {
                    "question": "?Qué es un array asociativo en PHP?",
                    "options": ["Un array normal", "Un array que usa claves string en lugar de índices numéricos", "Un array ordenado", "Un array de objetos"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "estructuras",
                    "explanation": "Los arrays asociativos usan claves string para acceder a los valores",
                    "points": 1,
                    "code_example": "$persona = array(\n    \"nombre\" => \"Juan\",\n    \"edad\" => 25,\n    \"ciudad\" => \"Madrid\"\n);\necho $persona[\"nombre\"];"
                },
                {
                    "question": "?Qué hace la función isset() en PHP?",
                    "options": ["Asigna un valor", "Verifica si una variable está definida y no es null", "Elimina una variable", "Convierte tipos"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "funciones",
                    "explanation": "isset() verifica si una variable está definida y tiene un valor diferente de null",
                    "points": 1,
                    "code_example": "if (isset($nombre)) {\n    echo \"La variable nombre está definida\";\n} else {\n    echo \"La variable no existe\";\n}"
                },
                {
                    "question": "?Cuál es la diferencia entre == y === en PHP?",
                    "options": ["No hay diferencia", "== compara valores, === compara valores y tipos", "=== es más rápido", "== es obsoleto"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "== hace comparación con conversión de tipos, === compara valor y tipo exactamente",
                    "points": 1,
                    "code_example": "$a = \"5\";\n$b = 5;\nvar_dump($a == $b);   // true\nvar_dump($a === $b);  // false"
                },
                {
                    "question": "?Qué son las superglobales en PHP?",
                    "options": ["Variables muy grandes", "Variables accesibles desde cualquier ámbito", "Variables del sistema", "Variables constantes"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Las superglobales como $_GET, $_POST, $_SESSION están disponibles en cualquier ámbito",
                    "points": 1,
                    "code_example": "// Superglobales comunes:\n$_GET, $_POST, $_SESSION, $_COOKIE, $_SERVER, $GLOBALS"
                },
                {
                    "question": "?Cómo se incluye un archivo en PHP?",
                    "options": ["import \"archivo.php\";", "include \"archivo.php\";", "#include \"archivo.php\"", "using \"archivo.php\";"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "sintaxis",
                    "explanation": "include, require, include_once y require_once se usan para incluir archivos",
                    "points": 1,
                    "code_example": "include \"config.php\";\nrequire_once \"functions.php\";\ninclude_once \"header.php\";"
                },
                
                # Avanzado
                {
                    "question": "?Qué es un namespace en PHP?",
                    "options": ["Un tipo de variable", "Una forma de encapsular elementos para evitar conflictos de nombres", "Una función especial", "Un array asociativo"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los namespaces permiten agrupar clases, funciones y constantes para evitar conflictos de nombres",
                    "points": 1,
                    "code_example": "namespace MiProyecto\\Modelos;\nclass Usuario { }\n\n// Uso:\n$usuario = new MiProyecto\\Modelos\\Usuario();"
                },
                {
                    "question": "?Qué son los traits en PHP?",
                    "options": ["Características de objetos", "Mecanismo para reutilizar código en herencia simple", "Tipos de variables", "Métodos especiales"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los traits permiten reutilizar métodos en múltiples clases sin herencia múltiple",
                    "points": 1,
                    "code_example": "trait Saludable {\n    public function saludar() {\n        echo \"Hola\";\n    }\n}\nclass Persona {\n    use Saludable;\n}"
                },
                {
                    "question": "?Qué es Composer en PHP?",
                    "options": ["Un editor de código", "Un gestor de dependencias", "Un framework", "Un servidor web"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Composer es el gestor de dependencias estándar para PHP",
                    "points": 1,
                    "code_example": "// composer.json\n{\n    \"require\": {\n        \"monolog/monolog\": \"^2.0\"\n    }\n}\n// composer install"
                },
                {
                    "question": "?Qué son los magic methods en PHP?",
                    "options": ["Métodos mágicos que se llaman automáticamente", "Métodos muy rápidos", "Métodos privados", "Métodos estáticos"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los magic methods como __construct, __get, __set se llaman automáticamente en ciertas situaciones",
                    "points": 1,
                    "code_example": "class MiClase {\n    public function __construct() { }\n    public function __get($name) { }\n    public function __set($name, $value) { }\n    public function __toString() { }\n}"
                },
                {
                    "question": "?Qué es PSR en PHP?",
                    "options": ["PHP Standard Recommendation", "PHP Super Rapid", "PHP System Resource", "PHP Secure Runtime"],
                    "correct_index": 0,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "PSR son estándares recomendados para mejorar la interoperabilidad entre proyectos PHP",
                    "points": 1,
                    "code_example": "// PSR-4: Autoloading\n// PSR-1: Basic Coding Standard\n// PSR-2: Coding Style Guide\n// PSR-7: HTTP Message Interface"
                }
            ],
            
            "Ruby": [
                # Principiante
                {
                    "question": "?Cómo se imprime texto en Ruby?",
                    "options": ["print \"texto\"", "puts \"texto\"", "echo \"texto\"", "console.log(\"texto\")"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "puts es la forma más común de imprimir texto en Ruby",
                    "points": 1,
                    "code_example": "puts \"Hola Mundo\"\nprint \"Sin salto de línea\"\np \"Para debugging\""
                },
                {
                    "question": "?Cómo se declara una variable en Ruby?",
                    "options": ["var nombre = valor", "nombre = valor", "$nombre = valor", "@nombre = valor"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "En Ruby las variables locales se declaran simplemente asignando un valor",
                    "points": 1,
                    "code_example": "nombre = \"Juan\"\nedad = 25\nactivo = true"
                },
                {
                    "question": "?Cómo se define un método en Ruby?",
                    "options": ["def nombre end", "function nombre() end", "method nombre end", "define nombre end"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "funciones",
                    "explanation": "Los métodos en Ruby se definen con 'def' y terminan con 'end'",
                    "points": 1,
                    "code_example": "def saludar(nombre)\n  \"Hola #{nombre}\"\nend\nputs saludar(\"Juan\")"
                },
                {
                    "question": "?Cómo se escribe un comentario en Ruby?",
                    "options": ["// comentario", "/* comentario */", "# comentario", "-- comentario"],
                    "correct_index": 2,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "Los comentarios en Ruby se escriben con #",
                    "points": 1,
                    "code_example": "# Este es un comentario\nputs \"Hola\"  # Comentario al final de línea"
                },
                {
                    "question": "?Cuál es la convención para nombres de variables en Ruby?",
                    "options": ["camelCase", "snake_case", "PascalCase", "kebab-case"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "sintaxis",
                    "explanation": "Ruby usa snake_case para variables y métodos",
                    "points": 1,
                    "code_example": "nombre_completo = \"Juan Pérez\"\nedad_usuario = 25\ndef calcular_promedio\nend"
                },
                
                # Intermedio
                {
                    "question": "?Qué es un símbolo (:symbol) en Ruby?",
                    "options": ["Un tipo de string", "Un identificador inmutable", "Un número especial", "Una variable global"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Los símbolos son identificadores inmutables que se usan frecuentemente como claves",
                    "points": 1,
                    "code_example": "hash = { :nombre => \"Juan\", :edad => 25 }\n# O con sintaxis moderna:\nhash = { nombre: \"Juan\", edad: 25 }"
                },
                {
                    "question": "?Qué hace el método each en Ruby?",
                    "options": ["Cuenta elementos", "Itera sobre cada elemento de una colección", "Busca un elemento", "Ordena elementos"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "funciones",
                    "explanation": "each itera sobre cada elemento de una colección ejecutando un bloque de código",
                    "points": 1,
                    "code_example": "[1, 2, 3].each do |numero|\n  puts numero\nend\n# O con sintaxis corta:\n[1, 2, 3].each { |n| puts n }"
                },
                {
                    "question": "?Qué es un bloque en Ruby?",
                    "options": ["Un comentario largo", "Un fragmento de código que se puede pasar a métodos", "Una función especial", "Un tipo de variable"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Los bloques son fragmentos de código que se pueden pasar a métodos para su ejecución",
                    "points": 1,
                    "code_example": "# Bloque con do..end\n5.times do |i|\n  puts i\nend\n# Bloque con {}\n5.times { |i| puts i }"
                },
                {
                    "question": "?Cuál es la diferencia entre puts y p en Ruby?",
                    "options": ["No hay diferencia", "puts formatea para humanos, p muestra representación cruda", "p es más rápido", "puts es obsoleto"],
                    "correct_index": 1,
                    "level": "intermedio",
                    "topic": "sintaxis",
                    "explanation": "puts convierte a string y formatea, p muestra la representación inspect del objeto",
                    "points": 1,
                    "code_example": "arr = [1, 2, 3]\nputs arr  # Imprime cada elemento en línea separada\np arr     # Imprime [1, 2, 3]"
                },
                {
                    "question": "?Qué son las variables de instancia en Ruby?",
                    "options": ["Variables que empiezan con @", "Variables globales", "Variables locales", "Variables constantes"],
                    "correct_index": 0,
                    "level": "intermedio",
                    "topic": "avanzado",
                    "explanation": "Las variables de instancia empiezan con @ y pertenecen a una instancia específica de clase",
                    "points": 1,
                    "code_example": "class Persona\n  def initialize(nombre)\n    @nombre = nombre  # Variable de instancia\n  end\n  def nombre\n    @nombre\n  end\nend"
                },
                
                # Avanzado
                {
                    "question": "?Qué es un mixin en Ruby?",
                    "options": ["Un tipo de herencia", "Un módulo que se incluye en una clase", "Una función especial", "Un tipo de variable"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Los mixins son módulos que se incluyen en clases para compartir funcionalidad",
                    "points": 1,
                    "code_example": "module Saludable\n  def saludar\n    puts \"Hola\"\n  end\nend\nclass Persona\n  include Saludable\nend\nPersona.new.saludar"
                },
                {
                    "question": "?Qué es metaprogramming en Ruby?",
                    "options": ["Programar muy rápido", "Escribir código que escribe código", "Usar muchos métodos", "Programar con metadatos"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Metaprogramming permite que el código se modifique a sí mismo durante la ejecución",
                    "points": 1,
                    "code_example": "class Persona\n  [:nombre, :edad].each do |attr|\n    define_method(attr) { instance_variable_get(\"@#{attr}\") }\n    define_method(\"#{attr}=\") { |val| instance_variable_set(\"@#{attr}\", val) }\n  end\nend"
                },
                {
                    "question": "?Qué hace yield en Ruby?",
                    "options": ["Termina el método", "Ejecuta el bloque pasado al método", "Devuelve un valor", "Crea una variable"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "yield ejecuta el bloque de código que se pasó al método",
                    "points": 1,
                    "code_example": "def mi_metodo\n  puts \"Antes del yield\"\n  yield\n  puts \"Después del yield\"\nend\nmi_metodo { puts \"En el bloque\" }"
                },
                {
                    "question": "?Qué son las clases singleton en Ruby?",
                    "options": ["Clases con un solo método", "Clases específicas para un objeto individual", "Clases que no se pueden instanciar", "Clases abstractas"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "Las clases singleton permiten definir métodos específicos para un objeto individual",
                    "points": 1,
                    "code_example": "obj = \"Hola\"\ndef obj.metodo_especial\n  \"Solo este objeto tiene este método\"\nend\nputs obj.metodo_especial"
                },
                {
                    "question": "?Qué es el patrón method_missing en Ruby?",
                    "options": ["Un error de método", "Un método que se llama cuando no se encuentra el método solicitado", "Un método privado", "Un método obsoleto"],
                    "correct_index": 1,
                    "level": "avanzado",
                    "topic": "avanzado",
                    "explanation": "method_missing se invoca cuando se llama a un método que no existe, permitiendo comportamiento dinámico",
                    "points": 1,
                    "code_example": "class DinamicoObj\n  def method_missing(name, *args)\n    puts \"Llamaste al método #{name} con argumentos #{args}\"\n  end\nend\nobj = DinamicoObj.new\nobj.cualquier_metodo(1, 2, 3)"
                }
            ]
        }
        
        # Devolver solo las primeras 10 preguntas del lenguaje solicitado o Python por defecto
        questions = assessments.get(language, assessments["Python"])
        return questions[:10]  # Limitar a 10 preguntas
    
    def _generate_fallback_assessment(self, language):
        """Genera evaluación básica cuando la IA no está disponible"""
        assessments = {
            "Python": [
                {
                    "question": f"?Cuál es la sintaxis correcta para definir una función en {language}?",
                    "options": ["def mi_funcion():", "function mi_funcion():", "func mi_funcion():", "define mi_funcion():"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "funciones",
                    "explanation": "En Python se usa 'def' para definir funciones",
                    "points": 1
                },
                {
                    "question": f"?Qué tipo de dato es [1, 2, 3] en {language}?",
                    "options": ["Tupla", "Lista", "Diccionario", "Set"],
                    "correct_index": 1,
                    "level": "principiante",
                    "topic": "estructuras",
                    "explanation": "Los corchetes [] definen listas en Python",
                    "points": 1
                }
            ],
            "JavaScript": [
                {
                    "question": f"?Cuál es la sintaxis correcta para declarar una variable en {language}?",
                    "options": ["var nombre;", "variable nombre;", "declare nombre;", "name nombre;"],
                    "correct_index": 0,
                    "level": "principiante",
                    "topic": "variables",
                    "explanation": "En JavaScript se usa 'var', 'let' o 'const'",
                    "points": 1
                }
            ]
        }
        
        return assessments.get(language, assessments["Python"])
    
    def evaluate_level_from_responses(self, language, responses):
        """Evalúa el nivel del estudiante basado en sus respuestas"""
        if not responses:
            return "principiante", 0, "Sin respuestas para evaluar"
        
        total_questions = len(responses)
        correct_answers = sum(1 for r in responses if r.get('is_correct', False))
        percentage = (correct_answers / total_questions) * 100
        
        # Análisis por nivel de preguntas
        level_scores = {"principiante": 0, "intermedio": 0, "avanzado": 0}
        level_totals = {"principiante": 0, "intermedio": 0, "avanzado": 0}
        
        for response in responses:
            level = response.get('level', 'principiante')
            level_totals[level] += 1
            if response.get('is_correct', False):
                level_scores[level] += 1
        
        # Calcular porcentajes por nivel
        level_percentages = {}
        for level in level_scores:
            if level_totals[level] > 0:
                level_percentages[level] = (level_scores[level] / level_totals[level]) * 100
            else:
                level_percentages[level] = 0
        
        # Determinar nivel final
        if level_percentages.get('avanzado', 0) >= 70:
            final_level = "avanzado"
        elif level_percentages.get('intermedio', 0) >= 60:
            final_level = "intermedio"
        else:
            final_level = "principiante"
        
        # Generar recomendaciones
        recommendations = self._generate_level_recommendations(language, final_level, level_percentages)
        
        return final_level, percentage, recommendations
    
    def _generate_level_recommendations(self, language, level, level_percentages):
        """Genera recomendaciones basadas en el nivel evaluado"""
        recommendations = {
            "principiante": f"""
            **Plan de Estudio para {language} - Nivel Principiante**
            
            **Enfoque Principal:**
            - Sintaxis básica y conceptos fundamentales
            - Práctica con ejercicios simples
            - Construcción de bases sólidas
            
            **Temas Prioritarios:**
            - Variables y tipos de datos
            - Estructuras de control (if, for, while)
            - Funciones básicas
            - Entrada y salida de datos
            
            **Tiempo Recomendado:** 2-3 horas por semana durante 4-6 semanas
            """,
            
            "intermedio": f"""
            **Plan de Estudio para {language} - Nivel Intermedio**
            
            **Enfoque Principal:**
            - Conceptos avanzados y mejores prácticas
            - Proyectos de mediana complejidad
            - Optimización y debugging
            
            **Temas Prioritarios:**
            - Estructuras de datos avanzadas
            - Programación orientada a objetos
            - Manejo de errores y excepciones
            - Algoritmos y complejidad
            
            **Tiempo Recomendado:** 3-4 horas por semana durante 6-8 semanas
            """,
            
            "avanzado": f"""
            **Plan de Estudio para {language} - Nivel Avanzado**
            
            **Enfoque Principal:**
            - Patrones de diseño y arquitectura
            - Proyectos complejos y reales
            - Especialización en áreas específicas
            
            **Temas Prioritarios:**
            - Patrones de diseño
            - Concurrencia y paralelismo
            - Optimización de rendimiento
            - Frameworks y librerías avanzadas
            
            **Tiempo Recomendado:** 4-5 horas por semana, enfoque en proyectos
            """
        }
        
        return recommendations.get(level, recommendations["principiante"])
    
    def generate_learning_resources(self, language, level, topics=None):
        """Genera recursos de aprendizaje personalizados"""
        if not self.model:
            return self._generate_fallback_resources(language, level)
        
        try:
            topics_str = ", ".join(topics) if topics else "conceptos generales"
            
            prompt = f"""
            Genera recursos de aprendizaje para {language} nivel {level}.
            
            TEMAS ESPECÍFICOS: {topics_str}
            
            TIPOS DE RECURSOS NECESARIOS:
            - 3 videos de YouTube (tutoriales específicos)
            - 2 sitios web/documentación oficial
            - 2 tutoriales online recomendados
            - 1 ejercicio práctico
            
            FORMATO JSON:
            [
                {{
                    "type": "video|website|tutorial|documentation|exercise",
                    "title": "Título del recurso",
                    "url": "URL real y funcional",
                    "description": "Descripción breve del contenido",
                    "provider": "YouTube|Coursera|MDN|etc",
                    "duration_minutes": 30,
                    "rating": 4.5,
                    "level": "{level}",
                    "topics": ["{topics_str}"]
                }}
            ]
            
            IMPORTANTE: 
            - Usa SOLO estos tipos: video, website, tutorial, documentation, exercise
            - Proporciona URLs reales y funcionales, no ejemplos
            """
            
            response = self.call_with_retry(prompt)
            result = self.extract_json_from_response(response, 'list')
            
            if isinstance(result, list) and len(result) > 0:
                return result
            else:
                return self._generate_fallback_resources(language, level)
                
        except Exception as e:
            return self._generate_fallback_resources(language, level)
    
    def _generate_fallback_resources(self, language, level):
        """Genera recursos básicos cuando la IA no está disponible"""
        resources = {
            "Python": {
                "principiante": [
                    {
                        "type": "website",
                        "title": "Python.org - Tutorial Oficial",
                        "url": "https://docs.python.org/3/tutorial/",
                        "description": "Tutorial oficial de Python para principiantes",
                        "provider": "Python.org",
                        "duration_minutes": 120,
                        "rating": 4.8,
                        "level": "principiante",
                        "topics": ["sintaxis básica", "conceptos fundamentales"]
                    },
                    {
                        "type": "video",
                        "title": "Python para Principiantes",
                        "url": "https://www.youtube.com/watch?v=rfscVS0vtbw",
                        "description": "Curso completo de Python desde cero",
                        "provider": "YouTube",
                        "duration_minutes": 240,
                        "rating": 4.6,
                        "level": "principiante",
                        "topics": ["variables", "funciones", "estructuras de control"]
                    }
                ]
            },
            "JavaScript": {
                "principiante": [
                    {
                        "type": "website",
                        "title": "MDN Web Docs - JavaScript",
                        "url": "https://developer.mozilla.org/es/docs/Web/JavaScript",
                        "description": "Documentación completa de JavaScript",
                        "provider": "MDN",
                        "duration_minutes": 180,
                        "rating": 4.9,
                        "level": "principiante",
                        "topics": ["sintaxis", "DOM", "eventos"]
                    }
                ]
            }
        }
        
        return resources.get(language, {}).get(level, resources["Python"]["principiante"])
    
    def generate_progressive_exercises(self, language, level, count=5):
        """Genera ejercicios escalonados"""
        if not self.model:
            return self._generate_fallback_exercises(language, level, count)
        
        try:
            prompt = f"""
            Crea {count} ejercicios progresivos para {language} nivel {level}.
            
            REQUISITOS:
            - Dificultad creciente del 1 al {count}
            - Cada ejercicio debe incluir descripción clara y ejemplo
            - Proporcionar código inicial (template) cuando sea apropiado
            - Incluir casos de prueba o resultados esperados
            
            FORMATO JSON:
            [
                {{
                    "title": "Título del ejercicio",
                    "description": "Descripción detallada del problema a resolver",
                    "difficulty": 1,
                    "topics": ["variables", "funciones"],
                    "exercise_code": "# Código inicial o template",
                    "expected_output": "Resultado esperado",
                    "hints": ["Pista 1", "Pista 2"],
                    "test_cases": [
                        {{"input": "entrada", "output": "salida esperada"}}
                    ]
                }}
            ]
            """
            
            response = self.call_with_retry(prompt)
            result = self.extract_json_from_response(response, 'list')
            
            if isinstance(result, list) and len(result) > 0:
                return result
            else:
                return self._generate_fallback_exercises(language, level, count)
                
        except Exception as e:
            return self._generate_fallback_exercises(language, level, count)
    
    def _generate_fallback_exercises(self, language, level, count):
        """Genera ejercicios básicos cuando la IA no está disponible"""
        exercises = {
            "Python": {
                "principiante": [
                    {
                        "title": "Hola Mundo Personalizado",
                        "description": "Crea un programa que pida tu nombre y te salude personalmente",
                        "difficulty": 1,
                        "topics": ["variables", "input", "print"],
                        "exercise_code": "# Pide el nombre del usuario\n# Muestra un saludo personalizado",
                        "expected_output": "Hola, [nombre]! Bienvenido a Python",
                        "hints": ["Usa input() para leer datos", "Usa print() para mostrar el resultado"],
                        "test_cases": [{"input": "Ana", "output": "Hola, Ana! Bienvenido a Python"}]
                    },
                    {
                        "title": "Calculadora Simple",
                        "description": "Crea una calculadora que sume dos números",
                        "difficulty": 2,
                        "topics": ["variables", "operadores", "conversión de tipos"],
                        "exercise_code": "# Pide dos números al usuario\n# Calcula y muestra la suma",
                        "expected_output": "La suma de 5 y 3 es: 8",
                        "hints": ["Convierte strings a números con int()", "Usa el operador + para sumar"],
                        "test_cases": [{"input": "5, 3", "output": "La suma de 5 y 3 es: 8"}]
                    }
                ]
            }
        }
        
        lang_exercises = exercises.get(language, exercises["Python"])
        level_exercises = lang_exercises.get(level, lang_exercises["principiante"])
        
        return level_exercises[:count]
    
    def evaluate_personal_exercise(self, exercise_description, student_code, language):
        """Evalúa un ejercicio personal del estudiante"""
        return self.evaluate_code(student_code, exercise_description, language)

    def get_socratic_hint(self, code, error, language="python"):
        # Mapear nombres de lenguajes para consistencia
        lang_map = {
            "Python": "Python",
            "Java": "Java", 
            "C++": "C++",
            "JavaScript": "JavaScript",
            "SQL": "SQL",
            "NoSQL": "NoSQL/MongoDB",
            "HTML/CSS": "HTML/CSS"
        }
        
        mapped_lang = lang_map.get(language, language)
        
        prompt = f"""
        Eres un tutor experto en {mapped_lang}. Un estudiante tiene problemas con su código.
        
        LENGUAJE: {mapped_lang}
        CÓDIGO DEL ESTUDIANTE:
        {code}
        
        PROBLEMA/ERROR REPORTADO:
        {error}
        
        Como tutor de {mapped_lang}, proporciona exactamente 3 pistas útiles y específicas para este lenguaje:
        
        1. Una pista sobre el error específico
        2. Una sugerencia de cómo solucionarlo en {mapped_lang}
        3. Un consejo general para mejorar el código en {mapped_lang}
        
        Usa la sintaxis y mejores prácticas específicas de {mapped_lang}.
        Sé claro, educativo y alentador.
        """
        
        return self.call_with_retry(prompt)

    def grade_open_question(self, q, a, p):
        """Califica una pregunta de texto abierto de forma INSTANTÁNEA (sin IA)"""
        # Si no hay respuesta, calificación 0
        if not a or len(a.strip()) < 5:
            return 0, "Sin respuesta o respuesta muy corta"
        
        # CALIFICACIÓN AUTOMÁTICA INTELIGENTE (sin IA para velocidad)
        answer = a.strip()
        question = q.strip()
        
        # Análisis de la respuesta
        length = len(answer)
        words = len(answer.split())
        sentences = answer.count('.') + answer.count('?') + answer.count('!')
        
        # Calcular puntuación base por longitud y estructura
        if length < 20:
            base_score = 0.2
            feedback = "Respuesta muy breve"
        elif length < 50:
            base_score = 0.4
            feedback = "Respuesta corta, falta desarrollo"
        elif length < 100:
            base_score = 0.6
            feedback = "Respuesta aceptable"
        elif length < 200:
            base_score = 0.75
            feedback = "Respuesta bien desarrollada"
        else:
            base_score = 0.85
            feedback = "Respuesta completa y detallada"
        
        # Bonificación por estructura (oraciones múltiples)
        if sentences >= 2:
            base_score += 0.05
            feedback += ", bien estructurada"
        
        # Bonificación por palabras clave de la pregunta
        question_words = set(question.lower().split())
        answer_words = set(answer.lower().split())
        common_words = question_words.intersection(answer_words)
        
        if len(common_words) >= 3:
            base_score += 0.05
            feedback += ", aborda la pregunta"
        
        # Limitar a máximo 1.0
        base_score = min(base_score, 1.0)
        
        # Calcular puntuación final
        final_score = round(base_score * p, 1)
        
        return final_score, f"{feedback} (calificación automática - el profesor puede ajustar)"
    
    def grade_open_question_with_ai(self, q, a, p):
        """Califica una pregunta de texto abierto usando IA (con timeout estricto)"""
        # Si no hay respuesta, calificación 0
        if not a or len(a.strip()) < 5:
            return 0, "Sin respuesta o respuesta muy corta"
        
        # Prompt ultra-optimizado para velocidad
        prompt = f"""Califica del 0 al {p}:
P: {q[:250]}
R: {a[:600]}

Responde SOLO: {{"s":X,"f":"comentario corto"}}"""
        
        try:
            # Configuración ultra-rápida con timeout de 10 segundos
            import signal
            import time
            
            start_time = time.time()
            
            res = self.call_with_retry(
                prompt,
                max_retries=1,
                max_output_tokens=50,  # Muy corto
                temperature=0.2,  # Muy determinista
                timeout=10  # Timeout de 10 segundos
            )
            
            elapsed = time.time() - start_time
            
            # Si tardó más de 10 segundos o hay error, usar fallback
            if elapsed > 10 or not res or "Error" in res or "Timeout" in res:
                return self.grade_open_question(q, a, p)
            
            # Intentar parsear JSON
            import re
            json_match = re.search(r'\{[^}]+\}', res)
            if json_match:
                import json
                parsed = json.loads(json_match.group())
                score = float(parsed.get('s', p * 0.5))
                feedback = parsed.get('f', 'Calificado con IA')
                score = max(0, min(score, p))
                return score, feedback
        except Exception as e:
            # Si falla, usar calificación automática
            pass
        
        # Fallback: usar calificación automática
        return self.grade_open_question(q, a, p)
    
    # ========== MÉTODOS PARA ESTRUCTURA POR TEMAS EN ESPAÑOL ==========
    
    def generate_course_topics_structure(self, language, level, sections_count=5):
        """
        Genera la estructura de temas para un curso IA adaptada al nivel específico.
        Incluye validación robusta de la estructura generada.
        """
        
        # SOLUCIÓN ROBUSTA: Usar estructura predefinida en lugar de IA para títulos
        # Esto garantiza que los títulos sean SIEMPRE correctos para el lenguaje
        
        structure_text = self._get_language_structure(language, level)
        
        # Parsear la estructura predefinida
        topics = []
        lines = structure_text.strip().split('\n')
        
        for idx, line in enumerate(lines[:sections_count], 1):
            # Extraer título de la línea (formato: "- Tema X: Título")
            if ':' in line:
                title_part = line.split(':', 1)[1].strip()
            else:
                title_part = line.replace('-', '').replace('Tema', '').strip()
            
            # Crear tema con estructura predefinida
            topic = {
                "topic_number": idx,
                "title": title_part,
                "description": f"Aprende {title_part.lower()} en {language}",
                "objectives": f"Dominar {title_part.lower()} aplicado a {language}",
                "estimated_hours": 3 + idx,
                "order_index": idx - 1,
                "order": idx  # Add for validator compatibility
            }
            topics.append(topic)
        
        # Si tenemos modelo de IA, mejorar descripciones y objetivos
        if self.model and len(topics) > 0:
            try:
                for topic in topics:
                    prompt = f"""
                    Para un curso de {language} nivel {level}, genera una descripción y objetivos para este tema:
                    
                    TEMA: {topic['title']}
                    LENGUAJE: {language}
                    NIVEL: {level}
                    
                    Genera un JSON con:
                    {{
                        "description": "Descripción detallada del tema en {language} (2-3 oraciones)",
                        "objectives": "Objetivos de aprendizaje específicos para {language} (2-3 objetivos)"
                    }}
                    
                    IMPORTANTE:
                    - TODO específico para {language}
                    - NO menciones otros lenguajes
                    - Descripción y objetivos en ESPAÑOL
                    
                    Responde SOLO con el JSON:
                    """
                    
                    response = self.call_with_retry(
                        prompt, 
                        max_retries=2,
                        operation_type='course_generation'
                    )
                    result = self.extract_json_from_response(response, 'dict')
                    
                    if isinstance(result, dict):
                        if 'description' in result and len(result['description']) >= 20:
                            topic['description'] = result['description']
                        if 'objectives' in result:
                            topic['objectives'] = result['objectives']
            except Exception as e:
                print(f"[WARNING] Error mejorando descripciones con IA: {e}")
                # Si falla la IA, usar descripciones básicas (ya están asignadas)
                pass
        
        # Validate the generated structure
        validator = ResponseValidator()
        is_valid, errors = validator.validate_course_structure(
            topics, 
            sections_count, 
            language, 
            level
        )
        
        if not is_valid:
            print(f"[WARNING] Course structure validation failed: {errors}")
            # Return partial results with warning
            # Filter out topics with critical errors
            valid_topics = []
            for i, topic in enumerate(topics):
                # Check if this topic has critical errors
                topic_errors = [e for e in errors if f"Topic {i+1}:" in e]
                has_critical_error = any(
                    'missing required field' in e.lower() or 
                    'is not a dictionary' in e.lower()
                    for e in topic_errors
                )
                if not has_critical_error:
                    valid_topics.append(topic)
            
            if valid_topics:
                print(f"[INFO] Returning {len(valid_topics)} valid topics out of {len(topics)}")
                return valid_topics[:sections_count]
        
        return topics[:sections_count]
    
    def _get_level_specifications(self, language, level):
        """Obtiene especificaciones detalladas por nivel"""
        specs = {
            "principiante": f"""
            - Estudiante SIN experiencia previa en {language}
            - Necesita explicaciones paso a paso
            - Conceptos desde cero: sintaxis, variables, tipos básicos
            - Ejemplos muy simples y prácticos
            - Enfoque en fundamentos sólidos
            """,
            "intermedio": f"""
            - Estudiante CON conocimientos básicos de {language}
            - Ya conoce sintaxis fundamental
            - Necesita conceptos más avanzados y patrones
            - Proyectos de complejidad media
            - Mejores prácticas y optimización
            """,
            "avanzado": f"""
            - Estudiante CON experiencia significativa en {language}
            - Domina conceptos básicos e intermedios
            - Necesita arquitectura, patrones avanzados
            - Proyectos complejos y profesionales
            - Optimización y rendimiento avanzado
            """
        }
        return specs.get(level, specs["principiante"])
    
    def _get_language_structure(self, language, level):
        """Obtiene estructura específica por lenguaje y nivel"""
        structures = {
            "Ruby": {
                "principiante": """
                - Tema 1: Instalación de Ruby, sintaxis básica, variables
                - Tema 2: Tipos de datos, operadores y entrada/salida
                - Tema 3: Condicionales y bucles en Ruby
                - Tema 4: Arrays y Hashes básicos
                - Tema 5: Métodos y bloques simples
                - Tema 6: Strings y símbolos en Ruby
                - Tema 7: Trabajo con archivos básicos
                - Tema 8: Primer proyecto Ruby
                """,
                "intermedio": """
                - Tema 1: Clases, objetos y herencia en Ruby
                - Tema 2: Módulos y mixins
                - Tema 3: Bloques, procs y lambdas
                - Tema 4: Manejo de excepciones y errores
                - Tema 5: Expresiones regulares en Ruby
                - Tema 6: Gemas y Bundler
                - Tema 7: Testing con RSpec
                - Tema 8: Proyecto con base de datos
                """,
                "avanzado": """
                - Tema 1: Metaprogramación en Ruby
                - Tema 2: Ruby on Rails fundamentos
                - Tema 3: APIs RESTful con Rails
                - Tema 4: ActiveRecord avanzado
                - Tema 5: Testing avanzado y TDD
                - Tema 6: Optimización y performance
                - Tema 7: Deployment y DevOps
                - Tema 8: Aplicación web completa con Rails
                """
            },
            "Python": {
                "principiante": """
                - Tema 1: Instalación, sintaxis básica, variables y tipos
                - Tema 2: Operadores, entrada/salida, primeros programas
                - Tema 3: Condicionales y bucles básicos
                - Tema 4: Listas, tuplas y diccionarios básicos
                - Tema 5: Funciones simples y parámetros
                - Tema 6: Manejo de strings y formateo
                - Tema 7: Trabajo con archivos básicos
                - Tema 8: Primer proyecto integrador
                """,
                "intermedio": """
                - Tema 1: Estructuras de datos avanzadas y comprehensions
                - Tema 2: Programación orientada a objetos
                - Tema 3: Manejo de archivos y excepciones
                - Tema 4: Módulos, paquetes y bibliotecas
                - Tema 5: Expresiones regulares y procesamiento de texto
                - Tema 6: Trabajo con APIs y JSON
                - Tema 7: Testing y debugging
                - Tema 8: Proyecto web o análisis de datos
                """,
                "avanzado": """
                - Tema 1: Decoradores, generadores y metaclases
                - Tema 2: Programación asíncrona y concurrencia
                - Tema 3: Optimización y profiling de código
                - Tema 4: Patrones de diseño y arquitectura
                - Tema 5: Bases de datos y ORMs
                - Tema 6: Web scraping y automatización
                - Tema 7: Machine Learning básico con Python
                - Tema 8: Proyecto complejo con testing y deployment
                """
            },
            "JavaScript": {
                "principiante": """
                - Tema 1: Sintaxis básica, variables y tipos de datos
                - Tema 2: Funciones básicas y scope
                - Tema 3: DOM básico y eventos simples
                - Tema 4: Arrays y objetos básicos
                - Tema 5: Manipulación de strings y números
                - Tema 6: Formularios y validación básica
                - Tema 7: LocalStorage y persistencia
                - Tema 8: Primer proyecto interactivo
                """,
                "intermedio": """
                - Tema 1: ES6+, arrow functions, destructuring
                - Tema 2: Programación asíncrona (Promises, async/await)
                - Tema 3: Manipulación avanzada del DOM
                - Tema 4: APIs y fetch, JSON
                - Tema 5: Módulos y bundling
                - Tema 6: Programación funcional
                - Tema 7: Testing con Jest
                - Tema 8: Proyecto con framework (React/Vue básico)
                """,
                "avanzado": """
                - Tema 1: Patrones de diseño en JavaScript
                - Tema 2: Node.js y desarrollo backend
                - Tema 3: Testing, bundling y herramientas
                - Tema 4: Performance y optimización
                - Tema 5: TypeScript y tipado estático
                - Tema 6: GraphQL y APIs modernas
                - Tema 7: Arquitectura de aplicaciones
                - Tema 8: Aplicación full-stack completa
                """
            },
            "Java": {
                "principiante": """
                - Tema 1: Instalación JDK, sintaxis básica, variables
                - Tema 2: Operadores, condicionales y bucles
                - Tema 3: Arrays y métodos básicos
                - Tema 4: Introducción a clases y objetos
                - Tema 5: Strings y manipulación de texto
                - Tema 6: Entrada/salida básica
                - Tema 7: Colecciones básicas (ArrayList, HashMap)
                - Tema 8: Primer proyecto con interfaz simple
                """,
                "intermedio": """
                - Tema 1: Herencia, polimorfismo e interfaces
                - Tema 2: Collections Framework completo
                - Tema 3: Manejo de excepciones y archivos
                - Tema 4: Threads y programación concurrente
                - Tema 5: Streams y programación funcional
                - Tema 6: JDBC y bases de datos
                - Tema 7: Testing con JUnit
                - Tema 8: Proyecto con base de datos
                """,
                "avanzado": """
                - Tema 1: Patrones de diseño y arquitectura
                - Tema 2: Spring Framework y microservicios
                - Tema 3: JVM tuning y optimización
                - Tema 4: Testing avanzado y CI/CD
                - Tema 5: Seguridad y autenticación
                - Tema 6: APIs RESTful con Spring Boot
                - Tema 7: Mensajería y eventos
                - Tema 8: Aplicación empresarial completa
                """
            },
            "C++": {
                "principiante": "- Tema 1: Instalación, sintaxis básica, variables y tipos\n- Tema 2: Operadores, entrada/salida con cin/cout\n- Tema 3: Condicionales y bucles\n- Tema 4: Arrays y strings básicos\n- Tema 5: Funciones y parámetros\n- Tema 6: Punteros básicos\n- Tema 7: Estructuras y tipos definidos\n- Tema 8: Primer proyecto en C++",
                "intermedio": "- Tema 1: Clases y objetos en C++\n- Tema 2: Herencia y polimorfismo\n- Tema 3: Punteros avanzados y referencias\n- Tema 4: Manejo de memoria dinámica\n- Tema 5: Templates básicos\n- Tema 6: STL: vectores, listas, mapas\n- Tema 7: Manejo de archivos y streams\n- Tema 8: Proyecto con estructuras de datos",
                "avanzado": "- Tema 1: Templates avanzados y metaprogramación\n- Tema 2: Smart pointers y gestión de memoria\n- Tema 3: Programación concurrente y threads\n- Tema 4: Optimización y performance\n- Tema 5: Patrones de diseño en C++\n- Tema 6: STL avanzado y algoritmos\n- Tema 7: C++17/20 características modernas\n- Tema 8: Proyecto de alto rendimiento"
            },
            "C#": {
                "principiante": "- Tema 1: Instalación .NET, sintaxis básica, variables\n- Tema 2: Operadores, condicionales y bucles\n- Tema 3: Arrays y colecciones básicas\n- Tema 4: Métodos y parámetros\n- Tema 5: Clases y objetos básicos\n- Tema 6: Strings y manipulación de texto\n- Tema 7: Entrada/salida y archivos\n- Tema 8: Primer proyecto Windows Forms",
                "intermedio": "- Tema 1: POO avanzada: herencia, interfaces\n- Tema 2: LINQ y expresiones lambda\n- Tema 3: Colecciones genéricas y delegates\n- Tema 4: Manejo de excepciones y eventos\n- Tema 5: Trabajo con archivos y serialización\n- Tema 6: Bases de datos con Entity Framework\n- Tema 7: Testing con NUnit\n- Tema 8: Aplicación WPF o ASP.NET básica",
                "avanzado": "- Tema 1: Async/await y programación asíncrona\n- Tema 2: ASP.NET Core y Web APIs\n- Tema 3: Dependency Injection y patrones\n- Tema 4: Entity Framework avanzado\n- Tema 5: SignalR y comunicación en tiempo real\n- Tema 6: Seguridad y autenticación\n- Tema 7: Microservicios con .NET\n- Tema 8: Aplicación empresarial completa"
            },
            "PHP": {
                "principiante": "- Tema 1: Instalación XAMPP, sintaxis básica PHP\n- Tema 2: Variables, tipos de datos y operadores\n- Tema 3: Condicionales y bucles\n- Tema 4: Arrays y funciones básicas\n- Tema 5: Formularios y GET/POST\n- Tema 6: Trabajo con strings y fechas\n- Tema 7: Archivos y sesiones básicas\n- Tema 8: Primer sitio web dinámico",
                "intermedio": "- Tema 1: POO en PHP: clases y objetos\n- Tema 2: MySQL y bases de datos\n- Tema 3: PDO y consultas preparadas\n- Tema 4: Sesiones y cookies avanzadas\n- Tema 5: Validación y sanitización\n- Tema 6: Subida de archivos e imágenes\n- Tema 7: APIs y JSON\n- Tema 8: Sistema CRUD completo",
                "avanzado": "- Tema 1: Laravel framework fundamentos\n- Tema 2: Eloquent ORM y migraciones\n- Tema 3: Autenticación y autorización\n- Tema 4: APIs RESTful con Laravel\n- Tema 5: Testing con PHPUnit\n- Tema 6: Colas y jobs en Laravel\n- Tema 7: Deployment y optimización\n- Tema 8: Aplicación web completa con Laravel"
            },
            "SQL": {
                "principiante": "- Tema 1: Introducción a bases de datos relacionales\n- Tema 2: SELECT básico y filtrado con WHERE\n- Tema 3: INSERT, UPDATE y DELETE\n- Tema 4: Ordenamiento y limitación de resultados\n- Tema 5: Funciones agregadas básicas\n- Tema 6: GROUP BY y HAVING\n- Tema 7: Creación de tablas y tipos de datos\n- Tema 8: Primer proyecto de base de datos",
                "intermedio": "- Tema 1: JOINs: INNER, LEFT, RIGHT, FULL\n- Tema 2: Subconsultas y consultas anidadas\n- Tema 3: Vistas y tablas temporales\n- Tema 4: Índices y optimización básica\n- Tema 5: Constraints y relaciones\n- Tema 6: Transacciones y ACID\n- Tema 7: Funciones y procedimientos almacenados\n- Tema 8: Base de datos normalizada completa",
                "avanzado": "- Tema 1: Optimización avanzada de consultas\n- Tema 2: Índices compuestos y estrategias\n- Tema 3: Triggers y eventos\n- Tema 4: Particionamiento de tablas\n- Tema 5: Replicación y alta disponibilidad\n- Tema 6: Análisis de planes de ejecución\n- Tema 7: Seguridad y permisos avanzados\n- Tema 8: Diseño de base de datos empresarial"
            },
            "NoSQL": {
                "principiante": "- Tema 1: Introducción a NoSQL y MongoDB\n- Tema 2: Documentos y colecciones básicas\n- Tema 3: Operaciones CRUD en MongoDB\n- Tema 4: Consultas básicas y filtros\n- Tema 5: Actualización de documentos\n- Tema 6: Tipos de datos en MongoDB\n- Tema 7: Índices básicos\n- Tema 8: Primera aplicación con MongoDB",
                "intermedio": "- Tema 1: Consultas avanzadas y operadores\n- Tema 2: Agregación y pipeline\n- Tema 3: Índices compuestos y optimización\n- Tema 4: Modelado de datos en NoSQL\n- Tema 5: Referencias y documentos embebidos\n- Tema 6: Transacciones en MongoDB\n- Tema 7: Mongoose y ODM\n- Tema 8: API con Node.js y MongoDB",
                "avanzado": "- Tema 1: Sharding y escalabilidad horizontal\n- Tema 2: Replicación y alta disponibilidad\n- Tema 3: Optimización de performance\n- Tema 4: Seguridad y autenticación\n- Tema 5: Backup y recuperación\n- Tema 6: Monitoreo y métricas\n- Tema 7: Arquitectura de microservicios\n- Tema 8: Sistema distribuido completo"
            },
            "HTML/CSS": {
                "principiante": "- Tema 1: Estructura HTML básica y etiquetas\n- Tema 2: Textos, listas y enlaces\n- Tema 3: Imágenes y multimedia\n- Tema 4: CSS básico: selectores y propiedades\n- Tema 5: Colores, fuentes y textos\n- Tema 6: Box model y espaciado\n- Tema 7: Formularios HTML\n- Tema 8: Primera página web completa",
                "intermedio": "- Tema 1: Flexbox para layouts\n- Tema 2: CSS Grid avanzado\n- Tema 3: Responsive design y media queries\n- Tema 4: Posicionamiento avanzado\n- Tema 5: Transiciones y animaciones CSS\n- Tema 6: Pseudo-clases y pseudo-elementos\n- Tema 7: Formularios avanzados y validación\n- Tema 8: Sitio web responsive completo",
                "avanzado": "- Tema 1: CSS avanzado: variables y funciones\n- Tema 2: Preprocesadores: Sass/SCSS\n- Tema 3: Metodologías: BEM, SMACSS\n- Tema 4: Animaciones complejas y keyframes\n- Tema 5: Performance y optimización CSS\n- Tema 6: Accesibilidad web (WCAG)\n- Tema 7: CSS moderno: Grid avanzado, Container Queries\n- Tema 8: Sistema de diseño completo"
            },
            "Go": {
                "principiante": "- Tema 1: Instalación Go, sintaxis básica, variables\n- Tema 2: Tipos de datos y operadores\n- Tema 3: Condicionales y bucles\n- Tema 4: Arrays, slices y maps\n- Tema 5: Funciones y múltiples retornos\n- Tema 6: Punteros básicos\n- Tema 7: Structs y métodos\n- Tema 8: Primer programa CLI en Go",
                "intermedio": "- Tema 1: Interfaces en Go\n- Tema 2: Goroutines y concurrencia básica\n- Tema 3: Channels y comunicación\n- Tema 4: Manejo de errores en Go\n- Tema 5: Paquetes y módulos\n- Tema 6: Testing en Go\n- Tema 7: Trabajo con JSON y APIs\n- Tema 8: Servidor HTTP básico",
                "avanzado": "- Tema 1: Patrones de concurrencia avanzados\n- Tema 2: Context y cancelación\n- Tema 3: Reflection y metaprogramación\n- Tema 4: Optimización y profiling\n- Tema 5: Microservicios con Go\n- Tema 6: gRPC y Protocol Buffers\n- Tema 7: Testing avanzado y benchmarks\n- Tema 8: Sistema distribuido con Go"
            },
            "Rust": {
                "principiante": "- Tema 1: Instalación Rust, Cargo, sintaxis básica\n- Tema 2: Variables, mutabilidad y tipos\n- Tema 3: Ownership y borrowing básico\n- Tema 4: Condicionales y bucles\n- Tema 5: Funciones y expresiones\n- Tema 6: Structs y enums básicos\n- Tema 7: Pattern matching\n- Tema 8: Primer programa en Rust",
                "intermedio": "- Tema 1: Ownership avanzado y lifetimes\n- Tema 2: Traits y generics\n- Tema 3: Manejo de errores con Result\n- Tema 4: Colecciones: Vec, HashMap, HashSet\n- Tema 5: Iteradores y closures\n- Tema 6: Smart pointers: Box, Rc, RefCell\n- Tema 7: Testing en Rust\n- Tema 8: Aplicación CLI completa",
                "avanzado": "- Tema 1: Concurrencia segura en Rust\n- Tema 2: Async/await y Tokio\n- Tema 3: Macros y metaprogramación\n- Tema 4: Unsafe Rust y FFI\n- Tema 5: Optimización y zero-cost abstractions\n- Tema 6: Web con Actix o Rocket\n- Tema 7: WebAssembly con Rust\n- Tema 8: Sistema de alto rendimiento"
            },
            "Swift": {
                "principiante": "- Tema 1: Instalación Xcode, sintaxis básica Swift\n- Tema 2: Variables, constantes y tipos\n- Tema 3: Operadores y condicionales\n- Tema 4: Colecciones: Arrays, Sets, Dictionaries\n- Tema 5: Funciones y closures básicos\n- Tema 6: Opcionales y unwrapping\n- Tema 7: Structs y clases básicas\n- Tema 8: Primera app iOS simple",
                "intermedio": "- Tema 1: POO en Swift: herencia y protocolos\n- Tema 2: Manejo de errores y guard\n- Tema 3: Extensiones y generics\n- Tema 4: UIKit básico: vistas y controladores\n- Tema 5: Auto Layout y constraints\n- Tema 6: Navegación y segues\n- Tema 7: Persistencia con UserDefaults\n- Tema 8: App iOS con múltiples pantallas",
                "avanzado": "- Tema 1: SwiftUI fundamentos\n- Tema 2: Combine framework\n- Tema 3: Arquitectura MVVM\n- Tema 4: Core Data y persistencia\n- Tema 5: Networking y APIs\n- Tema 6: Concurrencia con async/await\n- Tema 7: Testing y UI Testing\n- Tema 8: App iOS completa publicable"
            },
            "Kotlin": {
                "principiante": "- Tema 1: Instalación, sintaxis básica Kotlin\n- Tema 2: Variables, tipos y null safety\n- Tema 3: Condicionales y when expression\n- Tema 4: Colecciones y rangos\n- Tema 5: Funciones y lambdas básicas\n- Tema 6: Clases y objetos básicos\n- Tema 7: Data classes y sealed classes\n- Tema 8: Primera app Android simple",
                "intermedio": "- Tema 1: POO en Kotlin: herencia e interfaces\n- Tema 2: Extensiones y funciones de orden superior\n- Tema 3: Coroutines básicas\n- Tema 4: Android: Activities y Fragments\n- Tema 5: Layouts y Material Design\n- Tema 6: RecyclerView y adaptadores\n- Tema 7: Room database\n- Tema 8: App Android con base de datos",
                "avanzado": "- Tema 1: Jetpack Compose\n- Tema 2: Coroutines y Flow avanzado\n- Tema 3: Arquitectura MVVM con ViewModel\n- Tema 4: Retrofit y networking\n- Tema 5: Dependency Injection con Hilt\n- Tema 6: Testing en Android\n- Tema 7: Performance y optimización\n- Tema 8: App Android completa publicable"
            },
            "TypeScript": {
                "principiante": "- Tema 1: Instalación TypeScript, tipos básicos\n- Tema 2: Interfaces y type aliases\n- Tema 3: Funciones tipadas\n- Tema 4: Arrays y tuplas tipadas\n- Tema 5: Objetos y tipos literales\n- Tema 6: Union y intersection types\n- Tema 7: Clases básicas en TypeScript\n- Tema 8: Primer proyecto TypeScript",
                "intermedio": "- Tema 1: Generics en TypeScript\n- Tema 2: Decoradores y metadata\n- Tema 3: Módulos y namespaces\n- Tema 4: Type guards y narrowing\n- Tema 5: Utility types\n- Tema 6: Configuración avanzada tsconfig\n- Tema 7: TypeScript con React\n- Tema 8: Aplicación web tipada",
                "avanzado": "- Tema 1: Tipos avanzados y mapped types\n- Tema 2: Conditional types\n- Tema 3: Template literal types\n- Tema 4: Infer keyword y type inference\n- Tema 5: TypeScript con Node.js\n- Tema 6: Arquitectura y patrones\n- Tema 7: Testing tipado\n- Tema 8: Sistema full-stack con TypeScript"
            },
            "R": {
                "principiante": "- Tema 1: Instalación R y RStudio, sintaxis básica\n- Tema 2: Vectores y tipos de datos\n- Tema 3: Operadores y funciones básicas\n- Tema 4: Data frames y matrices\n- Tema 5: Lectura de datos CSV y Excel\n- Tema 6: Filtrado y selección de datos\n- Tema 7: Gráficos básicos con plot\n- Tema 8: Primer análisis de datos",
                "intermedio": "- Tema 1: dplyr para manipulación de datos\n- Tema 2: ggplot2 para visualización\n- Tema 3: tidyr y datos ordenados\n- Tema 4: Funciones y programación funcional\n- Tema 5: Estadística descriptiva\n- Tema 6: Pruebas de hipótesis básicas\n- Tema 7: Regresión lineal\n- Tema 8: Proyecto de análisis completo",
                "avanzado": "- Tema 1: Machine learning con caret\n- Tema 2: Modelos predictivos avanzados\n- Tema 3: Series temporales\n- Tema 4: Análisis multivariado\n- Tema 5: Shiny para aplicaciones web\n- Tema 6: R Markdown y reportes\n- Tema 7: Optimización y performance\n- Tema 8: Dashboard interactivo completo"
            },
            "MATLAB": {
                "principiante": "- Tema 1: Interfaz MATLAB, sintaxis básica\n- Tema 2: Vectores y matrices básicas\n- Tema 3: Operaciones matemáticas\n- Tema 4: Indexación y slicing\n- Tema 5: Gráficos 2D básicos\n- Tema 6: Scripts y funciones simples\n- Tema 7: Entrada/salida de datos\n- Tema 8: Primer proyecto de cálculo",
                "intermedio": "- Tema 1: Álgebra lineal en MATLAB\n- Tema 2: Gráficos 3D y visualización\n- Tema 3: Programación estructurada\n- Tema 4: Manejo de archivos y datos\n- Tema 5: Análisis numérico\n- Tema 6: Ecuaciones diferenciales\n- Tema 7: Optimización numérica\n- Tema 8: Simulación de sistemas",
                "avanzado": "- Tema 1: Simulink fundamentos\n- Tema 2: Procesamiento de señales\n- Tema 3: Procesamiento de imágenes\n- Tema 4: Machine learning con MATLAB\n- Tema 5: Sistemas de control\n- Tema 6: Optimización avanzada\n- Tema 7: Parallel computing\n- Tema 8: Proyecto de ingeniería completo"
            },
            "C": {
                "principiante": "- Tema 1: Instalación compilador, sintaxis básica\n- Tema 2: Variables, tipos de datos y operadores\n- Tema 3: Condicionales y bucles\n- Tema 4: Arrays y strings\n- Tema 5: Funciones y parámetros\n- Tema 6: Punteros básicos\n- Tema 7: Entrada/salida estándar\n- Tema 8: Primer programa en C",
                "intermedio": "- Tema 1: Punteros avanzados y aritmética\n- Tema 2: Estructuras y unions\n- Tema 3: Memoria dinámica: malloc, free\n- Tema 4: Archivos y streams\n- Tema 5: Preprocesador y macros\n- Tema 6: Listas enlazadas\n- Tema 7: Pilas y colas\n- Tema 8: Proyecto con estructuras de datos",
                "avanzado": "- Tema 1: Gestión avanzada de memoria\n- Tema 2: Programación de sistemas\n- Tema 3: Sockets y networking\n- Tema 4: Threads y concurrencia\n- Tema 5: Optimización y performance\n- Tema 6: Debugging avanzado\n- Tema 7: Interfaz con hardware\n- Tema 8: Sistema embebido o driver"
            }
        }
        
        # Obtener estructura específica o usar Python como fallback
        lang_structures = structures.get(language, structures["Python"])
        return lang_structures.get(level, lang_structures["principiante"])
    
    def _validate_topic_level(self, topic, language, level):
        """Valida que el tema sea apropiado para el nivel"""
        title = topic.get('title', '').lower()
        
        # Lista de todos los lenguajes para detectar menciones incorrectas
        all_languages = ['Python', 'JavaScript', 'Java', 'C++', 'C#', 'C', 'Ruby', 'PHP', 
                        'Go', 'Rust', 'Swift', 'Kotlin', 'TypeScript', 'SQL', 'NoSQL', 
                        'HTML/CSS', 'R', 'MATLAB']
        
        # Corregir menciones de lenguajes incorrectos en el título
        for wrong_lang in all_languages:
            if wrong_lang != language and wrong_lang.lower() in topic.get('title', '').lower():
                # Reemplazar el lenguaje incorrecto por el correcto
                topic['title'] = topic['title'].replace(wrong_lang, language)
                topic['title'] = topic['title'].replace(wrong_lang.lower(), language.lower())
        
        # Corregir menciones de lenguajes incorrectos en la descripción
        for wrong_lang in all_languages:
            if wrong_lang != language and wrong_lang.lower() in topic.get('description', '').lower():
                topic['description'] = topic['description'].replace(wrong_lang, language)
                topic['description'] = topic['description'].replace(wrong_lang.lower(), language.lower())
        
        # Palabras que indican nivel básico
        basic_keywords = ['básico', 'introducción', 'fundamentos', 'primeros pasos', 'sintaxis']
        
        # Palabras que indican nivel avanzado
        advanced_keywords = ['avanzado', 'optimización', 'arquitectura', 'patrones', 'profesional']
        
        # Ajustar según nivel
        if level == "principiante" and any(word in title for word in advanced_keywords):
            # Simplificar título para principiantes
            topic['title'] = topic['title'].replace('avanzado', 'básico').replace('Avanzado', 'Básico')
            topic['description'] = f"Introducción a {topic['description']}"
        
        elif level == "avanzado" and any(word in title for word in basic_keywords):
            # Hacer más avanzado para expertos
            topic['title'] = topic['title'].replace('básico', 'avanzado').replace('Básico', 'Avanzado')
            topic['description'] = f"Conceptos avanzados de {topic['description']}"
        
        return topic
    
    def _generate_fallback_topics_structure(self, language, level, sections_count):
        """Genera estructura de temas básica cuando la IA no está disponible"""
        topics_templates = {
            "Python": [
                {
                    "topic_number": 1,
                    "title": "Fundamentos de Python",
                    "description": "Aprende la sintaxis básica, variables, tipos de datos y operadores en Python",
                    "objectives": "Dominar variables, tipos de datos básicos, operadores y entrada/salida de datos",
                    "estimated_hours": 3,
                    "order_index": 0
                },
                {
                    "topic_number": 2,
                    "title": "Estructuras de Control",
                    "description": "Condicionales, bucles y control de flujo en Python",
                    "objectives": "Implementar lógica condicional y bucles para resolver problemas",
                    "estimated_hours": 4,
                    "order_index": 1
                },
                {
                    "topic_number": 3,
                    "title": "Funciones y Modularidad",
                    "description": "Definición de funciones, parámetros, return y organización del código",
                    "objectives": "Crear funciones reutilizables y organizar código de manera modular",
                    "estimated_hours": 4,
                    "order_index": 2
                },
                {
                    "topic_number": 4,
                    "title": "Estructuras de Datos",
                    "description": "Listas, diccionarios, tuplas y sets en Python",
                    "objectives": "Manipular y trabajar eficientemente con diferentes estructuras de datos",
                    "estimated_hours": 5,
                    "order_index": 3
                },
                {
                    "topic_number": 5,
                    "title": "Programación Orientada a Objetos",
                    "description": "Clases, objetos, herencia y encapsulación en Python",
                    "objectives": "Diseñar y implementar soluciones usando programación orientada a objetos",
                    "estimated_hours": 6,
                    "order_index": 4
                },
                {
                    "topic_number": 6,
                    "title": "Manejo de Excepciones y Archivos",
                    "description": "Gestión de errores, excepciones y trabajo con archivos en Python",
                    "objectives": "Manejar errores de forma robusta y trabajar con archivos de texto y binarios",
                    "estimated_hours": 4,
                    "order_index": 5
                },
                {
                    "topic_number": 7,
                    "title": "Módulos y Librerías",
                    "description": "Importación de módulos, uso de librerías estándar y externas",
                    "objectives": "Utilizar módulos y librerías para extender funcionalidades",
                    "estimated_hours": 5,
                    "order_index": 6
                },
                {
                    "topic_number": 8,
                    "title": "Proyecto Final Integrador",
                    "description": "Desarrollo de un proyecto completo aplicando todos los conceptos aprendidos",
                    "objectives": "Integrar todos los conocimientos en un proyecto real y funcional",
                    "estimated_hours": 8,
                    "order_index": 7
                }
            ],
            "JavaScript": [
                {
                    "topic_number": 1,
                    "title": "Fundamentos de JavaScript",
                    "description": "Sintaxis básica, variables, tipos de datos y operadores en JavaScript",
                    "objectives": "Dominar la sintaxis básica y conceptos fundamentales de JavaScript",
                    "estimated_hours": 3,
                    "order_index": 0
                },
                {
                    "topic_number": 2,
                    "title": "DOM y Eventos",
                    "description": "Manipulación del DOM y manejo de eventos en el navegador",
                    "objectives": "Crear páginas web interactivas manipulando el DOM",
                    "estimated_hours": 4,
                    "order_index": 1
                },
                {
                    "topic_number": 3,
                    "title": "Funciones y Scope",
                    "description": "Funciones, closures, scope y hoisting en JavaScript",
                    "objectives": "Entender el comportamiento de funciones y scope en JavaScript",
                    "estimated_hours": 4,
                    "order_index": 2
                },
                {
                    "topic_number": 4,
                    "title": "Arrays y Objetos",
                    "description": "Manipulación avanzada de arrays y objetos en JavaScript",
                    "objectives": "Trabajar eficientemente con estructuras de datos complejas",
                    "estimated_hours": 5,
                    "order_index": 3
                },
                {
                    "topic_number": 5,
                    "title": "Programación Asíncrona",
                    "description": "Callbacks, Promises y async/await en JavaScript",
                    "objectives": "Manejar operaciones asíncronas de manera efectiva",
                    "estimated_hours": 5,
                    "order_index": 4
                },
                {
                    "topic_number": 6,
                    "title": "APIs y Fetch",
                    "description": "Consumo de APIs REST y manejo de datos JSON",
                    "objectives": "Integrar APIs externas en aplicaciones web",
                    "estimated_hours": 4,
                    "order_index": 5
                },
                {
                    "topic_number": 7,
                    "title": "ES6+ y Características Modernas",
                    "description": "Arrow functions, destructuring, spread operator y más",
                    "objectives": "Utilizar características modernas de JavaScript",
                    "estimated_hours": 4,
                    "order_index": 6
                },
                {
                    "topic_number": 8,
                    "title": "Proyecto Web Completo",
                    "description": "Desarrollo de una aplicación web completa con JavaScript",
                    "objectives": "Crear una aplicación web funcional integrando todos los conceptos",
                    "estimated_hours": 8,
                    "order_index": 7
                }
            ]
        }
        
        # Obtener plantilla del lenguaje o usar Python por defecto
        template = topics_templates.get(language, topics_templates["Python"])
        
        # Retornar exactamente el número de secciones solicitado
        return template[:sections_count]
    
    def generate_topic_materials_spanish(self, language, topic_title, topic_description, level):
        """Genera materiales en español específicos para el nivel del estudiante"""
        if not self.model:
            return self._generate_fallback_topic_materials(language, topic_title, level)
        
        try:
            # Buscar video real de YouTube para el tema
            video_url = self._find_youtube_video(language, topic_title, level)
            
            # Solo retornar el video, sin materiales adicionales
            video_material = {
                "type": "video",
                "title": f"Video tutorial completo sobre {topic_title} adaptado para nivel {level}",
                "description": f"Tutorial en video que cubre los conceptos fundamentales de {topic_title} en {language}",
                "url": video_url,
                "order_index": 0,
                "estimated_minutes": 30,
                "difficulty_level": self._get_difficulty_number(level),
                "language_content": "es"
            }
            
            return [video_material]
                
        except Exception as e:
            return self._generate_fallback_topic_materials(language, topic_title, level)
    
    def _find_youtube_video(self, language, topic_title, level):
        """Usa IA para generar búsqueda específica de video en YouTube según nivel"""
        try:
            # Mapeo de niveles a términos descriptivos
            level_descriptions = {
                'principiante': 'para principiantes desde cero, explicación básica y simple',
                'intermedio': 'nivel intermedio, con ejemplos prácticos',
                'avanzado': 'nivel avanzado, conceptos complejos y optimización'
            }
            level_desc = level_descriptions.get(level.lower(), 'tutorial')
            
            # Usar IA para generar búsqueda específica
            prompt = f"""Genera una consulta de búsqueda de YouTube MUY ESPECÍFICA en ESPAÑOL para:

Lenguaje: {language}
Tema: {topic_title}
Nivel: {level} ({level_desc})

La búsqueda debe incluir:
- El lenguaje de programación
- El tema EXACTO (no genérico)
- El nivel específico: {level}
- La palabra "tutorial" o "español"

IMPORTANTE: El video debe ser apropiado para nivel {level}:
- Si es principiante: buscar tutoriales básicos, desde cero, para beginners
- Si es intermedio: buscar tutoriales con ejemplos prácticos, aplicaciones reales
- Si es avanzado: buscar tutoriales avanzados, optimización, mejores prácticas

Responde SOLO con la consulta de búsqueda, sin comillas ni explicaciones.

Ejemplos:
- Principiante: "Python variables principiantes desde cero tutorial español"
- Intermedio: "Ruby módulos y mixins intermedio tutorial español"
- Avanzado: "JavaScript async await avanzado optimización español"

Tu búsqueda para {language} - {topic_title} - {level}:"""
            
            # Usar call_with_retry en lugar de llamada directa - MÁS ROBUSTO
            response = self.call_with_retry(prompt, max_retries=3, max_output_tokens=100, temperature=0.5)
            
            # Verificar si hay error
            if not response or "Error" in response:
                return self._get_fallback_video(language, topic_title, level)
            
            search_query = response.strip()
            
            # Limpiar la respuesta
            search_query = search_query.replace('"', '').replace("'", "").replace('\n', ' ')
            search_query = search_query.replace(' ', '+')
            
            # Retornar URL de búsqueda de YouTube
            return f"https://www.youtube.com/results?search_query={search_query}"
            
        except Exception as e:
            # Fallback: búsqueda manual específica con nivel
            return self._get_fallback_video(language, topic_title, level)
    
    def _get_fallback_video(self, language, topic_title, level):
        """Genera URL de búsqueda de YouTube como fallback"""
        # Mapeo de niveles a términos de búsqueda
        level_terms = {
            'principiante': 'principiantes desde cero',
            'intermedio': 'intermedio',
            'avanzado': 'avanzado'
        }
        
        level_term = level_terms.get(level.lower(), 'tutorial')
        
        # Construir búsqueda específica
        search_query = f"{language} {topic_title} {level_term} español tutorial"
        search_query = search_query.replace(' ', '+')
        
        return f"https://www.youtube.com/results?search_query={search_query}"
    
    def _get_difficulty_number(self, level):
        """Convierte nivel de texto a número"""
        level_map = {
            'principiante': 1,
            'intermedio': 2,
            'avanzado': 3
        }
        return level_map.get(level.lower(), 1)
    
    def _get_material_level_content(self, level):
        """Obtiene especificaciones de contenido por nivel"""
        content = {
            "principiante": """
            - Estudiante necesita explicaciones muy detalladas
            - Materiales introductorios y básicos
            - Videos tutoriales paso a paso
            - Documentación para principiantes
            - Ejercicios guiados y simples
            """,
            "intermedio": """
            - Estudiante tiene conocimientos básicos
            - Materiales de nivel medio
            - Tutoriales de aplicación práctica
            - Documentación técnica estándar
            - Ejercicios con casos reales
            """,
            "avanzado": """
            - Estudiante tiene experiencia
            - Materiales avanzados y especializados
            - Videos de expertos y mejores prácticas
            - Documentación avanzada y optimización
            - Proyectos complejos y desafiantes
            """
        }
        return content.get(level, content["principiante"])
    
    def _generate_fallback_topic_materials(self, language, topic_title, level):
        """Genera materiales básicos cuando la IA no está disponible"""
        # Generar URLs de búsqueda reales de YouTube
        search_base = f"{language.lower()}+{topic_title.lower().replace(' ', '+')}+tutorial+español"
        
        # URLs de documentación por lenguaje
        docs_urls = {
            "Python": "https://docs.python.org/es/3/",
            "JavaScript": "https://developer.mozilla.org/es/docs/Web/JavaScript",
            "Java": "https://docs.oracle.com/javase/tutorial/",
            "C++": "https://en.cppreference.com/w/",
            "SQL": "https://www.postgresql.org/docs/",
            "NoSQL": "https://docs.mongodb.com/",
            "HTML/CSS": "https://developer.mozilla.org/es/docs/Web/HTML",
            "C#": "https://docs.microsoft.com/es-es/dotnet/csharp/",
            "PHP": "https://www.php.net/manual/es/",
            "Ruby": "https://www.ruby-lang.org/es/documentation/"
        }
        
        # URLs de tutoriales por lenguaje
        tutorial_urls = {
            "Python": "https://www.w3schools.com/python/",
            "JavaScript": "https://www.w3schools.com/js/",
            "Java": "https://www.w3schools.com/java/",
            "C++": "https://www.w3schools.com/cpp/",
            "SQL": "https://www.w3schools.com/sql/",
            "HTML/CSS": "https://www.w3schools.com/html/",
            "C#": "https://www.w3schools.com/cs/",
            "PHP": "https://www.w3schools.com/php/"
        }
        
        return [
            {
                "type": "video",
                "title": f"Tutorial de {topic_title} en {language} - Nivel {level}",
                "description": f"Video tutorial completo sobre {topic_title} en español",
                "url": f"https://www.youtube.com/results?search_query={search_base}+{level}",
                "order_index": 0,
                "estimated_minutes": 45,
                "difficulty_level": self._get_difficulty_number(level),
                "language_content": "es"
            },
            {
                "type": "video",
                "title": f"Ejemplos Prácticos de {topic_title}",
                "description": f"Ejemplos y ejercicios prácticos de {topic_title}",
                "url": f"https://www.youtube.com/results?search_query={search_base}+ejemplos+practicos",
                "order_index": 1,
                "estimated_minutes": 30,
                "difficulty_level": self._get_difficulty_number(level),
                "language_content": "es"
            },
            {
                "type": "website",
                "title": f"Documentación Oficial de {language}",
                "description": f"Documentación oficial sobre {topic_title}",
                "url": docs_urls.get(language, "https://www.google.com/search?q=" + language + "+documentation"),
                "order_index": 2,
                "estimated_minutes": 30,
                "difficulty_level": self._get_difficulty_number(level),
                "language_content": "es"
            },
            {
                "type": "tutorial",
                "title": f"Tutorial Interactivo: {topic_title}",
                "description": f"Tutorial interactivo paso a paso sobre {topic_title}",
                "url": tutorial_urls.get(language, "https://www.w3schools.com/"),
                "order_index": 3,
                "estimated_minutes": 60,
                "difficulty_level": self._get_difficulty_number(level),
                "language_content": "es"
            },
            {
                "type": "documentation",
                "title": f"Guía Completa de {topic_title}",
                "description": f"Guía detallada y completa sobre {topic_title}",
                "url": f"https://www.google.com/search?q={language}+{topic_title}+guia+español",
                "order_index": 4,
                "estimated_minutes": 40,
                "difficulty_level": self._get_difficulty_number(level),
                "language_content": "es"
            }
        ]
    
    def generate_topic_exercises(self, language, topic_title, level, difficulty_setting='normal', topic_content=''):
        """
        Genera 20 preguntas de opción múltiple basadas DIRECTAMENTE en el contenido de la lección.
        Las preguntas se extraen del contenido real que se acaba de generar.
        """
        if not self.model:
            import streamlit as st
            st.warning("[!] IA no disponible - usando ejercicio básico")
            return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
        
        try:
            import streamlit as st
            import json
            import re
            
            # CRÍTICO: Necesitamos el contenido de la lección para generar preguntas relevantes
            if not topic_content or len(topic_content) < 100:
                st.warning("⚠️ Contenido insuficiente para generar preguntas específicas")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Usar TODO el contenido disponible (máximo 3000 caracteres para no exceder límites)
            content_for_questions = topic_content[:3000]
            
            # Prompt COMPLETAMENTE NUEVO - Basado en el contenido real
            prompt = f"""Basándote EXCLUSIVAMENTE en el siguiente contenido de la lección, genera 20 preguntas de opción múltiple.

{'=' * 80}
CONTENIDO DE LA LECCIÓN (USA ESTO COMO BASE):
{'=' * 80}
{content_for_questions}

{'=' * 80}
INSTRUCCIONES CRÍTICAS:
{'=' * 80}

1. Lee el contenido de la lección arriba
2. Genera 20 preguntas que evalúen la comprensión de ESE contenido específico
3. Las preguntas deben ser sobre conceptos, código o ejemplos que APARECEN en el contenido
4. NO inventes preguntas genéricas - usa el contenido real

FORMATO DE CADA PREGUNTA:
- Pregunta clara sobre algo del contenido
- 4 opciones de respuesta (A, B, C, D)
- 1 opción correcta + 3 opciones incorrectas pero plausibles
- Explicación de por qué la respuesta es correcta

TIPOS DE PREGUNTAS (basadas en el contenido):
1. Sobre conceptos explicados en la lección
2. Sobre código de ejemplo mostrado
3. Sobre sintaxis o estructuras mencionadas
4. Sobre casos de uso o aplicaciones descritas
5. Sobre diferencias o comparaciones hechas

NIVEL: {level.upper()}
LENGUAJE: {language}

{'=' * 80}
FORMATO JSON DE RESPUESTA:
{'=' * 80}

{{
  "title": "Evaluación: {topic_title}",
  "description": "Responde las siguientes 20 preguntas sobre {topic_title} en {language}. Todas las preguntas están basadas en el contenido de la lección.",
  "questions": [
    {{
      "question": "[Pregunta basada en el contenido de la lección]",
      "options": [
        "Opción A (correcta)",
        "Opción B (incorrecta)",
        "Opción C (incorrecta)",
        "Opción D (incorrecta)"
      ],
      "correct_index": 0,
      "explanation": "Esta es la respuesta correcta porque [referencia al contenido de la lección]"
    }}
    ... (20 preguntas en total)
  ],
  "hints": "Revisa el contenido de la lección sobre {topic_title}"
}}

CRÍTICO:
- Genera EXACTAMENTE 20 preguntas
- TODAS basadas en el contenido proporcionado arriba
- Opciones específicas y relevantes
- TODO en español

Genera ahora tu JSON con 20 preguntas basadas en el contenido:
"""
            
            # Llamar a la IA con el prompt
            response = self.call_with_retry(prompt, max_retries=2, max_output_tokens=6000, temperature=0.7)
            
            if not response or not response.strip():
                st.error("[ERROR] Sin respuesta del modelo")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Parsear JSON con manejo robusto de errores
            result = None
            try:
                result = self.extract_json_from_response(response, 'dict')
            except:
                pass
            
            if not result:
                try:
                    # Intentar parseo manual
                    response_clean = response.strip()
                    start = response_clean.find('{')
                    if start == -1:
                        raise ValueError("No JSON found")
                    
                    # Buscar cierre del JSON
                    depth = 0
                    end = -1
                    for i in range(start, len(response_clean)):
                        if response_clean[i] == '{':
                            depth += 1
                        elif response_clean[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i
                                break
                    
                    if end == -1:
                        # Agregar cierres faltantes
                        json_str = response_clean[start:]
                        open_braces = json_str.count('{')
                        close_braces = json_str.count('}')
                        json_str += '}' * (open_braces - close_braces)
                    else:
                        json_str = response_clean[start:end+1]
                    
                    # Limpiar JSON
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    result = json.loads(json_str)
                    
                except Exception as e:
                    st.error(f"[ERROR] No se pudo parsear JSON: {str(e)[:100]}")
                    return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Validar resultado
            if not result or not isinstance(result, dict):
                st.error("[ERROR] Respuesta inválida")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Agregar campos faltantes
            if 'title' not in result:
                result['title'] = f"Evaluación: {topic_title}"
            if 'description' not in result:
                result['description'] = f"Preguntas sobre {topic_title}"
            
            # Validar preguntas
            if 'questions' not in result or not isinstance(result['questions'], list):
                st.error("[ERROR] No hay preguntas")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Limitar a 20 preguntas
            if len(result['questions']) > 20:
                result['questions'] = result['questions'][:20]
            
            # Validar cada pregunta
            valid_questions = []
            for q in result['questions']:
                if isinstance(q, dict) and 'question' in q and 'options' in q and 'correct_index' in q:
                    if isinstance(q['options'], list) and len(q['options']) == 4:
                        valid_questions.append(q)
            
            if len(valid_questions) < 10:
                st.warning(f"⚠️ Solo {len(valid_questions)} preguntas válidas, usando fallback")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            result['questions'] = valid_questions[:20]
            
            # Convertir a formato de ejercicio
            result['exercise_type'] = 'multiple_choice'
            result['difficulty_level'] = {'principiante': 1, 'intermedio': 2, 'avanzado': 3}.get(level.lower(), 2)
            result['order_index'] = 0
            result['points'] = 10
            result['is_required'] = True
            result['solution_code'] = ''
            result['initial_code'] = ''
            result['test_cases'] = json.dumps(result['questions'])
            
            if not result.get('hints'):
                result['hints'] = f"Revisa el contenido de la lección sobre {topic_title}"
            
            return [result]
                
        except Exception as e:
            import streamlit as st
            st.warning(f"[!] Error al generar ejercicio: {str(e)[:100]}")
            return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
    
    def _get_exercise_example_by_level(self, language, topic_title, level):
        """Genera ejemplo de ejercicio apropiado según el nivel"""
        if level.lower() == 'principiante':
            return '''{
  "title": "[LIBROS] Calculadora Simple de ''' + topic_title + '''",
  "description": "Crea una calculadora básica en ''' + language + ''' que demuestre ''' + topic_title + '''.\\n\\n**Requisitos (SIMPLE):**\\n1. Crear una función que sume dos números\\n2. Crear una función que reste dos números\\n3. Mostrar los resultados en pantalla\\n\\n**Ejemplos:**\\n• Entrada: suma(5, 3) → Salida: 8\\n• Entrada: resta(10, 4) → Salida: 6",
  "hints": "1) Define funciones simples. 2) Usa print para mostrar resultados. 3) Prueba con números diferentes."
}'''
        elif level.lower() == 'intermedio':
            return '''{
  "title": "[EMOJI] Sistema de Gestión con ''' + topic_title + '''",
  "description": "Crea un sistema de gestión en ''' + language + ''' aplicando ''' + topic_title + '''.\\n\\n**Requisitos (MODERADO):**\\n1. Clase principal con 3-4 atributos\\n2. Métodos para agregar, buscar y eliminar\\n3. Validaciones de datos de entrada\\n4. Manejo de casos cuando no se encuentra un elemento\\n5. Método para listar todos los elementos\\n\\n**Ejemplos:**\\n• Entrada: agregar('Item1') → Salida: Item agregado exitosamente\\n• Entrada: buscar('Item1') → Salida: Item encontrado\\n• Entrada: buscar('NoExiste') → Salida: Error: Item no encontrado",
  "hints": "1) Usa clases y objetos. 2) Valida antes de cada operación. 3) Usa estructuras de datos apropiadas."
}'''
        else:  # avanzado
            return '''{
  "title": "[EDUCACION] Sistema Complejo con ''' + topic_title + ''' y Optimización",
  "description": "Crea un sistema avanzado en ''' + language + ''' que demuestre dominio de ''' + topic_title + '''.\\n\\n**Requisitos (COMPLEJO):**\\n1. Múltiples clases con herencia/composición\\n2. Implementar patrón de diseño apropiado\\n3. Sistema de caché para optimización\\n4. Manejo robusto de errores y excepciones\\n5. Validaciones complejas con múltiples reglas\\n6. Logging de operaciones\\n7. Métodos de búsqueda optimizados (O(log n) o mejor)\\n8. Tests unitarios para funciones críticas\\n\\n**Ejemplos:**\\n• Entrada: operación_compleja(datos) → Salida: Resultado optimizado con caché\\n• Entrada: datos_inválidos → Salida: Excepción específica con mensaje detallado\\n• Entrada: búsqueda_masiva(1000 items) → Salida: Resultados en < 100ms",
  "hints": "1) Aplica SOLID principles. 2) Optimiza algoritmos críticos. 3) Maneja todos los casos edge. 4) Documenta decisiones de diseño."
}'''
    
    def _generate_simple_fallback_exercise(self, language, topic_title, level, topic_content=''):
        """Genera un ejercicio simple cuando la IA falla completamente"""
        import random
        
        # Diferentes tipos de ejercicios para variar
        exercise_types = [
            ("Calculadora", f"Crea una calculadora en {language} que realice operaciones relacionadas con {topic_title}."),
            ("Validador", f"Crea un programa en {language} que valide datos usando conceptos de {topic_title}."),
            ("Conversor", f"Crea un conversor en {language} aplicando los conceptos de {topic_title}."),
            ("Analizador", f"Crea un analizador en {language} que procese información usando {topic_title}."),
            ("Generador", f"Crea un generador en {language} que produzca resultados basados en {topic_title}."),
            ("Sistema", f"Crea un mini-sistema en {language} que demuestre tu comprensión de {topic_title}.")
        ]
        
        ex_type, base_description = random.choice(exercise_types)
        
        # Intentar hacer el ejercicio más específico si hay contexto
        description = base_description
        
        if topic_content and len(topic_content) > 50:
            # Extraer algunas palabras clave del contexto
            words = topic_content.split()
            keywords = [w for w in words if len(w) > 5][:3]
            if keywords:
                description += f" Incorpora conceptos como: {', '.join(keywords)}."
        
        description += f" Asegúrate de comentar tu código, seguir las mejores prácticas de {language}, y probar con diferentes casos."
        
        return [
            {
                "title": f"{ex_type} de {topic_title}",
                "description": description,
                "exercise_type": "coding",
                "difficulty_level": 2,
                "initial_code": f"# {ex_type} de {topic_title}\n# Escribe tu código aquí\n\n",
                "solution_code": "",
                "test_cases": "[]",
                "hints": f"1) Revisa el contenido de {topic_title}, 2) Piensa en casos de uso reales, 3) Escribe código limpio y comentado",
                "order_index": 0,
                "points": 10,
                "is_required": True
            }
        ]
    
    def _generate_fallback_topic_exercises(self, language, topic_title, level):
        """DEPRECADO: Usar _generate_simple_fallback_exercise en su lugar"""
        return self._generate_simple_fallback_exercise(language, topic_title, level)
    
    def generate_topic_evaluation(self, language, topic_title, level, difficulty_setting='normal'):
        """Genera evaluación para un tema específico"""
        if not self.model:
            return self._generate_fallback_topic_evaluation(language, topic_title, level)
        
        try:
            # Configuración de dificultad y especificaciones
            difficulty_map = {
                'facil': {'code_lines': '5-10', 'complexity': 'muy simple'},
                'normal': {'code_lines': '10-20', 'complexity': 'moderada'},
                'dificil': {'code_lines': '20-30', 'complexity': 'compleja'}
            }
            spec = difficulty_map.get(difficulty_setting, difficulty_map['normal'])
            
            prompt = f"""
            Genera 20 preguntas de evaluación para {topic_title} en {language}.
            
            IMPORTANTE - MOSTRAR DATOS EN LAS PREGUNTAS:
            
            Para preguntas de SQL, SIEMPRE incluir la tabla con datos:
            
            EJEMPLO CORRECTO:
            ```sql
            -- Tabla clientes:
            -- | id | nombre      | ciudad    | edad |
            -- |----|-------------|-----------|------|
            -- | 1  | Juan Pérez  | Madrid    | 30   |
            -- | 2  | Ana García  | Sevilla   | 25   |
            -- | 3  | María López | Barcelona | 28   |
            -- | 4  | Pedro Gómez | Madrid    | 35   |

            SELECT nombre FROM clientes WHERE ciudad = 'Madrid';
            ```
            ¿Cuál es el resultado de esta consulta?
            ¿Cuál es el resultado de esta consulta?
            A) Juan Pérez
            B) Ana García
            C) María López
            D) Pedro Gómez

            Respuesta correcta: A) Juan Pérez
            Explicación: La consulta busca el nombre donde ciudad = 'Madrid'. En la tabla, solo Juan Pérez (id=1) tiene ciudad = 'Madrid'. Pedro Gómez también está en Madrid pero la consulta sin LIMIT devuelve el primer resultado.

            MEJOR AÚN - Si hay múltiples resultados:
            ```sql
            -- Tabla clientes:
            -- | id | nombre      | ciudad    | edad |
            -- |----|-------------|-----------|------|
            -- | 1  | Juan Pérez  | Madrid    | 30   |
            -- | 2  | Ana García  | Sevilla   | 25   |
            -- | 3  | María López | Barcelona | 28   |
            -- | 4  | Pedro Gómez | Valencia  | 35   |

            SELECT COUNT(*) FROM clientes WHERE edad > 25;
            ```
            ¿Cuántos clientes tienen más de 25 años?
            A) 1
            B) 2
            C) 3
            D) 4

            Respuesta correcta: B) 2
            Explicación: Los clientes con edad > 25 son: Juan Pérez (30) y Pedro Gómez (35). Total: 2 clientes.

            {'=' * 80}
            MÁS EJEMPLOS CORRECTOS:
            {'=' * 80}

            Python con lista:
            ```python
            # Lista de números
            numeros = [10, 25, 30, 15, 40]

            resultado = [x for x in numeros if x > 20]
            print(len(resultado))
            ```
            ¿Qué imprime este código?
            A) 2
            B) 3
            C) 4
            D) 5

            Respuesta: B) 3
            Explicación: Los números mayores a 20 son: 25, 30, 40. Total: 3 elementos.

            JavaScript con objeto:
            ```javascript
            // Objeto persona
            const persona = {{
                nombre: "Carlos",
                edad: 28,
                ciudad: "Madrid"
            }};

            console.log(persona.edad + 2);
            ```
            ¿Qué se imprime en consola?
            A) 28
            B) 30
            C) 282
            D) NaN

            Respuesta: B) 30
            Explicación: persona.edad es 28, sumamos 2, resultado: 30.

            {'=' * 80}
            FORMATO DE RESPUESTA JSON:
            {'=' * 80}

            {{
              "title": "Evaluación: {topic_title}",
              "description": "Responde las siguientes 20 preguntas sobre {topic_title} en {language}. Lee cuidadosamente los datos proporcionados.",
              "questions": [
                {{
                  "question": "-- Tabla [nombre]:\\n-- | col1 | col2 | col3 |\\n-- |------|------|------|\\n-- | val1 | val2 | val3 |\\n-- | val4 | val5 | val6 |\\n\\n```{language.lower()}\\n[CÓDIGO]\\n```\\n\\n¿[PREGUNTA]?",
                  "options": [
                    "Valor específico 1",
                    "Valor específico 2",
                    "Valor específico 3",
                    "Valor específico 4"
                  ],
                  "correct_index": 0,
                  "explanation": "Explicación paso a paso de cómo llegar a la respuesta correcta."
                }}
                ... (20 preguntas en total)
              ],
              "hints": "Revisa los conceptos de {topic_title}"
            }}

            {'=' * 80}
            REQUISITOS FINALES:
            {'=' * 80}

            ✓ 20 preguntas variadas
            ✓ SIEMPRE mostrar datos en formato tabla si es necesario
            ✓ Código funcional de {spec['code_lines']} líneas
            ✓ Opciones con valores ESPECÍFICOS
            ✓ Explicación detallada
            ✓ Nivel {level.upper()}
            ✓ TODO en español

            Genera ahora tu JSON con 20 preguntas CON DATOS VISIBLES:
            """
            
            # Llamar con configuración de variabilidad
            response = self.call_with_retry(prompt, max_retries=3, max_output_tokens=8000, temperature=0.8)
            
            # Verificar si hay error
            if not response or not response.strip():
                st.error(f"[ERROR] Error en respuesta de IA: Sin respuesta del modelo")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Verificar errores de cuota
            if "Cuota" in response or "agotada" in response or "quota" in response.lower():
                st.error(f"[ERROR] Error de cuota de IA: {response[:200]}")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Extraer JSON de la respuesta con mejor manejo
            result = None
            try:
                result = self.extract_json_from_response(response, 'dict')
            except:
                pass
            
            # Si no se pudo parsear, intentar manualmente con mejor limpieza
            if not result:
                try:
                    import json
                    response_clean = response.strip()
                    
                    # Buscar el inicio del JSON
                    start = response_clean.find('{')
                    if start == -1:
                        raise ValueError("No se encontró inicio de JSON")
                    
                    # Buscar el final del JSON (último } que cierra el objeto principal)
                    depth = 0
                    end = -1
                    for i in range(start, len(response_clean)):
                        if response_clean[i] == '{':
                            depth += 1
                        elif response_clean[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i
                                break
                    
                    if end == -1:
                        # Si no encontramos el cierre, intentar agregar cierres faltantes
                        json_str = response_clean[start:]
                        # Contar { y } para saber cuántos faltan
                        open_braces = json_str.count('{')
                        close_braces = json_str.count('}')
                        missing_braces = open_braces - close_braces
                        if missing_braces > 0:
                            json_str += '}' * missing_braces
                    else:
                        json_str = response_clean[start:end+1]
                    
                    # Limpiar JSON: eliminar comas antes de } o ]
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    
                    # Intentar parsear
                    result = json.loads(json_str)
                    
                except Exception as parse_error:
                    st.error(f"[ERROR] No se pudo parsear el JSON. Error: {str(parse_error)[:100]}")
                    st.info("💡 Intentando generar ejercicio de respaldo...")
                    return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Validar que el resultado sea un diccionario
            if not result or not isinstance(result, dict):
                st.error(f"[ERROR] La respuesta no es un diccionario válido. Tipo: {type(result)}")
                st.info("💡 Generando ejercicio de respaldo...")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # Validar campos básicos (con valores por defecto si faltan)
            if 'title' not in result:
                result['title'] = f"Evaluación: {topic_title}"
            if 'description' not in result:
                result['description'] = f"Responde las siguientes preguntas sobre {topic_title} en {language}."
            
            # Validar que tenga preguntas
            if 'questions' not in result or not isinstance(result['questions'], list) or len(result['questions']) == 0:
                st.error(f"[ERROR] No se generaron preguntas válidas")
                st.info("💡 Generando ejercicio de respaldo...")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            # CRÍTICO: Limitar a exactamente 20 preguntas (la IA a veces genera más)
            if len(result['questions']) > 20:
                st.warning(f"⚠️ Se generaron {len(result['questions'])} preguntas, limitando a 20")
                result['questions'] = result['questions'][:20]
            
            # Validar que cada pregunta tenga los campos necesarios
            valid_questions = []
            for idx, q in enumerate(result['questions']):
                if isinstance(q, dict) and 'question' in q and 'options' in q and 'correct_index' in q:
                    valid_questions.append(q)
                else:
                    st.warning(f"⚠️ Pregunta {idx+1} inválida, omitiendo...")
            
            if len(valid_questions) == 0:
                st.error(f"[ERROR] No hay preguntas válidas")
                st.info("💡 Generando ejercicio de respaldo...")
                return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
            
            result['questions'] = valid_questions
            st.success(f"✅ Se generaron {len(valid_questions)} preguntas válidas")
            
            # Convertir formato de preguntas a formato de ejercicio
            result['exercise_type'] = 'multiple_choice'
            result['difficulty_level'] = {'principiante': 1, 'intermedio': 2, 'avanzado': 3}.get(level.lower(), 2)
            result['order_index'] = 0
            result['points'] = 10
            result['is_required'] = True
            result['solution_code'] = ''
            result['initial_code'] = ''
            result['test_cases'] = json.dumps(result['questions'])  # Guardar preguntas aquí
            
            # Asegurar que hints sea string
            if not result.get('hints'):
                result['hints'] = f"Revisa el contenido de la lección sobre {topic_title}. Presta atención a los ejemplos de código y conceptos clave."
            elif isinstance(result['hints'], list):
                result['hints'] = '. '.join(result['hints'])
            elif not isinstance(result['hints'], str):
                result['hints'] = str(result['hints'])
            
            return [result]
                
        except Exception as e:
            import streamlit as st
            st.warning(f"[!] Error al generar ejercicio: {str(e)[:100]}")
            return self._generate_simple_fallback_exercise(language, topic_title, level, topic_content)
    
    def _get_exercise_example_by_level(self, language, topic_title, level):
        """Genera ejemplo de ejercicio apropiado según el nivel"""
        if level.lower() == 'principiante':
            return '''{
  "title": "[LIBROS] Calculadora Simple de ''' + topic_title + '''",
  "description": "Crea una calculadora básica en ''' + language + ''' que demuestre ''' + topic_title + '''.\\n\\n**Requisitos (SIMPLE):**\\n1. Crear una función que sume dos números\\n2. Crear una función que reste dos números\\n3. Mostrar los resultados en pantalla\\n\\n**Ejemplos:**\\n• Entrada: suma(5, 3) → Salida: 8\\n• Entrada: resta(10, 4) → Salida: 6",
  "hints": "1) Define funciones simples. 2) Usa print para mostrar resultados. 3) Prueba con números diferentes."
}'''
        elif level.lower() == 'intermedio':
            return '''{
  "title": "[EMOJI] Sistema de Gestión con ''' + topic_title + '''",
  "description": "Crea un sistema de gestión en ''' + language + ''' aplicando ''' + topic_title + '''.\\n\\n**Requisitos (MODERADO):**\\n1. Clase principal con 3-4 atributos\\n2. Métodos para agregar, buscar y eliminar\\n3. Validaciones de datos de entrada\\n4. Manejo de casos cuando no se encuentra un elemento\\n5. Método para listar todos los elementos\\n\\n**Ejemplos:**\\n• Entrada: agregar('Item1') → Salida: Item agregado exitosamente\\n• Entrada: buscar('Item1') → Salida: Item encontrado\\n• Entrada: buscar('NoExiste') → Salida: Error: Item no encontrado",
  "hints": "1) Usa clases y objetos. 2) Valida antes de cada operación. 3) Usa estructuras de datos apropiadas."
}'''
        else:  # avanzado
            return '''{
  "title": "[EDUCACION] Sistema Complejo con ''' + topic_title + ''' y Optimización",
  "description": "Crea un sistema avanzado en ''' + language + ''' que demuestre dominio de ''' + topic_title + '''.\\n\\n**Requisitos (COMPLEJO):**\\n1. Múltiples clases con herencia/composición\\n2. Implementar patrón de diseño apropiado\\n3. Sistema de caché para optimización\\n4. Manejo robusto de errores y excepciones\\n5. Validaciones complejas con múltiples reglas\\n6. Logging de operaciones\\n7. Métodos de búsqueda optimizados (O(log n) o mejor)\\n8. Tests unitarios para funciones críticas\\n\\n**Ejemplos:**\\n• Entrada: operación_compleja(datos) → Salida: Resultado optimizado con caché\\n• Entrada: datos_inválidos → Salida: Excepción específica con mensaje detallado\\n• Entrada: búsqueda_masiva(1000 items) → Salida: Resultados en < 100ms",
  "hints": "1) Aplica SOLID principles. 2) Optimiza algoritmos críticos. 3) Maneja todos los casos edge. 4) Documenta decisiones de diseño."
}'''
    
    def _generate_simple_fallback_exercise(self, language, topic_title, level, topic_content=''):
        """Genera un ejercicio simple cuando la IA falla completamente"""
        import random
        
        # Diferentes tipos de ejercicios para variar
        exercise_types = [
            ("Calculadora", f"Crea una calculadora en {language} que realice operaciones relacionadas con {topic_title}."),
            ("Validador", f"Crea un programa en {language} que valide datos usando conceptos de {topic_title}."),
            ("Conversor", f"Crea un conversor en {language} aplicando los conceptos de {topic_title}."),
            ("Analizador", f"Crea un analizador en {language} que procese información usando {topic_title}."),
            ("Generador", f"Crea un generador en {language} que produzca resultados basados en {topic_title}."),
            ("Sistema", f"Crea un mini-sistema en {language} que demuestre tu comprensión de {topic_title}.")
        ]
        
        ex_type, base_description = random.choice(exercise_types)
        
        # Intentar hacer el ejercicio más específico si hay contexto
        description = base_description
        
        if topic_content and len(topic_content) > 50:
            # Extraer algunas palabras clave del contexto
            words = topic_content.split()
            keywords = [w for w in words if len(w) > 5][:3]
            if keywords:
                description += f" Incorpora conceptos como: {', '.join(keywords)}."
        
        description += f" Asegúrate de comentar tu código, seguir las mejores prácticas de {language}, y probar con diferentes casos."
        
        return [
            {
                "title": f"{ex_type} de {topic_title}",
                "description": description,
                "exercise_type": "coding",
                "difficulty_level": 2,
                "initial_code": f"# {ex_type} de {topic_title}\n# Escribe tu código aquí\n\n",
                "solution_code": "",
                "test_cases": "[]",
                "hints": f"1) Revisa el contenido de {topic_title}, 2) Piensa en casos de uso reales, 3) Escribe código limpio y comentado",
                "order_index": 0,
                "points": 10,
                "is_required": True
            }
        ]
    
    def _generate_fallback_topic_exercises(self, language, topic_title, level):
        """DEPRECADO: Usar _generate_simple_fallback_exercise en su lugar"""
        return self._generate_simple_fallback_exercise(language, topic_title, level)
    
    def generate_topic_evaluation(self, language, topic_title, level, difficulty_setting='normal'):
        """Genera evaluación para un tema específico"""
        if not self.model:
            return self._generate_fallback_topic_evaluation(language, topic_title, level)
        
        try:
            difficulty_map = {
                'facil': 'fácil con preguntas básicas',
                'normal': 'moderado con preguntas equilibradas',
                'dificil': 'desafiante con preguntas avanzadas'
            }
            difficulty_desc = difficulty_map.get(difficulty_setting, 'moderado')
            
            prompt = f"""
            Genera una evaluación completa en ESPAÑOL para el siguiente tema:
            
            TEMA: {topic_title}
            LENGUAJE: {language}
            NIVEL: {level}
            DIFICULTAD: {difficulty_desc}
            
            *** REGLA CRÍTICA - TODAS LAS PREGUNTAS DEBEN INCLUIR CÓDIGO ***
            
            Cada pregunta DEBE incluir un ejemplo de código funcional de 3-15 líneas.
            El código debe estar en un bloque markdown con el formato:
            
            ```{language.lower()}
            [CÓDIGO DE EJEMPLO FUNCIONAL]
            ```
            
            *** CRÍTICO - PREGUNTAS DETALLADAS Y ESPECÍFICAS ***
            
            Las preguntas deben ser:
            - DETALLADAS y ESPECÍFICAS sobre el tema {topic_title}
            - Basadas en conceptos REALES del tema
            - Con código que DEMUESTRE el concepto específico
            - Que evalúen COMPRENSIÓN PROFUNDA, no solo memorización
            - Adaptadas al nivel {level}
            
            EJEMPLO DE PREGUNTA DETALLADA (BUENA):
            ```python
            def calcular_promedio(numeros):
                total = sum(numeros)
                cantidad = len(numeros)
                return total / cantidad
            
            notas = [85, 90, 78, 92, 88]
            resultado = calcular_promedio(notas)
            print(resultado)
            ```
            Pregunta: "En este código que calcula el promedio de notas, ¿qué valor se imprime y por qué la función divide total entre cantidad?"
            
            EJEMPLO DE PREGUNTA GENÉRICA (MALA - NO HACER):
            ```python
            x = 5
            print(x)
            ```
            Pregunta: "¿Qué imprime?" ← Demasiado simple y genérica
            
            *** CRÍTICO - NÚMERO DE PREGUNTAS ***
            
            Debes generar EXACTAMENTE 15 preguntas (no menos, no más).
            Si generas menos de 15 preguntas, la evaluación será rechazada y tendrás que volver a intentar.
            Cuenta las preguntas antes de enviar: DEBEN SER 15.
            
            *** CRÍTICO - OPCIONES DE RESPUESTA ***
            
            TODAS las opciones deben ser:
            - CLARAS y ESPECÍFICAS
            - CORRECTAS gramaticalmente
            - DIFERENCIABLES entre sí
            - UNA Y SOLO UNA debe ser la respuesta correcta
            - Las incorrectas deben ser plausibles pero claramente erróneas
            - La respuesta correcta puede estar en CUALQUIER posición (0, 1, 2, o 3)
            
            IMPORTANTE: NO pongas siempre la respuesta correcta en la primera posición.
            Varía el índice correcto entre 0, 1, 2 y 3 para diferentes preguntas.
            
            EJEMPLO DE OPCIONES CORRECTAS:
            Pregunta: "¿Qué imprime este código?"
            ```python
            x = 5
            print(type(x))
            ```
            Opciones CORRECTAS:
            - "<class 'str'>"
            - "<class 'float'>"
            - "<class 'int'>" (CORRECTA - índice 2)
            - "5"
            correct_index: 2
            
            *** EJEMPLOS DE FORMATO CORRECTO POR LENGUAJE ***
            
            PYTHON:
            ```python
            numeros = [10, 25, 30, 15, 40]
            resultado = [x for x in numeros if x > 20]
            print(len(resultado))
            ```
            ¿Cuántos elementos tiene la lista 'resultado' después de filtrar los números mayores a 20?
            
            JAVASCRIPT:
            ```javascript
            const persona = {{
                nombre: "Carlos",
                edad: 28,
                ciudad: "Madrid"
            }};
            console.log(persona.edad + 2);
            ```
            ¿Qué valor se imprime en consola al sumar 2 a la edad de la persona?
            
            SQL (IMPORTANTE - Incluir tabla con datos):
            ```sql
            -- Tabla clientes:
            -- | id | nombre      | ciudad    | edad |
            -- |----|-------------|-----------|------|
            -- | 1  | Juan Pérez  | Madrid    | 30   |
            -- | 2  | Ana García  | Sevilla   | 25   |
            -- | 3  | María López | Barcelona | 28   |
            
            SELECT COUNT(*) FROM clientes WHERE edad > 25;
            ```
            ¿Cuántos clientes tienen más de 25 años según esta consulta?
            
            JAVA:
            ```java
            int[] numeros = {{5, 10, 15, 20}};
            int suma = 0;
            for (int num : numeros) {{
                suma += num;
            }}
            System.out.println(suma);
            ```
            ¿Qué valor imprime este código después de sumar todos los elementos del array?
            
            C++:
            ```cpp
            #include <iostream>
            using namespace std;
            
            int main() {{
                int x = 10;
                int y = 20;
                cout << x + y << endl;
                return 0;
            }}
            ```
            ¿Cuál es la salida del programa al sumar x e y?
            
            REQUISITOS OBLIGATORIOS:
            - Todas las preguntas en ESPAÑOL
            - Evaluación específica para {language}
            - Nivel de dificultad {difficulty_desc}
            - EXACTAMENTE 15 preguntas (OBLIGATORIO - cuenta antes de enviar)
            - TODAS las preguntas DEBEN incluir código de 3-15 líneas
            - Preguntas DETALLADAS y ESPECÍFICAS sobre {topic_title}
            - Variedad de tipos de preguntas
            - Cada pregunta debe ser única y diferente
            - Para SQL: SIEMPRE incluir tabla con datos en comentarios
            - Las opciones deben ser claras, específicas y solo UNA correcta
            - VARIAR el índice de la respuesta correcta (no siempre 0)
            
            DISTRIBUCIÓN DE PREGUNTAS (15 total):
            - 3 preguntas sobre conceptos teóricos de {topic_title} CON CÓDIGO
            - 3 preguntas de análisis de código específico de {topic_title}
            - 3 preguntas de aplicación práctica de {topic_title} CON CÓDIGO
            - 3 preguntas de debugging/errores relacionados con {topic_title} CON CÓDIGO
            - 3 preguntas de mejores prácticas de {topic_title} CON CÓDIGO
            
            FORMATO JSON OBLIGATORIO (array con 15 objetos):
            [
                {{
                    "question": "```{language.lower()}\\n[CÓDIGO FUNCIONAL DETALLADO]\\n```\\n\\n¿Pregunta DETALLADA y ESPECÍFICA sobre {topic_title}?",
                    "options": ["Opción A clara y específica", "Opción B clara y específica", "Opción C clara y específica (CORRECTA)", "Opción D clara y específica"],
                    "correct_index": 2,
                    "explanation": "Explicación detallada en español de por qué la opción correcta es correcta y las demás son incorrectas, con referencia al concepto de {topic_title}",
                    "points": 20,
                    "difficulty": 1,
                    "topic_area": "concepto",
                    "code_example": ""
                }},
                {{
                    "question": "```{language.lower()}\\n[CÓDIGO FUNCIONAL DETALLADO]\\n```\\n\\n¿Pregunta DETALLADA y ESPECÍFICA sobre {topic_title}?",
                    "options": ["Opción A clara y específica (CORRECTA)", "Opción B clara y específica", "Opción C clara y específica", "Opción D clara y específica"],
                    "correct_index": 0,
                    "explanation": "Explicación detallada en español de por qué la opción correcta es correcta y las demás son incorrectas, con referencia al concepto de {topic_title}",
                    "points": 20,
                    "difficulty": 1,
                    "topic_area": "sintaxis",
                    "code_example": ""
                }},
                {{
                    "question": "```{language.lower()}\\n[CÓDIGO FUNCIONAL DETALLADO]\\n```\\n\\n¿Pregunta DETALLADA y ESPECÍFICA sobre {topic_title}?",
                    "options": ["Opción A clara y específica", "Opción B clara y específica", "Opción C clara y específica", "Opción D clara y específica (CORRECTA)"],
                    "correct_index": 3,
                    "explanation": "Explicación detallada en español de por qué la opción correcta es correcta y las demás son incorrectas, con referencia al concepto de {topic_title}",
                    "points": 20,
                    "difficulty": 2,
                    "topic_area": "aplicacion",
                    "code_example": ""
                }},
                ... (continuar hasta 15 preguntas, TODAS con código y correct_index variado)
            ]
            
            IMPORTANTE:
            - Preguntas DETALLADAS y ESPECÍFICAS del tema {topic_title}
            - TODAS las preguntas DEBEN tener código en bloque markdown
            - Código de 3-15 líneas funcional y relevante al tema
            - Opciones claras, específicas y solo UNA correcta
            - Explicaciones educativas que justifiquen la respuesta correcta
            - NO generes menos de 15 preguntas
            - Cada pregunta debe ser única
            - NO uses opciones redundantes o contradictorias
            - VARÍA el correct_index entre 0, 1, 2 y 3 (no siempre 0)
            
            Genera AHORA las 15 preguntas DETALLADAS CON CÓDIGO en formato JSON (cuenta que sean exactamente 15):
            """
            
            # Aumentar tokens para permitir 15 preguntas - MÁS ROBUSTO CON 3 REINTENTOS
            response = self.call_with_retry(prompt, max_retries=3, max_output_tokens=8000, temperature=0.8)
            
            # Verificar si hay error
            if not response or "Error" in response:
                return self._generate_fallback_topic_evaluation(language, topic_title, level)
            
            # Extraer JSON con múltiples estrategias
            result = self.extract_json_from_response(response, 'list')
            
            # Validar que tenga al menos 15 preguntas
            if isinstance(result, list) and len(result) >= 15:
                # Validar que cada pregunta tenga código
                valid_questions = []
                questions_without_code = 0
                questions_with_short_code = 0
                
                for idx, question in enumerate(result):
                    # Validar campos básicos
                    if 'points' not in question:
                        question['points'] = 20
                    if 'difficulty' not in question:
                        base_difficulty = {'facil': 1, 'normal': 2, 'dificil': 3}[difficulty_setting]
                        # Asegurar que difficulty esté siempre entre 1 y 5
                        question['difficulty'] = min(5, max(1, base_difficulty + (idx // 10)))
                    if 'topic_area' not in question:
                        areas = ['concepto', 'sintaxis', 'aplicacion', 'debugging', 'mejores_practicas']
                        question['topic_area'] = areas[idx % len(areas)]
                    if 'explanation' not in question:
                        question['explanation'] = 'Revisa los conceptos del tema'
                    if 'code_example' not in question:
                        question['code_example'] = ''
                    
                    # VALIDACIÓN MÁS FLEXIBLE: Aceptar preguntas con o sin código
                    # La IA a veces no genera el código en el formato exacto que esperamos
                    if 'question' in question:
                        has_code = self._validate_question_has_code(question['question'], language)
                        
                        if has_code:
                            # Extraer el código y ponerlo en code_example
                            code_block_pattern = r'```[\w]*\n(.*?)\n```'
                            match = re.search(code_block_pattern, question['question'], re.DOTALL)
                            if match and not question.get('code_example'):
                                question['code_example'] = match.group(1)
                        
                        # MEZCLAR OPCIONES ALEATORIAMENTE para evitar patrones predecibles
                        if 'options' in question and 'correct_index' in question:
                            import random
                            options = question['options']
                            correct_index = question['correct_index']
                            
                            # Guardar la respuesta correcta
                            if 0 <= correct_index < len(options):
                                correct_answer = options[correct_index]
                                
                                # Mezclar las opciones
                                random.shuffle(options)
                                
                                # Encontrar el nuevo índice de la respuesta correcta
                                question['correct_index'] = options.index(correct_answer)
                                question['options'] = options
                        
                        # ACEPTAR TODAS LAS PREGUNTAS (con o sin código perfecto)
                        valid_questions.append(question)
                
                # Verificar umbral mínimo - DEBE tener al menos 10 preguntas
                if len(valid_questions) < 10:
                    st.error(f"❌ No se generaron suficientes preguntas ({len(valid_questions)}/10 mínimo requerido)")
                    st.info("💡 Generando evaluación de respaldo...")
                    return self._generate_fallback_topic_evaluation(language, topic_title, level)
                
                st.success(f"✅ Se generaron {len(valid_questions)} preguntas válidas")
                return valid_questions
            elif isinstance(result, list) and len(result) >= 3:
                # Si tiene menos de 10, intentar validar las que hay
                valid_questions = []
                questions_without_code = 0
                
                for idx, question in enumerate(result):
                    # Validar campos básicos
                    if 'points' not in question:
                        question['points'] = 20
                    if 'difficulty' not in question:
                        base_difficulty = {'facil': 1, 'normal': 2, 'dificil': 3}[difficulty_setting]
                        # Asegurar que difficulty esté siempre entre 1 y 5
                        question['difficulty'] = min(5, max(1, base_difficulty + (idx // 10)))
                    if 'topic_area' not in question:
                        areas = ['concepto', 'sintaxis', 'aplicacion', 'debugging', 'mejores_practicas']
                        question['topic_area'] = areas[idx % len(areas)]
                    if 'explanation' not in question:
                        question['explanation'] = 'Revisa los conceptos del tema'
                    if 'code_example' not in question:
                        question['code_example'] = ''
                    
                    # Validar que tenga código
                    if 'question' in question:
                        has_code = self._validate_question_has_code(question['question'], language)
                        if has_code:
                            # Extraer el código y ponerlo en code_example para mejor visualización
                            code_block_pattern = r'```[\w]*\n(.*?)\n```'
                            match = re.search(code_block_pattern, question['question'], re.DOTALL)
                            if match and not question.get('code_example'):
                                question['code_example'] = match.group(1)
                            
                            valid_questions.append(question)
                        else:
                            questions_without_code += 1
                
                # Si no hay suficientes preguntas con código, usar fallback
                if len(valid_questions) < 3:
                    st.error(f"❌ Muy pocas preguntas con código ({len(valid_questions)})")
                    return self._generate_fallback_topic_evaluation(language, topic_title, level)
                
                st.warning(f"⚠️ Solo se generaron {len(valid_questions)} preguntas con código (menos de 10)")
                return valid_questions
            else:
                return self._generate_fallback_topic_evaluation(language, topic_title, level)
                
        except Exception as e:
            return self._generate_fallback_topic_evaluation(language, topic_title, level)
    
    def _generate_fallback_topic_evaluation(self, language, topic_title, level):
        """Genera evaluación básica con código garantizado cuando la IA no está disponible"""
        
        # Plantillas de código por lenguaje
        code_templates = {
            'Python': [
                ("x = 10\ny = 20\nresult = x + y\nprint(result)", "¿Qué imprime este código?", ["30", "1020", "Error", "None"], 0),
                ("numbers = [1, 2, 3, 4, 5]\nsum_numbers = sum(numbers)\nprint(sum_numbers)", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("text = 'Hola Mundo'\ntext_upper = text.upper()\nprint(text_upper)", "¿Qué se imprime?", ["HOLA MUNDO", "hola mundo", "Hola Mundo", "Error"], 0),
                ("for i in range(3):\n    print(i)", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("def suma(a, b):\n    return a + b\nresult = suma(5, 3)\nprint(result)", "¿Qué imprime?", ["8", "53", "Error", "None"], 0),
            ],
            'JavaScript': [
                ("const x = 10;\nconst y = 20;\nconst result = x + y;\nconsole.log(result);", "¿Qué se imprime en consola?", ["30", "1020", "undefined", "Error"], 0),
                ("const arr = [1, 2, 3, 4, 5];\nconst sum = arr.reduce((a, b) => a + b);\nconsole.log(sum);", "¿Cuál es la salida?", ["15", "12345", "5", "undefined"], 0),
                ("const text = 'Hola';\nconst upper = text.toUpperCase();\nconsole.log(upper);", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "undefined"], 0),
                ("for (let i = 0; i < 3; i++) {\n    console.log(i);\n}", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("function suma(a, b) {\n    return a + b;\n}\nconsole.log(suma(5, 3));", "¿Qué imprime?", ["8", "53", "undefined", "Error"], 0),
            ],
            'Java': [
                ("int x = 10;\nint y = 20;\nint result = x + y;\nSystem.out.println(result);", "¿Qué imprime este código?", ["30", "1020", "Error", "null"], 0),
                ("int[] numbers = {1, 2, 3, 4, 5};\nint sum = 0;\nfor (int n : numbers) sum += n;\nSystem.out.println(sum);", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("String text = \"Hola\";\nString upper = text.toUpperCase();\nSystem.out.println(upper);", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "null"], 0),
                ("for (int i = 0; i < 3; i++) {\n    System.out.println(i);\n}", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("public static int suma(int a, int b) {\n    return a + b;\n}\nSystem.out.println(suma(5, 3));", "¿Qué imprime?", ["8", "53", "Error", "null"], 0),
            ],
            'SQL': [
                ("-- Tabla usuarios:\n-- | id | nombre | edad |\n-- |----|--------|------|\n-- | 1  | Ana    | 25   |\n-- | 2  | Juan   | 30   |\n\nSELECT COUNT(*) FROM usuarios;", "¿Cuántas filas retorna?", ["2", "1", "0", "Error"], 0),
                ("-- Tabla productos:\n-- | id | nombre | precio |\n-- |----|--------|--------|\n-- | 1  | Laptop | 1000   |\n-- | 2  | Mouse  | 20     |\n\nSELECT nombre FROM productos WHERE precio > 50;", "¿Qué nombre retorna?", ["Laptop", "Mouse", "Ambos", "Ninguno"], 0),
                ("-- Tabla empleados:\n-- | id | nombre | salario |\n-- |----|--------|--------|\n-- | 1  | Pedro  | 3000   |\n-- | 2  | María  | 4000   |\n\nSELECT MAX(salario) FROM empleados;", "¿Cuál es el resultado?", ["4000", "3000", "7000", "Error"], 0),
                ("-- Tabla clientes:\n-- | id | ciudad  |\n-- |----|--------|\n-- | 1  | Madrid  |\n-- | 2  | Madrid  |\n-- | 3  | Sevilla |\n\nSELECT DISTINCT ciudad FROM clientes;", "¿Cuántas ciudades únicas?", ["2", "3", "1", "Error"], 0),
                ("-- Tabla ventas:\n-- | id | monto |\n-- |----|-------|\n-- | 1  | 100   |\n-- | 2  | 200   |\n\nSELECT SUM(monto) FROM ventas;", "¿Cuál es la suma?", ["300", "100", "200", "Error"], 0),
            ],
            'C++': [
                ("int x = 10;\nint y = 20;\nint result = x + y;\nstd::cout << result;", "¿Qué imprime?", ["30", "1020", "Error", "0"], 0),
                ("int arr[] = {1, 2, 3, 4, 5};\nint sum = 0;\nfor (int i = 0; i < 5; i++) sum += arr[i];\nstd::cout << sum;", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("std::string text = \"Hola\";\nstd::transform(text.begin(), text.end(), text.begin(), ::toupper);\nstd::cout << text;", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "Error"], 0),
                ("for (int i = 0; i < 3; i++) {\n    std::cout << i << \" \";\n}", "¿Qué números se imprimen?", ["0 1 2", "1 2 3", "0 1 2 3", "1 2"], 0),
                ("int suma(int a, int b) {\n    return a + b;\n}\nstd::cout << suma(5, 3);", "¿Qué imprime?", ["8", "53", "Error", "0"], 0),
            ],
            'PHP': [
                ("<?php\n$x = 10;\n$y = 20;\n$result = $x + $y;\necho $result;\n?>", "¿Qué imprime este código?", ["30", "1020", "Error", "null"], 0),
                ("<?php\n$numbers = [1, 2, 3, 4, 5];\n$sum = array_sum($numbers);\necho $sum;\n?>", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("<?php\n$text = 'Hola';\n$upper = strtoupper($text);\necho $upper;\n?>", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "null"], 0),
                ("<?php\nfor ($i = 0; $i < 3; $i++) {\n    echo $i . ' ';\n}\n?>", "¿Qué números se imprimen?", ["0 1 2", "1 2 3", "0 1 2 3", "1 2"], 0),
                ("<?php\nfunction suma($a, $b) {\n    return $a + $b;\n}\necho suma(5, 3);\n?>", "¿Qué imprime?", ["8", "53", "Error", "null"], 0),
            ],
            'Ruby': [
                ("x = 10\ny = 20\nresult = x + y\nputs result", "¿Qué imprime este código?", ["30", "1020", "Error", "nil"], 0),
                ("numbers = [1, 2, 3, 4, 5]\nsum = numbers.sum\nputs sum", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("text = 'Hola'\nupper = text.upcase\nputs upper", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "nil"], 0),
                ("(0..2).each do |i|\n  puts i\nend", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("def suma(a, b)\n  a + b\nend\nputs suma(5, 3)", "¿Qué imprime?", ["8", "53", "Error", "nil"], 0),
            ],
            'Go': [
                ("package main\nimport \"fmt\"\nfunc main() {\n    x := 10\n    y := 20\n    fmt.Println(x + y)\n}", "¿Qué imprime este código?", ["30", "1020", "Error", "0"], 0),
                ("package main\nimport \"fmt\"\nfunc main() {\n    nums := []int{1, 2, 3, 4, 5}\n    sum := 0\n    for _, n := range nums {\n        sum += n\n    }\n    fmt.Println(sum)\n}", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("package main\nimport (\n    \"fmt\"\n    \"strings\"\n)\nfunc main() {\n    text := \"Hola\"\n    fmt.Println(strings.ToUpper(text))\n}", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "Error"], 0),
                ("package main\nimport \"fmt\"\nfunc main() {\n    for i := 0; i < 3; i++ {\n        fmt.Println(i)\n    }\n}", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("package main\nimport \"fmt\"\nfunc suma(a, b int) int {\n    return a + b\n}\nfunc main() {\n    fmt.Println(suma(5, 3))\n}", "¿Qué imprime?", ["8", "53", "Error", "0"], 0),
            ],
            'C#': [
                ("int x = 10;\nint y = 20;\nint result = x + y;\nConsole.WriteLine(result);", "¿Qué imprime este código?", ["30", "1020", "Error", "0"], 0),
                ("int[] numbers = {1, 2, 3, 4, 5};\nint sum = numbers.Sum();\nConsole.WriteLine(sum);", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("string text = \"Hola\";\nstring upper = text.ToUpper();\nConsole.WriteLine(upper);", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "null"], 0),
                ("for (int i = 0; i < 3; i++) {\n    Console.WriteLine(i);\n}", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("int Suma(int a, int b) {\n    return a + b;\n}\nConsole.WriteLine(Suma(5, 3));", "¿Qué imprime?", ["8", "53", "Error", "0"], 0),
            ],
            'TypeScript': [
                ("const x: number = 10;\nconst y: number = 20;\nconst result: number = x + y;\nconsole.log(result);", "¿Qué se imprime en consola?", ["30", "1020", "undefined", "Error"], 0),
                ("const arr: number[] = [1, 2, 3, 4, 5];\nconst sum = arr.reduce((a, b) => a + b);\nconsole.log(sum);", "¿Cuál es la salida?", ["15", "12345", "5", "undefined"], 0),
                ("const text: string = 'Hola';\nconst upper: string = text.toUpperCase();\nconsole.log(upper);", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "undefined"], 0),
                ("for (let i: number = 0; i < 3; i++) {\n    console.log(i);\n}", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("function suma(a: number, b: number): number {\n    return a + b;\n}\nconsole.log(suma(5, 3));", "¿Qué imprime?", ["8", "53", "undefined", "Error"], 0),
            ],
            'Kotlin': [
                ("val x = 10\nval y = 20\nval result = x + y\nprintln(result)", "¿Qué imprime este código?", ["30", "1020", "Error", "null"], 0),
                ("val numbers = listOf(1, 2, 3, 4, 5)\nval sum = numbers.sum()\nprintln(sum)", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("val text = \"Hola\"\nval upper = text.uppercase()\nprintln(upper)", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "null"], 0),
                ("for (i in 0..2) {\n    println(i)\n}", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("fun suma(a: Int, b: Int): Int {\n    return a + b\n}\nprintln(suma(5, 3))", "¿Qué imprime?", ["8", "53", "Error", "null"], 0),
            ],
            'Swift': [
                ("let x = 10\nlet y = 20\nlet result = x + y\nprint(result)", "¿Qué imprime este código?", ["30", "1020", "Error", "nil"], 0),
                ("let numbers = [1, 2, 3, 4, 5]\nlet sum = numbers.reduce(0, +)\nprint(sum)", "¿Cuál es la salida?", ["15", "12345", "5", "Error"], 0),
                ("let text = \"Hola\"\nlet upper = text.uppercased()\nprint(upper)", "¿Qué se imprime?", ["HOLA", "hola", "Hola", "nil"], 0),
                ("for i in 0..<3 {\n    print(i)\n}", "¿Qué números se imprimen?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "1, 2"], 0),
                ("func suma(_ a: Int, _ b: Int) -> Int {\n    return a + b\n}\nprint(suma(5, 3))", "¿Qué imprime?", ["8", "53", "Error", "nil"], 0),
            ],
        }
        
        # Obtener plantillas para el lenguaje (o usar Python por defecto)
        templates = code_templates.get(language, code_templates['Python'])
        
        # Generar preguntas usando las plantillas
        questions = []
        for idx, (code, question_text, options, correct_idx) in enumerate(templates[:10]):
            # Normalizar el identificador de lenguaje para markdown
            lang_lower = language.lower()
            if lang_lower == 'c++':
                lang_lower = 'cpp'
            
            question = {
                "question": f"```{lang_lower}\n{code}\n```\n\n{question_text}",
                "options": options,
                "correct_index": correct_idx,
                "explanation": f"Revisa los conceptos de {topic_title} en {language}",
                "points": 20,
                "difficulty": 1 + (idx // 3),
                "topic_area": ["concepto", "sintaxis", "aplicacion", "debugging", "mejores_practicas"][idx % 5],
                "code_example": code  # Agregar el código también aquí para visualización separada
            }
            questions.append(question)
        
        return questions
    
    def generate_final_course_evaluation(self, language, level, completed_topics, difficulty_setting='normal'):
        """Genera evaluación final del curso basada en todos los temas completados"""
        if not self.model:
            return self._generate_fallback_final_evaluation(language, level, completed_topics)
        
        try:
            topics_list = [topic.get('title', f'Tema {i+1}') for i, topic in enumerate(completed_topics)]
            topics_str = ', '.join(topics_list)
            
            difficulty_map = {
                'facil': 'fácil con preguntas básicas',
                'normal': 'moderado con preguntas equilibradas',
                'dificil': 'desafiante con preguntas avanzadas'
            }
            difficulty_desc = difficulty_map.get(difficulty_setting, 'moderado')
            
            prompt = f"""
            Genera una evaluación final completa en ESPAÑOL para el curso de {language}:
            
            LENGUAJE: {language}
            NIVEL: {level}
            DIFICULTAD: {difficulty_desc}
            TEMAS COMPLETADOS: {topics_str}
            
            REQUISITOS OBLIGATORIOS:
            - Todas las preguntas en ESPAÑOL
            - Evaluación integral de todos los temas
            - Nivel de dificultad {difficulty_desc}
            - Mínimo 10 preguntas para evaluación completa
            - Cubrir todos los temas del curso
            
            DISTRIBUCIÓN DE PREGUNTAS:
            - Conceptos fundamentales (30%)
            - Aplicación práctica (40%)
            - Análisis y debugging (20%)
            - Integración de conocimientos (10%)
            
            FORMATO JSON OBLIGATORIO:
            [
                {{
                    "question": "Pregunta integral sobre el curso de {language} en español",
                    "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
                    "correct_index": 0,
                    "explanation": "Explicación detallada en español",
                    "points": 10,
                    "difficulty": 1,
                    "topic_covered": "tema_relacionado",
                    "question_type": "fundamental|aplicacion|debugging|integracion",
                    "code_example": "Código de ejemplo si aplica"
                }}
            ]
            
            IMPORTANTE:
            - Preguntas que integren múltiples temas
            - Evaluación completa del aprendizaje
            - Código real y funcional
            - Progresión de dificultad
            """
            
            response = self.call_with_retry(prompt)
            result = self.extract_json_from_response(response, 'list')
            
            if isinstance(result, list) and len(result) >= 8:
                # Validar y completar datos faltantes
                for i, question in enumerate(result):
                    if 'points' not in question:
                        question['points'] = 10
                    if 'difficulty' not in question:
                        base_difficulty = {'facil': 1, 'normal': 2, 'dificil': 3}[difficulty_setting]
                        question['difficulty'] = min(5, base_difficulty + (i // 4))
                    if 'topic_covered' not in question:
                        if i < len(completed_topics):
                            question['topic_covered'] = completed_topics[i].get('title', f'Tema {i+1}')
                        else:
                            question['topic_covered'] = completed_topics[i % len(completed_topics)].get('title', f'Tema {i+1}')
                    if 'question_type' not in question:
                        types = ['fundamental', 'aplicacion', 'debugging', 'integracion']
                        question['question_type'] = types[i % len(types)]
                    if 'explanation' not in question:
                        question['explanation'] = 'Revisa los conceptos del curso'
                    if 'code_example' not in question:
                        question['code_example'] = ''
                
                return result
            else:
                return self._generate_fallback_final_evaluation(language, level, completed_topics)
                
        except Exception as e:
            return self._generate_fallback_final_evaluation(language, level, completed_topics)
    
    def _generate_fallback_final_evaluation(self, language, level, completed_topics):
        """Genera evaluación final básica cuando la IA no está disponible"""
        questions = []
        
        for i, topic in enumerate(completed_topics[:5]):  # Máximo 5 preguntas
            question = {
                "question": f"?Cuál es el concepto más importante de {topic.get('title', f'Tema {i+1}')} en {language}?",
                "options": [
                    "Concepto fundamental del tema",
                    "Concepto secundario",
                    "Concepto no relacionado",
                    "Ninguna de las anteriores"
                ],
                "correct_index": 0,
                "explanation": f"El concepto fundamental de {topic.get('title', f'Tema {i+1}')} es esencial para dominar {language}",
                "points": 10,
                "difficulty": min(3, 1 + (i // 2)),
                "topic_covered": topic.get('title', f'Tema {i+1}'),
                "question_type": "fundamental",
                "code_example": ""
            }
            questions.append(question)
        
        # Agregar preguntas integradoras
        if len(completed_topics) > 1:
            integration_question = {
                "question": f"?Cómo se integran los conceptos aprendidos en el curso de {language}?",
                "options": [
                    "Los conceptos se complementan para formar una base sólida",
                    "Los conceptos son independientes",
                    "Solo algunos conceptos son importantes",
                    "No hay relación entre los conceptos"
                ],
                "correct_index": 0,
                "explanation": f"Los conceptos del curso de {language} se integran para formar una comprensión completa del lenguaje",
                "points": 15,
                "difficulty": 3,
                "topic_covered": "Integración",
                "question_type": "integracion",
                "code_example": ""
            }
            questions.append(integration_question)
        
        return questions
    
    def evaluate_topic_exercise(self, exercise_description, student_code, language, topic_context, exercise_title='', level='intermedio'):
        """Evalúa un ejercicio de tema - Evaluación simple y directa según requisitos del usuario"""

        if not self.model:
            return 5, "IA no disponible para evaluar. Revisa tu código manualmente.", "parcial", [], []

        # Prompt simplificado - solo evaluar: ejercicio, lenguaje, código
        prompt = f"""Eres un profesor de {language}. Evalúa este código de forma simple y directa.

    EJERCICIO:
    {exercise_description}

    CÓDIGO DEL ESTUDIANTE:
    ```{language.lower()}
    {student_code}
    ```

    INSTRUCCIONES:
    1. Analiza si el código resuelve el ejercicio
    2. Identifica errores específicos (con líneas o fragmentos)
    3. Asigna nota del 1 al 10 basándote en:
       - Cantidad de errores
       - Si resuelve el ejercicio

    CRITERIOS:
    - 10/10: Perfecto, sin errores → FELICITAR
    - 8-9/10: Resuelve correctamente con errores menores
    - 6-7/10: Resuelve parcialmente o con algunos errores
    - 4-5/10: Errores graves pero intenta resolver
    - 1-3/10: No resuelve o código sin sentido

    FORMATO DE RESPUESTA (JSON sin markdown):
    {{"score": NUMERO, "feedback": "TEXTO", "suggestions": ["sugerencia1", "sugerencia2"]}}

    ESTRUCTURA DEL FEEDBACK:
    Si score = 10:
    "🎉 ¡Felicitaciones! Tu código es perfecto. Resuelve el ejercicio sin errores. [Explicar qué hace bien]"

    Si score < 10:
    "**Errores encontrados:**
    • [Error 1 con línea específica]
    • [Error 2 con fragmento de código]

    **Cómo mejorar:**
    • [Sugerencia específica 1]
    • [Sugerencia específica 2]

    **Aspectos positivos:**
    • [Qué funciona bien]"

    Responde SOLO con el JSON, sin markdown ni texto extra."""

        try:
            import json
            import re

            # Llamar a la IA
            response = self.call_with_retry(prompt, max_retries=3, max_output_tokens=1500, temperature=0.3)

            if not response or "Error" in response:
                return 6, "IA temporalmente no disponible. Si tu código funciona, está bien.", "parcial", ["Verificar funcionamiento"], [language.lower()]

            # Limpiar respuesta
            response_clean = response.strip().replace('```json', '').replace('```', '').strip()

            # Extraer JSON
            result = None
            json_match = re.search(r'\{[^{}]*"score"[^{}]*"feedback"[^{}]*\}', response_clean, re.DOTALL)

            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                except:
                    result = self.extract_json_from_response(response, 'dict')
            else:
                result = self.extract_json_from_response(response, 'dict')

            if not result:
                return 6, "Tu código parece correcto. La IA no pudo evaluarlo completamente.", "parcial", ["Verificar funcionamiento"], [language.lower()]

            # Extraer datos
            score = int(result.get('score', 5))
            score = max(0, min(10, score))  # Asegurar rango 0-10

            feedback = result.get('feedback', 'Evaluación completada')
            suggestions = result.get('suggestions', ['Revisar el código'])

            if isinstance(suggestions, str):
                suggestions = [suggestions]

            status = "correcto" if score >= 8 else "parcial" if score >= 6 else "incorrecto"
            concepts = [language.lower(), topic_context.lower()]

            return score, feedback, status, suggestions, concepts

        except Exception as e:
            return 6, f"Error al evaluar. Si tu código funciona correctamente, está bien.", "parcial", ["Verificar sintaxis"], [language.lower()]

    
    def evaluate_topic_assessment(self, questions_data, responses_data, language, topic_title):
        """Evalúa una evaluación de tema"""
        if not questions_data or not responses_data:
            return 0, 0, 0, False, "Sin datos para evaluar"
        
        try:
            questions = json.loads(questions_data) if isinstance(questions_data, str) else questions_data
            responses = json.loads(responses_data) if isinstance(responses_data, str) else responses_data
        except:
            return 0, 0, 0, False, "Error en formato de datos"
        
        total_points = sum(q.get('points', 20) for q in questions)
        earned_points = 0
        correct_count = 0
        
        for i, response in enumerate(responses):
            if i < len(questions):
                question = questions[i]
                if response.get('selected_index') == question.get('correct_index'):
                    earned_points += question.get('points', 20)
                    correct_count += 1
        
        percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        passed = percentage >= 70
        
        feedback = f"Evaluación de {topic_title}: {correct_count}/{len(questions)} respuestas correctas. "
        if passed:
            feedback += "!Excelente trabajo! Has dominado este tema."
        else:
            feedback += "Necesitas repasar algunos conceptos de este tema."
        
        return earned_points, total_points, percentage, passed, feedback

# Funciones PDF
def extract_text_from_pdf(file_bytes):
    if not PDF_AVAILABLE: return "PyPDF no instalado"
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages: text += page.extract_text() + "\n"
        return text.strip()
    except: return "Error PDF"

def display_pdf(file_bytes):
    if not file_bytes: return
    try:
        b64 = base64.b64encode(file_bytes).decode('utf-8')
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" type="application/pdf"></iframe>', unsafe_allow_html=True)
    except: pass

# Instancia global
ai_manager = AIManager()

# Shims de compatibilidad
def configure_ai(api_key=None):
    global ai_manager
    ai_manager = AIManager(api_key)
    return ai_manager.model

def ai_evaluator(model, code, criteria, language="Python"):
    return ai_manager.evaluate_code(code, criteria, language)

def get_socratic_hint(model, code, error_msg, lang):
    return ai_manager.get_socratic_hint(code, error_msg, lang)

def ai_grade_open_question(model, question, student_answer, max_points):
    return ai_manager.grade_open_question(question, student_answer, max_points)

def ai_generate_exam_from_text(model, context_text, num_questions, num_options):
    return ai_manager.ai_generate_exam_from_text(context_text, num_questions, num_options)

# ========== FUNCIONES PARA ACADEMIA PERSONAL IA ==========

def generate_level_assessment(model, language, level="mixed"):
    """Genera un examen de evaluación de nivel para un lenguaje específico"""
    return ai_manager.generate_level_assessment(language, level)

def evaluate_level_from_responses(model, language, responses):
    """Evalúa el nivel del estudiante basado en sus respuestas"""
    return ai_manager.evaluate_level_from_responses(language, responses)

def generate_learning_resources(model, language, level, topics=None):
    """Genera recursos de aprendizaje personalizados"""
    return ai_manager.generate_learning_resources(language, level, topics)

def generate_progressive_exercises(model, language, level, count=5):
    """Genera ejercicios escalonados para un lenguaje y nivel"""
    return ai_manager.generate_progressive_exercises(language, level, count)

def evaluate_personal_exercise(model, exercise_description, student_code, language):
    """Evalúa un ejercicio personal del estudiante"""
    return ai_manager.evaluate_personal_exercise(exercise_description, student_code, language)

# ========== NUEVAS FUNCIONES PARA ESTRUCTURA POR TEMAS ==========

def generate_course_topics_structure(model, language, level, sections_count=5):
    """Genera la estructura de temas para un curso IA"""
    return ai_manager.generate_course_topics_structure(language, level, sections_count)

def generate_topic_materials_spanish(model, language, topic_title, topic_description, level):
    """Genera materiales en español para un tema específico"""
    return ai_manager.generate_topic_materials_spanish(language, topic_title, topic_description, level)

def generate_topic_exercises(model, language, topic_title, level, difficulty_setting='normal', topic_content=''):
    """Genera ejercicios para un tema específico"""
    return ai_manager.generate_topic_exercises(language, topic_title, level, difficulty_setting, topic_content)

def generate_topic_evaluation(model, language, topic_title, level, difficulty_setting='normal'):
    """Genera evaluación para un tema específico"""
    return ai_manager.generate_topic_evaluation(language, topic_title, level, difficulty_setting)

def generate_final_course_evaluation(model, language, level, completed_topics, difficulty_setting='normal'):
    """Genera evaluación final del curso basada en todos los temas completados"""
    return ai_manager.generate_final_course_evaluation(language, level, completed_topics, difficulty_setting)

def evaluate_topic_exercise(model, exercise_description, student_code, language, topic_context, exercise_title='', level='intermedio'):
    """Evalúa un ejercicio de tema específico"""
    return ai_manager.evaluate_topic_exercise(exercise_description, student_code, language, topic_context, exercise_title, level)

def evaluate_topic_assessment(model, questions_data, responses_data, language, topic_title):
    """Evalúa una evaluación de tema"""
    return ai_manager.evaluate_topic_assessment(questions_data, responses_data, language, topic_title)


def generate_lesson_content(model, language, topic_title, topic_description, level):
    """
    Genera contenido educativo detallado donde la IA enseña el tema.
    La IA actúa como profesor y explica el contenido paso a paso.
    """
    if not model:
        return f"""
        <h2>{topic_title}</h2>
        <p>{topic_description}</p>
        <p>En esta lección aprenderás sobre {topic_title} en {language}.</p>
        """
    
    try:
        # Instrucciones específicas por nivel
        level_guide = {
            "principiante": "Explicaciones MUY simples, código básico (5-10 líneas), analogías del mundo real, vocabulario simple",
            "intermedio": "Explicaciones técnicas, código moderado (15-30 líneas), mejores prácticas, casos de uso realistas",
            "avanzado": "Explicaciones expertas, código complejo (30-50+ líneas), optimización, patrones avanzados, arquitectura"
        }
        
        prompt = f"""
Genera una lección educativa COMPLETA en HTML sobre "{topic_title}" para {language} nivel {level}.

*** REGLAS CRÍTICAS ***

1. TODO en ESPAÑOL (títulos, explicaciones, comentarios)
2. SOLO HTML (sin <!DOCTYPE>, sin <html>, sin <head>, sin <body>)
3. SIN atributos style (el CSS ya está definido)
4. Contenido ESPECÍFICO de {language} (sintaxis, características, librerías)
5. Nivel {level}: {level_guide.get(level, level_guide['principiante'])}

*** ESTRUCTURA OBLIGATORIA ***

<h2>¿Qué es {topic_title}?</h2>
<p>[Explicación clara y concisa en 2-3 párrafos sobre qué es {topic_title} EN {language}]</p>
<p>[Por qué es importante EN {language}]</p>
<p>[Cuándo se usa EN {language}]</p>

<h2>Conceptos Fundamentales</h2>
<h3>Concepto 1: [Nombre del concepto]</h3>
<p>[Explicación detallada del concepto EN {language}]</p>
<pre><code>// Ejemplo de código EN {language}
[Código funcional y correcto]
</code></pre>
<p>[Explicación línea por línea del código]</p>

<h3>Concepto 2: [Nombre del concepto]</h3>
<p>[Explicación detallada del concepto EN {language}]</p>
<pre><code>// Ejemplo de código EN {language}
[Código funcional y correcto]
</code></pre>
<p>[Explicación línea por línea del código]</p>

<h3>Concepto 3: [Nombre del concepto]</h3>
<p>[Explicación detallada del concepto EN {language}]</p>
<pre><code>// Ejemplo de código EN {language}
[Código funcional y correcto]
</code></pre>
<p>[Explicación línea por línea del código]</p>

<h2>Ejemplos Prácticos</h2>
<h3>Ejemplo 1: [Caso de uso real]</h3>
<p>[Descripción del problema a resolver]</p>
<pre><code>// Solución completa EN {language}
[Código funcional de 10-30 líneas según nivel]
</code></pre>
<p>[Explicación de cómo funciona la solución]</p>

<h3>Ejemplo 2: [Caso de uso real]</h3>
<p>[Descripción del problema a resolver]</p>
<pre><code>// Solución completa EN {language}
[Código funcional de 10-30 líneas según nivel]
</code></pre>
<p>[Explicación de cómo funciona la solución]</p>

<h2>Errores Comunes</h2>
<h3>Error 1: [Nombre del error]</h3>
<p>[Descripción del error común EN {language}]</p>
<pre><code>// Código INCORRECTO
[Ejemplo de código con error]
</code></pre>
<pre><code>// Código CORRECTO
[Ejemplo de código corregido]
</code></pre>
<p>[Explicación de por qué el primero está mal y el segundo está bien]</p>

<h3>Error 2: [Nombre del error]</h3>
<p>[Descripción del error común EN {language}]</p>
<pre><code>// Código INCORRECTO
[Ejemplo de código con error]
</code></pre>
<pre><code>// Código CORRECTO
[Ejemplo de código corregido]
</code></pre>
<p>[Explicación de por qué el primero está mal y el segundo está bien]</p>

<h2>Mejores Prácticas</h2>
<ul>
<li><strong>Práctica 1:</strong> [Recomendación específica para {language}]</li>
<li><strong>Práctica 2:</strong> [Recomendación específica para {language}]</li>
<li><strong>Práctica 3:</strong> [Recomendación específica para {language}]</li>
<li><strong>Práctica 4:</strong> [Recomendación específica para {language}]</li>
</ul>

<h2>Resumen</h2>
<p>[Recapitulación de los puntos clave aprendidos]</p>
<p>[Qué practicar para dominar {topic_title} en {language}]</p>
<p>[Próximos temas relacionados en {language}]</p>

<blockquote>
<strong>Consejo Final:</strong> [Un consejo práctico y motivador para el estudiante]
</blockquote>

*** IMPORTANTE ***

- Usa la sintaxis CORRECTA de {language}
- Los ejemplos deben ser FUNCIONALES
- Adapta la complejidad al nivel {level}
- TODO en español excepto el código
- NO repitas código, cada ejemplo debe ser ÚNICO
- NO uses texto plano, SOLO HTML con las etiquetas indicadas

Genera AHORA el contenido HTML completo siguiendo EXACTAMENTE esta estructura:
"""
        
        # Llamar al modelo
        response = ai_manager.call_with_retry(prompt, max_retries=2, max_output_tokens=4000, temperature=0.7)
        
        if not response or not response.strip():
            return f"""
            <h2>{topic_title}</h2>
            <p>{topic_description}</p>
            <p>En esta lección aprenderás sobre {topic_title} en {language}.</p>
            """
        
        # Limpiar la respuesta
        content = response.strip()
        
        # Remover texto introductorio común de la IA
        intro_phrases = [
            "¡Absolutamente!",
            "Aquí tienes",
            "A continuación",
            "Por supuesto",
            "Claro que sí"
        ]
        for phrase in intro_phrases:
            if content.startswith(phrase):
                # Buscar el primer <h2> y empezar desde ahí
                h2_pos = content.find('<h2>')
                if h2_pos > 0:
                    content = content[h2_pos:]
                break
        
        # Si la IA generó un documento HTML completo, extraer solo el contenido
        if '<body>' in content.lower():
            import re
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = body_match.group(1).strip()
        
        # Desescapar HTML si es necesario
        import html as html_module
        if '&lt;' in content or '&gt;' in content:
            content = html_module.unescape(content)
        
        return content
        
    except Exception as e:
        print(f"[ERROR] generate_lesson_content failed: {e}")
        return f"""
        <h2>{topic_title}</h2>
        <p>{topic_description}</p>
        <p>En esta lección aprenderás sobre {topic_title} en {language}.</p>
        """
        
        # {'=' * 80}
        # LIMPIAR CARACTERES MAL CODIFICADOS
        # {'=' * 80}
        
        # Reemplazar comillas y apóstrofes mal codificados
        replacements = {
            ''': "'",  # Apóstrofe curvo izquierdo
            ''': "'",  # Apóstrofe curvo derecho
            '"': '"',  # Comilla doble curva izquierda
            '"': '"',  # Comilla doble curva derecha
            ''': "'",  # Acento grave
            ''': "'",  # Acento agudo
            '-': '-',  # Guión medio
            '-': '-',  # Guión largo
            '...': '...',  # Puntos suspensivos
            '«': '"',  # Comilla angular izquierda
            '»': '"',  # Comilla angular derecha
            '‹': "'",  # Comilla angular simple izquierda
            '›': "'",  # Comilla angular simple derecha
        }
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        # {'=' * 80}
        
        # {'=' * 80}
        # DETECCIÓN DE REPETICIONES INFINITAS
        # {'=' * 80}
        
        # Detectar si hay frases que se repiten más de 2 veces (más estricto)
        def detect_repetitions(text, min_phrase_length=20):
            """Detecta si hay frases largas que se repiten excesivamente (bug de IA)"""
            # Limpiar HTML para analizar solo el texto
            import re
            text_only = re.sub(r'<[^>]+>', ' ', text)
            text_only = re.sub(r'\s+', ' ', text_only).strip()
            
            words = text_only.split()
            if len(words) < min_phrase_length:
                return False, 0, 0
            
            # Buscar frases de 20-8 palabras que se repitan 2+ veces (MUY estricto)
            for phrase_len in [20, 15, 12, 10, 8]:
                if len(words) < phrase_len * 2:  # Necesitamos al menos 2 repeticiones
                    continue
                for i in range(len(words) - phrase_len):
                    phrase = ' '.join(words[i:i+phrase_len])
                    # Contar cuántas veces aparece esta frase
                    count = 0
                    search_pos = 0
                    while True:
                        pos = text_only.find(phrase, search_pos)
                        if pos == -1:
                            break
                        count += 1
                        search_pos = pos + 1
                    
                    if count >= 2:  # Detectar desde 2 repeticiones
                        # Encontrar la posición en el texto original (con HTML)
                        first_occurrence = text.find(phrase)
                        return True, count, first_occurrence
            return False, 0, 0
        
        # NUEVA: Detectar y corregir bloques de código con includes/imports repetidos
        def fix_repeated_includes_in_code(html_content):
            """Detecta y corrige bloques de código con includes/imports repetidos"""
            import re
            
            # Buscar todos los bloques de código
            code_blocks = re.findall(r'<pre><code>(.*?)</code></pre>', html_content, re.DOTALL)
            
            for code_block in code_blocks:
                # Contar líneas de include/import/require
                lines = code_block.split('\n')
                include_lines = []
                
                for line in lines:
                    line_stripped = line.strip()
                    # Detectar líneas de include/import/require
                    if any(keyword in line_stripped for keyword in ['#include', 'require', 'import ', 'from ', 'using ']):
                        include_lines.append(line_stripped)
                
                # Si hay más de 5 includes del mismo archivo, es un error
                if len(include_lines) > 5:
                    from collections import Counter
                    include_counts = Counter(include_lines)
                    max_repetitions = max(include_counts.values()) if include_counts else 0
                    
                    if max_repetitions >= 5:
                        # Este bloque tiene includes repetidos - reemplazarlo con un ejemplo correcto
                        corrected_code = f"""// [!] Ejemplo corregido automáticamente
// El código original tenía includes repetidos (error de generación)

// Ejemplo correcto de {language}:
// [Consulta la documentación oficial de {language} para ejemplos específicos]

// Nota: Este contenido fue generado automáticamente y contenía errores.
// Por favor, consulta recursos oficiales de {language} para ejemplos precisos."""
                        
                        # Reemplazar el bloque de código incorrecto
                        html_content = html_content.replace(
                            f'<pre><code>{code_block}</code></pre>',
                            f'<pre><code>{corrected_code}</code></pre>'
                        )
            
            return html_content
        
        # Aplicar corrección de includes repetidos
        content = fix_repeated_includes_in_code(content)
        
        has_repetition, rep_count, first_rep_pos = detect_repetitions(content)
        
        if has_repetition and first_rep_pos > 0:
            # Contenido tiene repeticiones REALES (bug de IA), truncar en el primer punto de repetición
            # Truncar justo antes de la primera repetición
            content = content[:first_rep_pos]
            
            # Asegurarse de que no cortamos en medio de una etiqueta HTML
            # Buscar la última etiqueta de cierre completa
            import re
            last_closing_tag = max(
                content.rfind('</p>'),
                content.rfind('</h2>'),
                content.rfind('</h3>'),
                content.rfind('</ul>'),
                content.rfind('</ol>'),
                content.rfind('</pre>'),
                content.rfind('</div>')
            )
            
            if last_closing_tag > 0:
                # Encontrar el final de esa etiqueta
                tag_end = content.find('>', last_closing_tag)
                if tag_end > 0:
                    content = content[:tag_end + 1]
            
            content += """
            
            <div style="background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; border-radius: 8px;">
                <p><strong>Nota:</strong> El contenido fue optimizado para evitar repeticiones. 
                Continúa con los ejercicios prácticos para profundizar en este tema.</p>
            </div>
            """
        
        # Limitar longitud máxima solo si es EXCESIVAMENTE largo (más de 5000 palabras)
        max_words = 5000
        words = content.split()
        if len(words) > max_words:
            content = ' '.join(words[:max_words])
            content += f"""
            
            <div style="background: #d1ecf1; padding: 15px; border-left: 4px solid #0c5460; margin: 20px 0;">
                <p><strong>[LIBROS] Contenido extenso:</strong> Este tema tiene mucho contenido. 
                Continúa explorando los ejercicios y recursos adicionales para profundizar más.</p>
            </div>
            """
        
        # {'=' * 80}
        
        # Si la IA generó un documento HTML completo, extraer solo el body
        if '<body>' in content.lower():
            import re
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match:
                content = body_match.group(1).strip()
        
        # Si el contenido tiene etiquetas HTML escapadas, desescaparlas
        import html as html_module
        if '&lt;' in content or '&gt;' in content:
            content = html_module.unescape(content)
        
        # {'=' * 80}
        # DETECTAR SI LA IA GENERÓ TEXTO PLANO EN LUGAR DE HTML
        # {'=' * 80}
        import re
        
        # Contar etiquetas HTML en el contenido
        html_tags = len(re.findall(r'<[^>]+>', content))
        total_lines = len(content.split('\n'))
        
        # Si hay muy pocas etiquetas HTML (menos de 10% de las líneas), probablemente es texto plano
        if html_tags < (total_lines * 0.1) or html_tags < 5:
            # Convertir texto plano a HTML
            lines = content.split('\n')
            html_lines = []
            in_code_block = False
            code_buffer = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Detectar bloques de código (líneas que empiezan con espacios o contienen código)
                if line.startswith('    ') or line.startswith('\t') or ('{' in line and '}' in line) or line.startswith('//') or line.startswith('#'):
                    if not in_code_block:
                        in_code_block = True
                        code_buffer = []
                    code_buffer.append(line)
                else:
                    # Si estábamos en un bloque de código, cerrarlo
                    if in_code_block:
                        html_lines.append('<pre><code>' + '\n'.join(code_buffer) + '</code></pre>')
                        in_code_block = False
                        code_buffer = []
                    
                    # Detectar títulos (líneas cortas en mayúsculas o que terminan con :)
                    if len(line) < 60 and (line.isupper() or line.endswith(':')):
                        html_lines.append(f'<h2>{line.rstrip(":")}</h2>')
                    # Detectar subtítulos (líneas que empiezan con números o letras seguidas de punto)
                    elif re.match(r'^\d+\.|^[A-Z]\)', line):
                        html_lines.append(f'<h3>{line}</h3>')
                    # Detectar listas (líneas que empiezan con -, *, o •)
                    elif line.startswith(('-', '*', '•', '·')):
                        html_lines.append(f'<li>{line[1:].strip()}</li>')
                    # Párrafos normales
                    else:
                        html_lines.append(f'<p>{line}</p>')
            
            # Cerrar bloque de código si quedó abierto
            if in_code_block:
                html_lines.append('<pre><code>' + '\n'.join(code_buffer) + '</code></pre>')
            
            # Envolver listas en <ul>
            final_html = []
            in_list = False
            for line in html_lines:
                if line.startswith('<li>'):
                    if not in_list:
                        final_html.append('<ul>')
                        in_list = True
                    final_html.append(line)
                else:
                    if in_list:
                        final_html.append('</ul>')
                        in_list = False
                    final_html.append(line)
            
            if in_list:
                final_html.append('</ul>')
            
            content = '\n'.join(final_html)
        
        # {'=' * 80}
        
        # NUEVO: Formatear HTML para que sea legible (agregar saltos de línea)
        import re
        # Agregar saltos de línea después de etiquetas de cierre
        content = re.sub(r'(</h[1-6]>)', r'\1\n\n', content)
        content = re.sub(r'(</p>)', r'\1\n', content)
        content = re.sub(r'(</li>)', r'\1\n', content)
        content = re.sub(r'(</ul>)', r'\1\n\n', content)
        content = re.sub(r'(</ol>)', r'\1\n\n', content)
        content = re.sub(r'(</pre>)', r'\1\n\n', content)
        content = re.sub(r'(</blockquote>)', r'\1\n\n', content)
        content = re.sub(r'(</div>)', r'\1\n', content)
        
        # Agregar saltos de línea antes de etiquetas de apertura importantes
        content = re.sub(r'(<h[1-6])', r'\n\n\1', content)
        content = re.sub(r'(<p>)', r'\n\1', content)
        content = re.sub(r'(<ul>)', r'\n\n\1', content)
        content = re.sub(r'(<ol>)', r'\n\n\1', content)
        content = re.sub(r'(<pre>)', r'\n\n\1', content)
        content = re.sub(r'(<blockquote>)', r'\n\n\1', content)
        
        # Limpiar múltiples saltos de línea consecutivos
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content.strip()
        
        return content
        
    except Exception as e:
        return f"""
        <h3>{topic_title}</h3>
        <p>{topic_description}</p>
        <p><em>Error al generar contenido: {str(e)}</em></p>
        """

def generate_suggested_questions(model, language, topic_title, level):
    """
    Genera 3-5 preguntas sugeridas para el chat de la sección.
    Preguntas relevantes al tema y nivel del estudiante.
    """
    if not model:
        return [
            f"?Qué es {topic_title}?",
            f"?Cómo se usa {topic_title} en {language}?",
            f"?Puedes darme un ejemplo de {topic_title}?",
            f"?Cuáles son los errores comunes con {topic_title}?",
            f"?Cuándo debería usar {topic_title}?"
        ]
    
    try:
        level_focus = {
            "principiante": "preguntas básicas y fundamentales",
            "intermedio": "preguntas sobre aplicación y mejores prácticas",
            "avanzado": "preguntas sobre optimización y casos avanzados"
        }
        
        prompt = f"""
        Genera exactamente 5 preguntas sugeridas en ESPAÑOL para un estudiante de nivel {level} 
        que está aprendiendo sobre "{topic_title}" en {language}.
        
        NIVEL: {level.upper()}
        ENFOQUE: {level_focus.get(level, level_focus['principiante'])}
        
        Las preguntas deben ser:
        - Relevantes al tema {topic_title}
        - Apropiadas para nivel {level}
        - Claras y específicas
        - Que ayuden al aprendizaje
        - En español natural
        
        FORMATO JSON:
        [
            "Pregunta 1?",
            "Pregunta 2?",
            "Pregunta 3?",
            "Pregunta 4?",
            "Pregunta 5?"
        ]
        
        EJEMPLOS DE PREGUNTAS POR NIVEL:
        
        Principiante:
        - "Que es {topic_title} y para que sirve?"
        - "Como empiezo a usar {topic_title}?"
        - "Puedes mostrarme un ejemplo simple?"
        
        Intermedio:
        - "Cuales son las mejores practicas para {topic_title}?"
        - "Como se compara {topic_title} con otras alternativas?"
        - "Que errores debo evitar?"
        
        Avanzado:
        - "Como optimizar el rendimiento de {topic_title}?"
        - "Que patrones de diseno se usan con {topic_title}?"
        - "Cuales son los trade-offs de usar {topic_title}?"
        """
        
        response = model.generate_content(prompt)
        
        # Intentar extraer JSON
        import json
        import re
        
        text = response.text
        # Limpiar markdown
        text = text.replace(''''json', '').replace(''''', '').strip()
        
        # Buscar array JSON
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            questions = json.loads(match.group(0))
            if isinstance(questions, list) and len(questions) >= 3:
                return questions[:5]
        
        # Fallback: extraer preguntas manualmente
        lines = text.split('\n')
        questions = []
        for line in lines:
            line = line.strip()
            if line.startswith('"') and line.endswith('"') or line.startswith('"') and line.endswith('",'):
                question = line.strip('",').strip()
                if '?' in question:
                    questions.append(question)
        
        if len(questions) >= 3:
            return questions[:5]
        
        # Fallback final
        return [
            f"?Qué es {topic_title} en {language}?",
            f"?Cómo funciona {topic_title}?",
            f"?Puedes darme un ejemplo práctico?",
            f"?Cuáles son los errores comunes?",
            f"?Cuándo debería usar {topic_title}?"
        ]
        
    except Exception as e:
        return [
            f"?Qué es {topic_title}?",
            f"?Cómo se usa {topic_title} en {language}?",
            f"?Puedes darme un ejemplo?",
            f"?Cuáles son las mejores prácticas?",
            f"?Qué debo evitar al usar {topic_title}?"
        ]


# ========== FUNCIONES PARA CHAT IA SEMANAL ==========

def get_contextualized_chat_response(model, question, context, history=None, max_output_tokens=2000):
    """
    Obtiene respuesta contextualizada de la IA para el chat del módulo
    
    Args:
        model: Modelo de Gemini (GenerativeModel)
        question: Pregunta del estudiante
        context: Contenido del módulo (contexto)
        history: Lista de dicts con 'message' y 'response' (últimos 5)
        max_output_tokens: Límite de tokens en la respuesta
    
    Returns:
        Respuesta formateada de la IA
    """
    # Construir prompt con contexto
    prompt = f"""Eres un asistente educativo experto. Responde la siguiente pregunta basándote ÚNICAMENTE en el contenido proporcionado.

CONTENIDO DEL MÓDULO:
{context[:100000]}

"""
    
    # Agregar historial si existe
    if history:
        prompt += "\nHISTORIAL DE CONVERSACIÓN RECIENTE:\n"
        for h in history[-5:]:  # Últimos 5 mensajes
            prompt += f"Estudiante: {h['message']}\n"
            prompt += f"Asistente: {h['response']}\n\n"
    
    prompt += f"""
PREGUNTA DEL ESTUDIANTE:
{question}

INSTRUCCIONES:
- Responde de forma clara y educativa
- Basa tu respuesta en el contenido del módulo
- Si la pregunta no se puede responder con el contenido, indícalo claramente
- Usa ejemplos del contenido cuando sea apropiado
- Mantén un tono amigable y pedagógico
- Formatea la respuesta con markdown para mejor legibilidad
"""
    
    try:
        # Usar el modelo directamente con timeout
        request_options = RequestOptions(timeout=30)
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.7,
                'max_output_tokens': max_output_tokens
            },
            request_options=request_options
        )
        
        if response and hasattr(response, 'text') and response.text:
            return response.text
        else:
            return "Lo siento, no pude generar una respuesta. Por favor intenta de nuevo."
    except Exception as e:
        print(f"Error en chat IA: {e}")
        return f"Error al procesar tu pregunta: {str(e)}"


def generate_module_questions(model, content, num_questions=4):
    """
    Genera preguntas sugeridas basadas en el contenido del módulo
    
    Args:
        model: Modelo de Gemini (GenerativeModel)
        content: Texto del contenido del módulo
        num_questions: Número de preguntas a generar (3-5)
    
    Returns:
        Lista de strings con las preguntas generadas
    """
    prompt = f"""Analiza el siguiente contenido educativo y genera {num_questions} preguntas que un estudiante podría hacer para comprender mejor el material.

CONTENIDO:
{content[:50000]}

INSTRUCCIONES:
- Genera exactamente {num_questions} preguntas
- Las preguntas deben ser claras y específicas
- Deben cubrir diferentes aspectos del contenido
- Deben ser apropiadas para estudiantes
- Formato: Una pregunta por línea, sin numeración

EJEMPLO DE FORMATO:
¿Cuál es el concepto principal explicado en este módulo?
¿Cómo se aplica este concepto en la práctica?
¿Qué diferencias existen entre X y Y?
"""
    
    try:
        # Usar el modelo directamente con timeout
        request_options = RequestOptions(timeout=15)
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.8,
                'max_output_tokens': 500
            },
            request_options=request_options
        )
        
        # Parsear respuesta
        if response and hasattr(response, 'text') and response.text:
            questions = [q.strip() for q in response.text.split('\n') if q.strip() and '?' in q]
            # Asegurar que tengamos el número correcto
            if len(questions) >= num_questions:
                return questions[:num_questions]
            elif len(questions) > 0:
                return questions
    except Exception as e:
        print(f"Error generando preguntas: {e}")
    
    # Fallback: preguntas genéricas
    return [
        "¿Cuál es el tema principal de este módulo?",
        "¿Puedes explicar los conceptos clave?",
        "¿Cómo se aplica esto en la práctica?",
        "¿Qué ejemplos hay en el contenido?"
    ][:num_questions]



# ========== FUNCIÓN PARA GENERAR EXAMEN FINAL CREATIVO ==========

def generate_creative_final_exam(model, language, level, num_questions=20):
    """
    Genera un examen final con preguntas del banco de preguntas pre-validadas.
    Selecciona aleatoriamente 20 preguntas del banco según el lenguaje y nivel.
    
    Args:
        model: Modelo de IA de Google Gemini (no usado, mantenido por compatibilidad)
        language: Lenguaje de programación (ej: "Python", "JavaScript")
        level: Nivel de dificultad ("principiante", "intermedio", "avanzado")
        num_questions: Número de preguntas a generar (default: 20)
    
    Returns:
        dict: Examen con preguntas del banco seleccionadas aleatoriamente
    """
    import random
    from utils_question_bank import QuestionBank
    
    print(f"🎓 Generando examen desde banco de preguntas: {num_questions} preguntas para {language} nivel {level}")
    
    try:
        # Cargar banco de preguntas
        question_bank = QuestionBank()
        question_bank.load()
        
        # Recopilar todas las preguntas del lenguaje y nivel especificados
        all_questions = []
        seen_questions = set()  # Para evitar duplicados
        
        if language in question_bank.data.get("languages", {}):
            lang_data = question_bank.data["languages"][language]
            sections = lang_data.get("sections", {})
            
            for section_num, section_data in sections.items():
                difficulties = section_data.get("difficulties", {})
                if level in difficulties:
                    diff_data = difficulties[level]
                    questions = diff_data.get("questions", [])
                    
                    # Ahora todas las preguntas son únicas (ya limpiamos el banco)
                    # Tomar todas las preguntas disponibles
                    for q in questions:
                        q_text = q.get("question_text", "")
                        if q_text and q_text not in seen_questions:
                            seen_questions.add(q_text)
                            all_questions.append(q)
            
            print(f"  ✅ Encontradas {len(all_questions)} preguntas únicas en el banco")
        else:
            print(f"  ⚠️ Lenguaje '{language}' no encontrado en el banco de preguntas")
            return {
                "questions": [],
                "metadata": {
                    "language": language,
                    "level": level,
                    "total_questions": 0,
                    "source": "question_bank",
                    "error": f"Lenguaje '{language}' no disponible en el banco de preguntas"
                }
            }
        
        # Verificar que hay suficientes preguntas
        if len(all_questions) == 0:
            print(f"  ❌ No hay preguntas disponibles para {language} nivel {level}")
            return {
                "questions": [],
                "metadata": {
                    "language": language,
                    "level": level,
                    "total_questions": 0,
                    "source": "question_bank",
                    "error": f"No hay preguntas disponibles para {language} nivel {level}"
                }
            }
        
        if len(all_questions) < num_questions:
            print(f"  ⚠️ Solo hay {len(all_questions)} preguntas disponibles, se solicitaron {num_questions}")
            print(f"  → Se generarán {len(all_questions)} preguntas en lugar de {num_questions}")
            num_questions = len(all_questions)
        
        # Seleccionar aleatoriamente las preguntas
        random.shuffle(all_questions)
        selected_questions = all_questions[:num_questions]
        
        # Formatear preguntas al formato esperado
        formatted_questions = []
        for q in selected_questions:
            formatted_questions.append({
                "question": q.get("question_text", ""),
                "options": q.get("options", []),
                "correct_answer": q.get("correct_answer_index", 0),
                "explanation": q.get("explanation", ""),
                "example_code": q.get("example_code", "")
            })
        
        print(f"✅ Examen generado exitosamente con {len(formatted_questions)} preguntas del banco")
        
        return {
            "questions": formatted_questions,
            "metadata": {
                "language": language,
                "level": level,
                "total_questions": len(formatted_questions),
                "source": "question_bank"
            }
        }
        
    except FileNotFoundError:
        print("❌ Error: Archivo de banco de preguntas no encontrado")
        return {
            "questions": [],
            "metadata": {
                "language": language,
                "level": level,
                "total_questions": 0,
                "source": "question_bank",
                "error": "Archivo de banco de preguntas no encontrado"
            }
        }
    except Exception as e:
        print(f"❌ Error al cargar banco de preguntas: {e}")
        import traceback
        traceback.print_exc()
        return {
            "questions": [],
            "metadata": {
                "language": language,
                "level": level,
                "total_questions": 0,
                "source": "question_bank",
                "error": f"Error al cargar banco de preguntas: {str(e)}"
            }
        }


# ============================================================================
# SEMANTIC VALIDATION DATA STRUCTURES
# ============================================================================

# Reglas de validación por concepto técnico (optimizadas)
CONCEPT_VALIDATION_RULES = {
    # Estructuras de datos básicas
    "dictionary": {
        "required_keywords": ["diccionario", "dictionary", "clave", "key", "valor", "value", "pares"],
        "forbidden_descriptions": [r"^un tipo de lista$", r"^un tipo de archivo$"]
    },
    "diccionario": {
        "required_keywords": ["diccionario", "dictionary", "clave", "key", "valor", "value", "pares"],
        "forbidden_descriptions": [r"^un tipo de lista$", r"^un tipo de archivo$"]
    },
    "dict": {
        "required_keywords": ["diccionario", "dictionary", "clave", "key", "valor", "value", "pares"],
        "forbidden_descriptions": [r"^un tipo de lista$", r"^un tipo de archivo$"]
    },
    "set": {
        "required_keywords": ["conjunto", "set", "único", "unique", "sin duplicados"],
        "forbidden_descriptions": [r"^un tipo de lista$", r"^un tipo de diccionario$", r"^un tipo de archivo$"]
    },
    "conjunto": {
        "required_keywords": ["conjunto", "set", "único", "unique", "sin duplicados"],
        "forbidden_descriptions": [r"^un tipo de lista$", r"^un tipo de diccionario$"]
    },
    "tuple": {
        "required_keywords": ["tupla", "tuple", "inmutable", "secuencia"],
        "forbidden_descriptions": [r"^un tipo de diccionario$", r"^un tipo de archivo$", r"^un tipo de conjunto$"]
    },
    "tupla": {
        "required_keywords": ["tupla", "tuple", "inmutable", "secuencia"],
        "forbidden_descriptions": [r"^un tipo de diccionario$", r"^un tipo de conjunto$"]
    },
    
    # Funciones y conceptos avanzados
    "lambda": {
        "required_keywords": ["anónima", "anonymous", "sin nombre"],
        "forbidden_descriptions": [r"definida con nombre", r"defined with name", r"^un tipo de variable$", r"^un tipo de clase$"]
    },
    "list comprehension": {
        "required_keywords": ["expresión", "expression", "sintaxis", "syntax", "forma"],
        "forbidden_descriptions": [r"^.*es una función$", r"^un tipo de variable$"]
    },
    "try-except": {
        "required_keywords": ["excepción", "exception", "error", "manejo", "handling"],
        "forbidden_descriptions": [r"^un tipo de variable$", r"^un tipo de función$"]
    },
    "decorator": {
        "required_keywords": ["modifica", "modifies", "función", "function", "comportamiento", "behavior"],
        "forbidden_descriptions": [r"^un tipo de variable$", r"^un tipo de archivo$", r"^un tipo de clase$"]
    },
    "decorador": {
        "required_keywords": ["modifica", "función", "comportamiento"],
        "forbidden_descriptions": [r"^un tipo de variable$", r"^un tipo de archivo$"]
    },
    "async": {
        "required_keywords": ["asíncrona", "asynchronous", "función", "function", "coroutine"],
        "forbidden_descriptions": [r"^un tipo de variable$", r"^un tipo de archivo$", r"^un tipo de clase$"]
    },
    "await": {
        "required_keywords": ["espera", "wait", "asíncrona", "asynchronous"],
        "forbidden_descriptions": [r"^un tipo de variable$", r"^un tipo de archivo$", r"^un tipo de clase$"]
    },
    "generator": {
        "required_keywords": ["generador", "generator", "yield", "función", "function"],
        "forbidden_descriptions": [r"^un tipo de variable$", r"^un tipo de archivo$", r"^un tipo de clase$"]
    },
    "generador": {
        "required_keywords": ["generador", "generator", "yield", "función"],
        "forbidden_descriptions": [r"^un tipo de variable$", r"^un tipo de archivo$"]
    },
}

# Conceptos permitidos y prohibidos por nivel de dificultad (solo validar prohibidos críticos)
DIFFICULTY_LEVEL_CONCEPTS = {
    "principiante": {
        "forbidden": ["metaclass", "decorador", "decorator", "threading", "asyncio"]
    },
    "beginner": {
        "forbidden": ["metaclass", "decorator", "threading", "asyncio"]
    },
    "intermedio": {
        "forbidden": ["metaclass"]
    },
    "intermediate": {
        "forbidden": ["metaclass"]
    },
    "avanzado": {
        "forbidden": []
    },
    "advanced": {
        "forbidden": []
    }
}

# Terminología correcta por lenguaje de programación
LANGUAGE_TERMINOLOGY = {
    "Python": {
        "dictionary": ["dictionary", "dict"],
        "list": ["list", "lista"],
        "tuple": ["tuple", "tupla"],
        "set": ["set", "conjunto"],
        "string": ["string", "str", "cadena"],
        "function": ["function", "función", "def"],
        "class": ["class", "clase"],
        "method": ["method", "método"]
    },
    "python": {
        "dictionary": ["dictionary", "dict"],
        "list": ["list", "lista"],
        "tuple": ["tuple", "tupla"],
        "set": ["set", "conjunto"],
        "string": ["string", "str", "cadena"],
        "function": ["function", "función", "def"],
        "class": ["class", "clase"],
        "method": ["method", "método"]
    },
    "JavaScript": {
        "dictionary": ["object", "Map"],  # NO "dictionary"
        "list": ["array"],
        "tuple": [],  # JavaScript no tiene tuplas nativas
        "set": ["Set"],
        "string": ["string"],
        "function": ["function"],
        "class": ["class"],
        "method": ["method"]
    },
    "javascript": {
        "dictionary": ["object", "Map"],
        "list": ["array"],
        "tuple": [],
        "set": ["Set"],
        "string": ["string"],
        "function": ["function"],
        "class": ["class"],
        "method": ["method"]
    },
    "Java": {
        "dictionary": ["HashMap", "Map"],
        "list": ["ArrayList", "List"],
        "tuple": [],  # Java no tiene tuplas nativas
        "set": ["HashSet", "Set"],
        "string": ["String"],
        "function": ["method"],  # Java usa métodos, no funciones
        "class": ["class"],
        "method": ["method"]
    },
    "java": {
        "dictionary": ["HashMap", "Map"],
        "list": ["ArrayList", "List"],
        "tuple": [],
        "set": ["HashSet", "Set"],
        "string": ["String"],
        "function": ["method"],
        "class": ["class"],
        "method": ["method"]
    },
    "C++": {
        "dictionary": ["map", "unordered_map"],
        "list": ["vector", "list"],
        "tuple": ["tuple", "pair"],
        "set": ["set", "unordered_set"],
        "string": ["string"],
        "function": ["function"],
        "class": ["class"],
        "method": ["method", "member function"]
    },
    "c++": {
        "dictionary": ["map", "unordered_map"],
        "list": ["vector", "list"],
        "tuple": ["tuple", "pair"],
        "set": ["set", "unordered_set"],
        "string": ["string"],
        "function": ["function"],
        "class": ["class"],
        "method": ["method", "member function"]
    }
}


# ============================================================================
# SEMANTIC VALIDATION FUNCTIONS
# ============================================================================

def _detect_embedded_code(question_text):
    """
    Detecta si el texto de la pregunta contiene código embebido usando markdown.
    
    Args:
        question_text: Texto de la pregunta
        
    Returns:
        bool: True si hay código embebido (triple backticks), False en caso contrario
    """
    import re
    # Buscar patrones de código markdown: ```lenguaje\ncodigo\n```
    pattern = r'```[\w]*\n.*?\n```'
    has_code = bool(re.search(pattern, question_text, re.DOTALL))
    
    if has_code:
        print(f"  ℹ️ Código embebido detectado en pregunta")
    
    return has_code


def _validate_concept_correctness(question_text, options, correct_answer_idx):
    """
    Valida que las opciones describan correctamente los conceptos técnicos.
    
    Args:
        question_text: Texto de la pregunta
        options: Lista de opciones de respuesta
        correct_answer_idx: Índice de la opción correcta
    
    Returns:
        tuple: (is_valid: bool, rejection_reason: str)
    """
    question_lower = question_text.lower()
    
    # Buscar conceptos conocidos en la pregunta
    detected_concepts = []
    for concept in CONCEPT_VALIDATION_RULES.keys():
        # Usar regex para buscar el concepto como palabra completa o patrón
        if re.search(concept, question_lower):
            detected_concepts.append(concept)
    
    if not detected_concepts:
        # No se detectó ningún concepto conocido, aceptar la pregunta
        return (True, "")
    
    # Validar cada concepto detectado
    for concept in detected_concepts:
        rules = CONCEPT_VALIDATION_RULES[concept]
        correct_option = options[correct_answer_idx].lower()
        
        # Validar que la opción correcta NO contenga descripciones prohibidas
        for forbidden_pattern in rules["forbidden_descriptions"]:
            if re.search(forbidden_pattern, correct_option):
                reason = f"Concepto '{concept}': opción correcta contiene descripción prohibida (patrón: {forbidden_pattern})"
                print(f"  ❌ Validación semántica: {reason}")
                print(f"     Opción correcta: '{options[correct_answer_idx][:60]}...'")
                return (False, reason)
        
        # Validar que la opción correcta incluya keywords requeridos
        has_required = False
        
        for keyword in rules["required_keywords"]:
            if re.search(keyword, correct_option):
                has_required = True
                break
        
        if not has_required:
            reason = f"Concepto '{concept}': opción correcta no incluye keywords requeridos ({', '.join(rules['required_keywords'])})"
            print(f"  ❌ Validación semántica: {reason}")
            print(f"     Opción correcta: '{options[correct_answer_idx][:60]}...'")
            return (False, reason)
    
    return (True, "")


def _validate_code_question_match(question_text, example_code):
    """
    Valida que el código de ejemplo coincida con lo que pregunta.
    
    Args:
        question_text: Texto de la pregunta
        example_code: Código de ejemplo
    
    Returns:
        tuple: (is_valid: bool, rejection_reason: str)
    """
    if not example_code or example_code.strip() == "":
        # No hay código, no hay nada que validar
        return (True, "")
    
    question_lower = question_text.lower()
    code_lower = example_code.lower()
    
    # Detectar condiciones específicas en la pregunta y verificar en el código
    conditions = [
        {
            "keywords": ["números pares", "even numbers", "pares"],
            "code_patterns": [r"% 2 == 0", r"% 2 === 0", r"mod 2 == 0"],
            "description": "filtrado de números pares"
        },
        {
            "keywords": ["números impares", "odd numbers", "impares"],
            "code_patterns": [r"% 2 != 0", r"% 2 !== 0", r"% 2 == 1", r"mod 2 != 0", r"mod 2 == 1"],
            "description": "filtrado de números impares"
        },
        {
            "keywords": ["mayores que", "greater than", "mayor a"],
            "code_patterns": [r">"],
            "description": "comparación mayor que"
        },
        {
            "keywords": ["menores que", "less than", "menor a"],
            "code_patterns": [r"<"],
            "description": "comparación menor que"
        }
    ]
    
    for condition in conditions:
        # Verificar si la pregunta menciona esta condición
        mentions_condition = any(keyword in question_lower for keyword in condition["keywords"])
        
        if mentions_condition:
            # Verificar si el código implementa la condición
            implements_condition = any(re.search(pattern, code_lower) for pattern in condition["code_patterns"])
            
            if not implements_condition:
                reason = f"Pregunta menciona '{condition['description']}' pero el código no lo implementa"
                print(f"  ❌ Validación código-pregunta: {reason}")
                print(f"     Pregunta: '{question_text[:60]}...'")
                print(f"     Código: '{example_code[:60]}...'")
                return (False, reason)
    
    return (True, "")


def _validate_difficulty_level(question_text, level):
    """
    Valida que la complejidad de la pregunta corresponda al nivel.
    Solo valida conceptos prohibidos críticos.
    
    Args:
        question_text: Texto de la pregunta
        level: Nivel de dificultad (principiante, intermedio, avanzado)
    
    Returns:
        tuple: (is_valid: bool, rejection_reason: str)
    """
    level_lower = level.lower()
    question_lower = question_text.lower()
    
    # Buscar el nivel en las reglas
    if level_lower not in DIFFICULTY_LEVEL_CONCEPTS:
        # Nivel desconocido, aceptar la pregunta
        return (True, "")
    
    level_rules = DIFFICULTY_LEVEL_CONCEPTS[level_lower]
    
    # Verificar solo conceptos prohibidos críticos
    for forbidden_concept in level_rules["forbidden"]:
        if forbidden_concept.lower() in question_lower:
            reason = f"Nivel '{level}': pregunta contiene concepto prohibido '{forbidden_concept}'"
            print(f"  ❌ Validación de nivel: {reason}")
            print(f"     Pregunta: '{question_text[:60]}...'")
            return (False, reason)
    
    return (True, "")


def _validate_language_specific(question_text, options, language):
    """
    Valida que la terminología sea correcta para el lenguaje.
    
    Args:
        question_text: Texto de la pregunta
        options: Lista de opciones de respuesta
        language: Lenguaje de programación
    
    Returns:
        tuple: (is_valid: bool, rejection_reason: str)
    """
    if language not in LANGUAGE_TERMINOLOGY:
        # Lenguaje desconocido, aceptar la pregunta
        return (True, "")
    
    language_terms = LANGUAGE_TERMINOLOGY[language]
    question_lower = question_text.lower()
    
    # Verificar terminología incorrecta para el lenguaje
    # Por ejemplo, "dictionary" en JavaScript (debería ser "object" o "Map")
    
    # Caso especial: JavaScript no usa "dictionary"
    if language.lower() in ["javascript", "js"]:
        if "dictionary" in question_lower or "diccionario" in question_lower:
            # Verificar si menciona correctamente "object" o "Map"
            if "object" not in question_lower and "map" not in question_lower.replace("map()", ""):
                reason = f"Lenguaje '{language}': usa 'dictionary' en lugar de 'object' o 'Map'"
                print(f"  ❌ Validación de lenguaje: {reason}")
                print(f"     Pregunta: '{question_text[:60]}...'")
                return (False, reason)
    
    # Caso especial: JavaScript/Java no tienen tuplas nativas
    if language.lower() in ["javascript", "js", "java"]:
        if "tuple" in question_lower or "tupla" in question_lower:
            reason = f"Lenguaje '{language}': menciona 'tuple' pero el lenguaje no tiene tuplas nativas"
            print(f"  ❌ Validación de lenguaje: {reason}")
            print(f"     Pregunta: '{question_text[:60]}...'")
            return (False, reason)
    
    # Caso especial: Python no usa "array" (usa "list")
    if language.lower() == "python":
        if re.search(r'\barray\b', question_lower) and "numpy" not in question_lower:
            # Verificar si menciona correctamente "list"
            if "list" not in question_lower:
                reason = f"Lenguaje '{language}': usa 'array' en lugar de 'list'"
                print(f"  ❌ Validación de lenguaje: {reason}")
                print(f"     Pregunta: '{question_text[:60]}...'")
                return (False, reason)
    
    return (True, "")


def _generate_question_batch(model, language, level, num_questions, batch_number, section_title=None):
    """
    Genera un lote de preguntas para el examen.
    
    Args:
        model: Modelo de IA
        language: Lenguaje de programación
        level: Nivel de dificultad
        num_questions: Número de preguntas en este lote
        batch_number: Número del lote (para variedad)
        section_title: Título de la sección (opcional, para evaluaciones de sección)
    
    Returns:
        list: Lista de preguntas generadas
    """
    
    if section_title:
        intro = f"""Genera {num_questions} preguntas de opción múltiple para evaluar conocimientos de {language} a nivel {level}.
Las preguntas deben enfocarse específicamente en el tema: "{section_title}"."""
    else:
        intro = f"""Genera {num_questions} preguntas de opción múltiple para evaluar conocimientos de {language} a nivel {level}.
Este es el lote #{batch_number}, así que asegúrate de que las preguntas sean DIFERENTES a las de lotes anteriores."""
    
    prompt = f"""Eres un experto en crear evaluaciones de programación creativas y desafiantes.

{intro}

REQUISITOS CRÍTICOS:
1. Las preguntas deben ser CREATIVAS, DETALLADAS y DESAFIANTES - NO repetir patrones
2. CADA PREGUNTA DEBE SER COMPLETAMENTE ÚNICA - no repitas preguntas de lotes anteriores
3. Las preguntas deben ser ESPECÍFICAS al lenguaje {language} y nivel {level}
4. Incluir diferentes tipos de preguntas DETALLADAS:
   - Análisis de código COMPLEJO (¿qué imprime este código de 5-10 líneas?)
   - Conceptos teóricos AVANZADOS (no solo definiciones básicas)
   - Debugging de código REAL (encontrar errores sutiles)
   - Mejores prácticas y patrones de diseño
   - Casos de uso reales y aplicaciones prácticas
   - Optimización y complejidad algorítmica
   - Comparación profunda de enfoques y técnicas

3. Cada pregunta debe tener:
   - Texto claro y específico
   - 4 opciones de respuesta CLARAS Y LEGIBLES (sin código complejo en las opciones)
   - Una respuesta correcta PRECISA Y TÉCNICAMENTE CORRECTA
   - Explicación detallada
   - Código de ejemplo cuando sea relevante (ver reglas abajo)

3.1. IMPORTANTE sobre código de ejemplo:
   - Si incluyes código en el texto de la pregunta usando markdown (```python ... ```), NO incluyas el campo "example_code" (déjalo vacío "").
   - Si NO incluyes código en el texto de la pregunta, entonces usa el campo "example_code" para proporcionar el código.
   - NUNCA incluyas código en ambos lugares (texto de pregunta Y example_code), esto causa duplicación y confusión.
   - El código debe estar en UN SOLO LUGAR: O en el texto de la pregunta O en el campo example_code.

4. FORMATO DE OPCIONES - MUY IMPORTANTE:
   - NUNCA uses solo números como "1", "2", "3", "4" - esto es INCORRECTO
   - ⚠️ CRÍTICO: NUNCA repitas la misma opción o variaciones mínimas - TODAS las opciones deben ser COMPLETAMENTE DIFERENTES
   - ⚠️ CRÍTICO: Verifica que las 4 opciones sean ÚNICAS - no debe haber texto duplicado o casi idéntico
   - Para preguntas de "¿qué imprime?": usa el VALOR REAL que imprime, como "5", "10", "Error", "None", "[1, 2, 3]"
   - Para preguntas conceptuales: usa TEXTO DESCRIPTIVO completo, como "Permite crear objetos reutilizables", "Mejora el rendimiento del código"
   - Para preguntas de sintaxis: usa FRAGMENTOS DE CÓDIGO cortos y legibles, como "def funcion():", "lambda x: x + 1"
   - Para preguntas de comparación: usa NOMBRES O DESCRIPCIONES, como "Lista", "Tupla", "Diccionario", "Conjunto"
   - Las opciones deben ser AUTOEXPLICATIVAS y SIGNIFICATIVAS
   - NUNCA pongas código largo o complejo en las opciones
   - CRÍTICO: Las 4 opciones deben ser COMPLETAMENTE DIFERENTES entre sí - ni una sola palabra debe repetirse innecesariamente
   
   EJEMPLOS DE OPCIONES CORRECTAS (todas diferentes y adaptables a cualquier lenguaje):
   ✅ Para salida de código: ["[1, 2, 3, 4, 5]", "[1, 3, 5]", "[2, 4]", "Error"]
   ✅ Para conceptos: ["Permite reutilizar código", "Mejora la legibilidad", "Reduce errores", "Todas las anteriores"]
   ✅ Para complejidad: ["O(n)", "O(log n)", "O(n²)", "O(1)"]
   ✅ Para valores booleanos: ["true", "false", "null/None", "Error"]
   ✅ Para paradigmas: ["Funciones puras y evitar estado mutable", "Uso de clases y herencia", "Programación imperativa con bucles", "Uso de variables globales"]
   ✅ Para propósitos: ["Para iterar sobre dos colecciones simultáneamente", "Para invertir una colección", "Para ordenar elementos", "Para filtrar elementos"]
   ✅ Para manejo de errores: ["Un mecanismo para manejar excepciones (errores)", "Un método para almacenar datos", "Una función que modifica código", "Un tipo de dato"]
   ✅ Para funciones de orden superior: ["Aplica una función a cada elemento de una colección", "Modifica el comportamiento de otra función", "Un algoritmo de búsqueda", "Un tipo de dato"]
   ✅ Para conceptos avanzados: ["Una función que produce valores de forma perezosa", "Un tipo de dato que almacena valores", "Una función normal que retorna todos los valores", "Un algoritmo de búsqueda"]
   
   EJEMPLOS DE OPCIONES INCORRECTAS (NO HACER):
   ❌ ["1", "2", "3", "4"]  ← NUNCA HAGAS ESTO
   ❌ ["A", "B", "C", "D"]  ← NUNCA HAGAS ESTO
   ❌ ["Opción 1", "Opción 2", "Opción 3", "Opción 4"]  ← NUNCA HAGAS ESTO
   ❌ ["Para crear un nuevo diccionario con los valores de una lista.", "Para crear un nuevo diccionario con los valores de una lista.", "Para modificar la lista original.", "Para filtrar elementos."]  ← OPCIONES DUPLICADAS - NUNCA HAGAS ESTO
   ❌ ["Para iterar sobre las listas en orden inverso.", "Para iterar sobre las listas en orden inverso.", "Para iterar sobre las listas en orden inverso.", "Para iterar sobre las listas en orden inverso."]  ← TODAS IGUALES - NUNCA HAGAS ESTO
   ❌ ["Un enfoque orientado a objetos", "Un enfoque imperativo", "Un enfoque procedural", "Un enfoque dinámico"]  ← Ninguna describe correctamente el concepto
   
   - IMPORTANTE: La respuesta correcta puede estar en CUALQUIER posición (0, 1, 2, o 3)
   - NO pongas siempre la respuesta correcta en la primera posición
   - Varía la posición de la respuesta correcta entre las preguntas
   - CRÍTICO: La opción correcta debe ser TÉCNICAMENTE PRECISA y COMPLETA
   
   ⚠️ ANTES DE FINALIZAR CADA PREGUNTA: Lee las 4 opciones y verifica que sean TODAS DIFERENTES. Si encuentras duplicados, REESCRIBE las opciones duplicadas.

5. CALIDAD DE RESPUESTAS - CRÍTICO:
   - ⚠️ EXTREMADAMENTE IMPORTANTE: La opción marcada como correcta DEBE ser TÉCNICAMENTE PRECISA Y COMPLETA
   - ⚠️ VERIFICA CUIDADOSAMENTE que el índice de correct_answer apunte a la opción REALMENTE CORRECTA
   - NO uses opciones vagas o imprecisas como "correcta"
   - Para conceptos técnicos (ej: programación funcional, POO, etc.), la respuesta debe incluir las características CLAVE del concepto
   - Ejemplo CORRECTO para programación funcional: "Funciones como ciudadanos de primera clase, evita estado mutable, usa funciones puras"
   - Ejemplo INCORRECTO: "Un enfoque orientado a objetos" (esto es POO, no funcional)
   - ⚠️ ANTES DE FINALIZAR: Lee la opción marcada como correcta y verifica que sea TÉCNICAMENTE CORRECTA
   
   EJEMPLOS DE ERRORES COMUNES A EVITAR:
   ❌ Marcar como correcta: "Las listas son más rápidas de crear que las tuplas" cuando la pregunta es sobre diferencias principales
   ✅ Correcto: "Las listas son mutables, mientras que las tuplas son inmutables"
   
   ❌ Marcar como correcta: "Un tipo de variable que solo puede almacenar números" para diccionarios
   ✅ Correcto: "Una estructura de datos que almacena información en pares clave-valor"
   
   ❌ Marcar como correcta: "Para iterar sobre la lista" cuando la pregunta es sobre map()
   ✅ Correcto: "Para aplicar una función a cada elemento y crear una nueva lista con los resultados"
   
6. Nivel de dificultad {level} - INSTRUCCIONES ESPECÍFICAS:
   
   PRINCIPIANTE:
   - Preguntas sobre sintaxis básica CON ejemplos de código de 3-5 líneas
   - Tipos de datos y operaciones básicas con casos prácticos
   - Estructuras de control (if, for, while) con código real
   - Funciones simples con parámetros y retorno
   - Listas, tuplas, diccionarios básicos con ejemplos de uso
   - Ejemplo: "¿Qué imprime este código? x = [1,2,3]; x.append(4); print(x[-1])"
   
   INTERMEDIO:
   - Análisis de código con funciones de 5-8 líneas
   - POO: clases, herencia, métodos, atributos con ejemplos
   - List comprehensions, lambda, map, filter con código
   - Manejo de excepciones con try/except en contexto
   - Algoritmos de búsqueda y ordenamiento básicos
   - Complejidad temporal O(n), O(n²), O(log n)
   - Ejemplo: "Analiza esta clase con herencia: ¿qué método se ejecuta? [código 6-8 líneas]"
   
   AVANZADO:
   - Código complejo de 8-12 líneas con múltiples conceptos
   - Decoradores, generadores, context managers
   - Metaprogramación, reflexión, introspección
   - Patrones de diseño (Singleton, Factory, Observer)
   - Algoritmos avanzados con análisis de complejidad
   - Concurrencia, threading, async/await
   - Optimización de memoria y rendimiento
   - Ejemplo: "Analiza este decorador con closure: ¿qué valor retorna después de 3 llamadas? [código 10 líneas]"

7. IMPORTANTE: Las preguntas deben ser ESPECÍFICAS y DETALLADAS, no genéricas
   - ❌ MAL: "¿Qué es la herencia?"
   - ✅ BIEN: "Dado el siguiente código con herencia múltiple, ¿qué método se ejecutará y por qué? [código de 5-8 líneas]"
   
   - ❌ MAL: "¿Qué es un diccionario?"
   - ✅ BIEN: "¿Cuál es la complejidad temporal promedio de buscar una clave en un diccionario de Python y por qué es más eficiente que buscar en una lista?"
   
   - ❌ MAL: "¿Qué hace map()?"
   - ✅ BIEN: "Analiza este código: result = list(map(lambda x: x**2 if x % 2 == 0 else x, [1,2,3,4,5])). ¿Qué valor tendrá result?"

8. IMPORTANTE: Cada pregunta debe ser ÚNICA y DIFERENTE de las demás

7. EJEMPLOS DE PREGUNTAS BIEN FORMULADAS Y DETALLADAS (adaptables a {language}):

   Pregunta DETALLADA sobre Análisis de Código (CORRECTO):
   {{
       "question": "Analiza el siguiente código y determina qué se imprimirá:\\n```{language.lower()}\\n[código de 5-8 líneas específico del lenguaje]\\n```",
       "options": [
           "[valor esperado 1]",
           "[valor esperado 2]",
           "[valor esperado 3]",
           "Error de compilación/ejecución"
       ],
       "correct_answer": 0,
       "explanation": "Explicación detallada de por qué se produce ese resultado, mencionando conceptos clave del lenguaje.",
       "example_code": ""
   }}
   
   Pregunta DETALLADA sobre Conceptos Avanzados (CORRECTO):
   {{
       "question": "En {language}, ¿cuál es la diferencia entre [concepto A] y [concepto B], y cómo afecta esto al comportamiento del programa?",
       "options": [
           "Descripción técnica precisa de la diferencia principal",
           "Descripción incorrecta que confunde los conceptos",
           "Descripción parcialmente correcta pero incompleta",
           "Descripción que menciona características irrelevantes"
       ],
       "correct_answer": 0,
       "explanation": "Explicación detallada con ejemplos de cuándo usar cada uno.",
       "example_code": ""
   }}
   
   Pregunta DETALLADA sobre Complejidad (CORRECTO):
   {{
       "question": "¿Cuál es la complejidad temporal del siguiente código y por qué?\\n```{language.lower()}\\n[código con bucles anidados]\\n```",
       "options": [
           "O(n²) porque hay dos bucles anidados que iteran sobre n elementos",
           "O(n) porque el bucle interno solo itera desde i hasta n",
           "O(n log n) porque el bucle interno reduce el rango",
           "O(2n) porque ambos bucles dependen de n"
       ],
       "correct_answer": 0,
       "explanation": "Explicación del análisis de complejidad con justificación matemática.",
       "example_code": ""
   }}

   Pregunta SIMPLE - NO HACER (INCORRECTO):
   {{
       "question": "¿Qué es la programación funcional?",
       "options": ["...", "...", "...", "..."],
       "correct_answer": 0,
       "explanation": "..."
   }}

EJEMPLOS DE BUENAS OPCIONES:
✅ ["5", "10", "15", "Error"]
✅ ["True", "False", "None", "TypeError"]
✅ ["Lista", "Tupla", "Diccionario", "Conjunto"]
✅ ["O(n)", "O(log n)", "O(n²)", "O(1)"]

EJEMPLOS DE MALAS OPCIONES (NO HACER):
❌ ["file = open('archivo.txt', 'r')", "with open('archivo.txt') as file:", ...]
❌ ["def funcion(x, y): return x + y", "lambda x, y: x + y", ...]

FORMATO DE SALIDA (JSON ESTRICTO):
{{
    "questions": [
        {{
            "question": "Texto de la pregunta",
            "options": ["Opción A simple", "Opción B simple", "Opción C simple", "Opción D simple"],
            "correct_answer": 0,
            "explanation": "Explicación detallada"
            "example_code": ""
        }}
    ]
}}

⚠️ VERIFICACIÓN FINAL OBLIGATORIA PARA CADA PREGUNTA:
1. Lee las 4 opciones y verifica que sean TODAS DIFERENTES (sin duplicados)
2. Lee la pregunta y TODAS las opciones
3. Identifica cuál opción es TÉCNICAMENTE CORRECTA Y COMPLETA
4. Cuenta el índice de esa opción (0, 1, 2, o 3) y asigna ese número a correct_answer
5. Verifica que la explicación mencione por qué esa opción es correcta

⚠️ ERRORES COMUNES QUE DEBES EVITAR:
- NO marques como correcta una opción que es PARCIALMENTE correcta o VAGA
- NO marques como correcta una opción que es TÉCNICAMENTE INCORRECTA
- NO confundas conceptos (ej: herencia NO es un tipo de variable, POO NO es programación funcional)
- Threading usa HILOS, no procesos (procesos es multiprocessing)
- Asyncio es SINGLE-THREADED con event loop, no usa múltiples hilos
- Metaclasses son CLASES que crean clases, no solo funciones
- Polimorfismo es la capacidad de usar una interfaz común para diferentes tipos, no solo herencia
- List comprehension es una EXPRESIÓN SINTÁCTICA, NO una función
- Tuple/Set pueden almacenar CUALQUIER tipo de dato, no solo números
- Dictionary almacena PARES CLAVE-VALOR, no solo datos genéricos
- EVITA opciones genéricas como "Error: No se puede usar X" a menos que sea técnicamente correcto

EJEMPLOS DE VERIFICACIÓN:
Pregunta: "¿Qué es la herencia en Python?"
Opciones:
  [0] "Un tipo de variable que puede almacenar datos y comportamiento"
  [1] "Un mecanismo que permite crear clases basadas en otras clases"
  [2] "Un tipo de variable que solo almacena datos"
  [3] "Una función que modifica el comportamiento de otra función"
¿Cuál es correcta? → [1] "Un mecanismo que permite crear clases basadas en otras clases"
correct_answer: 1

Pregunta: "¿Qué es la programación orientada a objetos?"
Opciones:
  [0] "Un enfoque que utiliza clases y herencia para organizar código"
  [1] "Un enfoque funcional donde las funciones son los objetos principales"
  [2] "Un tipo de variable que almacena datos"
  [3] "Una forma de iterar sobre listas"
¿Cuál es correcta? → [0] "Un enfoque que utiliza clases y herencia para organizar código"
correct_answer: 0

Pregunta: "¿Cuál es la diferencia entre una lista y una tupla?"
Opciones:
  [0] "Las listas son más rápidas de crear"
  [1] "Las listas son mutables, las tuplas son inmutables"
  [2] "Las tuplas pueden almacenar más elementos"
  [3] "Las listas son solo para almacenar datos, las tuplas para código"
¿Cuál es correcta? → [1] "Las listas son mutables, las tuplas son inmutables"
correct_answer: 1

Pregunta: "¿Qué es un decorador en Python?"
Opciones:
  [0] "Una función que modifica el comportamiento de otra función"
  [1] "Un método que se define dentro de una clase"
  [2] "Un tipo de variable especial"
  [3] "Una forma de iterar sobre listas"
¿Cuál es correcta? → [0] "Una función que modifica el comportamiento de otra función"
correct_answer: 0

REGLAS JSON CRÍTICAS:
- USA SOLO comillas dobles (") para strings, NUNCA comillas simples (')
- NO uses comillas curvas (" ") ni apóstrofes curvos (' ')
- Escapa caracteres especiales con backslash: \n para nueva línea, \" para comillas dentro de strings
- NO pongas comas después del último elemento de un array u objeto
- Asegúrate de cerrar todos los corchetes y llaves

Genera EXACTAMENTE {num_questions} preguntas creativas y variadas.
Responde SOLO con el JSON válido, sin texto adicional antes o después."""

    try:
        print(f"  🤖 Llamando al modelo de IA...")
        request_options = RequestOptions(timeout=60)  # Timeout de 60 segundos
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.8,  # Creatividad moderada
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 8000,  # Suficiente para 10 preguntas
            },
            request_options=request_options
        )
        
        print(f"  ✅ Respuesta recibida del modelo")
        
        if not response or not hasattr(response, 'text'):
            print(f"  ❌ Respuesta vacía o sin texto del modelo")
            return []
        
        text = response.text.strip()
        
        if not text:
            print(f"  ❌ Texto de respuesta vacío")
            return []
        
        print(f"  📄 Longitud de respuesta: {len(text)} caracteres")
        
        # Limpiar markdown y caracteres problemáticos
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # Reemplazar comillas curvas por comillas rectas
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace("'", "'").replace("'", "'")
        
        # CRÍTICO: Escapar backslashes que no están escapados correctamente
        # Esto previene errores como "Invalid \escape" en el JSON
        # Buscar patrones como \m, \d, \x (que no son escapes válidos) y reemplazarlos por \\m, \\d, \\x
        # Pero NO tocar los escapes válidos como \n, \t, \", \\
        valid_escapes = ['n', 't', 'r', '"', "'", '\\', '/', 'b', 'f']
        
        # Función para escapar backslashes inválidos
        def fix_invalid_escapes(match):
            char_after_backslash = match.group(1)
            if char_after_backslash in valid_escapes:
                # Es un escape válido, dejarlo como está
                return match.group(0)
            else:
                # Es un escape inválido, agregar otro backslash
                return '\\\\' + char_after_backslash
        
        # Aplicar la corrección
        text = re.sub(r'\\(.)', fix_invalid_escapes, text)
        
        # Intentar encontrar el JSON si hay texto antes/después
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group(0)
        
        # Parsear JSON
        data = json.loads(text)
        
        # Validar estructura
        if "questions" not in data or not isinstance(data["questions"], list):
            raise ValueError("Formato de respuesta inválido")
        
        questions = data["questions"]
        
        # Validar cada pregunta y mezclar opciones aleatoriamente
        import random
        valid_questions = []
        rejected_count = 0
        
        for q in questions:
            if all(key in q for key in ["question", "options", "correct_answer", "explanation"]):
                # Asegurar que example_code existe
                if "example_code" not in q:
                    q["example_code"] = ""
                
                # VALIDAR QUE LAS OPCIONES NO SEAN SOLO NÚMEROS
                options = q["options"]
                if len(options) != 4:
                    print(f"  ⚠️ Pregunta rechazada: no tiene exactamente 4 opciones")
                    rejected_count += 1
                    continue
                
                # Verificar si todas las opciones son solo números del 1-4
                options_str = [str(opt).strip() for opt in options]
                if set(options_str) == {"1", "2", "3", "4"} or set(options_str) == {"A", "B", "C", "D"}:
                    print(f"  ⚠️ Pregunta rechazada: opciones inválidas (solo números o letras)")
                    rejected_count += 1
                    continue
                
                # Verificar que las opciones tengan contenido significativo
                all_too_short = all(len(str(opt).strip()) <= 2 for opt in options)
                if all_too_short:
                    print(f"  ⚠️ Pregunta rechazada: opciones demasiado cortas")
                    rejected_count += 1
                    continue
                
                # NUEVA VALIDACIÓN: Detectar opciones duplicadas o muy similares
                options_lower = [str(opt).strip().lower() for opt in options]
                
                # 1. Verificar duplicados EXACTOS (texto idéntico)
                if len(options_lower) != len(set(options_lower)):
                    print(f"  ⚠️ Pregunta rechazada: opciones duplicadas EXACTAS detectadas")
                    print(f"     Opciones originales: {options_str}")
                    # Mostrar cuáles son duplicadas
                    seen = set()
                    for idx, opt in enumerate(options_lower):
                        if opt in seen:
                            print(f"     ❌ Opción {idx+1} es duplicada: '{options_str[idx]}'")
                        seen.add(opt)
                    rejected_count += 1
                    continue
                
                # 2. Normalizar texto para comparación más estricta (quitar puntuación)
                import string
                def normalize_text(text):
                    """Normaliza texto quitando puntuación y espacios extra"""
                    # Quitar puntuación
                    text = text.translate(str.maketrans('', '', string.punctuation))
                    # Quitar espacios extra y convertir a minúsculas
                    return ' '.join(text.lower().split())
                
                options_normalized = [normalize_text(str(opt)) for opt in options]
                
                # Verificar duplicados después de normalización
                if len(options_normalized) != len(set(options_normalized)):
                    print(f"  ⚠️ Pregunta rechazada: opciones duplicadas (después de normalizar)")
                    print(f"     Opciones originales: {options_str}")
                    seen = set()
                    for idx, opt in enumerate(options_normalized):
                        if opt in seen:
                            print(f"     ❌ Opción {idx+1} es duplicada: '{options_str[idx]}'")
                        seen.add(opt)
                    rejected_count += 1
                    continue
                
                # 3. Verificar similitud alta (más del 85% de las palabras son iguales)
                has_similar = False
                for i in range(len(options_normalized)):
                    for j in range(i + 1, len(options_normalized)):
                        opt1_words = set(options_normalized[i].split())
                        opt2_words = set(options_normalized[j].split())
                        
                        if len(opt1_words) > 0 and len(opt2_words) > 0:
                            # Calcular similitud (palabras en común / total de palabras únicas)
                            common = len(opt1_words & opt2_words)
                            total = len(opt1_words | opt2_words)
                            similarity = common / total if total > 0 else 0
                            
                            if similarity > 0.85:  # Más del 85% similar
                                has_similar = True
                                print(f"  ⚠️ Pregunta rechazada: opciones muy similares detectadas")
                                print(f"     Opción {i+1}: {options_str[i]}")
                                print(f"     Opción {j+1}: {options_str[j]}")
                                print(f"     Similitud: {similarity*100:.0f}%")
                                break
                    if has_similar:
                        break
                
                if has_similar:
                    rejected_count += 1
                    continue
                
                # CONVERTIR correct_answer a int si es string
                try:
                    correct_answer_idx = int(q["correct_answer"])
                except (ValueError, TypeError):
                    print(f"  ⚠️ correct_answer inválido: {q['correct_answer']}, usando 0")
                    correct_answer_idx = 0
                
                # Validar que el índice esté en rango
                if correct_answer_idx < 0 or correct_answer_idx >= len(q["options"]):
                    print(f"  ⚠️ correct_answer fuera de rango: {correct_answer_idx}, usando 0")
                    correct_answer_idx = 0
                
                # Validar que las opciones no sean genéricas e incorrectas
                generic_wrong_options = [
                    "un tipo de variable",
                    "un algoritmo de búsqueda",
                    "una función que modifica",
                    "un método para almacenar",
                    "no se puede usar",
                    "error:",
                    "una lista de cadenas",
                    "solo almacena números",
                    "solo almacena datos"
                ]
                
                # Contar cuántas opciones son genéricas
                generic_count = sum(1 for opt in options_lower if any(generic in opt for generic in generic_wrong_options))
                
                # Si más de 2 opciones son genéricas, probablemente la pregunta es de mala calidad
                if generic_count >= 3:
                    print(f"  ⚠️ Pregunta rechazada: demasiadas opciones genéricas ({generic_count}/4)")
                    print(f"     Opciones: {options_str}")
                    rejected_count += 1
                    continue
                
                # Validar conceptos específicos mal definidos
                question_lower = q['question'].lower()
                
                # List comprehension NO es una función
                if 'list comprehension' in question_lower or 'comprensión' in question_lower:
                    if any('función' in opt.lower() for opt in options_str):
                        print(f"  ⚠️ Pregunta rechazada: list comprehension descrita incorrectamente como función")
                        rejected_count += 1
                        continue
                
                # Tuple/Set NO son solo para números
                if ('tuple' in question_lower or 'tupla' in question_lower or 'set' in question_lower or 'conjunto' in question_lower):
                    correct_opt = options_str[correct_answer_idx].lower()
                    if 'solo.*números' in correct_opt or 'solo.*datos' in correct_opt:
                        print(f"  ⚠️ Pregunta rechazada: tuple/set descrito incorrectamente")
                        rejected_count += 1
                        continue
                
                # VALIDACIÓN SEMÁNTICA BÁSICA: Detectar respuestas obviamente incorrectas
                question_lower = q['question'].lower()
                correct_option_lower = q['options'][correct_answer_idx].lower()
                
                # LOGGING DETALLADO: Mostrar la pregunta y la respuesta marcada como correcta
                print(f"\n  🔍 VALIDANDO PREGUNTA:")
                print(f"     Pregunta: {q['question'][:80]}...")
                print(f"     Opciones:")
                for idx, opt in enumerate(q['options']):
                    marker = " ← MARCADA COMO CORRECTA" if idx == correct_answer_idx else ""
                    print(f"       [{idx}] {opt[:70]}...{marker}")
                
                # Palabras clave que indican respuestas incorrectas
                obviously_wrong_patterns = [
                    ('herencia', 'tipo de variable'),  # Herencia no es un tipo de variable
                    ('herencia', 'solo.*datos'),  # Herencia no es solo datos
                    ('orientada a objetos', 'funcional'),  # POO no es funcional
                    ('orientada a objetos', 'función.*objeto'),  # POO no es funciones como objetos
                    ('diccionario', 'solo.*números'),  # Diccionarios no son solo números
                    ('tupla', 'pares clave-valor'),  # Tuplas no son diccionarios
                    ('conjunto', 'pares clave-valor'),  # Conjuntos no son diccionarios
                    ('lista.*tupla', 'más rápidas'),  # Diferencia principal no es velocidad
                    ('lista.*tupla', 'solo.*almacenar'),  # Diferencia principal es mutabilidad
                    ('decorador', 'método.*clase'),  # Decorador no es un método de clase
                    ('decorador', 'tipo de variable'),  # Decorador no es un tipo de variable
                    ('generador', 'modifica.*estado.*memoria'),  # Generador no modifica memoria
                    ('threading', 'procesos'),  # Threading usa hilos, no procesos
                    ('thread', 'procesos'),  # Thread usa hilos, no procesos
                    ('asyncio', 'múltiples.*hilos'),  # Asyncio es single-threaded
                    ('async', 'múltiples.*hilos'),  # Async es single-threaded
                    ('metaclass', 'función.*crea.*clase'),  # Metaclass no es solo una función
                    ('polimorfismo', 'herencia'),  # Polimorfismo no es solo herencia
                    ('método', 'atributo'),  # Método NO es un atributo
                    ('bucle', 'función.*modifica'),  # Bucle NO es una función que modifica
                    ('loop', 'función.*modifica'),  # Loop NO es una función que modifica
                    ('bucle', 'tipo.*variable'),  # Bucle NO es un tipo de variable
                    ('loop', 'tipo.*variable'),  # Loop NO es un tipo de variable
                    ('list comprehension', 'función.*modifica'),  # List comprehension NO es una función
                    ('comprensión', 'función.*modifica'),  # Comprensión NO es una función
                    ('map\\(\\)', 'iterar'),  # map() no es solo para iterar
                    ('filter\\(\\)', 'iterar'),  # filter() no es solo para iterar
                    ('lambda', 'clase'),  # lambda no es una clase
                ]
                
                is_obviously_wrong = False
                for keyword, wrong_pattern in obviously_wrong_patterns:
                    if re.search(keyword, question_lower) and re.search(wrong_pattern, correct_option_lower):
                        print(f"  ❌ Pregunta rechazada: respuesta correcta parece incorrecta")
                        print(f"     Pregunta contiene: '{keyword}'")
                        print(f"     Respuesta marcada como correcta: '{q['options'][correct_answer_idx][:60]}...'")
                        print(f"     Patrón sospechoso: '{wrong_pattern}'")
                        is_obviously_wrong = True
                        break
                
                if is_obviously_wrong:
                    rejected_count += 1
                    continue
                
                # ============================================================================
                # NUEVAS VALIDACIONES SEMÁNTICAS
                # ============================================================================
                
                # Validación 1: Validar corrección de conceptos técnicos
                is_valid, reason = _validate_concept_correctness(q['question'], q['options'], correct_answer_idx)
                if not is_valid:
                    print(f"  ❌ Pregunta rechazada por error técnico en concepto: {reason}")
                    rejected_count += 1
                    continue
                
                # Validación 2: Validar coherencia código-pregunta
                if q.get('example_code', '').strip():
                    is_valid, reason = _validate_code_question_match(q['question'], q['example_code'])
                    if not is_valid:
                        print(f"  ❌ Pregunta rechazada por código no coincidente: {reason}")
                        rejected_count += 1
                        continue
                
                # Validación 3: Validar nivel de dificultad
                is_valid, reason = _validate_difficulty_level(q['question'], level)
                if not is_valid:
                    print(f"  ❌ Pregunta rechazada por nivel incorrecto: {reason}")
                    rejected_count += 1
                    continue
                
                # Validación 4: Validar terminología específica del lenguaje
                is_valid, reason = _validate_language_specific(q['question'], q['options'], language)
                if not is_valid:
                    print(f"  ❌ Pregunta rechazada por terminología incorrecta: {reason}")
                    rejected_count += 1
                    continue
                
                # Validación 5: Prevenir bloques de código duplicados
                if _detect_embedded_code(q['question']) and q.get('example_code', '').strip():
                    print(f"  ⚠️ Código duplicado detectado (embebido + example_code), corrigiendo automáticamente")
                    q['example_code'] = ''  # Eliminar example_code, mantener código embebido
                
                print(f"  ✅ Pregunta validada correctamente")
                
                # MEZCLAR OPCIONES para que la respuesta correcta no siempre esté en la misma posición
                print(f"\n  🔍 PREGUNTA ANTES DE MEZCLAR:")
                print(f"     Texto: {q['question'][:60]}...")
                print(f"     Índice correcto ORIGINAL: {correct_answer_idx}")
                print(f"     Opción correcta ORIGINAL: '{q['options'][correct_answer_idx][:50]}...'")
                
                # Crear lista de tuplas (índice_original, opción)
                options_with_indices = list(enumerate(q['options']))
                random.shuffle(options_with_indices)
                
                # Reconstruir opciones mezcladas y encontrar nuevo índice de la respuesta correcta
                shuffled_options = [opt for _, opt in options_with_indices]
                new_correct_index = next(i for i, (orig_idx, _) in enumerate(options_with_indices) if orig_idx == correct_answer_idx)
                
                q['options'] = shuffled_options
                q['correct_answer'] = new_correct_index
                
                print(f"  ✅ Pregunta DESPUÉS de mezclar:")
                print(f"     Índice correcto NUEVO: {new_correct_index}")
                print(f"     Opción correcta: '{shuffled_options[new_correct_index][:50]}...'")
                print(f"     Todas las opciones mezcladas:")
                for idx, opt in enumerate(shuffled_options):
                    marker = " ← CORRECTA" if idx == new_correct_index else ""
                    print(f"       [{idx}] {opt[:50]}...{marker}")
                
                valid_questions.append(q)
        
        if rejected_count > 0:
            print(f"  ⚠️ Se rechazaron {rejected_count} preguntas por opciones inválidas")
        
        return valid_questions
        
    except json.JSONDecodeError as e:
        print(f"  ❌ Error parseando JSON en lote: {e}")
        print(f"  📄 Texto problemático cerca del error: {text[max(0, e.pos-100):min(len(text), e.pos+100)]}")
        print(f"  📄 Primeros 500 caracteres de la respuesta: {text[:500]}")
        return []
    except Exception as e:
        print(f"  ❌ Error generando lote de preguntas: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []


# ========== FUNCIÓN PARA GENERAR EVALUACIÓN DE SECCIÓN CREATIVA ==========

def generate_creative_section_evaluation(model, language, level, section_title, num_questions=15):
    """
    Genera una evaluación de sección con preguntas creativas usando IA.
    Similar a generate_creative_final_exam pero para secciones específicas.
    
    Args:
        model: Modelo de IA de Google Gemini
        language: Lenguaje de programación
        level: Nivel de dificultad
        section_title: Título de la sección/tema
        num_questions: Número de preguntas (default: 15)
    
    Returns:
        dict: Evaluación con preguntas creativas
    """
    
    # Generar en un solo lote para secciones (son pocas preguntas)
    questions = _generate_question_batch(model, language, level, num_questions, 1, section_title)
    
    return {
        "questions": questions,
        "metadata": {
            "language": language,
            "level": level,
            "section_title": section_title,
            "total_questions": len(questions),
            "source": "ai_generated"
        }
    }


# ==============================================================================
# EVALUACIÓN MEJORADA PARA DESAFÍOS - SIN PUNTUACIONES ARBITRARIAS
# ==============================================================================

def evaluate_challenge_code_clear(model, challenge_title, challenge_description, student_code, reference_solution=None, language="Python"):
    """
    Evalúa código de desafío de manera clara y precisa.
    Soporta cualquier lenguaje de programación.
    """

    _lang_map = {
        "Python": "python", "JavaScript": "javascript",
        "Java": "java", "C++": "cpp", "C#": "csharp",
        "C": "c", "Ruby": "ruby", "PHP": "php",
        "Go": "go", "Rust": "rust", "Swift": "swift",
        "Kotlin": "kotlin", "TypeScript": "typescript",
        "SQL": "sql", "NoSQL": "javascript",
        "HTML/CSS": "html", "R": "r", "MATLAB": "matlab",
    }
    lang_block = _lang_map.get(language, language.lower())

    prompt = f"""
Eres un evaluador experto en {language}. Tu tarea es evaluar si el código del estudiante resuelve correctamente el problema.

DESAFÍO: {challenge_title}
DESCRIPCIÓN: {challenge_description}
LENGUAJE: {language}

CÓDIGO DEL ESTUDIANTE:
```{lang_block}
{student_code}
```

{f'''SOLUCIÓN DE REFERENCIA:
```{lang_block}
{reference_solution}
```''' if reference_solution else ''}

INSTRUCCIONES:
1. Evalúa el código como experto en {language} — usa la sintaxis y convenciones correctas de {language}
2. Verifica si el código resuelve el problema planteado
3. NO penalices por usar convenciones de {language} diferentes a otros lenguajes

RESPONDE EN FORMATO JSON ESTRICTO:
{{
    "is_correct": true o false,
    "positive_aspects": ["aspecto positivo 1", "aspecto positivo 2"],
    "improvements": ["mejora 1"],
    "explanation": "Explicación clara de por qué el código está correcto o incorrecto"
}}

REGLAS CRÍTICAS:
- Evalúa según las reglas de {language}, NO de Python u otro lenguaje
- Si el código resuelve el problema correctamente, is_correct DEBE ser true
- Sé justo y preciso — el código correcto debe recibir true
"""

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()

        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'is_correct': result.get('is_correct', False),
                'positive_aspects': result.get('positive_aspects', []),
                'improvements': result.get('improvements', []),
                'explanation': result.get('explanation', 'Evaluación completada')
            }
        else:
            return {
                'is_correct': False,
                'positive_aspects': ['El código fue enviado correctamente'],
                'improvements': ['Revisa la sintaxis y la lógica del código'],
                'explanation': 'No se pudo evaluar el código. Por favor, intenta nuevamente.'
            }
    except Exception as e:
        return {
            'is_correct': False,
            'positive_aspects': ['Intentaste resolver el problema'],
            'improvements': [f'Error en la evaluación: {str(e)}'],
            'explanation': 'Hubo un error al evaluar el código. Por favor, intenta nuevamente.'
        }


# ==============================================================================
# GENERACIÓN DINÁMICA DE DESAFÍOS DIARIOS CON IA
# ==============================================================================

def generate_daily_challenge(model, language='Python', difficulty='easy'):
    """
    Genera un desafío diario único usando IA.
    
    Args:
        model: Modelo de IA de Gemini
        language: Lenguaje de programación
        difficulty: Dificultad (easy, medium, hard)
    
    Returns:
        dict con el desafío generado
    """
    
    difficulty_specs = {
        'easy': {
            'description': 'conceptos básicos y sintaxis fundamental',
            'lines': '5-15 líneas',
            'concepts': 'variables, operadores básicos, input/output, condicionales simples',
            'points': 30,
            'bonus': 15
        },
        'medium': {
            'description': 'estructuras de datos y lógica intermedia',
            'lines': '15-30 líneas',
            'concepts': 'listas, diccionarios, bucles, funciones, manejo de strings',
            'points': 50,
            'bonus': 20
        },
        'hard': {
            'description': 'algoritmos complejos y optimización',
            'lines': '30-50 líneas',
            'concepts': 'recursión, algoritmos de ordenamiento, estructuras avanzadas, optimización',
            'points': 80,
            'bonus': 30
        }
    }
    
    spec = difficulty_specs.get(difficulty, difficulty_specs['easy'])
    
    prompt = f"""
Genera un desafío de programación ÚNICO y ORIGINAL en {language} de dificultad {difficulty}.

ESPECIFICACIONES:
- Nivel: {difficulty.upper()}
- Conceptos: {spec['concepts']}
- Longitud esperada: {spec['lines']}
- Debe ser: {spec['description']}

REQUISITOS IMPORTANTES:
1. El desafío debe ser DIFERENTE cada vez (usa creatividad)
2. Debe ser práctico y realista
3. Debe tener casos de prueba claros
4. Debe incluir ejemplos de entrada/salida
5. La solución debe ser verificable

RESPONDE EN FORMATO JSON ESTRICTO:
{{
    "title": "Título corto y descriptivo del desafío",
    "description": "Descripción clara del problema a resolver (2-3 párrafos)",
    "input_description": "Descripción de la entrada esperada",
    "output_description": "Descripción de la salida esperada",
    "example_1_input": "Ejemplo de entrada 1",
    "example_1_output": "Ejemplo de salida 1",
    "example_2_input": "Ejemplo de entrada 2",
    "example_2_output": "Ejemplo de salida 2",
    "restrictions": ["Restricción 1", "Restricción 2", "Restricción 3"],
    "hint": "Una pista útil sin revelar la solución",
    "solution_code": "Código de la solución completa y funcional",
    "test_cases": [
        {{"input": "caso 1", "expected_output": "resultado 1"}},
        {{"input": "caso 2", "expected_output": "resultado 2"}}
    ]
}}

IMPORTANTE: 
- Sé creativo y genera un problema DIFERENTE cada vez
- Asegúrate de que el código de solución sea funcional
- Los ejemplos deben ser claros y específicos
"""
    
    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Extraer JSON de la respuesta
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            challenge_data = json.loads(json_match.group())
            
            # Agregar metadatos
            challenge_data['language'] = language
            challenge_data['difficulty'] = difficulty
            challenge_data['points'] = spec['points']
            challenge_data['bonus_points'] = spec['bonus']
            challenge_data['generated_at'] = datetime.now().isoformat()
            
            return challenge_data
        else:
            # Fallback con desafío básico
            return generate_fallback_challenge(language, difficulty, spec)
    except Exception as e:
        print(f"Error generando desafío: {e}")
        return generate_fallback_challenge(language, difficulty, spec)


def generate_fallback_challenge(language, difficulty, spec):
    """Genera un desafío de respaldo si falla la IA"""
    import random
    
    # Temas variados para generar desafíos diferentes
    topics = [
        "números primos", "palíndromos", "fibonacci", "factorial",
        "ordenamiento", "búsqueda", "validación", "conversión",
        "estadísticas", "manipulación de texto"
    ]
    
    topic = random.choice(topics)
    
    return {
        'title': f'Desafío de {topic.title()}',
        'description': f'Crea un programa en {language} que trabaje con {topic}.',
        'input_description': 'Entrada del usuario',
        'output_description': 'Resultado procesado',
        'example_1_input': '5',
        'example_1_output': '10',
        'example_2_input': '10',
        'example_2_output': '20',
        'restrictions': [
            f'Debe usar funciones de {language}',
            'Debe manejar errores',
            'Debe ser eficiente'
        ],
        'hint': 'Piensa en la lógica paso a paso',
        'solution_code': '# Solución de ejemplo\nprint("Implementa tu solución")',
        'test_cases': [],
        'language': language,
        'difficulty': difficulty,
        'points': spec['points'],
        'bonus_points': spec['bonus'],
        'generated_at': datetime.now().isoformat()
    }


# ==============================================================================
# TUTOR IA - ANÁLISIS DE ERRORES Y PISTAS
# ==============================================================================

def analyze_code_with_hints(model, student_code, language, problem_context=None):
    """
    Analiza código con errores y proporciona pistas para resolverlos (sin dar la solución completa).
    
    Args:
        model: Modelo de IA de Gemini
        student_code: Código del estudiante
        language: Lenguaje de programación
        problem_context: Contexto opcional del problema que está resolviendo
    
    Returns:
        dict con:
            - errors_found: list de errores detectados
            - hints: list de pistas para resolver cada error
            - areas_to_study: list de temas que debe estudiar/repasar
            - has_errors: bool indicando si hay errores
    """
    
    context_section = f"""
CONTEXTO DEL PROBLEMA:
{problem_context}
""" if problem_context else ""
    
    prompt = f"""
Eres un tutor experto en {language} que ayuda a estudiantes a aprender programación.

{context_section}

CÓDIGO DEL ESTUDIANTE:
```{language.lower()}
{student_code}
```

TU TAREA:
Analiza el código y ayuda al estudiante a encontrar y corregir errores POR SÍ MISMO.

IMPORTANTE: 
- NO des la solución completa
- NO escribas el código corregido
- DA PISTAS que guíen al estudiante a descubrir el error
- EXPLICA qué está mal sin dar la respuesta directa

RESPONDE EN FORMATO JSON ESTRICTO:
{{
    "has_errors": true o false,
    "errors_found": [
        {{
            "line": número de línea aproximado (o "general" si no es específico),
            "error_type": "sintaxis" | "lógica" | "tipo de dato" | "nombre" | "otro",
            "description": "Descripción clara del error sin dar la solución"
        }}
    ],
    "hints": [
        {{
            "for_error": "breve referencia al error",
            "hint": "Pista que guíe al estudiante (ej: '¿Has verificado si esa variable existe antes de usarla?')",
            "guiding_question": "Pregunta que haga pensar al estudiante"
        }}
    ],
    "areas_to_study": [
        {{
            "topic": "Tema a repasar (ej: 'Manejo de listas en Python')",
            "reason": "Por qué debe estudiar este tema",
            "resources": "Sugerencia de qué buscar o estudiar"
        }}
    ],
    "encouragement": "Mensaje motivacional para el estudiante"
}}

REGLAS:
1. Si no hay errores, has_errors debe ser false y errors_found debe estar vacío
2. Las pistas deben hacer PENSAR al estudiante, no darle la respuesta
3. Usa preguntas guía que lo lleven a descubrir el error
4. Sé específico sobre QUÉ revisar, pero no CÓMO corregirlo exactamente
5. Identifica áreas de conocimiento que necesita reforzar

EJEMPLOS DE BUENAS PISTAS:
- "¿Qué tipo de dato devuelve la función input()? ¿Es compatible con operaciones matemáticas?"
- "Revisa la línea donde usas el índice. ¿Estás seguro de que ese índice existe en la lista?"
- "¿Has considerado qué pasa cuando el usuario ingresa un valor no numérico?"

EJEMPLOS DE MALAS PISTAS (NO HAGAS ESTO):
- "Cambia int(x) por float(x)" (demasiado directo)
- "Agrega un try-except aquí" (da la solución)
- "El error está en la línea 5" (sin explicación)
"""
    
    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Extraer JSON de la respuesta
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'has_errors': result.get('has_errors', False),
                'errors_found': result.get('errors_found', []),
                'hints': result.get('hints', []),
                'areas_to_study': result.get('areas_to_study', []),
                'encouragement': result.get('encouragement', '¡Sigue intentando! Estás en el camino correcto.')
            }
        else:
            return {
                'has_errors': True,
                'errors_found': [{'line': 'general', 'error_type': 'otro', 'description': 'No se pudo analizar el código correctamente'}],
                'hints': [{'for_error': 'general', 'hint': 'Revisa la sintaxis básica del lenguaje', 'guiding_question': '¿Está todo correctamente escrito?'}],
                'areas_to_study': [],
                'encouragement': 'Intenta revisar tu código línea por línea.'
            }
    except Exception as e:
        return {
            'has_errors': True,
            'errors_found': [{'line': 'general', 'error_type': 'otro', 'description': f'Error al analizar: {str(e)}'}],
            'hints': [{'for_error': 'general', 'hint': 'Verifica la sintaxis básica', 'guiding_question': '¿El código está completo?'}],
            'areas_to_study': [],
            'encouragement': 'No te rindas, sigue intentando.'
        }


def provide_corrected_code_with_explanation(model, student_code, language, problem_context=None):
    """
    Proporciona el código corregido con explicación detallada de cada cambio realizado.
    
    Args:
        model: Modelo de IA de Gemini
        student_code: Código del estudiante con errores
        language: Lenguaje de programación
        problem_context: Contexto opcional del problema
    
    Returns:
        dict con:
            - corrected_code: str con el código corregido
            - changes_made: list de cambios realizados con explicación
            - why_it_works: str explicando por qué la solución funciona
            - learning_points: list de puntos clave de aprendizaje
    """
    
    context_section = f"""
CONTEXTO DEL PROBLEMA:
{problem_context}
""" if problem_context else ""
    
    prompt = f"""
Eres un tutor experto en {language} que proporciona soluciones educativas.

{context_section}

CÓDIGO DEL ESTUDIANTE (CON ERRORES):
```{language.lower()}
{student_code}
```

TU TAREA:
Proporciona el código CORREGIDO y explica CADA CAMBIO que realizaste.

RESPONDE EN FORMATO JSON ESTRICTO:
{{
    "corrected_code": "Código completo corregido y funcional",
    "changes_made": [
        {{
            "change_number": 1,
            "original": "Código o línea original",
            "corrected": "Código o línea corregida",
            "reason": "Explicación detallada de POR QUÉ se hizo este cambio",
            "concept": "Concepto de programación relacionado"
        }}
    ],
    "why_it_works": "Explicación de por qué la solución corregida funciona correctamente",
    "learning_points": [
        "Punto clave 1 que el estudiante debe recordar",
        "Punto clave 2 que el estudiante debe recordar",
        "Punto clave 3 que el estudiante debe recordar"
    ],
    "additional_tips": [
        "Consejo adicional 1 para mejorar",
        "Consejo adicional 2 para mejorar"
    ]
}}

REGLAS IMPORTANTES:
1. El código corregido debe ser FUNCIONAL y COMPLETO
2. CADA cambio debe estar documentado con su razón
3. Explica NO SOLO qué cambiaste, sino POR QUÉ era necesario
4. Identifica los conceptos de programación involucrados
5. Proporciona puntos de aprendizaje claros y concisos
6. Si el código original no tenía errores, indícalo claramente

FORMATO DE CAMBIOS:
- Sé específico: muestra el código antes y después
- Explica el concepto: relaciona el cambio con teoría de programación
- Sé educativo: el estudiante debe APRENDER del cambio, no solo copiarlo

EJEMPLO DE BUEN CAMBIO:
{{
    "change_number": 1,
    "original": "x = input('Número: ')",
    "corrected": "x = int(input('Número: '))",
    "reason": "La función input() siempre devuelve una cadena de texto (string). Para realizar operaciones matemáticas, necesitamos convertir el string a un número entero usando int(). Sin esta conversión, Python intentaría hacer operaciones con texto, lo cual causaría un error.",
    "concept": "Conversión de tipos de datos (Type Casting)"
}}
"""
    
    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Extraer JSON de la respuesta
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'corrected_code': result.get('corrected_code', student_code),
                'changes_made': result.get('changes_made', []),
                'why_it_works': result.get('why_it_works', 'El código ha sido corregido.'),
                'learning_points': result.get('learning_points', []),
                'additional_tips': result.get('additional_tips', [])
            }
        else:
            return {
                'corrected_code': student_code,
                'changes_made': [{'change_number': 1, 'original': 'N/A', 'corrected': 'N/A', 'reason': 'No se pudo procesar la corrección', 'concept': 'N/A'}],
                'why_it_works': 'No se pudo generar la corrección. Por favor, intenta nuevamente.',
                'learning_points': ['Verifica la sintaxis básica del lenguaje'],
                'additional_tips': []
            }
    except Exception as e:
        return {
            'corrected_code': student_code,
            'changes_made': [{'change_number': 1, 'original': 'N/A', 'corrected': 'N/A', 'reason': f'Error: {str(e)}', 'concept': 'N/A'}],
            'why_it_works': 'Hubo un error al generar la corrección.',
            'learning_points': ['Intenta revisar el código manualmente'],
            'additional_tips': []
        }


def ai_review_exam_attempt(ai_manager, exam_id, details, conn):
    """
    Revisa un intento de examen usando IA con contexto completo del examen.
    Usa ThreadPoolExecutor para imponer un timeout real por pregunta en Windows.
    """
    import json as _json
    import re as _re
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    # Obtener preguntas del examen con respuestas correctas y opciones
    exam_questions = conn.execute(
        "SELECT id, question, question_type, options_json, correct_answer, points FROM exam_questions WHERE exam_id = ?",
        (exam_id,)
    ).fetchall()
    exam_q_map = {str(row['id']): dict(row) for row in exam_questions}

    def _build_prompt(detail, eq):
        question_text = detail.get('question', eq.get('question', ''))
        student_answer = detail.get('answer', '') or '(sin respuesta)'
        max_points = float(detail.get('max_points', eq.get('points', 10)))
        q_type = detail.get('type', eq.get('question_type', 'multiple_choice'))

        options = []
        correct_answer = eq.get('correct_answer') or ''
        if eq.get('options_json'):
            try:
                opts = _json.loads(eq['options_json'])
                if isinstance(opts, list):
                    options = opts
                    if not correct_answer:
                        for opt in opts:
                            if isinstance(opt, dict) and opt.get('is_correct'):
                                correct_answer = opt.get('text', opt.get('value', ''))
                                break
            except Exception:
                pass

        options_text = ''
        for opt in options:
            if isinstance(opt, dict):
                marker = '✓' if opt.get('is_correct') else ' '
                options_text += f"\n  [{marker}] {opt.get('text', opt.get('value', str(opt)))}"
            else:
                options_text += f"\n  - {opt}"

        return (
            f"Evalúa la respuesta. Responde SOLO JSON.\n"
            f"PREGUNTA: {question_text[:300]}\n"
            f"{'OPCIONES:' + options_text if options_text else ''}\n"
            f"{'RESPUESTA CORRECTA: ' + correct_answer if correct_answer else ''}\n"
            f"RESPUESTA ESTUDIANTE: {student_answer[:400]}\n"
            f"JSON: {{\"score\": <0-{max_points}>, \"feedback\": \"<breve>\", \"needs_manual_review\": <true|false>}}"
        ), max_points

    def _call_ai(prompt, max_points):
        try:
            res = ai_manager.call_with_retry(
                prompt,
                max_retries=1,
                max_output_tokens=80,
                temperature=0.1,
                timeout=12
            )
            m = _re.search(r'\{[^}]+\}', res or '')
            if m:
                parsed = _json.loads(m.group())
                score = max(0.0, min(float(parsed.get('score', 0)), max_points))
                return score, parsed.get('feedback', 'Evaluado por IA'), bool(parsed.get('needs_manual_review', False))
        except Exception:
            pass
        return None, None, True  # fallback: manual review

    results = []
    with ThreadPoolExecutor(max_workers=1) as executor:
        for detail in details:
            q_id = str(detail.get('q_id', ''))
            eq = exam_q_map.get(q_id, {})
            prompt, max_points = _build_prompt(detail, eq)

            detail = dict(detail)
            try:
                future = executor.submit(_call_ai, prompt, max_points)
                score, feedback, needs_manual = future.result(timeout=20)  # hard 20s wall clock
            except (FuturesTimeout, Exception):
                score, feedback, needs_manual = None, None, True

            if needs_manual or score is None:
                detail['ai_feedback'] = '⚠️ Requiere revisión manual'
                detail['needs_manual_review'] = True
            else:
                detail['score'] = score
                detail['ai_feedback'] = f'{feedback} (IA contextual)'
                detail['graded'] = True
                detail['needs_manual_review'] = False

            results.append(detail)

    return results
