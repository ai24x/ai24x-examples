#!/usr/bin/env node

/**
 * Gitee推送验证脚本
 * 验证代码是否成功推送到Gitee
 */

const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

async function verifyGiteePush() {
    console.log('🔍 开始验证Gitee推送状态...\n');
    
    // 检查本地提交
    console.log('1. 检查本地提交历史...');
    try {
        const { stdout: localLog } = await execAsync('git log --oneline -5');
        console.log('   最近5次本地提交:');
        console.log('   ' + localLog.replace(/\n/g, '\n   '));
    } catch (error) {
        console.log(`   ❌ 本地提交检查失败: ${error.message}`);
    }
    
    // 检查远程连接
    console.log('\n2. 检查远程仓库连接...');
    try {
        const { stdout: remoteUrl } = await execAsync('git remote get-url origin');
        console.log(`   ✅ 远程仓库URL: ${remoteUrl.trim()}`);
    } catch (error) {
        console.log(`   ❌ 远程仓库检查失败: ${error.message}`);
    }
    
    // 检查推送状态
    console.log('\n3. 检查推送状态...');
    try {
        const { stdout: status } = await execAsync('git status -sb');
        console.log('   当前状态:');
        console.log('   ' + status.replace(/\n/g, '\n   '));
    } catch (error) {
        console.log(`   ❌ 状态检查失败: ${error.message}`);
    }
    
    // 尝试获取远程分支信息
    console.log('\n4. 验证远程仓库可访问性...');
    try {
        console.log('   ⏳ 尝试获取远程分支信息...');
        const { stdout: remoteBranches } = await execAsync('git ls-remote --heads origin', { timeout: 10000 });
        
        if (remoteBranches.trim()) {
            console.log('   ✅ 远程仓库可访问！');
            const branches = remoteBranches.split('\n').filter(line => line.includes('refs/heads/'));
            console.log(`   📊 远程分支数量: ${branches.length}`);
            
            branches.forEach(branch => {
                const branchName = branch.split('refs/heads/')[1];
                const commitHash = branch.split('\t')[0].substring(0, 8);
                console.log(`     - ${branchName} (${commitHash})`);
            });
            
            // 检查develop分支是否存在
            const hasDevelop = branches.some(branch => branch.includes('refs/heads/develop'));
            if (hasDevelop) {
                console.log('   🎉 develop分支已存在于远程仓库！');
            } else {
                console.log('   ⚠️ develop分支尚未推送到远程');
            }
        } else {
            console.log('   ⚠️ 远程仓库为空或无法获取分支信息');
        }
    } catch (error) {
        if (error.message.includes('timed out')) {
            console.log('   ⚠️ 连接超时，推送可能仍在进行中');
        } else {
            console.log(`   ❌ 远程访问失败: ${error.message}`);
        }
    }
    
    // 检查分支跟踪关系
    console.log('\n5. 检查分支跟踪关系...');
    try {
        const { stdout: branchInfo } = await execAsync('git branch -vv');
        console.log('   分支跟踪状态:');
        console.log('   ' + branchInfo.replace(/\n/g, '\n   '));
    } catch (error) {
        console.log(`   ❌ 分支检查失败: ${error.message}`);
    }
    
    console.log('\n📋 验证总结:');
    console.log('============');
    console.log('如果所有检查通过，代码已成功推送到Gitee');
    console.log('如果推送仍在进行，请等待几分钟后重试');
    console.log('\n🔗 Gitee仓库地址:');
    console.log('   https://gitee.com/ai24x/ai24x-website');
    console.log('\n🚀 下一步行动:');
    console.log('   1. 访问Gitee仓库确认代码');
    console.log('   2. 开始Day 2开发任务');
    console.log('   3. 测试完整的Git工作流');
}

// 执行验证
verifyGiteePush().catch(console.error);