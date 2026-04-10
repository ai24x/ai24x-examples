#!/usr/bin/env python3
"""
AI24X 副脑01 API 测试脚本
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
TEST_USER_ID = "test_user_001"


def test_health_check():
    """测试健康检查端点"""
    print("测试健康检查...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False


def test_chat_request():
    """测试聊天请求"""
    print("\n测试聊天请求...")
    
    payload = {
        "prompt": "用Python实现一个快速排序算法",
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 1000,
        "stream": False
    }
    
    try:
        # 使用用户ID进行测试（实际使用中应该用API Key）
        response = requests.post(
            f"{BASE_URL}/v1/chat/run?user_id={TEST_USER_ID}",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"请求ID: {data.get('request_id')}")
            print(f"用户类型: {data.get('user_type')}")
            print(f"处理时间: {data.get('processing_time')}秒")
            print(f"Token消耗: {data.get('token_count')}")
            print(f"回复内容: {data.get('response')[:100]}...")
            return True
        else:
            print(f"错误: {response.json()}")
            return False
            
    except Exception as e:
        print(f"聊天请求失败: {e}")
        return False


def test_user_info():
    """测试用户信息端点"""
    print("\n测试用户信息...")
    
    try:
        # 注意：实际使用中需要API Key，这里使用用户ID参数
        response = requests.get(f"{BASE_URL}/v1/user/info?user_id={TEST_USER_ID}")
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"用户ID: {data.get('user_id')}")
            print(f"用户类型: {data.get('user_type')}")
            print(f"每日限制: {data.get('daily_limit')}")
            print(f"今日已用: {data.get('daily_used')}")
            print(f"剩余配额: {data.get('remaining_daily')}")
            return True
        else:
            print(f"错误: {response.json()}")
            return False
            
    except Exception as e:
        print(f"用户信息查询失败: {e}")
        return False


def test_rate_limit():
    """测试速率限制"""
    print("\n测试速率限制（快速连续请求）...")
    
    payload = {
        "prompt": "测试速率限制",
        "model": "gpt-3.5-turbo"
    }
    
    success_count = 0
    fail_count = 0
    
    for i in range(5):
        try:
            response = requests.post(
                f"{BASE_URL}/v1/chat/run?user_id={TEST_USER_ID}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                success_count += 1
                print(f"请求 {i+1}: 成功")
            elif response.status_code == 429:
                fail_count += 1
                print(f"请求 {i+1}: 被限制 - {response.json().get('error')}")
            else:
                fail_count += 1
                print(f"请求 {i+1}: 失败 - 状态码 {response.status_code}")
                
            time.sleep(0.5)  # 稍微延迟
            
        except Exception as e:
            fail_count += 1
            print(f"请求 {i+1}: 异常 - {e}")
    
    print(f"\n总结: 成功 {success_count} 次, 失败 {fail_count} 次")
    return success_count > 0


def test_different_prompts():
    """测试不同的提示词"""
    print("\n测试不同的提示词...")
    
    test_cases = [
        {
            "name": "Python问题",
            "prompt": "解释Python中的装饰器"
        },
        {
            "name": "FastAPI问题", 
            "prompt": "FastAPI和Flask有什么区别？"
        },
        {
            "name": "数据库问题",
            "prompt": "PostgreSQL和MySQL的主要区别是什么？"
        },
        {
            "name": "算法问题",
            "prompt": "实现一个二分查找算法"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        
        payload = {
            "prompt": test_case["prompt"],
            "model": "gpt-3.5-turbo"
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/v1/chat/run?user_id={TEST_USER_ID}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  状态: 成功")
                print(f"  回复长度: {len(data.get('response', ''))} 字符")
            else:
                print(f"  状态: 失败 - {response.status_code}")
                
            time.sleep(1)  # 请求间隔
            
        except Exception as e:
            print(f"  异常: {e}")


def main():
    """主测试函数"""
    print("=" * 50)
    print("AI24X 副脑01 API 测试套件")
    print("=" * 50)
    
    # 等待服务启动
    print("等待服务启动...")
    time.sleep(2)
    
    tests = [
        ("健康检查", test_health_check),
        ("聊天请求", test_chat_request),
        ("用户信息", test_user_info),
        ("不同提示词", test_different_prompts),
        ("速率限制", test_rate_limit),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*30}")
        print(f"开始测试: {test_name}")
        print(f"{'='*30}")
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"测试异常: {e}")
            results.append((test_name, False))
    
    # 输出测试结果
    print(f"\n{'='*50}")
    print("测试结果汇总")
    print(f"{'='*50}")
    
    all_passed = True
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{test_name:20} {status}")
        if not success:
            all_passed = False
    
    print(f"\n总体结果: {'所有测试通过' if all_passed else '有测试失败'}")
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)