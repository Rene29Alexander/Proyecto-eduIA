# -*- coding: utf-8 -*-
"""
utils_ai_core.py — Núcleo de IA sin dependencias de Streamlit
Semana 5: Observabilidad, rendimiento y escalabilidad

Contiene:
- AICache          — cache persistente en disco para respuestas de Gemini
- APIKeyPool       — rotación automática de múltiples API keys
- AIManagerCore    — núcleo de IA con rate limiting, reintentos y backoff
- get_contextualized_chat_response — función standalone de chat
"""

import os
import time
import pickle
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger("eduia.ai_core")

# =============================================================================
# AICache — cache persistente en disco
# =============================================================================

class AICache:
    """Cache para respuestas de IA con TTL y límite de memoria."""

    def __init__(self, max_size: int = 100, ttl_hours: int = 24, max_memory_mb: int = 50):
        self.max_size = max_size
        self.ttl_hours = ttl_hours
        self.max_memory_mb = max_memory_mb
        self.cache: Dict[str, Any] = {}
        self.cache_file = "ai_cache.pkl"
        self.hit_count = 0
        self.miss_count = 0
        self._load_cache()

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "rb") as f:
                    self.cache = pickle.load(f)
                self._clean_expired()
            except Exception as exc:
                logger.warning("Error cargando cache: %s", exc)
                self.cache = {}

    def _save_cache(self):
        try:
            size_mb = len(pickle.dumps(self.cache)) / (1024 * 1024)
            if size_mb > self.max_memory_mb:
                self._reduce_cache_size()
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.cache, f)
        except Exception as exc:
            logger.warning("Error guardando cache: %s", exc)

    # ── Limpieza ──────────────────────────────────────────────────────────────

    def _is_expired(self, entry: Dict) -> bool:
        if not entry or "timestamp" not in entry:
            return True
        return datetime.now() - entry["timestamp"] >= timedelta(hours=self.ttl_hours)

    def _clean_expired(self):
        expired = [k for k, v in self.cache.items() if self._is_expired(v)]
        for k in expired:
            del self.cache[k]

    def _reduce_cache_size(self):
        if len(self.cache) <= self.max_size // 2:
            return
        sorted_items = sorted(
            self.cache.items(), key=lambda x: x[1].get("timestamp", datetime.min)
        )
        for key, _ in sorted_items[: len(sorted_items) - self.max_size // 2]:
            del self.cache[key]

    # ── API pública ───────────────────────────────────────────────────────────

    @staticmethod
    def make_key(prompt: str, model: str = "") -> str:
        raw = f"{model}:{prompt}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[str]:
        entry = self.cache.get(key)
        if entry and not self._is_expired(entry):
            self.hit_count += 1
            logger.debug("Cache HIT key=%s", key[:8])
            return entry["data"]
        if key in self.cache:
            del self.cache[key]
        self.miss_count += 1
        return None

    def set(self, key: str, data: str):
        if len(self.cache) >= self.max_size:
            self._reduce_cache_size()
        self.cache[key] = {"data": data, "timestamp": datetime.now()}
        self._save_cache()

    def stats(self) -> Dict[str, Any]:
        total = self.hit_count + self.miss_count
        return {
            "entries": len(self.cache),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": round(self.hit_count / total * 100, 1) if total else 0,
        }


# =============================================================================
# APIKeyPool — rotación automática de keys
# =============================================================================

class APIKeyPool:
    """
    Gestiona un pool de API keys de Gemini.
    Cuando una key recibe 429 la bloquea 60 s; con 403 la bloquea 24 h.
    """

    _BLOCK_QUOTA   = 60       # segundos bloqueada por cuota agotada
    _BLOCK_INVALID = 86_400   # segundos bloqueada por key inválida (24 h)

    def __init__(self, keys: List[str]):
        self.keys = [k.strip() for k in keys if k.strip()]
        self._blocked_until: Dict[str, float] = {}
        self._current_index = 0

    @classmethod
    def from_env_and_db(cls, db_path: Optional[str] = None) -> "APIKeyPool":
        """Carga keys de variables de entorno y opcionalmente de la BD."""
        keys: List[str] = []
        for i in range(1, 6):
            suffix = "" if i == 1 else f"_{i}"
            key = os.getenv(f"GEMINI_API_KEY{suffix}", "").strip()
            if key:
                keys.append(key)

        if db_path:
            try:
                import sqlite3
                conn = sqlite3.connect(db_path, timeout=5)
                for i in range(1, 6):
                    suffix = "" if i == 1 else f"_{i}"
                    row = conn.execute(
                        "SELECT value FROM system_settings WHERE key=?",
                        (f"gemini_api_key{suffix}",),
                    ).fetchone()
                    if row and row[0] and row[0].strip() not in keys:
                        keys.append(row[0].strip())
                conn.close()
            except Exception as exc:
                logger.warning("Error cargando keys desde BD: %s", exc)

        return cls(keys)

    def get_active_key(self) -> Optional[str]:
        now = time.time()
        for i in range(len(self.keys)):
            idx = (self._current_index + i) % len(self.keys)
            key = self.keys[idx]
            if now >= self._blocked_until.get(key, 0):
                self._current_index = idx
                return key
        return None  # todas bloqueadas

    def report_error(self, key: str, status_code: int):
        if status_code == 429:
            self._blocked_until[key] = time.time() + self._BLOCK_QUOTA
            logger.warning("Key ...%s bloqueada 60s por cuota (429)", key[-6:])
            self._current_index = (self._current_index + 1) % max(len(self.keys), 1)
        elif status_code == 403:
            self._blocked_until[key] = time.time() + self._BLOCK_INVALID
            logger.error("Key ...%s bloqueada 24h por inválida (403)", key[-6:])
            self._current_index = (self._current_index + 1) % max(len(self.keys), 1)

    def get_status(self) -> List[Dict]:
        now = time.time()
        result = []
        for key in self.keys:
            blocked_until = self._blocked_until.get(key, 0)
            result.append({
                "key_hint": f"...{key[-6:]}",
                "active": now >= blocked_until,
                "blocked_seconds_remaining": max(0, int(blocked_until - now)),
            })
        return result


# =============================================================================
# AIManagerCore — núcleo de IA sin Streamlit
# =============================================================================

class AIManagerCore:
    """
    Gestor de IA independiente de Streamlit.
    Soporta pool de keys, reintentos con backoff exponencial y fallback.
    """

    MODELS = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
    ]

    def __init__(self, api_key: str, db_path: Optional[str] = None):
        self.api_key = api_key
        self.model = None
        self.current_model_name: Optional[str] = None
        self.cache = AICache()
        self.key_pool = APIKeyPool.from_env_and_db(db_path)

        # Si el pool no cargó keys, usar la key directa
        if not self.key_pool.keys:
            self.key_pool = APIKeyPool([api_key])

        self._init_model()

    def _init_model(self):
        """Inicializa el modelo probando en orden de preferencia."""
        from google import genai
        from google.genai import types as genai_types

        key = self.key_pool.get_active_key() or self.api_key
        self._genai_client = genai.Client(api_key=key)

        for model_name in self.MODELS:
            try:
                # Prueba mínima para verificar que el modelo responde
                self._genai_client.models.generate_content(
                    model=model_name,
                    contents="test",
                    config=genai_types.GenerateContentConfig(max_output_tokens=5),
                )
                self.model = model_name          # guardamos el nombre, no un objeto
                self.current_model_name = model_name
                logger.info("Modelo inicializado: %s", model_name)
                return
            except Exception as exc:
                logger.warning("Modelo %s no disponible: %s", model_name, exc)
                self.model = None

        logger.error("Ningún modelo de Gemini disponible.")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        use_cache: bool = True,
        retries: int = 3,
    ) -> str:
        """Genera una respuesta con reintentos y backoff exponencial."""
        cache_key = AICache.make_key(prompt, self.current_model_name or "")

        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        if not self.model:
            return self._fallback_response()

        last_exc = None
        for attempt in range(retries):
            try:
                from google import genai
                from google.genai import types as genai_types

                active_key = self.key_pool.get_active_key() or self.api_key
                client = genai.Client(api_key=active_key)

                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        max_output_tokens=max_tokens
                    ),
                )
                text = response.text.strip()

                if use_cache:
                    self.cache.set(cache_key, text)

                return text

            except Exception as exc:
                last_exc = exc
                err_str = str(exc)
                current_key = self.key_pool.get_active_key() or self.api_key

                if "429" in err_str or "quota" in err_str.lower():
                    self.key_pool.report_error(current_key, 429)
                elif "403" in err_str or "invalid" in err_str.lower():
                    self.key_pool.report_error(current_key, 403)

                wait = 2 ** attempt
                logger.warning(
                    "Intento %d/%d fallido (%s). Esperando %ds...",
                    attempt + 1, retries, exc, wait,
                )
                time.sleep(wait)

        logger.error("Todos los reintentos agotados: %s", last_exc)
        return self._fallback_response()

    def _fallback_response(self) -> str:
        return (
            "El servicio de IA no está disponible en este momento. "
            "Por favor, verifica tu API key o intenta más tarde."
        )


# =============================================================================
# get_contextualized_chat_response — función standalone re-exportable
# =============================================================================

def get_contextualized_chat_response(
    manager: Any,
    context: str,
    question: str,
    history: Optional[List[Dict]] = None,
) -> str:
    """
    Genera una respuesta de chat educativo contextualizada.
    Compatible con AIManagerCore y con el AIManager original de utils_ai.py.
    """
    history_text = ""
    if history:
        lines = []
        for item in history[-5:]:  # máximo 5 turnos anteriores
            lines.append(f"Estudiante: {item.get('message', '')}")
            lines.append(f"Asistente: {item.get('response', '')}")
        history_text = "\n".join(lines)

    prompt = f"""Eres un tutor educativo experto. Responde la pregunta del estudiante
basándote únicamente en el contexto proporcionado. Si la respuesta no está en el
contexto, indícalo claramente. Responde en el idioma de la pregunta.

CONTEXTO:
{context[:8000]}

{"HISTORIAL RECIENTE:" + chr(10) + history_text if history_text else ""}

PREGUNTA DEL ESTUDIANTE:
{question}

RESPUESTA (clara, educativa y en formato Markdown si es conveniente):"""

    # Detectar tipo de manager y usar el método adecuado
    if hasattr(manager, "generate"):
        return manager.generate(prompt, max_tokens=1024)
    elif hasattr(manager, "generate_response"):
        return manager.generate_response(prompt)
    else:
        return "No se pudo generar una respuesta. El gestor de IA no está disponible."
