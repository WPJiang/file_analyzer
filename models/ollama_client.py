"""Ollama本地模型调用客户端

封装本地Ollama运行的qwen3.5:0.8b模型调用接口，
支持图片描述生成和图片分类功能。
"""

import os
import base64
import json
import requests
from typing import Optional, List, Dict, Any
from functools import lru_cache


class OllamaClient:
    """Ollama API客户端
    
    封装与本地Ollama服务的交互，支持:
    1. 文本生成
    2. 图片描述生成
    3. 图片分类
    """
    
    _instance = None
    
    def __new__(cls, base_url: str = "http://localhost:11434", model: str = "qwen3.5:0.8b"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3.5:0.8b"):
        if self._initialized:
            return

        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = 120
        # keep_alive参数：让模型在内存中保持的时间，避免每次调用重新加载
        # 默认10分钟，对于频繁调用的场景可以显著降低时延
        self.keep_alive = "10m"
        # 缓存系统prompt对应的会话ID，用于复用上下文
        self._session_cache: Dict[str, Any] = {}
        self._initialized = True

        print(f"[OllamaClient] 初始化完成，模型: {model}, 地址: {base_url}, keep_alive: {self.keep_alive}")
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64字符串
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            base64编码的图片字符串
        """
        with open(image_path, 'rb') as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')
    
    def _call_api(self, prompt: str, images: List[str] = None, stream: bool = False) -> Dict[str, Any]:
        """调用Ollama API (generate接口)

        Args:
            prompt: 提示文本
            images: base64编码的图片列表
            stream: 是否使用流式输出

        Returns:
            API响应字典
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "keep_alive": self.keep_alive  # 让模型在内存中保持
        }

        if images:
            payload["images"] = images

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            if stream:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        full_response += data.get("response", "")
                return {"response": full_response}
            else:
                return response.json()

        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接到Ollama服务，请确保Ollama正在运行: {self.base_url}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Ollama API调用超时，超时时间: {self.timeout}秒")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API调用失败: {str(e)}")

    def _call_chat_api(self, system_prompt: str, user_message: str, images: List[str] = None, stream: bool = False) -> Dict[str, Any]:
        """调用Ollama Chat API，支持系统prompt缓存

        使用/api/chat接口，将系统prompt和用户输入分离，
        Ollama可以对系统prompt的KV cache进行缓存，降低时延。

        Args:
            system_prompt: 系统提示词（会被缓存）
            user_message: 用户消息
            images: base64编码的图片列表
            stream: 是否使用流式输出

        Returns:
            API响应字典
        """
        url = f"{self.base_url}/api/chat"

        messages = []

        # 添加系统prompt
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 添加用户消息
        user_message_obj = {
            "role": "user",
            "content": user_message
        }
        # 图片附加到用户消息
        if images:
            user_message_obj["images"] = images
        messages.append(user_message_obj)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive  # 让模型在内存中保持
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            if stream:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data:
                            full_response += data["message"].get("content", "")
                return {"response": full_response}
            else:
                result = response.json()
                # 从chat响应中提取内容
                if "message" in result:
                    return {"response": result["message"].get("content", "")}
                return result

        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接到Ollama服务，请确保Ollama正在运行: {self.base_url}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Ollama API调用超时，超时时间: {self.timeout}秒")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API调用失败: {str(e)}")
    
    def check_service_available(self) -> bool:
        """检查Ollama服务是否可用
        
        Returns:
            服务是否可用
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> List[str]:
        """列出可用的模型
        
        Returns:
            模型名称列表
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except:
            return []
    
    def generate_text(self, prompt: str) -> str:
        """生成文本
        
        Args:
            prompt: 提示文本
            
        Returns:
            生成的文本
        """
        result = self._call_api(prompt)
        return result.get("response", "").strip()
    
    def generate_image_description(self, image_path: str, detail_level: str = "medium") -> str:
        """生成图片描述

        使用chat接口分离系统prompt，支持prompt缓存优化。

        Args:
            image_path: 图片文件路径
            detail_level: 描述详细程度 ("brief", "medium", "detailed")

        Returns:
            图片描述文本
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image_base64 = self._encode_image_to_base64(image_path)

        # 系统prompt（固定部分，可被缓存）
        system_prompt = """你是一个图片描述助手。请根据用户要求的详细程度，为图片生成描述。"""

        # 用户消息包含详细程度要求
        detail_prompts = {
            "brief": "请用一句话简要描述这张图片的内容。",
            "medium": "请详细描述这张图片的内容，包括主要元素、场景和氛围。",
            "detailed": "请非常详细地描述这张图片的内容，包括：1. 主要主体和人物 2. 场景和环境 3. 颜色和光线 4. 构图和视角 5. 图片传达的情感或信息"
        }

        user_message = detail_prompts.get(detail_level, detail_prompts["medium"])

        # 使用chat接口调用
        result = self._call_chat_api(system_prompt, user_message, images=[image_base64])
        return result.get("response", "").strip()
    
    def classify_image(self, image_path: str, categories: List[str] = None) -> Dict[str, Any]:
        """对图片进行分类

        使用chat接口分离系统prompt和用户输入，支持prompt缓存优化。

        Args:
            image_path: 图片文件路径
            categories: 可选的分类列表，如果不提供则使用默认分类

        Returns:
            分类结果字典，包含:
            - category: 分类结果
            - confidence: 置信度描述
            - reasoning: 分类理由
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

        # 构建系统prompt（固定部分，可被缓存）
        categories_text = "、".join(categories)
        system_prompt = f"""你是一个图片分类助手。请根据给定的分类列表，为图片选择最合适的分类。
可选分类：{categories_text}

请直接回答分类名称，不需要解释。"""

        # 用户消息（包含图片）
        user_message = "请对这张图片进行分类。"

        # 使用chat接口调用，系统prompt可被缓存
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

        使用chat接口分离系统prompt和用户输入，支持prompt缓存优化。

        Args:
            text: 待分类的文本内容
            categories: 可选的分类列表，如果不提供则使用默认分类
            category_descriptions: 可选的分类描述字典，用于提供更精确的分类依据

        Returns:
            分类结果字典，包含:
            - category: 分类结果
            - confidence: 置信度 (0-1)
            - reasoning: 分类理由
            - all_categories: 所有可选分类
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

        # 构建系统prompt（固定部分，可被缓存）
        categories_text = "、".join(categories)
        system_prompt = f"""你是一个文本分类助手。请根据给定的分类列表，为文本选择最合适的分类。
可选分类：{categories_text}

请直接回答分类名称，不需要解释。"""

        # 用户消息（变化部分）
        user_message = f"请对以下文本进行分类：\n\n{text}"

        # 使用chat接口调用，系统prompt可被缓存
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
                print(f"[OllamaClient] 已处理 {i + 1}/{len(texts)} 条文本")
        
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
                print(f"[OllamaClient] 已处理 {i + 1}/{len(image_paths)} 张图片")
        
        return results
    
    def extract_text_from_image(self, image_path: str) -> str:
        """从图片中提取文字内容描述

        使用chat接口分离系统prompt，支持prompt缓存优化。

        Args:
            image_path: 图片文件路径

        Returns:
            图片中的文字内容描述
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image_base64 = self._encode_image_to_base64(image_path)

        # 系统prompt（固定部分，可被缓存）
        system_prompt = """你是一个OCR助手。请识别图片中的文字内容并输出。
如果图片中没有文字，请描述图片的主要内容。"""

        # 用户消息
        user_message = "请识别并提取这张图片中的所有文字内容，直接输出文字内容，不需要额外说明。"

        # 使用chat接口调用
        result = self._call_chat_api(system_prompt, user_message, images=[image_base64])
        return result.get("response", "").strip()

    def generate_category_info(self, category_name: str) -> Dict[str, Any]:
        """为类别生成描述和关键词

        使用LLM基于类别名称生成合适的描述和关键词列表。

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

            # 解析JSON响应
            import json
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
            print(f"[OllamaClient] 生成类别信息失败: {e}")

        # 返回默认值
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

        print(f"[OllamaClient] 开始为 {total} 个类别生成描述和关键词...")

        for i, name in enumerate(category_names):
            try:
                info = self.generate_category_info(name)
                results[name] = info
                print(f"[OllamaClient] [{i+1}/{total}] '{name}' -> 描述: {info['description'][:30]}..., 关键词: {len(info['keywords'])}个")
            except Exception as e:
                print(f"[OllamaClient] [{i+1}/{total}] '{name}' 生成失败: {e}")
                results[name] = {
                    "description": f"{name}相关文件",
                    "keywords": []
                }

        return results

    def analyze_image_content(self, image_path: str) -> Dict[str, Any]:
        """综合分析图片内容

        使用chat接口分离系统prompt，支持prompt缓存优化。

        Args:
            image_path: 图片文件路径

        Returns:
            分析结果字典，包含:
            - description: 图片描述
            - category: 分类
            - text_content: 文字内容
            - tags: 标签列表
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image_base64 = self._encode_image_to_base64(image_path)

        # 系统prompt（固定部分，可被缓存）
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

        # 用户消息
        user_message = "请分析这张图片。"

        # 使用chat接口调用
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


_ollama_client = None


def get_ollama_client(base_url: str = "http://localhost:11434", model: str = "qwen3.5:0.8b") -> OllamaClient:
    """获取Ollama客户端单例
    
    Args:
        base_url: Ollama服务地址
        model: 模型名称
        
    Returns:
        OllamaClient实例
    """
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(base_url, model)
    return _ollama_client


def generate_image_description(image_path: str, detail_level: str = "medium") -> str:
    """生成图片描述的便捷函数
    
    Args:
        image_path: 图片文件路径
        detail_level: 描述详细程度
        
    Returns:
        图片描述文本
    """
    client = get_ollama_client()
    return client.generate_image_description(image_path, detail_level)


def classify_image(image_path: str, categories: List[str] = None) -> Dict[str, Any]:
    """图片分类的便捷函数
    
    Args:
        image_path: 图片文件路径
        categories: 可选的分类列表
        
    Returns:
        分类结果字典
    """
    client = get_ollama_client()
    return client.classify_image(image_path, categories)


def classify_text(text: str, categories: List[str] = None, category_descriptions: Dict[str, str] = None) -> Dict[str, Any]:
    """文本分类的便捷函数
    
    Args:
        text: 待分类的文本内容
        categories: 可选的分类列表
        category_descriptions: 可选的分类描述字典
        
    Returns:
        分类结果字典
    """
    client = get_ollama_client()
    return client.classify_text(text, categories, category_descriptions)


if __name__ == "__main__":
    client = get_ollama_client()
    
    print("检查Ollama服务状态...")
    if client.check_service_available():
        print("Ollama服务可用")
        print(f"可用模型: {client.list_models()}")
    else:
        print("Ollama服务不可用，请确保Ollama正在运行")
