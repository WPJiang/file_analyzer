# -*- coding: utf-8 -*-
"""设置对话框模块"""

import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QPushButton, QScrollArea, QWidget, QGroupBox, QFormLayout,
    QRadioButton, QButtonGroup, QMessageBox, QTabWidget, QStackedWidget,
    QLineEdit
)
from PyQt5.QtCore import Qt


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, config_path: str, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.config = {}
        self.api_config = {}  # 云侧API配置
        self.load_config()

        self.setWindowTitle("设置")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)

        self.init_ui()

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = {}
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.config = {}

        # 加载 api_config.json
        self._load_api_config()

    def _load_api_config(self):
        """加载云侧API配置文件"""
        config_dir = os.path.dirname(self.config_path)
        config_file = self.config.get('llm', {}).get('cloud', {}).get('config_file', 'api_config.json')
        api_config_path = os.path.join(config_dir, config_file)

        if os.path.exists(api_config_path):
            try:
                with open(api_config_path, 'r', encoding='utf-8') as f:
                    self.api_config = json.load(f)
            except Exception as e:
                print(f"加载API配置失败: {e}")
                self.api_config = {}
        else:
            self.api_config = {}

    def _save_api_config(self):
        """保存云侧API配置文件"""
        config_dir = os.path.dirname(self.config_path)
        config_file = self.config.get('llm', {}).get('cloud', {}).get('config_file', 'api_config.json')
        api_config_path = os.path.join(config_dir, config_file)

        try:
            with open(api_config_path, 'w', encoding='utf-8') as f:
                json.dump(self.api_config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存API配置失败: {e}")
            return False

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)

        # 使用标签页
        tab_widget = QTabWidget()

        # LLM设置标签页
        llm_tab = self.create_llm_tab()
        tab_widget.addTab(llm_tab, "LLM设置")

        # 图片处理设置标签页
        image_tab = self.create_image_tab()
        tab_widget.addTab(image_tab, "图片处理")

        # 语义分析设置标签页
        semantic_tab = self.create_semantic_tab()
        tab_widget.addTab(semantic_tab, "语义分析")

        layout.addWidget(tab_widget)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.on_save)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def create_llm_tab(self) -> QWidget:
        """创建LLM设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # LLM类型选择
        type_group = QGroupBox("LLM类型")
        type_layout = QHBoxLayout(type_group)

        self.llm_type_buttons = QButtonGroup(type_group)
        llm_types = [
            ('local_llama', '本地llama.cpp'),
            ('ollama', 'Ollama服务'),
            ('cloud', '云侧API')
        ]

        current_type = self.config.get('llm', {}).get('type', 'local_llama')

        for i, (type_val, type_name) in enumerate(llm_types):
            rb = QRadioButton(type_name)
            rb.setProperty('type_value', type_val)
            if type_val == current_type:
                rb.setChecked(True)
            self.llm_type_buttons.addButton(rb, i)
            type_layout.addWidget(rb)

        # 连接信号，切换显示对应的配置
        self.llm_type_buttons.buttonClicked.connect(self._on_llm_type_changed)

        layout.addWidget(type_group)

        # 使用 QStackedWidget 来切换显示不同的配置面板
        self.llm_config_stack = QStackedWidget()

        # 创建三个配置面板
        local_panel = self._create_local_llama_panel()
        ollama_panel = self._create_ollama_panel()
        cloud_panel = self._create_cloud_panel()

        self.llm_config_stack.addWidget(local_panel)   # index 0
        self.llm_config_stack.addWidget(ollama_panel)  # index 1
        self.llm_config_stack.addWidget(cloud_panel)   # index 2

        layout.addWidget(self.llm_config_stack)

        # 根据当前类型设置显示
        type_index_map = {'local_llama': 0, 'ollama': 1, 'cloud': 2}
        self.llm_config_stack.setCurrentIndex(type_index_map.get(current_type, 0))

        layout.addStretch()
        return widget

    def _on_llm_type_changed(self, button):
        """LLM类型改变时切换配置面板"""
        type_value = button.property('type_value')
        type_index_map = {'local_llama': 0, 'ollama': 1, 'cloud': 2}
        self.llm_config_stack.setCurrentIndex(type_index_map.get(type_value, 0))

    def _create_local_llama_panel(self) -> QWidget:
        """创建本地llama.cpp配置面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        group = QGroupBox("本地llama.cpp设置")
        form_layout = QFormLayout(group)

        self.local_url_combo = QComboBox()
        self.local_url_combo.setEditable(True)
        self.local_url_combo.addItems(['http://127.0.0.1:11435/v1', 'http://localhost:11435/v1'])
        self.local_url_combo.setCurrentText(
            self.config.get('llm', {}).get('local_llama', {}).get('base_url', 'http://127.0.0.1:11435/v1')
        )
        form_layout.addRow("服务地址:", self.local_url_combo)

        self.local_model_combo = QComboBox()
        self.local_model_combo.setEditable(True)
        self.local_model_combo.addItems(['qwen3.5-0.8b', 'qwen3-7b', 'llava'])
        self.local_model_combo.setCurrentText(
            self.config.get('llm', {}).get('local_llama', {}).get('model', 'qwen3.5-0.8b')
        )
        form_layout.addRow("模型名称:", self.local_model_combo)

        self.local_timeout = QSpinBox()
        self.local_timeout.setRange(30, 600)
        self.local_timeout.setValue(
            self.config.get('llm', {}).get('local_llama', {}).get('timeout', 300)
        )
        form_layout.addRow("超时时间(秒):", self.local_timeout)

        self.local_max_tokens = QSpinBox()
        self.local_max_tokens.setRange(256, 32768)
        self.local_max_tokens.setValue(
            self.config.get('llm', {}).get('local_llama', {}).get('max_tokens', 2048)
        )
        form_layout.addRow("最大Token:", self.local_max_tokens)

        layout.addWidget(group)
        layout.addStretch()
        return panel

    def _create_ollama_panel(self) -> QWidget:
        """创建Ollama配置面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        group = QGroupBox("Ollama设置")
        form_layout = QFormLayout(group)

        self.ollama_url_combo = QComboBox()
        self.ollama_url_combo.setEditable(True)
        self.ollama_url_combo.addItems(['http://localhost:11434', 'http://127.0.0.1:11434'])
        self.ollama_url_combo.setCurrentText(
            self.config.get('llm', {}).get('ollama', {}).get('base_url', 'http://localhost:11434')
        )
        form_layout.addRow("服务地址:", self.ollama_url_combo)

        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setEditable(True)
        self.ollama_model_combo.addItems(['qwen3.5:0.8b', 'llava', 'llava:13b'])
        self.ollama_model_combo.setCurrentText(
            self.config.get('llm', {}).get('ollama', {}).get('model', 'qwen3.5:0.8b')
        )
        form_layout.addRow("模型名称:", self.ollama_model_combo)

        layout.addWidget(group)
        layout.addStretch()
        return panel

    def _create_cloud_panel(self) -> QWidget:
        """创建云侧API配置面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        group = QGroupBox("云侧API设置")
        form_layout = QFormLayout(group)

        # API Key输入 - 从api_config.json读取
        self.cloud_api_key_edit = QComboBox()
        self.cloud_api_key_edit.setEditable(True)
        self.cloud_api_key_edit.setCurrentText(
            self.api_config.get('api_key', '')
        )
        self.cloud_api_key_edit.lineEdit().setEchoMode(
            self.cloud_api_key_edit.lineEdit().Password
        )
        form_layout.addRow("API Key:", self.cloud_api_key_edit)

        self.cloud_url_combo = QComboBox()
        self.cloud_url_combo.setEditable(True)
        self.cloud_url_combo.addItems([
            'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'https://open.bigmodel.cn/api/paas/v4',
            'https://api.deepseek.com/v1'
        ])
        self.cloud_url_combo.setCurrentText(
            self.api_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        )
        form_layout.addRow("API地址:", self.cloud_url_combo)

        self.cloud_model_combo = QComboBox()
        self.cloud_model_combo.setEditable(True)
        self.cloud_model_combo.addItems([
            'qwen3-vl-32b-thinking',
            'qwen-vl-plus',
            'qwen-vl-max',
            'gpt-4o',
            'gpt-4o-mini'
        ])
        self.cloud_model_combo.setCurrentText(
            self.api_config.get('model', 'qwen-vl-plus')
        )
        form_layout.addRow("模型名称:", self.cloud_model_combo)

        self.cloud_vision_model_combo = QComboBox()
        self.cloud_vision_model_combo.setEditable(True)
        self.cloud_vision_model_combo.addItems([
            'qwen3-vl-32b-thinking',
            'qwen-vl-plus',
            'qwen-vl-max',
            'gpt-4o'
        ])
        self.cloud_vision_model_combo.setCurrentText(
            self.api_config.get('vision_model', 'qwen-vl-plus')
        )
        form_layout.addRow("视觉模型:", self.cloud_vision_model_combo)

        self.cloud_timeout = QSpinBox()
        self.cloud_timeout.setRange(30, 300)
        self.cloud_timeout.setValue(
            self.api_config.get('timeout', 120)
        )
        form_layout.addRow("超时时间(秒):", self.cloud_timeout)

        self.cloud_max_tokens = QSpinBox()
        self.cloud_max_tokens.setRange(256, 32768)
        self.cloud_max_tokens.setValue(
            min(self.api_config.get('max_tokens', 4096), 32768)
        )
        form_layout.addRow("最大Token:", self.cloud_max_tokens)

        layout.addWidget(group)
        layout.addStretch()
        return panel

    def create_image_tab(self) -> QWidget:
        """创建图片处理设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 图片缩放设置
        resize_group = QGroupBox("图片缩放设置")
        resize_layout = QFormLayout(resize_group)

        self.max_dimension_combo = QComboBox()
        self.max_dimension_combo.addItems([
            '224 (快速处理)',
            '448 (平衡模式)',
            '896 (高质量)'
        ])
        # 根据配置选择
        current_dim = self.config.get('image_processing', {}).get('max_dimension', 448)
        dim_map = {224: 0, 448: 1, 896: 2}
        self.max_dimension_combo.setCurrentIndex(dim_map.get(current_dim, 1))
        resize_layout.addRow("图片缩放尺寸:", self.max_dimension_combo)

        layout.addWidget(resize_group)

        # OCR设置
        ocr_group = QGroupBox("OCR设置")
        ocr_layout = QFormLayout(ocr_group)

        self.ocr_width = QSpinBox()
        self.ocr_width.setRange(0, 3000)
        self.ocr_width.setValue(
            self.config.get('semantic_representation', {}).get('image', {}).get('ocr_max_image_width', 1500)
        )
        self.ocr_width.setSpecialValueText("不缩放")
        ocr_layout.addRow("OCR最大宽度:", self.ocr_width)

        layout.addWidget(ocr_group)

        layout.addStretch()
        return widget

    def create_semantic_tab(self) -> QWidget:
        """创建语义分析设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 分类方法设置
        classify_group = QGroupBox("分类方法")
        classify_layout = QVBoxLayout(classify_group)

        self.classify_buttons = QButtonGroup(classify_group)
        classify_methods = [
            ('similarity', '相似度分类'),
            ('clustering', '聚类分类'),
            ('llm', 'LLM分类')
        ]

        current_method = self.config.get('classification', {}).get('method', 'similarity')

        for i, (method_val, method_name) in enumerate(classify_methods):
            rb = QRadioButton(method_name)
            rb.setProperty('method_value', method_val)
            if method_val == current_method:
                rb.setChecked(True)
            self.classify_buttons.addButton(rb, i)
            classify_layout.addWidget(rb)

        layout.addWidget(classify_group)

        # Embedding模型设置
        embedding_group = QGroupBox("Embedding模型")
        embedding_layout = QFormLayout(embedding_group)

        self.embedding_combo = QComboBox()
        self.embedding_combo.addItems([
            'paraphrase-multilingual-MiniLM-L12-v2',
            'paraphrase-multilingual-MiniLM-L6-v2'
        ])
        self.embedding_combo.setCurrentText(
            self.config.get('semantic_representation', {}).get('embedding', {}).get('model_name', 'paraphrase-multilingual-MiniLM-L12-v2')
        )
        embedding_layout.addRow("模型选择:", self.embedding_combo)

        layout.addWidget(embedding_group)

        # 查询设置
        query_group = QGroupBox("查询设置")
        query_layout = QFormLayout(query_group)

        self.top_k = QSpinBox()
        self.top_k.setRange(1, 50)
        self.top_k.setValue(
            self.config.get('query', {}).get('top_k', 10)
        )
        query_layout.addRow("检索语义块数量(Top K):", self.top_k)

        self.top_m = QSpinBox()
        self.top_m.setRange(1, 20)
        self.top_m.setValue(
            self.config.get('query', {}).get('top_m', 5)
        )
        query_layout.addRow("返回文件数量(Top M):", self.top_m)

        layout.addWidget(query_group)

        layout.addStretch()
        return widget

    def on_save(self):
        """保存设置"""
        # 更新配置
        if 'llm' not in self.config:
            self.config['llm'] = {}
        if 'local_llama' not in self.config['llm']:
            self.config['llm']['local_llama'] = {}
        if 'cloud' not in self.config['llm']:
            self.config['llm']['cloud'] = {}
        if 'ollama' not in self.config['llm']:
            self.config['llm']['ollama'] = {}
        if 'image_processing' not in self.config:
            self.config['image_processing'] = {}
        if 'classification' not in self.config:
            self.config['classification'] = {}
        if 'semantic_representation' not in self.config:
            self.config['semantic_representation'] = {'image': {}, 'embedding': {}}
        if 'query' not in self.config:
            self.config['query'] = {}

        # LLM类型
        checked_btn = self.llm_type_buttons.checkedButton()
        if checked_btn:
            self.config['llm']['type'] = checked_btn.property('type_value')

        # 本地LLM设置
        self.config['llm']['local_llama']['base_url'] = self.local_url_combo.currentText()
        self.config['llm']['local_llama']['model'] = self.local_model_combo.currentText()
        self.config['llm']['local_llama']['timeout'] = self.local_timeout.value()
        self.config['llm']['local_llama']['max_tokens'] = self.local_max_tokens.value()

        # 云侧API设置 - 保存到api_config.json
        self.api_config['api_key'] = self.cloud_api_key_edit.currentText()
        self.api_config['base_url'] = self.cloud_url_combo.currentText()
        self.api_config['model'] = self.cloud_model_combo.currentText()
        self.api_config['vision_model'] = self.cloud_vision_model_combo.currentText()
        self.api_config['timeout'] = self.cloud_timeout.value()
        self.api_config['max_tokens'] = self.cloud_max_tokens.value()

        # Ollama设置
        self.config['llm']['ollama']['base_url'] = self.ollama_url_combo.currentText()
        self.config['llm']['ollama']['model'] = self.ollama_model_combo.currentText()

        # 图片处理设置
        dim_text = self.max_dimension_combo.currentText()
        dim_map = {'224': 224, '448': 448, '896': 896}
        for key, val in dim_map.items():
            if key in dim_text:
                self.config['image_processing']['max_dimension'] = val
                break

        # OCR设置
        if 'image' not in self.config['semantic_representation']:
            self.config['semantic_representation']['image'] = {}
        self.config['semantic_representation']['image']['ocr_max_image_width'] = self.ocr_width.value()

        # 分类方法
        checked_method = self.classify_buttons.checkedButton()
        if checked_method:
            self.config['classification']['method'] = checked_method.property('method_value')

        # Embedding模型
        if 'embedding' not in self.config['semantic_representation']:
            self.config['semantic_representation']['embedding'] = {}
        self.config['semantic_representation']['embedding']['model_name'] = self.embedding_combo.currentText()

        # 查询设置
        self.config['query']['top_k'] = self.top_k.value()
        self.config['query']['top_m'] = self.top_m.value()

        # 保存主配置文件
        if not self.save_config():
            QMessageBox.warning(self, "错误", "保存主配置文件失败。")
            return

        # 保存云侧API配置文件
        if not self._save_api_config():
            QMessageBox.warning(self, "错误", "保存API配置文件失败。")
            return

        QMessageBox.information(self, "成功", "设置已保存，部分设置需要重启生效。")
        self.accept()