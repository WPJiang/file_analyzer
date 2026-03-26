"""本地llama.cpp服务器调用客户端

封装本地llama.cpp服务器(通过llama-server.exe启动)的API调用接口，
使用OpenAI兼容API格式，支持文本生成和分类功能。
"""

import os
import base64
import json
import requests
from typing import Optional, List, Dict, Any


class LocalLlamaClient:
    """本地llama.cpp服务器API客户端

    通过llama-server.exe启动的本地服务，使用OpenAI兼容API格式。
    例如: ./llama-server.exe -m model.gguf -c 2048 --host 0.0.0.0 --port 11435

    实现与OllamaClient/CloudLLMClient相同的接口，便于无缝切换。
    """

    _instance = None

    def __new__(cls, base_url: str = None, model: str = None, config: Dict = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, base_url: str = None, model: str = None, config: Dict = None):
        if self._initialized:
            return

        # 从config或参数获取配置
        if config:
            self.base_url = (base_url or config.get('base_url', 'http://127.0.0.1:11435/v1')).rstrip('/')
            self.model = model or config.get('model', 'qwen3.5-0.8b')
            self.timeout = config.get('timeout', 300)
            self.max_tokens = config.get('max_tokens', 2048)
            self.temperature = config.get('temperature', 0.7)
        else:
            self.base_url = (base_url or 'http://127.0.0.1:11435/v1').rstrip('/')
            self.model = model or 'qwen3.5-0.8b'
            self.timeout = 300
            self.max_tokens = 2048
            self.temperature = 0.7

        self._initialized = True
        print(f"[LocalLlamaClient] 初始化完成，模型: {self.model}, 地址: {self.base_url}")

    def _get_headers(self) -> Dict[str, str]:
        """获取API请求头

        本地llama.cpp服务器通常不需要API密钥
        """
        return {
            "Content-Type": "application/json"
        }

    def _encode_image_to_base64(self, image_path: str, include_data_uri: bool = False) -> str:
        """将图片编码为base64字符串

        Args:
            image_path: 图片文件路径
            include_data_uri: 是否包含data URI前缀（llama.cpp通常不需要）

        Returns:
            base64编码的图片字符串
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
            '.bmp': 'image/bmp',
            '.heic': 'image/heic',
            '.heif': 'image/heif'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')

        base64_data = base64.b64encode(image_data).decode('utf-8')

        if include_data_uri:
            return f"data:{mime_type};base64,{base64_data}"
        else:
            # llama.cpp通常只需要纯base64
            return base64_data

    def _call_chat_api(self, system_prompt: str, user_message: str, images: List[str] = None, stream: bool = False) -> Dict[str, Any]:
        """调用Chat API

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            images: base64编码的图片列表（纯base64，不含data URI前缀）
            stream: 是否流式输出

        Returns:
            API响应字典
        """
        url = f"{self.base_url}/chat/completions"

        messages = []

        # 添加系统prompt
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 添加用户消息
        if images:
            # llama.cpp多模态格式 - 使用content数组
            content = [{"type": "text", "text": user_message}]
            for image_data in images:
                # 检查是否已经是完整的data URI格式
                if image_data.startswith('data:'):
                    image_url = image_data
                else:
                    # 纯base64，添加前缀
                    image_url = f"data:image/jpeg;base64,{image_data}"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
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

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": stream
        }

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            response.raise_for_status()

            if stream:
                # 流式处理
                full_content = ""
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data:"):
                            chunk = line[5:].strip()
                            if chunk != "[DONE]":
                                try:
                                    obj = json.loads(chunk)
                                    delta = obj.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    full_content += content
                                except json.JSONDecodeError:
                                    continue
                return {"response": full_content}
            else:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {})
                    content = message.get("content", "")
                    # Qwen3.5等模型可能使用reasoning_content字段（思考链模式）
                    reasoning_content = message.get("reasoning_content", "")
                    return {
                        "response": content if content else reasoning_content,
                        "content": content,
                        "reasoning_content": reasoning_content
                    }
                return {"response": ""}

        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接到本地llama服务: {self.base_url}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"本地llama API调用超时，超时时间: {self.timeout}秒")
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = response.json()
            except:
                pass

            # 检查是否是图片不支持的错误，提供详细提示
            error_msg = str(error_detail) if error_detail else str(e)
            if 'image input is not supported' in error_msg or 'mmproj' in error_msg:
                raise RuntimeError(
                    f"llama.cpp服务器不支持图片输入。\n\n"
                    f"要启用多模态支持，请在启动llama-server时添加--mmproj参数：\n"
                    f"  llama-server.exe -m model.gguf --mmproj mmproj.gguf --port 11435\n\n"
                    f"请确保：\n"
                    f"  1. 使用支持视觉的模型（如Qwen-VL、LLaVA等）\n"
                    f"  2. 下载对应的mmproj模型文件\n"
                    f"  3. 启动时指定--mmproj参数\n\n"
                    f"原始错误: {error_msg}"
                )
            raise RuntimeError(f"本地llama API调用失败: {str(e)}, 详情: {error_detail}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"本地llama API调用失败: {str(e)}")

    def check_service_available(self) -> bool:
        """检查本地llama服务是否可用

        Returns:
            服务是否可用
        """
        try:
            # 尝试获取模型列表或发送简单请求测试连接
            url = f"{self.base_url}/models"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            # 如果/models端点不存在，尝试简单聊天请求
            try:
                url = f"{self.base_url}/chat/completions"
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5
                }
                response = requests.post(url, json=payload, timeout=10)
                return response.status_code == 200
            except:
                return False

    def list_models(self) -> List[str]:
        """列出可用的模型

        Returns:
            模型名称列表
        """
        try:
            url = f"{self.base_url}/models"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model.get("id", self.model) for model in data.get("data", [])]
        except:
            pass
        # 如果无法获取模型列表，返回当前配置的模型
        return [self.model]

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
                print(f"[LocalLlamaClient] 已处理 {i + 1}/{len(texts)} 条文本")

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
                print(f"[LocalLlamaClient] 已处理 {i + 1}/{len(image_paths)} 张图片")

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
            print(f"[LocalLlamaClient] 生成类别信息失败: {e}")

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

        print(f"[LocalLlamaClient] 开始为 {total} 个类别生成描述和关键词...")

        for i, name in enumerate(category_names):
            try:
                info = self.generate_category_info(name)
                results[name] = info
                print(f"[LocalLlamaClient] [{i+1}/{total}] '{name}' -> 描述: {info['description'][:30]}..., 关键词: {len(info['keywords'])}个")
            except Exception as e:
                print(f"[LocalLlamaClient] [{i+1}/{total}] '{name}' 生成失败: {e}")
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
_local_llama_client = None


def get_local_llama_client(base_url: str = None, model: str = None, config: Dict = None) -> LocalLlamaClient:
    """获取本地llama客户端单例

    Args:
        base_url: 服务地址
        model: 模型名称
        config: 配置字典

    Returns:
        LocalLlamaClient实例
    """
    global _local_llama_client
    if _local_llama_client is None:
        _local_llama_client = LocalLlamaClient(base_url, model, config)
    return _local_llama_client


if __name__ == "__main__":
    client = get_local_llama_client()

    print("检查本地llama服务状态...")
    if client.check_service_available():
        print("本地llama服务可用")
        print(f"可用模型: {client.list_models()}")

        # 测试文本生成
        print("\n测试文本生成...")
        response = client.generate_text("你好，请介绍一下自己。")
        print(f"回复: {response}")
    else:
        print("本地llama服务不可用，请确保llama-server.exe正在运行")