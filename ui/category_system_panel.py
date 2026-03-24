"""类别体系管理面板

用于显示和管理类别体系，支持从目录结构自动获取类别。
"""

import os
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QMessageBox,
    QHeaderView, QMenu, QAction, QDialog, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon


class CategorySystem:
    """类别体系数据结构"""

    def __init__(self, name: str = "", categories: List[str] = None):
        self.name = name
        self.categories = categories or []
        self.id = id(self)  # 使用对象ID作为唯一标识

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "categories": self.categories
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CategorySystem':
        return cls(
            name=data.get("name", ""),
            categories=data.get("categories", [])
        )


class CategorySystemPanel(QWidget):
    """类别体系管理面板

    显示类别体系列表，支持添加、删除、重命名类别体系。
    """

    # 信号：选中的类别体系发生变化
    category_system_selected = pyqtSignal(object)  # CategorySystem

    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_systems: Dict[str, CategorySystem] = {}  # name -> CategorySystem
        self.current_system: Optional[CategorySystem] = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 头部区域
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("📁 类别体系")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 添加类别体系按钮
        add_btn = QPushButton("+")
        add_btn.setToolTip("添加类别体系")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        add_btn.clicked.connect(self.on_add_system)
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # 类别体系树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["类别体系", "类别数"])
        self.tree.setAnimated(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
        """)

        layout.addWidget(self.tree)

        # 状态标签
        self.status_label = QLabel("暂无类别体系")
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.setStyleSheet("""
            CategorySystemPanel {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

    def add_category_system(self, name: str, categories: List[str]) -> bool:
        """添加类别体系

        Args:
            name: 类别体系名称
            categories: 类别列表

        Returns:
            是否添加成功
        """
        if not name or not name.strip():
            QMessageBox.warning(self, "错误", "类别体系名称不能为空")
            return False

        if name in self.category_systems:
            QMessageBox.warning(self, "错误", f"类别体系 '{name}' 已存在")
            return False

        system = CategorySystem(name=name, categories=categories)
        self.category_systems[name] = system
        self.update_tree()
        return True

    def remove_category_system(self, name: str):
        """删除类别体系"""
        if name in self.category_systems:
            del self.category_systems[name]
            if self.current_system and self.current_system.name == name:
                self.current_system = None
            self.update_tree()

    def get_category_system(self, name: str) -> Optional[CategorySystem]:
        """获取指定的类别体系"""
        return self.category_systems.get(name)

    def get_all_category_systems(self) -> List[CategorySystem]:
        """获取所有类别体系"""
        return list(self.category_systems.values())

    def get_current_system(self) -> Optional[CategorySystem]:
        """获取当前选中的类别体系"""
        return self.current_system

    def update_tree(self):
        """更新树形显示"""
        self.tree.clear()

        if not self.category_systems:
            self.status_label.setText("暂无类别体系")
            return

        self.status_label.setText(f"共 {len(self.category_systems)} 个类别体系")

        for name, system in self.category_systems.items():
            # 创建类别体系节点
            system_item = QTreeWidgetItem(self.tree)
            system_item.setText(0, f"📁 {name}")
            system_item.setText(1, str(len(system.categories)))
            system_item.setData(0, Qt.UserRole, "system")
            system_item.setData(0, Qt.UserRole + 1, name)

            font = system_item.font(0)
            font.setBold(True)
            system_item.setFont(0, font)

            # 如果是当前选中的，高亮显示
            if self.current_system and self.current_system.name == name:
                system_item.setForeground(0, QColor("#2196F3"))

            # 添加类别子节点
            for category in system.categories:
                cat_item = QTreeWidgetItem(system_item)
                cat_item.setText(0, f"📂 {category}")
                cat_item.setData(0, Qt.UserRole, "category")
                cat_item.setData(0, Qt.UserRole + 1, category)

        self.tree.expandAll()

    def on_add_system(self):
        """添加类别体系"""
        name, ok = QLineEdit.getText(self, "新建类别体系", "请输入类别体系名称:")
        if ok and name:
            self.add_category_system(name, [])

    def on_item_clicked(self, item, column):
        """单击项目"""
        item_type = item.data(0, Qt.UserRole)

        if item_type == "system":
            name = item.data(0, Qt.UserRole + 1)
            self.current_system = self.category_systems.get(name)
            self.update_tree()  # 更新高亮
            self.category_system_selected.emit(self.current_system)

    def on_item_double_clicked(self, item, column):
        """双击项目 - 重命名"""
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

                self.update_tree()

    def show_context_menu(self, pos):
        """显示右键菜单"""
        item = self.tree.itemAt(pos)
        if not item:
            return

        item_type = item.data(0, Qt.UserRole)

        menu = QMenu(self)

        if item_type == "system":
            name = item.data(0, Qt.UserRole + 1)

            rename_action = QAction("重命名", self)
            rename_action.triggered.connect(lambda: self.on_item_double_clicked(item, 0))
            menu.addAction(rename_action)

            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self.confirm_delete(name))
            menu.addAction(delete_action)

        menu.exec_(self.tree.mapToGlobal(pos))

    def confirm_delete(self, name: str):
        """确认删除"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除类别体系 '{name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.remove_category_system(name)


class CategorySystemSelectDialog(QDialog):
    """类别体系选择对话框"""

    def __init__(self, category_systems: List[CategorySystem], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择类别体系")
        self.setMinimumWidth(300)

        self.selected_system: Optional[CategorySystem] = None
        self.category_systems = category_systems

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 提示标签
        label = QLabel("请选择要使用的类别体系:")
        label.setStyleSheet("font-size: 12px;")
        layout.addWidget(label)

        # 类别体系下拉框
        self.combo = QComboBox()
        self.combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
            }
        """)

        for system in self.category_systems:
            self.combo.addItem(f"{system.name} ({len(system.categories)}个类别)", system.name)

        layout.addWidget(self.combo)

        # 预览区域
        preview_label = QLabel("类别预览:")
        preview_label.setStyleSheet("font-size: 12px; margin-top: 10px;")
        layout.addWidget(preview_label)

        self.preview_text = QLabel()
        self.preview_text.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        self.preview_text.setWordWrap(True)
        layout.addWidget(self.preview_text)

        self.combo.currentIndexChanged.connect(self.update_preview)
        if self.category_systems:
            self.update_preview(0)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                padding: 8px 20px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        ok_btn.clicked.connect(self.on_accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def update_preview(self, index):
        """更新预览"""
        if index < 0 or index >= len(self.category_systems):
            return

        system = self.category_systems[index]
        categories_text = "、".join(system.categories[:10])
        if len(system.categories) > 10:
            categories_text += f"... 等{len(system.categories)}个类别"
        self.preview_text.setText(categories_text)

    def on_accept(self):
        """确定按钮"""
        index = self.combo.currentIndex()
        if index >= 0 and index < len(self.category_systems):
            self.selected_system = self.category_systems[index]
            self.accept()

    def get_selected_system(self) -> Optional[CategorySystem]:
        """获取选中的类别体系"""
        return self.selected_system