# -*- coding: utf-8 -*-
"""UI工具函数 - 提供自适应缩放支持"""

from PyQt5.QtWidgets import QApplication


def get_scale_factor() -> float:
    """获取屏幕缩放因子

    以1920x1080为基准计算缩放因子，支持高分辨率显示器。

    Returns:
        缩放因子，范围0.8到2.5
    """
    screen = QApplication.primaryScreen()
    if screen:
        geometry = screen.geometry()
        screen_width = geometry.width()

        # 以1920为基准
        base_width = 1920
        scale_factor = screen_width / base_width

        # 限制缩放范围
        return max(0.8, min(2.5, scale_factor))

    return 1.0


def scale_font_size(base_size: int) -> int:
    """根据屏幕分辨率缩放字体大小

    Args:
        base_size: 基础字体大小（针对1920x1080）

    Returns:
        缩放后的字体大小
    """
    scale_factor = get_scale_factor()
    return max(8, int(base_size * scale_factor))


def scale_size(base_size: int) -> int:
    """根据屏幕分辨率缩放尺寸

    Args:
        base_size: 基础尺寸（针对1920x1080）

    Returns:
        缩放后的尺寸
    """
    scale_factor = get_scale_factor()
    return max(1, int(base_size * scale_factor))


def get_font_sizes() -> dict:
    """获取预定义的字体大小配置

    Returns:
        包含各层级字体大小的字典
    """
    scale_factor = get_scale_factor()

    return {
        'title': max(12, int(14 * scale_factor)),      # 标题字体
        'normal': max(10, int(12 * scale_factor)),      # 正常字体
        'small': max(9, int(10 * scale_factor)),        # 小字体
        'tree': max(10, int(11 * scale_factor)),        # 树形控件字体
        'button': max(10, int(11 * scale_factor)),      # 按钮字体
        'icon_small': max(16, int(20 * scale_factor)),  # 小图标字体
        'icon_medium': max(20, int(24 * scale_factor)), # 中等图标字体
        'icon_large': max(48, int(64 * scale_factor)),  # 大图标字体
    }


def get_icon_sizes() -> dict:
    """获取预定义的图标大小配置

    Returns:
        包含各层级图标大小的字典（像素）
    """
    scale_factor = get_scale_factor()

    return {
        'tiny': max(12, int(16 * scale_factor)),       # 极小图标
        'small': max(16, int(20 * scale_factor)),      # 小图标
        'medium': max(24, int(28 * scale_factor)),     # 中等图标
        'large': max(32, int(40 * scale_factor)),      # 大图标
        'xlarge': max(48, int(56 * scale_factor)),     # 超大图标
        'huge': max(64, int(80 * scale_factor)),       # 巨大图标
    }


def get_window_sizes() -> dict:
    """获取预定义的窗口大小配置

    Returns:
        包含各类窗口大小的字典（像素）
    """
    scale_factor = get_scale_factor()

    return {
        # 主窗口
        'main_width': max(1200, int(1400 * scale_factor)),
        'main_height': max(800, int(900 * scale_factor)),
        # 对话框
        'dialog_width': max(500, int(600 * scale_factor)),
        'dialog_height': max(400, int(500 * scale_factor)),
        'settings_width': max(600, int(700 * scale_factor)),
        'settings_height': max(500, int(600 * scale_factor)),
        # 面板宽度
        'panel_min_width': max(200, int(250 * scale_factor)),
        'panel_max_width': max(350, int(400 * scale_factor)),
        'preview_min_width': max(400, int(500 * scale_factor)),
        # 按钮尺寸
        'button_height': max(28, int(32 * scale_factor)),
        'button_padding_h': max(6, int(8 * scale_factor)),
        'button_padding_v': max(4, int(6 * scale_factor)),
        # 输入框
        'input_height': max(28, int(32 * scale_factor)),
        'input_min_width': max(150, int(200 * scale_factor)),
        'input_max_width': max(300, int(400 * scale_factor)),
        # 间距
        'spacing_small': max(4, int(5 * scale_factor)),
        'spacing_normal': max(8, int(10 * scale_factor)),
        'spacing_large': max(12, int(15 * scale_factor)),
        'margin_small': max(5, int(6 * scale_factor)),
        'margin_normal': max(8, int(10 * scale_factor)),
        'margin_large': max(12, int(15 * scale_factor)),
    }


def get_scaled_stylesheet(template: str) -> str:
    """将样式表模板中的字体大小进行缩放

    支持 {font_title}, {font_normal}, {font_small} 等占位符

    Args:
        template: 样式表模板字符串

    Returns:
        缩放后的样式表
    """
    font_sizes = get_font_sizes()

    result = template
    result = result.replace('{font_title}', str(font_sizes['title']))
    result = result.replace('{font_normal}', str(font_sizes['normal']))
    result = result.replace('{font_small}', str(font_sizes['small']))
    result = result.replace('{font_tree}', str(font_sizes['tree']))
    result = result.replace('{font_button}', str(font_sizes['button']))

    return result