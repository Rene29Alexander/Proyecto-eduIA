import sqlite3, json
conn = sqlite3.connect('learning_platform.db')
conn.row_factory = sqlite3.Row

attempts = conn.execute('SELECT id, exam_id, student_id, details_json, score FROM exam_attempts LIMIT 3').fetchall()
for a in attempts:
    print(f'Attempt id={a["id"]} exam={a["exam_id"]} student={a["student_id"]} score={a["score"]}')
    if a['details_json']:
        d = json.loads(a['details_json'])
        if d:
            print('  Keys:', list(d[0].keys()))
            print('  Sample:', json.dumps(d[0], indent=2, ensure_ascii=False)[:500])

print()
try:
    questions = conn.execute('SELECT id, exam_id, question, question_type, options_json, correct_answer, points FROM exam_questions LIMIT 3').fetchall()
    for q in questions:
        print(f'Q id={q["id"]} exam={q["exam_id"]} type={q["question_type"]} pts={q["points"]}')
        print(f'  Q: {str(q["question"])[:80]}')
        print(f'  correct: {str(q["correct_answer"])[:80]}')
        print(f'  options: {str(q["options_json"])[:80]}')
except Exception as e:
    print('exam_questions error:', e)

conn.close()
