#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""简化版启动脚本"""

import sys
import os

if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
    internal_path = os.path.join(base_path, '_internal')
    if os.path.exists(internal_path):
        sys.path.insert(0, internal_path)
    sys.path.insert(0, base_path)
else:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, base_path)

from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

# 高DPI支持
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

app = QApplication(sys.argv)
app.setApplicationName("文件分析管理器")
app.setStyle('Fusion')

# 导入UI工具模块
try:
    from ui.utils import get_scale_factor, get_font_sizes, get_window_sizes
except ImportError:
    # 开发环境路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ui.utils import get_scale_factor, get_font_sizes, get_window_sizes

# 打印屏幕信息
screen = app.primaryScreen()
if screen:
    geometry = screen.geometry()
    scale_factor = get_scale_factor()
    font_sizes = get_font_sizes()
    window_sizes = get_window_sizes()

    print(f"[UI] 屏幕分辨率: {geometry.width()}x{geometry.height()}")
    print(f"[UI] 缩放因子: {scale_factor:.2f}")
    print(f"[UI] 基础字体大小: {font_sizes['normal']}")
    print(f"[UI] 主窗口大小: {window_sizes['main_width']}x{window_sizes['main_height']}")

# 设置应用程序字体
font = QFont("Microsoft YaHei", font_sizes['normal'])
app.setFont(font)

try:
    from ui.main_window import MainWindow
    window = MainWindow()
except Exception as e:
    import traceback
    traceback.print_exc()
    window = QMainWindow()
    window.setWindowTitle("测试")
    label = QLabel(f"测试成功！\n错误: {str(e)}", window)
    label.setGeometry(50, 50, 400, 100)
    window.resize(500, 200)

window.show()
sys.exit(app.exec_())