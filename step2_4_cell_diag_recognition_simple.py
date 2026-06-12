#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
step2.4 - 基于坐标中心值的文本块合并

该脚本基于step2-group_texts_by_line_advanced.py和step2.2-group_texts_by_diag_column.py
生成的文件，识别并处理处于同一行且同一列位置的多个文本块。
合并规则：将纵坐标中心值较小的文本块(A)放置在前，纵坐标中心值较大的文本块(B)放置在后，
最终合并结果应为字符串拼接形式：str = strA + strB。
"""

import json
import os
from typing import List, Dict, Tuple


def load_json_file(file_path: str) -> Dict:
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_coordinates_from_ocr(ocr_file_path: str) -> Dict[str, Dict]:
    """从OCR结果文件中提取文本块的坐标信息"""
    ocr_data = load_json_file(ocr_file_path)
    text_coordinates = {}
    
    if 'pages' in ocr_data:
        for page in ocr_data['pages']:
            if 'results' in page:
                for result in page['results']:
                    text = result.get('text', '').strip()
                    if text:  # 只处理非空文本
                        bbox = result.get('bbox', [])
                        if bbox and len(bbox) >= 4:
                            # 提取坐标信息
                            x_coords = [point[0] for point in bbox]
                            y_coords = [point[1] for point in bbox]
                            
                            x_min, x_max = min(x_coords), max(x_coords)
                            y_min, y_max = min(y_coords), max(y_coords)
                            x_center = (x_min + x_max) / 2
                            y_center = (y_min + y_max) / 2  # 纵坐标中心值
                            
                            text_coordinates[text] = {
                                'x_min': x_min,
                                'x_max': x_max,
                                'y_min': y_min,
                                'y_max': y_max,
                                'x_center': x_center,
                                'y_center': y_center,  # 关键：纵坐标中心值
                                'bbox': bbox
                            }
    
    return text_coordinates


def is_same_row_by_y_coordinates(coordA: Dict, coordB: Dict, y_threshold: float = 20.0) -> bool:
    """
    基于Y坐标判断两个文本块是否在同一行
    
    参数:
        coordA: 文本块A的坐标信息
        coordB: 文本块B的坐标信息
        y_threshold: Y坐标差异阈值（像素）
        
    返回:
        是否在同一行
    """
    # 计算Y坐标中心值的差异
    y_center_diff = abs(coordA['y_center'] - coordB['y_center'])
    
    # 如果Y坐标中心值差异小于阈值，认为在同一行
    return y_center_diff <= y_threshold


def is_same_column_by_x_coordinates(coordA: Dict, coordB: Dict, x_threshold: float = 50.0) -> bool:
    """
    基于X坐标判断两个文本块是否在同一列
    
    参数:
        coordA: 文本块A的坐标信息
        coordB: 文本块B的坐标信息
        x_threshold: X坐标差异阈值（像素）
        
    返回:
        是否在同一列
    """
    # 计算X坐标中心值的差异
    x_center_diff = abs(coordA['x_center'] - coordB['x_center'])
    
    # 如果X坐标中心值差异小于阈值，认为在同一列
    return x_center_diff <= x_threshold


def should_merge_text_blocks(textA: str, textB: str, coordA: Dict, coordB: Dict) -> bool:
    """
    基于语义和坐标综合判断是否应该合并两个文本块
    
    参数:
        textA: 文本A
        textB: 文本B
        coordA: 文本A的坐标信息
        coordB: 文本B的坐标信息
        
    返回:
        是否应该合并
    """
    # 1. 排除条件：如果是完全相同的文本，不应该合并
    if textA == textB:
        return False
    
    # 2. 排除条件：如果文本长度都超过10个字符，可能是独立的诊断，不应该合并
    if len(textA) > 10 and len(textB) > 10:
        print(f"[语义排除] 两个文本都较长，可能是独立诊断: '{textA}' ({len(textA)}字) + '{textB}' ({len(textB)}字)")
        return False
    
    # 3. 排除条件：如果文本包含完整的诊断关键词，可能是独立诊断
    diagnosis_keywords = ['分娩', '孕', '产', '手术', '操作', '诊断', '疾病', '综合征']
    textA_has_keyword = any(keyword in textA for keyword in diagnosis_keywords)
    textB_has_keyword = any(keyword in textB for keyword in diagnosis_keywords)
    
    if textA_has_keyword and textB_has_keyword:
        print(f"[语义排除] 两个文本都包含诊断关键词: '{textA}' + '{textB}'")
        return False
    
    # 4. 排除条件：如果文本看起来是完整的句子或诊断描述
    if (textA.endswith(('。', '，', '；', '、')) or 
        textB.endswith(('。', '，', '；', '、')) or
        textA.startswith(('。', '，', '；', '、')) or
        textB.startswith(('。', '，', '；', '、'))):
        print(f"[语义排除] 文本包含标点符号，可能是完整句子: '{textA}' + '{textB}'")
        return False
    
    # 5. 排除条件：如果文本包含数字和单位（如孕39周），可能是独立信息
    import re
    if re.search(r'\d+[周天月年]', textA) or re.search(r'\d+[周天月年]', textB):
        print(f"[语义排除] 文本包含时间/周期信息: '{textA}' + '{textB}'")
        return False
    
    # 6. 坐标验证：检查Y坐标差异是否过大（超过阈值）
    y_threshold = 15.0  # 像素
    y_center_diff = abs(coordA['y_center'] - coordB['y_center'])
    if y_center_diff > y_threshold:
        print(f"[坐标排除] Y坐标差异过大 ({y_center_diff:.1f} > {y_threshold}): '{textA}' + '{textB}'")
        return False
    
    # 7. 坐标验证：检查X坐标差异是否过大（超过阈值）
    x_threshold = 30.0  # 像素
    x_center_diff = abs(coordA['x_center'] - coordB['x_center'])
    if x_center_diff > x_threshold:
        print(f"[坐标排除] X坐标差异过大 ({x_center_diff:.1f} > {x_threshold}): '{textA}' + '{textB}'")
        return False
    
    # 8. 语义验证：检查合并后的文本是否合理
    merged_text = textA + textB
    if len(merged_text) > 50:  # 合并后文本过长
        print(f"[语义排除] 合并后文本过长 ({len(merged_text)}字): '{textA}' + '{textB}'")
        return False
    
    # 9. 语义验证：检查是否包含明显的语义断点
    semantic_breaks = ['。', '，', '；', '、', '：', '？', '！']
    if any(break_char in textA or break_char in textB for break_char in semantic_breaks):
        print(f"[语义排除] 文本包含语义断点: '{textA}' + '{textB}'")
        return False
    
    # 10. 通过所有检查，允许合并
    print(f"[允许合并] 通过语义和坐标验证: '{textA}' + '{textB}'")
    return True


def find_text_blocks_in_same_cell(line_grouped_data: Dict, column_grouped_data: Dict, 
                                 text_coordinates: Dict) -> List[Tuple[str, str]]:
    """
    基于精确坐标值相等识别同一单元格的文本块
    
    参数:
        line_grouped_data: 按行分组的数据（包含lines字段，每个元素是[text, y_coordinate]）
        column_grouped_data: 按列分组的数据（包含columns字段，每个元素是[text, x_coordinate]）
        text_coordinates: 文本块坐标信息
        
    返回:
        需要合并的文本块对列表 (textA, textB)
    """
    merge_candidates = []
    
    # 从行分组数据中获取行信息
    lines = line_grouped_data.get('lines', [])
    
    # 从列分组数据中获取列信息
    columns = column_grouped_data.get('columns', [])
    
    # 构建文本到Y坐标的映射（基于行分组数据）
    text_to_y_coord = {}
    for line in lines:
        for text_item in line:
            if isinstance(text_item, list) and len(text_item) == 2:
                text = text_item[0]
                y_coord = text_item[1]
                text_to_y_coord[text] = y_coord
    
    # 构建文本到X坐标的映射（基于列分组数据）
    text_to_x_coord = {}
    for column in columns:
        for text_item in column:
            if isinstance(text_item, list) and len(text_item) == 2:
                text = text_item[0]
                x_coord = text_item[1]
                text_to_x_coord[text] = x_coord
    
    # 构建Y坐标到行索引的映射（用于调试）
    y_coord_to_line = {}
    for line_idx, line in enumerate(lines):
        for text_item in line:
            if isinstance(text_item, list) and len(text_item) == 2:
                y_coord = text_item[1]
                if y_coord not in y_coord_to_line:
                    y_coord_to_line[y_coord] = line_idx
    
    # 构建X坐标到列索引的映射（用于调试）
    x_coord_to_column = {}
    for col_idx, column in enumerate(columns):
        for text_item in column:
            if isinstance(text_item, list) and len(text_item) == 2:
                x_coord = text_item[1]
                if x_coord not in x_coord_to_column:
                    x_coord_to_column[x_coord] = col_idx
    
    # 双重条件验证：仅基于坐标相等
    processed_pairs = set()
    
    # 遍历所有可能的文本对
    all_texts = list(text_to_y_coord.keys())
    
    for i in range(len(all_texts)):
        textA = all_texts[i]
        
        # 检查文本A是否在坐标字典中
        if textA not in text_coordinates:
            continue
            
        for j in range(i + 1, len(all_texts)):
            textB = all_texts[j]
            
            # 检查文本B是否在坐标字典中
            if textB not in text_coordinates:
                continue
            
            # 避免重复处理
            pair_key = tuple(sorted([textA, textB]))
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)
            
            # 条件1：检查Y坐标是否相等（同一行）
            same_y = (textA in text_to_y_coord and 
                     textB in text_to_y_coord and 
                     text_to_y_coord[textA] == text_to_y_coord[textB])
            
            # 条件2：检查X坐标是否相等（同一列）
            same_x = (textA in text_to_x_coord and 
                     textB in text_to_x_coord and 
                     text_to_x_coord[textA] == text_to_x_coord[textB])
            
            # 双重条件验证：仅基于坐标相等
            if same_y and same_x:
                # 获取坐标信息进行进一步验证
                coordA = text_coordinates[textA]
                coordB = text_coordinates[textB]
                
                # 检查是否应该合并（基于语义和坐标综合判断）
                should_merge = should_merge_text_blocks(textA, textB, coordA, coordB)
                
                if should_merge:
                    # 按纵坐标中心值排序：y_center值小的在前
                    if coordA['y_center'] < coordB['y_center']:
                        merge_candidates.append((textA, textB))
                    else:
                        merge_candidates.append((textB, textA))
                    
                    # 调试信息
                    y_coord = text_to_y_coord[textA]
                    x_coord = text_to_x_coord[textA]
                    line_idx = y_coord_to_line.get(y_coord, -1)
                    col_idx = x_coord_to_column.get(x_coord, -1)
                    
                    print(f"[坐标匹配] 行{line_idx}(Y={y_coord:.1f}), 列{col_idx}(X={x_coord:.1f}): "
                          f"'{textA}' + '{textB}'")
                else:
                    # 调试信息：被排除的文本
                    y_coord = text_to_y_coord[textA]
                    x_coord = text_to_x_coord[textA]
                    line_idx = y_coord_to_line.get(y_coord, -1)
                    col_idx = x_coord_to_column.get(x_coord, -1)
                    
                    print(f"[语义排除] 行{line_idx}(Y={y_coord:.1f}), 列{col_idx}(X={x_coord:.1f}): "
                          f"'{textA}' + '{textB}' (语义/坐标验证失败)")
    
    return merge_candidates


def merge_text_blocks(column_grouped_data: Dict, merge_candidates: List[Tuple[str, str]], 
                     text_coordinates: Dict) -> Dict:
    """
    合并文本块并更新列分组数据
    
    参数:
        column_grouped_data: 原始列分组数据（新格式）
        merge_candidates: 需要合并的文本块对列表
        text_coordinates: 文本块坐标信息
        
    返回:
        合并后的列分组数据
    """
    # 创建合并映射表，直接记录合并后的文本
    merged_texts_map = {}
    
    for textA, textB in merge_candidates:
        # 按纵坐标中心值确定合并顺序
        if text_coordinates[textA]['y_center'] < text_coordinates[textB]['y_center']:
            merged_text = textA + textB  # y_center小的在前
            # 记录合并关系
            merged_texts_map[textA] = merged_text
            merged_texts_map[textB] = merged_text
        else:
            merged_text = textB + textA  # y_center小的在前
            # 记录合并关系
            merged_texts_map[textA] = merged_text
            merged_texts_map[textB] = merged_text
    
    # 更新列分组数据（适应新格式）
    merged_columns = []
    original_columns = column_grouped_data.get('columns', [])
    
    # 构建所有需要合并的文本集合
    all_merged_texts = set()
    for textA, textB in merge_candidates:
        all_merged_texts.add(textA)
        all_merged_texts.add(textB)
    
    for col_idx, column in enumerate(original_columns):
        # 新格式：columns是二维数组，每个元素是[text, x_coordinate]
        original_text_items = column
        merged_column_texts = []
        
        # 用于跟踪已处理的合并组
        processed_merge_groups = set()
        
        for text_item in original_text_items:
            if isinstance(text_item, list) and len(text_item) == 2:
                text = text_item[0]
                x_coord = text_item[1]
                
                # 如果文本需要被合并
                if text in merged_texts_map:
                    merged_text = merged_texts_map[text]
                    
                    # 检查这个合并组是否已经处理过
                    if merged_text not in processed_merge_groups:
                        # 创建新的合并文本项
                        merged_text_item = [merged_text, x_coord]
                        merged_column_texts.append(merged_text_item)
                        # 标记这个合并组为已处理
                        processed_merge_groups.add(merged_text)
                else:
                    # 文本不需要合并，直接添加
                    merged_column_texts.append(text_item)
        
        merged_columns.append(merged_column_texts)
    
    # 构建合并后的结果
    merged_data = column_grouped_data.copy()
    merged_data['columns'] = merged_columns
    merged_data['total_columns'] = len(merged_columns)
    merged_data['merge_info'] = {
        'merged_pairs_count': len(merge_candidates),
        'merged_texts_count': len(set(merged_texts_map.values())),
        'merge_criteria': 'row_and_column_based'  # 更新合并标准
    }
    
    return merged_data


def process_cell_merging(line_grouped_file: str, column_grouped_file: str, 
                        ocr_file: str, output_file: str) -> Dict:
    """
    主处理函数：执行文本块合并操作
    
    参数:
        line_grouped_file: 按行分组文件路径
        column_grouped_file: 按列分组文件路径
        ocr_file: OCR结果文件路径
        output_file: 输出文件路径
        
    返回:
        合并后的数据
    """
    print("正在加载数据文件...")
    
    # 加载数据文件
    line_grouped_data = load_json_file(line_grouped_file)
    column_grouped_data = load_json_file(column_grouped_file)
    
    print("正在提取文本块坐标信息...")
    # 提取坐标信息
    text_coordinates = extract_coordinates_from_ocr(ocr_file)
    
    print(f"提取到 {len(text_coordinates)} 个文本块的坐标信息")
    
    print("正在识别需要合并的文本块...")
    # 识别需要合并的文本块
    merge_candidates = find_text_blocks_in_same_cell(
        line_grouped_data, column_grouped_data, text_coordinates
    )
    
    print(f"识别到 {len(merge_candidates)} 对需要合并的文本块")
    
    if merge_candidates:
        print("需要合并的文本块对（按纵坐标中心值排序）:")
        for i, (textA, textB) in enumerate(merge_candidates):
            coordA = text_coordinates[textA]
            coordB = text_coordinates[textB]
            print(f"  {i+1}. '{textA}' (y_center={coordA['y_center']:.1f}) + '{textB}' (y_center={coordB['y_center']:.1f})")
    
    print("正在执行文本块合并...")
    # 执行合并操作
    merged_data = merge_text_blocks(column_grouped_data, merge_candidates, text_coordinates)
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 保存结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    print(f"合并结果已保存到: {output_file}")
    
    # 输出统计信息
    print("\n" + "=" * 60)
    print("文本块合并完成！")
    print("=" * 60)
    print(f"处理统计:")
    print(f"  - 输入文件: {line_grouped_file}")
    print(f"  - 列分组文件: {column_grouped_file}")
    print(f"  - OCR文件: {ocr_file}")
    print(f"  - 识别到的合并对: {len(merge_candidates)}")
    print(f"  - 合并后的文本数: {merged_data.get('merge_info', {}).get('merged_texts_count', 0)}")
    print(f"  - 合并标准: {merged_data.get('merge_info', {}).get('merge_criteria', 'unknown')}")
    print(f"  - 输出文件: {output_file}")
    
    return merged_data


class CellDiagRecognitionSimple:
    """主函数"""
    def __init__(self, line_grouped_file, column_grouped_file, ocr_file):
        self.line_grouped_file = line_grouped_file
        self.column_grouped_file = column_grouped_file
        self.ocr_file = ocr_file
            
    # # 获取当前脚本所在目录
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # # 文件路径配置（相对于脚本目录）
    # line_grouped_file = os.path.join(script_dir, 'output', 'step2', '5_eye_Page1_2.0_line_diag_grouped_advanced.json')
    # column_grouped_file = os.path.join(script_dir, 'output', 'step2.2', '5_eye_Page1_2.0_column_grouped.json')
    # ocr_file = os.path.join(script_dir, 'output', 'step1', '5_eye_Page1_2.0.json')
    # output_file = os.path.join(script_dir, 'output', 'step2.4', '5_eye_Page1_2.0_cell_diag_merged.json')    
    
    def run(self):
        self.output_file = "DRG_model\output\step2.4\step2_4_cell_diag_merged.json"
        self.output_path = "DRG_model\output\step2.4"
        
        # 确保输出目录存在
        os.makedirs(self.output_path, exist_ok=True)
        
        print("=" * 60)
        print("开始执行文本块合并处理")
        print("=" * 60)
        print(f"输入文件配置:")
        print(f"  行分组文件: {self.line_grouped_file}")
        print(f"  列分组文件: {self.column_grouped_file}")
        print(f"  OCR文件: {self.ocr_file}")
        print(f"  输出文件: {self.output_file}")
        print()
        
        # 执行合并处理
        result = process_cell_merging(
            self.line_grouped_file, self.column_grouped_file, self.ocr_file, self.output_file
        )
        
        # 输出详细的合并统计信息
        print(f"\n合并处理完成！")
        print(f"  识别到的合并对: {result.get('merge_info', {}).get('merged_pairs_count', 0)}")
        print(f"  合并后的文本数: {result.get('merge_info', {}).get('merged_texts_count', 0)}")
        print(f"  合并标准: {result.get('merge_info', {}).get('merge_criteria', 'unknown')}")
        
        return self.output_path



if __name__ == "__main__":
    line_grouped_file = "DRG_model\output\step2.2\step2_2_diag_column.json"
    column_grouped_file = "DRG_model\output\step2.2\step2_2_diag_column.json"
    ocr_file = "DRG_model\output\step1\\14_page_1.json"
    out=CellDiagRecognitionSimple(line_grouped_file, column_grouped_file, ocr_file).run()
    print(out)