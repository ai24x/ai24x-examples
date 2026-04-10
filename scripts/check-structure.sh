#!/bin/bash

# AI24X Token平台目录结构检查脚本
# 用于确保所有副脑都使用标准化的目录结构

echo "🔍 检查AI24X Token平台目录结构..."
echo "========================================"

# 检查顶层目录
REQUIRED_DIRS=("api" "web" "db" "config" "scripts" "docs")
MISSING_DIRS=()

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        MISSING_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DIRS[@]} -eq 0 ]; then
    echo "✅ 所有必需目录都存在"
else
    echo "❌ 缺少以下目录: ${MISSING_DIRS[*]}"
    echo "   请执行: mkdir -p ${MISSING_DIRS[*]}"
fi

# 检查是否有非法顶层目录
echo ""
echo "📁 检查非法顶层目录..."
ILLEGAL_DIRS=()
for dir in */; do
    dir=${dir%/}
    if [[ ! " ${REQUIRED_DIRS[@]} " =~ " ${dir} " ]]; then
        if [[ "$dir" != "." && "$dir" != ".." ]]; then
            ILLEGAL_DIRS+=("$dir")
        fi
    fi
done

if [ ${#ILLEGAL_DIRS[@]} -eq 0 ]; then
    echo "✅ 没有非法顶层目录"
else
    echo "⚠️  发现非法顶层目录: ${ILLEGAL_DIRS[*]}"
    echo "   请将文件移动到标准目录中"
fi

# 检查git状态
echo ""
echo "📊 检查git状态..."
if git status --porcelain | grep -q "^"; then
    echo "⚠️  有未提交的更改"
    echo "   请执行: git add . && git commit -m '更新' && git push"
else
    echo "✅ 所有更改已提交"
fi

# 检查远程同步
echo ""
echo "🔄 检查远程同步..."
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/master 2>/dev/null || echo "")

if [ -z "$REMOTE_COMMIT" ]; then
    echo "❌ 无法获取远程提交信息"
    echo "   请检查网络连接和远程仓库配置"
elif [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo "✅ 本地和远程代码已同步"
else
    echo "⚠️  本地和远程代码不同步"
    echo "   请执行: git pull && git push"
fi

# 总结
echo ""
echo "========================================"
echo "📋 检查完成"

if [ ${#MISSING_DIRS[@]} -eq 0 ] && [ ${#ILLEGAL_DIRS[@]} -eq 0 ]; then
    echo "🎉 目录结构完全符合标准！"
else
    echo "🔧 需要修复的问题:"
    [ ${#MISSING_DIRS[@]} -gt 0 ] && echo "   - 创建缺失目录: ${MISSING_DIRS[*]}"
    [ ${#ILLEGAL_DIRS[@]} -gt 0 ] && echo "   - 处理非法目录: ${ILLEGAL_DIRS[*]}"
fi

echo ""
echo "💡 标准目录结构:"
echo "   api/     后端接口"
echo "   web/     前端页面"
echo "   db/      数据库"
echo "   config/  配置"
echo "   scripts/ 脚本"
echo "   docs/    文档"