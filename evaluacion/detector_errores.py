"""
Detector de Errores para el Sistema de Evaluación Directa Mejorada.

Este módulo contiene las clases para detectar errores de sintaxis, lógica
y código inválido en múltiples lenguajes de programación.
"""

from typing import Tuple, List
from models.evaluation_models import ErrorDetection
from evaluacion.analizador_sintaxis import Analizador_Sintaxis
from evaluacion.analizador_logica import Analizador_Logica


class Detector_Errores:
    """
    Coordina la detección de código inválido y errores específicos por lenguaje.
    """
    
    def __init__(self):
        """Inicializa el detector de errores."""
        self.analizador_sintaxis = Analizador_Sintaxis()
        self.analizador_logica = Analizador_Logica()
    
    def detectar_codigo_invalido(self, code: str, language: str) -> Tuple[bool, str]:
        """
        Detecta código aleatorio, mezcla de lenguajes, texto sin sentido.
        
        Args:
            code: Código a analizar
            language: Lenguaje de programación
            
        Returns:
            Tuple[bool, str]: (es_invalido, razon)
        """
        if not code or not code.strip():
            return True, "Código vacío"
        
        code_clean = code.strip().lower()
        
        # 1. Detectar mezcla de 3+ lenguajes diferentes
        syntax_indicators = {
            'sql': ['select ', 'from ', 'where ', 'insert into', 'update ', 'delete from'],
            'python': ['print(', 'def ', 'import ', 'if __name__'],
            'javascript': ['console.log', '.then(', '.catch(', 'var ', 'let ', 'const '],
            'java': ['system.out.println', 'public class', 'public static'],
            'nosql': ['db.', 'use ', 'aggregate', 'find(', 'insertone'],
        }
        
        detected_languages = []
        for lang_name, indicators in syntax_indicators.items():
            if any(indicator in code_clean for indicator in indicators):
                detected_languages.append(lang_name)
        
        # Si es NoSQL y detecta mongosh, no contar como mezcla
        if language == "NoSQL" and 'nosql' in detected_languages:
            detected_languages = ['nosql']
        
        if len(detected_languages) >= 3:
            return True, f"Mezcla de múltiples lenguajes: {', '.join(detected_languages)}"
        
        # 2. Detectar palabras sin sentido
        nonsense_patterns = [
            'asdfgh', 'qwerty', 'blablabla', 'nada existe',
            'nothing', 'infinito', 'yesterday', 'nowhere'
        ]
        
        if any(pattern in code_clean for pattern in nonsense_patterns):
            return True, "Código contiene palabras sin sentido"
        
        # 3. Detectar >30% caracteres especiales sin estructura
        if language not in ["NoSQL", "JavaScript", "C++", "Java", "SQL"]:
            special_chars = ''.join([c for c in code if c in '!@#$%^&*()+=[]{}|;:,.<>?'])
            if len(special_chars) > len(code) * 0.3:
                return True, "Demasiados caracteres especiales sin estructura"
        
        # 4. Detectar código <20 caracteres sin elementos de programación
        programming_keywords = [
            'def', 'print', 'if', 'for', 'while', 'return', 'import', 'class',
            'select', 'from', 'where', 'function', 'var', 'let', 'const'
        ]
        
        has_programming = any(keyword in code_clean for keyword in programming_keywords)
        
        if not has_programming and len(code_clean) < 20:
            return False, "Código demasiado corto sin elementos de programación"
        
        return False, ""
    
    def detectar_errores_lenguaje(self, code: str, language: str) -> Tuple[List[str], int]:
        """
        Coordina análisis de sintaxis y lógica según lenguaje.
        
        Args:
            code: Código a analizar
            language: Lenguaje de programación
            
        Returns:
            Tuple[List[str], int]: (lista_errores, severidad_total)
        """
        errores = []
        severidad = 0
        
        # Análisis de sintaxis
        errores_sintaxis, sev_sintaxis = self.analizador_sintaxis.analizar(code, language)
        errores.extend(errores_sintaxis)
        severidad += sev_sintaxis
        
        # Análisis de lógica
        errores_logica, sev_logica = self.analizador_logica.analizar(code, language)
        errores.extend(errores_logica)
        severidad += sev_logica
        
        return errores, severidad
