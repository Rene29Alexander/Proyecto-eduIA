"""Gestor de Tienda de Recompensas"""
from database import db_manager
import json
from datetime import datetime

class ShopManager:
    @staticmethod
    def get_shop_items(item_type=None):
        """Obtiene items de la tienda"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        if item_type:
            items = c.execute('''
                SELECT id, item_key, name, description, item_type, cost_coins, cost_points, stock, image_url
                FROM reward_shop_items
                WHERE is_available = 1 AND item_type = ?
                ORDER BY cost_coins ASC
            ''', (item_type,)).fetchall()
        else:
            items = c.execute('''
                SELECT id, item_key, name, description, item_type, cost_coins, cost_points, stock, image_url
                FROM reward_shop_items
                WHERE is_available = 1
                ORDER BY item_type, cost_coins ASC
            ''').fetchall()
        
        return [{'id': i[0], 'key': i[1], 'name': i[2], 'description': i[3], 
                 'type': i[4], 'cost_coins': i[5], 'cost_points': i[6], 
                 'stock': i[7], 'image_url': i[8]} for i in items]
    
    @staticmethod
    def _ensure_user_items_table():
        """Asegura que existe la tabla de items del usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_active_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                item_key TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        ''')
        conn.commit()
    
    @staticmethod
    def purchase_item(user_id, item_id):
        """Canjea un item de la tienda"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Obtener item
        item = c.execute('''
            SELECT cost_coins, cost_points, stock, item_key, metadata, name, item_type
            FROM reward_shop_items WHERE id = ?
        ''', (item_id,)).fetchone()
        
        if not item:
            return False, "Item no encontrado"
        
        cost_coins, cost_points, stock, item_key, metadata, name, item_type = item
        
        # Verificar stock
        if stock == 0:
            return False, "Item agotado"
        
        # Verificar saldo
        from .points_manager import PointsManager
        coins_data = PointsManager.get_user_coins(user_id)
        
        if coins_data['total_coins'] < cost_coins:
            return False, "Monedas insuficientes"
        
        # Realizar canje (gastar monedas)
        success, msg = PointsManager.spend_coins(user_id, cost_coins)
        if not success:
            return False, msg
        
        # Registrar canje
        c.execute('''
            INSERT INTO user_purchases (user_id, item_id, coins_spent, points_spent)
            VALUES (?, ?, ?, ?)
        ''', (user_id, item_id, cost_coins, cost_points))
        
        # Actualizar stock
        if stock > 0:
            c.execute('UPDATE reward_shop_items SET stock = stock - 1 WHERE id = ?', (item_id,))
        
        conn.commit()
        
        # Aplicar efecto del item según su tipo
        effect_message = ShopManager._apply_item_effect(user_id, item_key, name, item_type, metadata)
        
        return True, f"✅ Canje exitoso. {effect_message}"
    
    @staticmethod
    def _apply_item_effect(user_id, item_key, name, item_type, metadata):
        """Aplica el efecto del item canjeado"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Asegurar que existe la tabla
        ShopManager._ensure_user_items_table()
        
        # Parsear metadata si es string
        if isinstance(metadata, str):
            try:
                metadata_dict = json.loads(metadata) if metadata else {}
            except:
                metadata_dict = {}
        else:
            metadata_dict = metadata or {}
        
        if item_key == 'feature_freeze':
            # Congelador de racha - agregar a items activos
            from .streak_manager import StreakManager
            StreakManager.add_freeze(user_id, 1)
            
            c.execute('''
                INSERT INTO user_active_items (user_id, item_key, item_name, item_type, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, item_key, name, item_type, json.dumps({'freezes': 1})))
            conn.commit()
            
            return "❄️ ¡Congelador de racha agregado! Se activará automáticamente si pierdes tu racha."
            
        elif item_type == 'cosmetic':
            # Cosmético - registrar con metadata
            c.execute('''
                INSERT INTO user_active_items (user_id, item_key, item_name, item_type, is_active, metadata)
                VALUES (?, ?, ?, ?, 1, ?)
            ''', (user_id, item_key, name, item_type, json.dumps(metadata_dict)))
            conn.commit()
            
            return f"🎨 ¡{name} equipado! Ve a tu perfil para verlo."
        
        elif item_type == 'content':
            # Contenido premium - registrar acceso permanente
            c.execute('''
                INSERT INTO user_active_items (user_id, item_key, item_name, item_type, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (user_id, item_key, name, item_type))
            conn.commit()
            
            return f"📚 ¡Acceso a '{name}' desbloqueado permanentemente! Revisa la sección de cursos premium."
            
        elif item_type == 'certificate':
            # Certificado personalizado - registrar solicitud
            c.execute('''
                INSERT INTO user_active_items (user_id, item_key, item_name, item_type, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, item_key, name, item_type, json.dumps({'status': 'pending', 'requested_at': datetime.now().isoformat()})))
            conn.commit()
            
            return "🎓 ¡Certificado personalizado solicitado! El administrador te contactará para los detalles."
        
        return "Item canjeado exitosamente."
    
    @staticmethod
    def get_user_purchases(user_id):
        """Obtiene compras del usuario"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        purchases = c.execute('''
            SELECT rsi.name, up.coins_spent, up.purchased_at, up.status
            FROM user_purchases up
            JOIN reward_shop_items rsi ON up.item_id = rsi.id
            WHERE up.user_id = ?
            ORDER BY up.purchased_at DESC
        ''', (user_id,)).fetchall()
        
        return [{'name': p[0], 'coins_spent': p[1], 'purchased_at': p[2], 'status': p[3]} 
                for p in purchases]
    
    @staticmethod
    def get_user_active_items(user_id, item_type=None):
        """Obtiene items activos del usuario"""
        ShopManager._ensure_user_items_table()
        
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        if item_type:
            items = c.execute('''
                SELECT item_key, item_name, item_type, activated_at, metadata
                FROM user_active_items
                WHERE user_id = ? AND item_type = ? AND is_active = 1
                ORDER BY activated_at DESC
            ''', (user_id, item_type)).fetchall()
        else:
            items = c.execute('''
                SELECT item_key, item_name, item_type, activated_at, metadata
                FROM user_active_items
                WHERE user_id = ? AND is_active = 1
                ORDER BY activated_at DESC
            ''', (user_id,)).fetchall()
        
        return [{'key': i[0], 'name': i[1], 'type': i[2], 'activated_at': i[3], 
                 'metadata': json.loads(i[4]) if i[4] else {}} for i in items]
    
    @staticmethod
    def has_premium_content(user_id, content_key):
        """Verifica si el usuario tiene acceso a contenido premium"""
        active_items = ShopManager.get_user_active_items(user_id, 'content')
        return any(item['key'] == content_key for item in active_items)
    
    @staticmethod
    def get_active_cosmetics(user_id):
        """Obtiene cosméticos activos del usuario"""
        return ShopManager.get_user_active_items(user_id, 'cosmetic')
    
    @staticmethod
    def unequip_cosmetic(user_id, cosmetic_key):
        """Desequipa un cosmético (lo marca como inactivo pero no lo elimina)"""
        ShopManager._ensure_user_items_table()
        
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            UPDATE user_active_items
            SET is_active = 0
            WHERE user_id = ? AND item_key = ?
        ''', (user_id, cosmetic_key))
        conn.commit()
        
        return True
    
    @staticmethod
    def equip_cosmetic(user_id, cosmetic_key):
        """Equipa un cosmético que ya fue canjeado"""
        ShopManager._ensure_user_items_table()
        
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Verificar si el usuario tiene este cosmético
        existing = c.execute('''
            SELECT id FROM user_active_items
            WHERE user_id = ? AND item_key = ?
        ''', (user_id, cosmetic_key)).fetchone()
        
        if existing:
            # Reactivar el cosmético
            c.execute('''
                UPDATE user_active_items
                SET is_active = 1
                WHERE user_id = ? AND item_key = ?
            ''', (user_id, cosmetic_key))
            conn.commit()
            return True, "Cosmético equipado"
        else:
            return False, "No tienes este cosmético"
