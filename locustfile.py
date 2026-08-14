# -*- coding: utf-8 -*-
"""
locustfile.py — Pruebas de carga y estrés para EduIA API
Semana 5: Medición de rendimiento (línea base)

Escenarios:
  LightUser   — /health + /metadata                  (peso 2)
  StudentUser — /api/evaluate + /api/courses/generate (peso 5)
  ChatUser    — /api/chat/ask                         (peso 2)
  HeavyUser   — payloads grandes                      (peso 1)
  InvalidUser — entradas inválidas → espera 422       (peso 1)

Cómo correr
-----------
# UI interactiva (recomendado para capturas del informe):
  locust -f locustfile.py --host http://127.0.0.1:8000

# Headless con 20 usuarios mínimos (requisito de rúbrica):
  locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 2 -t 60s --html reporte_estres.html --csv reporte_estres

# Prueba de estrés completa 200 usuarios:
  locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 200 -r 10 -t 90s --html reporte_estres_200u.html --csv reporte_estres_200u
"""

import random
from locust import HttpUser, task, between, events


# =============================================================================
# Datos de prueba
# =============================================================================

PYTHON_SNIPPETS = [
    "def suma(a, b):\n    return a + b",
    "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)",
    "lista = [1, 2, 3]\nresultado = sum(lista)\nprint(resultado)",
    "for i in range(10):\n    if i % 2 == 0:\n        print(i)",
    "class Persona:\n    def __init__(self, nombre):\n        self.nombre = nombre\n    def saludar(self):\n        return f'Hola, soy {self.nombre}'",
]

JS_SNIPPETS = [
    "function suma(a, b) { return a + b; }",
    "const arr = [1,2,3]; const sum = arr.reduce((a,b)=>a+b,0);",
    "async function fetchData(url) { const r = await fetch(url); return r.json(); }",
]

CONTEXT_SAMPLE = (
    "Python es un lenguaje de programación interpretado de alto nivel. "
    "Sus características principales incluyen: sintaxis clara y legible, "
    "tipado dinámico, gestión automática de memoria, y una extensa biblioteca estándar. "
    "Las estructuras de datos más usadas son: listas (list), tuplas (tuple), "
    "diccionarios (dict) y conjuntos (set). Las estructuras de control incluyen "
    "if/elif/else para condicionales, y for/while para ciclos. "
    "Las funciones se definen con 'def' y pueden retornar valores con 'return'. "
    "Las clases se definen con 'class' y usan '__init__' como constructor."
)

QUESTIONS = [
    "¿Qué es una lista en Python?",
    "¿Cómo funciona un diccionario?",
    "¿Cuál es la diferencia entre una tupla y una lista?",
    "¿Qué es el tipado dinámico?",
    "¿Cómo se define una función en Python?",
    "¿Para qué sirve el método __init__?",
]


# =============================================================================
# Escenario 1 — LightUser: endpoints de sistema
# =============================================================================

class LightUser(HttpUser):
    """Simula usuarios que solo verifican salud y metadatos del servicio."""
    weight = 2
    wait_time = between(0.5, 2.0)

    @task(3)
    def health_check(self):
        with self.client.get("/health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check falló: {resp.status_code}")

    @task(1)
    def get_metadata(self):
        with self.client.get("/metadata", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Metadata falló: {resp.status_code}")


# =============================================================================
# Escenario 2 — StudentUser: flujos principales de estudiante
# =============================================================================

class StudentUser(HttpUser):
    """Simula estudiantes evaluando código y generando cursos."""
    weight = 5
    wait_time = between(1.0, 3.0)

    @task(3)
    def evaluate_python(self):
        payload = {
            "code": random.choice(PYTHON_SNIPPETS),
            "language": "python",
            "criteria": "Evalúa corrección, buenas prácticas y claridad del código.",
        }
        with self.client.post("/api/evaluate", json=payload, catch_response=True) as resp:
            if resp.status_code in (200, 503):
                resp.success()  # 503 = Gemini no disponible, es esperado sin key
            elif resp.status_code == 429:
                resp.success()  # rate limit diseñado
            else:
                resp.failure(f"evaluate_code inesperado: {resp.status_code} — {resp.text[:200]}")

    @task(2)
    def evaluate_javascript(self):
        payload = {
            "code": random.choice(JS_SNIPPETS),
            "language": "javascript",
            "criteria": "Evalúa la lógica y estilo del código JavaScript.",
        }
        with self.client.post("/api/evaluate", json=payload, catch_response=True) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"evaluate_js inesperado: {resp.status_code}")

    @task(1)
    def generate_course(self):
        payload = {
            "language": random.choice(["python", "javascript", "java", "sql"]),
            "level": random.choice(["principiante", "intermedio", "avanzado"]),
            "sections_count": random.randint(3, 7),
        }
        with self.client.post(
            "/api/courses/generate", json=payload, catch_response=True, timeout=120
        ) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"generate_course inesperado: {resp.status_code}")


# =============================================================================
# Escenario 3 — ChatUser: chat educativo
# =============================================================================

class ChatUser(HttpUser):
    """Simula estudiantes haciendo preguntas al chat IA."""
    weight = 2
    wait_time = between(2.0, 5.0)

    @task
    def ask_question(self):
        payload = {
            "context": CONTEXT_SAMPLE,
            "question": random.choice(QUESTIONS),
        }
        with self.client.post(
            "/api/chat/ask", json=payload, catch_response=True, timeout=120
        ) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"chat_ask inesperado: {resp.status_code} — {resp.text[:200]}")


# =============================================================================
# Escenario 4 — HeavyUser: payloads grandes
# =============================================================================

class HeavyUser(HttpUser):
    """Simula cargas pesadas con código largo y contextos extensos."""
    weight = 1
    wait_time = between(3.0, 8.0)

    @task(1)
    def evaluate_large_code(self):
        large_code = "\n".join([
            f"def funcion_{i}(x):",
            f"    '''Función {i} de prueba'''",
            f"    resultado = x * {i}",
            f"    if resultado > 100:",
            f"        return resultado // 2",
            f"    return resultado",
            "",
        ] for i in range(50))
        large_code = "\n".join(large_code) if isinstance(large_code, list) else large_code

        payload = {
            "code": large_code if isinstance(large_code, str) else str(large_code),
            "language": "python",
            "criteria": "Evalúa este módulo completo de funciones.",
        }
        with self.client.post("/api/evaluate", json=payload, catch_response=True, timeout=120) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"evaluate_large inesperado: {resp.status_code}")

    @task(1)
    def chat_long_context(self):
        long_context = (CONTEXT_SAMPLE + " ") * 20  # ~3000 chars
        payload = {
            "context": long_context,
            "question": "Resume los conceptos más importantes de este material.",
        }
        with self.client.post("/api/chat/ask", json=payload, catch_response=True, timeout=120) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"chat_long inesperado: {resp.status_code}")


# =============================================================================
# Escenario 5 — InvalidUser: validación de entradas incorrectas
# =============================================================================

class InvalidUser(HttpUser):
    """Envía entradas inválidas para verificar que la API retorna 422 correctamente."""
    weight = 1
    wait_time = between(1.0, 3.0)

    @task(2)
    def invalid_language(self):
        payload = {
            "code": "print('hello')",
            "language": "cobol",  # lenguaje no soportado
        }
        with self.client.post("/api/evaluate", json=payload, catch_response=True) as resp:
            if resp.status_code == 422:
                resp.success()  # comportamiento esperado
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422, recibí: {resp.status_code}")

    @task(1)
    def empty_code(self):
        payload = {
            "code": "   ",  # solo espacios
            "language": "python",
        }
        with self.client.post("/api/evaluate", json=payload, catch_response=True) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por código vacío, recibí: {resp.status_code}")

    @task(1)
    def missing_required_field(self):
        payload = {"language": "python"}  # falta 'code'
        with self.client.post("/api/evaluate", json=payload, catch_response=True) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por campo faltante, recibí: {resp.status_code}")

    @task(1)
    def short_context_chat(self):
        payload = {
            "context": "muy corto",  # menos de 50 chars
            "question": "¿Qué es Python?",
        }
        with self.client.post("/api/chat/ask", json=payload, catch_response=True) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por contexto corto, recibí: {resp.status_code}")


# =============================================================================
# Eventos — métricas adicionales en consola
# =============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "=" * 60)
    print("  EduIA — Prueba de carga iniciada")
    print("  Endpoint base:", environment.host)
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats.total
    print("\n" + "=" * 60)
    print("  EduIA — Resultados de la prueba")
    print(f"  Requests totales : {stats.num_requests}")
    print(f"  Fallos           : {stats.num_failures}")
    print(f"  RPS promedio     : {stats.current_rps:.1f}")
    print(f"  p50 (ms)         : {stats.get_response_time_percentile(0.50)}")
    print(f"  p95 (ms)         : {stats.get_response_time_percentile(0.95)}")
    print(f"  Máximo (ms)      : {stats.max_response_time}")
    print(f"  Tasa de error    : {stats.fail_ratio * 100:.1f}%")
    print("=" * 60 + "\n")
