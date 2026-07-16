# -*- coding: utf-8 -*-
"""
API RESTful — EduIA Plataforma Educativa
Semana 2: Exposición completa de capacidades inteligentes vía FastAPI

Levantar con:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

Swagger UI:  http://127.0.0.1:8000/docs
ReDoc:       http://127.0.0.1:8000/redoc
"""

import os
import sqlite3
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# ── Configuración propia (sin importar Streamlit) ────────────────────────────
from config import DB_PATH, AI_CONFIG, DEBUG

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eduia.api")

# ── Constantes ────────────────────────────────────────────────────────────────
SUPPORTED_LANGUAGES: List[str] = [
    "python", "javascript", "java", "sql", "nosql",
    "c", "c++", "typescript", "html", "css",
]

SUPPORTED_LEVELS: List[str] = ["principiante", "intermedio", "avanzado"]

# =============================================================================
# Aplicación FastAPI
# =============================================================================

app = FastAPI(
    title="EduIA — API de Capacidades Inteligentes",
    description=(
        "API RESTful que expone **todas** las capacidades de IA de la plataforma "
        "educativa EduIA:\n\n"
        "- 🧠 **Evaluación de código** con análisis estático + Google Gemini\n"
        "- 📚 **Generación de cursos** personalizados por lenguaje y nivel\n"
        "- 💬 **Chat educativo** contextualizado por material del módulo\n"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "Grupo 2 — EduIA", "email": "admin@plataforma.edu"},
)

# =============================================================================
# Manejador global — evita exponer stacktraces al cliente
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Error interno no controlado:\n%s", traceback.format_exc())
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Error interno del servidor. Por favor inténtalo de nuevo más tarde.",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

# =============================================================================
# ── Helpers internos ─────────────────────────────────────────────────────────
# =============================================================================

def _get_api_key() -> str:
    """
    Obtiene la API Key de Gemini en orden de prioridad:
      1. Variable de entorno GEMINI_API_KEY
      2. Registro en system_settings de la BD (configurado por el admin)
    Nunca escribe credenciales en el código fuente.
    """
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            row = conn.execute(
                "SELECT value FROM system_settings WHERE key = 'gemini_api_key'"
            ).fetchone()
            conn.close()
            if row and row[0]:
                key = row[0].strip()
        except Exception:
            pass
    return key


def _check_db() -> bool:
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception as exc:
        logger.warning("Fallo verificación BD: %s", exc)
        return False


def _build_ai_manager():
    """
    Instancia AIManager sin Streamlit.
    Retorna (manager, error_msg|None).
    """
    api_key = _get_api_key()
    if not api_key:
        return None, "GEMINI_API_KEY no configurada. Define la variable de entorno o regístrala en la configuración del sistema."
    try:
        from utils_ai import AIManager           # importación diferida para no activar Streamlit
        manager = AIManager(api_key=api_key)
        if not manager.model:
            return None, "No se pudo inicializar ningún modelo de Gemini con la clave provista."
        return manager, None
    except Exception as exc:
        logger.error("Error instanciando AIManager: %s", exc)
        return None, str(exc)


def _raise_gemini_unavailable(reason: str = "") -> None:
    """Lanza 503 con mensaje limpio cuando Gemini no está disponible."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "Servicio de IA (Gemini) no disponible.",
            "reason": reason or "No se pudo conectar con el servicio.",
            "suggestion": (
                "Verifica que GEMINI_API_KEY esté configurada correctamente "
                "y que tengas cuota disponible en Google AI Studio."
            ),
        },
    )


def _classify_ai_error(exc: Exception) -> None:
    """Clasifica errores de Gemini y lanza el código HTTP adecuado."""
    err = str(exc).lower()
    quota_keywords = ["quota", "429", "resource_exhausted", "rate_limit"]
    auth_keywords  = ["unauthorized", "403", "invalid api key", "api_key_invalid"]
    conn_keywords  = ["connection", "network", "timeout", "unavailable", "deadline"]

    if any(k in err for k in quota_keywords):
        _raise_gemini_unavailable("Cuota de la API agotada. Espera unos minutos e inténtalo de nuevo.")
    if any(k in err for k in auth_keywords):
        _raise_gemini_unavailable("API Key inválida o sin permisos. Verifica tu configuración.")
    if any(k in err for k in conn_keywords):
        _raise_gemini_unavailable("Error de red hacia Gemini. Verifica tu conexión a internet.")

    logger.error("Error inesperado en llamada a IA: %s", traceback.format_exc())
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Error interno al procesar la solicitud de IA.",
    )

# =============================================================================
# ── Modelos Pydantic ─────────────────────────────────────────────────────────
# =============================================================================

# ── /api/evaluate ─────────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        max_length=20_000,
        description="Código fuente del estudiante a evaluar.",
        examples=["def suma(a, b):\n    return a + b"],
    )
    language: str = Field(
        ...,
        description=f"Lenguaje de programación. Valores aceptados: {', '.join(SUPPORTED_LANGUAGES)}",
        examples=["python"],
    )
    criteria: Optional[str] = Field(
        default="Evalúa el código según buenas prácticas y corrección.",
        max_length=2_000,
        description="Descripción del ejercicio o criterios de evaluación.",
        examples=["Implementa una función que sume dos números enteros."],
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        n = v.strip().lower()
        if n not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Lenguaje '{v}' no soportado. "
                f"Opciones válidas: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        return n

    @field_validator("code")
    @classmethod
    def validate_code_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El campo 'code' no puede contener sólo espacios en blanco.")
        return v


class EvaluateResponse(BaseModel):
    score: int               = Field(..., ge=0, le=10, description="Puntuación 0–10.")
    correctness: str         = Field(..., description="'correcto', 'parcial' o 'incorrecto'.")
    feedback: str            = Field(..., description="Retroalimentación detallada generada por IA.")
    suggestions: List[str]   = Field(default_factory=list, description="Sugerencias de mejora.")
    concepts: List[str]      = Field(default_factory=list, description="Conceptos evaluados.")
    errors_detected: List[str] = Field(default_factory=list, description="Errores de análisis estático.")
    score_adjusted: bool     = Field(default=False, description="True si el validador ajustó el score.")
    adjustment_reason: str   = Field(default="",   description="Razón del ajuste.")
    language: str            = Field(..., description="Lenguaje evaluado (normalizado).")
    evaluated_at: str        = Field(..., description="Timestamp ISO-8601 UTC.")
    ai_available: bool       = Field(..., description="Indica si Gemini estuvo disponible.")


# ── /api/courses/generate ─────────────────────────────────────────────────────

class CourseGenerateRequest(BaseModel):
    language: str = Field(
        ...,
        description=f"Lenguaje de programación del curso. Valores aceptados: {', '.join(SUPPORTED_LANGUAGES)}",
        examples=["python"],
    )
    level: str = Field(
        ...,
        description=f"Nivel del estudiante. Valores aceptados: {', '.join(SUPPORTED_LEVELS)}",
        examples=["principiante"],
    )
    sections_count: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Número de temas/secciones del curso (1–10).",
        examples=[5],
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        n = v.strip().lower()
        if n not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Lenguaje '{v}' no soportado. "
                f"Opciones válidas: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        return n

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        n = v.strip().lower()
        if n not in SUPPORTED_LEVELS:
            raise ValueError(
                f"Nivel '{v}' no soportado. "
                f"Opciones válidas: {', '.join(SUPPORTED_LEVELS)}"
            )
        return n


class CourseTopic(BaseModel):
    topic_number: int
    title: str
    description: str
    objectives: str
    estimated_hours: int
    order_index: int


class CourseGenerateResponse(BaseModel):
    language: str              = Field(..., description="Lenguaje del curso (normalizado).")
    level: str                 = Field(..., description="Nivel del curso.")
    sections_count: int        = Field(..., description="Número de secciones solicitadas.")
    topics: List[Dict[str, Any]] = Field(..., description="Lista de temas generados.")
    generated_at: str          = Field(..., description="Timestamp ISO-8601 UTC.")
    ai_available: bool         = Field(..., description="Indica si Gemini mejoró el contenido.")


# ── /api/chat/ask ─────────────────────────────────────────────────────────────

class ChatHistoryItem(BaseModel):
    message: str  = Field(..., description="Pregunta anterior del estudiante.")
    response: str = Field(..., description="Respuesta anterior del asistente.")


class ChatAskRequest(BaseModel):
    context: str = Field(
        ...,
        min_length=50,
        max_length=500_000,
        description="Texto del material/módulo que sirve como contexto para la IA.",
        examples=[
            "Python es un lenguaje interpretado de alto nivel. "
            "Sus estructuras principales son: variables, tipos de datos, "
            "estructuras de control (if, elif, else), ciclos (for y while), "
            "funciones y estructuras de datos (listas, tuplas, diccionarios y conjuntos)."
        ],
    )
    question: str = Field(
        ...,
        min_length=1,
        max_length=1_000,
        description="Pregunta del estudiante.",
        examples=["¿Qué es una lista en Python?"],
    )
    history: Optional[List[ChatHistoryItem]] = Field(
        default=None,
        max_length=10,
        description="Historial reciente de la conversación (máx. 10 turnos).",
    )

    @field_validator("question")
    @classmethod
    def validate_question_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El campo 'question' no puede estar vacío.")
        return v.strip()

    @field_validator("context")
    @classmethod
    def validate_context_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El campo 'context' no puede estar vacío.")
        return v


class ChatAskResponse(BaseModel):
    response: str      = Field(..., description="Respuesta del asistente IA en formato Markdown.")
    question: str      = Field(..., description="Pregunta original recibida.")
    answered_at: str   = Field(..., description="Timestamp ISO-8601 UTC.")
    ai_available: bool = Field(..., description="Indica si Gemini estuvo disponible.")


# =============================================================================
# ── Endpoints de sistema ─────────────────────────────────────────────────────
# =============================================================================

@app.get(
    "/health",
    summary="Verificación de salud del servicio",
    tags=["Sistema"],
    responses={200: {"description": "Servicio activo."}},
)
async def health_check():
    """
    Verifica que el servicio está activo y que la base de datos SQLite es accesible.
    """
    db_ok = _check_db()
    return {
        "status": "ok",
        "database": "connected" if db_ok else "unreachable",
        "database_path": str(DB_PATH),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get(
    "/metadata",
    summary="Metadatos del servicio",
    tags=["Sistema"],
)
async def metadata():
    """
    Retorna información descriptiva del servicio: propósito, versión,
    tecnologías y capacidades disponibles.
    """
    return {
        "service": "EduIA — API de Capacidades Inteligentes",
        "version": "1.0.0",
        "purpose": (
            "Exponer las capacidades de IA de la plataforma educativa EduIA: "
            "evaluación de código, generación de cursos y chat educativo contextualizado."
        ),
        "technologies": ["FastAPI", "SQLite", "Google Gemini AI", "Pydantic v2", "Python 3.11+"],
        "ai_endpoints": [
            "POST /api/evaluate         — Evaluación inteligente de código",
            "POST /api/courses/generate — Generación de estructura de curso",
            "POST /api/chat/ask         — Chat educativo por contexto",
        ],
        "supported_languages": SUPPORTED_LANGUAGES,
        "supported_levels": SUPPORTED_LEVELS,
        "docs_url": "/docs",
        "timestamp": datetime.utcnow().isoformat(),
    }


# =============================================================================
# ── Endpoints inteligentes ───────────────────────────────────────────────────
# =============================================================================

# ── POST /api/evaluate ────────────────────────────────────────────────────────

@app.post(
    "/api/evaluate",
    response_model=EvaluateResponse,
    status_code=status.HTTP_200_OK,
    summary="Evalúa código de un estudiante con IA",
    tags=["IA — Evaluación"],
    responses={
        422: {"description": "Payload inválido (campo faltante o lenguaje no soportado)."},
        503: {"description": "Servicio de Gemini AI no disponible."},
        500: {"description": "Error interno del servidor."},
    },
)
async def evaluate_code(payload: EvaluateRequest):
    """
    **Motor de evaluación inteligente** — orquestado por `evaluacion/evaluador_integrado.py`.

    Ejecuta un pipeline de 5 fases:
    1. Validación de relevancia (IA)
    2. Detección de código inválido
    3. Análisis estático de errores por lenguaje
    4. Evaluación profunda con Gemini
    5. Validación de consistencia score ↔ feedback

    ### Validaciones de entrada
    | Campo | Regla | Error |
    |---|---|---|
    | `code` | No vacío, máx. 20 000 chars | 422 |
    | `language` | Valor en lista soportada | 422 |
    | Gemini no disponible | — | 503 |
    """
    logger.info("evaluate_code — language=%s len=%d", payload.language, len(payload.code))

    # Inicializar AIManager
    ai_manager, ai_error = _build_ai_manager()
    if ai_error and "no configurada" in ai_error.lower():
        _raise_gemini_unavailable(ai_error)

    # Instanciar evaluador
    try:
        from evaluacion.evaluador_integrado import Evaluador_Integrado
        evaluador = Evaluador_Integrado(ai_manager=ai_manager)
    except Exception as exc:
        logger.error("Error instanciando Evaluador_Integrado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al inicializar el evaluador de código.",
        )

    # Ejecutar evaluación
    try:
        result = evaluador.evaluar_codigo(
            code=payload.code,
            criteria=payload.criteria or "",
            language=payload.language.capitalize(),   # "python" → "Python"
        )
    except Exception as exc:
        _classify_ai_error(exc)

    return EvaluateResponse(
        score=result.score,
        correctness=result.correctness,
        feedback=result.feedback,
        suggestions=result.suggestions,
        concepts=result.concepts,
        errors_detected=result.errores_detectados,
        score_adjusted=result.score_ajustado,
        adjustment_reason=result.razon_ajuste,
        language=payload.language,
        evaluated_at=datetime.utcnow().isoformat(),
        ai_available=(ai_manager is not None),
    )


# ── POST /api/courses/generate ────────────────────────────────────────────────

@app.post(
    "/api/courses/generate",
    response_model=CourseGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Genera la estructura de un curso personalizado con IA",
    tags=["IA — Cursos"],
    responses={
        422: {"description": "Lenguaje, nivel o sections_count inválidos."},
        503: {"description": "Servicio de Gemini AI no disponible."},
        500: {"description": "Error interno del servidor."},
    },
)
async def generate_course(payload: CourseGenerateRequest):
    """
    **Generador de cursos personalizados** — usa `AIManager.generate_course_topics_structure`
    de `utils_ai.py`.

    Genera una estructura de N temas adaptada al lenguaje y nivel del estudiante.
    Si Gemini está disponible, enriquece descripciones y objetivos con IA;
    si no, retorna la estructura predefinida de calidad garantizada.

    ### Validaciones de entrada
    | Campo | Regla | Error |
    |---|---|---|
    | `language` | Valor en lista soportada | 422 |
    | `level` | principiante / intermedio / avanzado | 422 |
    | `sections_count` | Entre 1 y 10 | 422 |
    """
    logger.info(
        "generate_course — language=%s level=%s sections=%d",
        payload.language, payload.level, payload.sections_count,
    )

    # Inicializar AIManager (puede funcionar sin IA con estructura predefinida)
    ai_manager, ai_error = _build_ai_manager()

    # Llamar directamente al método del AIManager
    try:
        if ai_manager:
            topics = ai_manager.generate_course_topics_structure(
                language=payload.language.capitalize(),
                level=payload.level,
                sections_count=payload.sections_count,
            )
        else:
            # Sin IA, importar solo para usar la lógica predefinida (sin llamadas Gemini)
            from utils_ai import AIManager
            dummy = AIManager.__new__(AIManager)
            dummy.model = None
            dummy.ai_manager = None
            topics = dummy.generate_course_topics_structure(
                language=payload.language.capitalize(),
                level=payload.level,
                sections_count=payload.sections_count,
            )
    except Exception as exc:
        _classify_ai_error(exc)

    if not topics:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar la estructura del curso.",
        )

    return CourseGenerateResponse(
        language=payload.language,
        level=payload.level,
        sections_count=payload.sections_count,
        topics=topics,
        generated_at=datetime.utcnow().isoformat(),
        ai_available=(ai_manager is not None),
    )


# ── POST /api/chat/ask ────────────────────────────────────────────────────────

@app.post(
    "/api/chat/ask",
    response_model=ChatAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Responde una pregunta del estudiante usando el contexto del módulo",
    tags=["IA — Chat Educativo"],
    responses={
        422: {"description": "Campos faltantes o inválidos."},
        503: {"description": "Servicio de Gemini AI no disponible."},
        500: {"description": "Error interno del servidor."},
    },
)
async def chat_ask(payload: ChatAskRequest):
    """
    **Chat educativo contextualizado** — usa `get_contextualized_chat_response`
    de `utils_ai.py`.

    Recibe el texto del material del módulo como contexto y responde la pregunta
    del estudiante **basándose exclusivamente en ese contenido**.
    Soporta historial de conversación (máx. 10 turnos anteriores).

    ### Validaciones de entrada
    | Campo | Regla | Error |
    |---|---|---|
    | `context` | Mín. 50 chars, máx. 500 000 | 422 |
    | `question` | No vacía, máx. 1 000 chars | 422 |
    | Gemini no disponible | — | 503 |
    """
    logger.info(
        "chat_ask — context_len=%d question_len=%d",
        len(payload.context), len(payload.question),
    )

    # Gemini es obligatorio para el chat
    ai_manager, ai_error = _build_ai_manager()
    if not ai_manager:
        _raise_gemini_unavailable(ai_error or "AIManager no inicializado.")

    # Convertir historial Pydantic → lista de dicts que espera la función
    history_dicts = None
    if payload.history:
        history_dicts = [
            {"message": h.message, "response": h.response}
            for h in payload.history
        ]

    # Llamar a la función de utils_ai.py directamente
    try:
        from utils_ai import get_contextualized_chat_response

        raw_response = get_contextualized_chat_response(
            model=ai_manager.model,            # GenerativeModel ya inicializado
            question=payload.question,
            context=payload.context,
            history=history_dicts,
            max_output_tokens=2_000,
        )
    except Exception as exc:
        _classify_ai_error(exc)

    # Detectar respuestas de error retornadas como string por la función interna
    if not raw_response or raw_response.startswith("Error al procesar"):
        _raise_gemini_unavailable("La IA no pudo procesar la pregunta.")

    return ChatAskResponse(
        response=raw_response,
        question=payload.question,
        answered_at=datetime.utcnow().isoformat(),
        ai_available=True,
    )
