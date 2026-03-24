"""全局模型管理器

单例模式管理所有机器学习模型，避免重复加载，优化内存占用和初始化时间。

优化效果:
1. SentenceTransformer模型 (约420MB) 只加载一次
2. PaddleOCR模型 (约100-200MB) 只加载一次
3. jieba词典 (约50MB) 只加载一次
4. LLM客户端 (支持Ollama本地模型和云侧大模型)
"""

import os
import sys
import threading
import shutil
from typing import Optional, Any, Callable, Dict, List
from functools import lru_cache

# 添加父目录到路径
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)


class ModelManager:
    """全局模型管理器 - 单例模式

    管理以下模型的生命周期:
    1. SentenceTransformer embedding模型
    2. PaddleOCR模型
    3. jieba分词器
    4. LLM客户端 (支持Ollama本地模型和云侧大模型)

    线程安全，支持延迟加载。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._embedding_model = None
        self._embedding_model_name = None
        self._ocr_instance = None
        self._ocr_engine = None  # 保存 PaddleOCR 引用用于内存清理
        self._ocr_initialized = False
        self._jieba_initialized = False
        self._config = None  # 配置缓存

        # LLM客户端 (统一接口，支持Ollama和云侧模型)
        self._llm_client = None
        self._llm_type = None  # 'ollama' 或 'cloud'
        self._llm_initialized = False

        # 模型锁
        self._embedding_lock = threading.Lock()
        self._ocr_lock = threading.Lock()
        self._jieba_lock = threading.Lock()
        self._llm_lock = threading.Lock()

        # 本地模型路径
        self._local_model_path = self._find_local_model()

        # 本地OCR模型路径
        self._local_ocr_model_path = self._find_local_ocr_model()

        self._initialized = True

    def _load_config(self):
        """加载配置文件"""
        if self._config is not None:
            return self._config

        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
        if os.path.exists(config_path):
            try:
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"[ModelManager] 加载配置文件失败: {e}")
                self._config = {}
        else:
            self._config = {}

        return self._config

    def _find_local_model(self) -> Optional[str]:
        """查找本地embedding模型路径"""
        model_name = 'paraphrase-multilingual-MiniLM-L12-v2'

        possible_paths = []

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_paths.append(os.path.join(base_dir, 'models', model_name))

        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            possible_paths.append(os.path.join(exe_dir, 'models', model_name))
            possible_paths.append(os.path.join(exe_dir, '_internal', 'models', model_name))

        for path in possible_paths:
            if os.path.exists(path) and os.path.exists(os.path.join(path, 'config.json')):
                print(f"[ModelManager] 找到本地模型: {path}")
                return path

        return None

    def _find_local_ocr_model(self) -> Optional[str]:
        """查找本地OCR模型路径

        PaddleOCR模型目录结构:
        models/paddleocr/
        ├── det/                    # 文本检测模型
        │   └── ch_PP-OCRv4_det_infer/
        │       ├── inference.pdmodel
        │       ├── inference.pdiparams
        │       └── inference.pdiparams.info
        ├── rec/                    # 文本识别模型
        │   └── ch_PP-OCRv4_rec_infer/
        │       └── ...
        └── cls/                    # 文本方向分类模型
            └── ch_ppocr_mobile_v2.0_cls_infer/
                └── ...

        Returns:
            本地OCR模型目录路径，不存在则返回None
        """
        possible_paths = []

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_paths.append(os.path.join(base_dir, 'models', 'paddleocr'))

        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            possible_paths.append(os.path.join(exe_dir, 'models', 'paddleocr'))
            possible_paths.append(os.path.join(exe_dir, '_internal', 'models', 'paddleocr'))

        for path in possible_paths:
            # 检查是否存在必要的模型文件
            det_path = os.path.join(path, 'det', 'ch_PP-OCRv4_det_infer', 'inference.pdmodel')
            rec_path = os.path.join(path, 'rec', 'ch_PP-OCRv4_rec_infer', 'inference.pdmodel')
            cls_path = os.path.join(path, 'cls', 'ch_ppocr_mobile_v2.0_cls_infer', 'inference.pdmodel')

            if os.path.exists(det_path) and os.path.exists(rec_path) and os.path.exists(cls_path):
                print(f"[ModelManager] 找到本地OCR模型: {path}")
                return path

        return None

    def _save_ocr_model_to_local(self, source_dir: str, target_dir: str):
        """将OCR模型从源目录复制到本地models目录

        Args:
            source_dir: 源目录（通常是~/.paddleocr/whl）
            target_dir: 目标目录（通常是models/paddleocr）
        """
        try:
            print(f"[ModelManager] 正在保存OCR模型到本地: {target_dir}")

            # 确保目标目录存在
            os.makedirs(target_dir, exist_ok=True)

            # 需要复制的模型目录
            model_subdirs = [
                ('det', 'ch', 'ch_PP-OCRv4_det_infer'),
                ('rec', 'ch', 'ch_PP-OCRv4_rec_infer'),
                ('cls', 'ch_ppocr_mobile_v2.0_cls_infer'),
            ]

            for item in model_subdirs:
                if len(item) == 3:
                    category, subcategory, model_name = item
                    src_path = os.path.join(source_dir, category, subcategory, model_name)
                    dst_path = os.path.join(target_dir, category, model_name)
                else:
                    category, model_name = item
                    src_path = os.path.join(source_dir, category, model_name)
                    dst_path = os.path.join(target_dir, category, model_name)

                if os.path.exists(src_path):
                    # 创建目标目录
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                    # 复制整个模型目录
                    if os.path.exists(dst_path):
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)
                    print(f"[ModelManager] 已复制: {model_name}")

            print("[ModelManager] OCR模型保存完成")
            return True

        except Exception as e:
            print(f"[ModelManager] 保存OCR模型失败: {e}")
            return False

    def _save_downloaded_ocr_model(self):
        """将已下载的OCR模型保存到本地models目录

        PaddleOCR默认将模型下载到~/.paddleocr/whl目录，
        此方法将其复制到项目的models/paddleocr目录。
        """
        try:
            # 获取默认的PaddleOCR模型目录
            home_dir = os.path.expanduser('~')
            default_ocr_dir = os.path.join(home_dir, '.paddleocr', 'whl')

            if not os.path.exists(default_ocr_dir):
                print("[ModelManager] 未找到PaddleOCR默认模型目录")
                return False

            # 确定目标目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            target_dir = os.path.join(base_dir, 'models', 'paddleocr')

            return self._save_ocr_model_to_local(default_ocr_dir, target_dir)

        except Exception as e:
            print(f"[ModelManager] 保存下载的OCR模型失败: {e}")
            return False

    def get_embedding_model(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """获取embedding模型实例

        延迟加载，首次调用时才初始化模型。
        模型只会加载一次，后续调用直接返回已加载的实例。

        Args:
            model_name: 模型名称

        Returns:
            SentenceTransformer模型实例
        """
        if self._embedding_model is not None and self._embedding_model_name == model_name:
            return self._embedding_model

        with self._embedding_lock:
            # 双重检查
            if self._embedding_model is not None and self._embedding_model_name == model_name:
                return self._embedding_model

            try:
                from sentence_transformers import SentenceTransformer

                if self._local_model_path:
                    print(f"[ModelManager] 从本地路径加载embedding模型: {self._local_model_path}")
                    self._embedding_model = SentenceTransformer(self._local_model_path)
                else:
                    print(f"[ModelManager] 从HuggingFace Hub加载embedding模型: {model_name}")
                    self._embedding_model = SentenceTransformer(model_name)

                self._embedding_model_name = model_name
                print("[ModelManager] embedding模型加载完成")

            except ImportError:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install sentence-transformers"
                )

        return self._embedding_model

    def get_ocr_instance(self, use_ocr: bool = True):
        """获取OCR实例

        延迟加载，首次调用时才初始化OCR模型。
        每次OCR调用后自动清理内部张量，减少内存占用。

        支持两种加载模式：
        1. 本地加载：从models/paddleocr目录加载
        2. 联网下载：当本地模型不存在时，自动下载并保存到本地

        Args:
            use_ocr: 是否使用OCR

        Returns:
            OCR函数或None
        """
        if not use_ocr:
            return None

        if self._ocr_initialized and self._ocr_instance is not None:
            return self._ocr_instance

        with self._ocr_lock:
            # 双重检查
            if self._ocr_initialized:
                return self._ocr_instance

            try:
                from paddleocr import PaddleOCR

                # 从配置文件读取MKL-DNN设置
                config = self._load_config()
                semantic_config = config.get('semantic_representation', {})
                image_config = semantic_config.get('image', {})
                enable_mkldnn = image_config.get('enable_mkldnn', True)
                max_image_width = image_config.get('ocr_max_image_width', 1500)
                config_ocr_path = image_config.get('ocr_model_path', '')

                print(f"[ModelManager] MKL-DNN优化: {'启用' if enable_mkldnn else '禁用'}")

                # 确定使用的OCR模型路径（优先级：配置文件 > 自动查找 > 联网下载）
                ocr_model_path = None
                if config_ocr_path and os.path.exists(config_ocr_path):
                    ocr_model_path = config_ocr_path
                    print(f"[ModelManager] 使用配置文件指定的OCR模型路径: {ocr_model_path}")
                elif self._local_ocr_model_path:
                    ocr_model_path = self._local_ocr_model_path

                # 判断是本地加载还是联网下载
                if ocr_model_path:
                    # 本地加载模式
                    print(f"[ModelManager] 从本地路径加载OCR模型: {ocr_model_path}")
                    print("[ModelManager] 正在加载PaddleOCR模型...")

                    det_model_dir = os.path.join(ocr_model_path, 'det', 'ch_PP-OCRv4_det_infer')
                    rec_model_dir = os.path.join(ocr_model_path, 'rec', 'ch_PP-OCRv4_rec_infer')
                    cls_model_dir = os.path.join(ocr_model_path, 'cls', 'ch_ppocr_mobile_v2.0_cls_infer')

                    ocr = PaddleOCR(
                        use_angle_cls=True,
                        lang='ch',
                        use_gpu=False,
                        show_log=False,
                        enable_mkldnn=enable_mkldnn,
                        det_model_dir=det_model_dir,
                        rec_model_dir=rec_model_dir,
                        cls_model_dir=cls_model_dir
                    )
                else:
                    # 联网下载模式
                    print("[ModelManager] 本地OCR模型不存在，从网络下载...")
                    print("[ModelManager] 正在加载PaddleOCR模型（首次加载需要下载模型，请耐心等待）...")

                    ocr = PaddleOCR(
                        use_angle_cls=True,
                        lang='ch',
                        use_gpu=False,
                        show_log=False,
                        enable_mkldnn=enable_mkldnn
                    )

                    # 下载完成后，保存到本地
                    self._save_downloaded_ocr_model()

                # 保存OCR引擎引用用于内存清理
                self._ocr_engine = ocr

                print("[ModelManager] PaddleOCR模型加载完成")

                def paddleocr_ocr(image_path: str) -> Optional[str]:
                    """OCR识别函数 - 带内存优化和图片预处理

                    Args:
                        image_path: 图片路径

                    Returns:
                        识别的文本
                    """
                    # 使用配置的最大宽度
                    current_max_width = max_image_width
                    try:
                        # 图片预处理：缩小大图以加速OCR
                        processed_path = image_path
                        temp_file = None

                        try:
                            from PIL import Image
                            with Image.open(image_path) as img:
                                width, height = img.size
                                # 如果图片宽度超过max_width，缩小到max_width
                                # max_width为0表示不缩放
                                if current_max_width > 0 and width > current_max_width:
                                    scale = current_max_width / width
                                    new_width = int(width * scale)
                                    new_height = int(height * scale)
                                    # 使用高质量缩放
                                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                                    # 保存临时文件
                                    import tempfile
                                    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                                    resized_img.save(temp_file.name)
                                    processed_path = temp_file.name
                        except Exception as e:
                            print(f"[ModelManager] 图片预处理失败，使用原图: {e}")
                            processed_path = image_path

                        result = ocr.ocr(processed_path, cls=True)

                        # 清理临时文件
                        if temp_file:
                            try:
                                os.unlink(temp_file.name)
                            except:
                                pass

                        # 清理内部张量，释放内存（关键优化）
                        self._clear_ocr_cache()

                        if result and result[0]:
                            texts = [line[1][0] for line in result[0]]
                            return '\n'.join(texts)
                        return ""
                    except Exception as e:
                        print(f"[ModelManager] OCR识别失败: {e}")
                        # 即使失败也尝试清理
                        self._clear_ocr_cache()
                        return None

                self._ocr_instance = paddleocr_ocr
                self._ocr_initialized = True

            except ImportError as e:
                print(f"[ModelManager] WARNING: paddleocr未安装或导入失败: {e}")
                self._ocr_instance = None
                self._ocr_initialized = True
            except Exception as e:
                print(f"[ModelManager] ERROR: PaddleOCR初始化失败: {e}")
                self._ocr_instance = None
                self._ocr_initialized = True

        return self._ocr_instance

    def _clear_ocr_cache(self):
        """清理OCR模型内部张量，释放内存

        这是解决PaddleOCR内存累积问题的关键优化。
        每次OCR调用后，PaddleOCR会保留中间张量导致内存累积。
        调用此方法可以清理这些张量，显著降低内存占用（约80%）。
        """
        if self._ocr_engine is None:
            return

        try:
            # 清理文本检测器的中间张量
            if hasattr(self._ocr_engine, 'text_detector'):
                detector = self._ocr_engine.text_detector
                if hasattr(detector, 'predictor'):
                    detector.predictor.clear_intermediate_tensor()
        except Exception:
            pass

        try:
            # 清理文本识别器的中间张量
            if hasattr(self._ocr_engine, 'text_recognizer'):
                recognizer = self._ocr_engine.text_recognizer
                if hasattr(recognizer, 'predictor'):
                    recognizer.predictor.clear_intermediate_tensor()
        except Exception:
            pass

        try:
            # 清理文本分类器的中间张量
            if hasattr(self._ocr_engine, 'text_classifier'):
                classifier = self._ocr_engine.text_classifier
                if hasattr(classifier, 'predictor'):
                    classifier.predictor.clear_intermediate_tensor()
        except Exception:
            pass

        # 额外清理：强制垃圾回收和内存释放
        try:
            import gc
            gc.collect()
        except Exception:
            pass

    def init_jieba(self):
        """初始化jieba分词器

        jieba会自动缓存词典，但需要确保首次调用在主线程完成。
        """
        if self._jieba_initialized:
            return

        with self._jieba_lock:
            if self._jieba_initialized:
                return

            try:
                import jieba
                import jieba.analyse

                # 预加载词典
                jieba.initialize()
                print("[ModelManager] jieba分词器初始化完成")

            except ImportError:
                print("[ModelManager] WARNING: jieba未安装")
            except Exception as e:
                print(f"[ModelManager] jieba初始化失败: {e}")

            self._jieba_initialized = True

    def get_llm_client(self):
        """获取LLM客户端实例（统一接口）

        根据配置文件中的llm.type决定使用云侧模型还是Ollama。
        默认使用云侧模型。

        Returns:
            LLM客户端实例（OllamaClient或CloudLLMClient）
        """
        if self._llm_initialized and self._llm_client is not None:
            return self._llm_client

        with self._llm_lock:
            # 双重检查
            if self._llm_initialized:
                return self._llm_client

            # 从配置获取LLM类型
            config = self._load_config()
            llm_config = config.get('llm', {})
            llm_type = llm_config.get('type', 'cloud')

            if llm_type == 'ollama':
                # 使用Ollama本地模型
                self._init_ollama_client(llm_config.get('ollama', {}))
            else:
                # 默认使用云侧模型
                self._init_cloud_llm_client(llm_config.get('cloud', {}))

            self._llm_type = llm_type
            self._llm_initialized = True

        return self._llm_client

    def _init_ollama_client(self, ollama_config: Dict):
        """初始化Ollama客户端"""
        try:
            from models.ollama_client import OllamaClient

            base_url = ollama_config.get('base_url', 'http://localhost:11434')
            model = ollama_config.get('model', 'qwen3.5:0.8b')

            self._llm_client = OllamaClient(base_url, model)
            print(f"[ModelManager] Ollama客户端初始化完成，模型: {model}")

        except ImportError as e:
            print(f"[ModelManager] WARNING: 无法导入OllamaClient: {e}")
            self._llm_client = None
        except Exception as e:
            print(f"[ModelManager] ERROR: Ollama客户端初始化失败: {e}")
            self._llm_client = None

    def _init_cloud_llm_client(self, cloud_config: Dict):
        """初始化云侧LLM客户端"""
        try:
            from models.cloud_llm_client import CloudLLMClient

            self._llm_client = CloudLLMClient(config=cloud_config)
            print(f"[ModelManager] 云侧LLM客户端初始化完成")

        except ImportError as e:
            print(f"[ModelManager] WARNING: 无法导入CloudLLMClient: {e}")
            self._llm_client = None
        except Exception as e:
            print(f"[ModelManager] ERROR: 云侧LLM客户端初始化失败: {e}")
            self._llm_client = None

    def get_ollama_client(self, base_url: str = "http://localhost:11434", model: str = "qwen3.5:0.8b"):
        """获取Ollama客户端实例（兼容旧接口）

        注意：此方法保留用于向后兼容，建议使用get_llm_client()获取统一客户端。

        Args:
            base_url: Ollama服务地址
            model: 模型名称

        Returns:
            OllamaClient实例
        """
        # 如果已初始化且是Ollama类型，直接返回
        if self._llm_initialized and self._llm_type == 'ollama' and self._llm_client is not None:
            return self._llm_client

        # 否则强制使用Ollama初始化
        with self._llm_lock:
            try:
                from models.ollama_client import OllamaClient

                self._llm_client = OllamaClient(base_url, model)
                self._llm_type = 'ollama'
                self._llm_initialized = True
                print(f"[ModelManager] Ollama客户端初始化完成，模型: {model}")

            except ImportError as e:
                print(f"[ModelManager] WARNING: 无法导入OllamaClient: {e}")
                self._llm_client = None
            except Exception as e:
                print(f"[ModelManager] ERROR: Ollama客户端初始化失败: {e}")
                self._llm_client = None

        return self._llm_client

    def generate_image_description(self, image_path: str, detail_level: str = "medium") -> str:
        """使用LLM生成图片描述

        Args:
            image_path: 图片文件路径
            detail_level: 描述详细程度 ("brief", "medium", "detailed")

        Returns:
            图片描述文本
        """
        client = self.get_llm_client()
        if client is None:
            raise RuntimeError("LLM客户端未初始化")
        return client.generate_image_description(image_path, detail_level)

    def classify_image_with_llm(self, image_path: str, categories: List[str] = None) -> Dict[str, Any]:
        """使用LLM对图片进行分类

        Args:
            image_path: 图片文件路径
            categories: 可选的分类列表

        Returns:
            分类结果字典
        """
        client = self.get_llm_client()
        if client is None:
            raise RuntimeError("LLM客户端未初始化")
        return client.classify_image(image_path, categories)

    def classify_image_with_ollama(self, image_path: str, categories: List[str] = None) -> Dict[str, Any]:
        """使用Ollama对图片进行分类（兼容旧接口）

        Args:
            image_path: 图片文件路径
            categories: 可选的分类列表

        Returns:
            分类结果字典
        """
        return self.classify_image_with_llm(image_path, categories)

    def classify_text_with_llm(self, text: str, categories: List[str] = None, category_descriptions: Dict[str, str] = None) -> Dict[str, Any]:
        """使用LLM对文本进行分类

        Args:
            text: 待分类的文本内容
            categories: 可选的分类列表
            category_descriptions: 可选的分类描述字典

        Returns:
            分类结果字典
        """
        client = self.get_llm_client()
        if client is None:
            raise RuntimeError("LLM客户端未初始化")
        return client.classify_text(text, categories, category_descriptions)

    def classify_text_with_ollama(self, text: str, categories: List[str] = None, category_descriptions: Dict[str, str] = None) -> Dict[str, Any]:
        """使用Ollama对文本进行分类（兼容旧接口）

        Args:
            text: 待分类的文本内容
            categories: 可选的分类列表
            category_descriptions: 可选的分类描述字典

        Returns:
            分类结果字典
        """
        return self.classify_text_with_llm(text, categories, category_descriptions)

    def analyze_image_with_llm(self, image_path: str) -> Dict[str, Any]:
        """使用LLM综合分析图片内容

        Args:
            image_path: 图片文件路径

        Returns:
            分析结果字典
        """
        client = self.get_llm_client()
        if client is None:
            raise RuntimeError("LLM客户端未初始化")
        return client.analyze_image_content(image_path)

    def analyze_image_with_ollama(self, image_path: str) -> Dict[str, Any]:
        """使用Ollama综合分析图片内容（兼容旧接口）

        Args:
            image_path: 图片文件路径

        Returns:
            分析结果字典
        """
        return self.analyze_image_with_llm(image_path)

    def is_embedding_loaded(self) -> bool:
        """检查embedding模型是否已加载"""
        return self._embedding_model is not None

    def is_ocr_loaded(self) -> bool:
        """检查OCR模型是否已加载"""
        return self._ocr_instance is not None

    def is_llm_available(self) -> bool:
        """检查LLM服务是否可用"""
        client = self.get_llm_client()
        if client is None:
            return False
        return client.check_service_available()

    def is_ollama_available(self) -> bool:
        """检查Ollama服务是否可用（兼容旧接口）"""
        return self.is_llm_available()

    def get_llm_type(self) -> str:
        """获取当前LLM类型

        Returns:
            'cloud' 或 'ollama'
        """
        return self._llm_type or 'unknown'

    def get_memory_usage(self) -> dict:
        """获取模型内存使用情况"""
        usage = {
            'embedding_loaded': self._embedding_model is not None,
            'ocr_loaded': self._ocr_instance is not None,
            'jieba_initialized': self._jieba_initialized,
            'llm_initialized': self._llm_initialized,
            'llm_type': self._llm_type
        }

        # 尝试获取实际内存使用
        try:
            import psutil
            process = psutil.Process(os.getpid())
            usage['total_memory_mb'] = process.memory_info().rss / 1024 / 1024
        except ImportError:
            pass

        return usage

    def clear_cache(self):
        """清理模型缓存（谨慎使用）

        注意：这会释放模型内存，但下次使用需要重新加载
        """
        with self._embedding_lock:
            self._embedding_model = None
            self._embedding_model_name = None

        with self._ocr_lock:
            self._ocr_instance = None
            self._ocr_engine = None
            self._ocr_initialized = False

        with self._llm_lock:
            self._llm_client = None
            self._llm_type = None
            self._llm_initialized = False

        print("[ModelManager] 模型缓存已清理")

    def aggressive_cleanup(self):
        """积极的内存清理（推荐定期调用）

        在低内存设备上，建议每处理5-10个文件调用一次。
        清理OCR内部张量、Python垃圾回收、尝试释放内存给操作系统。
        """
        # 清理OCR内部张量
        self._clear_ocr_cache()

        # 强制垃圾回收
        import gc
        gc.collect()

        # 尝试释放内存给操作系统（仅在某些平台上有效）
        try:
            import ctypes
            if hasattr(ctypes, 'cdll'):
                # Linux: malloc_trim
                try:
                    ctypes.CDLL('libc.so.6').malloc_trim(0)
                except:
                    pass
        except:
            pass

        print("[ModelManager] 积极内存清理完成")


# 全局访问函数
def get_model_manager() -> ModelManager:
    """获取全局ModelManager实例"""
    return ModelManager()


def get_embedding_model(model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
    """获取embedding模型的便捷函数"""
    return get_model_manager().get_embedding_model(model_name)


def get_ocr_instance(use_ocr: bool = True):
    """获取OCR实例的便捷函数"""
    return get_model_manager().get_ocr_instance(use_ocr)


def init_jieba():
    """初始化jieba的便捷函数"""
    return get_model_manager().init_jieba()


def aggressive_cleanup():
    """积极内存清理的便捷函数"""
    return get_model_manager().aggressive_cleanup()


# ==================== LLM相关便捷函数 ====================

def get_llm_client():
    """获取LLM客户端的便捷函数（推荐使用）"""
    return get_model_manager().get_llm_client()


def get_ollama_client(base_url: str = "http://localhost:11434", model: str = "qwen3.5:0.8b"):
    """获取Ollama客户端的便捷函数（兼容旧接口）"""
    return get_model_manager().get_ollama_client(base_url, model)


def generate_image_description(image_path: str, detail_level: str = "medium") -> str:
    """生成图片描述的便捷函数"""
    return get_model_manager().generate_image_description(image_path, detail_level)


def classify_image_with_llm(image_path: str, categories: List[str] = None) -> Dict[str, Any]:
    """使用LLM对图片进行分类的便捷函数（推荐使用）"""
    return get_model_manager().classify_image_with_llm(image_path, categories)


def classify_image_with_ollama(image_path: str, categories: List[str] = None) -> Dict[str, Any]:
    """使用Ollama对图片进行分类的便捷函数（兼容旧接口）"""
    return get_model_manager().classify_image_with_llm(image_path, categories)


def classify_text_with_llm(text: str, categories: List[str] = None, category_descriptions: Dict[str, str] = None) -> Dict[str, Any]:
    """使用LLM对文本进行分类的便捷函数（推荐使用）"""
    return get_model_manager().classify_text_with_llm(text, categories, category_descriptions)


def classify_text_with_ollama(text: str, categories: List[str] = None, category_descriptions: Dict[str, str] = None) -> Dict[str, Any]:
    """使用Ollama对文本进行分类的便捷函数（兼容旧接口）"""
    return get_model_manager().classify_text_with_llm(text, categories, category_descriptions)


def analyze_image_with_llm(image_path: str) -> Dict[str, Any]:
    """使用LLM综合分析图片的便捷函数（推荐使用）"""
    return get_model_manager().analyze_image_with_llm(image_path)


def analyze_image_with_ollama(image_path: str) -> Dict[str, Any]:
    """使用Ollama综合分析图片的便捷函数（兼容旧接口）"""
    return get_model_manager().analyze_image_with_llm(image_path)


def is_llm_available() -> bool:
    """检查LLM服务是否可用的便捷函数"""
    return get_model_manager().is_llm_available()


def get_llm_type() -> str:
    """获取当前LLM类型的便捷函数"""
    return get_model_manager().get_llm_type()
