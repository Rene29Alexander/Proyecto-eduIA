-- ============================================================
-- SQL para ejecutar en: Supabase Dashboard → SQL Editor
-- ============================================================

-- 1. Eliminar constraints CHECK de 'role' en tablas de chat
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT conname, conrelid::regclass::text AS tname
        FROM pg_constraint
        WHERE conrelid IN (
            'module_ai_group_chat'::regclass,
            'module_ai_chat_conversations'::regclass,
            'ai_course_chat'::regclass
        ) AND contype = 'c'
    LOOP
        EXECUTE format('ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I', r.tname, r.conname);
        RAISE NOTICE 'Eliminada constraint % de %', r.conname, r.tname;
    END LOOP;
END;
$$;

-- 2. Hacer nullable las columnas problemáticas
ALTER TABLE module_ai_group_chat         ALTER COLUMN role    DROP NOT NULL;
ALTER TABLE module_ai_group_chat         ALTER COLUMN content DROP NOT NULL;
ALTER TABLE module_ai_chat_conversations ALTER COLUMN role    DROP NOT NULL;
ALTER TABLE module_ai_chat_conversations ALTER COLUMN content DROP NOT NULL;
ALTER TABLE module_ai_chat_conversations ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE ai_course_chat               ALTER COLUMN role    DROP NOT NULL;
ALTER TABLE ai_course_chat               ALTER COLUMN content DROP NOT NULL;

-- 3. Agregar DEFAULT a 'role'
ALTER TABLE module_ai_group_chat         ALTER COLUMN role SET DEFAULT 'user';
ALTER TABLE module_ai_chat_conversations ALTER COLUMN role SET DEFAULT 'user';

-- 4. Actualizar NULLs existentes
UPDATE module_ai_group_chat         SET role = 'user' WHERE role IS NULL;
UPDATE module_ai_group_chat         SET content = '' WHERE content IS NULL;
UPDATE module_ai_chat_conversations SET role = 'user' WHERE role IS NULL;
UPDATE module_ai_chat_conversations SET content = '' WHERE content IS NULL;

SELECT 'OK - constraints eliminadas y columnas actualizadas' AS resultado;
