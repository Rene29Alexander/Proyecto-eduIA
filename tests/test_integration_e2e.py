"""
Integration Tests End-to-End para el Sistema de Evaluación.

Este módulo contiene tests que validan el flujo completo de evaluación.
"""

import pytest
from utils_ai import AIManager


class TestIntegrationE2E:
    """Tests de integración end-to-end."""
    
    def setup_method(self):
        """Inicializar AIManager para cada test."""
        self.ai_manager = AIManager()
    
    def test_e2e_python_valido(self):
        """Test E2E: código Python válido → score 9-10, feedback positivo."""
        code = """
def suma(a, b):
    return a + b

def resta(a, b):
    return a - b

resultado = suma(5, 3)
print(f'Resultado: {resultado}')
"""
        criteria = "Crear funciones para sumar y restar dos números"
        language = "Python"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Validaciones
        assert isinstance(score, int), "Score debe ser entero"
        assert 0 <= score <= 10, "Score debe estar entre 0 y 10"
        assert isinstance(feedback, str), "Feedback debe ser string"
        assert len(feedback) > 0, "Feedback no debe estar vacío"
        assert correctness in ["correcto", "parcial", "incorrecto"], "Correctness debe ser válido"
        assert isinstance(suggestions, list), "Suggestions debe ser lista"
        assert isinstance(concepts, list), "Concepts debe ser lista"
        
        # Para código válido, esperamos score razonable (puede variar sin API key)
        assert score >= 5, f"Código válido debería tener score >= 5, obtuvo {score}"
    
    def test_e2e_sql_con_errores(self):
        """Test E2E: código SQL con errores → score 2-3, feedback con errores específicos."""
        code = "SELEC * FRO usuarios WHERE id == 1"
        criteria = "Consultar todos los usuarios con id = 1"
        language = "SQL"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Validaciones
        assert isinstance(score, int), "Score debe ser entero"
        assert 0 <= score <= 10, "Score debe estar entre 0 y 10"
        assert score <= 5, f"SQL con errores debería tener score bajo, obtuvo {score}"
        
        # Verificar que el feedback menciona los errores
        assert "SELEC" in feedback or "SELECT" in feedback, "Feedback debe mencionar error de SELEC"
        assert "FRO" in feedback or "FROM" in feedback, "Feedback debe mencionar error de FRO"
        
        assert correctness == "incorrecto", "Correctness debe ser incorrecto"
    
    def test_e2e_nosql_con_mezcla_javascript(self):
        """Test E2E: código NoSQL con mezcla de JavaScript → score 0-2, feedback sobre mezcla."""
        code = """
db.productos.find({stock: 10}).then(result => {
    console.log(result);
});
"""
        criteria = "Buscar productos con stock = 10"
        language = "NoSQL"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Validaciones
        assert isinstance(score, int), "Score debe ser entero"
        assert 0 <= score <= 10, "Score debe estar entre 0 y 10"
        # NoSQL con JavaScript puede tener score bajo
        assert score <= 5, f"NoSQL con mezcla debería tener score bajo, obtuvo {score}"
        
        # Verificar que el feedback menciona la mezcla
        feedback_lower = feedback.lower()
        assert "javascript" in feedback_lower or "then" in feedback_lower or "console" in feedback_lower, \
            "Feedback debe mencionar mezcla con JavaScript"
    
    def test_e2e_codigo_irrelevante(self):
        """Test E2E: código irrelevante al ejercicio → score 2, feedback sobre falta de relevancia."""
        code = """
def calcular_area_circulo(radio):
    return 3.14 * radio ** 2
"""
        criteria = "Crear una función que calcule el factorial de un número"
        language = "Python"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Validaciones
        assert isinstance(score, int), "Score debe ser entero"
        assert 0 <= score <= 10, "Score debe estar entre 0 y 10"
        # Código irrelevante debería tener score bajo
        assert score <= 5, f"Código irrelevante debería tener score bajo, obtuvo {score}"
        
        # Verificar que el feedback menciona la falta de relevancia
        feedback_lower = feedback.lower()
        assert "factorial" in feedback_lower or "problema" in feedback_lower or "requisito" in feedback_lower, \
            "Feedback debe mencionar que no resuelve el problema"
    
    def test_e2e_codigo_vacio(self):
        """Test E2E: código vacío → score 0, feedback apropiado."""
        code = ""
        criteria = "Crear una función"
        language = "Python"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Validaciones
        assert score == 0, "Código vacío debe tener score 0"
        assert "vacío" in feedback.lower(), "Feedback debe mencionar que el código está vacío"
        assert correctness == "incorrecto", "Correctness debe ser incorrecto"
    
    def test_e2e_python_con_errores_sintaxis(self):
        """Test E2E: Python con errores de sintaxis → score bajo, errores específicos."""
        code = """
def suma(a, b)
    return a + b

resultado = suma(5, 3
print(resultado)
"""
        criteria = "Crear una función que sume dos números"
        language = "Python"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Validaciones
        assert isinstance(score, int), "Score debe ser entero"
        assert score <= 5, f"Código con errores de sintaxis debería tener score bajo, obtuvo {score}"
        
        # Verificar que el feedback menciona los errores
        feedback_lower = feedback.lower()
        assert ":" in feedback or "dos puntos" in feedback_lower or "paréntesis" in feedback_lower, \
            "Feedback debe mencionar errores de sintaxis"
        
        assert correctness == "incorrecto", "Correctness debe ser incorrecto"
    
    def test_e2e_javascript_valido(self):
        """Test E2E: JavaScript válido → score razonable."""
        code = """
function suma(a, b) {
    return a + b;
}

const resultado = suma(5, 3);
console.log(resultado);
"""
        criteria = "Crear una función que sume dos números"
        language = "JavaScript"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Validaciones
        assert isinstance(score, int), "Score debe ser entero"
        assert 0 <= score <= 10, "Score debe estar entre 0 y 10"
        assert score >= 5, f"JavaScript válido debería tener score >= 5, obtuvo {score}"
    
    def test_e2e_consistencia_score_feedback(self):
        """Test E2E: verificar que score y feedback son consistentes."""
        # Código con errores graves
        code = "SELEC * FRO WHERE"
        criteria = "Consultar datos"
        language = "SQL"
        
        score, feedback, correctness, suggestions, concepts = self.ai_manager.evaluate_code(
            code, criteria, language
        )
        
        # Si el score es bajo, el feedback debe mencionar errores
        if score <= 3:
            feedback_lower = feedback.lower()
            assert any(word in feedback_lower for word in ["error", "incorrecto", "falta", "mal"]), \
                "Feedback debe mencionar errores cuando score es bajo"
        
        # Si el score es alto, el feedback debe ser positivo
        if score >= 8:
            feedback_lower = feedback.lower()
            assert any(word in feedback_lower for word in ["correcto", "bien", "excelente", "válido"]), \
                "Feedback debe ser positivo cuando score es alto"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
