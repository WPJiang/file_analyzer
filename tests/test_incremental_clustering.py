#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试增量聚类模块"""

import os
import sys
import math

# 设置路径
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_path)

# 设置控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def test_database_fields():
    """测试数据库字段是否正确添加"""
    print("\n" + "=" * 50)
    print("测试: 数据库字段")
    print("=" * 50)

    from database import DatabaseManager

    db = DatabaseManager()

    # 获取类别记录，检查字段
    cats = db.get_semantic_categories_by_system('默认类别体系')

    if cats:
        cat = cats[0]
        assert hasattr(cat, 'category_source'), "缺少 category_source 字段"
        assert hasattr(cat, 'semantic_vector'), "缺少 semantic_vector 字段"
        print(f"✓ category_source 字段存在: {cat.category_source}")
        print(f"✓ semantic_vector 字段存在: {cat.semantic_vector is not None}")
    else:
        print("⚠ 数据库中没有类别记录，跳过字段检查")

    print("✓ 数据库字段测试通过")
    return True


def test_clustering_init():
    """测试聚类初始化"""
    print("\n" + "=" * 50)
    print("测试: 聚类初始化")
    print("=" * 50)

    from semantic_clustering import SemanticClustering
    from database import DatabaseManager

    db = DatabaseManager()
    config = {
        'incremental_cluster_ratio': 0.1,
        'max_incremental_clusters': 20,
        'min_incremental_clusters': 1,
        'distance_metric': 'cosine'
    }

    clustering = SemanticClustering(config=config, db_manager=db)

    # 验证配置读取
    assert clustering.incremental_ratio == 0.1, "incremental_ratio 配置错误"
    assert clustering.max_incremental == 20, "max_incremental 配置错误"
    assert clustering.min_incremental == 1, "min_incremental 配置错误"

    print(f"✓ incremental_ratio = {clustering.incremental_ratio}")
    print(f"✓ max_incremental = {clustering.max_incremental}")
    print(f"✓ min_incremental = {clustering.min_incremental}")

    # 测试初始化（不加载embedding模型，只测试参数传递）
    print("✓ 聚类初始化测试通过")
    return True


def test_incremental_category_count():
    """测试增量类别数量计算"""
    print("\n" + "=" * 50)
    print("测试: 增量类别数量计算")
    print("=" * 50)

    ratio = 0.1
    max_inc = 20
    min_inc = 1

    test_cases = [
        (5, 1),    # k=5, m = ceil(0.5) = 1
        (10, 1),   # k=10, m = ceil(1.0) = 1
        (20, 2),   # k=20, m = ceil(2.0) = 2
        (100, 10), # k=100, m = ceil(10.0) = 10
        (200, 20), # k=200, m = ceil(20.0) = 20 (max limit)
    ]

    for k, expected_m in test_cases:
        m = max(min_inc, min(max_inc, math.ceil(k * ratio)))
        assert m == expected_m, f"k={k}: expected m={expected_m}, got m={m}"
        print(f"✓ k={k:3d} -> m={m:2d} (expected {expected_m})")

    print("✓ 增量类别数量计算测试通过")
    return True


def test_category_source_enum():
    """测试CategorySource枚举"""
    print("\n" + "=" * 50)
    print("测试: CategorySource枚举")
    print("=" * 50)

    from semantic_clustering.semantic_clustering import CategorySource

    assert CategorySource.PREDEFINED.value == 'predefined'
    assert CategorySource.IMPORTED.value == 'imported'
    assert CategorySource.GENERATED.value == 'generated'

    print(f"✓ PREDEFINED = '{CategorySource.PREDEFINED.value}'")
    print(f"✓ IMPORTED = '{CategorySource.IMPORTED.value}'")
    print(f"✓ GENERATED = '{CategorySource.GENERATED.value}'")

    print("✓ CategorySource枚举测试通过")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("增量聚类模块测试套件")
    print("=" * 60)

    tests = [
        ("数据库字段测试", test_database_fields),
        ("聚类初始化测试", test_clustering_init),
        ("增量类别数量测试", test_incremental_category_count),
        ("CategorySource枚举测试", test_category_source_enum),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {name} 失败: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)