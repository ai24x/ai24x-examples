-- AI24X Token平台 - PostgreSQL数据库表结构
-- 生成时间: 2026-04-10 01:45 GMT+8
-- 副脑04 - 国际节点运维官 (新加坡节点)

-- ====================
-- 1. 用户表 (users)
-- ====================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,          -- 用户名
    email VARCHAR(100) UNIQUE NOT NULL,            -- 邮箱
    password_hash VARCHAR(255) NOT NULL,           -- 密码哈希
    avatar_url TEXT,                               -- 头像URL
    role VARCHAR(20) DEFAULT 'user',              -- 角色: user, admin, super_admin
    status VARCHAR(20) DEFAULT 'active',          -- 状态: active, suspended, deleted
    token_balance DECIMAL(18, 8) DEFAULT 0.0,     -- Token余额
    api_call_count INTEGER DEFAULT 0,             -- API调用次数
    last_login_at TIMESTAMP,                      -- 最后登录时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 更新时间
);

-- ====================
-- 2. API密钥表 (api_keys)
-- ====================
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    api_key VARCHAR(64) UNIQUE NOT NULL,          -- API密钥
    api_secret VARCHAR(128) NOT NULL,             -- API密钥(加密存储)
    name VARCHAR(100) NOT NULL,                   -- 密钥名称
    permissions TEXT[],                           -- 权限列表
    rate_limit INTEGER DEFAULT 1000,              -- 频率限制(次/分钟)
    total_calls INTEGER DEFAULT 0,                -- 总调用次数
    last_used_at TIMESTAMP,                       -- 最后使用时间
    expires_at TIMESTAMP,                         -- 过期时间
    is_active BOOLEAN DEFAULT TRUE,               -- 是否激活
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 3. 聊天会话表 (chat_sessions)
-- ====================
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64) UNIQUE NOT NULL,       -- 会话ID
    title VARCHAR(200) DEFAULT '新会话',         -- 会话标题
    model_name VARCHAR(50),                       -- 使用的模型
    token_used INTEGER DEFAULT 0,                 -- 消耗的Token数量
    message_count INTEGER DEFAULT 0,              -- 消息数量
    last_message_at TIMESTAMP,                    -- 最后消息时间
    is_archived BOOLEAN DEFAULT FALSE,            -- 是否归档
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 4. 聊天消息表 (chat_messages)
-- ====================
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,                    -- 角色: user, assistant, system
    content TEXT NOT NULL,                        -- 消息内容
    model_name VARCHAR(50),                       -- 使用的模型
    input_tokens INTEGER,                         -- 输入Token数
    output_tokens INTEGER,                        -- 输出Token数
    total_tokens INTEGER,                         -- 总Token数
    metadata JSONB,                               -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 5. Token使用记录表 (token_usage)
-- ====================
CREATE TABLE token_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
    model_name VARCHAR(50) NOT NULL,              -- 模型名称
    input_tokens INTEGER DEFAULT 0,               -- 输入Token数
    output_tokens INTEGER DEFAULT 0,              -- 输出Token数
    total_tokens INTEGER DEFAULT 0,               -- 总Token数
    token_cost DECIMAL(18, 8) DEFAULT 0.0,       -- Token成本
    currency VARCHAR(10) DEFAULT 'CNY',          -- 货币类型
    amount DECIMAL(18, 2) DEFAULT 0.0,           -- 金额
    request_id VARCHAR(64) UNIQUE,               -- 请求ID
    endpoint VARCHAR(200),                        -- API端点
    status VARCHAR(20) DEFAULT 'success',        -- 状态: success, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 6. 计费记录表 (billing_records)
-- ====================
CREATE TABLE billing_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    billing_type VARCHAR(20) NOT NULL,            -- 类型: recharge, consumption, refund
    amount DECIMAL(18, 2) NOT NULL,              -- 金额
    currency VARCHAR(10) DEFAULT 'CNY',          -- 货币
    payment_method VARCHAR(50),                  -- 支付方式
    transaction_id VARCHAR(100) UNIQUE,          -- 交易ID
    description TEXT,                            -- 描述
    status VARCHAR(20) DEFAULT 'pending',        -- 状态: pending, completed, failed
    completed_at TIMESTAMP,                      -- 完成时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 7. 模型配置表 (model_configs)
-- ====================
CREATE TABLE model_configs (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(50) UNIQUE NOT NULL,      -- 模型名称
    provider VARCHAR(50) NOT NULL,               -- 提供商: deepseek, openai, etc.
    api_endpoint TEXT,                           -- API端点
    input_price DECIMAL(18, 8) DEFAULT 0.0,     -- 输入Token单价
    output_price DECIMAL(18, 8) DEFAULT 0.0,    -- 输出Token单价
    context_length INTEGER DEFAULT 4096,        -- 上下文长度
    max_tokens INTEGER DEFAULT 2048,            -- 最大输出Token
    is_enabled BOOLEAN DEFAULT TRUE,            -- 是否启用
    rate_limit INTEGER DEFAULT 100,             -- 频率限制
    config JSONB,                               -- 配置参数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 8. 系统配置表 (system_configs)
-- ====================
CREATE TABLE system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,     -- 配置键
    config_value TEXT,                           -- 配置值
    config_type VARCHAR(20) DEFAULT 'string',    -- 类型: string, number, boolean, json
    category VARCHAR(50) DEFAULT 'general',      -- 分类
    description TEXT,                            -- 描述
    is_public BOOLEAN DEFAULT FALSE,             -- 是否公开
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 9. 审计日志表 (audit_logs)
-- ====================
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,                 -- 操作类型
    resource_type VARCHAR(50),                   -- 资源类型
    resource_id VARCHAR(100),                    -- 资源ID
    details JSONB,                               -- 详细信息
    ip_address INET,                             -- IP地址
    user_agent TEXT,                             -- 用户代理
    status VARCHAR(20) DEFAULT 'success',        -- 状态: success, failed
    error_message TEXT,                          -- 错误信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 10. 文件存储表 (files)
-- ====================
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,             -- 文件名
    file_path TEXT NOT NULL,                     -- 文件路径
    file_size BIGINT,                            -- 文件大小(字节)
    mime_type VARCHAR(100),                      -- MIME类型
    storage_type VARCHAR(20) DEFAULT 'local',    -- 存储类型: local, s3, cos
    storage_url TEXT,                            -- 存储URL
    is_public BOOLEAN DEFAULT FALSE,             -- 是否公开
    access_count INTEGER DEFAULT 0,              -- 访问次数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- 索引优化
-- ====================
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_api_key ON api_keys(api_key);
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX idx_token_usage_user_id ON token_usage(user_id);
CREATE INDEX idx_token_usage_created_at ON token_usage(created_at);
CREATE INDEX idx_billing_records_user_id ON billing_records(user_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- ====================
-- 初始化数据
-- ====================
-- 插入默认模型配置
INSERT INTO model_configs (model_name, provider, input_price, output_price, context_length, max_tokens, is_enabled) VALUES
('deepseek-chat', 'deepseek', 0.000002, 0.000008, 16384, 4096, TRUE),
('deepseek-reasoner', 'deepseek', 0.000008, 0.000032, 32768, 8192, TRUE),
('gpt-4o', 'openai', 0.000015, 0.000060, 128000, 4096, TRUE),
('claude-3-haiku', 'anthropic', 0.000003, 0.000015, 200000, 4096, TRUE);

-- 插入系统配置
INSERT INTO system_configs (config_key, config_value, config_type, category, description) VALUES
('platform_name', 'AI24X Token平台', 'string', 'general', '平台名称'),
('currency', 'CNY', 'string', 'billing', '默认货币'),
('token_price', '0.01', 'number', 'billing', 'Token单价(CNY)'),
('rate_limit_per_user', '1000', 'number', 'security', '用户频率限制'),
('maintenance_mode', 'false', 'boolean', 'system', '维护模式');

-- ====================
-- 表结构创建完成
-- ====================