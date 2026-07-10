#  Arquitectura Actual — EduIA

> Estado real del sistema al inicio del Módulo 4 (Semana 1)

---

## Actores principales

| Actor | Rol |
|---|---|
| Administrador | Gestiona usuarios, cursos y notificaciones |
| Docente | Crea módulos, tareas, exámenes y configura el chat IA |
| Estudiante | Accede al contenido, entrega tareas y usa la IA |

---

## Componentes del sistema

### 1. Interfaz — Streamlit
Toda la interfaz está construida con Streamlit. No hay separación entre frontend y backend; todo el código de presentación y lógica vive en los mismos archivos Python.

- `views_admin.py` — Panel del administrador
- `views_teacher.py` — Panel del docente
- `views_student.py` — Panel del estudiante
- `styles.py` — CSS personalizado

### 2. Backend / Lógica de negocio — Python
La lógica está distribuida en los archivos de vista y en módulos de utilidades:

- `database.py` — Inicialización del esquema SQLite y operaciones de BD
- `utils_ai.py` — Llamadas a la API de Gemini (generación de exámenes, evaluación de código)
- `utils_chat_ai.py` — Chat IA por módulo (individual y grupal)
- `utils_chat.py` — Chat privado entre usuarios
- `utils_notifications.py` — Sistema de notificaciones
- `utils_security.py` — Validaciones de seguridad
- `config.py` — Configuración general
- `engagement/` — Sistema de gamificación (rachas, puntos, tienda)

### 3. Componente de IA — Google Gemini
- **Modelo:** `gemini-1.5-flash`
- **Librería:** `google-generativeai`
- **Técnica:** Prompting con contexto dinámico. El sistema construye un prompt con el material del módulo y la pregunta del usuario.
- **Casos de uso:** Generación de exámenes, chat educativo, evaluación de código, plan de aprendizaje personalizado.

### 4. Base de datos — SQLite
- Archivo: `learning_platform.db`
- Tablas principales: `users`, `courses`, `modules`, `tasks`, `exams`, `submissions`, `exam_attempts`, `private_messages`, `notifications`, `conversations`, `ai_courses`
- Los PDFs de materiales se almacenan como BLOBs en `course_materials.content_blob`

### 5. Servicios externos
- **Google Gemini API** — requiere internet y API key válida

### 6. Configuración
- API key en `.streamlit/secrets.toml`
- Dependencias en `requirements.txt`

---

## Flujo básico de información

```
[Usuario en navegador]
        │
        ▼
[Streamlit — main.py]
   Renderiza la vista según el rol del usuario
        │
        ├──── Acción normal (sin IA)
        │         │
        │         ▼
        │     [Python — lógica de negocio]
        │         │
        │         ▼
        │     [SQLite — lectura/escritura]
        │
        └──── Acción con IA (chat, examen, evaluación)
                  │
                  ▼
              [utils_ai.py / utils_chat_ai.py]
              Construye prompt con contexto
                  │
                  ▼
              [Google Gemini API — Internet]
              Devuelve respuesta en texto o JSON
                  │
                  ▼
              [Procesamiento de respuesta]
              Validación del formato y guardado en SQLite
```

---

## Dependencias manuales y puntos frágiles

| Punto frágil | Descripción |
|---|---|
| API de Gemini | Sin internet o sin API key, las funciones de IA no funcionan |
| Formato JSON de Gemini | A veces la respuesta viene malformada; se reintenta pero puede fallar |
| SQLite local | No soporta múltiples usuarios simultáneos en producción real |
| Ausencia de separación frontend/backend | Todo el código de vista y lógica está mezclado |
| Sin variables de entorno externas | La API key está en `.streamlit/secrets.toml`, no en un sistema de secretos seguro |
| Sin pruebas automatizadas | No hay tests unitarios ni de integración activos |

---

## Diagrama simplificado

```
┌─────────────────────────────────────────────────────┐
│                  NAVEGADOR WEB                       │
└──────────────────────────┬──────────────────────────┘
                           │ HTTP (localhost)
                           ▼
┌─────────────────────────────────────────────────────┐
│              STREAMLIT (main.py)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐  │
│  │ views_admin  │ │views_teacher │ │views_student│  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬──────┘  │
│         └────────────────┴────────────────┘          │
│                          │                           │
│              Utilidades Python                       │
│         utils_ai / utils_chat / database             │
└──────────┬───────────────────────────┬──────────────┘
           │                           │
           ▼                           ▼
  ┌─────────────────┐       ┌───────────────────────┐
  │  SQLite          │       │  Google Gemini API    │
  │  learning_       │       │  (Internet requerido) │
  │  platform.db     │       └───────────────────────┘
  └─────────────────┘
```
