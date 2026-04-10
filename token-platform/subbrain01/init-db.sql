-- AI24X 副脑01 数据库初始化脚本

-- 创建扩展（如果需要）
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建测试用户
INSERT INTO users (user_id, user_type, api_key, daily_request_limit, monthly_request_limit, is_active)
VALUES 
    ('test_user_001', 'free', 'sk_test_free_001', 100, 3000, true),
    ('test_user_002', 'vip', 'sk_test_vip_001', 1000, 30000, true),
    ('admin_user', 'vip', 'sk_admin_001', 5000, 150000, true)
ON CONFLICT (user_id) DO NOTHING;

-- 创建示例请求记录
INSERT INTO chat_requests (
    request_id, user_id, user_type, prompt, model, response, 
    status, is_success, token_count, cost, processing_duration
)
VALUES 
    (
        'req_sample_001', 
        'test_user_001', 
        'free', 
        '如何学习Python编程？', 
        'gpt-3.5-turbo',
        '学习Python编程可以从基础语法开始，然后逐步学习数据结构、面向对象编程等。建议使用官方文档和在线教程。',
        'completed',
        true,
        45,
        0.00009,
        1.2
    ),
    (
        'req_sample_002', 
        'test_user_002', 
        'vip', 
        'FastAPI的最佳实践是什么？', 
        'gpt-4',
        'FastAPI的最佳实践包括：使用Pydantic进行数据验证、依赖注入管理、异步处理、合理的错误处理、API版本控制等。',
        'completed',
        true,
        68,
        0.000136,
        1.8
    )
ON CONFLICT (request_id) DO NOTHING;

-- 创建速率限制记录
INSERT INTO rate_limits (user_id, window_type, request_count, window_start, window_end)
VALUES 
    ('test_user_001', 'daily', 15, CURRENT_DATE, CURRENT_DATE + INTERVAL '1 day'),
    ('test_user_001', 'monthly', 150, DATE_TRUNC('month', CURRENT_DATE), DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'),
    ('test_user_002', 'daily', 120, CURRENT_DATE, CURRENT_DATE + INTERVAL '1 day'),
    ('test_user_002', 'monthly', 1200, DATE_TRUNC('month', CURRENT_DATE), DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')
ON CONFLICT DO NOTHING;