# AI24X Token聚合平台 - 标准化目录结构

## 📁 目录结构（永久固定）

```
ai24x01/  (本地目录) = token-platform/ (Gitee线上目录)
├── api/     后端接口代码
├── web/     前端页面代码
├── db/      数据库SQL文件
├── config/  配置文件
├── scripts/ 部署脚本
└── docs/    项目文档
```

## 🚨 重要规则

1. **结构必须一致**：不许自建顶层目录，不许乱改结构
2. **操作流程**：
   ```bash
   git pull → 开发 → git add → commit → push
   ```
3. **本地目录**：ai24x01
4. **线上目录**：token-platform

## 🔄 标准操作流程

### 1. 首次克隆（只做1次）
```bash
git clone https://gitee.com/ai24x/ai24x-website.git ai24x01
cd ai24x01
```

### 2. 每次开发前（防冲突）
```bash
cd ai24x01
git pull
```

### 3. 开发完成后上传
```bash
cd ai24x01
git add .
git commit -m "更新token-platform"
git push
```

## 📌 固定配置
- **Gitee仓库**: https://gitee.com/ai24x/ai24x-website.git
- **访问令牌**: 8d6d649284a6ee802f3360388053fa0b
- **本地目录**: ai24x01
- **线上目录**: token-platform

---

**@all 副脑注意**：必须严格执行此目录结构和操作流程！