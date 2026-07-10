"""
Evaluador Integrado para el Sistema de Evaluación Directa Mejorada.

Este módulo integra todos los componentes del sistema de evaluación.
"""

from typing import Tuple, List
import time
from models.evaluation_models import EvaluationResult
from evaluacion.detector_errores import Detector_Errores
from evaluacion.sistema_calificacion import Sistema_Calificacion
from evaluacion.generador_feedback import Generador_Feedback
from evaluacion.validador_consistencia import Validador_Consistencia
from evaluacion.logger_evaluacion import Logger_Evaluacion


class Evaluador_Integrado:
    """
    Integra todos los componentes del sistema de evaluación.
    """
    
    def __init__(self, ai_manager=None):
        """
        Inicializa el evaluador integrado.
        
        Args:
            ai_manager: Instancia de AIManager para llamadas a IA
        """
        self.detector_errores = Detector_Errores()
        self.sistema_calificacion = Sistema_Calificacion()
        self.generador_feedback = Generador_Feedback(ai_manager)
        self.validador_consistencia = Validador_Consistencia()
        self.logger = Logger_Evaluacion()
        self.ai_manager = ai_manager
        self.timeout_seconds = 30
    
    def evaluar_codigo(self, code: str, criteria: str, language: str = "Python") -> EvaluationResult:
        """
        Evalúa código siguiendo el flujo de 5 fases con manejo de errores.
        
        Args:
            code: Código del estudiante
            criteria: Contexto del ejercicio
            language: Lenguaje de programación
            
        Returns:
            EvaluationResult: Resultado completo de evaluación
        """
        start_time = time.time()
        
        try:
            # Validación inicial
            if not code or not code.strip():
                return EvaluationResult(
                    score=0,
                    feedback="Código vacío. Debes escribir código para resolver el problema.",
                    correctness="incorrecto",
                    suggestions=["Escribe código que resuelva el problema"],
                    concepts=["programación básica"]
                )
            
            # Verificar timeout
            if time.time() - start_time > self.timeout_seconds:
                return self._timeout_result()
            
            # FASE 1: Validación de Relevancia
            if self.ai_manager:
                try:
                    relevancia = self.ai_manager._validate_code_relevance(code, criteria, language)
                    
                    if relevancia < 0.15:
                        score = self.sistema_calificacion.calcular_score_relevancia(relevancia)
                        return EvaluationResult(
                            score=score,
                            feedback=f"El código no resuelve el problema planteado. El desafío requiere: {criteria[:200]}...",
                            correctness="incorrecto",
                            suggestions=["Leer cuidadosamente el problema", "Implementar la solución específica solicitada"],
                            concepts=["comprensión del problema"]
                        )
                except Exception as e:
                    print(f"Error en validación de relevancia: {e}")
                    # Continuar con el análisis
            
            # FASE 2: Detección de Código Inválido
            try:
                es_invalido, razon_invalido = self.detector_errores.detectar_codigo_invalido(code, language)
                
                if es_invalido:
                    self.logger.log_invalid_code(language, razon_invalido)
                    return EvaluationResult(
                        score=0,
                        feedback=f"Código inválido: {razon_invalido}",
                        correctness="incorrecto",
                        suggestions=["Escribir código válido", "Usar sintaxis correcta"],
                        concepts=["sintaxis básica"],
                        errores_detectados=[razon_invalido]
                    )
            except Exception as e:
                print(f"Error en detección de código inválido: {e}")
                # Continuar con el análisis
            
            # Verificar timeout
            if time.time() - start_time > self.timeout_seconds:
                return self._timeout_result()
            
            # FASE 3: Análisis de Errores Específicos por Lenguaje
            try:
                errores, severidad = self.detector_errores.detectar_errores_lenguaje(code, language)
                
                if errores:
                    score = self.sistema_calificacion.calcular_score_por_severidad(severidad)
                    feedback = self.generador_feedback.generar_feedback_errores(errores, severidad, language)
                    
                    return EvaluationResult(
                        score=score,
                        feedback=feedback,
                        correctness="incorrecto",
                        suggestions=["Corregir errores de sintaxis", "Revisar variables", "Verificar lógica"],
                        concepts=["depuración", "sintaxis"],
                        errores_detectados=errores
                    )
            except Exception as e:
                print(f"Error en análisis de errores: {e}")
                # Continuar con evaluación de IA
            
            # FASE 4: Evaluación con IA
            if self.ai_manager:
                try:
                    # Reintentar hasta 3 veces con backoff exponencial
                    for attempt in range(3):
                        try:
                            result_ia = self.generador_feedback.generar_feedback_ia(code, criteria, language)
                            
                            score = result_ia.get('score', 5)
                            feedback = result_ia.get('feedback', 'Sin comentarios')
                            correctness = result_ia.get('correctness', 'incorrecto')
                            suggestions = result_ia.get('suggestions', [])
                            concepts = result_ia.get('concepts', [])
                            
                            # FASE 5: Validación de Consistencia
                            score_ajustado, razon_ajuste = self.validador_consistencia.validar_consistencia(
                                score, feedback, code, criteria, language
                            )
                            
                            # Registrar ajuste si hubo
                            if score != score_ajustado:
                                self.logger.log_consistency_adjustment(score, score_ajustado, language, razon_ajuste)
                            
                            # Registrar métricas
                            evaluation_time = time.time() - start_time
                            self.logger.update_metrics(language, score_ajustado, evaluation_time)
                            
                            return EvaluationResult(
                                score=score_ajustado,
                                feedback=feedback,
                                correctness=correctness,
                                suggestions=suggestions,
                                concepts=concepts,
                                score_ajustado=(score != score_ajustado),
                                razon_ajuste=razon_ajuste
                            )
                        except Exception as e:
                            if attempt < 2:
                                time.sleep(2 ** attempt)  # Backoff exponencial: 1s, 2s, 4s
                            else:
                                raise
                
                except Exception as e:
                    print(f"Error en evaluación con IA: {e}")
                    self.logger.log_api_error(str(e), code[:100])
                    return self._fallback_evaluation(code, language)
            else:
                # Sin IA, retornar evaluación básica
                return self._fallback_evaluation(code, language)
        
        except Exception as e:
            print(f"Error general en evaluación: {e}")
            return EvaluationResult(
                score=5,
                feedback=f"Error en evaluación: {str(e)}",
                correctness="incorrecto",
                suggestions=["Revisar código", "Intentar nuevamente"],
                concepts=["error de sistema"]
            )
    
    def _timeout_result(self) -> EvaluationResult:
        """Retorna resultado cuando hay timeout."""
        self.logger.log_timeout('evaluacion_completa', self.timeout_seconds)
        return EvaluationResult(
            score=5,
            feedback="Timeout en evaluación. El código es demasiado complejo o largo. Intenta con código más simple.",
            correctness="incorrecto",
            suggestions=["Simplificar código", "Reducir complejidad"],
            concepts=["optimización"]
        )
    
    def _fallback_evaluation(self, code: str, language: str) -> EvaluationResult:
        """Evaluación de respaldo cuando falla la IA."""
        return EvaluationResult(
            score=5,
            feedback="Evaluación básica: código sin errores detectados manualmente. La evaluación completa no está disponible.",
            correctness="parcial",
            suggestions=["Revisar lógica", "Agregar validaciones", "Probar el código"],
            concepts=["programación general"]
        )
