-- ============================================
-- AI 只读数据库用户创建脚本
--
-- 用途：为 Text-to-SQL 功能创建专用只读用户
-- 这是数据库级别的最后防线 —— 即使代码层所有安全检查都被绕过，
-- 该用户也只有 SELECT 权限，无法执行任何写操作。
--
-- 使用方法：
--   1. 以超级管理员身份连接 PostgreSQL
--   2. 修改下方密码为安全的随机密码
--   3. 执行此脚本
--   4. 将连接字符串配置到 .env 的 AI_READONLY_DB_URL
--
-- 注意：表名列表需与 SchemaProvider.ALLOWED_TENANT_TABLES 保持同步
-- ============================================

-- Step 1: 创建只读用户（请替换密码）
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_readonly') THEN
        CREATE USER ai_readonly WITH PASSWORD 'CHANGE_ME_TO_SECURE_PASSWORD';
    END IF;
END
$$;

-- Step 2: 授予连接权限
GRANT CONNECT ON DATABASE novusai_saas TO ai_readonly;
GRANT USAGE ON SCHEMA public TO ai_readonly;

-- Step 3: 授予业务表 SELECT 权限（白名单）
-- 与 SchemaProvider.ALLOWED_TENANT_TABLES 保持一致
GRANT SELECT ON
    tenant_users,
    tenant_admins,
    agents,
    agent_conversations,
    conversation_messages,
    usage_stats,
    ai_call_logs,
    tool_definitions,
    knowledge_bases,
    knowledge_documents,
    attachments,
    operation_logs,
    tenant_domains
TO ai_readonly;

-- Step 4: 显式撤销系统敏感表权限（防御性措施）
-- 即使未来有人误操作 GRANT ALL，这里也会撤销
REVOKE ALL ON
    admins,
    admin_roles,
    permissions,
    admin_tokens,
    admin_refresh_tokens,
    tenant_admin_roles,
    provider_api_keys,
    system_configs,
    alembic_version
FROM ai_readonly;

-- Step 5: 设置默认权限（未来新建的表默认无权限）
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL ON TABLES FROM ai_readonly;

-- Step 6: 连接级安全限制
-- 限制最大连接数（防止连接池耗尽）
ALTER USER ai_readonly CONNECTION LIMIT 5;

-- Step 7: 设置默认只读事务（双重保险）
ALTER USER ai_readonly SET default_transaction_read_only = ON;

-- Step 8: 设置默认语句超时（防止慢查询 DoS）
ALTER USER ai_readonly SET statement_timeout = '15s';

-- 验证：查看用户权限
-- SELECT grantee, table_name, privilege_type
-- FROM information_schema.table_privileges
-- WHERE grantee = 'ai_readonly';
