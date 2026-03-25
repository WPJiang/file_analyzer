import requests

url = "http://127.0.0.1:11435/v1/chat/completions"

data = {
    "model": "qwen3.5-0.8b",
    "messages": [
        {"role": "user", "content": "你好！请介绍一下自己"}
    ],
    "stream": True
}

# 流式输出
with requests.post(url, json=data, stream=True) as resp:
    for line in resp.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk != "[DONE]":
                    import json
                    obj = json.loads(chunk)
                    content = obj["choices"][0]["delta"].get("content", "")
                    print(content, end="", flush=True)