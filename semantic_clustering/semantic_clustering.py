from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import numpy as np
from enum import Enum
import sys
import os

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)


@dataclass
class ClusterResult:
    block_id: str
    cluster_id: int
    cluster_name: str
    confidence: float
    distance_to_center: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'block_id': self.block_id,
            'cluster_id': self.cluster_id,
            'cluster_name': self.cluster_name,
            'confidence': self.confidence,
            'distance_to_center': self.distance_to_center
        }


@dataclass
class SemanticCategory:
    name: str
    description: str
    keywords: List[str]
    center_vector: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'keywords': self.keywords,
            'center_vector': self.center_vector.tolist() if self.center_vector is not None else None
        }


class DistanceMetric(Enum):
    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    MANHATTAN = "manhattan"


class SemanticClustering:
    DEFAULT_CATEGORIES = [
        SemanticCategory(
            name="技术文档",
            description="技术规范、API文档、技术手册等",
            keywords=["技术", "API", "接口", "开发", "代码", "系统", "架构", "配置", "部署", "服务器"]
        ),
        SemanticCategory(
            name="商业报告",
            description="商业计划、市场分析、财务报告等",
            keywords=["市场", "销售", "收入", "利润", "客户", "竞争", "战略", "投资", "商业", "业务"]
        ),
        SemanticCategory(
            name="学术论文",
            description="研究论文、学术文章、研究报告等",
            keywords=["研究", "实验", "方法", "结果", "分析", "理论", "模型", "数据", "论文", "引用"]
        ),
        SemanticCategory(
            name="会议演示",
            description="会议PPT、演讲稿、培训材料等",
            keywords=["会议", "演示", "培训", "演讲", "PPT", "展示", "介绍", "汇报", "方案", "计划"]
        ),
        SemanticCategory(
            name="合同协议",
            description="合同、协议、法律文件等",
            keywords=["合同", "协议", "条款", "甲方", "乙方", "法律", "责任", "义务", "权利", "签署"]
        ),
        SemanticCategory(
            name="产品说明",
            description="产品手册、使用指南、说明书等",
            keywords=["产品", "功能", "使用", "操作", "说明", "指南", "特性", "规格", "型号", "安装"]
        ),
        SemanticCategory(
            name="新闻资讯",
            description="新闻报道、新闻稿、媒体文章等",
            keywords=["新闻", "报道", "发布", "消息", "媒体", "记者", "事件", "宣布", "最新", "动态"]
        ),
        SemanticCategory(
            name="个人文档",
            description="简历、个人陈述、信函等",
            keywords=["个人", "简历", "经历", "教育", "技能", "自我", "介绍", "申请", "工作", "职位"]
        ),
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        self.categories: List[SemanticCategory] = []
        self._category_vectors: List[np.ndarray] = []
        self._embedding_model = None
        self._is_initialized = False
        
        self.distance_metric = DistanceMetric(
            self.config.get('distance_metric', 'cosine')
        )
        
        self._init_categories()
    
    def _init_categories(self):
        custom_categories = self.config.get('categories', [])
        
        if custom_categories:
            for cat_data in custom_categories:
                self.categories.append(SemanticCategory(
                    name=cat_data['name'],
                    description=cat_data.get('description', ''),
                    keywords=cat_data.get('keywords', [])
                ))
        else:
            self.categories = self.DEFAULT_CATEGORIES.copy()
    
    def initialize(self, embedding_model=None):
        if embedding_model:
            self._embedding_model = embedding_model
        else:
            SentenceTransformerEmbedding = None
            
            try:
                from semantic_representation.semantic_representation import SentenceTransformerEmbedding
            except ImportError:
                try:
                    from .semantic_representation import SentenceTransformerEmbedding
                except ImportError:
                    try:
                        from ..semantic_representation import SentenceTransformerEmbedding
                    except ImportError:
                        try:
                            import importlib.util
                            import os
                            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            module_path = os.path.join(base_dir, 'semantic_representation', 'semantic_representation.py')
                            if os.path.exists(module_path):
                                spec = importlib.util.spec_from_file_location('semantic_representation', module_path)
                                module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(module)
                                SentenceTransformerEmbedding = module.SentenceTransformerEmbedding
                        except Exception as e:
                            raise ImportError(
                                f"无法加载 SentenceTransformerEmbedding: {str(e)}. "
                                "请确保已安装 sentence-transformers: pip install sentence-transformers"
                            )
            
            if SentenceTransformerEmbedding is not None:
                self._embedding_model = SentenceTransformerEmbedding()
            else:
                raise ImportError(
                    "sentence-transformers is required for clustering. "
                    "Install with: pip install sentence-transformers"
                )
        
        self._compute_category_centers()
        self._is_initialized = True
    
    def _compute_category_centers(self):
        self._category_vectors = []
        
        for category in self.categories:
            texts = [category.description] + category.keywords
            vectors = self._embedding_model.encode(texts)
            center = np.mean(vectors, axis=0)
            category.center_vector = center
            self._category_vectors.append(center)
    
    def cluster(self, block) -> ClusterResult:
        from semantic_representation import SemanticBlock
        
        if not self._is_initialized:
            raise RuntimeError("Clustering not initialized. Call initialize() first.")
        
        if not isinstance(block, SemanticBlock):
            raise TypeError(f"Expected SemanticBlock, got {type(block)}")
        
        if block.semantic_vector is None:
            if block.text_description:
                vector = self._embedding_model.encode_single(block.text_description)
            else:
                raise ValueError("Block has no semantic vector or text description")
        else:
            vector = block.semantic_vector
        
        distances = []
        for i, center in enumerate(self._category_vectors):
            dist = self._compute_distance(vector, center)
            distances.append((i, dist))
        
        distances.sort(key=lambda x: x[1])
        best_idx, best_dist = distances[0]
        
        confidence = self._compute_confidence(distances)
        
        return ClusterResult(
            block_id=block.block_id,
            cluster_id=best_idx,
            cluster_name=self.categories[best_idx].name,
            confidence=confidence,
            distance_to_center=best_dist
        )
    
    def cluster_batch(self, blocks: List) -> List[ClusterResult]:
        from semantic_representation import SemanticBlock
        
        if not self._is_initialized:
            raise RuntimeError("Clustering not initialized. Call initialize() first.")
        
        results = []
        vectors = []
        
        for block in blocks:
            if not isinstance(block, SemanticBlock):
                raise TypeError(f"Expected SemanticBlock, got {type(block)}")
            
            if block.semantic_vector is not None:
                vectors.append(block.semantic_vector)
            elif block.text_description:
                vec = self._embedding_model.encode_single(block.text_description)
                vectors.append(vec)
            else:
                vectors.append(None)
        
        for i, (block, vector) in enumerate(zip(blocks, vectors)):
            if vector is None:
                results.append(ClusterResult(
                    block_id=block.block_id,
                    cluster_id=-1,
                    cluster_name="未分类",
                    confidence=0.0,
                    distance_to_center=float('inf')
                ))
                continue
            
            distances = []
            for j, center in enumerate(self._category_vectors):
                dist = self._compute_distance(vector, center)
                distances.append((j, dist))
            
            distances.sort(key=lambda x: x[1])
            best_idx, best_dist = distances[0]
            
            confidence = self._compute_confidence(distances)
            
            results.append(ClusterResult(
                block_id=block.block_id,
                cluster_id=best_idx,
                cluster_name=self.categories[best_idx].name,
                confidence=confidence,
                distance_to_center=best_dist
            ))
        
        return results
    
    def _compute_distance(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        if self.distance_metric == DistanceMetric.EUCLIDEAN:
            return float(np.linalg.norm(vec1 - vec2))
        elif self.distance_metric == DistanceMetric.COSINE:
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 1.0
            return float(1 - np.dot(vec1, vec2) / (norm1 * norm2))
        elif self.distance_metric == DistanceMetric.MANHATTAN:
            return float(np.sum(np.abs(vec1 - vec2)))
        else:
            return float(np.linalg.norm(vec1 - vec2))
    
    def _compute_confidence(self, distances: List[Tuple[int, float]]) -> float:
        if len(distances) < 2:
            return 1.0
        
        best_dist = distances[0][1]
        second_dist = distances[1][1]
        
        if second_dist == 0:
            return 0.5
        
        ratio = best_dist / second_dist
        
        confidence = 1 - ratio
        confidence = max(0.0, min(1.0, confidence))
        
        return confidence
    
    def add_category(self, category: SemanticCategory):
        if not self._is_initialized:
            self.categories.append(category)
            return
        
        if category.center_vector is None and self._embedding_model:
            texts = [category.description] + category.keywords
            vectors = self._embedding_model.encode(texts)
            category.center_vector = np.mean(vectors, axis=0)
        
        self.categories.append(category)
        if category.center_vector is not None:
            self._category_vectors.append(category.center_vector)
    
    def remove_category(self, name: str) -> bool:
        for i, cat in enumerate(self.categories):
            if cat.name == name:
                self.categories.pop(i)
                if i < len(self._category_vectors):
                    self._category_vectors.pop(i)
                return True
        return False
    
    def get_category_names(self) -> List[str]:
        return [cat.name for cat in self.categories]
    
    def get_category_by_name(self, name: str) -> Optional[SemanticCategory]:
        for cat in self.categories:
            if cat.name == name:
                return cat
        return None
    
    def get_cluster_distribution(self, results: List[ClusterResult]) -> Dict[str, int]:
        distribution = {}
        for result in results:
            name = result.cluster_name
            distribution[name] = distribution.get(name, 0) + 1
        return distribution
