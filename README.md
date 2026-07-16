#  EduIA — Plataforma Educativa con Inteligencia Artificial

> Plataforma web educativa que integra IA para automatizar la generación de contenido, evaluaciones y retroalimentación personalizada para estudiantes, docentes y administradores.

---

##  Integrantes del grupo

- Rene Alexander Araujo Soto
- Jonathan Roberto Acosta Lopez
- Mario Alexander Hernandez Quevedo

---

## 1. Descripción del problema

Los docentes invierten demasiado tiempo en tareas repetitivas: crear exámenes desde cero, calificar entregas y dar retroalimentación individual. Al mismo tiempo, los estudiantes aprenden a ritmos distintos pero reciben el mismo contenido estático sin ninguna adaptación.

Este problema afecta a docentes con grupos numerosos y a estudiantes que necesitan apoyo personalizado que no pueden recibir por limitación de tiempo del profesor.

---

## 2. Usuarios o beneficiarios principales

| Usuario | Necesidad |
|---|---|
|  Docente | Crear evaluaciones y dar retroalimentación sin invertir horas extras |
|  Estudiante | Aprender a su ritmo con apoyo personalizado e inmediato |
|  Administrador | Gestionar la plataforma de forma eficiente |

---

## 3. Descripción general de la solución

EduIA es una plataforma web construida con Python y Streamlit que permite:
- Gestionar cursos, módulos, tareas y exámenes
- Generar evaluaciones automáticamente con IA a partir de PDFs o texto
- Ofrecer un chat educativo por módulo usando el material del curso como contexto
- Personalizar el aprendizaje de programación según el nivel de cada estudiante
- Comunicar a admin, docentes y estudiantes mediante chat privado y notificaciones

---

## 4. ¿Dónde está la Inteligencia Artificial?

La IA participa en tres momentos clave:

1. **Generación de exámenes** — el docente sube material y Gemini genera preguntas automáticamente
2. **Chat educativo por módulo** — el estudiante pregunta y Gemini responde usando el material configurado
3. **Academia Personal de Programación** — evaluación diagnóstica y plan de aprendizaje adaptado al nivel del estudiante

---

## 5. Tipo de IA, modelo y técnica utilizada

| Elemento | Detalle |
|---|---|
| Tipo | IA Generativa — Large Language Model (LLM) |
| Modelo | Google Gemini (`gemini-1.5-flash`) |
| Servicio | Google AI Studio API (`google-generativeai`) |
| Técnica | Prompting con contexto dinámico (RAG simplificado) |

---

## 6. Datos de entrada y salida

| Dirección | Descripción |
|---|---|
| **Entrada** | Texto del docente, PDFs del material, código del estudiante, preguntas del chat, respuestas de evaluación diagnóstica |
| **Salida** | Preguntas de examen estructuradas, retroalimentación de código, respuestas del chat, plan de aprendizaje personalizado |

---

## 7. Instrucciones de instalación y ejecución

### Requisitos
- Python 3.11 o superior
- Cuenta y API Key de Google Gemini (gratis en [aistudio.google.com](https://aistudio.google.com))

### Instalación

```bash
# 1. Clonar o descomprimir el proyecto
cd Grupo-2-proyecto

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key (ver sección siguiente)

# 5. Ejecutar la aplicación
python -m streamlit run main.py
```

---

## 8. Variables de entorno requeridas

Crear el archivo `.streamlit/secrets.toml` con el siguiente contenido:

```toml
GEMINI_API_KEY = "tu_api_key_aqui"
```

>  No subir este archivo a repositorios públicos. Ver `.env.example` para referencia.

---

## 9. Arquitectura

-  [Arquitectura actual](docs/arquitectura-actual.md)
-  [Arquitectura objetivo](docs/arquitectura-objetivo.md)

---

## 10. Limitaciones conocidas del prototipo

- Depende de internet y disponibilidad de la API de Gemini
- La generación de exámenes no siempre produce el número exacto de preguntas solicitadas
- Sin versión móvil optimizada (diseñada para escritorio)
- La base de datos es local (SQLite), no soporta múltiples instancias simultáneas
- Sin sistema de autenticación por roles con tokens seguros (solo sesión en memoria)

---

## 11. API REST — FastAPI (Semana 2)

La plataforma expone **todas** sus capacidades de IA a través de una API RESTful construida con FastAPI.

### Instalación de dependencias

```bash
pip install fastapi uvicorn
```

O instala todo el proyecto de una vez:

```bash
pip install -r requirements.txt
```

### Configurar la API Key de Gemini

Antes de levantar la API, define la variable de entorno con tu clave:

```bash
# Windows CMD
set GEMINI_API_KEY=tu_api_key_aqui

# Windows PowerShell
$env:GEMINI_API_KEY="tu_api_key_aqui"

# Linux / Mac
export GEMINI_API_KEY=tu_api_key_aqui
```

> La API Key también puede estar en `.streamlit/secrets.toml` si ya usas la app Streamlit.

### Levantar el servidor

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

El flag `--reload` reinicia el servidor automáticamente al detectar cambios.

### Acceder a la documentación interactiva

| Interfaz | URL |
|---|---|
| **Swagger UI** (probar endpoints desde el navegador) | http://127.0.0.1:8000/docs |
| **ReDoc** (documentación de referencia) | http://127.0.0.1:8000/redoc |

### Endpoints disponibles

| Método | Ruta | Tipo | Descripción |
|---|---|---|---|
| `GET` | `/health` | Sistema | Estado del servicio y BD |
| `GET` | `/metadata` | Sistema | Versión, tecnologías y capacidades |
| `POST` | `/api/evaluate` | IA | Evaluación inteligente de código |
| `POST` | `/api/courses/generate` | IA | Genera estructura de curso personalizado |
| `POST` | `/api/chat/ask` | IA | Chat educativo contextualizado por material |

### Ejemplos rápidos

**Evaluar código:**
```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"code": "def suma(a, b):\n    return a + b", "language": "python"}'
```

**Generar curso:**
```bash
curl -X POST http://127.0.0.1:8000/api/courses/generate \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "level": "principiante", "sections_count": 5}'
```

**Chat educativo:**
```bash
curl -X POST http://127.0.0.1:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"context": "Python usa listas [] y tuplas (). Las listas son mutables.", "question": "¿Qué diferencia hay entre lista y tupla?"}'
```

> Documentación completa con todos los contratos, ejemplos de error y más comandos curl en [`docs/api.md`](docs/api.md)

---

## 12. Plan de mejora — Semanas 2 a 6

| Semana | Objetivo |
|---|---|
| Semana 2 | Crear API REST con FastAPI para separar la lógica de IA del frontend |
| Semana 3 | Agregar pruebas automatizadas y pipeline CI/CD básico |
| Semana 4 | Contenerizar con Docker y preparar despliegue en la nube |
| Semana 5 | Agregar logs, métricas de uso y monitoreo de la API |
| Semana 6 | Revisar seguridad, documentación final y defensa técnica |

---

##  Estructura del proyecto

```
proyectof/
├── main.py                    # Punto de entrada
├── views_admin.py             # Vista del administrador
├── views_teacher.py           # Vista del docente
├── views_student.py           # Vista del estudiante
├── database.py                # Inicialización y manejo de BD
├── database_engagement.py     # BD del sistema de engagement
├── utils_ai.py                # Integración con Gemini
├── utils_chat_ai.py           # Chat IA por módulo
├── utils_chat.py              # Chat privado entre usuarios
├── utils_notifications.py     # Sistema de notificaciones
├── utils_security.py          # Validaciones de seguridad
├── utils_performance.py       # Optimizaciones de rendimiento
├── utils_question_bank.py     # Banco de preguntas
├── utils_recommendation.py    # Sistema de recomendaciones
├── styles.py                  # Estilos CSS
├── config.py                  # Configuración general
├── ai_course_functions.py     # Cursos de programación personalizados con IA
├── engagement_system.py       # Sistema de gamificación principal
├── engagement/                # Módulos del sistema de engagement
│   ├── badge_manager.py
│   ├── challenge_manager.py
│   ├── daily_question_manager.py
│   ├── duel_manager.py
│   ├── leaderboard_manager.py
│   ├── notification_manager.py
│   ├── points_manager.py
│   ├── shop_manager.py
│   └── statistics_manager.py
├── data/                      # Datos estáticos
│   └── question_bank.json
├── docs/                      # Documentación técnica
│   ├── diagnostico-semana1.md
│   ├── arquitectura-actual.md
│   ├── arquitectura-objetivo.md
│   ├── riesgos-tecnicos.md
│   └── plan-mejora.md
├── scripts/                   # Scripts de utilidad y mantenimiento
│   ├── add_test_coins.py
│   ├── check_users.py
│   ├── create_daily_challenges.py
│   ├── fix_force_refresh.py
│   ├── inspect_exam.py
│   └── test_tutor_functions.py
├── tests/                     # Pruebas automatizadas
├── backups/                   # Backups automáticos de la BD
├── learning_platform.db       # Base de datos SQLite
├── requirements.txt
├── .env.example               # Plantilla de variables de entorno
└── .streamlit/
    └── secrets.toml           # API keys (NO subir al repo)
```

---

## Credenciales de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `admin123` |
| Docente | _(crear desde panel admin)_ | _(la que se asigne)_ |
| Estudiante | _(crear desde panel admin)_ | _(la que se asigne)_ |
