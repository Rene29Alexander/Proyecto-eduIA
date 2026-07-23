# -*- coding: utf-8 -*-
"""
Unit Tests para el Analizador de Lógica.
Usa inputs que realmente activan los detectores implementados.

Ejecutar con:
    pytest tests/test_analizador_logica.py -v
"""

import pytest
from evaluacion.analizador_logica import Analizador_Logica


class TestAnalizadorLogicaPython:
    """Tests para análisis de lógica Python."""

    def setup_method(self):
        self.analizador = Analizador_Logica()

    def test_python_bucle_infinito_sin_break(self):
        """Detecta while True sin break ni return."""
        code = "while True:\n    print('hola')"
        errores, severidad = self.analizador.analizar_logica_python(code)
        assert len(errores) > 0
        assert any("bucle" in e.lower() or "infinito" in e.lower() for e in errores)

    def test_python_bucle_infinito_con_break_es_valido(self):
        """while True con break no debe generar error de bucle infinito."""
        code = "while True:\n    x = input()\n    if x == 'q':\n        break"
        errores, severidad = self.analizador.analizar_logica_python(code)
        assert not any("bucle" in e.lower() or "infinito" in e.lower() for e in errores)

    def test_python_condicion_or_incorrecta(self):
        """Detecta >= 0 or <= 100 (debe ser and)."""
        code = "if x >= 0 or x <= 100:\n    print('válido')"
        errores, severidad = self.analizador.analizar_logica_python(code)
        assert len(errores) > 0
        assert any("and" in e.lower() or "or" in e.lower() for e in errores)

    def test_python_range_incorrecto_7_dias(self):
        """Detecta range(1,7) cuando el comentario indica 7 días."""
        code = "# Procesar 7 días\nfor dia in range(1, 7):\n    print(dia)"
        errores, severidad = self.analizador.analizar_logica_python(code)
        assert len(errores) > 0
        assert any("range" in e.lower() or "días" in e.lower() for e in errores)

    def test_python_variable_flor_vs_flores(self):
        """Detecta 'in flor:' cuando la variable correcta es 'flores'."""
        code = "flores = ['Rosa', 'Tulipán']\nfor f in flores:\n    if f in flor:\n        print(f)"
        errores, severidad = self.analizador.analizar_logica_python(code)
        assert len(errores) > 0

    def test_python_concatenacion_string_numero(self):
        """Detecta concatenación de string con número sin str()."""
        code = "promedio = 8.5\nprint('Promedio: ' + promedio)"
        errores, severidad = self.analizador.analizar_logica_python(code)
        assert len(errores) > 0

    def test_python_codigo_limpio_no_genera_errores(self):
        """Código Python limpio no genera errores lógicos."""
        code = (
            "def suma(a, b):\n"
            "    return a + b\n\n"
            "resultado = suma(3, 4)\n"
            "print(resultado)\n"
        )
        errores, severidad = self.analizador.analizar_logica_python(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorLogicaNoSQL:
    """Tests para análisis de lógica NoSQL."""

    def setup_method(self):
        self.analizador = Analizador_Logica()

    def test_nosql_tweet_count_como_string(self):
        """Detecta tweet_count guardado como string en lugar de integer."""
        # El detector busca exactamente: tweet_count": "
        code = 'db.tweets.insertOne({tweet_count: "100", user: "Ana"})'
        # Construir el string con el patrón exacto que detecta el analizador
        code2 = '{"tweet_count": "100"}'
        errores, severidad = self.analizador.analizar_logica_nosql(code2)
        assert len(errores) > 0
        assert any("tweet_count" in e.lower() or "integer" in e.lower() for e in errores)

    def test_nosql_case_sensitivity_twitter(self):
        """Detecta discrepancia Twitter vs twitter."""
        code = (
            'db.tweets.find({source: "twitter"})\n'
            '// Datos tienen source": "Twitter" con mayúscula'
        )
        errores, severidad = self.analizador.analizar_logica_nosql(code)
        assert len(errores) > 0

    def test_nosql_referencia_campo_erronea(self):
        """Detecta referencia al campo '$68' cuando debería ser '$67'."""
        code = (
            'db.collection.aggregate([{$project: {value: "$68"}}])\n'
            '// Correcto: "67": "valor_campo"'
        )
        errores, severidad = self.analizador.analizar_logica_nosql(code)
        assert len(errores) > 0

    def test_nosql_codigo_valido_no_genera_errores(self):
        """NoSQL lógicamente correcto no genera errores."""
        code = "db.productos.find({stock: {$gt: 0}}).sort({nombre: 1})"
        errores, severidad = self.analizador.analizar_logica_nosql(code)
        assert len(errores) == 0
        assert severidad == 0


class TestAnalizadorLogicaGeneral:
    """Tests para analizar_logica_general() — requiere parámetro language."""

    def setup_method(self):
        self.analizador = Analizador_Logica()

    def test_general_float_input_sin_try_except(self):
        """Detecta float(input(...)) sin bloque try/except."""
        code = "x = float(input('Número: '))\nprint(x)"
        errores, severidad = self.analizador.analizar_logica_general(code, "Python")
        assert len(errores) > 0
        assert any("float" in e.lower() or "conversión" in e.lower() or "excepción" in e.lower()
                   for e in errores)

    def test_general_valor_fuera_rango(self):
        """Detecta valor 150 cuando el máximo permitido es 100."""
        code = "edad = 150  # máximo permitido: 100"
        errores, severidad = self.analizador.analizar_logica_general(code, "Python")
        assert len(errores) > 0
        assert any("150" in e or "rango" in e.lower() for e in errores)

    def test_general_codigo_valido_no_genera_errores(self):
        """Código sin problemas lógicos generales no genera errores."""
        code = "x = 50\nprint(x)"
        errores, severidad = self.analizador.analizar_logica_general(code, "Python")
        assert len(errores) == 0
        assert severidad == 0

    def test_general_no_falla_con_otros_lenguajes(self):
        """analizar_logica_general no crashea con lenguajes no-Python."""
        code = "SELECT * FROM tabla"
        errores, severidad = self.analizador.analizar_logica_general(code, "SQL")
        assert isinstance(errores, list)
        assert isinstance(severidad, int)


class TestMetodoAnalizar:
    """Tests del método analizar() que despacha por lenguaje."""

    def setup_method(self):
        self.analizador = Analizador_Logica()

    def test_analizar_python_bucle_infinito(self):
        """analizar() con Python detecta bucle infinito."""
        code = "while True:\n    x = 1"
        errores, severidad = self.analizador.analizar(code, "Python")
        assert len(errores) > 0

    def test_analizar_nosql_tipo_incorrecto(self):
        """analizar() con NoSQL detecta tipo de dato incorrecto."""
        code = '{"tweet_count": "100"}'
        errores, severidad = self.analizador.analizar(code, "NoSQL")
        assert len(errores) > 0

    def test_analizar_python_valido(self):
        """analizar() con código Python válido retorna sin errores."""
        code = "def f(x):\n    return x * 2\nprint(f(5))"
        errores, severidad = self.analizador.analizar(code, "Python")
        assert len(errores) == 0
        assert severidad == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
