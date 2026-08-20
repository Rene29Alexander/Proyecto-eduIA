import re, psycopg2
from pathlib import Path
s = (Path(__file__).parent.parent / '.streamlit' / 'secrets.toml').read_text(encoding='utf-8')
url = re.search(r'DATABASE_URL\s*=\s*["\']([^"\']+)["\']', s).group(1)
pg = psycopg2.connect(url)
pg.autocommit = True
cur = pg.cursor()
for t in ['module_ai_chat_conversations', 'module_ai_group_chat']:
    cur.execute(f'DELETE FROM "{t}"')
    print(f'  ✅ {t}')
pg.close()
print('Listo')
