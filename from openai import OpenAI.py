from openai import OpenAI
import os
from typing import List, Dict, Optional

class OpenAIChatClient:
    """OpenAI 接口调用客户端，支持单次问答、多轮对话、流式响应"""
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions",  # 官方域名，国内平台替换为对应域名
        model: str = "glm-4.7",  # 模型名称（gpt-4/gpt-3.5-turbo/自定义模型）
        temperature: float = 0.7,      # 生成随机性（0-2，越低越精准）
        max_tokens: int = 65536         # 最大生成 Token 数
    ):
        # 初始化客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url  # 国内平台需替换，如智谱：https://open.bigmodel.cn/api/paas/v4
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        # 维护多轮对话上下文
        self.chat_history: List[Dict[str, str]] = []

    def single_chat(self, question: str, stream: bool = False) -> str:
        """
        单次问答（无上下文）
        :param question: 用户提问内容
        :param stream: 是否开启流式响应（实时输出）
        :return: 模型回复内容
        """
        # 构造对话消息（仅包含当前提问）
        messages = [{"role": "user", "content": question}]
        
        if stream:
            # 流式响应（实时打印，类似打字机效果）
            full_answer = ""
            print("=== 模型回复（流式）===")
            stream_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True  # 开启流式
            )
            for chunk in stream_response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    print(content, end="", flush=True)
            print("\n")
            return full_answer
        else:
            # 同步响应（一次性返回结果）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False
            )
            answer = response.choices[0].message.content
            return answer

    def multi_chat(self, question: str, stream: bool = False) -> str:
        """
        多轮对话（自动维护上下文）
        :param question: 本轮用户提问
        :param stream: 是否开启流式响应
        :return: 模型回复内容
        """
        # 将本轮提问加入上下文
        self.chat_history.append({"role": "user", "content": question})
        
        if stream:
            full_answer = ""
            print("=== 模型回复（流式）===")
            stream_response = self.client.chat.completions.create(
                model=self.model,
                messages=self.chat_history,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            for chunk in stream_response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    print(content, end="", flush=True)
            print("\n")
            # 将模型回复加入上下文
            self.chat_history.append({"role": "assistant", "content": full_answer})
            return full_answer
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.chat_history,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False
            )
            answer = response.choices[0].message.content
            # 将模型回复加入上下文
            self.chat_history.append({"role": "assistant", "content": answer})
            return answer

    def clear_history(self) -> None:
        """清空多轮对话上下文"""
        self.chat_history = []

    def close(self) -> None:
        """关闭客户端连接（释放资源）"""
        self.client.close()

# ---------------------- 测试用例 ----------------------
if __name__ == "__main__":
    # 1. 配置参数（替换为你的实际信息）
    API_KEY = "54d9b6b997a44211b21c05a7f63b0889.cqkGpYlP3CmIJ209"  # 推荐通过环境变量配置
    # 国内平台示例：智谱 GLM-4（兼容 OpenAI 协议）
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    MODEL = "glm-4.7"
    # 官方平台
    # BASE_URL = "https://api.openai.com/v1"
    # MODEL = "gpt-3.5-turbo"

    # 2. 初始化客户端
    client = OpenAIChatClient(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL,
        temperature=0.7,
        max_tokens=2048
    )

    try:
        # 场景1：单次问答（同步响应）
        print("===== 单次问答（同步） =====")
        single_question = "用Python实现QThread多线程，给出核心代码示例"
        single_answer = client.single_chat(single_question)
        print(f"提问：{single_question}\n回复：{single_answer}\n")

        # 场景2：单次问答（流式响应）
        print("===== 单次问答（流式） =====")
        stream_question = "详细解释QThread中moveToThread的用法和避坑点"
        client.single_chat(stream_question, stream=True)

        # 场景3：多轮对话（同步响应）
        print("\n===== 多轮对话 =====")
        multi_q1 = "什么是Token？OpenAI的计费方式是怎样的？"
        multi_a1 = client.multi_chat(multi_q1)
        print(f"提问1：{multi_q1}\n回复1：{multi_a1}\n")

        multi_q2 = "如何优化Token使用，降低调用成本？"
        multi_a2 = client.multi_chat(multi_q2)
        print(f"提问2：{multi_q2}\n回复2：{multi_a2}\n")

        # 清空上下文（可选）
        client.clear_history()

    except Exception as e:
        print(f"接口调用失败：{str(e)}")
    finally:
        # 关闭客户端
        client.close()