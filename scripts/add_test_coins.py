"""
Script para agregar monedas y puntos de prueba a un usuario
"""

from database import db_manager
from engagement import PointsManager

def add_test_rewards(username, coins=10000, points=1000000):
    """Agrega monedas y puntos de prueba a un usuario"""
    
    print(f"🎁 Agregando recompensas de prueba a {username}...")
    
    # Agregar puntos
    success = PointsManager.add_points(
        username, 
        points, 
        'test', 
        'Puntos de prueba para testing'
    )
    
    if success:
        print(f"✅ {points:,} puntos agregados")
    else:
        print(f"❌ Error agregando puntos")
    
    # Agregar monedas directamente en la BD
    conn = db_manager.get_connection()
    c = conn.cursor()
    
    try:
        # Verificar si existe el registro
        existing = c.execute('''
            SELECT total_coins FROM user_coins WHERE user_id = ?
        ''', (username,)).fetchone()
        
        if existing:
            # Actualizar
            c.execute('''
                UPDATE user_coins 
                SET total_coins = total_coins + ?,
                    coins_earned = coins_earned + ?
                WHERE user_id = ?
            ''', (coins, coins, username))
        else:
            # Crear
            c.execute('''
                INSERT INTO user_coins (user_id, total_coins, coins_earned)
                VALUES (?, ?, ?)
            ''', (username, coins, coins))
        
        conn.commit()
        print(f"✅ {coins:,} monedas agregadas")
        
        # Mostrar saldo final
        final_coins = c.execute('''
            SELECT total_coins FROM user_coins WHERE user_id = ?
        ''', (username,)).fetchone()
        
        final_points = c.execute('''
            SELECT total_points, level FROM user_points WHERE user_id = ?
        ''', (username,)).fetchone()
        
        print(f"\n📊 Saldo final de {username}:")
        print(f"   🪙 Monedas: {final_coins[0]:,}" if final_coins else "   🪙 Monedas: 0")
        print(f"   ⭐ Puntos: {final_points[0]:,} (Nivel {final_points[1]})" if final_points else "   ⭐ Puntos: 0")
        
        return True
        
    except Exception as e:
        print(f"❌ Error agregando monedas: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Agregar recompensas a alexander (username correcto)
    add_test_rewards('alexander', coins=10000, points=1000000)
    
    print("\n✅ ¡Listo! Ahora puedes probar la tienda con el usuario alexander")
