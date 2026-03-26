# File Analyzer - 文件分析管理器

## 项目简介

File Analyzer 是一个多功能文件分析管理工具，支持多种文件格式（PPT、Word、PDF、图片、音频等）的解析、语义分析和智能分类。通过 GUI 界面提供直观的文件管理和分析功能。

### 主要功能

- **多格式文件解析**：支持 PDF、Word、PPT、图片（JPG/PNG/GIF/HEIC 等）、音频等格式
- **语义表征**：将文件内容转化为统一的语义表示（文本描述、关键词、语义向量）
- **语义搜索**：基于自然语言描述搜索相关文件
- **智能分类**：基于预定义类别或自动生成的类别进行文件分类
- **图片分析**：
  - 时空元数据提取（拍摄时间、GPS 位置）
  - Caption 和标签生成（基于 LLM）
- **多 LLM 后端支持**：本地 llama.cpp、Ollama、云侧 API

## 快速开始

### 环境要求

- Python 3.10
- Conda（推荐）

### 安装步骤

1. **创建虚拟环境**

```bash
conda create -n file_analyzer python=3.10
conda activate file_analyzer
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置云侧 API（可选）**

如需使用云侧 LLM 功能，复制配置模板并填入 API Key：

```bash
cp api_config_example.json api_config.json
# 编辑 api_config.json，填入您的 API Key
```

### 启动程序

**主程序入口**：`ui/main_window.py`

```bash
# 方式一：直接运行启动脚本
python simple_launch.py

# 方式二：作为模块运行
python -c "from ui.main_window import MainWindow; from PyQt5.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); w = MainWindow(); w.show(); sys.exit(app.exec_())"
```

## GUI 界面说明

### 界面布局

程序采用三栏布局：

| 区域 | 功能 |
|------|------|
| **左侧 - 推荐面板** | 显示相似文件推荐，基于当前选中文件进行语义相似度匹配 |
| **中间 - 预览面板** | 文件内容预览，支持文本、图片、PDF 等多种格式预览 |
| **右侧 - 分类面板** | 三个子标签页：类别体系、分类结果、搜索功能 |

### 顶部工具栏

工具栏提供以下操作按钮：

| 按钮 | 功能 |
|------|------|
| **目录选择** | 选择要扫描的文件夹 |
| **解析** | 解析选中目录中的文件，提取文本内容 |
| **语义表征** | 生成语义向量、关键词、描述文本 |
| **分类** | 将文件分类到预定义类别中 |

### 菜单栏

#### 文件菜单

| 菜单项 | 快捷键 | 功能 |
|--------|--------|------|
| 打开目录... | Ctrl+O | 选择并扫描目录 |
| 扫描默认目录 | Ctrl+D | 扫描预设的默认目录 |
| 退出 | Ctrl+Q | 退出程序 |

#### 工具菜单

| 菜单项 | 功能 |
|--------|------|
| 自动获取预定义类别 | 从目录结构自动生成分类类别 |
| 图片时空数据分析 | 提取图片的拍摄时间、GPS 位置等元数据 |
| 图片 Caption 和标签生成 | 使用 LLM 为图片生成描述和标签 |
| 清空历史分析 | 清空所有分析数据 |
| 清空历史分析(仅保留类别体系) | 清空分析数据但保留类别定义 |
| 清空历史分类结果 | 仅清空分类结果 |

#### 设置菜单

| 菜单项 | 快捷键 | 功能 |
|--------|--------|------|
| 系统设置... | Ctrl+, | 打开设置对话框 |

### 设置对话框

#### LLM 设置

选择 LLM 后端类型：

1. **本地 llama.cpp**：连接本地 llama.cpp 服务器
   - 服务地址：默认 `http://127.0.0.1:11435/v1`
   - 模型名称：如 `qwen3.5-0.8b`

2. **Ollama 服务**：连接本地 Ollama
   - 服务地址：默认 `http://localhost:11434`
   - 模型名称：如 `qwen3.5:0.8b`

3. **云侧 API**：使用云服务商 API
   - API Key：您的 API 密钥
   - API 地址：如阿里云 `https://dashscope.aliyuncs.com/compatible-mode/v1`
   - 模型名称：如 `qwen-vl-plus`

#### 图片处理设置

- 图片缩放尺寸：224（快速）/ 448（平衡）/ 896（高质量）
- OCR 最大宽度：控制 OCR 处理时的图片缩放

#### 语义分析设置

- 分类方法：相似度分类 / 聚类分类 / LLM 分类
- Embedding 模型选择
- 检索参数（Top K、Top M）

### 操作流程

1. **扫描目录**：点击"打开目录"选择包含文件的文件夹
2. **解析文件**：点击"解析"按钮提取文件内容
3. **语义表征**：点击"语义表征"生成语义向量
4. **分类文件**：点击"分类"将文件归类
5. **搜索文件**：在搜索框输入自然语言描述，搜索相关文件

## Windows 打包指南

### 方式一：使用 PyInstaller

1. **安装 PyInstaller**

```bash
pip install pyinstaller
```

2. **打包命令**

```bash
pyinstaller --name "文件分析管理器" ^
    --windowed ^
    --onefile ^
    --add-data "config.json;." ^
    --add-data "api_config_example.json;." ^
    --hidden-import=torch ^
    --hidden-import=transformers ^
    --hidden-import=sentence_transformers ^
    --collect-all paddleocr ^
    --collect-all paddlepaddle ^
    simple_launch.py
```

3. **输出位置**

打包完成后，可执行文件位于 `dist/文件分析管理器.exe`

### 方式二：使用 PyInstaller（目录模式，推荐）

目录模式启动更快，便于调试：

```bash
pyinstaller --name "文件分析管理器" ^
    --windowed ^
    --add-data "config.json;." ^
    --add-data "api_config_example.json;." ^
    --hidden-import=torch ^
    --hidden-import=transformers ^
    --hidden-import=sentence_transformers ^
    --collect-all paddleocr ^
    --collect-all paddlepaddle ^
    simple_launch.py
```

输出目录：`dist/文件分析管理器/`

### 方式三：使用 Nuitka（更小体积）

```bash
pip install nuitka

python -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --enable-plugin=pyqt5 ^
    --include-data-file=config.json=. ^
    --include-data-file=api_config_example.json=. ^
    simple_launch.py
```

### 打包注意事项

1. **配置文件**：确保 `config.json` 和 `api_config_example.json` 打包到可执行文件同目录

2. **首次运行**：打包后首次运行需要复制 `api_config_example.json` 为 `api_config.json` 并配置 API Key

3. **大模型处理**：PaddleOCR 和 Sentence-Transformers 模型较大，首次加载较慢

4. **排除敏感文件**：确保 `api_config.json` 已添加到 `.gitignore`，不要打包真实的 API Key

5. **依赖问题**：如遇到模块导入错误，使用 `--hidden-import` 添加隐藏导入

## 配置说明

### 云侧 API 配置

配置文件：`api_config.json`（不提交到 Git）

```json
{
    "api_key": "your-api-key-here",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-vl-plus",
    "vision_model": "qwen-vl-max",
    "timeout": 120,
    "max_tokens": 4096,
    "temperature": 0.7
}
```

**支持的云服务商**：

| 服务商 | API 地址 |
|--------|----------|
| 阿里云通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` |
| DeepSeek | `https://api.deepseek.com/v1` |

### 主配置文件

配置文件：`config.json`

```json
{
    "llm": {
        "type": "cloud",
        "cloud": {
            "config_file": "api_config.json"
        }
    },
    "image_processing": {
        "max_dimension": 448
    },
    "classification": {
        "method": "similarity"
    }
}
```

## 项目结构

```
file_analyzer/
├── ui/                     # GUI 界面模块
│   ├── main_window.py      # 主窗口（程序入口）
│   ├── preview_panel.py    # 预览面板
│   ├── search_panel.py     # 搜索面板
│   ├── classification_panel.py
│   ├── recommendation_panel.py
│   └── settings_dialog.py  # 设置对话框
├── database/               # 数据库模块
├── data_parser/            # 文件解析模块
├── semantic_representation/ # 语义表征模块
├── models/                 # LLM 模型客户端
├── directory_scanner/      # 目录扫描模块
├── config.json             # 主配置文件
├── api_config.json         # API 配置（不提交）
├── api_config_example.json # API 配置示例
├── simple_launch.py        # 启动脚本
└── requirements.txt        # 依赖列表
```

## 依赖说明

主要依赖包（详见 requirements.txt）：

| 包名 | 用途 |
|------|------|
| PyQt5 | GUI 界面 |
| sentence-transformers | 语义向量生成 |
| pdfplumber | PDF 解析 |
| python-docx | Word 解析 |
| python-pptx | PPT 解析 |
| Pillow | 图片处理 |
| paddleocr | OCR 识别 |
| exifread | EXIF 元数据提取 |
| openai | OpenAI 兼容 API 客户端 |

## 许可证

本项目采用 MIT 许可证。