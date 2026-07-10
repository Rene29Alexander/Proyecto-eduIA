"""
Unit Tests para el Analizador de Sintaxis.

Este módulo contiene tests específicos para cada lenguaje soportado.
"""

import pytest
from evaluacion.analizador_sintaxis import Analizador_Sintaxis


class TestAnalizadorPython:
    """Tests para análisis de sintaxis Python."""
    
    def setup_method(self):
        self.analizador = Analizador_Sintaxis()
    
    def test_python_falta_dos_puntos_def(self):
        """Test: detecta falta de ':' después de def."""
        code = "def suma(a, b)\n    return a + b"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0
        assert any(":" in error.lower() for error in errores)
        assert severidad >= 3
    
    def test_python_falta_dos_puntos_if(self):
        """Test: detecta falta de ':' después de if."""
        code = "if x > 5\n    print(x)"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0
        assert any(":" in error.lower() for error in errores)
    
    def test_python_parentesis_no_balanceados(self):
        """Test: detecta paréntesis no balanceados."""
        code = "print('hola'\nresult = suma(1, 2"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0
        assert any("paréntesis" in error.lower() or "parenthes" in error.lower() for error in errores)
    
    def test_python_metodo_inexistente_dict(self):
        """Test: detecta .remove() en diccionario."""
        code = "mi_dict = {'a': 1}\nmi_dict.remove('a')"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0
        assert any("remove" in error.lower() for error in errores)
    
    def test_python_range_con_dict(self):
        """Test: detecta range() con diccionario."""
        code = "mi_dict = {'a': 1}\nfor i in range(mi_dict):\n    print(i)"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0
        assert any("range" in error.lower() for error in errores)
    
    def test_python_codigo_valido(self):
        """Test: código Python válido no genera errores."""
        code = "def suma(a, b):\n    return a + b\n\nresult = suma(1, 2)\nprint(result)"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorSQL:
    """Tests para análisis de sintaxis SQL."""
    
    def setup_method(self):
        self.analizador = Analizador_Sintaxis()
    
    def test_sql_select_mal_escrito(self):
        """Test: detecta SELEC en lugar de SELECT."""
        code = "SELEC * FROM usuarios"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0
        assert any("selec" in error.lower() for error in errores)
    
    def test_sql_from_mal_escrito(self):
        """Test: detecta FRO en lugar de FROM."""
        code = "SELECT * FRO usuarios"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0
        assert any("fro" in error.lower() or "from" in error.lower() for error in errores)
    
    def test_sql_operador_incorrecto(self):
        """Test: detecta == en lugar de =."""
        code = "SELECT * FROM usuarios WHERE id == 1"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0
        assert any("==" in error or "operador" in error.lower() for error in errores)
    
    def test_sql_comando_malformado(self):
        """Test: detecta comandos SQL malformados."""
        code = "INSERT INTO SELECT UPDATE DELETE"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0
        assert severidad >= 3
    
    def test_sql_nombre_tabla_invalido(self):
        """Test: detecta nombres de tabla sin sentido."""
        code = "SELECT * FROM NADA EXISTE"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0
    
    def test_sql_codigo_valido(self):
        """Test: código SQL válido no genera errores."""
        code = "SELECT id, nombre FROM usuarios WHERE edad > 18 ORDER BY nombre"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorNoSQL:
    """Tests para análisis de sintaxis NoSQL."""
    
    def setup_method(self):
        self.analizador = Analizador_Sintaxis()
    
    def test_nosql_nombre_db_duplicado(self):
        """Test: detecta 'dbdb' duplicado."""
        code = "use farmacia_dbdb"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0
        assert any("dbdb" in error.lower() or "duplicado" in error.lower() for error in errores)
    
    def test_nosql_insertmany_objeto(self):
        """Test: detecta insertMany con objeto en lugar de array."""
        code = "db.productos.insertMany({nombre: 'test'})"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0
        assert any("insertmany" in error.lower() or "array" in error.lower() for error in errores)
    
    def test_nosql_string_sin_comillas(self):
        """Test: detecta strings sin comillas."""
        code = "db.productos.insertOne({nombre: Paracetamol})"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0
        assert any("comillas" in error.lower() or "string" in error.lower() for error in errores)
    
    def test_nosql_operador_incorrecto(self):
        """Test: detecta operadores incorrectos."""
        code = "db.productos.find({stock == 10})"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0
        assert any("==" in error or "operador" in error.lower() for error in errores)
    
    def test_nosql_fecha_invalida(self):
        """Test: detecta fechas inválidas."""
        code = 'db.productos.insertOne({fecha: "2026-15-03"})'
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0
        assert any("fecha" in error.lower() for error in errores)
    
    def test_nosql_codigo_valido(self):
        """Test: código NoSQL válido no genera errores."""
        code = 'db.productos.find({stock: {$gt: 0}}).sort({nombre: 1})'
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorJavaScript:
    """Tests para análisis de sintaxis JavaScript."""
    
    def setup_method(self):
        self.analizador = Analizador_Sintaxis()
    
    def test_javascript_falta_punto_coma(self):
        """Test: detecta falta de punto y coma."""
        code = "let x = 5\nlet y = 10\nreturn x + y"
        errores, severidad = self.analizador.analizar_javascript(code)
        assert len(errores) > 0
        assert any(";" in error or "punto y coma" in error.lower() for error in errores)
    
    def test_javascript_llaves_no_balanceadas(self):
        """Test: detecta llaves no balanceadas."""
        code = "function suma(a, b) {\n    return a + b"
        errores, severidad = self.analizador.analizar_javascript(code)
        assert len(errores) > 0
        assert any("llave" in error.lower() or "{" in error or "}" in error for error in errores)
    
    def test_javascript_codigo_valido(self):
        """Test: código JavaScript válido no genera errores."""
        code = "function suma(a, b) {\n    return a + b;\n}\nconst result = suma(1, 2);"
        errores, severidad = self.analizador.analizar_javascript(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorJava:
    """Tests para análisis de sintaxis Java."""
    
    def setup_method(self):
        self.analizador = Analizador_Sintaxis()
    
    def test_java_falta_llave_cierre(self):
        """Test: detecta falta de llave de cierre."""
        code = "public class Test {\n    public static void main(String[] args) {\n        System.out.println('Hola');\n    }"
        errores, severidad = self.analizador.analizar_java(code)
        assert len(errores) > 0
        assert any("}" in error or "llave" in error.lower() for error in errores)
    
    def test_java_falta_punto_coma(self):
        """Test: detecta falta de punto y coma."""
        code = "System.out.println('Hola')"
        errores, severidad = self.analizador.analizar_java(code)
        assert len(errores) > 0
        assert any(";" in error or "punto y coma" in error.lower() for error in errores)
    
    def test_java_codigo_valido(self):
        """Test: código Java válido no genera errores."""
        code = "public class Test {\n    public static void main(String[] args) {\n        System.out.println('Hola');\n    }\n}"
        errores, severidad = self.analizador.analizar_java(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorCPP:
    """Tests para análisis de sintaxis C++."""
    
    def setup_method(self):
        self.analizador = Analizador_Sintaxis()
    
    def test_cpp_include_incorrecto(self):
        """Test: detecta sintaxis incorrecta en #include."""
        code = "#include iostream\nint main() { return 0; }"
        errores, severidad = self.analizador.analizar_cpp(code)
        assert len(errores) > 0
        assert any("include" in error.lower() for error in errores)
    
    def test_cpp_codigo_valido(self):
        """Test: código C++ válido no genera errores."""
        code = "#include <iostream>\nint main() {\n    std::cout << 'Hola';\n    return 0;\n}"
        errores, severidad = self.analizador.analizar_cpp(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorHTMLCSS:
    """Tests para análisis de sintaxis HTML/CSS."""
    
    def setup_method(self):
        self.analizador = Analizador_Sintaxis()
    
    def test_html_etiqueta_no_cerrada(self):
        """Test: detecta etiquetas HTML no cerradas."""
        code = "<div><p>Hola</p>"
        errores, severidad = self.analizador.analizar_html_css(code)
        assert len(errores) > 0
        assert any("div" in error.lower() or "cerrada" in error.lower() for error in errores)
    
    def test_html_codigo_valido(self):
        """Test: código HTML válido no genera errores."""
        code = "<div><p>Hola</p></div>"
        errores, severidad = self.analizador.analizar_html_css(code)
        assert len(errores) == 0
        assert severidad == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
