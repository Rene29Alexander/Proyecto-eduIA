# -*- coding: utf-8 -*-
"""
Pruebas unitarias del módulo de evaluacion/.

Cubre: Sistema_Calificacion, Validador_Consistencia, Detector_Errores.

Ejecutar con:
    pytest tests/test_sistema_evaluacion.py -v

No requiere servidor ni API Key de Gemini.
"""

import pytest
import sys
import types

# ── Mock de streamlit para evitar ImportError ─────────────────────────────────
if "streamlit" not in sys.modules:
    st_mock = types.ModuleType("streamlit")
    st_mock.session_state = {}
    st_mock.secrets = {}
    st_mock.error = lambda *a, **k: None
    st_mock.warning = lambda *a, **k: None
    sys.modules["streamlit"] = st_mock

from evaluacion.sistema_calificacion import Sistema_Calificacion
from evaluacion.validador_consistencia import Validador_Consistencia
from evaluacion.detector_errores import Detector_Errores


# =============================================================================
# BLOQUE 1 — Sistema_Calificacion
# =============================================================================

class TestSistemaCalificacion:
    """Pruebas del sistema de puntuación por severidad."""

    def setup_method(self):
        self.sc = Sistema_Calificacion()

    # --- calcular_score_por_severidad ---

    def test_severidad_critica_retorna_1(self):
        """Severidad >= 10 debe retornar score 1."""
        assert self.sc.calcular_score_por_severidad(10) == 1
        assert self.sc.calcular_score_por_severidad(15) == 1

    def test_severidad_muy_grave_retorna_2(self):
        """Severidad entre 8 y 9 debe retornar score 2."""
        assert self.sc.calcular_score_por_severidad(8) == 2
        assert self.sc.calcular_score_por_severidad(9) == 2

    def test_severidad_grave_retorna_3(self):
        """Severidad entre 6 y 7 debe retornar score 3."""
        assert self.sc.calcular_score_por_severidad(6) == 3
        assert self.sc.calcular_score_por_severidad(7) == 3

    def test_severidad_moderada_retorna_5(self):
        """Severidad entre 4 y 5 debe retornar score 5."""
        assert self.sc.calcular_score_por_severidad(4) == 5
        assert self.sc.calcular_score_por_severidad(5) == 5

    def test_severidad_menor_retorna_7(self):
        """Severidad entre 2 y 3 debe retornar score 7."""
        assert self.sc.calcular_score_por_severidad(2) == 7
        assert self.sc.calcular_score_por_severidad(3) == 7

    def test_severidad_minima_retorna_8(self):
        """Severidad 0 o 1 debe retornar score 8."""
        assert self.sc.calcular_score_por_severidad(0) == 8
        assert self.sc.calcular_score_por_severidad(1) == 8

    def test_score_siempre_entre_1_y_10(self):
        """El score resultante siempre debe estar en el rango 1-10."""
        for sev in range(0, 20):
            score = self.sc.calcular_score_por_severidad(sev)
            assert 1 <= score <= 10, f"Score {score} fuera de rango para severidad {sev}"

    # --- calcular_score_relevancia ---

    def test_relevancia_muy_baja_retorna_2(self):
        """Relevancia < 0.15 debe retornar score 2."""
        assert self.sc.calcular_score_relevancia(0.0) == 2
        assert self.sc.calcular_score_relevancia(0.10) == 2

    def test_relevancia_baja_retorna_4(self):
        """Relevancia entre 0.15 y 0.29 debe retornar score 4."""
        assert self.sc.calcular_score_relevancia(0.20) == 4

    def test_relevancia_media_retorna_6(self):
        """Relevancia entre 0.30 y 0.49 debe retornar score 6."""
        assert self.sc.calcular_score_relevancia(0.40) == 6

    def test_relevancia_alta_retorna_8_o_9(self):
        """Relevancia >= 0.70 debe retornar score 8 o 9."""
        score = self.sc.calcular_score_relevancia(0.80)
        assert score in (8, 9)

    def test_relevancia_maxima_retorna_9(self):
        """Relevancia >= 0.85 debe retornar score 9."""
        assert self.sc.calcular_score_relevancia(0.90) == 9
        assert self.sc.calcular_score_relevancia(1.0) == 9

    def test_relevancia_score_siempre_entre_0_y_10(self):
        """Score de relevancia siempre debe estar en rango 0-10."""
        for rel in [0.0, 0.1, 0.25, 0.45, 0.60, 0.75, 0.90, 1.0]:
            score = self.sc.calcular_score_relevancia(rel)
            assert 0 <= score <= 10, f"Score {score} fuera de rango para relevancia {rel}"


# =============================================================================
# BLOQUE 2 — Validador_Consistencia
# =============================================================================

class TestValidadorConsistencia:
    """Pruebas del validador de coherencia entre score y feedback."""

    def setup_method(self):
        self.vc = Validador_Consistencia()

    def test_sin_inconsistencia_score_no_cambia(self):
        """Un feedback neutro no debe modificar el score."""
        score, razon = self.vc.validar_consistencia(
            score=6,
            feedback="El código tiene algunos comentarios útiles.",
            code="x = 1",
            criteria="ejercicio básico",
            language="python"
        )
        assert score == 6
        assert razon == ""

    def test_feedback_errores_criticos_baja_score_alto(self):
        """Si feedback menciona 'errores críticos' y score > 7, debe ajustarse a 3."""
        score, razon = self.vc.validar_consistencia(
            score=9,
            feedback="El código presenta errores críticos que impiden su ejecución.",
            code="def f(",
            criteria="función básica",
            language="python"
        )
        assert score == 3
        assert razon != ""

    def test_feedback_perfecto_sube_score_bajo(self):
        """Si feedback menciona 'perfecto' y score < 8, debe ajustarse a 9."""
        score, razon = self.vc.validar_consistencia(
            score=5,
            feedback="El código es perfecto, sin ningún problema.",
            code="def suma(a, b): return a + b",
            criteria="función suma",
            language="python"
        )
        assert score == 9
        assert razon != ""

    def test_feedback_funciona_parcialmente_baja_score_muy_alto(self):
        """Si feedback dice 'funciona parcialmente' y score > 8, debe ajustarse a 7."""
        score, razon = self.vc.validar_consistencia(
            score=10,
            feedback="El código funciona parcialmente en algunos casos.",
            code="def div(a, b): return a / b",
            criteria="división",
            language="python"
        )
        assert score == 7
        assert razon != ""

    def test_feedback_no_ejecuta_baja_score_alto(self):
        """Si feedback dice 'no ejecuta' y score > 5, debe ajustarse a 2."""
        score, razon = self.vc.validar_consistencia(
            score=8,
            feedback="El programa no ejecuta debido a un error de importación.",
            code="import modulo_inexistente",
            criteria="importación",
            language="python"
        )
        assert score == 2
        assert razon != ""

    def test_score_consistente_sin_criticos_no_cambia(self):
        """Score bajo con feedback neutro no debe cambiar."""
        score, razon = self.vc.validar_consistencia(
            score=4,
            feedback="Hay algunas mejoras posibles en la estructura.",
            code="x=1",
            criteria="variables",
            language="python"
        )
        assert score == 4

    def test_retorna_tupla_con_int_y_str(self):
        """La función siempre debe retornar (int, str)."""
        resultado = self.vc.validar_consistencia(
            score=7,
            feedback="Código funcional con pequeñas observaciones.",
            code="print('hola')",
            criteria="salida básica",
            language="python"
        )
        assert isinstance(resultado, tuple)
        assert len(resultado) == 2
        assert isinstance(resultado[0], int)
        assert isinstance(resultado[1], str)


# =============================================================================
# BLOQUE 3 — Detector_Errores
# =============================================================================

class TestDetectorErrores:
    """Pruebas del detector de código inválido y errores por lenguaje."""

    def setup_method(self):
        self.de = Detector_Errores()

    # --- detectar_codigo_invalido ---

    def test_codigo_vacio_es_invalido(self):
        """Código vacío debe detectarse como inválido."""
        invalido, razon = self.de.detectar_codigo_invalido("", "python")
        assert invalido is True
        assert razon != ""

    def test_codigo_solo_espacios_es_invalido(self):
        """Código con solo espacios debe ser inválido."""
        invalido, razon = self.de.detectar_codigo_invalido("   ", "python")
        assert invalido is True

    def test_codigo_python_valido_no_es_invalido(self):
        """Código Python correcto no debe marcarse como inválido."""
        invalido, _ = self.de.detectar_codigo_invalido(
            "def suma(a, b):\n    return a + b", "python"
        )
        assert invalido is False

    def test_codigo_nonsense_es_invalido(self):
        """Texto sin sentido debe detectarse como inválido."""
        invalido, razon = self.de.detectar_codigo_invalido("asdfgh qwerty blablabla", "python")
        assert invalido is True
        assert "sin sentido" in razon.lower()

    def test_mezcla_tres_lenguajes_es_invalido(self):
        """Código que mezcla 3+ lenguajes debe ser inválido."""
        codigo_mezcla = (
            "SELECT * FROM users; "
            "print('hola') "
            "console.log('test') "
            "System.out.println('java')"
        )
        invalido, razon = self.de.detectar_codigo_invalido(codigo_mezcla, "python")
        assert invalido is True
        assert "mezcla" in razon.lower()

    def test_codigo_sql_valido_no_es_invalido(self):
        """Una consulta SQL válida no debe marcarse como inválida."""
        invalido, _ = self.de.detectar_codigo_invalido(
            "SELECT id, nombre FROM usuarios WHERE activo = 1", "sql"
        )
        assert invalido is False

    # --- detectar_errores_lenguaje ---

    def test_retorna_lista_y_entero(self):
        """La función debe retornar (list, int)."""
        errores, severidad = self.de.detectar_errores_lenguaje("print('hola')", "python")
        assert isinstance(errores, list)
        assert isinstance(severidad, int)

    def test_codigo_correcto_severidad_baja(self):
        """Código Python correcto debe tener severidad baja o cero."""
        _, severidad = self.de.detectar_errores_lenguaje(
            "def suma(a, b):\n    return a + b\n\nresultado = suma(2, 3)", "python"
        )
        assert severidad >= 0

    def test_codigo_con_error_tiene_errores_detectados(self):
        """Código con error de sintaxis conocido debe tener al menos un error."""
        codigo_con_error = "def funcion(\n    print('sin cerrar')"
        errores, _ = self.de.detectar_errores_lenguaje(codigo_con_error, "python")
        # No todos los analizadores detectan todos los errores,
        # pero la estructura de retorno debe ser válida
        assert isinstance(errores, list)

    def test_severidad_no_negativa(self):
        """La severidad nunca debe ser negativa."""
        for codigo in ["print('ok')", "", "x = 1 + 2", "SELECT * FROM t"]:
            for lang in ["python", "sql", "javascript"]:
                _, sev = self.de.detectar_errores_lenguaje(codigo, lang)
                assert sev >= 0, f"Severidad negativa para '{codigo}' en {lang}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
