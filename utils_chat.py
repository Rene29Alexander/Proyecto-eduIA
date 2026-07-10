# -*- coding: utf-8 -*-
"""
Módulo de Chat Privado entre Usuarios - Plataforma Educativa
Gestiona conversaciones privadas entre estudiantes y profesores
"""

import html
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from database import db_manager
from utils_notifications import notification_manager


class ChatManager:
    """Gestor del sistema de chat privado entre usuarios"""
    
    def __init__(self):
        """Inicializa el gestor con conexión a BD"""
        self.conn = db_manager.get_connection()
    
    def create_or_get_conversation(
        self, 
        user1_id: str, 
        user2_id: str, 
        course_id: int
    ) -> Optional[int]:
        """
        Crea una nueva conversación o retorna el ID de una existente.
        
        Args:
            user1_id: Username del primer participante
            user2_id: Username del segundo participante
            course_id: ID del curso en contexto
            
        Returns:
            ID de la conversación o None si hay error
            
        Validations:
            - Ambos usuarios deben estar inscritos en el curso
            - Los usuarios deben ser diferentes
            - Al menos uno debe ser profesor o ambos estudiantes
        """
        try:
            # Validar que los usuarios sean diferentes
            if user1_id == user2_id:
                return None
            
            # Validar inscripción en el curso
            if not self.validate_course_enrollment(user1_id, user2_id, course_id):
                return None
            
            # Ordenar user_id alfabéticamente para garantizar unicidad
            if user1_id > user2_id:
                user1_id, user2_id = user2_id, user1_id
            
            # Buscar conversación existente
            existing = self.conn.execute("""
                SELECT id FROM conversations
                WHERE user1_id = ? AND user2_id = ? AND course_id = ?
            """, (user1_id, user2_id, course_id)).fetchone()
            
            if existing:
                return existing['id']
            
            # Crear nueva conversación
            cursor = self.conn.execute("""
                INSERT INTO conversations (user1_id, user2_id, course_id)
                VALUES (?, ?, ?)
            """, (user1_id, user2_id, course_id))
            
            self.conn.commit()
            return cursor.lastrowid
            
        except Exception as e:
            print(f"Error creando conversación: {e}")
            return None
    
    def validate_course_enrollment(
        self, 
        user1_id: str, 
        user2_id: str, 
        course_id: int
    ) -> bool:
        """
        Valida que ambos usuarios estén inscritos en el curso.
        
        Args:
            user1_id: Username del primer usuario
            user2_id: Username del segundo usuario
            course_id: ID del curso
            
        Returns:
            True si ambos están inscritos, False en caso contrario
        """
        try:
            # Obtener roles de los usuarios
            user1 = self.conn.execute(
                "SELECT role FROM users WHERE username = ?", 
                (user1_id,)
            ).fetchone()
            
            user2 = self.conn.execute(
                "SELECT role FROM users WHERE username = ?", 
                (user2_id,)
            ).fetchone()
            
            if not user1 or not user2:
                return False
            
            # Si uno de los usuarios es admin, permitir conversación sin validación adicional
            if user1['role'] == 'admin' or user2['role'] == 'admin':
                # Solo verificar que el otro usuario (no-admin) esté relacionado con el curso
                non_admin_id = user2_id if user1['role'] == 'admin' else user1_id
                non_admin_role = user2['role'] if user1['role'] == 'admin' else user1['role']
                
                if non_admin_role == 'teacher':
                    teacher_course = self.conn.execute(
                        "SELECT 1 FROM courses WHERE id = ? AND teacher_id = ?",
                        (course_id, non_admin_id)
                    ).fetchone()
                    return teacher_course is not None
                elif non_admin_role == 'student':
                    enrollment = self.conn.execute(
                        "SELECT 1 FROM enrollments WHERE student_id = ? AND course_id = ?",
                        (non_admin_id, course_id)
                    ).fetchone()
                    return enrollment is not None
                else:
                    return True  # Si el no-admin también es admin
            
            # Si uno es profesor, verificar que sea profesor del curso
            if user1['role'] == 'teacher':
                teacher_course = self.conn.execute(
                    "SELECT 1 FROM courses WHERE id = ? AND teacher_id = ?",
                    (course_id, user1_id)
                ).fetchone()
                if not teacher_course:
                    return False
            else:
                # Si es estudiante, verificar inscripción
                enrollment1 = self.conn.execute(
                    "SELECT 1 FROM enrollments WHERE student_id = ? AND course_id = ?",
                    (user1_id, course_id)
                ).fetchone()
                if not enrollment1:
                    return False
            
            # Verificar segundo usuario
            if user2['role'] == 'teacher':
                teacher_course = self.conn.execute(
                    "SELECT 1 FROM courses WHERE id = ? AND teacher_id = ?",
                    (course_id, user2_id)
                ).fetchone()
                if not teacher_course:
                    return False
            else:
                enrollment2 = self.conn.execute(
                    "SELECT 1 FROM enrollments WHERE student_id = ? AND course_id = ?",
                    (user2_id, course_id)
                ).fetchone()
                if not enrollment2:
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error validando inscripción: {e}")
            return False
    
    def validate_user_access(
        self, 
        conversation_id: int, 
        user_id: str
    ) -> bool:
        """
        Valida que un usuario tenga acceso a una conversación.
        
        Args:
            conversation_id: ID de la conversación
            user_id: Username del usuario
            
        Returns:
            True si el usuario es participante, False en caso contrario
        """
        try:
            conversation = self.conn.execute("""
                SELECT user1_id, user2_id FROM conversations
                WHERE id = ?
            """, (conversation_id,)).fetchone()
            
            if not conversation:
                return False
            
            return user_id in (conversation['user1_id'], conversation['user2_id'])
            
        except Exception as e:
            print(f"Error validando acceso: {e}")
            return False
    
    def send_message(
        self, 
        conversation_id: int, 
        sender_id: str, 
        message_text: str
    ) -> Optional[int]:
        """
        Envía un mensaje de texto en una conversación.
        
        Args:
            conversation_id: ID de la conversación
            sender_id: Username del remitente
            message_text: Contenido del mensaje
            
        Returns:
            ID del mensaje creado o None si hay error
            
        Validations:
            - El remitente debe ser participante de la conversación
            - El texto no debe estar vacío
            - El texto debe ser sanitizado (prevenir XSS)
        """
        try:
            # Validar acceso
            if not self.validate_user_access(conversation_id, sender_id):
                return None
            
            # Validar que el mensaje no esté vacío
            if not message_text or not message_text.strip():
                return None
            
            # NO escapar aquí - se escapará en el render para evitar doble escape
            # Solo limpiar espacios
            clean_text = message_text.strip()
            
            # Validar longitud máxima (5000 caracteres)
            if len(clean_text) > 5000:
                return None
            
            # Obtener el destinatario
            conversation = self.conn.execute("""
                SELECT user1_id, user2_id FROM conversations
                WHERE id = ?
            """, (conversation_id,)).fetchone()
            
            recipient_id = conversation['user2_id'] if conversation['user1_id'] == sender_id else conversation['user1_id']
            
            # Insertar mensaje
            cursor = self.conn.execute("""
                INSERT INTO private_messages 
                (conversation_id, sender_id, recipient_id, message_text)
                VALUES (?, ?, ?, ?)
            """, (conversation_id, sender_id, recipient_id, clean_text))
            
            # Actualizar last_message_at en conversación
            self.conn.execute("""
                UPDATE conversations
                SET last_message_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
            
            self.conn.commit()
            message_id = cursor.lastrowid
            
            # Enviar notificación al destinatario
            try:
                sender = self.conn.execute(
                    "SELECT first_name, last_name FROM users WHERE username = ?",
                    (sender_id,)
                ).fetchone()
                
                if sender:
                    sender_name = f"{sender['first_name']} {sender['last_name']}"
                    notification_manager.notify_new_message(
                        recipient_id=recipient_id,
                        sender_name=sender_name,
                        message_preview=clean_text[:100],  # Preview truncado
                        conversation_id=conversation_id,
                        has_attachment=False
                    )
            except Exception as e:
                print(f"Error enviando notificación: {e}")
                # No fallar el envío del mensaje si falla la notificación
            
            return message_id
            
        except Exception as e:
            print(f"Error enviando mensaje: {e}")
            self.conn.rollback()
            return None
    
    def send_attachment(
        self, 
        message_id: int, 
        file_name: str, 
        file_content: bytes, 
        file_type: str, 
        file_size: int
    ) -> bool:
        """
        Adjunta un archivo a un mensaje.
        
        Args:
            message_id: ID del mensaje
            file_name: Nombre del archivo
            file_content: Contenido binario del archivo
            file_type: Tipo MIME del archivo
            file_size: Tamaño en bytes
            
        Returns:
            True si se adjuntó exitosamente, False en caso contrario
            
        Validations:
            - Tipo de archivo debe ser: PDF, PNG, JPG, JPEG, GIF, DOC, DOCX, TXT
            - Tamaño máximo: 10 MB (10485760 bytes)
        """
        try:
            # Validar tamaño
            if file_size > 10485760:  # 10 MB
                return False
            
            # Validar tipo de archivo
            allowed_types = [
                'application/pdf',
                'image/png',
                'image/jpeg',
                'image/gif',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain'
            ]
            
            if file_type not in allowed_types:
                return False
            
            # Insertar adjunto
            self.conn.execute("""
                INSERT INTO message_attachments 
                (message_id, file_name, file_type, file_size, file_content)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, file_name, file_type, file_size, file_content))
            
            # Marcar mensaje como con adjunto
            self.conn.execute("""
                UPDATE private_messages
                SET has_attachment = 1
                WHERE id = ?
            """, (message_id,))
            
            self.conn.commit()
            
            # Enviar notificación actualizada con indicador de adjunto
            try:
                message = self.conn.execute("""
                    SELECT pm.sender_id, pm.recipient_id, pm.message_text, pm.conversation_id
                    FROM private_messages pm
                    WHERE pm.id = ?
                """, (message_id,)).fetchone()
                
                if message:
                    sender = self.conn.execute(
                        "SELECT first_name, last_name FROM users WHERE username = ?",
                        (message['sender_id'],)
                    ).fetchone()
                    
                    if sender:
                        sender_name = f"{sender['first_name']} {sender['last_name']}"
                        notification_manager.notify_new_message(
                            recipient_id=message['recipient_id'],
                            sender_name=sender_name,
                            message_preview=message['message_text'],
                            conversation_id=message['conversation_id'],
                            has_attachment=True
                        )
            except Exception as e:
                print(f"Error enviando notificación de adjunto: {e}")
            
            return True
            
        except Exception as e:
            print(f"Error adjuntando archivo: {e}")
            self.conn.rollback()
            return False
    
    def get_conversation_history(
        self, 
        conversation_id: int, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict]:
        """
        Obtiene el historial de mensajes de una conversación.
        
        Args:
            conversation_id: ID de la conversación
            user_id: Username del usuario solicitante
            limit: Número máximo de mensajes a retornar
            offset: Desplazamiento para paginación
            
        Returns:
            Lista de diccionarios con datos de mensajes
            
        Validations:
            - El usuario debe ser participante de la conversación
            - Retornar mensajes en orden cronológico descendente
        """
        try:
            # Validar acceso
            if not self.validate_user_access(conversation_id, user_id):
                return []
            
            # Obtener mensajes
            messages = self.conn.execute("""
                SELECT 
                    pm.id,
                    pm.sender_id,
                    pm.recipient_id,
                    pm.message_text,
                    pm.is_read,
                    pm.has_attachment,
                    pm.sent_at,
                    pm.read_at,
                    u.first_name || ' ' || u.last_name as sender_name,
                    u.avatar as sender_avatar
                FROM private_messages pm
                JOIN users u ON pm.sender_id = u.username
                WHERE pm.conversation_id = ?
                ORDER BY pm.sent_at DESC
                LIMIT ? OFFSET ?
            """, (conversation_id, limit, offset)).fetchall()
            
            result = []
            for msg in messages:
                msg_dict = dict(msg)
                
                # Obtener adjuntos si existen
                if msg['has_attachment']:
                    attachments = self.conn.execute("""
                        SELECT id, file_name, file_type, file_size, uploaded_at
                        FROM message_attachments
                        WHERE message_id = ?
                    """, (msg['id'],)).fetchall()
                    msg_dict['attachments'] = [dict(att) for att in attachments]
                else:
                    msg_dict['attachments'] = []
                
                result.append(msg_dict)
            
            return result
            
        except Exception as e:
            print(f"Error obteniendo historial: {e}")
            return []
    
    def mark_messages_as_read(
        self, 
        conversation_id: int, 
        user_id: str
    ) -> int:
        """
        Marca todos los mensajes no leídos como leídos.
        
        Args:
            conversation_id: ID de la conversación
            user_id: Username del usuario que lee los mensajes
            
        Returns:
            Número de mensajes marcados como leídos
            
        Validations:
            - Solo marcar mensajes donde el usuario es el destinatario
        """
        try:
            # Validar acceso
            if not self.validate_user_access(conversation_id, user_id):
                return 0
            
            # Marcar como leídos
            cursor = self.conn.execute("""
                UPDATE private_messages
                SET is_read = 1, read_at = CURRENT_TIMESTAMP
                WHERE conversation_id = ? 
                AND recipient_id = ? 
                AND is_read = 0
            """, (conversation_id, user_id))
            
            self.conn.commit()
            return cursor.rowcount
            
        except Exception as e:
            print(f"Error marcando mensajes como leídos: {e}")
            self.conn.rollback()
            return 0
    
    def get_user_contacts(
        self, 
        user_id: str, 
        course_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Obtiene la lista de contactos disponibles para un usuario.
        
        Args:
            user_id: Username del usuario
            course_id: ID del curso (opcional, filtra por curso)
            
        Returns:
            Lista de diccionarios con datos de contactos
            
        Logic:
            - Si es estudiante: retornar otros estudiantes del curso + profesor
            - Si es profesor: retornar todos los estudiantes de sus cursos
            - Si es admin: retornar todos los usuarios con los que tiene conversaciones activas
            - Incluir contador de mensajes no leídos por contacto
            - Incluir preview del último mensaje
            - Ordenar por: mensajes no leídos primero, luego por último mensaje
        """
        try:
            # Obtener rol del usuario
            user = self.conn.execute(
                "SELECT role FROM users WHERE username = ?", 
                (user_id,)
            ).fetchone()
            
            if not user:
                return []
            
            contacts = []
            
            if user['role'] == 'admin':
                # Admin: obtener todos los usuarios con conversaciones activas
                # Buscar conversaciones donde el admin es user1_id o user2_id
                conversations = self.conn.execute("""
                    SELECT DISTINCT 
                        CASE 
                            WHEN c.user1_id = ? THEN c.user2_id
                            ELSE c.user1_id
                        END as contact_username
                    FROM conversations c
                    WHERE c.user1_id = ? OR c.user2_id = ?
                """, (user_id, user_id, user_id)).fetchall()
                
                # Obtener información de cada contacto
                for conv in conversations:
                    contact_info = self.conn.execute("""
                        SELECT username, first_name, last_name, role, avatar
                        FROM users
                        WHERE username = ?
                    """, (conv['contact_username'],)).fetchone()
                    
                    if contact_info:
                        contacts.append(dict(contact_info))
            
            elif user['role'] == 'student':
                # Estudiante: obtener compañeros y profesores del curso
                if course_id:
                    # Obtener compañeros estudiantes
                    students = self.conn.execute("""
                        SELECT DISTINCT u.username, u.first_name, u.last_name, u.role, u.avatar
                        FROM users u
                        JOIN enrollments e ON u.username = e.student_id
                        WHERE e.course_id = ? AND u.username != ?
                    """, (course_id, user_id)).fetchall()
                    
                    # Obtener profesor del curso
                    teacher = self.conn.execute("""
                        SELECT u.username, u.first_name, u.last_name, u.role, u.avatar
                        FROM users u
                        JOIN courses c ON u.username = c.teacher_id
                        WHERE c.id = ?
                    """, (course_id,)).fetchone()
                    
                    contacts = [dict(s) for s in students]
                    if teacher:
                        contacts.append(dict(teacher))
                else:
                    # Obtener todos los contactos de todos los cursos
                    all_contacts = self.conn.execute("""
                        SELECT DISTINCT u.username, u.first_name, u.last_name, u.role, u.avatar
                        FROM users u
                        WHERE u.username IN (
                            SELECT e2.student_id FROM enrollments e2
                            WHERE e2.course_id IN (
                                SELECT e1.course_id FROM enrollments e1
                                WHERE e1.student_id = ?
                            ) AND e2.student_id != ?
                        )
                        OR u.username IN (
                            SELECT c.teacher_id FROM courses c
                            WHERE c.id IN (
                                SELECT e.course_id FROM enrollments e
                                WHERE e.student_id = ?
                            )
                        )
                    """, (user_id, user_id, user_id)).fetchall()
                    contacts = [dict(c) for c in all_contacts]
            
            else:  # teacher
                # Profesor: obtener todos los estudiantes de sus cursos
                if course_id:
                    students = self.conn.execute("""
                        SELECT DISTINCT u.username, u.first_name, u.last_name, u.role, u.avatar
                        FROM users u
                        JOIN enrollments e ON u.username = e.student_id
                        WHERE e.course_id = ? AND e.course_id IN (
                            SELECT id FROM courses WHERE teacher_id = ?
                        )
                    """, (course_id, user_id)).fetchall()
                    contacts = [dict(s) for s in students]
                else:
                    students = self.conn.execute("""
                        SELECT DISTINCT u.username, u.first_name, u.last_name, u.role, u.avatar
                        FROM users u
                        JOIN enrollments e ON u.username = e.student_id
                        WHERE e.course_id IN (
                            SELECT id FROM courses WHERE teacher_id = ?
                        )
                    """, (user_id,)).fetchall()
                    contacts = [dict(s) for s in students]
            
            # Enriquecer con información de conversación
            enriched_contacts = []
            for contact in contacts:
                # Obtener conversación existente
                user1, user2 = sorted([user_id, contact['username']])
                conv = self.conn.execute("""
                    SELECT c.id, c.last_message_at, c.course_id, co.name as course_name, co.code as course_code
                    FROM conversations c
                    JOIN courses co ON c.course_id = co.id
                    WHERE c.user1_id = ? AND c.user2_id = ?
                """, (user1, user2)).fetchone()
                
                if conv:
                    # Verificar si hay mensajes en la conversación
                    has_messages = self.conn.execute("""
                        SELECT COUNT(*) as count FROM private_messages
                        WHERE conversation_id = ?
                    """, (conv['id'],)).fetchone()
                    
                    # Solo incluir si hay mensajes
                    if has_messages['count'] > 0:
                        contact['conversation_id'] = conv['id']
                        contact['last_message_at'] = conv['last_message_at']
                        contact['course_name'] = conv['course_name']
                        contact['course_code'] = conv.get('course_code', '')
                        
                        # Obtener contador de no leídos
                        unread = self.conn.execute("""
                            SELECT COUNT(*) as count FROM private_messages
                            WHERE conversation_id = ? 
                            AND recipient_id = ? 
                            AND is_read = 0
                        """, (conv['id'], user_id)).fetchone()
                        contact['unread_count'] = unread['count']
                        
                        # Obtener preview del último mensaje
                        last_msg = self.conn.execute("""
                            SELECT message_text, sender_id FROM private_messages
                            WHERE conversation_id = ?
                            ORDER BY sent_at DESC
                            LIMIT 1
                        """, (conv['id'],)).fetchone()
                        
                        if last_msg:
                            preview = last_msg['message_text'][:100]
                            if last_msg['sender_id'] == user_id:
                                preview = f"Tú: {preview}"
                            contact['last_message_preview'] = preview
                        else:
                            contact['last_message_preview'] = ""
                        
                        enriched_contacts.append(contact)
            
            # Ordenar: no leídos primero, luego por último mensaje
            enriched_contacts.sort(
                key=lambda x: (
                    -x['unread_count'],
                    x['last_message_at'] if x['last_message_at'] else ''
                ),
                reverse=True
            )
            
            return enriched_contacts
            
        except Exception as e:
            print(f"Error obteniendo contactos: {e}")
            return []
    
    def search_contacts(
        self, 
        user_id: str, 
        search_term: str, 
        course_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Busca contactos por nombre.
        
        Args:
            user_id: Username del usuario
            search_term: Término de búsqueda
            course_id: ID del curso (opcional)
            
        Returns:
            Lista filtrada de contactos que coinciden con el término
            
        Logic:
            - Búsqueda case-insensitive
            - Buscar en nombre completo (first_name + last_name)
            - Aplicar mismas reglas de visibilidad que get_user_contacts
        """
        try:
            # Obtener todos los contactos
            all_contacts = self.get_user_contacts(user_id, course_id)
            
            # Filtrar por término de búsqueda
            search_lower = search_term.lower()
            filtered = [
                c for c in all_contacts
                if search_lower in f"{c['first_name']} {c['last_name']}".lower()
            ]
            
            return filtered
            
        except Exception as e:
            print(f"Error buscando contactos: {e}")
            return []
    
    def get_unread_count(
        self, 
        user_id: str
    ) -> int:
        """
        Obtiene el conteo total de mensajes no leídos.
        
        Args:
            user_id: Username del usuario
            
        Returns:
            Número total de mensajes no leídos
        """
        try:
            result = self.conn.execute("""
                SELECT COUNT(*) as count FROM private_messages
                WHERE recipient_id = ? AND is_read = 0
            """, (user_id,)).fetchone()
            
            return result['count'] if result else 0
            
        except Exception as e:
            print(f"Error obteniendo contador de no leídos: {e}")
            return 0
    
    def get_conversation_unread_count(
        self, 
        conversation_id: int, 
        user_id: str
    ) -> int:
        """
        Obtiene el conteo de mensajes no leídos en una conversación.
        
        Args:
            conversation_id: ID de la conversación
            user_id: Username del usuario
            
        Returns:
            Número de mensajes no leídos en la conversación
        """
        try:
            result = self.conn.execute("""
                SELECT COUNT(*) as count FROM private_messages
                WHERE conversation_id = ? 
                AND recipient_id = ? 
                AND is_read = 0
            """, (conversation_id, user_id)).fetchone()
            
            return result['count'] if result else 0
            
        except Exception as e:
            print(f"Error obteniendo contador de no leídos: {e}")
            return 0
    
    def get_attachment(
        self, 
        attachment_id: int, 
        user_id: str
    ) -> Optional[Dict]:
        """
        Obtiene un archivo adjunto.
        
        Args:
            attachment_id: ID del adjunto
            user_id: Username del usuario solicitante
            
        Returns:
            Diccionario con datos del archivo o None si no tiene acceso
            
        Validations:
            - Verificar que el usuario sea participante de la conversación
        """
        try:
            # Obtener adjunto y verificar permisos
            attachment = self.conn.execute("""
                SELECT 
                    ma.id,
                    ma.message_id,
                    ma.file_name,
                    ma.file_type,
                    ma.file_size,
                    ma.file_content,
                    ma.uploaded_at,
                    pm.conversation_id
                FROM message_attachments ma
                JOIN private_messages pm ON ma.message_id = pm.id
                WHERE ma.id = ?
            """, (attachment_id,)).fetchone()
            
            if not attachment:
                return None
            
            # Validar acceso a la conversación
            if not self.validate_user_access(attachment['conversation_id'], user_id):
                return None
            
            return dict(attachment)
            
        except Exception as e:
            print(f"Error obteniendo adjunto: {e}")
            return None
    
    def delete_conversation(
        self,
        conversation_id: int,
        user_id: str
    ) -> bool:
        """
        Elimina una conversación y todos sus mensajes.
        
        Args:
            conversation_id: ID de la conversación
            user_id: Username del usuario que solicita eliminar
            
        Returns:
            True si se eliminó correctamente, False en caso contrario
            
        Validations:
            - El usuario debe ser participante de la conversación
            - Se eliminan todos los mensajes y adjuntos asociados
        """
        try:
            # Validar que el usuario sea participante
            if not self.validate_user_access(conversation_id, user_id):
                return False
            
            # Eliminar adjuntos
            self.conn.execute("""
                DELETE FROM message_attachments
                WHERE message_id IN (
                    SELECT id FROM private_messages
                    WHERE conversation_id = ?
                )
            """, (conversation_id,))
            
            # Eliminar mensajes
            self.conn.execute("""
                DELETE FROM private_messages
                WHERE conversation_id = ?
            """, (conversation_id,))
            
            # Eliminar conversación
            self.conn.execute("""
                DELETE FROM conversations
                WHERE id = ?
            """, (conversation_id,))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error eliminando conversación: {e}")
            self.conn.rollback()
            return False


# Instancia global del gestor de chat
chat_manager = ChatManager()


def format_timestamp(timestamp) -> str:
    """
    Formatea timestamp de manera legible.
    
    Args:
        timestamp: Timestamp como string o datetime
        
    Returns:
        String formateado según la antigüedad del timestamp
        
    Logic:
        - Menos de 1 hora: "HH:MM"
        - Hoy: "Hoy HH:MM"
        - Ayer: "Ayer HH:MM"
        - Más de 2 días: "DD/MM/YYYY HH:MM"
    """
    try:
        # Convertir string a datetime si es necesario
        if isinstance(timestamp, str):
            # Intentar varios formatos
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f']:
                try:
                    dt = datetime.strptime(timestamp, fmt)
                    break
                except ValueError:
                    continue
            else:
                return timestamp  # Si no se puede parsear, retornar original
        else:
            dt = timestamp
        
        # Calcular diferencia con ahora
        now = datetime.now()
        diff = now - dt
        
        # Menos de 1 hora - mostrar solo la hora
        if diff.total_seconds() < 3600:
            return dt.strftime('%H:%M')
        
        # Hoy
        if dt.date() == now.date():
            return f"Hoy {dt.strftime('%H:%M')}"
        
        # Ayer
        if (now.date() - dt.date()).days == 1:
            return f"Ayer {dt.strftime('%H:%M')}"
        
        # Más de 2 días
        return dt.strftime('%d/%m/%Y %H:%M')
        
    except Exception as e:
        print(f"Error formateando timestamp: {e}")
        return str(timestamp)
