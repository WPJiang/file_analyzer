import os
import sys
from typing import Optional, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QComboBox, QLabel, QFileDialog, QMenu, QAction,
    QProgressBar, QCompleter
)
from PyQt5.QtCore import Qt, pyqtSignal, QStringListModel
from PyQt5.QtGui import QIcon, QFont

from .utils import get_font_sizes, get_window_sizes, get_icon_sizes


class SearchPanel(QWidget):
    """搜索/输入组件"""

    search_requested = pyqtSignal(str)
    directory_changed = pyqtSignal(str)
    parse_requested = pyqtSignal()  # 文件解析信号
    semantic_represent_requested = pyqtSignal()  # 语义表征信号
    classify_requested = pyqtSignal()  # 分类信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_history = []
        self.max_history = 10
        self.font_sizes = get_font_sizes()
        self.icon_sizes = get_icon_sizes()
        self.window_sizes = get_window_sizes()

        self.init_ui()

    def init_ui(self):
        """初始化UI - 单行布局"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self.window_sizes['margin_normal'],
            self.window_sizes['margin_small'],
            self.window_sizes['margin_normal'],
            self.window_sizes['margin_small']
        )
        layout.setSpacing(self.window_sizes['spacing_normal'])

        # 搜索标签
        search_label = QLabel("🔍")
        search_label.setStyleSheet(f"font-size: {self.font_sizes['icon_medium']}px;")
        search_label.setToolTip("搜索")
        layout.addWidget(search_label)

        # 搜索输入框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索文件...")
        self.search_edit.setMinimumWidth(self.window_sizes['input_min_width'])
        self.search_edit.setMaximumWidth(self.window_sizes['input_max_width'])
        self.search_edit.setMinimumHeight(self.window_sizes['input_height'])
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 2px solid #ddd;
                border-radius: 4px;
                font-size: {self.font_sizes['normal']}px;
                background-color: white;
            }}
            QLineEdit:focus {{
                border-color: #2196F3;
            }}
        """)

        # 设置自动完成
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_edit.setCompleter(self.completer)

        self.search_edit.returnPressed.connect(self.on_search)
        layout.addWidget(self.search_edit)

        # 搜索按钮
        search_btn = QPushButton("搜索")
        search_btn.setMinimumHeight(self.window_sizes['button_height'])
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2196F3;
                color: white;
                padding: {self.window_sizes['button_padding_v']}px {self.window_sizes['button_padding_h']}px;
                border: none;
                border-radius: 4px;
                font-size: {self.font_sizes['button']}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
        """)
        search_btn.clicked.connect(self.on_search)
        layout.addWidget(search_btn)

        # 清除按钮
        clear_btn = QPushButton("✕")
        clear_btn.setToolTip("清除搜索")
        clear_btn.setMinimumHeight(self.window_sizes['button_height'])
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #f5f5f5;
                color: #666;
                padding: {self.window_sizes['button_padding_v']}px 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: {self.font_sizes['normal']}px;
            }}
            QPushButton:hover {{
                background-color: #e0e0e0;
            }}
        """)
        clear_btn.clicked.connect(self.clear_search)
        layout.addWidget(clear_btn)

        # 分隔线
        line2 = QLabel("|")
        line2.setStyleSheet(f"color: #ddd; font-size: {self.font_sizes['icon_medium']}px; margin: 0 5px;")
        layout.addWidget(line2)

        # 文件类型筛选
        self.type_combo = QComboBox()
        self.type_combo.addItem("全部", "")
        self.type_combo.addItem("文档", ".pdf,.doc,.docx")
        self.type_combo.addItem("图片", ".jpg,.jpeg,.png,.gif")
        self.type_combo.addItem("音频", ".mp3,.wav")
        self.type_combo.addItem("文本", ".txt,.md")
        self.type_combo.setMinimumHeight(self.window_sizes['input_height'])
        self.type_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 5px 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                min-width: 80px;
                font-size: {self.font_sizes['normal']}px;
            }}
            QComboBox:hover {{
                border-color: #2196F3;
            }}
        """)
        layout.addWidget(self.type_combo)

        # 搜索历史
        self.history_combo = QComboBox()
        self.history_combo.addItem("历史")
        self.history_combo.setMinimumHeight(self.window_sizes['input_height'])
        self.history_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 5px 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                min-width: 80px;
                font-size: {self.font_sizes['normal']}px;
            }}
        """)
        self.history_combo.currentIndexChanged.connect(self.on_history_selected)
        layout.addWidget(self.history_combo)

        # 分隔线
        line3 = QLabel("|")
        line3.setStyleSheet(f"color: #ddd; font-size: {self.font_sizes['icon_medium']}px; margin: 0 5px;")
        layout.addWidget(line3)

        # 文件解析按钮
        parse_btn = QPushButton("📄 解析")
        parse_btn.setToolTip("解析当前目录文件，生成数据块并保存到cache")
        parse_btn.setMinimumHeight(self.window_sizes['button_height'])
        parse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #00BCD4;
                color: white;
                padding: {self.window_sizes['button_padding_v']}px 20px;
                border: none;
                border-radius: 4px;
                font-size: {self.font_sizes['button']}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0097A7;
            }}
        """)
        parse_btn.clicked.connect(self.on_parse)
        layout.addWidget(parse_btn)

        # 语义表征按钮
        semantic_btn = QPushButton("🧠 语义表征")
        semantic_btn.setToolTip("对已解析文件生成语义表征")
        semantic_btn.setMinimumHeight(self.window_sizes['button_height'])
        semantic_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF9800;
                color: white;
                padding: {self.window_sizes['button_padding_v']}px 20px;
                border: none;
                border-radius: 4px;
                font-size: {self.font_sizes['button']}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #F57C00;
            }}
        """)
        semantic_btn.clicked.connect(self.on_semantic_represent)
        layout.addWidget(semantic_btn)

        # 分类按钮
        classify_btn = QPushButton("🏷 分类")
        classify_btn.setToolTip("使用选定的类别体系对文件进行分类")
        classify_btn.setMinimumHeight(self.window_sizes['button_height'])
        classify_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #9C27B0;
                color: white;
                padding: {self.window_sizes['button_padding_v']}px 20px;
                border: none;
                border-radius: 4px;
                font-size: {self.font_sizes['button']}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #7B1FA2;
            }}
        """)
        classify_btn.clicked.connect(self.on_classify)
        layout.addWidget(classify_btn)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(int(150 * (self.window_sizes['main_width'] / 1400)))
        self.progress_bar.setMinimumHeight(self.window_sizes['button_height'])
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                font-size: {self.font_sizes['small']}px;
            }}
            QProgressBar::chunk {{
                background-color: #4CAF50;
            }}
        """)
        layout.addWidget(self.progress_bar)

        layout.addStretch()

        # 设置样式
        self.setStyleSheet("""
            SearchPanel {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

    def on_parse(self):
        """触发文件解析"""
        self.parse_requested.emit()

    def on_semantic_represent(self):
        """触发语义表征"""
        self.semantic_represent_requested.emit()

    def on_classify(self):
        """触发分类"""
        self.classify_requested.emit()
    
    def show_progress(self, visible: bool = True):
        """显示/隐藏进度条"""
        self.progress_bar.setVisible(visible)
        if visible:
            self.progress_bar.setValue(0)
    
    def set_progress(self, value: int):
        """设置进度"""
        self.progress_bar.setValue(value)
    
    def on_search(self):
        """执行搜索"""
        query = self.search_edit.text().strip()
        if query:
            self.add_to_history(query)
            self.search_requested.emit(query)
    
    def clear_search(self):
        """清除搜索"""
        self.search_edit.clear()
        self.search_requested.emit("")
    
    def add_to_history(self, query: str):
        """添加到搜索历史"""
        if query in self.search_history:
            self.search_history.remove(query)
        
        self.search_history.insert(0, query)
        
        if len(self.search_history) > self.max_history:
            self.search_history = self.search_history[:self.max_history]
        
        self.update_history_ui()
    
    def update_history_ui(self):
        """更新历史UI"""
        model = QStringListModel(self.search_history)
        self.completer.setModel(model)
        
        self.history_combo.clear()
        self.history_combo.addItem("-- 选择历史记录 --")
        for query in self.search_history:
            self.history_combo.addItem(query)
    
    def on_history_selected(self, index: int):
        """选择历史记录"""
        if index > 0:
            query = self.history_combo.itemText(index)
            self.search_edit.setText(query)
            self.search_requested.emit(query)
            self.history_combo.setCurrentIndex(0)
    
    def set_directory(self, directory: str):
        """设置当前目录"""
        pass
    
    def get_directory(self) -> str:
        """获取当前目录"""
        return ""
    
    def get_search_query(self) -> str:
        """获取搜索关键词"""
        return self.search_edit.text().strip()
    
    def get_file_type_filter(self) -> str:
        """获取文件类型筛选"""
        return self.type_combo.currentData()
    
    def focus_search(self):
        """聚焦搜索框"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()
