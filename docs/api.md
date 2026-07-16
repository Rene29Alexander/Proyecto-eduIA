# EduIA — Documentación de la API REST

> **Versión:** 1.0.0  
> **Base URL (local):** `http://127.0.0.1:8000`  
> **Swagger UI interactivo:** `http://127.0.0.1:8000/docs`  
> **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## Índice

| # | Endpoint | Tipo |
|---|---|---|
| 1 | [GET /health](#1-get-health) | Sistema |
| 2 | [GET /metadata](#2-get-metadata) | Sistema |
| 3 | [POST /api/evaluate](#3-post-apievaluate) | IA — Evaluación de código |
| 4 | [POST /api/courses/generate](#4-post-apicoursesgenearte) | IA — Generación de cursos |
| 5 | [POST /api/chat/ask](#5-post-apichatask) | IA — Chat educativo |

---

## 1. GET /health

**Descripción:** Verifica que el servicio API está activo y que la base de datos SQLite es accesible. Útil para monitoreo y balanceadores de carga.

**Método:** `GET`  **Ruta:** `/health`

**Payload de entrada:** Ninguno.

**Respuesta exitosa — 200 OK**
```json
{
  "status": "ok",
  "database": "connected",
  "database_path": "C:/ruta/al/learning_platform.db",
  "timestamp": "2026-07-15T14:30:00.123456"
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `status` | string | Siempre `"ok"` si el servidor responde |
| `database` | string | `"connected"` ó `"unreachable"` |
| `database_path` | string | Ruta absoluta al archivo SQLite |
| `timestamp` | string | Timestamp ISO-8601 en UTC |

**Respuesta de error:** No aplica — el endpoint siempre retorna 200 (si el servidor está caído, no hay respuesta).

---

## 2. GET /metadata

**Descripción:** Retorna información descriptiva del servicio: propósito, versión, tecnologías, endpoints disponibles y lenguajes/niveles soportados.

**Método:** `GET`  **Ruta:** `/metadata`

**Payload de entrada:** Ninguno.

**Respuesta exitosa — 200 OK**
```json
{
  "service": "EduIA — API de Capacidades Inteligentes",
  "version": "1.0.0",
  "purpose": "Exponer las capacidades de IA de la plataforma educativa EduIA...",
  "technologies": ["FastAPI", "SQLite", "Google Gemini AI", "Pydantic v2", "Python 3.11+"],
  "ai_endpoints": [
    "POST /api/evaluate         — Evaluación inteligente de código",
    "POST /api/courses/generate — Generación de estructura de curso",
    "POST /api/chat/ask         — Chat educativo por contexto"
  ],
  "supported_languages": ["python", "javascript", "java", "sql", "nosql", "c", "c++", "typescript", "html", "css"],
  "supported_levels": ["principiante", "intermedio", "avanzado"],
  "docs_url": "/docs",
  "timestamp": "2026-07-15T14:30:00.123456"
}
```

---

## 3. POST /api/evaluate

**Descripción:** Motor de evaluación inteligente de código. Ejecuta un pipeline de 5 fases: validación de relevancia, detección de código inválido, análisis estático, evaluación con Gemini y validación de consistencia. Orquestado por `evaluacion/evaluador_integrado.py`.

**Método:** `POST`  **Ruta:** `/api/evaluate`  
**Content-Type:** `application/json`

### Payload de entrada

```json
{
  "code": "def suma(a, b):\n    return a + b",
  "language": "python",
  "criteria": "Implementa una función que sume dos números enteros y retorne el resultado."
}
```

| Campo | Tipo | Requerido | Reglas |
|---|---|---|---|
| `code` | string | ✅ | Mín. 1 char, máx. 20 000 chars. No puede ser sólo espacios. |
| `language` | string | ✅ | Uno de: `python`, `javascript`, `java`, `sql`, `nosql`, `c`, `c++`, `typescript`, `html`, `css`. Case-insensitive. |
| `criteria` | string | ❌ | Máx. 2 000 chars. Default: evaluación por buenas prácticas. |

### Respuesta exitosa — 200 OK

```json
{
  "score": 9,
  "correctness": "correcto",
  "feedback": "¡Excelente! La función `suma` es clara y sigue las convenciones de Python. Retorna el resultado directamente sin efectos secundarios.",
  "suggestions": [
    "Agrega anotaciones de tipo: def suma(a: int, b: int) -> int",
    "Incluye un docstring describiendo la función"
  ],
  "concepts": ["funciones", "retorno de valores", "buenas prácticas"],
  "errors_detected": [],
  "score_adjusted": false,
  "adjustment_reason": "",
  "language": "python",
  "evaluated_at": "2026-07-15T14:30:00.123456",
  "ai_available": true
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `score` | integer (0–10) | Puntuación de la evaluación |
| `correctness` | string | `"correcto"` / `"parcial"` / `"incorrecto"` |
| `feedback` | string | Retroalimentación generada por IA |
| `suggestions` | array[string] | Sugerencias de mejora concretas |
| `concepts` | array[string] | Conceptos de programación evaluados |
| `errors_detected` | array[string] | Errores del análisis estático |
| `score_adjusted` | boolean | `true` si el validador ajustó el score |
| `adjustment_reason` | string | Razón del ajuste (vacío si no hubo) |
| `language` | string | Lenguaje evaluado (normalizado) |
| `evaluated_at` | string | Timestamp UTC |
| `ai_available` | boolean | Si Gemini estuvo disponible |

### Respuestas de error

**422 — Lenguaje no soportado**
```json
{
  "detail": [{
    "type": "value_error",
    "loc": ["body", "language"],
    "msg": "Value error, Lenguaje 'cobol' no soportado. Opciones válidas: python, javascript, ...",
    "input": "cobol"
  }]
}
```

**422 — Código vacío**
```json
{
  "detail": [{
    "type": "value_error",
    "loc": ["body", "code"],
    "msg": "Value error, El campo 'code' no puede contener sólo espacios en blanco.",
    "input": "   "
  }]
}
```

**503 — Gemini no disponible**
```json
{
  "detail": {
    "error": "Servicio de IA (Gemini) no disponible.",
    "reason": "GEMINI_API_KEY no configurada.",
    "suggestion": "Verifica que GEMINI_API_KEY esté configurada correctamente."
  }
}
```

---

## 4. POST /api/courses/generate

**Descripción:** Genera la estructura de temas para un curso personalizado según el lenguaje y nivel del estudiante. Usa `AIManager.generate_course_topics_structure` de `utils_ai.py`. Si Gemini está disponible, enriquece descripciones; si no, usa la estructura predefinida garantizada.

**Método:** `POST`  **Ruta:** `/api/courses/generate`  
**Content-Type:** `application/json`

### Payload de entrada

```json
{
  "language": "python",
  "level": "principiante",
  "sections_count": 5
}
```

| Campo | Tipo | Requerido | Reglas |
|---|---|---|---|
| `language` | string | ✅ | Mismo listado que `/api/evaluate`. Case-insensitive. |
| `level` | string | ✅ | `principiante`, `intermedio` ó `avanzado`. |
| `sections_count` | integer | ❌ | Entre 1 y 10. Default: 5. |

### Respuesta exitosa — 200 OK

```json
{
  "language": "python",
  "level": "principiante",
  "sections_count": 5,
  "topics": [
    {
      "topic_number": 1,
      "title": "Introducción a Python y Variables",
      "description": "Aprende los fundamentos de Python: instalación, sintaxis básica y manejo de variables.",
      "objectives": "Dominar variables, tipos de datos y la consola de Python.",
      "estimated_hours": 4,
      "order_index": 0
    },
    {
      "topic_number": 2,
      "title": "Estructuras de Control",
      "description": "Comprende los condicionales if/else y los bucles for/while en Python.",
      "objectives": "Implementar lógica condicional y repetitiva en programas Python.",
      "estimated_hours": 5,
      "order_index": 1
    }
  ],
  "generated_at": "2026-07-15T14:30:00.123456",
  "ai_available": true
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `language` | string | Lenguaje del curso (normalizado) |
| `level` | string | Nivel del curso |
| `sections_count` | integer | Número de secciones solicitadas |
| `topics` | array[object] | Lista de temas generados |
| `topics[].topic_number` | integer | Número de orden del tema |
| `topics[].title` | string | Título del tema |
| `topics[].description` | string | Descripción del contenido |
| `topics[].objectives` | string | Objetivos de aprendizaje |
| `topics[].estimated_hours` | integer | Horas estimadas de estudio |
| `topics[].order_index` | integer | Índice de orden (base 0) |
| `generated_at` | string | Timestamp UTC |
| `ai_available` | boolean | Si Gemini enriqueció el contenido |

### Respuestas de error

**422 — Nivel no válido**
```json
{
  "detail": [{
    "type": "value_error",
    "loc": ["body", "level"],
    "msg": "Value error, Nivel 'experto' no soportado. Opciones válidas: principiante, intermedio, avanzado",
    "input": "experto"
  }]
}
```

**422 — sections_count fuera de rango**
```json
{
  "detail": [{
    "type": "greater_than_equal",
    "loc": ["body", "sections_count"],
    "msg": "Input should be greater than or equal to 1",
    "input": 0
  }]
}
```

---

## 5. POST /api/chat/ask

**Descripción:** Chat educativo contextualizado. Recibe el texto completo del material del módulo y la pregunta del estudiante. La IA responde **basándose exclusivamente en el contexto provisto**. Usa `get_contextualized_chat_response` de `utils_ai.py`.

**Método:** `POST`  **Ruta:** `/api/chat/ask`  
**Content-Type:** `application/json`

### Payload de entrada

```json
{
  "context": "Python es un lenguaje de programación interpretado y de alto nivel. Sus características principales son: sintaxis clara, tipado dinámico, y una gran biblioteca estándar. Las estructuras de datos más comunes son: listas [], tuplas (), diccionarios {} y conjuntos set().",
  "question": "¿Qué diferencia hay entre una lista y una tupla en Python?",
  "history": [
    {
      "message": "¿Qué es Python?",
      "response": "Python es un lenguaje interpretado de alto nivel con sintaxis clara y tipado dinámico."
    }
  ]
}
```

| Campo | Tipo | Requerido | Reglas |
|---|---|---|---|
| `context` | string | ✅ | Mín. 50 chars, máx. 500 000 chars. |
| `question` | string | ✅ | No vacía, máx. 1 000 chars. |
| `history` | array[object] | ❌ | Hasta 10 turnos previos. Cada objeto necesita `message` y `response`. |

### Respuesta exitosa — 200 OK

```json
{
  "response": "## Diferencia entre Lista y Tupla en Python\n\nSegún el contenido del módulo:\n\n**Lista `[]`:**\n- Es **mutable** — puedes agregar, eliminar o modificar elementos después de crearla.\n- Ejemplo: `mi_lista = [1, 2, 3]`\n\n**Tupla `()`:**\n- Es **inmutable** — una vez creada no puede modificarse.\n- Se usa cuando los datos no deben cambiar.\n- Ejemplo: `mi_tupla = (1, 2, 3)`",
  "question": "¿Qué diferencia hay entre una lista y una tupla en Python?",
  "answered_at": "2026-07-15T14:30:00.123456",
  "ai_available": true
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `response` | string | Respuesta del asistente en formato Markdown |
| `question` | string | Pregunta original recibida |
| `answered_at` | string | Timestamp UTC |
| `ai_available` | boolean | Si Gemini generó la respuesta |

### Respuestas de error

**422 — Contexto demasiado corto**
```json
{
  "detail": [{
    "type": "string_too_short",
    "loc": ["body", "context"],
    "msg": "String should have at least 50 characters",
    "input": "Hola"
  }]
}
```

**422 — Pregunta vacía**
```json
{
  "detail": [{
    "type": "value_error",
    "loc": ["body", "question"],
    "msg": "Value error, El campo 'question' no puede estar vacío.",
    "input": "   "
  }]
}
```

**503 — Gemini no disponible**
```json
{
  "detail": {
    "error": "Servicio de IA (Gemini) no disponible.",
    "reason": "Cuota de la API agotada. Espera unos minutos e inténtalo de nuevo.",
    "suggestion": "Verifica que GEMINI_API_KEY esté configurada correctamente y que tengas cuota disponible."
  }
}
```

---

## Comandos curl para probar los endpoints POST

### POST /api/evaluate

```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def suma(a, b):\n    return a + b",
    "language": "python",
    "criteria": "Implementa una función que sume dos números enteros."
  }'
```

**Con código incorrecto (para ver feedback de errores):**
```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def suma(a, b)\n    retun a + b",
    "language": "python"
  }'
```

### POST /api/courses/generate

```bash
curl -X POST http://127.0.0.1:8000/api/courses/generate \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "level": "principiante",
    "sections_count": 5
  }'
```

**Curso avanzado de JavaScript:**
```bash
curl -X POST http://127.0.0.1:8000/api/courses/generate \
  -H "Content-Type: application/json" \
  -d '{
    "language": "javascript",
    "level": "avanzado",
    "sections_count": 7
  }'
```

### POST /api/chat/ask

```bash
curl -X POST http://127.0.0.1:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{
    "context": "Python es un lenguaje interpretado de alto nivel. Sus estructuras de datos principales son: listas [], tuplas (), diccionarios {} y conjuntos set(). Las listas son mutables y las tuplas son inmutables.",
    "question": "¿Qué diferencia hay entre una lista y una tupla?",
    "history": []
  }'
```

**Con historial de conversación:**
```bash
curl -X POST http://127.0.0.1:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{
    "context": "Python es un lenguaje interpretado. Las funciones se definen con la palabra clave def. Una función puede recibir parámetros y retornar valores con return.",
    "question": "¿Puedo tener una función sin parámetros?",
    "history": [
      {
        "message": "¿Cómo se define una función en Python?",
        "response": "En Python las funciones se definen con la palabra clave def seguida del nombre y paréntesis."
      }
    ]
  }'
```

> **Nota Windows CMD:** reemplaza las comillas simples externas por dobles y escapa las internas con `\"`.

---

## Tabla resumen de validaciones

| Endpoint | Validación | Código |
|---|---|---|
| `/api/evaluate` | `code` vacío o solo espacios | 422 |
| `/api/evaluate` | `language` no soportado | 422 |
| `/api/evaluate` | `code` > 20 000 chars | 422 |
| `/api/courses/generate` | `language` no soportado | 422 |
| `/api/courses/generate` | `level` no soportado | 422 |
| `/api/courses/generate` | `sections_count` < 1 ó > 10 | 422 |
| `/api/chat/ask` | `context` < 50 chars | 422 |
| `/api/chat/ask` | `question` vacía | 422 |
| `/api/chat/ask` | `context` > 500 000 chars | 422 |
| Todos los POST IA | Gemini sin API key | 503 |
| Todos los POST IA | Cuota agotada / error auth | 503 |
| Todos los POST IA | Error interno inesperado | 500 |

---

## Evidencia de prueba

### Herramienta recomendada
**Swagger UI** en `http://127.0.0.1:8000/docs` — permite ejecutar cada endpoint directamente en el navegador sin instalar nada adicional.

También se puede usar:
- **Postman**: importar los curl como colección
- **curl**: comandos en la sección anterior
- **Script automatizado**: `python tests/test_api_evidencia.py` (requiere API corriendo)

### Cómo generar la evidencia de prueba

**Paso 1:** Levantar la API
```bash
set GEMINI_API_KEY=tu_api_key_aqui
uvicorn api:app --reload
```

**Paso 2:** Abrir `http://127.0.0.1:8000/docs` en el navegador

**Paso 3:** Ejecutar cada endpoint desde Swagger y capturar pantalla mostrando:
- Respuesta exitosa 200 de `GET /health`
- Respuesta exitosa 200 de `POST /api/evaluate` con código válido
- Respuesta de error 422 de `POST /api/evaluate` con lenguaje `"pascal"` (no soportado)
- Respuesta de error 422 de `POST /api/chat/ask` con contexto de 4 caracteres

**Paso 4 (alternativo):** Ejecutar el script de evidencia automática
```bash
# Con la API corriendo en otra terminal:
python tests/test_api_evidencia.py
```

El script prueba los 13 casos documentados (exitosos y de error) e imprime un resumen con PASS/FAIL por cada uno.

### Casos de prueba cubiertos

| # | Endpoint | Tipo de prueba | Código esperado |
|---|---|---|---|
| 1 | `GET /health` | Exitosa | 200 |
| 2 | `GET /metadata` | Exitosa | 200 |
| 3 | `POST /api/evaluate` | Código Python correcto | 200 |
| 4 | `POST /api/evaluate` | Código con errores sintácticos | 200 |
| 5 | `POST /api/evaluate` | Lenguaje no soportado | 422 |
| 6 | `POST /api/evaluate` | Código solo espacios | 422 |
| 7 | `POST /api/evaluate` | Sin campo `code` | 422 |
| 8 | `POST /api/courses/generate` | Python principiante 3 temas | 200 |
| 9 | `POST /api/courses/generate` | Nivel `"experto"` inválido | 422 |
| 10 | `POST /api/courses/generate` | `sections_count=0` | 422 |
| 11 | `POST /api/chat/ask` | Pregunta con contexto válido | 200 |
| 12 | `POST /api/chat/ask` | Con historial de conversación | 200 |
| 13 | `POST /api/chat/ask` | Contexto menor a 50 chars | 422 |

---

## Seguridad

- La API Key de Gemini **nunca** aparece en el código fuente. Se lee desde la variable de entorno `GEMINI_API_KEY` o desde la base de datos (configuración del admin).
- Los stacktraces internos se escriben en los logs del servidor pero **no se exponen** al cliente.
- Todos los campos de texto tienen límite máximo para prevenir abuso.
