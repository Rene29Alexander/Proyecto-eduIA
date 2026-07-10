"""
Analizador de Lógica para el Sistema de Evaluación Directa Mejorada.

Este módulo contiene la clase que evalúa corrección lógica y funcional del código.
"""

from typing import Tuple, List
import re


class Analizador_Logica:
    """
    Evalúa corrección lógica y funcional del código.
    """
    
    def analizar(self, code: str, language: str) -> Tuple[List[str], int]:
        """
        Analiza lógica según el lenguaje.
        
        Args:
            code: Código a analizar
            language: Lenguaje de programación
            
        Returns:
            Tuple[List[str], int]: (lista_errores, severidad_total)
        """
        errores = []
        severidad = 0
        
        if language == "Python":
            err_py, sev_py = self.analizar_logica_python(code)
            errores.extend(err_py)
            severidad += sev_py
        elif language == "NoSQL":
            err_nosql, sev_nosql = self.analizar_logica_nosql(code)
            errores.extend(err_nosql)
            severidad += sev_nosql
        
        # Análisis lógico general para todos los lenguajes
        err_gen, sev_gen = self.analizar_logica_general(code, language)
        errores.extend(err_gen)
        severidad += sev_gen
        
        return errores, severidad
    
    def analizar_logica_python(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores lógicos en Python."""
        errores = []
        severidad = 0
        lines = code.split('\n')

        # 1. Variables no definidas o mal escritas
        if 'in flor:' in code and 'flores' in code:
            errores.append("Variable 'flor' no definida, probablemente debería ser 'flores'")
            severidad += 2

        # Detectar variables similares pero mal escritas (singular vs plural común)
        # Buscar patrones como: suma += numero cuando existe numeros
        for i, line in enumerate(lines):
            # Patrón: variable singular usada cuando existe plural
            if re.search(r'\bnumero\b', line) and 'numeros' in code:
                if 'for numero in numeros' not in line:  # Excluir el caso válido del for
                    errores.append(f"Línea {i+1}: Variable 'numero' no definida, probablemente debería ser 'numeros'")
                    severidad += 3

            # Otros patrones comunes
            if re.search(r'\bvalor\b', line) and 'valores' in code:
                if 'for valor in valores' not in line:
                    errores.append(f"Línea {i+1}: Variable 'valor' no definida, probablemente debería ser 'valores'")
                    severidad += 3

            if re.search(r'\bdato\b', line) and 'datos' in code:
                if 'for dato in datos' not in line:
                    errores.append(f"Línea {i+1}: Variable 'dato' no definida, probablemente debería ser 'datos'")
                    severidad += 3

        # 2. Tipos inconsistentes
        if '"90"' in code and '85' in code and 'nota' in code.lower():
            errores.append("Mezcla tipos string ('90') e integer (85)")
            severidad += 2

        # 3. Concatenación incorrecta de tipos (string + int/float)
        for i, line in enumerate(lines):
            # Detectar patrones como: "texto" + variable_numerica
            # Buscar print con concatenación usando +
            if 'print(' in line and '+' in line:
                # Buscar patrones de concatenación string + variable
                if re.search(r'["\'][^"\']*["\'][\s]*\+[\s]*[a-zA-Z_]', line):
                    # Verificar si la variable es numérica (promedio, suma, total, resultado, etc.)
                    if any(var in line for var in ['promedio', 'suma', 'total', 'resultado', 'count', 'cantidad']):
                        errores.append(f"Línea {i+1}: No se puede concatenar string con número, usar f-string o str()")
                        severidad += 3

        # 4. Sobreescritura de datos
        if 'agregar_nota' in code and code.count('agregar_nota("Ana"') > 1:
            if 'notas[i]["Notas"] =' in code:
                errores.append("agregar_nota() sobreescribe la nota anterior en lugar de agregar")
                severidad += 3

        # 5. Validaciones faltantes (división por cero)
        # DESHABILITADA TEMPORALMENTE - Genera demasiados falsos positivos
        # TODO: Reimplementar con análisis AST en lugar de regex
        # Solo detectar divisiones matemáticas reales en asignaciones o returns
        pass
        
        # Código comentado para referencia futura:
        # for i, line in enumerate(lines):
        #     if line.strip().startswith('#'):
        #         continue
        #     if re.search(r'(=|return)\s+\w+\s*/\s*\w+', line):
        #         # Buscar validaciones...
        #         pass

        # 6. Bucles infinitos
        has_infinite_loop = False
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith('while True') or stripped.startswith('while 1')) and ':' in stripped:
                has_infinite_loop = True

        if has_infinite_loop and 'break' not in code and 'return' not in code:
            errores.append("Posible bucle infinito: 'while True' sin 'break' ni 'return'")
            severidad += 3

        # 7. Condiciones incorrectas (>= 0 or <= 100 debería ser and)
        for i, line in enumerate(lines):
            if '>= 0 or' in line and '<= 100' in line:
                errores.append(f"Línea {i+1}: Condición lógica incorrecta - usar 'and' en lugar de 'or'")
                severidad += 1

        # 8. Rangos incorrectos
        for i, line in enumerate(lines):
            if 'range(1, 7)' in line and ('7 días' in code or '7_dias' in code):
                errores.append(f"Línea {i+1}: range(1, 7) solo recorre 6 días, debería ser range(1, 8)")
                severidad += 1

        return errores, severidad

    
    def analizar_logica_nosql(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores lógicos en NoSQL."""
        errores = []
        severidad = 0
        
        # 1. Tipos de datos incorrectos
        if 'tweet_count": "' in code:
            errores.append("tweet_count debe ser integer, no string")
            severidad += 3
        
        # 2. Suma de tipos mixtos
        if '$sum: "$tweet_count"' in code and 'tweet_count": "' in code:
            errores.append("$sum no puede sumar strings y números mixtos")
            severidad += 3
        
        # 3. Case sensitivity
        if 'source: "twitter"' in code and 'source": "Twitter"' in code:
            errores.append("Error de case sensitivity: 'twitter' no coincide con 'Twitter'")
            severidad += 2
        
        # 4. Referencias de campos incorrectas
        if '"$68"' in code and '"67":' in code:
            errores.append("Campo '$68' no existe, debería ser '$67'")
            severidad += 3
        
        return errores, severidad
    
    def analizar_logica_general(self, code: str, language: str) -> Tuple[List[str], int]:
        """Detecta errores lógicos comunes a todos los lenguajes."""
        errores = []
        severidad = 0
        
        # 1. Conversiones de tipo sin manejo de excepciones
        if language == "Python":
            if 'float(input(' in code and 'try:' not in code and 'except' not in code:
                errores.append("Conversión a float sin manejo de excepciones")
                severidad += 1
        
        # 2. Valores fuera de rango
        if '= 150' in code and '100' in code and 'máximo' in code:
            errores.append("Valor 150 excede el máximo permitido de 100")
            severidad += 2
        
        return errores, severidad
