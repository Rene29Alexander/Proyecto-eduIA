"""
Modelos de datos para el sistema de Evaluación Directa Mejorada del Tutor IA.

Este módulo define las estructuras de datos utilizadas en el proceso de evaluación
de código, incluyendo detección de errores, resultados de evaluación, reglas de
validación por lenguaje y ajustes de consistencia.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional


@dataclass
class ErrorDetection:
    """
    Resultado de detección de errores en código.
    
    Attributes:
        errores: Lista de descripciones de errores encontrados
        severidad: Severidad acumulada (suma de severidades individuales)
        es_invalido: True si el código es completamente inválido
        razon_invalido: Razón por la que el código es inválido (si aplica)
    """
    errores: List[str] = field(default_factory=list)
    severidad: int = 0
    es_invalido: bool = False
    razon_invalido: str = ""


@dataclass
class EvaluationResult:
    """
    Resultado completo de evaluación de código.
    
    Attributes:
        score: Puntuación 0-10
        feedback: Retroalimentación detallada
        correctness: Estado de corrección ("correcto", "parcial", "incorrecto")
        suggestions: Lista de sugerencias de mejora
        concepts: Lista de conceptos relevantes evaluados
        errores_detectados: Errores encontrados manualmente
        score_ajustado: True si Validador_Consistencia ajustó el score
        razon_ajuste: Razón del ajuste (si aplica)
    """
    score: int
    feedback: str
    correctness: str = "incorrecto"
    suggestions: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    errores_detectados: List[str] = field(default_factory=list)
    score_ajustado: bool = False
    razon_ajuste: str = ""


@dataclass
class SyntaxRule:
    """
    Regla de sintaxis individual para validación de código.
    
    Attributes:
        patron: Patrón regex o string a buscar
        descripcion_error: Descripción del error si se encuentra
        severidad: Severidad del error (1-4)
        sugerencia: Sugerencia de corrección
    """
    patron: str
    descripcion_error: str
    severidad: int
    sugerencia: str


@dataclass
class LogicRule:
    """
    Regla de lógica individual para validación de código.
    
    Attributes:
        condicion: Función que evalúa si hay error
        descripcion_error: Descripción del error
        severidad: Severidad del error (1-4)
        sugerencia: Sugerencia de corrección
    """
    condicion: Callable[[str], bool]
    descripcion_error: str
    severidad: int
    sugerencia: str


@dataclass
class LanguageRules:
    """
    Reglas de validación específicas por lenguaje de programación.
    
    Attributes:
        nombre: Nombre del lenguaje ("Python", "SQL", "NoSQL", etc.)
        reglas_sintaxis: Lista de reglas de sintaxis
        reglas_logica: Lista de reglas de lógica
        keywords_invalidos: Keywords que indican mezcla de lenguajes
    """
    nombre: str
    reglas_sintaxis: List[SyntaxRule] = field(default_factory=list)
    reglas_logica: List[LogicRule] = field(default_factory=list)
    keywords_invalidos: List[str] = field(default_factory=list)


@dataclass
class ConsistencyAdjustment:
    """
    Registro de ajuste de consistencia entre score y feedback.
    
    Attributes:
        timestamp: Momento del ajuste
        language: Lenguaje del código evaluado
        score_original: Score antes del ajuste
        score_ajustado: Score después del ajuste
        razon: Razón del ajuste
        feedback_snippet: Primeros 200 caracteres del feedback
    """
    timestamp: datetime
    language: str
    score_original: int
    score_ajustado: int
    razon: str
    feedback_snippet: str
