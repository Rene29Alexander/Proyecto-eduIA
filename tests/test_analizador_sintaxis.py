# -*- coding: utf-8 -*-
"""
Unit Tests para el Analizador de Sintaxis.
Prueba cada lenguaje soportado con inputs que realmente activan los detectores.

Ejecutar con:
    pytest tests/test_analizador_sintaxis.py -v
"""

import pytest
from evaluacion.analizador_sintaxis import Analizador_Sintaxis


class TestAnalizadorPython:
    """Tests para análisis de sintaxis Python."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_python_falta_dos_puntos_def(self):
        """Detecta falta de ':' después de def."""
        code = "def suma(a, b)\n    return a + b"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0
        assert severidad > 0

    def test_python_falta_dos_puntos_if(self):
        """Detecta falta de ':' después de if."""
        code = "if x > 5\n    print(x)"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0

    def test_python_parentesis_no_balanceados(self):
        """Detecta paréntesis no balanceados."""
        code = "print('hola'\nresult = suma(1, 2"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0

    def test_python_codigo_valido_no_genera_errores(self):
        """Código Python correcto no genera errores."""
        code = "def suma(a, b):\n    return a + b\n\nresult = suma(1, 2)\nprint(result)"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) == 0
        assert severidad == 0

    def test_python_metodo_inexistente_dict(self):
        """Detecta .remove() en diccionario."""
        code = "mi_dict = {'a': 1}\nmi_dict.remove('a')"
        errores, severidad = self.analizador.analizar_python(code)
        assert len(errores) > 0


class TestAnalizadorSQL:
    """Tests para análisis de sintaxis SQL."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_sql_select_mal_escrito(self):
        """Detecta SELEC en lugar de SELECT."""
        code = "SELEC * FROM usuarios"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0

    def test_sql_from_mal_escrito(self):
        """Detecta FRO en lugar de FROM."""
        code = "SELECT * FRO usuarios"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0

    def test_sql_operador_igual_doble(self):
        """Detecta == en lugar de = en SQL."""
        code = "SELECT * FROM usuarios WHERE id == 1"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) > 0

    def test_sql_codigo_valido_no_genera_errores(self):
        """SQL correcto no genera errores."""
        code = "SELECT id, nombre FROM usuarios WHERE edad > 18 ORDER BY nombre"
        errores, severidad = self.analizador.analizar_sql(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorNoSQL:
    """Tests para análisis de sintaxis NoSQL."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_nosql_insertmany_con_objeto(self):
        """Detecta insertMany con objeto en lugar de array."""
        code = "db.productos.insertMany({nombre: 'test'})"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0

    def test_nosql_string_sin_comillas(self):
        """Detecta strings sin comillas en valor de campo."""
        code = "db.productos.insertOne({nombre: Paracetamol})"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0

    def test_nosql_operador_igual_doble(self):
        """Detecta operador == incorrecto en NoSQL."""
        code = "db.productos.find({stock == 10})"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) > 0

    def test_nosql_codigo_valido_no_genera_errores(self):
        """NoSQL correcto no genera errores."""
        code = "db.productos.find({stock: {$gt: 0}}).sort({nombre: 1})"
        errores, severidad = self.analizador.analizar_nosql(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorJavaScript:
    """Tests para análisis de sintaxis JavaScript."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_javascript_falta_punto_coma(self):
        """Detecta falta de punto y coma."""
        code = "let x = 5\nlet y = 10\nreturn x + y"
        errores, severidad = self.analizador.analizar_javascript(code)
        assert len(errores) > 0

    def test_javascript_llaves_no_balanceadas(self):
        """Detecta llaves no balanceadas."""
        code = "function suma(a, b) {\n    return a + b"
        errores, severidad = self.analizador.analizar_javascript(code)
        assert len(errores) > 0

    def test_javascript_codigo_valido_no_genera_errores(self):
        """JavaScript correcto no genera errores."""
        code = "function suma(a, b) {\n    return a + b;\n}\nconst result = suma(1, 2);"
        errores, severidad = self.analizador.analizar_javascript(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorJava:
    """Tests para análisis de sintaxis Java."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_java_falta_punto_coma(self):
        """Detecta falta de punto y coma en Java."""
        code = "System.out.println('Hola')"
        errores, severidad = self.analizador.analizar_java(code)
        assert len(errores) > 0

    def test_java_falta_punto_coma_en_println(self):
        """Detecta falta de punto y coma en System.out.println."""
        code = "public class Test {\n    public static void main(String[] args) {\n        System.out.println(\"Hola\")\n    }\n}"
        errores, severidad = self.analizador.analizar_java(code)
        assert len(errores) > 0
        assert severidad > 0

    def test_java_codigo_valido_no_genera_errores(self):
        """Java correcto no genera errores."""
        code = "public class Test {\n    public static void main(String[] args) {\n        System.out.println(\"Hola\");\n    }\n}"
        errores, severidad = self.analizador.analizar_java(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorCPP:
    """Tests para análisis de sintaxis C++."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_cpp_include_sin_angulos(self):
        """Detecta #include sin <> o comillas."""
        code = "#include iostream\nint main() { return 0; }"
        errores, severidad = self.analizador.analizar_cpp(code)
        assert len(errores) > 0

    def test_cpp_codigo_valido_no_genera_errores(self):
        """C++ correcto no genera errores."""
        code = "#include <iostream>\nint main() {\n    return 0;\n}"
        errores, severidad = self.analizador.analizar_cpp(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorHTMLCSS:
    """Tests para análisis de sintaxis HTML/CSS."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_html_etiqueta_no_cerrada(self):
        """Detecta etiquetas HTML no cerradas."""
        code = "<div><p>Hola</p>"
        errores, severidad = self.analizador.analizar_html_css(code)
        assert len(errores) > 0

    def test_html_codigo_valido_no_genera_errores(self):
        """HTML correcto no genera errores."""
        code = "<div><p>Hola</p></div>"
        errores, severidad = self.analizador.analizar_html_css(code)
        assert len(errores) == 0
        assert severidad == 0


class TestMetodoGeneral:
    """Tests del método analizar() que despacha por lenguaje."""

    def setup_method(self):
        self.analizador = Analizador_Sintaxis()

    def test_analizar_despacha_python(self):
        """analizar() con Python llama al analizador correcto."""
        code = "def f(x)\n    return x"
        errores, severidad = self.analizador.analizar(code, "Python")
        assert len(errores) > 0

    def test_analizar_despacha_sql(self):
        """analizar() con SQL llama al analizador correcto."""
        code = "SELEC * FROM tabla"
        errores, severidad = self.analizador.analizar(code, "SQL")
        assert len(errores) > 0

    def test_analizar_codigo_valido_python(self):
        """analizar() con Python válido retorna sin errores."""
        code = "def suma(a, b):\n    return a + b"
        errores, severidad = self.analizador.analizar(code, "Python")
        assert len(errores) == 0
        assert severidad == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
