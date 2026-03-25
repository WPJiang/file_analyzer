"""图片Caption和标签生成模块

使用LLM对图片进行描述(caption)和标签分类。
"""

import os
import base64
import json
import requests
from typing import Dict, Any, List, Optional, Tuple


# 图片标签分类体系 - 基于常见图片分类测评集和个人照片场景
IMAGE_TAG_CATEGORIES = {
    # 场景类别
    "场景": [
        "室内", "户外", "自然风光", "城市街景", "建筑", "海滩", "山脉",
        "森林", "公园", "花园", "田野", "沙漠", "雪景", "夜景"
    ],
    # 人物类别
    "人物": [
        "单人照", "双人照", "合影", "自拍", "家庭照", "儿童", "老人",
        "朋友聚会", "情侣", "婚礼"
    ],
    # 活动类别
    "活动": [
        "旅行", "美食", "运动健身", "节日庆典", "生日派对", "毕业典礼",
        "会议活动", "演出表演", "宠物", "游戏娱乐"
    ],
    # 物品类别
    "物品": [
        "美食饮品", "服饰穿搭", "电子产品", "交通工具", "家具家居",
        "书籍文具", "工艺品", "珠宝首饰", "化妆品", "玩具"
    ],
    # 摄影类型
    "摄影": [
        "人像摄影", "风景摄影", "微距摄影", "街拍", "纪实摄影",
        "艺术摄影", "建筑摄影", "美食摄影", "产品摄影"
    ],
    # 时间/季节
    "时间": [
        "日出", "日落", "白天", "夜晚", "春天", "夏天", "秋天", "冬天"
    ],
    # 情感氛围
    "氛围": [
        "温馨", "浪漫", "欢乐", "宁静", "活力", "怀旧", "清新", "时尚"
    ]
}

# 扁平化的所有标签列表
ALL_IMAGE_TAGS = []
for category, tags in IMAGE_TAG_CATEGORIES.items():
    ALL_IMAGE_TAGS.extend(tags)


class ImageCaptionTagger:
    """图片Caption和标签生成器"""

    def __init__(self, llm_client=None):
        """初始化

        Args:
            llm_client: LLM客户端实例，如果为None则使用全局客户端
        """
        self.llm_client = llm_client

    def _get_llm_client(self):
        """获取LLM客户端"""
        if self.llm_client is not None:
            return self.llm_client

        from models.model_manager import get_llm_client
        return get_llm_client()

    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64字符串"""
        with open(image_path, 'rb') as f:
            image_data = f.read()

        ext = os.path.splitext(image_path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.heic': 'image/heic',
            '.heif': 'image/heif'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')

        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"

    def generate_caption_and_tags(self, image_path: str) -> Dict[str, Any]:
        """生成图片的Caption和标签

        Args:
            image_path: 图片文件路径

        Returns:
            包含caption和tags的字典:
            {
                'caption': '30字以内的描述',
                'tags': ['标签1', '标签2', ...],
                'success': True/False,
                'error': '错误信息(如果失败)'
            }
        """
        result = {
            'caption': None,
            'tags': [],
            'success': False,
            'error': None
        }

        if not os.path.exists(image_path):
            result['error'] = f'图片文件不存在: {image_path}'
            return result

        try:
            client = self._get_llm_client()
            if client is None:
                result['error'] = 'LLM服务不可用'
                return result

            # 编码图片
            image_base64 = self._encode_image_to_base64(image_path)

            # 构建prompt
            all_tags_str = '、'.join(ALL_IMAGE_TAGS[:50])  # 只列出部分标签作为参考

            system_prompt = """你是一个图片描述和标签助手。请分析图片并输出：
1. caption：用中文简洁描述图片内容，不超过30字
2. tags：选择3-5个最贴切的标签

请严格按照以下JSON格式输出，不要有多余内容：
{
    "caption": "图片描述文字，不超过30字",
    "tags": ["标签1", "标签2", "标签3"]
}"""

            user_message = f"请分析这张图片并生成描述和标签。可参考的标签类别包括：{all_tags_str}等。"

            # 调用LLM
            response = self._call_llm_with_image(client, system_prompt, user_message, image_base64)

            if response:
                # 解析响应
                parsed = self._parse_response(response)
                if parsed:
                    result['caption'] = parsed.get('caption', '')
                    result['tags'] = parsed.get('tags', [])
                    result['success'] = True
                else:
                    result['error'] = '解析LLM响应失败'
            else:
                result['error'] = 'LLM未返回有效响应'

        except Exception as e:
            result['error'] = str(e)

        return result

    def _call_llm_with_image(self, client, system_prompt: str, user_message: str, image_base64: str) -> Optional[str]:
        """调用LLM处理图片

        Args:
            client: LLM客户端
            system_prompt: 系统提示词
            user_message: 用户消息
            image_base64: base64编码的图片

        Returns:
            LLM响应文本
        """
        try:
            # 尝试使用支持图片的方法
            if hasattr(client, '_call_chat_api'):
                # LocalLlamaClient
                result = client._call_chat_api(system_prompt, user_message, images=[image_base64])
                return result.get('response', '')
            elif hasattr(client, 'generate_image_description'):
                # 使用现有的图片描述方法，但我们需要自定义prompt
                # 这种方法可能不太理想，但作为备选
                return self._call_with_custom_prompt(client, system_prompt, user_message, image_base64)
            else:
                return None
        except Exception as e:
            error_msg = str(e)
            # 检查是否是图片不支持的错误
            if 'image input is not supported' in error_msg or 'mmproj' in error_msg:
                raise RuntimeError(
                    "当前LLM服务不支持图片输入。\n\n"
                    "请使用支持视觉的模型，例如：\n"
                    "• Ollama + llava 模型\n"
                    "• llama.cpp 带 mmproj 支持\n"
                    "• 云侧API（如GPT-4V）"
                )
            print(f"[ImageCaptionTagger] LLM调用失败: {e}")
            return None

    def _call_with_custom_prompt(self, client, system_prompt: str, user_message: str, image_base64: str) -> Optional[str]:
        """使用自定义prompt调用LLM"""
        # 对于OpenAI兼容API
        try:
            if hasattr(client, 'base_url'):
                url = f"{client.base_url}/chat/completions"
                headers = {"Content-Type": "application/json"}

                messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_message},
                            {"type": "image_url", "image_url": {"url": image_base64}}
                        ]
                    }
                ]

                payload = {
                    "model": getattr(client, 'model', 'default'),
                    "messages": messages,
                    "max_tokens": getattr(client, 'max_tokens', 500),
                    "temperature": getattr(client, 'temperature', 0.7)
                }

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=getattr(client, 'timeout', 60)
                )
                response.raise_for_status()

                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0].get("message", {}).get("content", "")
            return None
        except Exception as e:
            print(f"[ImageCaptionTagger] API调用失败: {e}")
            return None

    def _parse_response(self, response: str) -> Optional[Dict]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)

                # 验证字段
                caption = parsed.get('caption', '')
                tags = parsed.get('tags', [])

                # 清理标签
                if isinstance(tags, list):
                    tags = [str(t) for t in tags if t]

                # 限制caption长度
                if len(caption) > 50:
                    caption = caption[:47] + '...'

                return {
                    'caption': caption,
                    'tags': tags[:5]  # 最多5个标签
                }
        except json.JSONDecodeError as e:
            print(f"[ImageCaptionTagger] JSON解析失败: {e}")
        except Exception as e:
            print(f"[ImageCaptionTagger] 响应解析失败: {e}")

        return None

    def batch_generate(self, image_paths: List[str], progress_callback=None) -> List[Dict[str, Any]]:
        """批量生成Caption和标签

        Args:
            image_paths: 图片路径列表
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            结果列表
        """
        results = []
        total = len(image_paths)

        for i, image_path in enumerate(image_paths):
            if progress_callback:
                progress_callback(i + 1, total, f"处理: {os.path.basename(image_path)}")

            result = self.generate_caption_and_tags(image_path)
            result['file_path'] = image_path
            results.append(result)

        return results


def generate_image_caption_and_tags(image_path: str, llm_client=None) -> Dict[str, Any]:
    """便捷函数：生成图片Caption和标签

    Args:
        image_path: 图片文件路径
        llm_client: 可选的LLM客户端

    Returns:
        包含caption和tags的字典
    """
    tagger = ImageCaptionTagger(llm_client)
    return tagger.generate_caption_and_tags(image_path)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    # 测试
    test_image = "D:/jiangweipeng/trae_code/个人文件/图片sample/IMG_20250308_163304.jpg"

    if os.path.exists(test_image):
        print(f"测试图片: {test_image}")
        result = generate_image_caption_and_tags(test_image)
        print(f"Caption: {result.get('caption')}")
        print(f"Tags: {result.get('tags')}")
        print(f"Success: {result.get('success')}")
        if result.get('error'):
            print(f"Error: {result.get('error')}")
    else:
        print(f"测试图片不存在: {test_image}")