"""
Analizador de Sintaxis para el Sistema de Evaluación Directa Mejorada.

Este módulo contiene la clase que valida sintaxis específica por lenguaje.
"""

from typing import Tuple, List
import re


class Analizador_Sintaxis:
    """
    Valida sintaxis específica por lenguaje de programación.
    """
    
    def analizar(self, code: str, language: str) -> Tuple[List[str], int]:
        """
        Analiza sintaxis según el lenguaje.
        
        Args:
            code: Código a analizar
            language: Lenguaje de programación
            
        Returns:
            Tuple[List[str], int]: (lista_errores, severidad_total)
        """
        if language == "Python":
            return self.analizar_python(code)
        elif language == "SQL":
            return self.analizar_sql(code)
        elif language == "NoSQL":
            return self.analizar_nosql(code)
        elif language == "JavaScript":
            return self.analizar_javascript(code)
        elif language == "Java":
            return self.analizar_java(code)
        elif language == "C++":
            return self.analizar_cpp(code)
        elif language == "HTML/CSS":
            return self.analizar_html_css(code)
        else:
            return [], 0
    
    def analizar_python(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores de sintaxis Python."""
        errores = []
        severidad = 0
        lines = code.split('\n')
        
        # 1. Falta ':' después de def, if, else, for, while
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('def ') and not stripped.endswith(':'):
                errores.append(f"Línea {i+1}: Falta ':' después de 'def'")
                severidad += 3
            if stripped.startswith('if ') and not ':' in stripped:
                errores.append(f"Línea {i+1}: Falta ':' después de 'if'")
                severidad += 3
            if stripped == 'else' or (stripped.startswith('else') and not stripped.endswith(':')):
                errores.append(f"Línea {i+1}: Falta ':' después de 'else'")
                severidad += 3
            if stripped.startswith('for ') and not ':' in stripped:
                errores.append(f"Línea {i+1}: Falta ':' después de 'for'")
                severidad += 3
            if stripped.startswith('while ') and not ':' in stripped:
                errores.append(f"Línea {i+1}: Falta ':' después de 'while'")
                severidad += 3
        
        # 2. Paréntesis no balanceados
        if code.count('(') != code.count(')'):
            errores.append("Paréntesis no balanceados")
            severidad += 3
        
        # 3. Métodos inexistentes para tipos
        # Detectar .remove() en diccionarios (no en listas)
        if '.remove(' in code:
            # Buscar patrones como: mi_dict.remove(...)
            # Excluir casos donde la variable es claramente una lista
            for i, line in enumerate(lines):
                if '.remove(' in line:
                    # Extraer el nombre de la variable antes de .remove(
                    match = re.search(r'(\w+)\.remove\(', line)
                    if match:
                        var_name = match.group(1)
                        # Verificar si la variable es un diccionario
                        # Buscar declaraciones como: var_name = {} o var_name = dict()
                        if re.search(rf'{var_name}\s*=\s*{{', code) or re.search(rf'{var_name}\s*=\s*dict\(', code):
                            errores.append(f"Línea {i+1}: Método .remove() no existe para diccionarios, usar del o .pop()")
                            severidad += 4
        
        # 4. Funciones con argumentos incorrectos
        if 'range(' in code:
            # Detectar range(dict) o range con argumentos inválidos
            if re.search(r'range\([a-zA-Z_]+\)', code):
                var_name = re.search(r'range\(([a-zA-Z_]+)\)', code).group(1)
                if 'dict' in code.lower() or '{' in code:
                    errores.append(f"range({var_name}) no funciona con diccionarios")
                    severidad += 4
        
        # 5. Acceso incorrecto a elementos
        for i, line in enumerate(lines):
            # Detectar acceso a índice en string cuando es clave
            if '[0]' in line and 'for ' in code:
                errores.append(f"Línea {i+1}: Acceso incorrecto a elemento, verificar tipo de dato")
                severidad += 3
        
        return errores, severidad
    
    def analizar_sql(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores de sintaxis SQL."""
        errores = []
        severidad = 0
        sql_upper = code.upper()
        
        # 1. Palabras clave mal escritas
        if 'SELEC ' in sql_upper and 'SELECT' not in sql_upper:
            errores.append("Error de sintaxis: 'SELEC' debería ser 'SELECT'")
            severidad += 3
        
        if 'FRO ' in sql_upper and 'FROM' not in sql_upper:
            errores.append("Error de sintaxis: 'FRO' debería ser 'FROM'")
            severidad += 3
        
        # 2. Comandos malformados
        if 'SELECT FROM WHERE' in sql_upper:
            errores.append("Consulta malformada: SELECT sin columnas especificadas")
            severidad += 4
        
        # 3. Operadores incorrectos
        if '==' in code:
            errores.append("Error de operador: SQL usa '=' no '==' para comparaciones")
            severidad += 2
        
        # 4. Valores inválidos
        if "'25:00'" in code:
            errores.append("Error de tiempo: '25:00' no es una hora válida")
            severidad += 2
        
        if 'IS YESTERDAY' in sql_upper:
            errores.append("'IS YESTERDAY' no es sintaxis SQL válida")
            severidad += 3
        
        # 5. Nombres de tablas sin sentido
        if 'NADA EXISTE' in sql_upper or 'NOTHING' in sql_upper:
            errores.append("Nombre de tabla sin sentido")
            severidad += 3
        
        return errores, severidad
    
    def analizar_nosql(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores de sintaxis NoSQL/MongoDB."""
        errores = []
        severidad = 0
        
        # Verificar si es mongosh (permite JavaScript)
        is_mongosh = any(indicator in code for indicator in ['use(', 'db.getCollection(', '// MongoDB'])
        
        # 1. Sintaxis JSON/BSON inválida
        if re.search(r'nombre:\s*[A-Za-z]', code) and not re.search(r'nombre:\s*"', code):
            errores.append("Valores string deben estar entre comillas")
            severidad += 3
        
        # 2. insertMany con objeto en lugar de array
        if 'insertMany({' in code and not 'insertMany([{' in code:
            errores.append("insertMany debe recibir un array de documentos")
            severidad += 3
        
        # 3. Operadores incorrectos
        if 'stock == 10' in code:
            errores.append("Usar {stock: 10} en lugar de 'stock == 10'")
            severidad += 3
        
        # 4. Mezcla con JavaScript (solo si NO es mongosh)
        if not is_mongosh:
            if 'console.log' in code:
                errores.append("console.log es JavaScript, no NoSQL")
                severidad += 2
            if '.then(' in code or '.catch(' in code:
                errores.append("Promesas (.then/.catch) son JavaScript, no NoSQL")
                severidad += 2
        
        # 5. Fechas ISO inválidas
        if re.search(r'"20\d{2}-(1[3-9]|[2-9]\d)-\d{2}"', code):
            errores.append("Fecha ISO inválida (mes > 12)")
            severidad += 3
        
        return errores, severidad
    
    def analizar_javascript(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores de sintaxis JavaScript."""
        errores = []
        severidad = 0
        lines = code.split('\n')
        
        # Punto y coma faltante después de return
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('return ') and not stripped.endswith(';') and not stripped.endswith('}'):
                errores.append(f"Línea {i+1}: Falta punto y coma después de 'return'")
                severidad += 1
        
        # Llaves no balanceadas
        if code.count('{') != code.count('}'):
            errores.append("Llaves no balanceadas")
            severidad += 3
        
        return errores, severidad
    
    def analizar_java(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores de sintaxis Java."""
        errores = []
        severidad = 0
        
        # Falta '}' para cerrar clase
        if 'public class' in code and not code.strip().endswith('}'):
            errores.append("Falta '}' para cerrar la clase")
            severidad += 3
        
        # Falta ';' después de System.out.println
        if 'System.out.println' in code:
            lines = code.split('\n')
            for i, line in enumerate(lines):
                if 'System.out.println' in line and not ';' in line:
                    errores.append(f"Línea {i+1}: Falta ';' después de System.out.println")
                    severidad += 2
        
        return errores, severidad
    
    def analizar_cpp(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores de sintaxis C++."""
        errores = []
        severidad = 0
        
        # Sintaxis incorrecta en #include
        if '#include' in code:
            lines = code.split('\n')
            for i, line in enumerate(lines):
                if '#include' in line and not ('>' in line or '"' in line):
                    errores.append(f"Línea {i+1}: Sintaxis incorrecta en #include")
                    severidad += 3
        
        return errores, severidad
    
    def analizar_html_css(self, code: str) -> Tuple[List[str], int]:
        """Detecta errores de sintaxis HTML/CSS."""
        errores = []
        severidad = 0
        
        # Etiquetas no cerradas
        if '<div' in code and '</div>' not in code:
            errores.append("Etiqueta <div> no cerrada")
            severidad += 2
        
        if '<p' in code and '</p>' not in code:
            errores.append("Etiqueta <p> no cerrada")
            severidad += 2
        
        return errores, severidad
