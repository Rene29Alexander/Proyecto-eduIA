"""
Generador de Feedback para el Sistema de Evaluación Directa Mejorada.

Este módulo contiene la clase que produce retroalimentación específica y contextualizada.
"""

from typing import List, Dict
import re


class Generador_Feedback:
    """
    Produce retroalimentación específica y contextualizada.
    """
    
    def __init__(self, ai_manager=None):
        """
        Inicializa el generador de feedback.
        
        Args:
            ai_manager: Instancia de AIManager para llamadas a IA
        """
        self.ai_manager = ai_manager
    
    def generar_feedback_errores(self, errores: List[str], severidad: int, language: str) -> str:
        """
        Genera feedback cuando se detectan errores manualmente.
        
        Args:
            errores: Lista de errores detectados
            severidad: Severidad acumulada
            language: Lenguaje de programación
            
        Returns:
            str: Feedback detallado
        """
        if not errores:
            return ""
        
        error_list = "\n".join([f"• {error}" for error in errores])
        
        feedback = f"El código tiene {len(errores)} error(es) detectado(s):\n\n{error_list}\n\n"
        
        if severidad >= 10:
            feedback += "Estos son errores críticos que impiden completamente la ejecución del código."
        elif severidad >= 6:
            feedback += "Estos errores impiden que el código funcione correctamente."
        elif severidad >= 3:
            feedback += "Estos errores afectan la funcionalidad del código."
        else:
            feedback += "Estos son errores menores que deberían corregirse."
        
        return feedback
    
    def generar_feedback_ia(self, code: str, criteria: str, language: str) -> Dict:
        """
        Genera feedback usando Gemini AI.
        
        Args:
            code: Código del estudiante
            criteria: Contexto del ejercicio
            language: Lenguaje de programación
            
        Returns:
            dict: {"score": int, "feedback": str, "correctness": str, 
                   "suggestions": list, "concepts": list}
        """
        if not self.ai_manager:
            return {
                "score": 5,
                "feedback": "Error: AI Manager no disponible",
                "correctness": "incorrecto",
                "suggestions": [],
                "concepts": []
            }
        
        # Mapear nombres de lenguajes
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
Actúa como un profesor experto en programación que evalúa código de estudiantes.

### [EMOJI] Configuración de la Sesión:
- **Lenguaje:** {mapped_lang}
- **Ejercicio:** {criteria[:200]}...
- **Contexto:** Código de estudiante en aprendizaje

### [OBJETIVO] Tu Misión:
1. **Análisis:** Revisa el código con criterios PRÁCTICOS y PROPORCIONALES al ejercicio
2. **Evaluación:** Analiza sintaxis, lógica, cumplimiento de requisitos
3. **Calificación:** Asigna nota 1-10 basada en funcionalidad y corrección

### [CODIGO] Código del Estudiante:
```{language.lower()}
{code}
```

### [LISTA] Desafío a Resolver:
{criteria}

### [IA] Evaluación de Gemini - Formato Requerido:

**Análisis Técnico:**
[Análisis detallado y PRAGMÁTICO]

**Aspectos Positivos:**
- [Punto positivo 1 específico del código]
- [Punto positivo 2 específico del código]

**Áreas de Mejora:**
1. [Primera mejora PRÁCTICA y PROPORCIONAL]
2. [Segunda mejora PRÁCTICA y PROPORCIONAL]

**Criterios de Éxito:**
- [Qué se esperaba vs qué falta]

**Nota Final:** [X/10]

### [!] REGLAS CRÍTICAS:

**Análisis del Código Real:**
1. LEE el código COMPLETO antes de hacer sugerencias
2. IDENTIFICA qué estructuras de datos ya se usan (lista, diccionario, set, etc.)
3. VERIFICA qué validaciones ya existen antes de sugerir agregar más
4. NO sugieras cambiar a una estructura que YA se está usando

**Coherencia Técnica:**
5. NO sugieras cambios que EMPEOREN la complejidad temporal (ej: diccionario O(1) → lista O(n))
6. NO llames "redundante" a validaciones de estado o programación defensiva
7. NO llames "compleja" a validación estándar y clara
8. MIDE la complejidad temporal antes de sugerir cambios de estructura de datos

**Especificidad:**
9. Feedback 100% específico al código revisado
10. NO mencionar conceptos ausentes del desafío
11. NO usar feedback genérico
12. Mencionar elementos ESPECÍFICOS (nombres de variables, funciones, líneas de código)

**Balance:**
13. Mencionar SIEMPRE al menos 2 aspectos positivos
14. Dar SIEMPRE al menos 2 sugerencias de mejora

**Proporcionalidad:**
15. Sugerencias PROPORCIONALES al problema - NO sugerir arquitecturas complejas (grafos, árboles, microservicios) para problemas simples
16. Evaluar el código en su CONTEXTO - un gestor simple NO necesita bases de datos complejas ni arquitecturas enterprise
17. Priorizar CLARIDAD y FUNCIONALIDAD sobre optimizaciones prematuras
18. Si el código funciona correctamente, enfocarse en mejoras incrementales, NO en rediseños completos

**Ejemplos de Errores a EVITAR:**
❌ "Usar diccionario en lugar de lista" cuando YA usa diccionario
❌ "La validación es redundante" cuando es programación defensiva válida
❌ "Simplificar validación" cuando la validación es estándar y clara
❌ "Cambiar a lista" cuando usa diccionario (downgrade de O(1) a O(n))

Responde SOLO este JSON:
{{"score": NUMERO_0_AL_10, "feedback": "...", "correctness": "correcto_o_incorrecto", 
 "suggestions": ["..."], "concepts": ["..."]}}
"""
        
        response = self.ai_manager.call_with_retry(prompt)
        result = self.ai_manager.extract_json_from_response(response, 'dict')
        
        if isinstance(result, dict) and 'score' in result:
            # Validar relevancia del feedback
            feedback = result.get('feedback', '')
            if not self.validar_relevancia_feedback(feedback, criteria, code):
                # Regenerar feedback más específico
                result['feedback'] = self._regenerar_feedback_especifico(code, criteria, language)
            
            return result
        else:
            return {
                "score": 5,
                "feedback": "Error al procesar respuesta de IA",
                "correctness": "incorrecto",
                "suggestions": [],
                "concepts": []
            }
    
    def validar_relevancia_feedback(self, feedback: str, criteria: str, code: str = "") -> bool:
        """
        Verifica que feedback sea relevante al ejercicio y técnicamente coherente.
        
        Args:
            feedback: Feedback generado
            criteria: Contexto del ejercicio
            code: Código evaluado (para verificar coherencia)
            
        Returns:
            bool: True si es relevante y coherente, False si no
        """
        # Detectar keywords irrelevantes
        irrelevant_keywords = [
            'lógica de recomendación', 'sistema de recomendación',
            'algoritmo de búsqueda', 'sistema de inventario',
            'gestión de inventario', 'base de datos de productos'
        ]
        
        # Detectar overengineering (arquitecturas complejas innecesarias)
        overengineering_keywords = [
            'árbol de tareas', 'grafo', 'sistema basado en grafo',
            'microservicios', 'arquitectura distribuida',
            'sistema de gestión de tareas más sofisticado',
            'arquitectura enterprise', 'patrón saga',
            'event sourcing', 'cqrs', 'arquitectura hexagonal'
        ]
        
        feedback_lower = feedback.lower()
        criteria_lower = criteria.lower()
        
        # Verificar keywords irrelevantes
        for keyword in irrelevant_keywords:
            if keyword in feedback_lower and keyword not in criteria_lower:
                return False
        
        # Verificar overengineering
        for keyword in overengineering_keywords:
            if keyword in feedback_lower:
                return False  # Rechazar feedback con sugerencias de overengineering
        
        # Verificar coherencia técnica si se proporciona código
        if code:
            if not self._verificar_coherencia_tecnica(feedback, code):
                return False
        
        return True
    
    def _verificar_coherencia_tecnica(self, feedback: str, code: str) -> bool:
        """
        Verifica que el feedback no contenga incoherencias técnicas.
        
        Args:
            feedback: Feedback generado
            code: Código evaluado
            
        Returns:
            bool: True si es coherente, False si tiene incoherencias
        """
        feedback_lower = feedback.lower()
        
        # 1. Detectar si sugiere usar diccionario cuando ya usa diccionario
        if re.search(r'(usar|cambiar|considerar|con|con un).*(diccionario|dict)', feedback_lower):
            # Verificar si el código ya usa diccionarios
            if re.search(r'(=\s*\{|dict\(\))', code):
                return False  # Incoherencia: ya usa diccionario
        
        # 2. Detectar si sugiere usar lista cuando ya usa diccionario (downgrade O(1) → O(n))
        if re.search(r'(usar|cambiar|considerar|con|con una).*(lista|list)', feedback_lower):
            # Verificar si el código usa diccionarios para búsqueda/acceso
            if re.search(r'(=\s*\{.*:|dict\(\))', code):
                # Si sugiere lista cuando hay diccionario con keys, es downgrade
                return False
        
        # 3. Detectar si llama "redundante" a validaciones de estado
        if 'redundante' in feedback_lower:
            # Verificar si hay validaciones de estado en el código
            if re.search(r'(if\s+self\.\w+|raise\s+ValueError)', code):
                # Validaciones de estado NO son redundantes
                return False
        
        # 4. Detectar si llama "compleja" a validación estándar
        if re.search(r'validación.*(compleja|complicada)', feedback_lower):
            # Contar líneas de validación
            validation_lines = len(re.findall(r'(if\s+not\s+|raise\s+ValueError)', code))
            if validation_lines <= 5:  # Validación estándar (hasta 5 checks), no compleja
                return False
        
        return True
    
    def _regenerar_feedback_especifico(self, code: str, criteria: str, language: str) -> str:
        """
        Regenera feedback más específico basado en keywords del ejercicio.
        
        Args:
            code: Código del estudiante
            criteria: Contexto del ejercicio
            language: Lenguaje de programación
            
        Returns:
            str: Feedback regenerado
        """
        # Extraer conceptos clave del ejercicio
        concepts = self._extraer_conceptos(criteria)
        
        # Generar feedback básico
        feedback = f"El código aborda el problema de {', '.join(concepts) if concepts else 'programación'}. "
        
        # Analizar elementos del código
        if 'def ' in code:
            functions = re.findall(r'def\s+(\w+)', code)
            if functions:
                feedback += f"Se definen las funciones: {', '.join(functions)}. "
        
        if 'class ' in code:
            classes = re.findall(r'class\s+(\w+)', code)
            if classes:
                feedback += f"Se definen las clases: {', '.join(classes)}. "
        
        feedback += "Revisar la implementación para asegurar que cumple todos los requisitos."
        
        return feedback
    
    def _extraer_conceptos(self, criteria: str) -> List[str]:
        """
        Extrae conceptos clave del contexto del ejercicio.
        
        Args:
            criteria: Contexto del ejercicio
            
        Returns:
            List[str]: Lista de conceptos
        """
        concepts = []
        criteria_lower = criteria.lower()
        
        concept_keywords = {
            'calculadora': 'cálculos matemáticos',
            'inventario': 'gestión de inventario',
            'usuarios': 'gestión de usuarios',
            'productos': 'gestión de productos',
            'api': 'API REST',
            'base de datos': 'base de datos',
            'juego': 'lógica de juego'
        }
        
        for keyword, concept in concept_keywords.items():
            if keyword in criteria_lower:
                concepts.append(concept)
        
        return concepts if concepts else ['programación general']
