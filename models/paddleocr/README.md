# PaddleOCR 模型文件

此目录用于存放PaddleOCR模型文件，支持本地加载模式。

## 目录结构

```
paddleocr/
├── det/                              # 文本检测模型
│   └── ch_PP-OCRv4_det_infer/
│       ├── inference.pdmodel
│       ├── inference.pdiparams
│       └── inference.pdiparams.info
├── rec/                              # 文本识别模型
│   └── ch_PP-OCRv4_rec_infer/
│       ├── inference.pdmodel
│       ├── inference.pdiparams
│       └── inference.pdiparams.info
└── cls/                              # 文本方向分类模型
    └── ch_ppocr_mobile_v2.0_cls_infer/
        ├── inference.pdmodel
        ├── inference.pdiparams
        └── inference.pdiparams.info
```

## 模型获取方式

### 方式一：自动下载（推荐）

首次运行程序时，如果此目录为空，系统会自动从网络下载模型，并保存到此目录。

### 方式二：手动下载

1. 从PaddleOCR官方下载模型：
   - 检测模型: https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar
   - 识别模型: https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar
   - 分类模型: https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar

2. 解压后按照上述目录结构放置

### 方式三：从已下载的模型复制

如果之前运行过程序，模型可能已下载到 `~/.paddleocr/whl/` 目录，
可以将该目录下的模型文件复制到本目录。

## 配置说明

在 `config.json` 中可以配置：
- `ocr_model_path`: 指定OCR模型路径（留空则自动查找）

## 注意事项

- 模型文件总大小约 50-100MB
- 使用本地模型可以避免每次运行时联网下载
- 打包发布时建议包含此目录以支持离线运行