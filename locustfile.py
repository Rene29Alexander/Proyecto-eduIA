# -*- coding: utf-8 -*-
"""
locustfile.py — Pruebas de carga y estrés para EduIA API
Semana 5: Medición de rendimiento (línea base)

Escenarios:
  LightUser   — /health + /metadata                   (peso 2)
  StudentUser — /api/evaluate + /api/courses/generate  (peso 5)
  ChatUser    — /api/chat/ask con historial             (peso 2)
  HeavyUser   — payloads grandes y máx. secciones      (peso 1)
  InvalidUser — entradas inválidas → espera 422         (peso 1)

Cómo correr
-----------
# UI interactiva (recomendado para capturas del informe):
  locust -f locustfile.py --host http://127.0.0.1:8000

# Headless con 20 usuarios mínimos (requisito de rúbrica):
  locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 2 -t 60s --html reporte_estres.html --csv reporte_estres

# Prueba de estrés completa 200 usuarios:
  locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 200 -r 10 -t 90s --html reporte_estres_200u.html --csv reporte_estres_200u

Filtrar por tipo de prueba:
  locust --tags system      → solo health/metadata
  locust --tags ai          → solo endpoints IA
  locust --tags validation  → solo casos inválidos
"""

import random
from locust import HttpUser, task, between, tag, events


# =============================================================================
# Datos de prueba
# =============================================================================

LANGUAGES = ["python", "javascript", "java", "sql", "c++"]
LEVELS    = ["principiante", "intermedio", "avanzado"]

PYTHON_SNIPPETS = [
    "def suma(a, b):\n    return a + b\n\nprint(suma(3, 5))",
    "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)\n\nprint(factorial(5))",
    "numeros = [1, 2, 3, 4, 5]\ntotal = sum(numeros)\npromedio = total / len(numeros)\nprint(promedio)",
    "for i in range(10):\n    if i % 2 == 0:\n        print(f'{i} es par')",
    "class Persona:\n    def __init__(self, nombre):\n        self.nombre = nombre\n    def saludar(self):\n        return f'Hola, soy {self.nombre}'",
    # código con error intencional para probar detección
    "def divide(a, b):\n    return a / b\n\nprint(divide(10, 0))",
]

JS_SNIPPETS = [
    "function suma(a, b) {\n  return a + b;\n}\nconsole.log(suma(2, 3));",
    "const arr = [1,2,3,4,5];\nconst dobles = arr.map(x => x * 2);\nconsole.log(dobles);",
    "async function fetchData(url) {\n  const res = await fetch(url);\n  return res.json();\n}",
]

JAVA_SNIPPETS = [
    "public class Hola {\n    public static void main(String[] args) {\n        System.out.println(\"Hola mundo\");\n    }\n}",
]

SQL_SNIPPETS = [
    "SELECT nombre, apellido FROM usuarios WHERE activo = 1 ORDER BY nombre ASC;",
    "SELECT c.nombre, COUNT(e.estudiante_id) AS total\nFROM cursos c\nLEFT JOIN inscripciones e ON c.id = e.curso_id\nGROUP BY c.nombre;",
]

CODE_SAMPLES = {
    "python":     PYTHON_SNIPPETS,
    "javascript": JS_SNIPPETS,
    "java":       JAVA_SNIPPETS,
    "sql":        SQL_SNIPPETS,
    "c++":        ["#include <iostream>\nint main() {\n    std::cout << \"Hola\" << std::endl;\n    return 0;\n}"],
}

CRITERIA_SAMPLES = [
    "Evalúa corrección, buenas prácticas y claridad del código.",
    "Implementa una función que sume dos números enteros.",
    "Evalúa la lógica y estilo del código.",
    "Comprueba el manejo de errores y casos borde.",
]

CONTEXT_MATERIAL = (
    "Python es un lenguaje de programación interpretado de alto nivel. "
    "Sus características principales incluyen: sintaxis clara y legible, "
    "tipado dinámico, gestión automática de memoria, y una extensa biblioteca estándar. "
    "Las estructuras de datos más usadas son: listas (list), tuplas (tuple), "
    "diccionarios (dict) y conjuntos (set). Las estructuras de control incluyen "
    "if/elif/else para condicionales, y for/while para ciclos. "
    "Las funciones se definen con 'def' y pueden retornar valores con 'return'. "
    "Las clases se definen con 'class' y usan '__init__' como constructor. "
    "Python se usa ampliamente en ciencia de datos, IA, desarrollo web y automatización."
)

QUESTIONS = [
    "¿Qué es una lista en Python y cómo se diferencia de una tupla?",
    "¿Cómo funciona el manejo de excepciones con try/except?",
    "¿Qué son los argumentos *args y **kwargs en una función?",
    "¿Para qué sirve el método __init__?",
    "¿Cuál es la diferencia entre una tupla y una lista?",
    "¿Qué es el tipado dinámico?",
    "¿Cómo se define una función en Python?",
]


# =============================================================================
# Escenario 1 — LightUser: endpoints de sistema
# =============================================================================

class LightUser(HttpUser):
    """Simula monitoreo, balanceadores y health checks frecuentes."""
    weight    = 2
    wait_time = between(0.5, 2.0)

    @task(3)
    @tag("system", "health")
    def health_check(self):
        with self.client.get("/health", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") != "ok":
                    resp.failure(f"Status inesperado: {data.get('status')}")
                else:
                    resp.success()
            else:
                resp.failure(f"Health check falló: {resp.status_code}")

    @task(1)
    @tag("system", "metadata")
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
    weight    = 5
    wait_time = between(1.0, 3.0)

    def on_start(self):
        self.language = random.choice(LANGUAGES)

    @task(3)
    @tag("ai", "evaluate")
    def evaluate_code(self):
        lang    = random.choice(LANGUAGES)
        samples = CODE_SAMPLES.get(lang, PYTHON_SNIPPETS)
        payload = {
            "code":     random.choice(samples),
            "language": lang,
            "criteria": random.choice(CRITERIA_SAMPLES),
        }
        with self.client.post(
            "/api/evaluate", json=payload, catch_response=True,
            name="/api/evaluate [código válido]",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "score" not in data:
                    resp.failure("Respuesta sin campo 'score'")
                else:
                    resp.success()
            elif resp.status_code in (429, 503):
                resp.success()
            else:
                resp.failure(f"evaluate inesperado: {resp.status_code} — {resp.text[:200]}")

    @task(2)
    @tag("ai", "evaluate")
    def evaluate_javascript(self):
        payload = {
            "code":     random.choice(JS_SNIPPETS),
            "language": "javascript",
            "criteria": "Evalúa la lógica y estilo del código JavaScript.",
        }
        with self.client.post(
            "/api/evaluate", json=payload, catch_response=True,
            name="/api/evaluate [javascript]",
        ) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"evaluate_js inesperado: {resp.status_code}")

    @task(2)
    @tag("ai", "courses")
    def generate_course(self):
        payload = {
            "language":      random.choice(LANGUAGES),
            "level":         random.choice(LEVELS),
            "sections_count": random.randint(3, 7),
        }
        with self.client.post(
            "/api/courses/generate", json=payload,
            catch_response=True, timeout=120,
            name="/api/courses/generate",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "topics" not in data or len(data["topics"]) == 0:
                    resp.failure("Respuesta sin topics")
                else:
                    resp.success()
            elif resp.status_code in (429, 503):
                resp.success()
            else:
                resp.failure(f"generate_course inesperado: {resp.status_code}")

    @task(1)
    @tag("system")
    def check_health_between_tasks(self):
        """Simula que la UI hace un ping de estado ocasionalmente."""
        self.client.get("/health", name="/health [ping UI]")


# =============================================================================
# Escenario 3 — ChatUser: chat educativo con historial
# =============================================================================

class ChatUser(HttpUser):
    """Simula estudiantes en sesión de estudio con el asistente IA."""
    weight    = 2
    wait_time = between(2.0, 5.0)

    def on_start(self):
        self.history = []

    @task
    @tag("ai", "chat")
    def ask_question(self):
        question = random.choice(QUESTIONS)
        payload  = {
            "context":  CONTEXT_MATERIAL,
            "question": question,
            "history":  self.history[-4:] if self.history else None,
        }
        with self.client.post(
            "/api/chat/ask", json=payload,
            catch_response=True, timeout=120,
            name="/api/chat/ask",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("response", "").strip():
                    resp.failure("Respuesta vacía del chat")
                else:
                    self.history.append({"message": question, "response": data["response"][:200]})
                    if len(self.history) > 6:
                        self.history = self.history[-6:]
                    resp.success()
            elif resp.status_code in (429, 503):
                resp.success()
            else:
                resp.failure(f"chat_ask inesperado: {resp.status_code} — {resp.text[:200]}")

    @task(1)
    @tag("ai", "chat")
    def chat_long_context(self):
        """Prueba chat con contexto extenso (~3000 chars)."""
        long_context = (CONTEXT_MATERIAL + " ") * 20
        payload = {
            "context":  long_context,
            "question": "Resume los conceptos más importantes de este material.",
        }
        with self.client.post(
            "/api/chat/ask", json=payload,
            catch_response=True, timeout=120,
            name="/api/chat/ask [contexto largo]",
        ) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"chat_long inesperado: {resp.status_code}")


# =============================================================================
# Escenario 4 — HeavyUser: payloads grandes para medir límites
# =============================================================================

class HeavyUser(HttpUser):
    """Cargas pesadas — código largo, contextos extensos, máx. secciones."""
    weight    = 1
    wait_time = between(3.0, 8.0)

    LONG_CODE = "\n".join([
        "# Módulo complejo de ejemplo",
        "import math",
        "",
        "class Calculadora:",
        "    def __init__(self):",
        "        self.historial = []",
        "",
        "    def sumar(self, a, b):",
        "        r = a + b",
        "        self.historial.append(('suma', a, b, r))",
        "        return r",
        "",
        "    def raiz(self, n):",
        "        if n < 0:",
        "            raise ValueError('No se puede calcular raíz de negativo')",
        "        return math.sqrt(n)",
        "",
        "    def mostrar_historial(self):",
        "        for op in self.historial:",
        "            print(f'Op: {op[0]} | {op[1]} y {op[2]} = {op[3]}')",
        "",
        "calc = Calculadora()",
        "print(calc.sumar(10, 5))",
        "print(calc.raiz(16))",
        "calc.mostrar_historial()",
    ])

    @task(2)
    @tag("ai", "evaluate", "heavy")
    def evaluate_large_code(self):
        with self.client.post(
            "/api/evaluate",
            json={
                "code":     self.LONG_CODE,
                "language": "python",
                "criteria": "Evalúa calidad, clases, manejo de errores y buenas prácticas.",
            },
            catch_response=True, timeout=120,
            name="/api/evaluate [código largo]",
        ) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"evaluate_large inesperado: {resp.status_code}")

    @task(1)
    @tag("ai", "courses", "heavy")
    def generate_max_sections(self):
        with self.client.post(
            "/api/courses/generate",
            json={"language": "python", "level": "avanzado", "sections_count": 10},
            catch_response=True, timeout=120,
            name="/api/courses/generate [10 secciones]",
        ) as resp:
            if resp.status_code in (200, 503, 429):
                resp.success()
            else:
                resp.failure(f"generate_max inesperado: {resp.status_code}")


# =============================================================================
# Escenario 5 — InvalidUser: validación de entradas incorrectas
# =============================================================================

class InvalidUser(HttpUser):
    """Envía entradas inválidas — la API debe retornar 422, nunca 500."""
    weight    = 1
    wait_time = between(1.0, 3.0)

    @task(2)
    @tag("validation", "evaluate")
    def evaluate_invalid_language(self):
        with self.client.post(
            "/api/evaluate",
            json={"code": "print('hello')", "language": "cobol"},
            catch_response=True,
            name="/api/evaluate [lenguaje inválido → 422]",
        ) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422, recibí: {resp.status_code}")

    @task(2)
    @tag("validation", "evaluate")
    def evaluate_empty_code(self):
        with self.client.post(
            "/api/evaluate",
            json={"code": "   ", "language": "python"},
            catch_response=True,
            name="/api/evaluate [código vacío → 422]",
        ) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por código vacío, recibí: {resp.status_code}")

    @task(1)
    @tag("validation", "evaluate")
    def evaluate_missing_field(self):
        with self.client.post(
            "/api/evaluate",
            json={"language": "python"},  # falta 'code'
            catch_response=True,
            name="/api/evaluate [campo faltante → 422]",
        ) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por campo faltante, recibí: {resp.status_code}")

    @task(1)
    @tag("validation", "courses")
    def generate_invalid_level(self):
        with self.client.post(
            "/api/courses/generate",
            json={"language": "python", "level": "experto"},
            catch_response=True,
            name="/api/courses/generate [nivel inválido → 422]",
        ) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por nivel inválido, recibí: {resp.status_code}")

    @task(1)
    @tag("validation", "courses")
    def generate_sections_out_of_range(self):
        with self.client.post(
            "/api/courses/generate",
            json={"language": "python", "level": "principiante", "sections_count": 99},
            catch_response=True,
            name="/api/courses/generate [sections=99 → 422]",
        ) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por sections=99, recibí: {resp.status_code}")

    @task(1)
    @tag("validation", "chat")
    def chat_short_context(self):
        with self.client.post(
            "/api/chat/ask",
            json={"context": "muy corto", "question": "¿Qué es Python?"},
            catch_response=True,
            name="/api/chat/ask [contexto corto → 422]",
        ) as resp:
            if resp.status_code == 422:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Esperaba 422 por contexto corto, recibí: {resp.status_code}")


# =============================================================================
# Eventos — resumen en consola + hook de inicio
# =============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "=" * 60)
    print("  EduIA — Prueba de carga iniciada")
    print("  Endpoint base:", environment.host)
    print("  Escenarios: LightUser(2) StudentUser(5) ChatUser(2) HeavyUser(1) InvalidUser(1)")
    print("  Tags: --tags system | ai | validation | heavy")
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
