# -*- coding: utf-8 -*-
"""
Módulo de Chat IA Semanal - Plataforma Educativa
Gestiona el chat con IA contextualizado por módulo
"""

import json
import time
from datetime import datetime
import html


class ModuleChatManager:
    """Gestor de chat IA por módulo"""
    
    def __init__(self, conn, ai_manager):
        self.conn = conn
        self.ai_manager = ai_manager

    @staticmethod
    def _resolve_model(ai_manager):
        """Devuelve siempre un GenerativeModel, sin importar si recibe AIManager o GenerativeModel"""
        if hasattr(ai_manager, 'model'):
            return ai_manager.model
        return ai_manager
    
    def configure_module_chat(self, module_id, content_type, content, file_name=None):
        """
        Configura el chat IA para un módulo
        
        Args:
            module_id: ID del módulo
            content_type: 'pdf' o 'text'
            content: Texto del contenido (extraído si es PDF)
            file_name: Nombre del archivo original (opcional)
        
        Returns:
            dict con 'success', 'content_id', 'questions', 'error'
        """
        try:
            # Validar longitud del contenido
            if len(content) < 50:
                return {
                    'success': False,
                    'error': 'El contenido es demasiado corto (mínimo 50 caracteres)'
                }
            
            # Truncar solo si es extremadamente largo (para evitar problemas de memoria)
            if len(content) > 500000:  # 500k caracteres = ~125k palabras
                content = content[:500000]
                truncated = True
            else:
                truncated = False
            
            # Sanitizar contenido
            content = self._sanitize_input(content)
            
            # Verificar si ya existe contenido para este módulo
            existing = self.conn.execute(
                "SELECT id FROM module_ai_chat_content WHERE module_id = ?",
                (module_id,)
            ).fetchone()
            
            if existing:
                # Actualizar contenido existente
                self.conn.execute("""
                    UPDATE module_ai_chat_content 
                    SET content_type = ?, content_text = ?, file_name = ?, updated_at = ?
                    WHERE module_id = ?
                """, (content_type, content, file_name, datetime.now(), module_id))
                content_id = existing['id']
            else:
                # Insertar nuevo contenido
                cursor = self.conn.execute("""
                    INSERT INTO module_ai_chat_content (module_id, content_type, content_text, file_name)
                    VALUES (?, ?, ?, ?)
                """, (module_id, content_type, content, file_name))
                content_id = cursor.lastrowid
            
            self.conn.commit()
            
            # Generar preguntas sugeridas
            questions = self.generate_suggested_questions(content, num_questions=4)
            
            # Guardar preguntas sugeridas
            self.update_suggested_questions(module_id, questions)
            
            result = {
                'success': True,
                'content_id': content_id,
                'questions': questions
            }
            
            if truncated:
                result['warning'] = 'El contenido fue truncado a 500,000 caracteres (límite de memoria)'
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error al configurar chat: {str(e)}'
            }
    
    def get_chat_content(self, module_id):
        """
        Obtiene el contenido de contexto de un módulo
        
        Args:
            module_id: ID del módulo
        
        Returns:
            dict con 'content_text', 'content_type', 'file_name', 'created_at'
            o None si no existe
        """
        try:
            row = self.conn.execute("""
                SELECT content_text, content_type, file_name, created_at
                FROM module_ai_chat_content
                WHERE module_id = ?
            """, (module_id,)).fetchone()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            print(f"Error obteniendo contenido de chat: {e}")
            return None
    
    def get_suggested_questions(self, module_id):
        """
        Obtiene las preguntas sugeridas de un módulo
        
        Args:
            module_id: ID del módulo
        
        Returns:
            Lista de dicts con 'id', 'question_text', 'order_index'
        """
        try:
            rows = self.conn.execute("""
                SELECT id, question_text, order_index
                FROM module_ai_chat_suggested_questions
                WHERE module_id = ?
                ORDER BY order_index ASC
            """, (module_id,)).fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"Error obteniendo preguntas sugeridas: {e}")
            return []
    
    def send_message(self, module_id, student_id, message):
        """
        Procesa un mensaje del estudiante y obtiene respuesta de IA
        
        Args:
            module_id: ID del módulo
            student_id: Username del estudiante
            message: Pregunta del estudiante
        
        Returns:
            dict con 'success', 'response', 'conversation_id', 'error'
        """
        try:
            # Validar longitud del mensaje
            if len(message) < 1 or len(message) > 1000:
                return {
                    'success': False,
                    'error': 'El mensaje debe tener entre 1 y 1000 caracteres'
                }
            
            # Limpiar espacios del mensaje (sin escapar HTML para no corromper el texto al mostrarlo)
            message = message.strip()
            
            # Obtener contenido de contexto
            content = self.get_chat_content(module_id)
            if not content:
                return {
                    'success': False,
                    'error': 'El chat no está configurado para este módulo'
                }
            
            # Obtener historial reciente (últimos 5 mensajes)
            history = self.get_conversation_history(module_id, student_id, limit=5)
            
            # Obtener respuesta de IA
            from utils_ai import get_contextualized_chat_response
            
            response = get_contextualized_chat_response(
                self._resolve_model(self.ai_manager),
                message,
                content['content_text'],
                history,
                max_output_tokens=2000
            )
            
            # Verificar si hubo error
            if not response or "Error" in response:
                return {
                    'success': False,
                    'error': 'No se pudo obtener respuesta de la IA'
                }
            
            # Truncar respuesta si es muy larga
            if len(response) > 5000:
                response = response[:5000] + "\n\n... (respuesta truncada)"
            
            # Guardar conversación
            cursor = self.conn.execute("""
                INSERT INTO module_ai_chat_conversations (module_id, student_id, message, response)
                VALUES (?, ?, ?, ?)
            """, (module_id, student_id, message, response))
            
            conversation_id = cursor.lastrowid
            self.conn.commit()
            
            return {
                'success': True,
                'response': response,
                'conversation_id': conversation_id
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error al procesar mensaje: {str(e)}'
            }
    
    def get_conversation_history(self, module_id, student_id, limit=50):
        """
        Obtiene el historial de conversación de un estudiante en un módulo
        
        Args:
            module_id: ID del módulo
            student_id: Username del estudiante
            limit: Número máximo de mensajes a retornar
        
        Returns:
            Lista de dicts con 'id', 'message', 'response', 'created_at'
        """
        try:
            rows = self.conn.execute("""
                SELECT id, message, response, created_at
                FROM module_ai_chat_conversations
                WHERE module_id = ? AND student_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (module_id, student_id, limit)).fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"Error obteniendo historial: {e}")
            return []
    
    def generate_suggested_questions(self, content_text, num_questions=4):
        """
        Genera preguntas sugeridas usando IA
        
        Args:
            content_text: Texto del contenido
            num_questions: Número de preguntas a generar (3-5)
        
        Returns:
            Lista de strings con las preguntas
        """
        try:
            from utils_ai import generate_module_questions
            
            # self.ai_manager puede ser AIManager o GenerativeModel
            questions = generate_module_questions(
                self._resolve_model(self.ai_manager),
                content_text,
                num_questions=num_questions
            )
            
            return questions
            
        except Exception as e:
            print(f"Error generando preguntas: {e}")
            # Fallback: preguntas genéricas
            return [
                "¿Cuál es el tema principal de este módulo?",
                "¿Puedes explicar los conceptos clave?",
                "¿Cómo se aplica esto en la práctica?",
                "¿Qué ejemplos hay en el contenido?"
            ][:num_questions]
    
    def delete_module_chat(self, module_id):
        """
        Elimina todo el contenido de chat de un módulo
        
        Args:
            module_id: ID del módulo
        
        Returns:
            True si se eliminó correctamente
        """
        try:
            # Eliminar contenido (las otras tablas se eliminan por CASCADE)
            self.conn.execute(
                "DELETE FROM module_ai_chat_content WHERE module_id = ?",
                (module_id,)
            )
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error eliminando chat: {e}")
            return False
    
    def update_suggested_questions(self, module_id, questions):
        """
        Actualiza las preguntas sugeridas de un módulo
        
        Args:
            module_id: ID del módulo
            questions: Lista de strings con las nuevas preguntas
        
        Returns:
            True si se actualizó correctamente
        """
        try:
            # Eliminar preguntas existentes
            self.conn.execute(
                "DELETE FROM module_ai_chat_suggested_questions WHERE module_id = ?",
                (module_id,)
            )
            
            # Insertar nuevas preguntas
            for i, question in enumerate(questions):
                self.conn.execute("""
                    INSERT INTO module_ai_chat_suggested_questions (module_id, question_text, order_index)
                    VALUES (?, ?, ?)
                """, (module_id, question, i))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error actualizando preguntas: {e}")
            return False
    
    def _sanitize_input(self, text):
        """
        Sanitiza entrada de texto para prevenir inyección
        
        Args:
            text: Texto a sanitizar
        
        Returns:
            Texto sanitizado
        """
        # Escapar HTML
        text = html.escape(text)
        return text


class GroupChatManager:
    """
    Gestor de chat grupal IA por módulo.
    Todos los alumnos y profesores pueden preguntar y ver las respuestas de todos.
    Usa el mismo contexto (PDF/texto) configurado por el profesor en el chat individual.
    """

    def __init__(self, conn, ai_manager):
        self.conn = conn
        self.ai_manager = ai_manager
        self._ensure_table()

    def _ensure_table(self):
        """Crea la tabla si no existe (por si la BD es antigua)"""
        try:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS module_ai_group_chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    user_role TEXT NOT NULL DEFAULT 'student',
                    message TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
                )
            ''')
            self.conn.commit()
        except Exception:
            pass

    def get_chat_content(self, module_id):
        """Reutiliza el mismo contexto del chat individual del módulo"""
        row = self.conn.execute(
            "SELECT content_text, content_type, file_name FROM module_ai_chat_content WHERE module_id = ?",
            (module_id,)
        ).fetchone()
        if row:
            return {'content_text': row[0], 'content_type': row[1], 'file_name': row[2]}
        return None

    def send_message(self, module_id, user_id, user_role, message):
        """
        Envía un mensaje al chat grupal y obtiene respuesta de la IA.
        Retorna dict con 'success', 'response', 'error'.
        """
        if not message or not message.strip():
            return {'success': False, 'error': 'Mensaje vacío'}

        message = message.strip()

        # Obtener contexto del módulo
        content = self.get_chat_content(module_id)
        if not content:
            return {'success': False, 'error': 'El chat no tiene contexto configurado. El profesor debe subir el material primero.'}

        # Obtener últimos 5 mensajes del grupo como historial
        history = self.get_messages(module_id, limit=5)

        # Construir prompt
        from utils_ai import get_contextualized_chat_response
        raw_model = ModuleChatManager._resolve_model(self.ai_manager)
        response_text = get_contextualized_chat_response(
            raw_model,
            message,
            content['content_text'],
            history=[{'message': m['message'], 'response': m['response']} for m in history]
        )

        # Guardar en BD
        try:
            self.conn.execute('''
                INSERT INTO module_ai_group_chat (module_id, user_id, user_role, message, response)
                VALUES (?, ?, ?, ?, ?)
            ''', (module_id, user_id, user_role, message, response_text))
            self.conn.commit()
            return {'success': True, 'response': response_text}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_messages(self, module_id, limit=50):
        """Obtiene los últimos mensajes del chat grupal (todos los usuarios)"""
        rows = self.conn.execute('''
            SELECT g.id, g.user_id, g.user_role, g.message, g.response, g.created_at,
                   COALESCE(u.full_name, g.user_id) as display_name
            FROM module_ai_group_chat g
            LEFT JOIN users u ON g.user_id = u.username
            WHERE g.module_id = ?
            ORDER BY g.created_at ASC
            LIMIT ?
        ''', (module_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def delete_all_messages(self, module_id):
        """Elimina todos los mensajes del chat grupal de un módulo (solo profesor)"""
        try:
            self.conn.execute('DELETE FROM module_ai_group_chat WHERE module_id = ?', (module_id,))
            self.conn.commit()
            return True
        except Exception:
            return False
