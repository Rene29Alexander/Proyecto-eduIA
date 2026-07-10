#  EduIA — Plataforma Educativa con Inteligencia Artificial

---

## 1. Información General

| Campo | Detalle |
|---|---|
| **Módulo** | Módulo 4 - Desarrollo de Aplicaciones con IA |
| **Semana** | Semana 1 - Diagnóstico y arquitectura inicial |
| **Nombre del equipo** | equipo 2 |

**Integrantes:**
- Integrante 1: Rene Alexander Araujo Soto
- Integrante 2: Jonathan Roberto Acosta Lopez
- Integrante 3: Mario Alexander Hernandez Quevedo

---

## 2. Descripción del Problema

Los docentes invierten demasiado tiempo en tareas repetitivas como crear exámenes, calificar entregas y dar retroalimentación uno a uno. Al mismo tiempo, los estudiantes aprenden a ritmos distintos pero reciben el mismo contenido estático, sin ninguna adaptación a su nivel real.

**¿Qué problema se quiere resolver?**
La carga manual del docente y la falta de personalización en el aprendizaje.

**¿A quién afecta?**
A docentes con grupos numerosos y a estudiantes que necesitan apoyo personalizado que no pueden recibir por la limitación de tiempo del profesor.

**¿Por qué la IA aporta valor aquí?**
Porque puede generar evaluaciones automáticamente, responder preguntas de los estudiantes en tiempo real usando el material del curso, y adaptar el plan de aprendizaje según el nivel de cada persona — sin reemplazar al docente, sino apoyándolo.

---

## 3. Usuarios y Beneficiarios

###  Docente
- **Necesidad:** Crear exámenes, gestionar entregas y dar retroalimentación sin invertir horas extras.
- **Cómo ayuda la app:** Genera exámenes automáticamente desde PDFs o texto, centraliza todas las entregas en un solo lugar y permite calificar con apoyo de IA.

###  Estudiante
- **Necesidad:** Aprender a su propio ritmo y obtener respuestas rápidas sobre el contenido del curso.
- **Cómo ayuda la app:** Chat con IA por módulo que responde usando el material del curso, cursos de programación personalizados según su nivel evaluado, y retroalimentación inmediata en tareas.

###  Administrador
- **Necesidad:** Gestionar usuarios, cursos y comunicaciones de forma eficiente.
- **Cómo ayuda la app:** Panel de control completo con creación de cursos y usuarios, notificaciones masivas y chat directo con estudiantes.

---

## 4. Descripción de la Solución

EduIA es una plataforma web educativa que integra inteligencia artificial para automatizar y mejorar el proceso de enseñanza-aprendizaje.

**¿Qué permite hacer?**
- Gestionar cursos, módulos, tareas y exámenes.
- Generar evaluaciones automáticamente usando IA.
- Comunicarse en tiempo real entre docentes, estudiantes y administradores.
- Personalizar el aprendizaje de programación según el nivel de cada estudiante.

**¿Qué recibe como entrada?**
PDFs del material del curso, texto de temas, código de programación, respuestas de evaluaciones diagnósticas y preguntas en el chat.

**¿Qué entrega como resultado?**
Exámenes generados automáticamente, retroalimentación de código, respuestas personalizadas en el chat y planes de aprendizaje adaptados al estudiante.

**¿Qué automatiza?**
La creación de evaluaciones, la retroalimentación de código, el contenido del chat educativo por módulo y la generación de cursos de programación personalizados.

---

## 5. Componente de Inteligencia Artificial

| Elemento | Descripción |
|---|---|
| **Tipo de IA** | IA Generativa — Large Language Model (LLM) |
| **Modelo / Servicio** | Google Gemini (`gemini-1.5-flash`) vía API oficial |
| **Datos de entrada** | Texto del docente, PDFs del material, código del estudiante, preguntas del chat, resultados de evaluación diagnóstica |
| **Resultado generado** | Preguntas de examen en formato estructurado, retroalimentación de código, respuestas en el chat, plan de aprendizaje por lenguaje y nivel |
| **Evaluación** | Validación del formato de respuesta (JSON válido), calidad de retroalimentación revisada manualmente |
| **Limitaciones actuales** | Requiere internet; el número de preguntas generadas no siempre coincide exactamente; el JSON puede venir malformado y necesita reintento |

**¿Cómo participa la IA?**

La IA interviene en tres momentos clave:

1. **Generación de exámenes:** El docente sube material o escribe un tema, Gemini genera las preguntas automáticamente.
2. **Chat educativo por módulo:** El estudiante hace preguntas y Gemini responde usando el contenido del módulo como contexto.
3. **Academia Personal de Programación:** El estudiante hace una evaluación diagnóstica y Gemini genera un plan de aprendizaje completo adaptado a su nivel real.

En todos los casos la IA actúa con el contexto que el sistema le proporciona — no inventa información.

---

## 6. Estado Actual del Proyecto

###  Funcionalidades que ya funcionan

- Login con tres roles: Administrador, Docente y Estudiante
- Gestión completa de usuarios y cursos desde el panel del administrador
- Creación de módulos y subida de materiales (PDF, texto, imágenes)
- Creación de tareas y exámenes (manual y con generación por IA)
- Entrega de tareas por archivo o código, con calificación del docente
- Exámenes con cronómetro, autocorrección y calificación automática
- Chat de IA por módulo (individual y grupal) usando el material configurado
- Academia Personal IA con evaluación diagnóstica y plan personalizado por lenguaje
- Sistema de engagement: racha de días, puntos, monedas y tienda de ítems
- Chat privado entre usuarios (docente-estudiante, admin-estudiante)
- Notificaciones masivas por categoría desde el administrador
- Exportación de notas en Excel y CSV
- Backups automáticos y manuales de la base de datos
- Panel de mantenimiento del sistema

###  Funcionalidades incompletas o con problemas

- La generación de exámenes no garantiza siempre el número exacto de preguntas solicitadas
- El chat privado del administrador con estudiantes no siempre muestra las conversaciones correctamente
- Las notificaciones del profesor presentan problemas en algunas sesiones por conexión de base de datos
- Sin versión móvil optimizada (diseñada para escritorio)
- Sin reportes avanzados para el administrador (solo estadísticas básicas)

---

## 7. Arquitectura Actual

### Componentes del sistema

| Componente | Descripción | Estado |
|---|---|---|
| **Interfaz** | Streamlit — vistas para cada rol (`views_admin.py`, `views_teacher.py`, `views_student.py`) | ✅ Funcional |
| **Backend / Lógica** | Python — manejo de sesiones, validaciones y lógica de negocio en archivos `views_*` y utilidades | ✅ Funcional |
| **Componente IA** | Google Gemini vía `utils_ai.py` y `utils_chat_ai.py` | ✅ Funcional (con limitaciones de formato) |
| **Base de Datos** | SQLite (`learning_platform.db`) — usuarios, cursos, tareas, exámenes, chat, notificaciones | ✅ Funcional |
| **Servicio Externo** | API de Google Gemini (requiere clave en `.streamlit/secrets.toml`) | ✅ Funcional (requiere internet) |
| **Configuración** | `secrets.toml` para API key, `requirements.txt` para dependencias, `database.py` para esquema | ✅ Funcional |

### Diagrama de arquitectura

```
┌─────────────────────────────────────────────┐
│          Navegador del usuario               │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Interfaz Web — Streamlit             │
│   views_admin  │  views_teacher  │  views_student │
└───────┬─────────────────┬────────────────────┘
        │                 │
        ▼                 ▼
┌───────────────┐  ┌──────────────────────┐
│  Backend      │  │  Servicio IA         │
│  Python       │  │  Google Gemini API   │
│  utils_*.py   │  │  (internet requerido)│
└───────┬───────┘  └──────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│         Base de Datos — SQLite               │
│         learning_platform.db                 │
└─────────────────────────────────────────────┘
```

**Flujo principal:**
El usuario interactúa con la interfaz → Python procesa la acción → si involucra IA, se llama a Gemini → el resultado se muestra o guarda → los datos persisten en SQLite.
