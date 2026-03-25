import os
import sys
import json
import gc  # 方案C：添加垃圾回收模块
from typing import Optional, List, Dict, Any
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QAction,
    QMessageBox, QFileDialog, QApplication, QToolBar,
    QLabel, QPushButton, QComboBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QKeySequence

# 导入日志模块
try:
    from ..logger import processing_logger
except ImportError:
    try:
        from logger import processing_logger
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from logger import processing_logger

# 导入性能监控模块
try:
    from ..performance_monitor import get_performance_monitor
except ImportError:
    try:
        from performance_monitor import get_performance_monitor
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from performance_monitor import get_performance_monitor

# 处理相对导入
try:
    from .preview_panel import PreviewPanel
    from .recommendation_panel import RecommendationPanel
    from .search_panel import SearchPanel
    from .classification_panel import ClassificationPanel
    from ..directory_scanner import DirectoryScanner
except ImportError:
    try:
        from preview_panel import PreviewPanel
        from recommendation_panel import RecommendationPanel
        from search_panel import SearchPanel
        from classification_panel import ClassificationPanel
        from directory_scanner import DirectoryScanner
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from ui.preview_panel import PreviewPanel
        from ui.recommendation_panel import RecommendationPanel
        from ui.search_panel import SearchPanel
        from ui.classification_panel import ClassificationPanel
        from directory_scanner.directory_scanner import DirectoryScanner

# 导入模型管理器（用于内存优化）
try:
    from models.model_manager import aggressive_cleanup
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models.model_manager import aggressive_cleanup


class ParseWorker(QThread):
    """文件解析工作线程"""
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self._is_cancelled = False
        self.pending_files = []

    def set_pending_files(self, files: List[str]):
        self.pending_files = files

    def cancel(self):
        self._is_cancelled = True

    def _load_config(self) -> dict:
        """加载配置文件"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            config_path = os.path.join(base_dir, 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载配置文件失败: {e}")
            internal_path = os.path.join(base_dir, '_internal', 'config.json')
            if os.path.exists(internal_path):
                try:
                    with open(internal_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载_internal配置文件失败: {e}")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载配置文件失败: {e}")
        return {}

    def run(self):
        """执行文件解析"""
        print("[DEBUG] ParseWorker.run() 开始执行")
        from database import FileStatus

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)

        try:
            config = self._load_config()
        except Exception as e:
            self.error.emit(f"配置加载失败: {str(e)}")
            return

        # 初始化DataParser
        try:
            from data_parser import DataParser
            data_parser = DataParser(config)
        except ImportError as e:
            self.error.emit(f"无法加载解析模块: {str(e)}")
            return

        results = {}
        files_to_parse = self.pending_files
        total = len(files_to_parse)
        processed = 0

        print(f"[DEBUG] 开始解析 {total} 个文件")

        for file_path in files_to_parse:
            if self._is_cancelled:
                self.error.emit("解析已取消")
                return

            try:
                self.progress.emit(f"解析: {os.path.basename(file_path)}", int(100 * processed / total))

                # 获取文件ID
                file_id = None
                if self.db_manager:
                    file_record = self.db_manager.get_file_by_path(file_path)
                    if file_record:
                        file_id = file_record.id

                # 解析文件
                blocks = data_parser.parse_file(file_path, self.db_manager, file_id)
                print(f"[DEBUG] 文件 {os.path.basename(file_path)} 解析出 {len(blocks) if blocks else 0} 个数据块")

                # 更新文件状态为PARSED
                if self.db_manager and file_id:
                    self.db_manager.update_file_status(file_id, FileStatus.PARSED)

                results[file_path] = {
                    'blocks_count': len(blocks) if blocks else 0,
                    'success': True
                }

            except Exception as e:
                print(f"[DEBUG] 解析文件失败 {file_path}: {e}")
                results[file_path] = {
                    'blocks_count': 0,
                    'success': False,
                    'error': str(e)
                }

            processed += 1
            gc.collect()

        self.progress.emit("解析完成", 100)
        self.finished.emit(results)


class SemanticRepresentWorker(QThread):
    """语义表征工作线程"""
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self._is_cancelled = False
        self.pending_files = []

    def set_pending_files(self, files: List[str]):
        self.pending_files = files

    def cancel(self):
        self._is_cancelled = True

    def _load_config(self) -> dict:
        """加载配置文件"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            config_path = os.path.join(base_dir, 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载配置文件失败: {e}")
            internal_path = os.path.join(base_dir, '_internal', 'config.json')
            if os.path.exists(internal_path):
                try:
                    with open(internal_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载_internal配置文件失败: {e}")
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载配置文件失败: {e}")
        return {}

    def run(self):
        """执行语义表征"""
        print("[DEBUG] SemanticRepresentWorker.run() 开始执行")
        from database import FileStatus

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)

        try:
            config = self._load_config()
        except Exception as e:
            self.error.emit(f"配置加载失败: {str(e)}")
            return

        # 初始化SemanticRepresentation
        try:
            from semantic_representation import SemanticRepresentation
            semantic_rep = SemanticRepresentation(config)
        except ImportError as e:
            self.error.emit(f"无法加载语义表征模块: {str(e)}")
            return

        results = {}
        files_to_process = self.pending_files
        total = len(files_to_process)
        processed = 0

        print(f"[DEBUG] 开始语义表征 {total} 个文件")

        for file_path in files_to_process:
            if self._is_cancelled:
                self.error.emit("语义表征已取消")
                return

            try:
                self.progress.emit(f"语义表征: {os.path.basename(file_path)}", int(100 * processed / total))

                # 获取文件ID和数据块
                file_id = None
                if self.db_manager:
                    file_record = self.db_manager.get_file_by_path(file_path)
                    if file_record:
                        file_id = file_record.id

                if not file_id:
                    processed += 1
                    continue

                # 获取数据块
                data_blocks = self.db_manager.get_data_blocks_by_file(file_id)

                # 生成语义表征
                semantic_blocks = []
                for block_record in data_blocks:
                    # 从数据库记录创建DataBlock对象
                    from data_parser import DataBlock, ModalityType
                    block = DataBlock(
                        block_id=block_record.block_id,
                        modality=ModalityType(block_record.modality),
                        addr=block_record.addr,
                        file_path=file_path,
                        page_number=block_record.page_number,
                        metadata=block_record.metadata or {}
                    )

                    # 生成语义表征
                    sb = semantic_rep.represent(block, self.db_manager, block_record.id, file_id)
                    semantic_blocks.append(sb)

                # 更新文件状态为PRELIMINARY
                if self.db_manager and file_id:
                    self.db_manager.update_file_status(file_id, FileStatus.PRELIMINARY)

                results[file_path] = {
                    'semantic_blocks_count': len(semantic_blocks),
                    'success': True
                }

            except Exception as e:
                print(f"[DEBUG] 语义表征失败 {file_path}: {e}")
                import traceback
                traceback.print_exc()
                results[file_path] = {
                    'semantic_blocks_count': 0,
                    'success': False,
                    'error': str(e)
                }

            processed += 1
            gc.collect()

        self.progress.emit("语义表征完成", 100)
        self.finished.emit(results)


class AnalyzeWorker(QThread):
    """后台分析工作线程"""
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, db_manager, classification_method: str = 'similarity', stop_before_classification: bool = False):
        super().__init__()
        self.db_manager = db_manager
        self._is_cancelled = False
        self.classification_method = classification_method
        self.stop_before_classification = stop_before_classification  # 是否在分类前停止
        self.pending_files = []

    def set_pending_files(self, files: List[str]):
        self.pending_files = files

    def cancel(self):
        self._is_cancelled = True
    
    def _load_config(self) -> dict:
        """加载配置文件 - 支持打包后的环境"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            base_dir = os.path.dirname(sys.executable)
            # 首先尝试外部目录
            config_path = os.path.join(base_dir, 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载配置文件失败: {e}")
            # 然后尝试_internal目录
            internal_path = os.path.join(base_dir, '_internal', 'config.json')
            if os.path.exists(internal_path):
                try:
                    with open(internal_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载_internal配置文件失败: {e}")
        else:
            # 开发环境
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'config.json')
            
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[DEBUG] 加载配置文件失败: {e}")
        
        return {}
    
    def run(self):
        print("[DEBUG] AnalyzeWorker.run() 开始执行")
        from database import DatabaseManager, FileStatus

        DataParser = None
        SemanticRepresentation = None
        SemanticClustering = None
        SemanticClassification = None

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)
        
        print(f"[DEBUG] base_dir: {base_dir}")
        print(f"[DEBUG] sys.path: {sys.path}")

        try:
            config = self._load_config()
            print(f"[DEBUG] 配置加载成功: {len(config)} 个配置项")
        except Exception as e:
            print(f"[DEBUG] 配置加载失败: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"配置加载失败: {str(e)}")
            return

        # 读取内存清理配置
        low_memory_config = config.get('low_memory_mode', {})
        memory_cleanup_config = low_memory_config.get('periodic_memory_cleanup', {})
        memory_cleanup_enabled = memory_cleanup_config.get('enabled', False)
        memory_cleanup_interval = memory_cleanup_config.get('file_interval', 5)
        if memory_cleanup_enabled:
            print(f"[Memory] 定期内存清理已启用，间隔: {memory_cleanup_interval} 个文件")

        # 初始化性能监控器
        perf_monitor = get_performance_monitor()
        perf_monitor.initialize(config)

        classification_method = config.get('classification', {}).get('method', self.classification_method)
        print(f"[DEBUG] 分类方法: {classification_method}")
        
        import_patterns = [
            ('data_parser', 'DataParser'),
            ('semantic_representation', 'SemanticRepresentation'),
            ('semantic_clustering', 'SemanticClustering'),
            ('semantic_classification', 'SemanticClassification'),
        ]
        
        print("[DEBUG] 开始导入模块...")
        for module_name, class_name in import_patterns:
            print(f"[DEBUG] 尝试导入 {module_name}.{class_name}")
            loaded = False
            try:
                module = __import__(module_name)
                DataParser = getattr(module, 'DataParser') if class_name == 'DataParser' else DataParser
                SemanticRepresentation = getattr(module, 'SemanticRepresentation') if class_name == 'SemanticRepresentation' else SemanticRepresentation
                SemanticClustering = getattr(module, 'SemanticClustering') if class_name == 'SemanticClustering' else SemanticClustering
                SemanticClassification = getattr(module, 'SemanticClassification') if class_name == 'SemanticClassification' else SemanticClassification
                loaded = True
                print(f"[DEBUG] 成功导入 {module_name}.{class_name} (方式1)")
            except ImportError as e:
                print(f"[DEBUG] 方式1导入失败 {module_name}: {e}")
            
            if not loaded:
                try:
                    module = __import__(f'file_analyzer.{module_name}', fromlist=[class_name])
                    DataParser = getattr(module, 'DataParser') if class_name == 'DataParser' else DataParser
                    SemanticRepresentation = getattr(module, 'SemanticRepresentation') if class_name == 'SemanticRepresentation' else SemanticRepresentation
                    SemanticClustering = getattr(module, 'SemanticClustering') if class_name == 'SemanticClustering' else SemanticClustering
                    SemanticClassification = getattr(module, 'SemanticClassification') if class_name == 'SemanticClassification' else SemanticClassification
                    loaded = True
                    print(f"[DEBUG] 成功导入 {module_name}.{class_name} (方式2)")
                except ImportError as e:
                    print(f"[DEBUG] 方式2导入失败 {module_name}: {e}")
            
            if not loaded:
                try:
                    import importlib.util
                    module_path = os.path.join(base_dir, module_name, '__init__.py')
                    print(f"[DEBUG] 尝试方式3，模块路径: {module_path}")
                    if os.path.exists(module_path):
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        DataParser = getattr(module, 'DataParser') if class_name == 'DataParser' else DataParser
                        SemanticRepresentation = getattr(module, 'SemanticRepresentation') if class_name == 'SemanticRepresentation' else SemanticRepresentation
                        SemanticClustering = getattr(module, 'SemanticClustering') if class_name == 'SemanticClustering' else SemanticClustering
                        SemanticClassification = getattr(module, 'SemanticClassification') if class_name == 'SemanticClassification' else SemanticClassification
                        loaded = True
                        print(f"[DEBUG] 成功导入 {module_name}.{class_name} (方式3)")
                    else:
                        print(f"[DEBUG] 方式3失败，文件不存在: {module_path}")
                except Exception as e:
                    print(f"[DEBUG] 方式3导入失败 {module_name}: {e}")
                    self.error.emit(f"无法加载模块 {module_name}: {str(e)}")
                    return
            
            if not loaded and class_name in ['DataParser', 'SemanticRepresentation']:
                print(f"[DEBUG] 关键模块 {module_name} 导入失败")
                self.error.emit(f"无法加载模块 {module_name}")
                return
        
        print(f"[DEBUG] 模块导入完成: DataParser={DataParser is not None}, SemanticRepresentation={SemanticRepresentation is not None}")
        
        if DataParser is None or SemanticRepresentation is None:
            self.error.emit("无法加载必要的分析模块")
            return
        
        if classification_method == 'clustering' and SemanticClustering is None:
            self.error.emit("无法加载语义聚类模块")
            return
        
        if classification_method == 'similarity' and SemanticClassification is None:
            self.error.emit("无法加载语义分类模块")
            return
        
        try:
            self.progress.emit("初始化分析引擎...", 0)

            # 使用已加载的配置
            # perf_monitor 已在外部初始化

            # 初始化各模块（带性能追踪）
            with perf_monitor.track_module("DataParser.init"):
                data_parser = DataParser(config)
            with perf_monitor.track_module("SemanticRepresentation.init"):
                semantic_rep = SemanticRepresentation(config)

            classifier = None
            # 如果不需要在分类前停止，才初始化分类器
            if not self.stop_before_classification:
                if classification_method == 'clustering':
                    with perf_monitor.track_module("SemanticClustering.init"):
                        classifier = SemanticClustering()
                    self.progress.emit("初始化聚类模型...", 5)
                else:
                    with perf_monitor.track_module("SemanticClassification.init"):
                        classifier = SemanticClassification()
                    self.progress.emit("初始化分类模型...", 5)

                with perf_monitor.track_module("Classifier.initialize"):
                    classifier.initialize()
            else:
                print("[DEBUG] stop_before_classification=True，跳过分类器初始化")
                self.progress.emit("仅生成语义表征...", 5)
            
            results = {}
            
            # 获取待分析的文件列表
            files_to_analyze = self.pending_files if self.pending_files else []
            if not files_to_analyze and self.db_manager:
                # 从数据库获取待分析的文件
                pending_records = self.db_manager.get_files_by_status(FileStatus.PENDING)
                files_to_analyze = [r.file_path for r in pending_records]
            
            total = len(files_to_analyze)
            processed = 0
            
            print(f"[DEBUG] 开始分析 {total} 个文件，使用{classification_method}方法")
            
            for file_path in files_to_analyze:
                if self._is_cancelled:
                    self.error.emit("分析已取消")
                    perf_monitor.stop()
                    return

                try:
                    # 开始文件处理追踪
                    perf_monitor.start_file_processing(file_path)

                    self.progress.emit(f"解析: {os.path.basename(file_path)}", int(10 + 80 * processed / total))

                    # 获取文件ID
                    file_id = None
                    if self.db_manager:
                        file_record = self.db_manager.get_file_by_path(file_path)
                        if file_record:
                            file_id = file_record.id

                    # 解析文件并写入数据块表（带性能追踪）
                    with perf_monitor.track_module("DataParser.parse_file"):
                        blocks = data_parser.parse_file(file_path, self.db_manager, file_id)
                    print(f"[DEBUG] 文件 {os.path.basename(file_path)} 解析出 {len(blocks) if blocks else 0} 个块")
                    if not blocks:
                        perf_monitor.end_file_processing(success=True, error_message="无数据块")
                        # 即使没有数据块，也更新文件状态为PRELIMINARY，避免重复处理
                        if self.db_manager and file_id:
                            self.db_manager.update_file_status(file_id, FileStatus.PRELIMINARY)
                            print(f"[DEBUG] 文件无数据块，状态已更新为PRELIMINARY")
                        processed += 1
                        continue

                    self.progress.emit(f"分析: {os.path.basename(file_path)}", int(10 + 80 * processed / total))

                    # 语义表征并写入语义块表
                    semantic_blocks = []

                    # 检查是否为轻量模式下的多页文档（首页数据块需要整合）
                    is_light_mode_first_page = False
                    if blocks and len(blocks) > 0:
                        # 检查第一个数据块的元数据
                        first_block = blocks[0]
                        if hasattr(first_block, 'metadata') and first_block.metadata:
                            if first_block.metadata.get('parsing_mode') == 'light_first_page':
                                is_light_mode_first_page = True

                    if is_light_mode_first_page and len(blocks) > 1:
                        # 轻量模式下的多页文档首页：整合所有首页数据块为一个语义块
                        print(f"[DEBUG] 轻量模式首页整合：{len(blocks)} 个数据块 -> 1 个语义块")
                        try:
                            # 获取最大长度配置
                            max_length = config.get('parsing', {}).get('light_mode_max_length', 256)

                            # 使用 represent_first_page_blocks 整合所有首页数据块（带性能追踪）
                            with perf_monitor.track_module("SemanticRepresentation.represent_first_page"):
                                sb = semantic_rep.represent_first_page_blocks(
                                    blocks=blocks,
                                    db_manager=self.db_manager,
                                    file_id=file_id,
                                    max_length=max_length
                                )
                            semantic_blocks.append(sb)
                            print(f"[DEBUG] 首页整合完成，生成 1 个语义块")
                        except Exception as e:
                            print(f"[DEBUG] 首页整合失败: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        # 深度模式或其他类型：逐个处理数据块
                        # 优化：预先获取所有数据块，避免重复数据库查询
                        data_blocks_map = {}
                        if self.db_manager and file_id:
                            data_blocks = self.db_manager.get_data_blocks_by_file(file_id)
                            data_blocks_map = {db.block_id: db.id for db in data_blocks}

                        for block in blocks:
                            try:
                                # 获取数据块ID（从预加载的map中查找）
                                data_block_id = data_blocks_map.get(block.block_id)

                                # 语义表征（带性能追踪）
                                with perf_monitor.track_module("SemanticRepresentation.represent"):
                                    sb = semantic_rep.represent(block, self.db_manager, data_block_id, file_id)
                                semantic_blocks.append(sb)
                            except Exception as e:
                                print(f"[DEBUG] 语义表征失败: {e}")
                                pass

                    print(f"[DEBUG] 语义表征完成，{len(semantic_blocks)} 个语义块")

                    if semantic_blocks:
                        # 检查是否需要在分类前停止
                        if self.stop_before_classification:
                            # 仅生成语义块，不进行分类
                            print(f"[DEBUG] stop_before_classification=True，跳过分类步骤")

                            # 更新文件状态为已生成语义块
                            if self.db_manager and file_id:
                                self.db_manager.update_file_status(file_id, FileStatus.PRELIMINARY)

                            # 将文件添加到结果中（无分类）
                            if '待分类' not in results:
                                results['待分类'] = []

                            results['待分类'].append({
                                'path': file_path,
                                'categories': [],
                                'primary_category': '待分类',
                                'primary_confidence': 0,
                                'total_blocks': len(semantic_blocks)
                            })

                            perf_monitor.end_file_processing(success=True)
                            gc.collect()
                            processed += 1
                            continue

                        # 分类并写入分类结果表（带性能追踪）
                        with perf_monitor.track_module("Classifier.classify_batch"):
                            if classification_method == 'clustering':
                                class_results = classifier.cluster_batch(semantic_blocks)
                            else:
                                class_results = classifier.classify_batch(semantic_blocks, self.db_manager, file_id)
                        print(f"[DEBUG] 分类完成，{len(class_results)} 个结果")

                        file_categories = {}
                        total_confidence = 0.0

                        for block, result in zip(semantic_blocks, class_results):
                            if classification_method == 'clustering':
                                category = result.cluster_name
                            else:
                                category = result.category_name
                            conf = result.confidence
                            total_confidence += conf

                            if category not in file_categories:
                                file_categories[category] = {
                                    'confidence_sum': 0.0,
                                    'block_count': 0,
                                    'keywords': []
                                }

                            file_categories[category]['confidence_sum'] += conf
                            file_categories[category]['block_count'] += 1
                            if block.keywords:
                                file_categories[category]['keywords'].extend(block.keywords[:3])
                        
                        file_category_list = []
                        for cat, data in file_categories.items():
                            normalized_conf = data['confidence_sum'] / total_confidence if total_confidence > 0 else 0
                            file_category_list.append({
                                'category': cat,
                                'confidence': normalized_conf,
                                'block_count': data['block_count'],
                                'keywords': list(set(data['keywords']))[:5]
                            })
                        
                        file_category_list.sort(key=lambda x: x['confidence'], reverse=True)
                        
                        primary_category = file_category_list[0]['category'] if file_category_list else '未分类'
                        
                        # 更新文件表的语义类别和分析状态
                        if self.db_manager and file_id:
                            self.db_manager.update_file_semantic_categories(file_id, file_category_list)
                            self.db_manager.update_file_status(file_id, FileStatus.PRELIMINARY)
                        
                        if primary_category not in results:
                            results[primary_category] = []

                        results[primary_category].append({
                            'path': file_path,
                            'categories': file_category_list,
                            'primary_category': primary_category,
                            'primary_confidence': file_category_list[0]['confidence'] if file_category_list else 0,
                            'total_blocks': len(semantic_blocks)
                        })

                        # 结束文件处理追踪（成功）
                        perf_monitor.end_file_processing(success=True)

                        # 方案C：显式垃圾回收，释放内存
                        gc.collect()
                    else:
                        # semantic_blocks 为空，但文件已处理，需要更新状态
                        print(f"[DEBUG] 文件 {os.path.basename(file_path)} 没有生成语义块，更新状态为PRELIMINARY")
                        if self.db_manager and file_id:
                            self.db_manager.update_file_status(file_id, FileStatus.PRELIMINARY)
                        perf_monitor.end_file_processing(success=True, error_message="无语义块")
                        gc.collect()
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"[DEBUG] 处理文件失败 {file_path}: {e}\n{error_detail}")

                    # 记录错误到日志
                    processing_logger.log_error("AnalyzeWorker", e, f"处理文件失败: {file_path}")

                    # 结束文件处理追踪（失败）
                    perf_monitor.end_file_processing(success=False, error_message=str(e))

                    # 更新文件状态为PRELIMINARY，避免重复处理失败的文件
                    if self.db_manager and file_id:
                        self.db_manager.update_file_status(file_id, FileStatus.PRELIMINARY)
                        print(f"[DEBUG] 文件处理失败，状态已更新为PRELIMINARY，避免重复处理")

                    # 方案C：即使失败也执行垃圾回收
                    gc.collect()

                processed += 1

                # 定期内存清理（根据配置）
                if memory_cleanup_enabled and processed % memory_cleanup_interval == 0:
                    try:
                        aggressive_cleanup()
                        print(f"[Memory] 已处理 {processed} 个文件，执行积极内存清理")
                    except Exception as e:
                        print(f"[Memory] 内存清理失败: {e}")

            # 所有文件处理完成后执行最终垃圾回收
            gc.collect()
            if memory_cleanup_enabled:
                aggressive_cleanup()  # 最终积极清理
            print("[Memory] 最终垃圾回收完成")

            # 生成性能报告
            perf_report_path = perf_monitor.generate_report()
            if perf_report_path:
                print(f"[PerformanceMonitor] 性能报告已生成: {perf_report_path}")

            print(f"[DEBUG] 分析完成，最终结果: {len(results)} 个分类")
            self.progress.emit("分析完成", 100)
            self.finished.emit(results)
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[DEBUG] 分析失败: {e}\n{error_detail}")
            perf_monitor.stop()
            self.error.emit(f"分析失败: {str(e)}")


class ScanWorker(QThread):
    """后台扫描工作线程"""
    scan_finished = pyqtSignal(dict)
    scan_progress = pyqtSignal(str, int)

    def __init__(self, scanner: DirectoryScanner, scan_type: str = 'default', db_manager=None):
        super().__init__()
        self.scanner = scanner
        self.scan_type = scan_type
        self.directory = None
        self.db_manager = db_manager

    def set_directory(self, directory: str):
        self.directory = directory
    
    def run(self):
        try:
            if self.scan_type == 'default':
                self.scan_progress.emit("正在扫描默认目录...", 0)
                # 扫描默认目录并收集目录结构
                results = self.scan_default_directories_with_structure()
                self.scan_finished.emit(results)
            elif self.scan_type == 'directory' and self.directory:
                self.scan_progress.emit(f"正在扫描: {self.directory}", 0)
                # 递归扫描目录，同时收集目录结构
                files, dir_structure = self.scan_directory_with_structure(self.directory)
                results = {
                    'default_directories': {os.path.basename(self.directory): files},
                    'total_files': len(files),
                    'scanned_directories': [self.directory],
                    'directory_structure': dir_structure,
                    'root_directory': self.directory
                }
                self.scan_finished.emit(results)
        except Exception as e:
            self.scan_finished.emit({'error': str(e)})
    
    def scan_default_directories_with_structure(self) -> Dict[str, Any]:
        """扫描默认目录并收集目录结构
        
        Returns:
            包含目录结构的结果字典
        """
        directories = self.scanner.get_default_scan_directories()
        all_files = []
        default_dirs = {}
        
        # 创建虚拟根目录结构
        root_structure = {
            'name': '默认目录',
            'path': '默认目录',
            'dirs': {},
            'files': []
        }
        
        for directory in directories:
            dir_name = os.path.basename(directory) or directory
            self.scan_progress.emit(f"正在扫描: {dir_name}", 0)
            
            # 扫描目录并收集结构
            files, dir_structure = self.scan_directory_with_structure(directory)
            
            if files:
                all_files.extend(files)
                default_dirs[dir_name] = files
                
                # 将每个默认目录作为虚拟根的子目录
                root_structure['dirs'][dir_name] = dir_structure
        
        return {
            'default_directories': default_dirs,
            'total_files': len(all_files),
            'scanned_directories': directories,
            'directory_structure': root_structure,
            'root_directory': '默认目录'
        }
    
    def scan_directory_with_structure(self, directory: str) -> tuple:
        """扫描目录并收集目录结构，同时写入数据库

        Returns:
            tuple: (文件列表, 目录结构字典)
        """
        from datetime import datetime

        files = []
        file_records = []
        dir_structure = {'name': os.path.basename(directory), 'path': directory, 'dirs': {}, 'files': []}

        for root, dirs, filenames in os.walk(directory):
            # 计算相对路径
            rel_path = os.path.relpath(root, directory)

            # 获取当前目录在结构中的位置
            current = dir_structure
            if rel_path != '.':
                parts = rel_path.split(os.sep)
                for part in parts:
                    if part not in current['dirs']:
                        current['dirs'][part] = {
                            'name': part,
                            'path': os.path.join(current['path'], part),
                            'dirs': {},
                            'files': []
                        }
                    current = current['dirs'][part]

            # 添加文件
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(file_path)
                current['files'].append(file_path)

                # 准备数据库记录
                if self.db_manager:
                    try:
                        stat = os.stat(file_path)
                        file_ext = os.path.splitext(filename)[1].lower()
                        file_records.append({
                            'file_path': file_path,
                            'file_name': filename,
                            'file_size': stat.st_size,
                            'file_type': file_ext,
                            'modified_time': datetime.fromtimestamp(stat.st_mtime),
                            'created_time': datetime.fromtimestamp(stat.st_ctime),
                            'directory_path': directory
                        })
                    except Exception as e:
                        print(f"获取文件信息失败 {file_path}: {e}")

        # 批量写入数据库
        if self.db_manager and file_records:
            self.db_manager.add_files_batch(file_records)
            print(f"已将 {len(file_records)} 个文件写入数据库")

        return files, dir_structure


class GenerateCategoryWorker(QThread):
    """生成类别信息的工作线程"""
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, categories: List[str]):
        super().__init__()
        self.categories = categories

    def run(self):
        """在工作线程中执行 LLM 调用生成类别信息"""
        try:
            from models.model_manager import get_llm_client, is_llm_available, get_llm_type

            self.progress.emit("检查 LLM 服务...", 10)

            if not is_llm_available():
                # LLM 不可用，使用默认信息
                self.progress.emit("LLM 服务不可用，使用默认信息", 100)
                default_info = self._get_default_category_info(self.categories)
                self.finished.emit({
                    'success': True,
                    'category_info': default_info,
                    'used_llm': False
                })
                return

            self.progress.emit(f"正在使用 AI ({get_llm_type()}) 生成类别信息...", 30)

            client = get_llm_client()
            category_info = client.generate_category_info_batch(self.categories)

            self.progress.emit("类别信息生成完成", 100)
            self.finished.emit({
                'success': True,
                'category_info': category_info,
                'used_llm': True
            })

        except Exception as e:
            import traceback
            print(f"[GenerateCategoryWorker] 生成类别信息失败: {e}\n{traceback.format_exc()}")
            # 出错时使用默认信息
            default_info = self._get_default_category_info(self.categories)
            self.finished.emit({
                'success': True,
                'category_info': default_info,
                'used_llm': False,
                'error': str(e)
            })

    def _get_default_category_info(self, categories: list) -> dict:
        """生成默认的类别信息"""
        return {
            cat: {
                "description": f"{cat}相关文件",
                "keywords": []
            }
            for cat in categories
        }


class ImageMetadataWorker(QThread):
    """图片时空元数据分析工作线程"""
    progress = pyqtSignal(str, int, int)  # message, current, total
    finished = pyqtSignal(dict)  # result
    error = pyqtSignal(str)

    def __init__(self, db_manager, file_ids: List[int] = None):
        super().__init__()
        self.db_manager = db_manager
        self.file_ids = file_ids  # 指定文件ID列表，None则处理所有图片
        self._is_cancelled = False

    def cancel(self):
        """取消分析"""
        self._is_cancelled = True

    def run(self):
        """执行图片元数据分析"""
        try:
            from semantic_representation.image_metadata_extractor import ImageMetadataExtractor

            extractor = ImageMetadataExtractor(use_gps_reverse=True)

            # 获取待分析的图片文件
            if self.file_ids:
                files = []
                for file_id in self.file_ids:
                    record = self.db_manager.get_file_by_id(file_id)
                    if record:
                        files.append(record)
            else:
                # 获取所有图片类型文件
                files = self.db_manager.get_files_by_type('image')

            total = len(files)
            if total == 0:
                self.finished.emit({'processed': 0, 'updated': 0, 'errors': 0})
                return

            self.progress.emit(f"开始分析 {total} 个图片文件...", 0, total)

            processed = 0
            updated = 0
            errors = 0
            updates = []

            for file_record in files:
                if self._is_cancelled:
                    break

                processed += 1
                file_path = file_record.file_path

                # 检查是否为图片文件
                if not extractor.is_image_file(file_path):
                    continue

                try:
                    # 提取元数据
                    metadata = extractor.extract_metadata(file_path)

                    # 只有提取到有意义的信息才更新
                    has_useful_info = any([
                        metadata.get('capture_time_extracted'),
                        metadata.get('capture_time_from_filename'),
                        metadata.get('location_info'),
                        metadata.get('image_width'),
                        metadata.get('image_height')
                    ])

                    if has_useful_info:
                        updates.append((file_record.id, metadata))
                        updated += 1

                    # 更新进度
                    if processed % 10 == 0 or processed == total:
                        self.progress.emit(
                            f"已处理 {processed}/{total} 个文件，更新 {updated} 个",
                            processed, total
                        )

                except Exception as e:
                    errors += 1
                    print(f"[ImageMetadataWorker] 处理文件失败: {file_path}, 错误: {e}")

            # 批量更新数据库
            if updates:
                self.db_manager.update_file_metadata_batch(updates)

            result = {
                'processed': processed,
                'updated': updated,
                'errors': errors,
                'cancelled': self._is_cancelled
            }

            self.progress.emit(f"分析完成: 处理 {processed} 个，更新 {updated} 个", total, total)
            self.finished.emit(result)

        except Exception as e:
            import traceback
            print(f"[ImageMetadataWorker] 分析失败: {e}\n{traceback.format_exc()}")
            self.error.emit(f"图片元数据分析失败: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def _get_config_path(self):
        """获取配置文件路径 - 支持打包后的环境"""
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            base_dir = os.path.dirname(sys.executable)
            # 首先尝试外部目录
            config_path = os.path.join(base_dir, 'config.json')
            if os.path.exists(config_path):
                return config_path
            # 然后尝试_internal目录
            internal_path = os.path.join(base_dir, '_internal', 'config.json')
            if os.path.exists(internal_path):
                return internal_path
            return config_path  # 返回默认路径
        else:
            # 开发环境
            return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
    
    def __init__(self):
        super().__init__()

        # 预加载PyTorch和sentence_transformers（修复Windows子线程加载问题）
        try:
            import torch
            import sentence_transformers
        except ImportError:
            pass

        self.scanner = DirectoryScanner()
        self.current_directory = None
        self.current_files = []
        self.scan_worker = None
        self.analyze_worker = None
        self.parse_worker = None
        self.semantic_represent_worker = None
        self._generate_category_worker = None
        self._image_metadata_worker = None
        self._pending_category_system_name = None
        self._pending_category_list = None
        self.config = self._load_config()
        
        # 初始化日志会话（根据配置决定是否启用）
        self._init_logging()
        
        # 初始化数据库
        from database import DatabaseManager
        self.db_manager = DatabaseManager()
        
        self.init_ui()
        self.init_menu()
        self.init_toolbar()
        self.init_statusbar()

        # 加载配置中的类别体系
        self._load_category_systems_from_config()

        self.load_default_directories()

    def _load_category_systems_from_config(self):
        """从配置文件和数据库加载类别体系"""
        # 首先从数据库加载已保存的类别体系
        self._load_category_systems_from_database()

        # 然后从配置文件加载默认类别体系
        category_systems = self.config.get('category_systems', [])

        if not category_systems:
            # 如果没有category_systems，尝试从旧的categories字段构建默认类别体系
            categories = self.config.get('categories', [])
            if categories:
                # 构建类别信息
                category_names = []
                category_info = {}
                for cat in categories:
                    name = cat.get('name', '')
                    if name:
                        category_names.append(name)
                        category_info[name] = {
                            'description': cat.get('description', f'{name}相关文件'),
                            'keywords': cat.get('keywords', [])
                        }

                default_system = {
                    'system_name': '默认类别体系',
                    'description': '系统内置的默认文件分类类别体系',
                    'categories': category_names,
                    'category_info': category_info
                }
                category_systems = [default_system]

        for system_data in category_systems:
            system_name = system_data.get('system_name', '未命名类别体系')
            categories = system_data.get('categories', [])
            category_info = system_data.get('category_info', {})

            # 提取类别名称列表
            if categories and isinstance(categories[0], dict):
                category_names = [cat.get('name', '') for cat in categories if cat.get('name')]
                # 从字典列表构建 category_info
                if not category_info:
                    for cat in categories:
                        name = cat.get('name', '')
                        if name:
                            category_info[name] = {
                                'description': cat.get('description', f'{name}相关文件'),
                                'keywords': cat.get('keywords', [])
                            }
            else:
                category_names = categories

            if category_names:
                # 检查是否已存在同名类别体系
                if not self.classification_panel.get_category_system(system_name):
                    self.classification_panel.add_category_system(system_name, category_names, category_info)
                    # 如果数据库中也没有，则保存到数据库
                    if self.db_manager:
                        self._save_category_system_to_database(system_name, category_names, category_info)

    def _load_category_systems_from_database(self):
        """从数据库加载已保存的类别体系"""
        if not self.db_manager:
            return

        try:
            # 获取所有类别体系
            category_systems = self.db_manager.get_all_category_systems()

            for system_name, categories in category_systems.items():
                if not categories:
                    continue

                category_names = [cat.category_name for cat in categories]
                category_info = {}

                for cat in categories:
                    category_info[cat.category_name] = {
                        'description': cat.description,
                        'keywords': cat.keywords or []
                    }

                # 添加到分类面板
                self.classification_panel.add_category_system(system_name, category_names, category_info)
                print(f"[MainWindow] 从数据库加载类别体系: {system_name}, 包含 {len(categories)} 个类别")

        except Exception as e:
            print(f"[MainWindow] 从数据库加载类别体系失败: {e}")

    def _init_logging(self):
        """根据配置初始化日志"""
        logging_config = self.config.get('logging', {})
        enabled = logging_config.get('enabled', True)
        
        if enabled:
            try:
                log_path = processing_logger.start_session("file_analyzer")
                print(f"日志文件已创建: {log_path}")
            except Exception as e:
                print(f"初始化日志失败: {e}")
        else:
            print("日志记录已禁用（根据配置）")
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        return {}
    
    def _save_config(self):
        """保存配置文件"""
        if not self.config:
            return
        
        try:
            config_path = self._get_config_path()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def _save_initial_directory(self, directory: str):
        """保存初始目录到配置文件"""
        self.config['initial_directory'] = directory
        self._save_config()
    
    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("文件分析管理器")
        self.setGeometry(100, 100, 1400, 900)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 主内容区域（使用分割器）- 设置拉伸因子，确保占用至少80%高度
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 左侧：推荐窗口
        self.recommendation_panel = RecommendationPanel()
        self.recommendation_panel.recommendation_selected.connect(self.on_recommendation_selected)
        self.recommendation_panel.setMinimumHeight(400)
        content_splitter.addWidget(self.recommendation_panel)
        
        # 中间：预览窗口 - 设置最小高度
        self.preview_panel = PreviewPanel()
        self.preview_panel.setMinimumHeight(400)
        content_splitter.addWidget(self.preview_panel)
        
        # 右侧：分类结果窗口（包含类别体系、分类结果、搜索三种模式）
        self.classification_panel = ClassificationPanel()
        self.classification_panel.file_selected.connect(self.on_file_selected)
        self.classification_panel.category_system_changed.connect(self.on_category_system_changed)
        self.classification_panel.set_db_manager(self.db_manager)  # 设置数据库管理器
        self.classification_panel.setMinimumHeight(400)
        content_splitter.addWidget(self.classification_panel)

        # 设置分割器比例（三列布局）
        content_splitter.setSizes([300, 500, 400])
        
        # 将分割器添加到主布局，设置拉伸因子为1，确保占用主要空间
        main_layout.addWidget(content_splitter, 1)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QComboBox:hover {
                border-color: #2196F3;
            }
        """)
    
    def init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        # 打开目录
        open_dir_action = QAction("打开目录...", self)
        open_dir_action.setShortcut(QKeySequence.Open)
        open_dir_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_dir_action)
        
        # 扫描默认目录
        scan_default_action = QAction("扫描默认目录", self)
        scan_default_action.setShortcut("Ctrl+D")
        scan_default_action.triggered.connect(self.scan_default_directories)
        file_menu.addAction(scan_default_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")

        # 自动获取预定义类别
        auto_categories_action = QAction("自动获取预定义类别", self)
        auto_categories_action.setShortcut("Ctrl+G")
        auto_categories_action.setToolTip("从当前目录结构自动获取分类类别")
        auto_categories_action.triggered.connect(self.auto_get_categories_from_directory)
        tools_menu.addAction(auto_categories_action)

        tools_menu.addSeparator()

        # 图片时空数据分析
        image_metadata_action = QAction("图片时空数据分析", self)
        image_metadata_action.setToolTip("提取图片的拍摄时间、地点等元数据信息")
        image_metadata_action.triggered.connect(self.analyze_image_metadata)
        tools_menu.addAction(image_metadata_action)

        tools_menu.addSeparator()

        # 设置
        settings_action = QAction("设置...", self)
        settings_action.triggered.connect(self.show_settings)
        tools_menu.addAction(settings_action)

        tools_menu.addSeparator()

        # 清空历史分析
        clear_history_action = QAction("清空历史分析", self)
        clear_history_action.triggered.connect(self.clear_analysis_history)
        tools_menu.addAction(clear_history_action)

        # 清空历史分析(仅保留类别体系)
        clear_history_keep_categories_action = QAction("清空历史分析(仅保留类别体系)", self)
        clear_history_keep_categories_action.triggered.connect(self.clear_analysis_history_keep_categories)
        tools_menu.addAction(clear_history_keep_categories_action)

        # 清空历史分类结果
        clear_classification_action = QAction("清空历史分类结果", self)
        clear_classification_action.triggered.connect(self.clear_classification_results_history)
        tools_menu.addAction(clear_classification_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def init_toolbar(self):
        """初始化工具栏"""
        # 搜索面板作为工具栏
        self.search_panel = SearchPanel()
        self.search_panel.search_requested.connect(self.on_search)
        self.search_panel.directory_changed.connect(self.on_directory_changed)
        self.search_panel.parse_requested.connect(self.start_parse)
        self.search_panel.semantic_represent_requested.connect(self.start_semantic_represent)
        self.search_panel.classify_requested.connect(self.start_classify)

        # 将搜索面板添加为工具栏
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.addToolBar(toolbar)
        toolbar.addWidget(self.search_panel)
    
    def init_statusbar(self):
        """初始化状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        self.statusbar.showMessage("就绪")
        
        # 文件计数标签
        self.file_count_label = QLabel("文件: 0")
        self.statusbar.addPermanentWidget(self.file_count_label)
        
        # 选中文件标签
        self.selected_label = QLabel("选中: 无")
        self.statusbar.addPermanentWidget(self.selected_label)
    
    def load_default_directories(self):
        """加载默认目录"""
        initial_dir = self.config.get('initial_directory', '')
        
        if initial_dir and os.path.exists(initial_dir):
            self.current_directory = initial_dir
            self.load_directory(self.current_directory)
        else:
            default_dirs = self.scanner.get_default_scan_directories()
            if default_dirs:
                self.current_directory = default_dirs[0]
                self.load_directory(self.current_directory)
    
    def load_directory(self, directory: str):
        """加载指定目录"""
        if not os.path.exists(directory):
            QMessageBox.warning(self, "错误", f"目录不存在: {directory}")
            return
        
        self.current_directory = directory
        self._save_initial_directory(directory)
        
        self.start_scan('directory', directory)
    
    def start_scan(self, scan_type: str, directory: str = None):
        """启动后台扫描"""
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.wait()

        self.scan_worker = ScanWorker(self.scanner, scan_type, self.db_manager)
        if directory:
            self.scan_worker.set_directory(directory)

        self.scan_worker.scan_progress.connect(self.on_scan_progress)
        self.scan_worker.scan_finished.connect(self.on_scan_finished)

        self.statusbar.showMessage("正在扫描...")
        self.scan_worker.start()
    
    def on_scan_progress(self, message: str, progress: int):
        """扫描进度回调"""
        self.statusbar.showMessage(message)
    
    def on_scan_finished(self, results: Dict[str, Any]):
        """扫描完成回调"""
        if 'error' in results:
            QMessageBox.critical(self, "扫描错误", f"扫描失败: {results['error']}")
            self.statusbar.showMessage("扫描失败")
            return
        
        # 收集所有文件
        all_files = []
        for dir_name, files in results.get('default_directories', {}).items():
            all_files.extend(files)
        
        self.current_files = all_files
        
        # 更新状态栏
        total_files = results.get('total_files', len(all_files))
        self.file_count_label.setText(f"文件: {total_files}")
        self.statusbar.showMessage(f"扫描完成，共 {total_files} 个文件")
        
        # 更新推荐面板（显示目录树）
        root_dir = results.get('root_directory', self.current_directory)
        dir_structure = results.get('directory_structure')
        
        if dir_structure:
            # 如果有目录结构字典，直接使用（支持虚拟根目录）
            self.recommendation_panel.set_directory_structure_from_dict(root_dir or '默认目录', dir_structure)
        elif root_dir and os.path.exists(root_dir):
            self.recommendation_panel.set_directory_structure(root_dir, all_files)
        else:
            self.generate_recommendations_legacy(all_files)
    
    def generate_recommendations_legacy(self, files: List[str]):
        """生成文件推荐（旧方式，用于兼容）"""
        # 按类型分组
        file_groups = {}
        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in file_groups:
                file_groups[ext] = []
            file_groups[ext].append(file_path)
        
        # 生成推荐项
        recommendations = []
        
        # 最近修改的文件
        recent_files = sorted(files, 
                            key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0,
                            reverse=True)[:5]
        if recent_files:
            recommendations.append({
                'title': '最近修改',
                'files': recent_files,
                'type': 'recent'
            })
        
        # 按类型推荐
        for ext, ext_files in sorted(file_groups.items(), key=lambda x: len(x[1]), reverse=True)[:3]:
            type_names = {
                '.pdf': 'PDF文档',
                '.doc': 'Word文档',
                '.docx': 'Word文档',
                '.ppt': 'PPT演示',
                '.pptx': 'PPT演示',
                '.txt': '文本文件',
                '.jpg': '图片',
                '.jpeg': '图片',
                '.png': '图片',
                '.mp3': '音频',
                '.wav': '音频',
            }
            type_name = type_names.get(ext, f'{ext} 文件')
            recommendations.append({
                'title': type_name,
                'files': ext_files[:5],
                'type': 'category'
            })
        
        self.recommendation_panel.set_recommendations(recommendations)
    
    def on_file_selected(self, file_path: str):
        """文件选中回调"""
        self.selected_label.setText(f"选中: {os.path.basename(file_path)}")
        self.preview_panel.preview_file(file_path)
    
    def on_search(self, query: str):
        """搜索回调 - 使用语义搜索"""
        if not query:
            # 如果查询为空，切换回类别体系模式
            self.classification_panel.set_category_system_mode()
            self.statusbar.showMessage("已返回类别体系")
            return

        # 执行语义搜索
        self.perform_semantic_search(query)
    
    def perform_semantic_search(self, query: str):
        """执行语义搜索
        
        Args:
            query: 搜索查询文本
        """
        try:
            self.statusbar.showMessage(f"正在执行语义搜索: '{query}'...")
            
            # 导入语义查询模块
            from semantic_query import SemanticQuery
            
            # 创建语义查询器
            semantic_query = SemanticQuery(
                db_manager=self.db_manager,
                config=self.config
            )
            
            # 从配置中获取top_k和top_m参数
            query_config = self.config.get('query', {})
            top_k = query_config.get('top_k', 10)
            top_m = query_config.get('top_m', 5)
            
            # 执行搜索
            search_result = semantic_query.search(query, top_k=top_k, top_m=top_m)
            
            # 在分类面板中显示搜索结果
            self.classification_panel.set_search_results(search_result)
            
            # 更新状态栏
            file_count = len(search_result.files)
            self.statusbar.showMessage(
                f"语义搜索 '{query}' 完成，找到 {file_count} 个相关文件"
            )
            
        except Exception as e:
            print(f"语义搜索失败: {e}")
            import traceback
            traceback.print_exc()
            self.statusbar.showMessage(f"语义搜索失败: {str(e)}")
            QMessageBox.warning(self, "搜索失败", f"语义搜索执行失败: {str(e)}")
    
    def on_directory_changed(self, directory: str):
        """目录改变回调"""
        self.load_directory(directory)
    
    def on_recommendation_selected(self, file_path: str):
        """推荐项选中回调"""
        self.on_file_selected(file_path)

    def start_parse(self):
        """开始文件解析

        流程：
        1. 扫描目录，将文件添加到数据库
        2. 检查每个文件的分析状态
        3. 已解析的文件跳过
        4. 待解析的文件执行解析流程（生成数据块，保存到cache）
        """
        print("[DEBUG] start_parse 被调用", flush=True)
        from database import FileStatus

        if not self.current_directory:
            print("[DEBUG] 错误: 未选择目录", flush=True)
            QMessageBox.warning(self, "提示", "请先选择一个目录")
            return

        print(f"[DEBUG] 当前目录: {self.current_directory}", flush=True)

        # 先扫描目录并将文件添加到数据库
        print("[DEBUG] 开始扫描目录...", flush=True)
        files = []
        try:
            files = self.scanner.scan_directory(self.current_directory, db_manager=self.db_manager)
            print(f"[DEBUG] 扫描完成，找到 {len(files)} 个文件", flush=True)
        except Exception as e:
            print(f"[DEBUG] 扫描目录失败: {e}", flush=True)
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"扫描目录失败: {str(e)}")
            return

        if not files:
            print("[DEBUG] 目录中没有可解析的文件")
            QMessageBox.warning(self, "提示", "目录中没有可解析的文件")
            return

        self.current_files = files

        # 收集待解析的文件（PENDING状态）
        files_to_parse = []
        parsed_count = 0

        print("[DEBUG] 开始检查文件解析状态...")
        for file_path in files:
            try:
                file_record = self.db_manager.get_file_by_path(file_path)
                if file_record:
                    if file_record.analysis_status >= FileStatus.PARSED:
                        # 已解析，跳过
                        parsed_count += 1
                    elif file_record.analysis_status == FileStatus.PENDING:
                        # 待解析
                        files_to_parse.append(file_path)
                else:
                    # 文件记录不存在，需要解析
                    files_to_parse.append(file_path)
            except Exception as e:
                print(f"[DEBUG] 检查文件状态失败 {file_path}: {e}")

        print(f"[DEBUG] 已解析: {parsed_count} 个, 待解析: {len(files_to_parse)} 个")

        # 如果没有待解析的文件
        if not files_to_parse:
            if parsed_count > 0:
                QMessageBox.information(
                    self, "解析完成",
                    f"所有 {parsed_count} 个文件已解析。\n\n"
                    f"请点击'语义表征'按钮生成语义表征。"
                )
                self.statusbar.showMessage(
                    f"所有文件已解析，请点击'语义表征'按钮生成语义表征"
                )
            else:
                QMessageBox.information(self, "提示", "没有需要解析的文件")
            return

        # 启动解析线程
        print("[DEBUG] 启动解析线程...")
        try:
            self.parse_worker = ParseWorker(self.db_manager)
            self.parse_worker.set_pending_files(files_to_parse)
            self.parse_worker.progress.connect(self.on_parse_progress)
            self.parse_worker.finished.connect(
                lambda results: self.on_parse_finished(results, len(files_to_parse))
            )
            self.parse_worker.error.connect(self.on_parse_error)

            self.search_panel.show_progress(True)
            self.statusbar.showMessage(f"正在解析 {len(files_to_parse)} 个文件...")
            print("[DEBUG] 解析线程启动前...")
            self.parse_worker.start()
            print("[DEBUG] 解析线程已启动")
        except Exception as e:
            print(f"[DEBUG] 启动解析线程失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"启动解析失败: {str(e)}")

    def on_parse_progress(self, message: str, progress: int):
        """解析进度回调"""
        self.search_panel.set_progress(progress)
        self.statusbar.showMessage(message)

    def on_parse_finished(self, results: Dict, files_count: int = 0):
        """解析完成回调"""
        self.search_panel.show_progress(False)

        success_count = sum(1 for r in results.values() if r.get('success', False))
        print(f"[DEBUG] 解析完成，成功 {success_count} 个文件")

        self.statusbar.showMessage(
            f"文件解析完成，共 {success_count} 个文件。"
            f"请点击'语义表征'按钮生成语义表征。"
        )

        QMessageBox.information(
            self, "解析完成",
            f"已完成 {success_count} 个文件的解析。\n\n"
            f"数据块已保存到cache目录。\n"
            f"请点击'语义表征'按钮生成语义表征。"
        )

    def on_parse_error(self, error_msg: str):
        """解析错误回调"""
        self.search_panel.show_progress(False)
        QMessageBox.critical(self, "解析错误", error_msg)
        self.statusbar.showMessage("解析失败")

    def start_semantic_represent(self):
        """开始语义表征

        流程：
        1. 检查每个文件的分析状态
        2. 已生成语义表征的文件跳过
        3. 已解析的文件执行语义表征流程
        """
        print("[DEBUG] start_semantic_represent 被调用", flush=True)
        from database import FileStatus

        if not self.current_directory:
            print("[DEBUG] 错误: 未选择目录", flush=True)
            QMessageBox.warning(self, "提示", "请先选择一个目录")
            return

        # 收集待语义表征的文件（PARSED状态）
        files_to_represent = []
        preliminary_count = 0

        print("[DEBUG] 开始检查文件状态...")
        try:
            parsed_records = self.db_manager.get_files_by_status(FileStatus.PARSED)
            files_to_represent = [r.file_path for r in parsed_records]

            preliminary_records = self.db_manager.get_files_by_status(FileStatus.PRELIMINARY)
            preliminary_count = len(preliminary_records)
        except Exception as e:
            print(f"[DEBUG] 检查文件状态失败: {e}")

        print(f"[DEBUG] 已生成语义表征: {preliminary_count} 个, 待语义表征: {len(files_to_represent)} 个")

        # 如果没有待语义表征的文件
        if not files_to_represent:
            if preliminary_count > 0:
                QMessageBox.information(
                    self, "语义表征完成",
                    f"所有 {preliminary_count} 个文件已生成语义表征。\n\n"
                    f"请选择类别体系后点击'分类'按钮进行分类。"
                )
                self.statusbar.showMessage(
                    f"所有文件已生成语义表征，请点击'分类'按钮进行分类"
                )
            else:
                QMessageBox.information(self, "提示", "没有待语义表征的文件。\n请先点击'解析'按钮解析文件。")
            return

        # 启动语义表征线程
        print("[DEBUG] 启动语义表征线程...")
        try:
            self.semantic_represent_worker = SemanticRepresentWorker(self.db_manager)
            self.semantic_represent_worker.set_pending_files(files_to_represent)
            self.semantic_represent_worker.progress.connect(self.on_semantic_represent_progress)
            self.semantic_represent_worker.finished.connect(
                lambda results: self.on_semantic_represent_finished(results, len(files_to_represent))
            )
            self.semantic_represent_worker.error.connect(self.on_semantic_represent_error)

            self.search_panel.show_progress(True)
            self.statusbar.showMessage(f"正在生成语义表征 {len(files_to_represent)} 个文件...")
            print("[DEBUG] 语义表征线程启动前...")
            self.semantic_represent_worker.start()
            print("[DEBUG] 语义表征线程已启动")
        except Exception as e:
            print(f"[DEBUG] 启动语义表征线程失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"启动语义表征失败: {str(e)}")

    def on_semantic_represent_progress(self, message: str, progress: int):
        """语义表征进度回调"""
        self.search_panel.set_progress(progress)
        self.statusbar.showMessage(message)

    def on_semantic_represent_finished(self, results: Dict, files_count: int = 0):
        """语义表征完成回调"""
        self.search_panel.show_progress(False)

        success_count = sum(1 for r in results.values() if r.get('success', False))
        print(f"[DEBUG] 语义表征完成，成功 {success_count} 个文件")

        self.statusbar.showMessage(
            f"语义表征生成完成，共 {success_count} 个文件。"
            f"请选择类别体系后点击'分类'按钮进行分类。"
        )

        QMessageBox.information(
            self, "语义表征完成",
            f"已完成 {success_count} 个文件的语义表征生成。\n\n"
            f"请在右侧面板选择或创建类别体系，\n"
            f"然后点击'分类'按钮进行分类。"
        )

    def on_semantic_represent_error(self, error_msg: str):
        """语义表征错误回调"""
        self.search_panel.show_progress(False)
        QMessageBox.critical(self, "语义表征错误", error_msg)
        self.statusbar.showMessage("语义表征失败")

    def start_classify(self):
        """开始分类流程

        使用当前选中的类别体系对文件进行分类。
        检查文件的语义类别字段，如果已包含当前类别体系的结果则跳过。
        """
        # 获取当前选中的类别体系
        current_system = self.classification_panel.get_current_system()

        if not current_system:
            QMessageBox.warning(
                self, "提示",
                "请先选择一个类别体系。\n"
                "可以通过菜单 '工具->自动获取预定义类别' 创建类别体系，"
                "或在右侧面板中点击类别体系进行选择。"
            )
            return

        category_system_name = current_system.name
        print(f"[DEBUG] start_classify: 当前类别体系 '{category_system_name}'")

        # 检查是否有已生成语义表征的文件
        from database import FileStatus
        preliminary_records = self.db_manager.get_files_by_status(FileStatus.PRELIMINARY)

        print(f"[DEBUG] get_files_by_status(PRELIMINARY) 返回 {len(preliminary_records)} 个文件")

        if not preliminary_records:
            QMessageBox.warning(
                self, "提示",
                "没有待分类的文件。\n请先点击'语义表征'按钮生成语义表征。"
            )
            return

        # 筛选出需要分类的文件（semantic_categories中不包含当前类别体系结果的文件）
        files_to_classify = []
        already_classified = 0

        for record in preliminary_records:
            print(f"[DEBUG] 检查文件 {record.file_name}, analysis_status={record.analysis_status}, semantic_categories={record.semantic_categories}")
            # 检查该文件是否已有当前类别体系的分类结果
            existing_categories = record.semantic_categories or []
            has_current_system = any(
                cat.get('category_system_name') == category_system_name
                for cat in existing_categories
            )

            if not has_current_system:
                # 还没有当前类别体系的分类结果，需要分类
                files_to_classify.append(record)
                print(f"[DEBUG] -> 需要分类")
            else:
                already_classified += 1
                print(f"[DEBUG] -> 已有分类结果，跳过")

        print(f"[DEBUG] 需要分类: {len(files_to_classify)}, 已有分类: {already_classified}")

        if not files_to_classify:
            QMessageBox.information(
                self, "提示",
                f"所有 {len(preliminary_records)} 个文件已在 '{category_system_name}' 类别体系下分类。\n"
                f"无需重复分类。"
            )
            return

        # 执行分类
        self._perform_classification(current_system, files_to_classify, already_classified)

    def _perform_classification(self, category_system, pending_records, already_classified=0):
        """执行分类

        Args:
            category_system: 选中的类别体系
            pending_records: 待分类的文件记录列表
            already_classified: 已分类的文件数量（其他类别体系）
        """
        categories = category_system.categories
        category_system_name = category_system.name
        results = {}

        self.statusbar.showMessage(f"正在使用 '{category_system_name}' 进行分类...")

        try:
            # 使用语义分类器进行分类
            from semantic_classification import SemanticClassification

            classifier = SemanticClassification()
            classifier.initialize()

            # 设置自定义类别
            classifier.set_categories(categories)

            for file_record in pending_records:
                try:
                    file_id = file_record.id
                    file_path = file_record.file_path

                    # 获取文件的语义块记录（数据库记录）
                    semantic_block_records = self.db_manager.get_semantic_blocks_by_file(file_id)

                    if not semantic_block_records:
                        print(f"[DEBUG] 文件 {file_path} 没有语义块，跳过")
                        continue

                    # 将 SemanticBlockRecord 转换为 SemanticBlock
                    import numpy as np
                    from semantic_representation import SemanticBlock

                    semantic_blocks = []
                    for record in semantic_block_records:
                        # 将 bytes 转换为 numpy array
                        semantic_vector = None
                        if record.semantic_vector:
                            try:
                                semantic_vector = np.frombuffer(record.semantic_vector, dtype=np.float32)
                            except Exception as e:
                                print(f"[DEBUG] 向量转换失败: {e}")

                        sb = SemanticBlock(
                            block_id=record.semantic_block_id,
                            text_description=record.text_description,
                            keywords=record.keywords,
                            semantic_vector=semantic_vector,
                            modality="text",
                            original_metadata={}
                        )
                        semantic_blocks.append(sb)

                    # 执行分类，传入类别体系名称
                    class_results = classifier.classify_batch(
                        semantic_blocks, self.db_manager, file_id,
                        category_system_name=category_system_name
                    )

                    # 统计分类结果
                    file_categories = {}
                    total_confidence = 0.0

                    for _, result in zip(semantic_blocks, class_results):
                        category = result.category_name
                        conf = result.confidence
                        total_confidence += conf

                        if category not in file_categories:
                            file_categories[category] = {
                                'confidence_sum': 0.0,
                                'block_count': 0
                            }

                        file_categories[category]['confidence_sum'] += conf
                        file_categories[category]['block_count'] += 1

                    # 生成当前类别体系的分类结果列表
                    current_system_results = []
                    for cat, data in file_categories.items():
                        normalized_conf = data['confidence_sum'] / total_confidence if total_confidence > 0 else 0
                        current_system_results.append({
                            'category': cat,
                            'confidence': normalized_conf,
                            'block_count': data['block_count'],
                            'category_system_name': category_system_name
                        })

                    current_system_results.sort(key=lambda x: x['confidence'], reverse=True)

                    primary_category = current_system_results[0]['category'] if current_system_results else '未分类'

                    # 获取原有的分类结果，追加新的分类结果
                    existing_categories = list(file_record.semantic_categories or [])
                    # 移除同一类别体系的旧结果（如果存在）
                    existing_categories = [
                        cat for cat in existing_categories
                        if cat.get('category_system_name') != category_system_name
                    ]
                    # 合并新旧结果
                    updated_categories = existing_categories + current_system_results

                    # 更新数据库
                    self.db_manager.update_file_semantic_categories(file_id, updated_categories)

                    # 添加到结果（用于UI显示）
                    if primary_category not in results:
                        results[primary_category] = []

                    results[primary_category].append({
                        'path': file_path,
                        'categories': current_system_results,
                        'primary_category': primary_category,
                        'primary_confidence': current_system_results[0]['confidence'] if current_system_results else 0,
                        'total_blocks': len(semantic_blocks),
                        'category_system_name': category_system_name
                    })

                except Exception as e:
                    print(f"[DEBUG] 分类文件失败 {file_record.file_path}: {e}")
                    import traceback
                    traceback.print_exc()

            # 更新UI - 显示当前类别体系的所有分类结果
            self.classification_panel.show_classification_results_for_system(
                self.db_manager, category_system_name
            )
            total_files = sum(len(files) for files in results.values())

            # 构建完成消息
            msg = f"使用 '{category_system_name}' 分类体系\n共分类 {total_files} 个文件"
            if already_classified > 0:
                msg += f"\n（{already_classified} 个文件已有该类别体系的结果，已跳过）"

            self.statusbar.showMessage(f"分类完成，共 {total_files} 个文件使用 '{category_system_name}' 分类体系")
            QMessageBox.information(self, "分类完成", msg)

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "分类错误", f"分类执行失败: {str(e)}")
            self.statusbar.showMessage("分类失败")

    def on_category_system_changed(self, category_system):
        """当选择的类别体系变化时

        如果已有分类结果，显示该类别体系的分类结果。

        Args:
            category_system: 新选中的类别体系（CategorySystem对象或None）
        """
        if category_system and self.db_manager:
            # 显示该类别体系的分类结果
            self.classification_panel.show_classification_results_for_system(
                self.db_manager, category_system.name
            )

    def open_directory(self):
        """打开目录对话框"""
        directory = QFileDialog.getExistingDirectory(self, "选择目录")
        if directory:
            self.load_directory(directory)
    
    def scan_default_directories(self):
        """扫描默认目录"""
        self.start_scan('default')
    
    def show_settings(self):
        """显示设置对话框"""
        QMessageBox.information(self, "设置", "设置功能待实现")

    def analyze_image_metadata(self):
        """分析图片时空元数据"""
        # 检查是否有图片文件
        image_files = self.db_manager.get_files_by_type('image')

        if not image_files:
            QMessageBox.information(
                self, "提示",
                "数据库中没有图片文件。\n请先扫描并解析包含图片的目录。"
            )
            return

        reply = QMessageBox.question(
            self, "图片时空数据分析",
            f"将对 {len(image_files)} 个图片文件进行时空元数据分析。\n\n"
            "将提取以下信息：\n"
            "• 拍摄时间（从EXIF等元数据提取）\n"
            "• 拍摄时间（从文件名解析）\n"
            "• 地点信息（从GPS坐标反查）\n"
            "• 图片尺寸\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            return

        # 禁用重复操作
        if self._image_metadata_worker and self._image_metadata_worker.isRunning():
            QMessageBox.warning(self, "提示", "图片元数据分析正在进行中...")
            return

        # 启动工作线程
        self._image_metadata_worker = ImageMetadataWorker(self.db_manager)
        self._image_metadata_worker.progress.connect(self._on_image_metadata_progress)
        self._image_metadata_worker.finished.connect(self._on_image_metadata_finished)
        self._image_metadata_worker.error.connect(self._on_image_metadata_error)
        self._image_metadata_worker.start()

        self.statusbar.showMessage("正在分析图片元数据...")
        QApplication.processEvents()

    def _on_image_metadata_progress(self, message: str, current: int, total: int):
        """图片元数据分析进度回调"""
        self.statusbar.showMessage(message)

    def _on_image_metadata_finished(self, result: dict):
        """图片元数据分析完成回调"""
        processed = result.get('processed', 0)
        updated = result.get('updated', 0)
        errors = result.get('errors', 0)
        cancelled = result.get('cancelled', False)

        if cancelled:
            self.statusbar.showMessage("图片元数据分析已取消")
            QMessageBox.information(
                self, "分析取消",
                f"图片元数据分析已取消。\n"
                f"已处理: {processed} 个文件\n"
                f"已更新: {updated} 个文件"
            )
        else:
            self.statusbar.showMessage(
                f"图片元数据分析完成: 处理 {processed} 个，更新 {updated} 个"
            )
            QMessageBox.information(
                self, "分析完成",
                f"图片时空元数据分析完成！\n\n"
                f"处理文件: {processed} 个\n"
                f"更新元数据: {updated} 个\n"
                f"处理错误: {errors} 个"
            )

        # 清理工作线程
        self._image_metadata_worker = None

    def _on_image_metadata_error(self, error_msg: str):
        """图片元数据分析错误回调"""
        self.statusbar.showMessage(f"图片元数据分析失败: {error_msg}")
        QMessageBox.warning(self, "分析失败", error_msg)
        self._image_metadata_worker = None

    def auto_get_categories_from_directory(self):
        """从当前目录结构自动获取分类类别

        获取当前目录的子目录列表（不含文件），作为类别体系。
        使用独立线程调用 LLM 模型，基于类别名补充关键词和类别描述。
        自动保存到语义类别表。
        """
        if not self.current_directory:
            QMessageBox.warning(self, "提示", "请先选择一个目录")
            return

        if not os.path.exists(self.current_directory):
            QMessageBox.warning(self, "错误", f"目录不存在: {self.current_directory}")
            return

        # 获取子目录列表
        try:
            categories = []
            for item in os.listdir(self.current_directory):
                item_path = os.path.join(self.current_directory, item)
                if os.path.isdir(item_path):
                    categories.append(item)

            if not categories:
                QMessageBox.information(self, "提示", "当前目录下没有子目录，无法生成类别体系")
                return

            # 按名称排序
            categories.sort()

            # 生成默认名称
            dir_name = os.path.basename(self.current_directory)
            default_name = f"{dir_name}目录结构"

            # 弹出对话框让用户命名
            from PyQt5.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(
                self, "命名类别体系",
                "请为类别体系命名:",
                text=default_name
            )

            if ok and name:
                # 保存数据供线程回调使用
                self._pending_category_system_name = name
                self._pending_category_list = categories

                # 禁用菜单项，防止重复操作
                self.statusbar.showMessage("正在使用 AI 生成类别信息，请稍候...")
                QApplication.processEvents()

                # 启动工作线程
                self._generate_category_worker = GenerateCategoryWorker(categories)
                self._generate_category_worker.progress.connect(self._on_generate_category_progress)
                self._generate_category_worker.finished.connect(self._on_generate_category_finished)
                self._generate_category_worker.start()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取目录结构失败: {str(e)}")

    def _on_generate_category_progress(self, message: str, progress: int):
        """生成类别信息进度回调"""
        self.statusbar.showMessage(message)

    def _on_generate_category_finished(self, result: dict):
        """生成类别信息完成回调"""
        if not result.get('success', False):
            QMessageBox.warning(self, "生成失败", f"生成类别信息失败: {result.get('error', '未知错误')}")
            return

        name = self._pending_category_system_name
        categories = self._pending_category_list
        category_info = result.get('category_info', {})
        used_llm = result.get('used_llm', False)

        # 添加到分类面板的类别体系
        success = self.classification_panel.add_category_system(name, categories, category_info)
        if success:
            # 自动保存到数据库的语义类别表
            self._save_category_system_to_database(name, categories, category_info)

            self.statusbar.showMessage(f"已创建并保存类别体系 '{name}'，包含 {len(categories)} 个类别")

            if used_llm:
                QMessageBox.information(
                    self, "成功",
                    f"已创建类别体系 '{name}'\n类别: {', '.join(categories)}\n已使用 AI 生成类别描述和关键词\n已保存到数据库"
                )
            else:
                QMessageBox.information(
                    self, "成功",
                    f"已创建类别体系 '{name}'\n类别: {', '.join(categories)}\n已保存到数据库\n（LLM 服务不可用，使用默认描述）"
                )
        else:
            QMessageBox.warning(self, "失败", f"类别体系 '{name}' 已存在")

        # 清理工作线程引用
        self._generate_category_worker = None

    def _save_category_system_to_database(self, system_name: str, categories: List[str],
                                            category_info: Dict[str, Dict[str, Any]]):
        """保存类别体系到数据库的语义类别表

        Args:
            system_name: 类别体系名称
            categories: 类别名称列表
            category_info: 类别信息字典
        """
        if not self.db_manager:
            print("[MainWindow] 数据库管理器未初始化，无法保存类别体系")
            return

        try:
            for category in categories:
                info = category_info.get(category, {})
                description = info.get("description", f"{category}相关文件")
                keywords = info.get("keywords", [])

                self.db_manager.add_semantic_category(
                    category_name=category,
                    description=description,
                    keywords=keywords,
                    category_system_name=system_name
                )

            print(f"[MainWindow] 已保存类别体系 '{system_name}' 到数据库，包含 {len(categories)} 个类别")

        except Exception as e:
            print(f"[MainWindow] 保存类别体系到数据库失败: {e}")
            QMessageBox.warning(self, "保存失败", f"保存类别体系到数据库时出错：{str(e)}")

    def _generate_category_info_with_ollama(self, categories: list) -> dict:
        """使用 Ollama 为类别生成描述和关键词

        Args:
            categories: 类别名称列表

        Returns:
            类别信息字典，格式为 {类别名: {"description": "描述", "keywords": ["关键词"]}}
        """
        try:
            from models.model_manager import get_llm_client, is_llm_available, get_llm_type

            client = get_llm_client()

            # 检查 LLM 服务是否可用
            if not is_llm_available():
                print(f"[MainWindow] {get_llm_type()} 服务不可用，使用默认类别信息")
                return self._get_default_category_info(categories)

            # 显示进度提示
            self.statusbar.showMessage(f"正在使用 AI ({get_llm_type()}) 生成 {len(categories)} 个类别的描述和关键词...")
            QApplication.processEvents()  # 强制刷新 UI

            # 批量生成类别信息
            category_info = client.generate_category_info_batch(categories)

            self.statusbar.showMessage("类别信息生成完成")
            return category_info

        except Exception as e:
            print(f"[MainWindow] 调用 LLM 失败: {e}，使用默认类别信息")
            return self._get_default_category_info(categories)

    def _get_default_category_info(self, categories: list) -> dict:
        """生成默认的类别信息

        Args:
            categories: 类别名称列表

        Returns:
            默认类别信息字典
        """
        return {
            cat: {
                "description": f"{cat}相关文件",
                "keywords": []
            }
            for cat in categories
        }
    
    def clear_analysis_history(self):
        """清空历史分析数据"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有历史分析数据吗？\n这将删除所有文件记录、数据块、语义块、分类结果和类别体系。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.clear_all_data()
                if success:
                    QMessageBox.information(self, "清空成功", "所有历史分析数据已清空")
                    self.statusbar.showMessage("历史数据已清空")
                    # 清空分类面板的分类结果
                    self.classification_panel.set_classification_results({})
                    # 清空分类面板的类别体系
                    self.classification_panel.clear_category_systems()
                    # 从配置文件重新加载默认类别体系
                    self._load_category_systems_from_config()
                else:
                    QMessageBox.warning(self, "清空失败", "清空历史数据时出错，请查看控制台日志")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清空历史数据失败: {str(e)}")

    def clear_analysis_history_keep_categories(self):
        """清空历史分析数据但保留类别体系"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空历史分析数据吗？\n\n将删除：文件记录、数据块、语义块、分类结果\n将保留：类别体系",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.clear_all_data_except_categories()
                if success:
                    QMessageBox.information(self, "清空成功", "历史分析数据已清空，类别体系已保留")
                    self.statusbar.showMessage("历史数据已清空（保留类别体系）")
                    # 清空分类面板
                    self.classification_panel.set_classification_results({})
                else:
                    QMessageBox.warning(self, "清空失败", "清空历史数据时出错，请查看控制台日志")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清空历史数据失败: {str(e)}")

    def clear_classification_results_history(self):
        """清空历史分类结果"""
        from database import FileStatus

        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有历史分类结果吗？\n这将删除所有文件的分类结果，但保留文件记录和语义块数据。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.clear_classification_results()
                if success:
                    QMessageBox.information(self, "清空成功", "所有历史分类结果已清空")
                    self.statusbar.showMessage("分类结果已清空")
                    # 清空分类面板
                    self.classification_panel.set_classification_results({})
                    # 清空文件表中的语义类别
                    files = self.db_manager.get_files_by_status(FileStatus.PENDING)
                    files.extend(self.db_manager.get_files_by_status(FileStatus.PARSED))
                    files.extend(self.db_manager.get_files_by_status(FileStatus.PRELIMINARY))
                    files.extend(self.db_manager.get_files_by_status(FileStatus.DEEP))
                    for file_record in files:
                        self.db_manager.update_file_semantic_categories(file_record.id, [])
                else:
                    QMessageBox.warning(self, "清空失败", "清空分类结果时出错，请查看控制台日志")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清空分类结果失败: {str(e)}")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
            "<h2>文件分析管理器</h2>"
            "<p>版本: 1.0.0</p>"
            "<p>基于文件分析引擎的本地文件管理工具</p>"
            "<p>支持多种文件格式的解析、预览和语义分析</p>"
        )
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.wait(1000)

        # 停止性能监控
        try:
            perf_monitor = get_performance_monitor()
            perf_monitor.stop()
        except Exception as e:
            print(f"停止性能监控失败: {e}")

        # 结束日志会话（如果日志已启用）
        logging_config = self.config.get('logging', {})
        if logging_config.get('enabled', True):
            try:
                processing_logger.end_session()
            except Exception as e:
                print(f"关闭日志失败: {e}")

        event.accept()


def main():
    """主入口函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("文件分析管理器")
    app.setApplicationVersion("1.0.0")
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
