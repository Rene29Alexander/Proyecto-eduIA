"""
Sistema de Calificación para el Sistema de Evaluación Directa Mejorada.

Este módulo contiene la clase que asigna puntuaciones 1-10 basadas en severidad de errores.
"""


class Sistema_Calificacion:
    """
    Asigna puntuaciones 1-10 basadas en severidad de errores.
    """
    
    def calcular_score_por_severidad(self, severidad: int) -> int:
        """
        Calcula score basado en severidad acumulada de errores.
        
        Args:
            severidad: Severidad acumulada de errores
            
        Returns:
            int: Score entre 1-10
        """
        if severidad >= 10:  # Errores críticos múltiples
            return 1
        elif severidad >= 8:  # Errores muy graves
            return 2
        elif severidad >= 6:  # Errores graves
            return 3
        elif severidad >= 4:  # Errores moderados
            return 5
        elif severidad >= 2:  # Errores menores
            return 7
        else:  # Errores muy menores
            return 8
    
    def calcular_score_relevancia(self, relevancia: float) -> int:
        """
        Calcula score cuando código no es relevante al ejercicio.
        
        Args:
            relevancia: Score de relevancia (0.0 - 1.0)
            
        Returns:
            int: Score entre 0-10
        """
        if relevancia < 0.15:
            return 2
        elif relevancia < 0.30:
            return 4
        elif relevancia < 0.50:
            return 6
        elif relevancia < 0.70:
            return 7
        elif relevancia < 0.85:
            return 8
        else:
            return 9
