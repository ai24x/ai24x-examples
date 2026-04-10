/**
 * AI24X支付系统API
 * 版本: 1.0
 * 创建时间: 2026-03-18
 * 负责人: 副脑01（首席开发工程师）
 */

const fs = require('fs');
const path = require('path');

// 支付系统配置
const PAYMENT_CONFIG = {
  LAUNCH_DATE: '2026-03-25', // 支付功能上线日期
  CURRENCY: 'CNY',
  TAX_RATE: 0.06, // 6%税率
  DATA_DIR: path.join(__dirname, '..', 'data'),
  SCHEMA_FILE: 'payment-schema.json',
  PLANS_FILE: 'payment-plans.json',
  SUBSCRIPTIONS_FILE: 'user-subscriptions.json',
  TRANSACTIONS_FILE: 'payment-transactions.json'
};

// 初始化支付数据文件
function initPaymentData() {
  const dataDir = PAYMENT_CONFIG.DATA_DIR;
  
  // 确保数据目录存在
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  
  // 读取架构文件
  let schema = {};
  try {
    const schemaPath = path.join(dataDir, PAYMENT_CONFIG.SCHEMA_FILE);
    if (fs.existsSync(schemaPath)) {
      schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
    }
  } catch (error) {
    console.error('读取支付架构文件失败:', error);
  }
  
  // 初始化默认数据文件
  const dataFiles = [
    {
      file: PAYMENT_CONFIG.PLANS_FILE,
      defaultData: schema.default_plans || []
    },
    {
      file: PAYMENT_CONFIG.SUBSCRIPTIONS_FILE,
      defaultData: []
    },
    {
      file: PAYMENT_CONFIG.TRANSACTIONS_FILE,
      defaultData: []
    }
  ];
  
  dataFiles.forEach(({ file, defaultData }) => {
    const filePath = path.join(dataDir, file);
    if (!fs.existsSync(filePath)) {
      fs.writeFileSync(filePath, JSON.stringify(defaultData, null, 2), 'utf8');
      console.log(`初始化支付数据文件: ${file}`);
    }
  });
  
  return true;
}

// 读取JSON数据
function readJsonFile(filename) {
  try {
    const filePath = path.join(PAYMENT_CONFIG.DATA_DIR, filename);
    if (!fs.existsSync(filePath)) {
      return [];
    }
    const data = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    console.error(`读取文件 ${filename} 失败:`, error);
    return [];
  }
}

// 写入JSON数据
function writeJsonFile(filename, data) {
  try {
    const filePath = path.join(PAYMENT_CONFIG.DATA_DIR, filename);
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (error) {
    console.error(`写入文件 ${filename} 失败:`, error);
    return false;
  }
}

// 生成唯一ID
function generateId(prefix = '') {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substr(2, 9);
  return `${prefix}${timestamp}${random}`;
}

// 获取当前时间戳
function getCurrentTimestamp() {
  return new Date().toISOString();
}

// 支付系统API类
class PaymentSystem {
  constructor() {
    initPaymentData();
  }
  
  // 获取所有付费套餐
  getAllPlans() {
    return readJsonFile(PAYMENT_CONFIG.PLANS_FILE);
  }
  
  // 获取单个套餐
  getPlanById(planId) {
    const plans = this.getAllPlans();
    return plans.find(plan => plan.id === planId);
  }
  
  // 获取用户订阅
  getUserSubscription(userId) {
    const subscriptions = readJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE);
    return subscriptions.find(sub => 
      sub.user_id === userId && sub.status === 'active'
    );
  }
  
  // 获取用户所有订阅历史
  getUserSubscriptionHistory(userId) {
    const subscriptions = readJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE);
    return subscriptions.filter(sub => sub.user_id === userId);
  }
  
  // 创建用户订阅
  createSubscription(userId, planId, billingCycle = 'monthly') {
    const plan = this.getPlanById(planId);
    if (!plan) {
      throw new Error(`套餐 ${planId} 不存在`);
    }
    
    // 检查用户是否已有活跃订阅
    const existingSubscription = this.getUserSubscription(userId);
    if (existingSubscription) {
      throw new Error('用户已有活跃订阅，请先取消当前订阅');
    }
    
    const now = getCurrentTimestamp();
    const startDate = now;
    
    // 计算结束日期
    let endDate = new Date(now);
    if (billingCycle === 'monthly') {
      endDate.setMonth(endDate.getMonth() + 1);
    } else if (billingCycle === 'yearly') {
      endDate.setFullYear(endDate.getFullYear() + 1);
    }
    
    const subscription = {
      id: generateId('sub_'),
      user_id: userId,
      plan_id: planId,
      billing_cycle: billingCycle,
      status: 'active',
      start_date: startDate,
      end_date: endDate.toISOString(),
      auto_renew: true,
      created_at: now,
      updated_at: now
    };
    
    // 保存订阅
    const subscriptions = readJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE);
    subscriptions.push(subscription);
    writeJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE, subscriptions);
    
    // 创建初始交易记录
    this.createTransaction({
      subscription_id: subscription.id,
      user_id: userId,
      amount: billingCycle === 'monthly' ? plan.price_monthly : plan.price_yearly,
      description: `订阅 ${plan.name} (${billingCycle})`,
      payment_method: 'pending'
    });
    
    return subscription;
  }
  
  // 取消订阅
  cancelSubscription(userId) {
    const subscription = this.getUserSubscription(userId);
    if (!subscription) {
      throw new Error('用户没有活跃订阅');
    }
    
    const subscriptions = readJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE);
    const index = subscriptions.findIndex(sub => sub.id === subscription.id);
    
    if (index !== -1) {
      subscriptions[index].status = 'cancelled';
      subscriptions[index].auto_renew = false;
      subscriptions[index].updated_at = getCurrentTimestamp();
      writeJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE, subscriptions);
      
      return subscriptions[index];
    }
    
    return null;
  }
  
  // 创建交易记录
  createTransaction(transactionData) {
    const now = getCurrentTimestamp();
    
    const transaction = {
      id: generateId('txn_'),
      ...transactionData,
      currency: PAYMENT_CONFIG.CURRENCY,
      status: 'pending',
      created_at: now,
      updated_at: now
    };
    
    const transactions = readJsonFile(PAYMENT_CONFIG.TRANSACTIONS_FILE);
    transactions.push(transaction);
    writeJsonFile(PAYMENT_CONFIG.TRANSACTIONS_FILE, transactions);
    
    return transaction;
  }
  
  // 更新交易状态
  updateTransactionStatus(transactionId, status, transactionIdExternal = null) {
    const transactions = readJsonFile(PAYMENT_CONFIG.TRANSACTIONS_FILE);
    const index = transactions.findIndex(txn => txn.id === transactionId);
    
    if (index !== -1) {
      transactions[index].status = status;
      transactions[index].updated_at = getCurrentTimestamp();
      
      if (transactionIdExternal) {
        transactions[index].transaction_id = transactionIdExternal;
      }
      
      writeJsonFile(PAYMENT_CONFIG.TRANSACTIONS_FILE, transactions);
      
      // 如果交易成功，更新订阅状态
      if (status === 'success') {
        this._updateSubscriptionAfterPayment(transactions[index]);
      }
      
      return transactions[index];
    }
    
    return null;
  }
  
  // 支付成功后更新订阅
  _updateSubscriptionAfterPayment(transaction) {
    const subscriptions = readJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE);
    const subscriptionIndex = subscriptions.findIndex(
      sub => sub.id === transaction.subscription_id
    );
    
    if (subscriptionIndex !== -1) {
      subscriptions[subscriptionIndex].last_payment_date = transaction.created_at;
      
      // 计算下次支付日期
      const nextPaymentDate = new Date(transaction.created_at);
      if (subscriptions[subscriptionIndex].billing_cycle === 'monthly') {
        nextPaymentDate.setMonth(nextPaymentDate.getMonth() + 1);
      } else {
        nextPaymentDate.setFullYear(nextPaymentDate.getFullYear() + 1);
      }
      
      subscriptions[subscriptionIndex].next_payment_date = nextPaymentDate.toISOString();
      subscriptions[subscriptionIndex].updated_at = getCurrentTimestamp();
      
      writeJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE, subscriptions);
    }
  }
  
  // 获取用户交易历史
  getUserTransactions(userId) {
    const transactions = readJsonFile(PAYMENT_CONFIG.TRANSACTIONS_FILE);
    return transactions.filter(txn => txn.user_id === userId);
  }
  
  // 检查用户权限
  checkUserPermission(userId, requiredPermission) {
    const subscription = this.getUserSubscription(userId);
    if (!subscription) {
      return false;
    }
    
    const plan = this.getPlanById(subscription.plan_id);
    if (!plan) {
      return false;
    }
    
    // 根据套餐检查权限
    switch (requiredPermission) {
      case 'create_agent':
        return subscription.status === 'active';
      case 'api_access':
        return plan.id !== 'free';
      case 'priority_support':
        return plan.priority_support === true;
      case 'custom_workflow':
        return plan.id === 'pro' || plan.id === 'business' || plan.id === 'enterprise';
      default:
        return subscription.status === 'active';
    }
  }
  
  // 获取系统统计
  getSystemStats() {
    const subscriptions = readJsonFile(PAYMENT_CONFIG.SUBSCRIPTIONS_FILE);
    const transactions = readJsonFile(PAYMENT_CONFIG.TRANSACTIONS_FILE);
    
    const activeSubscriptions = subscriptions.filter(sub => sub.status === 'active');
    const successfulTransactions = transactions.filter(txn => txn.status === 'success');
    
    const totalRevenue = successfulTransactions.reduce((sum, txn) => sum + txn.amount, 0);
    
    return {
      total_users: new Set(subscriptions.map(sub => sub.user_id)).size,
      active_subscriptions: activeSubscriptions.length,
      total_transactions: transactions.length,
      successful_transactions: successfulTransactions.length,
      total_revenue: totalRevenue,
      launch_date: PAYMENT_CONFIG.LAUNCH_DATE,
      currency: PAYMENT_CONFIG.CURRENCY
    };
  }
}

// 导出支付系统实例
const paymentSystem = new PaymentSystem();

// Express路由处理
module.exports = function(app) {
  // 初始化支付数据
  app.get('/api/payment/init', (req, res) => {
    try {
      initPaymentData();
      res.json({ success: true, message: '支付系统初始化完成' });
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  // 获取所有套餐
  app.get('/api/payment/plans', (req, res) => {
    try {
      const plans = paymentSystem.getAllPlans();
      res.json({ success: true, data: plans });
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  // 获取用户订阅状态
  app.get('/api/payment/subscription', (req, res) => {
    try {
      const userId = req.query.user_id || req.session?.user_id;
      if (!userId) {
        return res.status(400).json({ success: false, error: '需要用户ID' });
      }
      
      const subscription = paymentSystem.getUserSubscription(userId);
      const plan = subscription ? paymentSystem.getPlanById(subscription.plan_id) : null;
      
      res.json({
        success: true,
        data: {
          has_subscription: !!subscription,
          subscription: subscription,
          plan: plan,
          permissions: {
            can_create_agent: paymentSystem.checkUserPermission(userId, 'create_agent'),
            has_api_access: paymentSystem.checkUserPermission(userId, 'api_access'),
            has_priority_support: paymentSystem.checkUserPermission(userId, 'priority_support'),
            can_use_custom_workflow: paymentSystem.checkUserPermission(userId, 'custom_workflow')
          }
        }
      });
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  // 创建订阅（模拟）
  app.post('/api/payment/subscribe', (req, res) => {
    try {
      const { user_id, plan_id, billing_cycle } = req.body;
      
      if (!user_id || !plan_id) {
        return res.status(400).json({ success: false, error: '缺少必要参数' });
      }
      
      const subscription = paymentSystem.createSubscription(user_id, plan_id, billing_cycle);
      
      res.json({
        success: true,
        message: '订阅创建成功（模拟）',
        data: subscription,
        note: '支付功能将于2026年3月25日正式上线，当前为模拟模式'
      });
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  // 取消订阅
  app.post('/api/payment/cancel', (req, res) => {
    try {
      const { user_id } = req.body;
      
      if (!user_id) {
        return res.status(400).json({ success: false, error: '需要用户ID' });
      }
      
      const subscription = paymentSystem.cancelSubscription(user_id);
      
      if (subscription) {
        res.json({ success: true, message: '订阅已取消', data: subscription });
      } else {
        res.status(404).json({ success: false, error: '未找到活跃订阅' });
      }
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  // 检查用户权限
  app.get('/api/payment/permissions', (req, res) => {
    try {
      const userId = req.query.user_id || req.session?.user_id;
      const permission = req.query.permission;
      
      if (!userId) {
        return res.status(400).json({ success: false, error: '需要用户ID' });
      }
      
      if (permission) {
        const hasPermission = paymentSystem.checkUserPermission(userId, permission);
        res.json({ success: true, has_permission: hasPermission });
      } else {
        const permissions = {
          can_create_agent: paymentSystem.checkUserPermission(userId, 'create_agent'),
          has_api_access: paymentSystem.checkUserPermission(userId, 'api_access'),
          has_priority_support: paymentSystem.checkUserPermission(userId, 'priority_support'),
          can_use_custom_workflow: paymentSystem.checkUserPermission(userId, 'custom_workflow')
        };
        res.json({ success: true, permissions: permissions });
      }
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  // 获取系统统计
  app.get('/api/payment/stats', (req, res) => {
    try {
      const stats = paymentSystem.getSystemStats();
      res.json({ success: true, data: stats });
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  // 支付反馈处理
  app.post('/api/feedback', (req, res) => {
    try {
      const { name, email, message, feedback_type } = req.body;
      
      // 保存反馈到文件
      const feedbackDir = path.join(PAYMENT_CONFIG.DATA_DIR, 'feedback');
      if (!fs.existsSync(feedbackDir)) {
        fs.mkdirSync(feedbackDir, { recursive: true });
      }
      
      const feedbackFile = path.join(feedbackDir, 'payment-feedback.json');
      let feedbacks = [];
      
      if (fs.existsSync(feedbackFile)) {
        feedbacks = JSON.parse(fs.readFileSync(feedbackFile, 'utf8'));
      }
      
      const feedback = {
        id: generateId('fb_'),
        name: name || '匿名用户',
        email: email || '',
        message: message || '',
        feedback_type: feedback_type || 'general',
        created_at: getCurrentTimestamp(),
        ip: req.ip
      };
      
      feedbacks.push(feedback);
      fs.writeFileSync(feedbackFile, JSON.stringify(feedbacks, null, 2), 'utf8');
      
      res.json({
        success: true,
        message: '感谢您的反馈！我们已收到并会尽快处理。',
        data: { id: feedback.id }
      });
    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  });
  
  console.log('支付系统API已注册');
};