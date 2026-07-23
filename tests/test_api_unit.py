# -*- coding: utf-8 -*-
"""
Pruebas unitarias de la API EduIA — sin servidor externo.
Usa TestClient de FastAPI (httpx) para probar endpoints directamente.

Ejecutar con:
    pytest tests/test_api_unit.py -v

No requiere que la API esté corriendo ni una API Key real.
"""

import pytest
from fastapi.testclient import TestClient

# ── Parchear AIManager ANTES de importar api.py ──────────────────────────────
# Esto evita que se intente conectar a Gemini durante los tests
import sys
import types

# Crear módulo falso de streamlit para evitar ImportError
if "streamlit" not in sys.modules:
    st_mock = types.ModuleType("streamlit")
    st_mock.session_state = {}
    st_mock.secrets = {}
    st_mock.error = lambda *a, **k: None
    st_mock.warning = lambda *a, **k: None
    sys.modules["streamlit"] = st_mock

from api import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# =============================================================================
# BLOQUE 1 — Endpoints de sistema
# =============================================================================

class TestHealth:
    """Pruebas del endpoint GET /health."""

    def test_health_retorna_200(self):
        """El endpoint /health debe retornar HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_contiene_status_ok(self):
        """El cuerpo debe incluir status='ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_contiene_campo_database(self):
        """El cuerpo debe incluir el campo 'database'."""
        response = client.get("/health")
        data = response.json()
        assert "database" in data
        assert data["database"] in ("connected", "unreachable")

    def test_health_contiene_timestamp(self):
        """El cuerpo debe incluir el campo 'timestamp'."""
        response = client.get("/health")
        data = response.json()
        assert "timestamp" in data
        assert len(data["timestamp"]) > 0


class TestMetadata:
    """Pruebas del endpoint GET /metadata."""

    def test_metadata_retorna_200(self):
        """El endpoint /metadata debe retornar HTTP 200."""
        response = client.get("/metadata")
        assert response.status_code == 200

    def test_metadata_version_correcta(self):
        """La versión debe ser 1.0.0."""
        response = client.get("/metadata")
        data = response.json()
        assert data["version"] == "1.0.0"

    def test_metadata_contiene_tecnologias(self):
        """Debe incluir la lista de tecnologías."""
        response = client.get("/metadata")
        data = response.json()
        assert "technologies" in data
        assert "FastAPI" in data["technologies"]
        assert "Google Gemini AI" in data["technologies"]

    def test_metadata_contiene_lenguajes(self):
        """Debe incluir la lista de lenguajes soportados."""
        response = client.get("/metadata")
        data = response.json()
        assert "supported_languages" in data
        assert "python" in data["supported_languages"]


# =============================================================================
# BLOQUE 2 — Validaciones de entrada en /api/evaluate
# =============================================================================

class TestEvaluateValidaciones:
    """Pruebas de validación del endpoint POST /api/evaluate."""

    def test_evaluate_sin_code_retorna_422(self):
        """Sin campo 'code' debe retornar 422."""
        response = client.post("/api/evaluate", json={"language": "python"})
        assert response.status_code == 422

    def test_evaluate_sin_language_retorna_422(self):
        """Sin campo 'language' debe retornar 422."""
        response = client.post("/api/evaluate", json={"code": "print('hola')"})
        assert response.status_code == 422

    def test_evaluate_language_no_soportado_retorna_422(self):
        """Lenguaje no soportado debe retornar 422."""
        response = client.post("/api/evaluate", json={
            "code": "PROGRAM Hello; BEGIN END.",
            "language": "pascal"
        })
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("pascal" in str(e).lower() for e in detail)

    def test_evaluate_code_solo_espacios_retorna_422(self):
        """Código con solo espacios debe retornar 422."""
        response = client.post("/api/evaluate", json={
            "code": "     ",
            "language": "python"
        })
        assert response.status_code == 422

    def test_evaluate_language_case_insensitive(self):
        """El lenguaje debe aceptarse en mayúsculas o minúsculas."""
        # "PYTHON" debe normalizarse a "python" — si Gemini no está disponible
        # retorna 503 pero el lenguaje pasó la validación (no 422)
        response = client.post("/api/evaluate", json={
            "code": "def f(): pass",
            "language": "PYTHON"
        })
        # 422 sería fallo de validación — no debe ocurrir
        assert response.status_code != 422

    def test_evaluate_payload_vacio_retorna_422(self):
        """Payload completamente vacío debe retornar 422."""
        response = client.post("/api/evaluate", json={})
        assert response.status_code == 422

    def test_evaluate_lenguajes_validos_no_dan_422(self):
        """Todos los lenguajes de la lista soportada deben pasar validación."""
        lenguajes = ["python", "javascript", "java", "sql", "nosql",
                     "c", "c++", "typescript", "html", "css"]
        for lang in lenguajes:
            response = client.post("/api/evaluate", json={
                "code": "codigo de prueba valido",
                "language": lang
            })
            # Solo verificamos que no sea error de validación (422)
            assert response.status_code != 422, \
                f"Lenguaje '{lang}' fue rechazado con 422 incorrectamente"


# =============================================================================
# BLOQUE 3 — Validaciones de entrada en /api/courses/generate
# =============================================================================

class TestCoursesValidaciones:
    """Pruebas de validación del endpoint POST /api/courses/generate."""

    def test_courses_sin_language_retorna_422(self):
        """Sin 'language' debe retornar 422."""
        response = client.post("/api/courses/generate", json={"level": "principiante"})
        assert response.status_code == 422

    def test_courses_sin_level_retorna_422(self):
        """Sin 'level' debe retornar 422."""
        response = client.post("/api/courses/generate", json={"language": "python"})
        assert response.status_code == 422

    def test_courses_level_invalido_retorna_422(self):
        """Nivel no válido debe retornar 422."""
        response = client.post("/api/courses/generate", json={
            "language": "python",
            "level": "experto"
        })
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("experto" in str(e).lower() for e in detail)

    def test_courses_sections_count_cero_retorna_422(self):
        """sections_count=0 debe retornar 422."""
        response = client.post("/api/courses/generate", json={
            "language": "python",
            "level": "principiante",
            "sections_count": 0
        })
        assert response.status_code == 422

    def test_courses_sections_count_sobre_limite_retorna_422(self):
        """sections_count=11 debe retornar 422."""
        response = client.post("/api/courses/generate", json={
            "language": "python",
            "level": "principiante",
            "sections_count": 11
        })
        assert response.status_code == 422

    def test_courses_niveles_validos_no_dan_422(self):
        """Los tres niveles válidos deben pasar la validación."""
        for nivel in ["principiante", "intermedio", "avanzado"]:
            response = client.post("/api/courses/generate", json={
                "language": "python",
                "level": nivel
            })
            assert response.status_code != 422, \
                f"Nivel '{nivel}' fue rechazado con 422 incorrectamente"


# =============================================================================
# BLOQUE 4 — Validaciones de entrada en /api/chat/ask
# =============================================================================

class TestChatValidaciones:
    """Pruebas de validación del endpoint POST /api/chat/ask."""

    CONTEXTO_VALIDO = (
        "Python es un lenguaje interpretado de alto nivel creado por Guido van Rossum. "
        "Sus estructuras principales son: variables, listas, tuplas, diccionarios y funciones. "
        "Es ampliamente usado en ciencia de datos, desarrollo web e inteligencia artificial."
    )

    def test_chat_sin_context_retorna_422(self):
        """Sin 'context' debe retornar 422."""
        response = client.post("/api/chat/ask", json={
            "question": "¿Qué es Python?"
        })
        assert response.status_code == 422

    def test_chat_sin_question_retorna_422(self):
        """Sin 'question' debe retornar 422."""
        response = client.post("/api/chat/ask", json={
            "context": self.CONTEXTO_VALIDO
        })
        assert response.status_code == 422

    def test_chat_context_corto_retorna_422(self):
        """Contexto menor a 50 caracteres debe retornar 422."""
        response = client.post("/api/chat/ask", json={
            "context": "Hola",
            "question": "¿Qué es Python?"
        })
        assert response.status_code == 422

    def test_chat_question_vacia_retorna_422(self):
        """Pregunta vacía debe retornar 422."""
        response = client.post("/api/chat/ask", json={
            "context": self.CONTEXTO_VALIDO,
            "question": "   "
        })
        assert response.status_code == 422

    def test_chat_payload_valido_no_da_422(self):
        """Payload válido no debe retornar 422 (puede retornar 503 si no hay Gemini)."""
        response = client.post("/api/chat/ask", json={
            "context": self.CONTEXTO_VALIDO,
            "question": "¿Qué es una lista?"
        })
        assert response.status_code != 422


# =============================================================================
# BLOQUE 5 — Esquema de respuesta
# =============================================================================

class TestEsquemaRespuesta:
    """Pruebas de que los errores 422 tienen estructura estándar de FastAPI."""

    def test_error_422_tiene_campo_detail(self):
        """Los errores de validación deben tener campo 'detail'."""
        response = client.post("/api/evaluate", json={})
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_error_422_detail_es_lista(self):
        """El campo 'detail' debe ser una lista."""
        response = client.post("/api/evaluate", json={})
        data = response.json()
        assert isinstance(data["detail"], list)

    def test_error_422_detail_contiene_loc(self):
        """Cada error de validación debe indicar la ubicación del campo."""
        response = client.post("/api/evaluate", json={"language": "python"})
        data = response.json()
        assert any("loc" in err for err in data["detail"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
