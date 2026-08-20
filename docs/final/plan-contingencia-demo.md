# Plan de Contingencia — Demostración Final EduIA

> Evaluación Final Módulo 4 — Preespecialización UGB
> Versión: 1.0.0 | URL pública: https://eduiaiugb.streamlit.app/

---

## Verificaciones programadas

| Momento | Acciones |
|---|---|
| 24 horas antes | Congelar release, probar recorrido completo desde ventana privada, revisar API key y generar respaldo |
| 2 horas antes | Confirmar URL pública, datos de prueba, cuota de Gemini, cuenta demo y estado del pipeline |
| 15 minutos antes | Calentar servicio abriendo la URL, iniciar sesión con cuenta demo, cerrar notificaciones y abrir pestañas |
| Al finalizar | No exponer credenciales, registrar incidentes y conservar la versión evaluada |

---

## Credenciales de demostración

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `admin123` |
| Docente | _(crear desde panel admin antes de la demo)_ | _(definir antes)_ |
| Estudiante | _(crear desde panel admin antes de la demo)_ | _(definir antes)_ |

> ⚠️ Compartir credenciales solo por canal seguro (WhatsApp del grupo), nunca en el repositorio.

---

## Flujo crítico a demostrar (3 minutos)

| Tiempo | Acción | URL / Sección |
|---|---|---|
| 0:00 - 0:20 | Abrir URL pública, identificar producto y versión | https://eduiaiugb.streamlit.app/ |
| 0:20 - 1:30 | Iniciar sesión como estudiante → Academia de Programación → Evaluar código Python | Sección "Academia" |
| 1:30 - 2:10 | Ingresar código con error → mostrar que detecta el error y da feedback | Mismo módulo |
| 2:10 - 2:40 | Mostrar endpoint /health desde navegador o Swagger | URL/health o /docs |
| 2:40 - 3:00 | Confirmar resultado, mencionar limitación SQLite y cerrar | — |

---

## Riesgos y respuestas preparadas

| Riesgo | Prevención | Respuesta |
|---|---|---|
| Servicio dormido en Streamlit Cloud | Abrir la URL 15 min antes para despertar el servicio | Esperar 30s a que cargue; mostrar pantalla de carga como evidencia de despliegue real |
| Cuota de Gemini agotada | Revisar panel de Google AI Studio antes. Limitar demos de prueba | La app muestra mensaje de error controlado — demostrarlo como falla gestionada |
| URL no carga | Probar desde ventana privada y otra red 24h antes | Usar respaldo local con Docker si el docente lo autoriza |
| Sesión vencida | Validar cuenta y permisos 15 min antes | Reingreso rápido con credenciales preparadas |
| Error de CORS o migración de BD | Probar producción después del último release | Rollback a commit `8a05d00` en rama main |
| Red o audiovisual falla | Probar red, audio y pantalla antes del turno | Segundo dispositivo con la URL abierta |
| API de Gemini lenta | Timeout configurado en utils_ai_core.py con reintentos | Mostrar mensaje controlado como evidencia de manejo de errores |

---

## Respaldo

Si la URL pública falla por incidente externo verificable:

1. Levantar Docker local: `docker run -d -p 8000:8000 -e GEMINI_API_KEY=key --name eduia-api eduia-api:1.0`
2. Levantar Streamlit local: `py -m streamlit run main.py`
3. Mostrar desde `http://localhost:8501` con autorización expresa del docente

> El respaldo local solo se usa ante contingencia externa verificable y por decisión del docente.

---

## Pestañas a tener abiertas antes de la demo

1. https://eduiaiugb.streamlit.app/ — app principal (con sesión iniciada)
2. https://github.com/Rene29Alexander/Proyecto-eduIA — repositorio
3. https://github.com/Rene29Alexander/Proyecto-eduIA/releases — tag/release
4. https://github.com/Rene29Alexander/Proyecto-eduIA/actions — pipeline CI/CD
