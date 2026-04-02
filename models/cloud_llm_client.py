"""云侧大模型调用客户端

封装云侧大模型API调用接口，支持OpenAI兼容API格式。
使用OpenAI官方SDK进行调用，更加稳定可靠。
实现与OllamaClient相同的接口，支持图片描述生成和分类功能。
"""

import os
import base64
import json
from typing import Optional, List, Dict, Any


class CloudLLMClient:
    """云侧大模型API客户端

    支持OpenAI兼容API格式的云侧大模型服务，如:
    - OpenAI GPT-4V
    - 通义千问 (Qwen)
    - DeepSeek
    - 智谱 GLM-4V
    - vLLM部署的本地模型
    - 其他兼容OpenAI格式的服务

    使用OpenAI官方SDK调用，更加稳定可靠。
    """

    _instance = None

    def __new__(cls, api_key: str = None, base_url: str = None, model: str = None, config: Dict = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None, config: Dict = None):
        if self._initialized:
            return

        # 从config或参数获取配置
        if config:
            self.api_key = api_key or config.get('api_key', 'EMPTY')
            self.base_url = (base_url or config.get('base_url', 'https://api.openai.com/v1')).rstrip('/')
            self.model = model or config.get('model', 'gpt-4o')
            self.vision_model = config.get('vision_model', self.model)
            self.timeout = config.get('timeout', 120)
            # 限制 max_tokens 最大为 32768（部分模型限制）
            self.max_tokens = min(config.get('max_tokens', 2048), 32768)
            self.temperature = config.get('temperature', 0.7)
            self.disable_proxy = config.get('disable_proxy', False)
            self.max_retries = config.get('max_retries', 5)
        else:
            self.api_key = api_key or os.environ.get('OPENAI_API_KEY', 'EMPTY')
            self.base_url = (base_url or 'https://api.openai.com/v1').rstrip('/')
            self.model = model or 'gpt-4o'
            self.vision_model = self.model
            self.timeout = 120
            self.max_tokens = 2048
            self.temperature = 0.7
            self.disable_proxy = False
            self.max_retries = 5

        # 初始化OpenAI客户端
        self._init_client()

        self._initialized = True
        print(f"[CloudLLMClient] 初始化完成，模型: {self.model}, 地址: {self.base_url}")

    def _init_client(self):
        """初始化OpenAI客户端"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装openai库: pip install openai")

        # 如果配置了禁用代理，设置环境变量
        if self.disable_proxy:
            # 解析base_url获取主机地址
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            host = parsed.netloc

            os.environ["NO_PROXY"] = f"{host},localhost,127.0.0.1"
            os.environ["HTTP_PROXY"] = ""
            os.environ["HTTPS_PROXY"] = ""
            print(f"[CloudLLMClient] 已禁用代理，直连: {host}")

        # 创建OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64字符串

        Args:
            image_path: 图片文件路径

        Returns:
            base64编码的图片字符串（带data URI前缀）
        """
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # 检测图片类型
        ext = os.path.splitext(image_path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')

        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"

    def _call_chat_api(self, system_prompt: str, user_message: str, images: List[str] = None) -> Dict[str, Any]:
        """调用云侧Chat API

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            images: base64编码的图片列表

        Returns:
            API响应字典
        """
        messages = []

        # 添加系统prompt
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 添加用户消息
        if images:
            # 多模态消息格式
            content = [{"type": "text", "text": user_message}]
            for image_data in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_data}
                })
            messages.append({
                "role": "user",
                "content": content
            })
        else:
            messages.append({
                "role": "user",
                "content": user_message
            })

        # 重试机制
        for attempt in range(self.max_retries):
            try:
                # 使用OpenAI客户端调用
                response = self.client.chat.completions.create(
                    model=self.vision_model if images else self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )

                # 提取响应内容
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content or ""
                    return {"response": content}
                return {"response": ""}

            except Exception as e:
                error_msg = str(e)
                # 检查是否是超时错误
                is_timeout = 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower()

                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避：1, 2, 4, 8, 16秒
                    if is_timeout:
                        print(f"[CloudLLMClient] API调用超时 (尝试 {attempt + 1}/{self.max_retries}), {wait_time}秒后重试...")
                    else:
                        print(f"[CloudLLMClient] API调用失败: {error_msg} (尝试 {attempt + 1}/{self.max_retries}), {wait_time}秒后重试...")
                    import time
                    time.sleep(wait_time)
                else:
                    # 最后一次尝试失败，抛出异常
                    raise RuntimeError(f"云侧API调用失败 (已重试{self.max_retries}次): {error_msg}")

    def check_service_available(self) -> bool:
        """检查云侧API服务是否可用

        Returns:
            服务是否可用
        """
        try:
            # 发送简单请求测试连接
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10
            )
            return True
        except Exception as e:
            print(f"[CloudLLMClient] 服务不可用: {e}")
            return False

    def list_models(self) -> List[str]:
        """列出可用的模型

        Returns:
            模型名称列表
        """
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            print(f"[CloudLLMClient] 获取模型列表失败: {e}")
            return []

    def generate_text(self, prompt: str) -> str:
        """生成文本

        Args:
            prompt: 提示文本

        Returns:
            生成的文本
        """
        result = self._call_chat_api("", prompt)
        return result.get("response", "").strip()

    def generate_image_description(self, image_path: str, detail_level: str = "medium") -> str:
        """生成图片描述

        Args:
            image_path: 图片文件路径
            detail_level: 描述详细程度 ("brief", "medium", "detailed")

        Returns:
            图片描述文本
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image_base64 = self._encode_image_to_base64(image_path)

        # 系统prompt
        system_prompt = """你是一个图片描述助手。请根据用户要求的详细程度，为图片生成描述。"""

        # 用户消息包含详细程度要求
        detail_prompts = {
            "brief": "请用一句话简要描述这张图片的内容。",
            "medium": "请详细描述这张图片的内容，包括主要元素、场景和氛围。",
            "detailed": "请非常详细地描述这张图片的内容，包括：1. 主要主体和人物 2. 场景和环境 3. 颜色和光线 4. 构图和视角 5. 图片传达的情感或信息"
        }

        user_message = detail_prompts.get(detail_level, detail_prompts["medium"])

        result = self._call_chat_api(system_prompt, user_message, images=[image_base64])
        return result.get("response", "").strip()

    def classify_image(self, image_path: str, categories: List[str] = None) -> Dict[str, Any]:
        """对图片进行分类

        Args:
            image_path: 图片文件路径
            categories: 可选的分类列表，如果不提供则使用默认分类

        Returns:
            分类结果字典
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image_base64 = self._encode_image_to_base64(image_path)

        if categories is None:
            categories = [
                "技术文档",
                "商业报告",
                "学术论文",
                "会议演示",
                "合同协议",
                "产品说明",
                "新闻资讯",
                "个人文档",
                "其他"
            ]

        categories_text = "、".join(categories)
        system_prompt = f"""你是一个图片分类助手。请根据给定的分类列表，为图片选择最合适的分类。
可选分类：{categories_text}

请直接回答分类名称，不需要解释。"""

        user_message = "请对这张图片进行分类。"

        result = self._call_chat_api(system_prompt, user_message, images=[image_base64])
        response_text = result.get("response", "").strip()

        category = "其他"
        reasoning = response_text

        for cat in categories:
            if cat in response_text:
                category = cat
                break

        return {
            "category": category,
            "reasoning": reasoning,
            "all_categories": categories
        }

    def classify_text(self, text: str, categories: List[str] = None, category_descriptions: Dict[str, str] = None) -> Dict[str, Any]:
        """对文本进行分类

        Args:
            text: 待分类的文本内容
            categories: 可选的分类列表
            category_descriptions: 可选的分类描述字典

        Returns:
            分类结果字典
        """
        if not text or not text.strip():
            return {
                "category": "其他",
                "confidence": 0.0,
                "reasoning": "输入文本为空",
                "all_categories": categories or []
            }

        if categories is None:
            categories = [
                "技术文档",
                "商业报告",
                "学术论文",
                "会议演示",
                "合同协议",
                "产品说明",
                "新闻资讯",
                "个人文档",
                "其他"
            ]

        max_text_length = 1000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."

        categories_text = "、".join(categories)
        system_prompt = f"""你是一个文本分类助手。请根据给定的分类列表，为文本选择最合适的分类。
可选分类：{categories_text}

请直接回答分类名称，不需要解释。"""

        user_message = f"请对以下文本进行分类：\n\n{text}"

        result = self._call_chat_api(system_prompt, user_message)
        response_text = result.get("response", "").strip()

        category = "其他"
        confidence = 0.5
        reasoning = response_text

        for cat in categories:
            if cat in response_text:
                category = cat
                break

        return {
            "category": category,
            "confidence": confidence,
            "reasoning": reasoning,
            "all_categories": categories
        }

    def classify_text_batch(self, texts: List[str], categories: List[str] = None, category_descriptions: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """批量对文本进行分类

        Args:
            texts: 待分类的文本列表
            categories: 可选的分类列表
            category_descriptions: 可选的分类描述字典

        Returns:
            分类结果列表
        """
        results = []
        for i, text in enumerate(texts):
            try:
                result = self.classify_text(text, categories, category_descriptions)
                result["index"] = i
                result["success"] = True
            except Exception as e:
                result = {
                    "index": i,
                    "category": "其他",
                    "confidence": 0.0,
                    "reasoning": f"分类失败: {str(e)}",
                    "success": False
                }
            results.append(result)

            if (i + 1) % 10 == 0:
                print(f"[CloudLLMClient] 已处理 {i + 1}/{len(texts)} 条文本")

        return results

    def classify_image_batch(self, image_paths: List[str], categories: List[str] = None) -> List[Dict[str, Any]]:
        """批量对图片进行分类

        Args:
            image_paths: 图片文件路径列表
            categories: 可选的分类列表

        Returns:
            分类结果列表
        """
        results = []
        for i, image_path in enumerate(image_paths):
            try:
                result = self.classify_image(image_path, categories)
                result["file_path"] = image_path
                result["success"] = True
            except Exception as e:
                result = {
                    "file_path": image_path,
                    "category": "其他",
                    "reasoning": f"分类失败: {str(e)}",
                    "success": False
                }
            results.append(result)

            if (i + 1) % 10 == 0:
                print(f"[CloudLLMClient] 已处理 {i + 1}/{len(image_paths)} 张图片")

        return results

    def extract_text_from_image(self, image_path: str) -> str:
        """从图片中提取文字内容描述

        Args:
            image_path: 图片文件路径

        Returns:
            图片中的文字内容描述
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image_base64 = self._encode_image_to_base64(image_path)

        system_prompt = """你是一个OCR助手。请识别图片中的文字内容并输出。
如果图片中没有文字，请描述图片的主要内容。"""

        user_message = "请识别并提取这张图片中的所有文字内容，直接输出文字内容，不需要额外说明。"

        result = self._call_chat_api(system_prompt, user_message, images=[image_base64])
        return result.get("response", "").strip()

    def generate_category_info(self, category_name: str) -> Dict[str, Any]:
        """为类别生成描述和关键词

        Args:
            category_name: 类别名称

        Returns:
            包含 description 和 keywords 的字典
        """
        system_prompt = """你是一个文件分类助手。请根据给定的类别名称，生成该类别的描述和关键词。
描述应该简洁明了，说明这类文件的特征。
关键词应该是5-8个能够代表该类别的词语，用于文件分类匹配。

请按以下JSON格式输出：
{
    "description": "类别描述，一句话说明这类文件的特征",
    "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"]
}"""

        user_message = f"请为类别 '{category_name}' 生成描述和关键词。"

        try:
            result = self._call_chat_api(system_prompt, user_message)
            response_text = result.get("response", "").strip()

            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)
                return {
                    "description": parsed.get("description", f"{category_name}相关文件"),
                    "keywords": parsed.get("keywords", [])
                }
        except Exception as e:
            print(f"[CloudLLMClient] 生成类别信息失败: {e}")

        return {
            "description": f"{category_name}相关文件",
            "keywords": []
        }

    def generate_category_info_batch(self, category_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量为类别生成描述和关键词

        Args:
            category_names: 类别名称列表

        Returns:
            类别名称 -> {description, keywords} 的字典
        """
        results = {}
        total = len(category_names)

        print(f"[CloudLLMClient] 开始为 {total} 个类别生成描述和关键词...")

        for i, name in enumerate(category_names):
            try:
                info = self.generate_category_info(name)
                results[name] = info
                print(f"[CloudLLMClient] [{i+1}/{total}] '{name}' -> 描述: {info['description'][:30]}..., 关键词: {len(info['keywords'])}个")
            except Exception as e:
                print(f"[CloudLLMClient] [{i+1}/{total}] '{name}' 生成失败: {e}")
                results[name] = {
                    "description": f"{name}相关文件",
                    "keywords": []
                }

        return results

    def analyze_image_content(self, image_path: str) -> Dict[str, Any]:
        """综合分析图片内容

        Args:
            image_path: 图片文件路径

        Returns:
            分析结果字典
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image_base64 = self._encode_image_to_base64(image_path)

        system_prompt = """你是一个图片分析助手。请综合分析图片并提供以下信息：
1. 描述：简要描述图片内容
2. 分类：选择一个合适的分类（如：技术文档、商业报告、学术论文、会议演示、产品图片、新闻资讯、个人照片、风景、建筑、其他）
3. 文字内容：如果图片中有文字，请提取出来
4. 标签：给出3-5个描述图片的关键标签

请按以下JSON格式输出：
{
    "description": "图片描述",
    "category": "分类",
    "text_content": "文字内容",
    "tags": ["标签1", "标签2", "标签3"]
}"""

        user_message = "请分析这张图片。"

        result = self._call_chat_api(system_prompt, user_message, images=[image_base64])
        response_text = result.get("response", "").strip()

        analysis = {
            "description": "",
            "category": "其他",
            "text_content": "",
            "tags": []
        }

        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                analysis = json.loads(json_str)
        except json.JSONDecodeError:
            analysis["description"] = response_text

        return analysis


# 全局实例
_cloud_llm_client = None


def get_cloud_llm_client(api_key: str = None, base_url: str = None, model: str = None, config: Dict = None) -> CloudLLMClient:
    """获取云侧LLM客户端单例

    Args:
        api_key: API密钥
        base_url: API基础URL
        model: 模型名称
        config: 配置字典

    Returns:
        CloudLLMClient实例
    """
    global _cloud_llm_client
    if _cloud_llm_client is None:
        _cloud_llm_client = CloudLLMClient(api_key, base_url, model, config)
    return _cloud_llm_client