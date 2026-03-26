import os
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QPushButton, QHeaderView, QMenu, QAction, QStackedWidget,
    QMessageBox, QLineEdit, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QScreen

from .utils import get_font_sizes, get_window_sizes, get_icon_sizes


class CategorySystem:
    """类别体系数据结构"""

    def __init__(self, name: str = "", categories: List[str] = None,
                 category_info: Dict[str, Dict[str, Any]] = None):
        self.name = name
        self.categories = categories or []
        # category_info: {类别名: {"description": "描述", "keywords": ["关键词"]}}
        self.category_info = category_info or {}
        self.id = id(self)  # 使用对象ID作为唯一标识

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "categories": self.categories,
            "category_info": self.category_info
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CategorySystem':
        return cls(
            name=data.get("name", ""),
            categories=data.get("categories", []),
            category_info=data.get("category_info", {})
        )


class ClassificationPanel(QWidget):
    """右侧面板：支持类别体系、分类结果、搜索三种模式切换"""

    file_selected = pyqtSignal(str)
    category_system_changed = pyqtSignal(object)  # CategorySystem

    CATEGORY_ICONS = {
        "技术文档": "📄",
        "商业报告": "📊",
        "学术论文": "📚",
        "会议演示": "📽",
        "合同协议": "📋",
        "产品说明": "📖",
        "新闻资讯": "📰",
        "个人文档": "👤",
        "未分类": "❓",
    }

    CATEGORY_COLORS = {
        "技术文档": "#2196F3",
        "商业报告": "#4CAF50",
        "学术论文": "#9C27B0",
        "会议演示": "#FF9800",
        "合同协议": "#F44336",
        "产品说明": "#00BCD4",
        "新闻资讯": "#795548",
        "个人文档": "#607D8B",
        "未分类": "#9E9E9E",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_systems: Dict[str, CategorySystem] = {}  # name -> CategorySystem
        self.current_system: Optional[CategorySystem] = None
        self.classification_results = {}
        self.search_results = None
        self.current_mode = "category_system"  # "category_system", "classification", "search"
        self.db_manager = None  # 数据库管理器，用于保存类别体系

        # 计算自适应字体大小
        self.font_sizes = get_font_sizes()
        self.icon_sizes = get_icon_sizes()
        self.window_sizes = get_window_sizes()

        self.init_ui()

    def set_db_manager(self, db_manager):
        """设置数据库管理器"""
        self.db_manager = db_manager

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.window_sizes['spacing_small'])

        # 头部区域
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(
            self.window_sizes['margin_small'],
            self.window_sizes['margin_small'],
            self.window_sizes['margin_small'],
            self.window_sizes['margin_small']
        )

        self.title_label = QLabel("📁 类别体系")
        self.title_label.setStyleSheet(f"font-weight: bold; font-size: {self.font_sizes['title']}px;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # 保存类别体系按钮（替换原来的加号按钮）
        btn_size = self.icon_sizes['small']
        self.save_system_btn = QPushButton("💾")
        self.save_system_btn.setToolTip("保存所有类别体系到数据库")
        self.save_system_btn.setFixedSize(btn_size, btn_size)
        self.save_system_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: {btn_size // 2}px;
                font-size: {self.font_sizes['title']}px;
            }}
            QPushButton:hover {{
                background-color: #F57C00;
            }}
        """)
        self.save_system_btn.clicked.connect(self.on_save_systems)
        header_layout.addWidget(self.save_system_btn)

        # 功能切换按钮（替换原来的搜索按钮）
        self.mode_btn = QPushButton("功能切换")
        self.mode_btn.setMinimumHeight(self.window_sizes['button_height'])
        self.mode_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: {self.font_sizes['button']}px;
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
        """)
        self.mode_btn.clicked.connect(self.toggle_mode)
        header_layout.addWidget(self.mode_btn)

        header_layout.addSpacing(self.window_sizes['spacing_normal'])

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: #666; font-size: {self.font_sizes['small']}px;")
        header_layout.addWidget(self.count_label)

        layout.addWidget(header)

        # 创建堆叠窗口用于切换显示
        self.stacked_widget = QStackedWidget()

        # 类别体系树
        self.category_system_tree = QTreeWidget()
        self.category_system_tree.setHeaderLabels(["类别体系", "类别数"])
        self.category_system_tree.setAnimated(True)
        self.category_system_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.category_system_tree.customContextMenuRequested.connect(self.show_category_system_context_menu)
        self.category_system_tree.itemClicked.connect(self.on_category_system_item_clicked)
        self.category_system_tree.itemDoubleClicked.connect(self.on_category_system_item_double_clicked)

        header = self.category_system_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.category_system_tree.setStyleSheet(self._get_tree_style())

        # 分类结果树
        self.classification_tree = QTreeWidget()
        self.classification_tree.setHeaderLabels(["分类/文件", "置信度"])
        self.classification_tree.setAnimated(True)
        self.classification_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.classification_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.classification_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.classification_tree.itemClicked.connect(self.on_item_clicked)

        header = self.classification_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.classification_tree.setStyleSheet(self._get_tree_style())

        # 搜索结果树
        self.search_tree = QTreeWidget()
        self.search_tree.setHeaderLabels(["文件", "相似度"])
        self.search_tree.setAnimated(True)
        self.search_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.search_tree.customContextMenuRequested.connect(self.show_search_context_menu)
        self.search_tree.itemDoubleClicked.connect(self.on_search_item_double_clicked)
        self.search_tree.itemClicked.connect(self.on_search_item_clicked)

        header2 = self.search_tree.header()
        header2.setSectionResizeMode(0, QHeaderView.Stretch)
        header2.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.search_tree.setStyleSheet(self._get_tree_style())

        self.stacked_widget.addWidget(self.category_system_tree)
        self.stacked_widget.addWidget(self.classification_tree)
        self.stacked_widget.addWidget(self.search_tree)

        layout.addWidget(self.stacked_widget)

        # 引用当前显示的树
        self.tree = self.category_system_tree

        self.setStyleSheet("""
            ClassificationPanel {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

    def _get_tree_style(self) -> str:
        """获取树形控件样式"""
        return f"""
            QTreeWidget {{
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: {self.font_sizes['tree']}px;
            }}
            QTreeWidget::item {{
                padding: 5px;
            }}
            QTreeWidget::item:hover {{
                background-color: #f5f5f5;
            }}
            QTreeWidget::item:selected {{
                background-color: #e3f2fd;
                color: #1976D2;
            }}
        """

    # ==================== 类别体系管理 ====================

    def add_category_system(self, name: str, categories: List[str],
                            category_info: Dict[str, Dict[str, Any]] = None) -> bool:
        """添加类别体系

        Args:
            name: 类别体系名称
            categories: 类别名称列表
            category_info: 类别信息字典，格式为 {类别名: {"description": "描述", "keywords": ["关键词"]}}

        Returns:
            是否添加成功
        """
        if not name or not name.strip():
            QMessageBox.warning(self, "错误", "类别体系名称不能为空")
            return False

        if name in self.category_systems:
            QMessageBox.warning(self, "错误", f"类别体系 '{name}' 已存在")
            return False

        system = CategorySystem(name=name, categories=categories, category_info=category_info or {})
        self.category_systems[name] = system

        # 如果是第一个体系，自动选中
        if len(self.category_systems) == 1:
            self.current_system = system
            self.category_system_changed.emit(system)

        self.update_category_system_tree()
        return True

    def remove_category_system(self, name: str):
        """删除类别体系"""
        if name in self.category_systems:
            del self.category_systems[name]
            if self.current_system and self.current_system.name == name:
                # 选中下一个可用的体系
                remaining = list(self.category_systems.values())
                self.current_system = remaining[0] if remaining else None
                self.category_system_changed.emit(self.current_system)
            self.update_category_system_tree()

    def clear_category_systems(self):
        """清空所有类别体系"""
        self.category_systems.clear()
        self.current_system = None
        self.category_system_changed.emit(None)
        self.update_category_system_tree()

    def get_category_system(self, name: str) -> Optional[CategorySystem]:
        """获取指定的类别体系"""
        return self.category_systems.get(name)

    def get_all_category_systems(self) -> List[CategorySystem]:
        """获取所有类别体系"""
        return list(self.category_systems.values())

    def get_current_system(self) -> Optional[CategorySystem]:
        """获取当前选中的类别体系"""
        return self.current_system

    def update_category_system_tree(self):
        """更新类别体系树形显示"""
        self.category_system_tree.clear()

        if not self.category_systems:
            self.count_label.setText("暂无类别体系")
            return

        self.count_label.setText(f"共 {len(self.category_systems)} 个体系")

        for name, system in self.category_systems.items():
            # 创建类别体系节点
            system_item = QTreeWidgetItem(self.category_system_tree)
            system_item.setText(0, f"📁 {name}")
            system_item.setText(1, str(len(system.categories)))
            system_item.setData(0, Qt.UserRole, "system")
            system_item.setData(0, Qt.UserRole + 1, name)

            font = system_item.font(0)
            font.setBold(True)
            system_item.setFont(0, font)

            # 如果是当前选中的，高亮显示并展开
            is_current = self.current_system and self.current_system.name == name
            if is_current:
                system_item.setForeground(0, QColor("#2196F3"))
                self.category_system_tree.expandItem(system_item)

            # 添加类别子节点
            for category in system.categories:
                cat_item = QTreeWidgetItem(system_item)
                cat_item.setText(0, f"📂 {category}")
                cat_item.setData(0, Qt.UserRole, "category")
                cat_item.setData(0, Qt.UserRole + 1, category)

    def on_save_systems(self):
        """保存所有类别体系到数据库"""
        if not self.db_manager:
            QMessageBox.warning(self, "错误", "数据库管理器未初始化")
            return

        if not self.category_systems:
            QMessageBox.warning(self, "提示", "没有类别体系需要保存")
            return

        saved_count = 0
        total_categories = 0

        try:
            for name, system in self.category_systems.items():
                # 保存每个类别到语义类别表
                for category in system.categories:
                    # 获取类别的描述和关键词
                    cat_info = system.category_info.get(category, {})
                    description = cat_info.get("description", f"{category}相关文件")
                    keywords = cat_info.get("keywords", [])

                    self.db_manager.add_semantic_category(
                        category_name=category,
                        description=description,
                        keywords=keywords,
                        category_system_name=name
                    )
                    total_categories += 1
                saved_count += 1

            QMessageBox.information(
                self, "保存成功",
                f"已保存 {saved_count} 个类别体系，\n共 {total_categories} 个类别到数据库。"
            )
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存类别体系时出错：{str(e)}")

    def on_category_system_item_clicked(self, item, column):
        """单击类别体系项目"""
        item_type = item.data(0, Qt.UserRole)

        if item_type == "system":
            name = item.data(0, Qt.UserRole + 1)
            self.current_system = self.category_systems.get(name)
            self.update_category_system_tree()
            self.category_system_changed.emit(self.current_system)

    def on_category_system_item_double_clicked(self, item, column):
        """双击类别体系项目 - 重命名"""
        item_type = item.data(0, Qt.UserRole)

        if item_type == "system":
            old_name = item.data(0, Qt.UserRole + 1)
            new_name, ok = QLineEdit.getText(self, "重命名", "请输入新名称:", text=old_name)
            if ok and new_name and new_name != old_name:
                if new_name in self.category_systems:
                    QMessageBox.warning(self, "错误", f"类别体系 '{new_name}' 已存在")
                    return

                system = self.category_systems.pop(old_name)
                system.name = new_name
                self.category_systems[new_name] = system

                if self.current_system and self.current_system.name == old_name:
                    self.current_system = system

                self.update_category_system_tree()

    def show_category_system_context_menu(self, pos):
        """显示类别体系右键菜单"""
        item = self.category_system_tree.itemAt(pos)
        if not item:
            return

        item_type = item.data(0, Qt.UserRole)

        menu = QMenu(self)

        if item_type == "system":
            name = item.data(0, Qt.UserRole + 1)

            rename_action = QAction("重命名", self)
            rename_action.triggered.connect(lambda: self.on_category_system_item_double_clicked(item, 0))
            menu.addAction(rename_action)

            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self.confirm_delete_system(name))
            menu.addAction(delete_action)

        menu.exec_(self.category_system_tree.mapToGlobal(pos))

    def confirm_delete_system(self, name: str):
        """确认删除类别体系"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除类别体系 '{name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 先从内存中删除
            self.remove_category_system(name)
            # 再从数据库中删除
            if self.db_manager:
                self.db_manager.delete_category_system(name)

    # ==================== 模式切换 ====================

    def toggle_mode(self):
        """切换显示模式 - 显示菜单选择"""
        menu = QMenu(self)
        menu.setStyleSheet(f"font-size: {self.font_sizes['normal']}px;")

        # 类别体系选项
        cat_action = QAction("📁 类别体系", self)
        cat_action.triggered.connect(self.set_category_system_mode)
        if self.current_mode == "category_system":
            cat_action.setCheckable(True)
            cat_action.setChecked(True)
        menu.addAction(cat_action)

        # 分类结果选项
        class_action = QAction("📊 分类结果", self)
        class_action.triggered.connect(self.set_classification_mode)
        if self.current_mode == "classification":
            class_action.setCheckable(True)
            class_action.setChecked(True)
        menu.addAction(class_action)

        # 搜索选项
        search_action = QAction("🔍 搜索", self)
        search_action.triggered.connect(self.set_search_mode)
        if self.current_mode == "search":
            search_action.setCheckable(True)
            search_action.setChecked(True)
        menu.addAction(search_action)

        # 显示菜单
        menu.exec_(self.mode_btn.mapToGlobal(self.mode_btn.rect().bottomLeft()))

    def set_category_system_mode(self):
        """切换到类别体系模式"""
        self.current_mode = "category_system"
        self.title_label.setText("📁 类别体系")
        self.stacked_widget.setCurrentIndex(0)
        self.tree = self.category_system_tree
        self.save_system_btn.setVisible(True)
        self.update_category_system_tree()

    def set_classification_mode(self):
        """切换到分类结果模式"""
        self.current_mode = "classification"
        self.title_label.setText("📊 分类结果")
        self.stacked_widget.setCurrentIndex(1)
        self.tree = self.classification_tree
        self.save_system_btn.setVisible(False)
        self.update_classification_tree()

    def set_search_mode(self):
        """切换到搜索结果模式"""
        self.current_mode = "search"
        self.title_label.setText("🔍 搜索结果")
        self.stacked_widget.setCurrentIndex(2)
        self.tree = self.search_tree
        self.save_system_btn.setVisible(False)
        self.update_search_tree()

    # ==================== 分类结果 ====================

    def set_classification_results(self, results: Dict[str, List[Dict[str, Any]]]):
        """设置分类结果并自动切换到分类结果模式"""
        self.classification_results = results
        self.set_classification_mode()

    def update_classification_tree(self):
        """更新分类结果树形显示"""
        self.classification_tree.clear()

        if not self.classification_results:
            self.count_label.setText("暂无分类结果")
            return

        total_files = sum(len(files) for files in self.classification_results.values())
        self.count_label.setText(f"共 {total_files} 个文件")

        sorted_categories = sorted(
            self.classification_results.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        for category, files in sorted_categories:
            category_item = QTreeWidgetItem(self.classification_tree)

            icon = self.CATEGORY_ICONS.get(category, "📁")
            color = self.CATEGORY_COLORS.get(category, "#666666")

            category_item.setText(0, f"{icon} {category}")
            category_item.setText(1, str(len(files)))
            category_item.setData(0, Qt.UserRole, "category")
            category_item.setData(0, Qt.UserRole + 1, category)

            category_item.setForeground(0, QColor(color))
            font = category_item.font(0)
            font.setBold(True)
            category_item.setFont(0, font)

            for file_info in files:
                file_item = QTreeWidgetItem(category_item)

                file_name = os.path.basename(file_info.get('path', '未知文件'))
                confidence = file_info.get('primary_confidence', 0)
                categories = file_info.get('categories', [])
                total_blocks = file_info.get('total_blocks', 0)

                file_item.setText(0, file_name)
                file_item.setText(1, f"{confidence:.0%}")
                file_item.setData(0, Qt.UserRole, "file")
                file_item.setData(0, Qt.UserRole + 1, file_info.get('path', ''))

                tooltip_parts = [file_info.get('path', '')]
                tooltip_parts.append(f"\n共 {total_blocks} 个语义块")
                tooltip_parts.append("\n类别分布:")
                for cat_info in categories:
                    tooltip_parts.append(f"  • {cat_info['category']}: {cat_info['confidence']:.1%} ({cat_info['block_count']}块)")
                file_item.setToolTip(0, '\n'.join(tooltip_parts))

                if confidence >= 0.8:
                    file_item.setForeground(1, QColor("#4CAF50"))
                elif confidence >= 0.5:
                    file_item.setForeground(1, QColor("#FF9800"))
                else:
                    file_item.setForeground(1, QColor("#F44336"))

        self.classification_tree.expandAll()

    def show_context_menu(self, pos):
        """显示分类结果右键菜单"""
        item = self.classification_tree.itemAt(pos)
        if not item:
            return

        item_type = item.data(0, Qt.UserRole)

        menu = QMenu(self)

        if item_type == "file":
            file_path = item.data(0, Qt.UserRole + 1)

            open_action = QAction("打开文件", self)
            open_action.triggered.connect(lambda: self.open_file(file_path))
            menu.addAction(open_action)

            open_folder_action = QAction("打开所在文件夹", self)
            open_folder_action.triggered.connect(lambda: self.open_folder(file_path))
            menu.addAction(open_folder_action)

            menu.addSeparator()

            copy_action = QAction("复制路径", self)
            copy_action.triggered.connect(lambda: self.copy_path(file_path))
            menu.addAction(copy_action)

        elif item_type == "category":
            category = item.data(0, Qt.UserRole + 1)

            expand_action = QAction("展开", self)
            expand_action.triggered.connect(lambda: self.classification_tree.expandItem(item))
            menu.addAction(expand_action)

            collapse_action = QAction("折叠", self)
            collapse_action.triggered.connect(lambda: self.classification_tree.collapseItem(item))
            menu.addAction(collapse_action)

        menu.exec_(self.classification_tree.mapToGlobal(pos))

    def on_item_clicked(self, item, column):
        """单击分类结果项目"""
        item_type = item.data(0, Qt.UserRole)

        if item_type == "file":
            file_path = item.data(0, Qt.UserRole + 1)
            self.file_selected.emit(file_path)

    def on_item_double_clicked(self, item, column):
        """双击分类结果项目"""
        item_type = item.data(0, Qt.UserRole)

        if item_type == "file":
            file_path = item.data(0, Qt.UserRole + 1)
            self.file_selected.emit(file_path)

    # ==================== 搜索结果 ====================

    def set_search_results(self, search_results):
        """设置搜索结果"""
        self.search_results = search_results
        if search_results and search_results.files:
            self.set_search_mode()
        else:
            if self.current_mode == "search":
                self.update_search_tree()

    def update_search_tree(self):
        """更新搜索结果显示"""
        self.search_tree.clear()

        if not self.search_results or not self.search_results.files:
            self.count_label.setText("共 0 个文件")
            if self.current_mode == "search":
                item = QTreeWidgetItem(self.search_tree)
                item.setText(0, "请输入搜索内容或执行搜索")
                item.setForeground(0, QColor("#999"))
            return

        query_text = self.search_results.query_text
        total_files = len(self.search_results.files)
        self.count_label.setText(f"查询: '{query_text}' | 共 {total_files} 个文件")

        query_item = QTreeWidgetItem(self.search_tree)
        query_item.setText(0, f"🔍 查询: {query_text}")
        query_item.setText(1, f"{total_files}个结果")
        font = query_item.font(0)
        font.setBold(True)
        query_item.setFont(0, font)
        query_item.setForeground(0, QColor("#2196F3"))

        for file_result in self.search_results.files:
            file_item = QTreeWidgetItem(query_item)

            file_name = os.path.basename(file_result.file_path)
            similarity = file_result.similarity_score

            file_item.setText(0, f"📄 {file_name}")
            file_item.setText(1, f"{similarity:.1%}")
            file_item.setData(0, Qt.UserRole, "search_file")
            file_item.setData(0, Qt.UserRole + 1, file_result.file_path)

            tooltip_parts = [file_result.file_path]
            tooltip_parts.append(f"\n相似度: {similarity:.2%}")
            if file_result.matched_blocks:
                tooltip_parts.append(f"\n匹配的语义块: {len(file_result.matched_blocks)}个")
                for block in file_result.matched_blocks[:3]:
                    tooltip_parts.append(f"  • {block.text_description[:50]}...")
            file_item.setToolTip(0, '\n'.join(tooltip_parts))

            if similarity >= 0.8:
                file_item.setForeground(1, QColor("#4CAF50"))
            elif similarity >= 0.5:
                file_item.setForeground(1, QColor("#FF9800"))
            else:
                file_item.setForeground(1, QColor("#F44336"))

        self.search_tree.expandAll()

    def show_search_context_menu(self, pos):
        """显示搜索结果的右键菜单"""
        item = self.search_tree.itemAt(pos)
        if not item:
            return

        item_type = item.data(0, Qt.UserRole)

        menu = QMenu(self)

        if item_type == "search_file":
            file_path = item.data(0, Qt.UserRole + 1)

            open_action = QAction("打开文件", self)
            open_action.triggered.connect(lambda: self.open_file(file_path))
            menu.addAction(open_action)

            open_folder_action = QAction("打开所在文件夹", self)
            open_folder_action.triggered.connect(lambda: self.open_folder(file_path))
            menu.addAction(open_folder_action)

            menu.addSeparator()

            copy_action = QAction("复制路径", self)
            copy_action.triggered.connect(lambda: self.copy_path(file_path))
            menu.addAction(copy_action)

        menu.exec_(self.search_tree.mapToGlobal(pos))

    def on_search_item_clicked(self, item, column):
        """单击搜索结果项目"""
        item_type = item.data(0, Qt.UserRole)

        if item_type == "search_file":
            file_path = item.data(0, Qt.UserRole + 1)
            self.file_selected.emit(file_path)

    def on_search_item_double_clicked(self, item, column):
        """双击搜索结果项目"""
        item_type = item.data(0, Qt.UserRole)

        if item_type == "search_file":
            file_path = item.data(0, Qt.UserRole + 1)
            self.file_selected.emit(file_path)

    # ==================== 通用方法 ====================

    def open_file(self, file_path: str):
        """打开文件"""
        if os.path.exists(file_path):
            os.startfile(file_path)

    def open_folder(self, file_path: str):
        """打开所在文件夹"""
        if os.path.exists(file_path):
            folder = os.path.dirname(file_path)
            os.startfile(folder)

    def copy_path(self, file_path: str):
        """复制路径"""
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(file_path)

    def get_files_by_category(self, category: str) -> List[str]:
        """获取指定分类的文件列表"""
        files = self.classification_results.get(category, [])
        return [f.get('path', '') for f in files]

    def get_all_files(self) -> List[str]:
        """获取所有文件列表"""
        all_files = []
        for files in self.classification_results.values():
            all_files.extend([f.get('path', '') for f in files])
        return all_files

    def clear_results(self):
        """清空结果"""
        self.classification_results = {}
        self.classification_tree.clear()
        self.count_label.setText("")

    def show_classification_results_for_system(self, db_manager, category_system_name: str):
        """显示指定类别体系的分类结果

        从数据库加载所有已分类文件，并显示在当前类别体系下的分类结果。

        Args:
            db_manager: 数据库管理器
            category_system_name: 类别体系名称
        """
        if not db_manager:
            return

        from database import FileStatus

        # 获取所有已完成初步分析的文件
        all_files = db_manager.get_files_by_status(FileStatus.PRELIMINARY)

        # 按当前类别体系的分类结果分组
        results = {}
        total_classified = 0

        for file_record in all_files:
            semantic_categories = file_record.semantic_categories or []

            # 筛选当前类别体系的结果
            current_system_cats = [
                cat for cat in semantic_categories
                if cat.get('category_system_name') == category_system_name
            ]

            if not current_system_cats:
                continue

            total_classified += 1

            # 获取主要分类（置信度最高的）
            current_system_cats.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            primary_category = current_system_cats[0]['category'] if current_system_cats else '未分类'

            # 添加到结果中
            if primary_category not in results:
                results[primary_category] = []

            results[primary_category].append({
                'path': file_record.file_path,
                'categories': current_system_cats,
                'primary_category': primary_category,
                'primary_confidence': current_system_cats[0].get('confidence', 0) if current_system_cats else 0,
                'total_blocks': len(semantic_categories),
                'category_system_name': category_system_name
            })

        # 更新分类结果并切换到分类结果模式
        if results:
            self.classification_results = results
            self.set_classification_mode()
        else:
            # 没有分类结果，显示提示
            self.count_label.setText(f"'{category_system_name}' 类别体系暂无分类结果")