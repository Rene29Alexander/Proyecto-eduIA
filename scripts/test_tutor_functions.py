# -*- coding: utf-8 -*-
"""
Test script para las nuevas funciones del tutor IA
"""

from utils_ai import AIManager, analyze_code_with_hints, provide_corrected_code_with_explanation

# Código de prueba con errores
test_code = """
x = input('Ingresa un número: ')
y = input('Ingresa otro número: ')
suma = x + y
print('La suma es:', suma)
"""

print("=" * 60)
print("PRUEBA 1: Análisis con Pistas")
print("=" * 60)

try:
    ai_manager = AIManager()
    
    if ai_manager.model:
        print("\n✅ Modelo de IA inicializado correctamente")
        print(f"Modelo actual: {ai_manager.current_model_name}")
        
        # Probar análisis con pistas
        print("\n🔍 Analizando código con errores...")
        result = analyze_code_with_hints(
            ai_manager.model,
            test_code,
            "Python",
            "Sumar dos números ingresados por el usuario"
        )
        
        print(f"\n¿Tiene errores? {result['has_errors']}")
        print(f"Errores encontrados: {len(result['errors_found'])}")
        print(f"Pistas proporcionadas: {len(result['hints'])}")
        print(f"Áreas de estudio: {len(result['areas_to_study'])}")
        
        if result['errors_found']:
            print("\n❌ Errores detectados:")
            for error in result['errors_found']:
                print(f"  - Línea {error['line']}: {error['description']}")
        
        if result['hints']:
            print("\n💡 Pistas:")
            for hint in result['hints']:
                print(f"  - {hint['hint']}")
        
        print("\n" + "=" * 60)
        print("PRUEBA 2: Código Corregido con Explicaciones")
        print("=" * 60)
        
        # Probar corrección con explicaciones
        print("\n🔧 Generando código corregido...")
        result2 = provide_corrected_code_with_explanation(
            ai_manager.model,
            test_code,
            "Python",
            "Sumar dos números ingresados por el usuario"
        )
        
        print(f"\nCambios realizados: {len(result2['changes_made'])}")
        print(f"Puntos de aprendizaje: {len(result2['learning_points'])}")
        
        if result2['changes_made']:
            print("\n🔄 Cambios:")
            for change in result2['changes_made']:
                print(f"\n  Cambio #{change['change_number']}:")
                print(f"    Concepto: {change['concept']}")
        
        print("\n✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        
    else:
        print("❌ No se pudo inicializar el modelo de IA")
        print("Verifica la API key en la configuración")
        
except Exception as e:
    print(f"\n❌ Error durante las pruebas: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
