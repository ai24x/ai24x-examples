/**
 * AI24X — PM2 local dev config (Windows-friendly).
 *
 * Local port convention:
 * - AI股秘书静态（p/a/web）: 18001
 * - 山海渔 Fisher 网页联调（p/game/fisher/web）: 18002
 * - AI股秘书 API（p/a/api/server）: 18031
 * - 山海渔 Fisher API（p/game/fisher/api/server）: 18041
 *
 * Notes:
 * - This file is for local development; production uses `ecosystem.config.cjs`.
 * - On Windows, `python` should resolve to your installed Python.
 */
module.exports = {
  apps: [
    {
      name: "core-8000",
      cwd: "./api",
      script: "C:\\Users\\Admin\\AppData\\Local\\Programs\\Python\\Python314\\python.exe",
      windowsHide: true,
      // Run uvicorn directly (no reload) to avoid WatchFiles/WinError issues.
      args: "-m uvicorn main:app --host 127.0.0.1 --port 8000",
      autorestart: true,
      max_memory_restart: "900M",
      env: {
        PYTHONUNBUFFERED: "1",
        // Standardized: PostgreSQL only. Use `api/.env` for DATABASE_URL.
        SKIP_DB_INIT: "0",
        API_WORKERS: "1",
        AI24X_ENV: "dev",
      },
      out_file: "./logs/pm2-core-out.log",
      error_file: "./logs/pm2-core-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    // a1 (current) — static + api
    {
      name: "a1-web-18001",
      cwd: "./p/a1/web",
      script: "python",
      windowsHide: true,
      args: "-m http.server 18001 --bind 127.0.0.1",
      autorestart: true,
      max_memory_restart: "200M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      out_file: "./logs/pm2-a1-web-out.log",
      error_file: "./logs/pm2-a1-web-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    {
      name: "a1-api-18011",
      cwd: "./p/a1/api/server",
      script: "C:\\Users\\Admin\\AppData\\Local\\Programs\\Python\\Python314\\python.exe",
      windowsHide: true,
      args: "-m uvicorn app.main:app --host 127.0.0.1 --port 18011",
      autorestart: true,
      max_memory_restart: "650M",
      env: {
        PYTHONUNBUFFERED: "1",
        AI24X_ENV: "dev",
      },
      out_file: "./logs/pm2-a1-api-out.log",
      error_file: "./logs/pm2-a1-api-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    {
      name: "fisher-web-18002",
      cwd: "./p/game/fisher/web",
      script: "python",
      windowsHide: true,
      args: "-m http.server 18002",
      autorestart: true,
      max_memory_restart: "120M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      out_file: "./logs/pm2-fisher-web-out.log",
      error_file: "./logs/pm2-fisher-web-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    {
      name: "fisher-api-18041",
      cwd: "./p/game/fisher/api/server",
      script: "python",
      windowsHide: true,
      args: "-m uvicorn app.main:app --host 127.0.0.1 --port 18041",
      autorestart: true,
      max_memory_restart: "400M",
      env: {
        PYTHONUNBUFFERED: "1",
        FISHER_ENV: "dev",
        FISHER_DATABASE_URL:
          "postgresql+psycopg2://ai24x_a:Ai24x%402026@127.0.0.1:5432/ai24x_a_pre",
      },
      out_file: "./logs/pm2-fisher-api-out.log",
      error_file: "./logs/pm2-fisher-api-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
  ],
};

