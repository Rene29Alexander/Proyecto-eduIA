"""
Validador de Consistencia para el Sistema de Evaluación Directa Mejorada.

Este módulo contiene la clase que verifica coherencia entre puntuación y retroalimentación.
"""

from typing import Tuple
from datetime import datetime
from models.evaluation_models import ConsistencyAdjustment
import json
import os


class Validador_Consistencia:
    """
    Verifica coherencia entre puntuación y retroalimentación.
    """
    
    def __init__(self):
        """Inicializa el validador de consistencia."""
        self.log_file = "logs/consistency_adjustments.json"
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """Asegura que el directorio de logs existe."""
        os.makedirs("logs", exist_ok=True)
    
    def validar_consistencia(self, score: int, feedback: str, code: str, 
                            criteria: str, language: str) -> Tuple[int, str]:
        """
        Valida coherencia entre score y feedback, ajusta si es necesario.
        
        Args:
            score: Puntuación original
            feedback: Retroalimentación generada
            code: Código evaluado
            criteria: Contexto del ejercicio
            language: Lenguaje de programación
            
        Returns:
            Tuple[int, str]: (score_ajustado, razon_ajuste)
        """
        feedback_lower = feedback.lower()
        score_original = score
        razon_ajuste = ""
        
        # Regla 1: Si feedback menciona "errores críticos" y score > 7
        if any(keyword in feedback_lower for keyword in ['errores críticos', 'error crítico', 'crítico']):
            if score > 7:
                score = 3
                razon_ajuste = "Feedback menciona 'errores críticos' pero score era alto"
        
        # Regla 2: Si feedback indica "código perfecto" y score < 8
        if any(keyword in feedback_lower for keyword in ['perfecto', 'excelente', 'impecable']):
            if score < 8:
                score = 9
                razon_ajuste = "Feedback indica 'código perfecto' pero score era bajo"
        
        # Regla 3: Si feedback menciona "funciona parcialmente" y score > 8
        if any(keyword in feedback_lower for keyword in ['funciona parcialmente', 'parcialmente correcto']):
            if score > 8:
                score = 7
                razon_ajuste = "Feedback menciona 'funciona parcialmente' pero score era muy alto"
        
        # Regla 4: Si feedback menciona "no ejecuta" y score > 5
        if any(keyword in feedback_lower for keyword in ['no ejecuta', 'no funciona', 'no corre']):
            if score > 5:
                score = 2
                razon_ajuste = "Feedback menciona 'no ejecuta' pero score era alto"
        
        # Si hubo ajuste, registrarlo
        if score != score_original:
            self.registrar_ajuste(score_original, score, feedback, razon_ajuste, language)
        
        return score, razon_ajuste
    
    def registrar_ajuste(self, score_original: int, score_ajustado: int, 
                        feedback: str, razon: str, language: str):
        """
        Registra ajustes para monitoreo y mejora continua.
        
        Args:
            score_original: Score antes del ajuste
            score_ajustado: Score después del ajuste
            feedback: Feedback generado
            razon: Razón del ajuste
            language: Lenguaje de programación
        """
        adjustment = ConsistencyAdjustment(
            timestamp=datetime.now(),
            language=language,
            score_original=score_original,
            score_ajustado=score_ajustado,
            razon=razon,
            feedback_snippet=feedback[:200]
        )
        
        # Guardar en archivo JSON
        try:
            adjustments = []
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    adjustments = json.load(f)
            
            adjustments.append({
                'timestamp': adjustment.timestamp.isoformat(),
                'language': adjustment.language,
                'score_original': adjustment.score_original,
                'score_ajustado': adjustment.score_ajustado,
                'razon': adjustment.razon,
                'feedback_snippet': adjustment.feedback_snippet
            })
            
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(adjustments, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"Error registrando ajuste: {e}")
