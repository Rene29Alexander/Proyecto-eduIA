"""
Script para crear desafíos diarios automáticamente
Ejecutar diariamente para generar nuevos desafíos
"""

from datetime import date, timedelta
from engagement import ChallengeManager
import random

# Desafíos predefinidos por dificultad
CHALLENGES = {
    'easy': [
        {
            'title': 'Suma de Números',
            'description': 'Crea una función que sume todos los números de una lista',
            'exercise_code': 'def sumar_lista(numeros):\n    # Tu código aquí\n    pass',
            'solution_code': 'def sumar_lista(numeros):\n    return sum(numeros)',
        },
        {
            'title': 'Número Par o Impar',
            'description': 'Crea una función que determine si un número es par o impar',
            'exercise_code': 'def es_par(numero):\n    # Tu código aquí\n    pass',
            'solution_code': 'def es_par(numero):\n    return numero % 2 == 0',
        },
        {
            'title': 'Invertir String',
            'description': 'Crea una función que invierta un string',
            'exercise_code': 'def invertir(texto):\n    # Tu código aquí\n    pass',
            'solution_code': 'def invertir(texto):\n    return texto[::-1]',
        },
    ],
    'medium': [
        {
            'title': 'Fibonacci',
            'description': 'Crea una función que genere los primeros n números de Fibonacci',
            'exercise_code': 'def fibonacci(n):\n    # Tu código aquí\n    pass',
            'solution_code': 'def fibonacci(n):\n    if n <= 0: return []\n    if n == 1: return [0]\n    fib = [0, 1]\n    for i in range(2, n):\n        fib.append(fib[i-1] + fib[i-2])\n    return fib',
        },
        {
            'title': 'Palíndromo',
            'description': 'Crea una función que verifique si una palabra es palíndromo',
            'exercise_code': 'def es_palindromo(palabra):\n    # Tu código aquí\n    pass',
            'solution_code': 'def es_palindromo(palabra):\n    palabra = palabra.lower().replace(" ", "")\n    return palabra == palabra[::-1]',
        },
    ],
    'hard': [
        {
            'title': 'Ordenamiento Rápido',
            'description': 'Implementa el algoritmo QuickSort',
            'exercise_code': 'def quicksort(arr):\n    # Tu código aquí\n    pass',
            'solution_code': 'def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)',
        },
    ]
}

def create_challenge_for_date(target_date, language='Python'):
    """Crea un desafío para una fecha específica"""
    
    # Seleccionar dificultad (70% easy, 20% medium, 10% hard)
    rand = random.random()
    if rand < 0.7:
        difficulty = 'easy'
    elif rand < 0.9:
        difficulty = 'medium'
    else:
        difficulty = 'hard'
    
    # Seleccionar desafío aleatorio de esa dificultad
    challenge_template = random.choice(CHALLENGES[difficulty])
    
    # Crear desafío
    challenge_id = ChallengeManager.create_daily_challenge(
        challenge_date=target_date.isoformat(),
        language=language,
        difficulty=difficulty,
        title=challenge_template['title'],
        description=challenge_template['description'],
        exercise_code=challenge_template['exercise_code'],
        solution_code=challenge_template['solution_code'],
        test_cases=None,
        points=50,
        bonus_points=20
    )
    
    if challenge_id:
        print(f"✅ Desafío creado para {target_date}: {challenge_template['title']} ({difficulty})")
        return True
    else:
        print(f"⚠️  Ya existe desafío para {target_date}")
        return False

def create_challenges_for_week():
    """Crea desafíos para los próximos 7 días"""
    print("🎯 Creando desafíos para la próxima semana...\n")
    
    today = date.today()
    created = 0
    
    for i in range(7):
        target_date = today + timedelta(days=i)
        if create_challenge_for_date(target_date):
            created += 1
    
    print(f"\n📊 Resumen: {created} desafíos creados")

if __name__ == "__main__":
    create_challenges_for_week()
