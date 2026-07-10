#  Plan de Mejora — EduIA (Semanas 2 a 6)

> Plan progresivo para llevar EduIA de un prototipo funcional a una solución desplegable y defendible.

---

## Semana 2 — API inteligente y contratos de entrada/salida

**Objetivo:** Separar la lógica de IA del frontend creando una API REST.

**Tareas:**
- Crear una API con FastAPI para los servicios de IA
- Definir endpoint `/api/exam/generate` — recibe texto/PDF, devuelve preguntas en JSON
- Definir endpoint `/api/chat/ask` — recibe pregunta + contexto del módulo, devuelve respuesta
- Definir endpoint `/api/code/evaluate` — recibe código + enunciado, devuelve retroalimentación
- Documentar contratos de entrada/salida con ejemplos
- Actualizar Streamlit para llamar a la API en lugar de usar las utilidades directamente

**Resultado esperado:**
Al menos un endpoint funcional que Streamlit consuma correctamente.

---

## Semana 3 — Pruebas automatizadas y CI/CD

**Objetivo:** Asegurar que el código funciona correctamente con pruebas automáticas.

**Tareas:**
- Escribir pruebas unitarias para funciones de generación de exámenes
- Escribir pruebas de integración para los endpoints de la API
- Configurar GitHub Actions (o similar) para correr pruebas en cada commit
- Agregar prueba básica que verifique que la app levanta sin errores
- Documentar cómo correr las pruebas manualmente

**Resultado esperado:**
El pipeline CI corre automáticamente y reporta si algo está roto.

---

## Semana 4 — Contenedor y despliegue

**Objetivo:** La aplicación corre en Docker y puede desplegarse en la nube.

**Tareas:**
- Crear `Dockerfile` para la aplicación Streamlit + FastAPI
- Crear `docker-compose.yml` para levantar todo junto
- Probar que el contenedor funciona localmente
- Preparar configuración para despliegue en Render, Railway o Fly.io
- Documentar el proceso de despliegue

**Resultado esperado:**
`docker-compose up` levanta la aplicación completa sin configuración manual.

---

## Semana 5 — Observabilidad, rendimiento y escalabilidad

**Objetivo:** Poder ver qué está pasando en la aplicación y detectar problemas.

**Tareas:**
- Agregar logging estructurado (JSON) a los endpoints de la API
- Registrar métricas: latencia de Gemini, errores de formato, tokens usados
- Evaluar si SQLite es suficiente o si se necesita PostgreSQL
- Optimizar consultas lentas identificadas con los logs
- Agregar endpoint `/health` para verificar el estado del sistema

**Resultado esperado:**
Se puede ver el historial de llamadas a la IA y detectar cuándo falla algo.

---

## Semana 6 — Seguridad, documentación final y defensa técnica

**Objetivo:** Entregar un proyecto seguro, bien documentado y listo para defender.

**Tareas:**
- Revisar que no haya API keys ni contraseñas en el código
- Agregar validaciones de entrada en todos los endpoints
- Completar el README con instrucciones claras de despliegue
- Preparar presentación técnica del proyecto
- Grabar evidencia de funcionamiento (capturas o video)
- Revisión final del checklist de la evaluación

**Resultado esperado:**
Proyecto completo, documentado y defendible ante el docente.

---

## Resumen visual

```
Semana 1 ──► Diagnóstico y documentación inicial         
Semana 2 ──► API REST con FastAPI                        
Semana 3 ──► Pruebas + CI/CD                             
Semana 4 ──► Docker + Despliegue                         
Semana 5 ──► Logs + Métricas + Escalabilidad             
Semana 6 ──► Seguridad + Defensa final                   
```
