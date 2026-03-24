"""云侧大模型连接测试脚本

测试云侧LLM API是否可用，包括：
1. API连接测试
2. 模型列表获取
3. 简单文本生成测试
"""

import os
import sys
import json
import requests
from typing import Dict, Any

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = os.path.join(project_root, 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def test_api_connection(base_url: str, api_key: str) -> Dict[str, Any]:
    """测试API连接

    Args:
        base_url: API基础URL
        api_key: API密钥

    Returns:
        测试结果字典
    """
    result = {
        'test_name': 'API连接测试',
        'success': False,
        'message': '',
        'details': {}
    }

    if not api_key:
        result['message'] = 'API密钥未配置'
        return result

    try:
        url = f"{base_url.rstrip('/')}/models"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        print(f"\n[测试1] 请求URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)

        result['details']['status_code'] = response.status_code

        if response.status_code == 200:
            result['success'] = True
            result['message'] = 'API连接成功'
            try:
                data = response.json()
                models = [m.get('id', m.get('name', 'unknown')) for m in data.get('data', data.get('models', []))]
                result['details']['available_models'] = models[:10]  # 只显示前10个
            except:
                result['details']['response'] = response.text[:500]
        else:
            result['message'] = f'API返回错误: HTTP {response.status_code}'
            try:
                error_data = response.json()
                result['details']['error'] = error_data
            except:
                result['details']['response'] = response.text[:500]

    except requests.exceptions.ConnectionError as e:
        result['message'] = f'连接失败: 无法连接到 {base_url}'
        result['details']['error'] = str(e)
    except requests.exceptions.Timeout:
        result['message'] = '连接超时: 请求超过10秒未响应'
    except Exception as e:
        result['message'] = f'连接异常: {str(e)}'
        result['details']['error'] = str(e)

    return result


def test_text_generation(base_url: str, api_key: str, model: str) -> Dict[str, Any]:
    """测试文本生成

    Args:
        base_url: API基础URL
        api_key: API密钥
        model: 模型名称

    Returns:
        测试结果字典
    """
    result = {
        'test_name': '文本生成测试',
        'success': False,
        'message': '',
        'details': {}
    }

    if not api_key:
        result['message'] = 'API密钥未配置'
        return result

    try:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "请用一句话回答: 1+1等于几?"}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        print(f"\n[测试2] 请求URL: {url}")
        print(f"[测试2] 使用模型: {model}")

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        result['details']['status_code'] = response.status_code

        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0].get('message', {}).get('content', '')
                result['success'] = True
                result['message'] = '文本生成成功'
                result['details']['response'] = content
                result['details']['model_used'] = data.get('model', model)
                result['details']['usage'] = data.get('usage', {})
            else:
                result['message'] = '响应格式异常: 未找到choices'
                result['details']['response'] = data
        else:
            result['message'] = f'API返回错误: HTTP {response.status_code}'
            try:
                error_data = response.json()
                result['details']['error'] = error_data
            except:
                result['details']['response'] = response.text[:500]

    except requests.exceptions.ConnectionError as e:
        result['message'] = f'连接失败: 无法连接到 {base_url}'
    except requests.exceptions.Timeout:
        result['message'] = '请求超时: 生成超过30秒未完成'
    except Exception as e:
        result['message'] = f'请求异常: {str(e)}'
        result['details']['error'] = str(e)

    return result


def print_result(result: Dict[str, Any]):
    """打印测试结果"""
    status = "[OK] 通过" if result['success'] else "[FAIL] 失败"
    print(f"\n{'='*60}")
    print(f"测试项目: {result['test_name']}")
    print(f"测试结果: {status}")
    print(f"结果说明: {result['message']}")

    if result.get('details'):
        print("\n详细信息:")
        for key, value in result['details'].items():
            if isinstance(value, list):
                print(f"  {key}: {value}")
            elif isinstance(value, dict):
                print(f"  {key}: {json.dumps(value, ensure_ascii=False, indent=4)}")
            else:
                print(f"  {key}: {value}")
    print('='*60)


def main():
    """主测试函数"""
    print("="*60)
    print("云侧大模型连接测试")
    print("="*60)

    # 加载配置
    config = load_config()
    llm_config = config.get('llm', {})
    cloud_config = llm_config.get('cloud', {})

    # 获取配置参数
    api_key = cloud_config.get('api_key', '')
    base_url = cloud_config.get('base_url', 'https://api.openai.com/v1')
    model = cloud_config.get('model', 'gpt-4o')

    print(f"\n配置信息:")
    print(f"  API地址: {base_url}")
    print(f"  模型名称: {model}")
    print(f"  API密钥: {'已配置 (' + api_key[:8] + '...' + api_key[-4:] + ')' if api_key else '未配置'}")
    print(f"  LLM类型: {llm_config.get('type', 'cloud')}")

    all_passed = True

    # 测试1: API连接
    result1 = test_api_connection(base_url, api_key)
    print_result(result1)
    if not result1['success']:
        all_passed = False

    # 测试2: 文本生成 (只有连接测试通过才执行)
    if result1['success']:
        result2 = test_text_generation(base_url, api_key, model)
        print_result(result2)
        if not result2['success']:
            all_passed = False
    else:
        print("\n[跳过] 文本生成测试 (API连接失败)")

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    if all_passed:
        print("[OK] 所有测试通过，云侧大模型服务可用")
    else:
        print("[FAIL] 部分测试失败，请检查配置或网络")

        # 提供常见问题排查建议
        print("\n常见问题排查:")
        print("1. 检查API密钥是否正确")
        print("2. 检查base_url是否与模型匹配:")
        print("   - 阿里云通义千问: https://dashscope.aliyuncs.com/compatible-mode/v1")
        print("   - OpenAI: https://api.openai.com/v1")
        print("   - DeepSeek: https://api.deepseek.com/v1")
        print("   - Kimi: https://api.moonshot.cn/v1")
        print("3. 检查模型名称是否正确:")
        print("   - 阿里云: qwen-turbo, qwen-plus, qwen-max, qwen-vl-plus")
        print("   - OpenAI: gpt-4o, gpt-4o-mini")
        print("   - DeepSeek: deepseek-chat, deepseek-coder")
        print("   - Kimi: moonshot-v1-8k, moonshot-v1-32k")
        print("4. 检查网络是否能访问API地址")
        print("5. 检查API密钥是否有余额/额度")

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)