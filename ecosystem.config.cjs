/**
 * AI24X — PM2 process manager config (Linux server recommended).
 *
 * Port convention (server):
 * - a.ai24x.com backend (p/a): 8001
 * - api.ai24x.com backend (api/): 8002
 *
 * Notes
 * - Static sites should be served by Nginx directly (no PM2 needed).
 * - Each app can keep its own `.env` file in its cwd.
 */
module.exports = {
  apps: [
    {
      name: "a-api-8001",
      cwd: "./p/a/api/server",
      script: "python3",
      args: "-m uvicorn app.main:app --host 127.0.0.1 --port 8001",
      autorestart: true,
      max_memory_restart: "600M",
      env: {
        PYTHONUNBUFFERED: "1",
        // AI24X_ENV: "prod",
      },
      out_file: "./logs/pm2-out.log",
      error_file: "./logs/pm2-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    {
      name: "core-api-8002",
      cwd: "./api",
      script: "python3",
      args: "-m uvicorn main:app --host 127.0.0.1 --port 8002",
      autorestart: true,
      max_memory_restart: "900M",
      env: {
        PYTHONUNBUFFERED: "1",
        // AI24X_ENV: "prod",
        // SKIP_DB_INIT: "false",
      },
      out_file: "./logs/pm2-out.log",
      error_file: "./logs/pm2-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
  ],
};

