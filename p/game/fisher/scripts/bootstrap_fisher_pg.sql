-- 山海渔 Fisher API：本机一次建库/建用户（按 psql 实际路径以管理员执行）
-- 口令需与 p/game/fisher/api/server/.env 中 FISHER_DATABASE_URL 一致

CREATE USER fisher WITH PASSWORD 'fisher';
CREATE DATABASE fisher OWNER fisher;
