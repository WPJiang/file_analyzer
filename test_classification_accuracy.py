"""
分类正确率测试脚本

扫描给定目录结构，每个文件的真实分类标签为其所在目录名。
读取数据库中的分类结果，计算各类别的精确率和召回率。

使用方法:
    python test_classification_accuracy.py --directory "D:/测试目录" --category-system "目录结构类别体系"

参数:
    --directory: 要测试的目录路径
    --category-system: 使用的类别体系名称（可选，默认使用第一个可用的类别体系）
"""

import os
import sys
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple, Set

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from database.database import DatabaseManager, FileStatus


def get_ground_truth_labels(directory: str) -> Dict[str, str]:
    """
    扫描目录，获取每个文件的真实标签（所在目录名）

    Args:
        directory: 根目录路径

    Returns:
        文件路径 -> 真实标签 的字典
    """
    ground_truth = {}

    # 获取根目录下的一级子目录作为类别
    categories = set()
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            categories.add(item)

    print(f"扫描目录: {directory}")
    print(f"发现的类别（子目录）: {sorted(categories)}")

    # 遍历每个子目录，收集文件
    for category in categories:
        category_path = os.path.join(directory, category)
        for root, dirs, files in os.walk(category_path):
            for file in files:
                file_path = os.path.join(root, file)
                ground_truth[file_path] = category

    print(f"共发现 {len(ground_truth)} 个文件")
    return ground_truth


def get_predicted_labels(db_manager: DatabaseManager, category_system_name: str = None) -> Dict[str, str]:
    """
    从数据库获取每个文件的预测分类

    Args:
        db_manager: 数据库管理器
        category_system_name: 类别体系名称，为None则使用第一个可用的

    Returns:
        文件路径 -> 预测标签 的字典
    """
    predicted = {}

    # 获取所有已分析的文件
    files = db_manager.get_files_by_status(FileStatus.PRELIMINARY)

    if not files:
        print("数据库中没有已分析的文件")
        return predicted

    print(f"数据库中共有 {len(files)} 个已分析文件")

    # 获取第一个文件的分类结果来确定类别体系
    if category_system_name is None and files:
        first_file = files[0]
        if first_file.semantic_categories:
            category_system_name = first_file.semantic_categories[0].get('category_system_name')

    if category_system_name:
        print(f"使用类别体系: {category_system_name}")
    else:
        print("未找到类别体系，使用所有分类结果")

    # 提取每个文件的主要分类
    for file_record in files:
        if not file_record.semantic_categories:
            continue

        # 筛选指定类别体系的结果
        relevant_categories = file_record.semantic_categories
        if category_system_name:
            relevant_categories = [
                cat for cat in file_record.semantic_categories
                if cat.get('category_system_name') == category_system_name
            ]

        if relevant_categories:
            # 按置信度排序，取最高的作为主要分类
            relevant_categories.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            primary_category = relevant_categories[0].get('category')
            predicted[file_record.file_path] = primary_category

    return predicted


def calculate_metrics(
    ground_truth: Dict[str, str],
    predicted: Dict[str, str]
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    """
    计算分类指标

    Args:
        ground_truth: 真实标签
        predicted: 预测标签

    Returns:
        (各类别指标, 总体指标)
    """
    # 获取所有类别
    all_categories = set(ground_truth.values()) | set(predicted.values())

    # 初始化统计
    # TP: True Positive, FP: False Positive, FN: False Negative
    stats = defaultdict(lambda: {'TP': 0, 'FP': 0, 'FN': 0})

    # 获取共同的文件集合
    common_files = set(ground_truth.keys()) & set(predicted.keys())
    only_in_ground = set(ground_truth.keys()) - set(predicted.keys())
    only_in_predicted = set(predicted.keys()) - set(ground_truth.keys())

    print(f"\n文件统计:")
    print(f"  真实标签文件数: {len(ground_truth)}")
    print(f"  预测标签文件数: {len(predicted)}")
    print(f"  共同文件数: {len(common_files)}")
    print(f"  仅在真实标签中: {len(only_in_ground)}")
    print(f"  仅在预测标签中: {len(only_in_predicted)}")

    # 计算每个类别的 TP, FP, FN
    for file_path in common_files:
        true_label = ground_truth[file_path]
        pred_label = predicted[file_path]

        if true_label == pred_label:
            stats[true_label]['TP'] += 1
        else:
            stats[true_label]['FN'] += 1  # 真实是该类，但预测错误
            stats[pred_label]['FP'] += 1  # 预测是该类，但实际不是

    # 对于仅在预测中的文件，算作预测类的 FP
    for file_path in only_in_predicted:
        pred_label = predicted[file_path]
        stats[pred_label]['FP'] += 1

    # 对于仅在真实标签中的文件，算作真实类的 FN
    for file_path in only_in_ground:
        true_label = ground_truth[file_path]
        stats[true_label]['FN'] += 1

    # 计算精确率和召回率
    metrics = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for category in sorted(all_categories):
        tp = stats[category]['TP']
        fp = stats[category]['FP']
        fn = stats[category]['FN']

        # 精确率 = TP / (TP + FP)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0

        # 召回率 = TP / (TP + FN)
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        # F1分数
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[category] = {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'TP': tp,
            'FP': fp,
            'FN': fn,
            'support': tp + fn  # 该类实际样本数
        }

        total_tp += tp
        total_fp += fp
        total_fn += fn

    # 计算总体指标（宏平均和微平均）
    # 宏平均：各类别指标的算术平均
    macro_precision = sum(m['precision'] for m in metrics.values()) / len(metrics) if metrics else 0
    macro_recall = sum(m['recall'] for m in metrics.values()) / len(metrics) if metrics else 0
    macro_f1 = sum(m['f1'] for m in metrics.values()) / len(metrics) if metrics else 0

    # 微平均：基于总体 TP, FP, FN 计算
    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if (micro_precision + micro_recall) > 0 else 0

    overall = {
        'macro_precision': macro_precision,
        'macro_recall': macro_recall,
        'macro_f1': macro_f1,
        'micro_precision': micro_precision,
        'micro_recall': micro_recall,
        'micro_f1': micro_f1,
        'total_samples': len(common_files),
        'accuracy': total_tp / len(common_files) if common_files else 0  # 整体准确率
    }

    return metrics, overall


def print_results(metrics: Dict[str, Dict[str, float]], overall: Dict[str, float]):
    """打印分类结果报告"""

    print("\n" + "=" * 80)
    print("分类评估报告")
    print("=" * 80)

    # 打印各类别指标
    print("\n各类别指标:")
    print("-" * 80)
    print(f"{'类别':<20} {'精确率':>10} {'召回率':>10} {'F1分数':>10} {'样本数':>10}")
    print("-" * 80)

    for category, m in sorted(metrics.items()):
        print(f"{category:<20} {m['precision']:>10.2%} {m['recall']:>10.2%} {m['f1']:>10.2%} {m['support']:>10}")

    print("-" * 80)

    # 打印总体指标
    print("\n总体指标:")
    print("-" * 80)
    print(f"{'指标':<30} {'宏平均':>15} {'微平均':>15}")
    print("-" * 80)
    print(f"{'精确率 (Precision)':<30} {overall['macro_precision']:>15.2%} {overall['micro_precision']:>15.2%}")
    print(f"{'召回率 (Recall)':<30} {overall['macro_recall']:>15.2%} {overall['micro_recall']:>15.2%}")
    print(f"{'F1分数':<30} {overall['macro_f1']:>15.2%} {overall['micro_f1']:>15.2%}")
    print("-" * 80)
    print(f"{'整体准确率 (Accuracy)':<30} {overall['accuracy']:>15.2%}")
    print(f"{'总样本数':<30} {overall['total_samples']:>15}")
    print("=" * 80)


def generate_confusion_matrix(
    ground_truth: Dict[str, str],
    predicted: Dict[str, str]
) -> Tuple[List[str], List[List[int]]]:
    """
    生成混淆矩阵

    Returns:
        (类别列表, 混淆矩阵)
    """
    # 获取所有类别并排序
    categories = sorted(set(ground_truth.values()) | set(predicted.values()))
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    # 初始化混淆矩阵
    n = len(categories)
    matrix = [[0] * n for _ in range(n)]

    # 填充混淆矩阵
    common_files = set(ground_truth.keys()) & set(predicted.keys())
    for file_path in common_files:
        true_label = ground_truth[file_path]
        pred_label = predicted[file_path]

        true_idx = cat_to_idx[true_label]
        pred_idx = cat_to_idx[pred_label]

        matrix[true_idx][pred_idx] += 1

    return categories, matrix


def print_confusion_matrix(categories: List[str], matrix: List[List[int]]):
    """打印混淆矩阵"""
    n = len(categories)

    print("\n混淆矩阵:")
    print("-" * (12 * (n + 1)))

    # 打印表头
    header = "真实\\预测".ljust(12)
    for cat in categories:
        header += cat[:8].ljust(12)
    print(header)
    print("-" * (12 * (n + 1)))

    # 打印每行
    for i, cat in enumerate(categories):
        row = cat[:8].ljust(12)
        for j in range(n):
            row += str(matrix[i][j]).ljust(12)
        print(row)

    print("-" * (12 * (n + 1)))


def main():
    parser = argparse.ArgumentParser(description='分类正确率测试脚本')
    parser.add_argument('--directory', '-d', type=str, required=True,
                        help='要测试的目录路径')
    parser.add_argument('--category-system', '-c', type=str, default=None,
                        help='使用的类别体系名称（可选）')
    parser.add_argument('--db-path', type=str, default='data/file_analyzer.db',
                        help='数据库路径（默认: data/file_analyzer.db）')
    parser.add_argument('--no-confusion-matrix', action='store_true',
                        help='不显示混淆矩阵')

    args = parser.parse_args()

    # 检查目录是否存在
    if not os.path.exists(args.directory):
        print(f"错误: 目录不存在: {args.directory}")
        sys.exit(1)

    # 初始化数据库
    db_path = os.path.join(_project_root, args.db_path)
    if not os.path.exists(db_path):
        print(f"错误: 数据库不存在: {db_path}")
        print("请先运行应用程序进行分析")
        sys.exit(1)

    db_manager = DatabaseManager(db_path)

    # 获取真实标签
    ground_truth = get_ground_truth_labels(args.directory)

    if not ground_truth:
        print("错误: 目录中没有找到文件")
        sys.exit(1)

    # 获取预测标签
    predicted = get_predicted_labels(db_manager, args.category_system)

    if not predicted:
        print("错误: 数据库中没有分类结果")
        sys.exit(1)

    # 计算指标
    metrics, overall = calculate_metrics(ground_truth, predicted)

    # 打印结果
    print_results(metrics, overall)

    # 打印混淆矩阵
    if not args.no_confusion_matrix:
        categories, matrix = generate_confusion_matrix(ground_truth, predicted)
        print_confusion_matrix(categories, matrix)

    return 0


if __name__ == "__main__":
    sys.exit(main())