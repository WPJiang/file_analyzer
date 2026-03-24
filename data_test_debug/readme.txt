测试数据目录说明
================

请将测试文件放入此目录，用于 data_parser 模块的单元测试。

支持的测试文件类型：

1. PDF 文件 (.pdf)
   - test.pdf
   - sample.pdf

2. Word 文件 (.docx, .doc)
   - test.docx
   - test.doc

3. PPT 文件 (.pptx, .ppt)
   - test.pptx
   - test.ppt

4. 图片文件 (.jpg, .jpeg, .png, .gif, .bmp)
   - test.jpg
   - test.png

5. 文本文件 (.txt, .md)
   - test.txt
   - test.md

6. 音频文件 (.mp3, .wav)
   - test.mp3
   - test.wav

测试方法：
1. 将测试文件放入此目录
2. 运行测试: python tests/test_data_parser.py
   或使用 pytest: python -m pytest tests/test_data_parser.py -v
