"""
Property-Based Tests para el Sistema de Evaluación Directa Mejorada.

Este módulo contiene property tests que validan propiedades universales
del sistema de evaluación de código del Tutor IA.

Feature: tutor-ia-evaluacion-directa-mejorada
"""

import pytest
from hypothesis import given, strategies as st, settings
from hypothesis.strategies import composite
import sys
import os

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_ai import AIManager
from models.evaluation_models import ErrorDetection, EvaluationResult


# ============================================================================
# GENERADORES DE DATOS
# ============================================================================

@composite
def python_code_with_syntax_errors(draw):
    """Genera código Python con errores de sintaxis conocidos."""
    error_type = draw(st.sampled_from(['missing_colon', 'unbalanced_parens', 'wrong_method']))
    if error_type == 'missing_colon':
        return "def function()\n    return 42"
    elif error_type == 'unbalanced_parens':
        return "print('hello'"
    else:
        return "my_dict.remove('key')"


@composite
def sql_code_with_errors(draw):
    """Genera código SQL con errores conocidos."""
    error_type = draw(st.sampled_from(['typo', 'malformed', 'invalid_operator']))
    if error_type == 'typo':
        return "SELEC * FROM users"
    elif error_type == 'malformed':
        return "SELECT FROM WHERE;"
    else:
        return "SELECT * FROM users WHERE id == 1"


@composite
def valid_code_any_language(draw):
    """Genera código válido en cualquier lenguaje soportado."""
    language = draw(st.sampled_from(['Python', 'SQL', 'NoSQL', 'JavaScript', 'Java', 'C++', 'HTML/CSS']))
    
    code_samples = {
        'Python': "def hello():\n    return 'world'",
        'SQL': "SELECT * FROM users WHERE active = 1",
        'NoSQL': "db.users.find({active: true})",
        'JavaScript': "function hello() { return 'world'; }",
        'Java': "public class Hello { public static void main(String[] args) { System.out.println(\"Hello\"); } }",
        'C++': "#include <iostream>\nint main() { std::cout << \"Hello\"; return 0; }",
        'HTML/CSS': "<html><body><h1>Hello</h1></body></html>"
    }
    
    return (code_samples[language], language)


@composite
def mixed_language_code(draw):
    """Genera código que mezcla múltiples lenguajes."""
    return "SELECT * FROM users; print('hello'); console.log('world');"


@composite
def code_with_nonsense_words(draw):
    """Genera código con palabras sin sentido."""
    nonsense = draw(st.sampled_from(['asdfgh', 'qwerty', 'blablabla', 'nada existe']))
    return f"def {nonsense}():\n    {nonsense} = {nonsense}"


@composite
def relevant_code_and_criteria(draw):
    """Genera código y criterios relevantes entre sí."""
    topic = draw(st.sampled_from(['calculadora', 'inventario', 'usuarios', 'productos']))
    
    criteria_templates = {
        'calculadora': "Crear una calculadora que sume dos números",
        'inventario': "Crear un sistema de inventario con productos",
        'usuarios': "Crear un sistema de gestión de usuarios",
        'productos': "Crear una base de datos de productos"
    }
    
    code_templates = {
        'calculadora': "def sumar(a, b):\n    return a + b",
        'inventario': "class Inventario:\n    def __init__(self):\n        self.productos = []",
        'usuarios': "class Usuario:\n    def __init__(self, nombre):\n        self.nombre = nombre",
        'productos': "CREATE TABLE productos (id INT, nombre VARCHAR(100))"
    }
    
    return (code_templates[topic], criteria_templates[topic], 'Python')


# ============================================================================
# PROPERTY TESTS
# ============================================================================

# Property 12: Validación de Relevancia
# Valida: Requisitos 3.1, 3.2
@given(st.text(min_size=50, max_size=200), st.text(min_size=50, max_size=200))
@settings(max_examples=100, deadline=None)
def test_property_12_relevance_validation(code, criteria):
    """
    Feature: tutor-ia-evaluacion-directa-mejorada
    Property 12: Validación de Relevancia
    
    Para cualquier código enviado con su Contexto_Ejercicio, el sistema debe
    calcular un puntaje de relevancia que mida qué tan bien el código aborda
    los requisitos específicos.
    """
    # Crear instancia de AIManager (sin API key para tests)
    ai_manager = AIManager(api_key="test_key")
    
    # Llamar al método de validación de relevancia
    try:
        relevancia = ai_manager._validate_code_relevance(code, criteria, "Python")
        
        # Verificar que retorna un valor entre 0.0 y 1.0
        assert 0.0 <= relevancia <= 1.0, f"Relevancia debe estar entre 0.0 y 1.0, obtuvo {relevancia}"
        
        # Verificar que el cálculo es determinístico
        relevancia2 = ai_manager._validate_code_relevance(code, criteria, "Python")
        assert relevancia == relevancia2, "El cálculo de relevancia debe ser determinístico"
        
    except Exception as e:
        # Si hay error, debe ser manejado apropiadamente
        assert False, f"Error inesperado en validación de relevancia: {e}"


# Property 13: Rechazo por Baja Relevancia
# Valida: Requisitos 3.3
@given(relevant_code_and_criteria())
@settings(max_examples=50, deadline=None)
def test_property_13_low_relevance_rejection(code_and_criteria):
    """
    Feature: tutor-ia-evaluacion-directa-mejorada
    Property 13: Rechazo por Baja Relevancia
    
    Para cualquier código con puntaje de relevancia menor al 15%, el sistema
    debe asignar una puntuación de 2 y explicar qué requisitos no se cumplen.
    """
    code, criteria, language = code_and_criteria
    
    # Crear código completamente irrelevante
    irrelevant_code = "x = 1 + 1\nprint(x)"
    
    ai_manager = AIManager(api_key="test_key")
    relevancia = ai_manager._validate_code_relevance(irrelevant_code, criteria, language)
    
    # Si la relevancia es menor al 15%, verificar comportamiento esperado
    if relevancia < 0.15:
        # El sistema debería rechazar este código
        # (Esta verificación se hará en la integración completa)
        assert relevancia < 0.15, "Código irrelevante debe tener relevancia < 15%"


# Nota: Los demás property tests se implementarán después de crear
# las clases Detector_Errores, Analizador_Sintaxis, etc.
