# -*- coding: utf-8 -*-
"""
Agente supervisor de la API EduIA.

Corre en background, lee logs/api.log cada 30 segundos, detecta anomalias
y pide a Gemini un diagnostico en lenguaje natural.

Notificaciones: envia alertas a Discord via webhook si DISCORD_WEBHOOK_URL
esta configurada como variable de entorno.

No ejecuta acciones automaticas — solo diagnostica y expone el estado
en GET /api/monitor.
"""

import os
import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("eduia.monitor")

# Umbrales para generar alertas
_THRESHOLD_500  = 3   # errores 500 en las ultimas 50 lineas
_THRESHOLD_503  = 5   # errores 503
_THRESHOLD_429  = 10  # rate limit hits
_THRESHOLD_SLOW = 3   # timeouts

# Emojis para el mensaje de Discord
_EMOJI_ALERT  = "🚨"
_EMOJI_OK     = "✅"
_EMOJI_WARN   = "⚠️"


class APIMonitorAgent:
    """
    Monitorea el archivo de log de la API y genera diagnosticos con Gemini
    cuando detecta patrones anomalos.
    """

    def __init__(self, log_file: str = "logs/api.log", check_interval: int = 30):
        self.log_file      = log_file
        self.check_interval = check_interval
        self.alerts: List[Dict] = []          # historial de alertas generadas
        self.started_at    = datetime.utcnow().isoformat()
        self._running      = False
        self._thread: Optional[threading.Thread] = None
        self._ai_manager   = None             # se inyecta desde api.py al arrancar

    # ------------------------------------------------------------------
    # Control del agente
    # ------------------------------------------------------------------

    def start(self, ai_manager=None):
        """
        Inicia el monitoreo en un hilo daemon.
        ai_manager: instancia de AIManagerCore (opcional, inyectada desde api.py).
        """
        if self._running:
            return
        self._ai_manager = ai_manager
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Agente monitor iniciado — intervalo %ds, log: %s",
                    self.check_interval, self.log_file)
        # Notificar a Discord que la API arrancó
        self._notify_startup()

    def stop(self):
        self._running = False
        logger.info("Agente monitor detenido.")

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------

    def _monitor_loop(self):
        while self._running:
            try:
                self._check_logs()
            except Exception as exc:
                logger.warning("Error en ciclo de monitoreo: %s", exc)
            time.sleep(self.check_interval)

    # ------------------------------------------------------------------
    # Analisis de logs
    # ------------------------------------------------------------------

    def _check_logs(self):
        """Lee las ultimas 50 lineas del log y detecta anomalias."""
        try:
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-50:]
        except FileNotFoundError:
            logger.debug("Log file no encontrado aun: %s", self.log_file)
            return

        if not lines:
            return

        # Conteo de patrones de error
        errors_500  = [l for l in lines if " status=500 " in l or '"500"' in l]
        errors_503  = [l for l in lines if " status=503 " in l or '"503"' in l]
        errors_429  = [l for l in lines if " status=429 " in l or '"429"' in l]
        timeouts    = [l for l in lines if "timeout" in l.lower() or "timed out" in l.lower()]
        exceptions  = [l for l in lines if "[ERROR]" in l]

        issues = []
        if len(errors_500) >= _THRESHOLD_500:
            issues.append(f"{len(errors_500)} errores HTTP 500 detectados")
        if len(errors_503) >= _THRESHOLD_503:
            issues.append(f"{len(errors_503)} errores HTTP 503 (Gemini no disponible)")
        if len(errors_429) >= _THRESHOLD_429:
            issues.append(f"{len(errors_429)} respuestas 429 (rate limit alcanzado)")
        if len(timeouts) >= _THRESHOLD_SLOW:
            issues.append(f"{len(timeouts)} timeouts detectados")
        if len(exceptions) >= 5:
            issues.append(f"{len(exceptions)} errores internos en logs recientes")

        if issues:
            # Evitar alertas duplicadas: comparar con la ultima
            if self.alerts:
                last_issues = self.alerts[-1].get("issues", [])
                if last_issues == issues:
                    return  # mismos problemas, no duplicar

            self._generate_alert(issues, lines)

    # ------------------------------------------------------------------
    # Generacion de alerta con Gemini
    # ------------------------------------------------------------------

    def _generate_alert(self, issues: List[str], log_lines: List[str]):
        """Pide a Gemini que diagnostique el problema y guarda la alerta."""
        diagnosis = self._ask_gemini(issues, log_lines)

        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "issues": issues,
            "diagnosis": diagnosis,
        }
        self.alerts.append(alert)

        # Mantener maximo 50 alertas en memoria
        if len(self.alerts) > 50:
            self.alerts = self.alerts[-50:]

        logger.warning(
            "ALERTA MONITOR | Problemas: %s | Diagnostico: %s",
            ", ".join(issues), diagnosis,
        )

        # Notificar a Discord si esta configurado
        self._send_discord(issues, diagnosis)

    def _send_discord(self, issues: List[str], diagnosis: str):
        """
        Envia una alerta al canal de Discord via webhook.
        Solo actua si DISCORD_WEBHOOK_URL esta definida como variable de entorno.
        """
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        if not webhook_url:
            return

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        issues_text = "\n".join(f"• {issue}" for issue in issues)

        message = (
            f"{_EMOJI_ALERT} **ALERTA — EduIA API**\n"
            f"🕐 `{timestamp}`\n\n"
            f"**Problemas detectados:**\n{issues_text}\n\n"
            f"**Diagnóstico IA:**\n{diagnosis}"
        )

        self._post_discord(message)

    def _notify_startup(self):
        """Envia un mensaje a Discord cuando la API arranca correctamente."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (
            f"{_EMOJI_OK} **EduIA API — iniciada correctamente**\n"
            f"🕐 `{timestamp}`\n"
            f"Agente supervisor activo, revisando logs cada {self.check_interval}s."
        )
        self._post_discord(message)

    def _post_discord(self, message: str):
        """Envia cualquier mensaje al webhook de Discord."""
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        if not webhook_url:
            return

        try:
            import subprocess
            import json as _json

            payload = _json.dumps({"content": message})
            # Usar PowerShell Invoke-WebRequest que ya demostro funcionar
            ps_cmd = (
                f'Invoke-WebRequest -Uri "{webhook_url}" '
                f'-Method POST '
                f'-Body \'{payload}\' '
                f'-ContentType "application/json" '
                f'-UseBasicParsing | Out-Null'
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                logger.info("Mensaje enviado a Discord correctamente.")
            else:
                logger.warning("Discord error: %s", result.stderr.strip())
        except Exception as exc:
            logger.warning("No se pudo enviar mensaje a Discord: %s", exc)

    def _ask_gemini(self, issues: List[str], log_lines: List[str]) -> str:
        """
        Llama a Gemini para obtener un diagnostico.
        Si no hay AI disponible, retorna un mensaje de fallback descriptivo.
        """
        if not self._ai_manager or not self._ai_manager.model:
            return (
                "Diagnostico automatico no disponible (Gemini sin configurar). "
                f"Problemas detectados: {', '.join(issues)}. Revisar logs manualmente."
            )

        # Tomar las ultimas 15 lineas para el contexto del prompt
        context_lines = "".join(log_lines[-15:])

        prompt = f"""Eres un agente de monitoreo de una API educativa con IA llamada EduIA.
Analiza los problemas detectados y explica en 2-3 oraciones que esta pasando
y que deberia revisarse. Se directo, tecnico y claro. Responde en espanol.

Problemas detectados:
{chr(10).join(f'- {issue}' for issue in issues)}

Ultimas lineas del log:
{context_lines}

Responde en maximo 3 oraciones."""

        try:
            diagnosis = self._ai_manager.generate(
                prompt=prompt,
                max_tokens=250,
                use_cache=False,   # alertas siempre frescas, sin cache
            )
            return diagnosis if diagnosis else "No se pudo obtener diagnostico de Gemini."
        except Exception as exc:
            logger.warning("Error llamando Gemini para diagnostico: %s", exc)
            return f"Error obteniendo diagnostico: {exc}"

    # ------------------------------------------------------------------
    # Estado publico — consumido por GET /api/monitor
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Retorna el estado actual del agente para el endpoint /api/monitor."""
        uptime_seconds = None
        try:
            from datetime import timezone
            started = datetime.fromisoformat(self.started_at)
            # Calcular uptime en segundos
            delta = datetime.utcnow() - started
            uptime_seconds = int(delta.total_seconds())
        except Exception:
            pass

        return {
            "monitoring": self._running,
            "log_file": self.log_file,
            "check_interval_seconds": self.check_interval,
            "started_at": self.started_at,
            "uptime_seconds": uptime_seconds,
            "ai_diagnosis_available": (
                self._ai_manager is not None
                and getattr(self._ai_manager, "model", None) is not None
            ),
            "total_alerts": len(self.alerts),
            "recent_alerts": self.alerts[-5:],   # ultimas 5 alertas
        }


# Instancia global — importada desde api.py
monitor_agent = APIMonitorAgent()
