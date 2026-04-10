// AI24X Gitee Webhook处理器
// 版本: 1.0.0
// 作者: 副脑01 (首席开发工程师)
// 日期: 2026-03-18

const express = require('express');
const crypto = require('crypto');
const { exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

// 配置
const config = {
  port: process.env.GITEE_WEBHOOK_PORT || 8080,
  secret: process.env.GITEE_WEBHOOK_SECRET || 'ai24x_webhook_secret_2026',
  projectPath: process.env.PROJECT_PATH || process.cwd(),
  logDir: path.join(process.cwd(), 'logs', 'webhook'),
  maxDeployTime: 300000, // 5分钟超时
  allowedBranches: ['develop', 'main', 'release/*'],
  environmentMap: {
    'develop': 'preprod',
    'main': 'production',
    'release/': 'staging'
  }
};

// 创建Express应用
const app = express();
app.use(express.json());

// 中间件：验证Webhook签名
function verifySignature(req, res, next) {
  const signature = req.headers['x-gitee-token'];
  const payload = JSON.stringify(req.body);
  
  if (!signature) {
    return res.status(401).json({ error: 'Missing signature' });
  }
  
  const hmac = crypto.createHmac('sha256', config.secret);
  const computedSignature = hmac.update(payload).digest('hex');
  
  if (signature !== computedSignature) {
    console.warn('Invalid signature received');
    return res.status(403).json({ error: 'Invalid signature' });
  }
  
  next();
}

// 中间件：记录日志
async function logRequest(req, res, next) {
  const logEntry = {
    timestamp: new Date().toISOString(),
    method: req.method,
    url: req.url,
    headers: req.headers,
    body: req.body,
    ip: req.ip
  };
  
  // 确保日志目录存在
  await fs.mkdir(config.logDir, { recursive: true });
  
  const logFile = path.join(config.logDir, `webhook-${new Date().toISOString().split('T')[0]}.log`);
  await fs.appendFile(logFile, JSON.stringify(logEntry, null, 2) + '\n---\n');
  
  next();
}

// 工具函数：获取分支名称
function getBranchName(ref) {
  if (!ref) return null;
  return ref.replace('refs/heads/', '');
}

// 工具函数：确定部署环境
function getEnvironment(branch) {
  for (const [branchPattern, env] of Object.entries(config.environmentMap)) {
    if (branch === branchPattern || branch.startsWith(branchPattern)) {
      return env;
    }
  }
  return 'preprod'; // 默认环境
}

// 工具函数：执行部署命令
function executeDeployment(environment, branch) {
  return new Promise((resolve, reject) => {
    const deployScript = path.join(config.projectPath, 'deploy-config', 'deploy.ps1');
    const command = `powershell -ExecutionPolicy Bypass -File "${deployScript}" -Environment ${environment} -Branch ${branch}`;
    
    console.log(`执行部署命令: ${command}`);
    
    const child = exec(command, {
      cwd: config.projectPath,
      timeout: config.maxDeployTime,
      maxBuffer: 10 * 1024 * 1024 // 10MB
    });
    
    let output = '';
    let errorOutput = '';
    
    child.stdout.on('data', (data) => {
      output += data;
      console.log(`部署输出: ${data}`);
    });
    
    child.stderr.on('data', (data) => {
      errorOutput += data;
      console.error(`部署错误: ${data}`);
    });
    
    child.on('close', (code) => {
      const result = {
        exitCode: code,
        output: output,
        error: errorOutput,
        success: code === 0
      };
      
      if (code === 0) {
        console.log(`部署成功完成，退出码: ${code}`);
        resolve(result);
      } else {
        console.error(`部署失败，退出码: ${code}`);
        reject(new Error(`部署失败: ${errorOutput}`));
      }
    });
    
    child.on('error', (error) => {
      console.error(`部署进程错误: ${error.message}`);
      reject(error);
    });
  });
}

// 工具函数：发送飞书通知
async function sendFeishuNotification(event, branch, environment, success, message) {
  const webhookUrl = process.env.FEISHU_WEBHOOK_URL;
  
  if (!webhookUrl) {
    console.log('飞书Webhook URL未配置，跳过通知');
    return;
  }
  
  const title = success ? '✅ 部署成功' : '❌ 部署失败';
  const color = success ? 'green' : 'red';
  
  const payload = {
    msg_type: 'interactive',
    card: {
      config: {
        wide_screen_mode: true
      },
      header: {
        title: {
          tag: 'plain_text',
          content: title
        },
        template: color
      },
      elements: [
        {
          tag: 'div',
          text: {
            tag: 'lark_md',
            content: `**事件类型**: ${event}\n**分支**: ${branch}\n**环境**: ${environment}\n**时间**: ${new Date().toLocaleString('zh-CN')}`
          }
        },
        {
          tag: 'div',
          text: {
            tag: 'lark_md',
            content: `**详细信息**:\n${message.substring(0, 500)}${message.length > 500 ? '...' : ''}`
          }
        },
        {
          tag: 'action',
          actions: [
            {
              tag: 'button',
              text: {
                tag: 'plain_text',
                content: '查看部署日志'
              },
              type: 'primary',
              url: `${process.env.DEPLOY_DASHBOARD_URL || '#'}`
            },
            {
              tag: 'button',
              text: {
                tag: 'plain_text',
                content: '访问网站'
              },
              type: 'default',
              url: `http://${environment === 'production' ? 'ai24x.com' : 'preprod.ai24x.com'}`
            }
          ]
        }
      ]
    }
  };
  
  try {
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      console.error(`飞书通知发送失败: ${response.status} ${response.statusText}`);
    } else {
      console.log('飞书通知发送成功');
    }
  } catch (error) {
    console.error(`飞书通知发送错误: ${error.message}`);
  }
}

// Webhook处理：Push事件
async function handlePushEvent(payload) {
  const { ref, commits, repository, pusher } = payload;
  const branch = getBranchName(ref);
  
  console.log(`收到Push事件 - 仓库: ${repository.full_name}, 分支: ${branch}, 提交数: ${commits.length}`);
  
  // 检查是否允许的分支
  const isAllowed = config.allowedBranches.some(allowed => 
    branch === allowed || (allowed.endsWith('/*') && branch.startsWith(allowed.slice(0, -2)))
  );
  
  if (!isAllowed) {
    console.log(`分支 ${branch} 不在允许列表中，跳过部署`);
    return {
      success: false,
      message: `分支 ${branch} 不允许自动部署`,
      skipped: true
    };
  }
  
  // 确定部署环境
  const environment = getEnvironment(branch);
  console.log(`确定部署环境: ${environment} (分支: ${branch})`);
  
  try {
    // 执行部署
    const deployResult = await executeDeployment(environment, branch);
    
    // 发送通知
    const message = `部署完成\n环境: ${environment}\n分支: ${branch}\n提交: ${commits.length}个\n最新提交: ${commits[0]?.message || 'N/A'}`;
    await sendFeishuNotification('push', branch, environment, true, message);
    
    return {
      success: true,
      environment,
      branch,
      commits: commits.length,
      output: deployResult.output,
      message: '部署成功完成'
    };
  } catch (error) {
    // 发送失败通知
    const errorMessage = `部署失败\n环境: ${environment}\n分支: ${branch}\n错误: ${error.message}`;
    await sendFeishuNotification('push', branch, environment, false, errorMessage);
    
    return {
      success: false,
      environment,
      branch,
      error: error.message,
      message: '部署失败'
    };
  }
}

// Webhook处理：Merge Request事件
async function handleMergeRequestEvent(payload) {
  const { action, object_attributes, project, user } = payload;
  const { source_branch, target_branch, state, title } = object_attributes;
  
  console.log(`收到Merge Request事件 - 动作: ${action}, 源分支: ${source_branch}, 目标分支: ${target_branch}`);
  
  // 只处理合并完成的事件
  if (action !== 'merge' && state !== 'merged') {
    return {
      success: false,
      message: `Merge Request未合并，跳过部署 (动作: ${action}, 状态: ${state})`,
      skipped: true
    };
  }
  
  // 如果合并到main分支，触发生产环境部署
  if (target_branch === 'main') {
    console.log(`Merge Request合并到main分支，触发生产环境部署`);
    return await handlePushEvent({
      ref: 'refs/heads/main',
      commits: [{ message: `Merge: ${title}` }],
      repository: project,
      pusher: user
    });
  }
  
  return {
    success: false,
    message: `Merge Request目标分支 ${target_branch} 不触发自动部署`,
    skipped: true
  };
}

// Webhook处理：Tag事件
async function handleTagEvent(payload) {
  const { ref, commits, repository } = payload;
  const tagName = ref.replace('refs/tags/', '');
  
  console.log(`收到Tag事件 - 标签: ${tagName}, 仓库: ${repository.full_name}`);
  
  // 检查是否为版本标签 (v1.0.0格式)
  const versionPattern = /^v\d+\.\d+\.\d+$/;
  if (!versionPattern.test(tagName)) {
    return {
      success: false,
      message: `标签 ${tagName} 不是版本标签，跳过部署`,
      skipped: true
    };
  }
  
  // 版本标签触发生产环境部署
  console.log(`版本标签 ${tagName} 触发生产环境部署`);
  return await handlePushEvent({
    ref: 'refs/heads/main',
    commits: [{ message: `Release: ${tagName}` }],
    repository,
    pusher: { name: 'Release Bot' }
  });
}

// Webhook路由
app.post('/webhook/gitee', logRequest, verifySignature, async (req, res) => {
  const eventType = req.headers['x-gitee-event'];
  const payload = req.body;
  
  console.log(`收到Webhook事件: ${eventType}`);
  
  let result;
  
  try {
    switch (eventType) {
      case 'Push Hook':
        result = await handlePushEvent(payload);
        break;
      
      case 'Merge Request Hook':
        result = await handleMergeRequestEvent(payload);
        break;
      
      case 'Tag Push Hook':
        result = await handleTagEvent(payload);
        break;
      
      default:
        result = {
          success: false,
          message: `不支持的事件类型: ${eventType}`,
          skipped: true
        };
    }
    
    res.status(200).json({
      success: true,
      event: eventType,
      handled: !result.skipped,
      result: result
    });
    
  } catch (error) {
    console.error(`Webhook处理错误: ${error.message}`);
    res.status(500).json({
      success: false,
      error: error.message,
      event: eventType
    });
  }
});

// 健康检查端点
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    service: 'gitee-webhook-handler',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage()
  });
});

// 状态端点
app.get('/status', (req, res) => {
  res.status(200).json({
    service: 'Gitee Webhook Handler',
    version: '1.0.0',
    environment: process.env.NODE_ENV || 'development',
    config: {
      port: config.port,
      projectPath: config.projectPath,
      allowedBranches: config.allowedBranches
    },
    stats: {
      startTime: new Date(Date.now() - process.uptime() * 1000).toISOString(),
      uptime: process.uptime()
    }
  });
});

// 错误处理
app.use((err, req, res, next) => {
  console.error(`服务器错误: ${err.message}`);
  console.error(err.stack);
  
  res.status(500).json({
    error: 'Internal Server Error',
    message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
  });
});

// 404处理
app.use((req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `路径 ${req.path} 不存在`
  });
});

// 启动服务器
const server = app.listen(config.port, () => {
  console.log(`========================================`);
  console.log(`   AI24X Gitee Webhook处理器 v1.0.0    `);
  console.log(`========================================`);
  console.log(`服务启动时间: ${new Date().toLocaleString('zh-CN')}`);
  console.log(`监听端口: ${config.port}`);
  console.log(`项目路径: ${config.projectPath}`);
  console.log(`允许的分支: ${config.allowedBranches.join(', ')}`);
  console.log(`环境映射: ${JSON.stringify(config.environmentMap)}`);
  console.log(`========================================`);
  console.log(`健康检查: http://localhost:${config.port}/health`);
  console.log(`状态查询: http://localhost:${config.port}/status`);
  console.log(`Webhook端点: http://localhost:${config.port}/webhook/gitee`);
  console.log(`========================================`);
});

// 优雅关闭
process.on('SIGTERM', () => {
  console.log('收到SIGTERM信号，开始优雅关闭...');
  server.close(() => {
    console.log('HTTP服务器已关闭');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('收到SIGINT信号，开始优雅关闭...');
  server.close(() => {
    console.log('HTTP服务器已关闭');
    process.exit(0);
  });
});

// 未捕获异常处理
process.on('uncaughtException', (error) => {
  console.error('未捕获异常:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('未处理的Promise拒绝:', reason);
});

module.exports = {
  app,
  config,
  handlePushEvent,
  handleMergeRequestEvent,
  handleTagEvent
};