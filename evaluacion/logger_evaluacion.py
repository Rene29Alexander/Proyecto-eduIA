"""
Logger para el Sistema de Evaluación Directa Mejorada.

Este módulo maneja el logging de eventos y métricas del sistema.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any


class Logger_Evaluacion:
    """
    Maneja el logging de eventos y métricas del sistema de evaluación.
    """
    
    def __init__(self):
        """Inicializa el logger."""
        self.log_dir = "logs"
        self._ensure_log_directory()
        
        self.events_file = os.path.join(self.log_dir, "evaluation_events.json")
        self.metrics_file = os.path.join(self.log_dir, "evaluation_metrics.json")
        self.errors_file = os.path.join(self.log_dir, "evaluation_errors.json")
    
    def _ensure_log_directory(self):
        """Asegura que el directorio de logs existe."""
        os.makedirs(self.log_dir, exist_ok=True)
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        Registra un evento del sistema.
        
        Args:
            event_type: Tipo de evento
            data: Datos del evento
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'data': data
        }
        
        self._append_to_file(self.events_file, event)
    
    def log_consistency_adjustment(self, score_original: int, score_ajustado: int,
                                   language: str, razon: str):
        """Registra ajuste de consistencia."""
        self.log_event('consistency_adjustment', {
            'score_original': score_original,
            'score_ajustado': score_ajustado,
            'language': language,
            'razon': razon
        })
    
    def log_api_error(self, error: str, code_snippet: str):
        """Registra error de API de IA."""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error': error,
            'code_snippet': code_snippet[:100]
        }
        
        self._append_to_file(self.errors_file, error_data)
    
    def log_invalid_code(self, language: str, razon: str):
        """Registra código inválido rechazado."""
        self.log_event('invalid_code_rejected', {
            'language': language,
            'razon': razon
        })
    
    def log_timeout(self, component: str, elapsed_time: float):
        """Registra timeout de análisis."""
        self.log_event('analysis_timeout', {
            'component': component,
            'elapsed_time': elapsed_time
        })
    
    def update_metrics(self, language: str, score: int, evaluation_time: float):
        """
        Actualiza métricas de monitoreo.
        
        Args:
            language: Lenguaje de programación
            score: Puntuación asignada
            evaluation_time: Tiempo de evaluación en segundos
        """
        metrics = self._load_metrics()
        
        if language not in metrics:
            metrics[language] = {
                'total_evaluations': 0,
                'score_distribution': {str(i): 0 for i in range(11)},
                'total_time': 0.0,
                'avg_time': 0.0
            }
        
        metrics[language]['total_evaluations'] += 1
        metrics[language]['score_distribution'][str(score)] += 1
        metrics[language]['total_time'] += evaluation_time
        metrics[language]['avg_time'] = metrics[language]['total_time'] / metrics[language]['total_evaluations']
        
        self._save_metrics(metrics)
    
    def _load_metrics(self) -> Dict:
        """Carga métricas desde archivo."""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_metrics(self, metrics: Dict):
        """Guarda métricas a archivo."""
        try:
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando métricas: {e}")
    
    def _append_to_file(self, filepath: str, data: Dict):
        """Agrega datos a un archivo JSON."""
        try:
            entries = []
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    entries = json.load(f)
            
            entries.append(data)
            
            # Mantener solo las últimas 1000 entradas
            if len(entries) > 1000:
                entries = entries[-1000:]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"Error escribiendo a {filepath}: {e}")
    
    def get_metrics_summary(self) -> Dict:
        """
        Obtiene resumen de métricas.
        
        Returns:
            Dict: Resumen de métricas por lenguaje
        """
        return self._load_metrics()
