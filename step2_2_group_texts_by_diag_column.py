#!/usr/bin/env python
# -*- coding: utf-8 -*-
# step2_2_group_texts_by_diag_column.py
"""
step2.2 - 基于坐标按列组织文本内容

该脚本处理OCR识别结果，提取"其他诊断"到"入院病情"之间的文本内容，
基于X坐标范围按列进行组织，适用于表格结构的文本数据。
"""

import json
import os

# ================== 配置参数 ==================
# 列划分的X坐标阈值（像素）
X_THRESHOLD = 150

# 关键字段标识
START_MARKER = "其他诊断"
END_MARKER = "入院病情"

# ================== 辅助函数 ==================

def extract_text_range_excluding_end(ocr_results, start_marker, end_marker):
    """
    从OCR结果中提取指定范围内的文本内容，基于表格结构
    只提取"其他诊断"表格内的内容，不包括后续的独立行
    
    参数:
        ocr_results: OCR识别结果列表
        start_marker: 开始标记文本
        end_marker: 结束标记文本
        
    返回:
        extracted_texts: 提取的文本块列表
        start_found: 是否找到开始标记
        end_found: 是否找到结束标记
    """
    extracted_texts = []
    start_found = False
    end_found = False
    
    # 记录开始标记的Y坐标，用于确定表格范围
    start_y = None
    
    # 增强容错性的开始标记匹配
    start_marker_variants = [
        start_marker,  # 原始标记
        start_marker.replace("其他", "他"),  # OCR可能漏掉"其"字
        start_marker.replace("诊断", "诊"),  # OCR可能漏掉"断"字
        "他诊断",  # 常见OCR错误
        "他诊"  # 更简化的错误
    ]
    
    for item in ocr_results:
        text = item.get('text', '')
        bbox = item.get('bbox', [])
        
        # 计算文本块的Y坐标
        if bbox and len(bbox) >= 4:
            y_coords = [point[1] for point in bbox]
            y_center = (min(y_coords) + max(y_coords)) / 2
        else:
            y_center = 0
        
        # 检查是否找到开始标记（增强容错性）
        if not start_found:
            for variant in start_marker_variants:
                if variant in text:
                    start_found = True
                    start_y = y_center  # 记录开始标记的Y坐标
                    print(f"找到开始标记变体: '{variant}' (原始文本: '{text}')")
                    # 包含开始标记行（保持文本块完整性）
                    extracted_texts.append(item)
                    break
            if start_found:
                continue
        
        # 如果已经找到开始标记，检查是否应该停止提取
        if start_found:
            # 检查是否找到结束标记
            if end_marker in text:
                end_found = True
                print(f"找到结束标记: '{end_marker}'")
                break  # 找到结束标记，停止提取
            
            # 检查Y坐标是否超出表格范围（与开始标记Y坐标差异过大）
            # 如果Y坐标差异超过100像素，认为已经超出表格范围
            if start_y is not None and abs(y_center - start_y) > 100:
                # 检查当前文本是否可能是新的表格标题
                if any(keyword in text for keyword in ['入院病情', '损伤、中毒', '病理诊断']):
                    end_found = True
                    print(f"超出表格范围，找到新标题: '{text}'")
                    break  # 超出表格范围，停止提取
            
            # 如果在表格范围内，添加到提取列表
            extracted_texts.append(item)
    
    return extracted_texts, start_found, end_found


def group_texts_by_column(text_blocks):
    """
    基于X坐标将文本块按列进行分组
    
    参数:
        text_blocks: 文本块列表，每个包含text和bbox
        
    返回:
        (columns, column_average_x_coordinates): 按列组织的文本列表和每列的X坐标平均值列表
    """
    if not text_blocks:
        return []
    
    # 计算每个文本块的X中心坐标和Y坐标
    processed_blocks = []
    for item in text_blocks:
        text = item.get('text', '')
        bbox = item.get('bbox', [])
        
        if not text or not bbox or len(bbox) < 4:
            continue
        
        # 计算坐标
        x_coords = [point[0] for point in bbox]
        y_coords = [point[1] for point in bbox]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        
        processed_blocks.append({
            'text': text,
            'x_center': x_center,
            'y_center': y_center,
            'x_min': x_min,
            'x_max': x_max,
            'bbox': bbox
        })
    
    if not processed_blocks:
        return []
    
    # 按Y坐标排序（行顺序）
    processed_blocks.sort(key=lambda x: x['y_center'])
    
    # 使用聚类方法识别列边界，考虑X坐标范围重叠
    column_boundaries = identify_column_boundaries(processed_blocks)
    
    # 初始化列
    columns = [[] for _ in range(len(column_boundaries) + 1)]
    
    # 按行处理，将每行的文本分配到对应的列
    current_y = None
    current_row_texts = []
    
    for block in processed_blocks:
        if current_y is None:
            current_y = block['y_center']
            current_row_texts = [block]
        else:
            # 如果Y坐标差异小于阈值，认为是同一行
            if abs(block['y_center'] - current_y) < 20:  # 行阈值
                current_row_texts.append(block)
            else:
                # 处理当前行
                assign_columns_for_row(current_row_texts, columns, column_boundaries, processed_blocks)
                current_row_texts = [block]
                current_y = block['y_center']
    
    # 处理最后一行
    if current_row_texts:
        assign_columns_for_row(current_row_texts, columns, column_boundaries, processed_blocks)
    
    # 过滤空列
    columns = [col for col in columns if col]
    
    # 计算每列的X坐标平均值
    column_average_x_coordinates = []
    for column_texts in columns:
        average_x = calculate_column_average_x_coordinate(column_texts, processed_blocks)
        column_average_x_coordinates.append(average_x)
    
    return columns, column_average_x_coordinates


def identify_column_boundaries(text_blocks):
    """
    识别列边界，考虑文本块的X坐标范围重叠
    """
    if not text_blocks:
        return []
    
    # 提取所有文本块的X范围
    x_ranges = []
    for block in text_blocks:
        bbox = block.get('bbox', [])
        if bbox and len(bbox) >= 4:
            x_coords = [point[0] for point in bbox]
            x_min, x_max = min(x_coords), max(x_coords)
            x_ranges.append((x_min, x_max, block['text']))
    
    # 按X最小值排序
    x_ranges.sort(key=lambda x: x[0])
    
    # 使用聚类算法识别列
    clusters = []
    current_cluster = [x_ranges[0]] if x_ranges else []
    
    for i in range(1, len(x_ranges)):
        current_min, current_max, _ = current_cluster[-1]
        next_min, next_max, _ = x_ranges[i]
        
        # 检查是否有显著重叠
        overlap = min(current_max, next_max) - max(current_min, next_min)
        overlap_ratio = overlap / min(current_max - current_min, next_max - next_min)
        
        # 如果有显著重叠（>30%），认为是同一列
        if overlap > 0 and overlap_ratio > 0.3:
            current_cluster.append(x_ranges[i])
        else:
            # 新列开始
            clusters.append(current_cluster)
            current_cluster = [x_ranges[i]]
    
    if current_cluster:
        clusters.append(current_cluster)
    
    # 计算列边界
    boundaries = []
    for i in range(len(clusters) - 1):
        # 当前列的右边界
        current_max = max(max_x for _, max_x, _ in clusters[i])
        # 下一列的左边界
        next_min = min(min_x for min_x, _, _ in clusters[i+1])
        # 边界点（两列之间的中间点）
        boundary = (current_max + next_min) / 2
        boundaries.append(boundary)
    
    print(f"识别到 {len(clusters)} 个列聚类:")
    for i, cluster in enumerate(clusters):
        min_x = min(min_x for min_x, _, _ in cluster)
        max_x = max(max_x for _, max_x, _ in cluster)
        texts = [text for _, _, text in cluster]
        print(f"  列{i+1}: X范围[{min_x:.0f}-{max_x:.0f}], 文本: {texts}")
    
    return boundaries


def calculate_column_average_x_coordinate(column_texts, processed_blocks):
    """
    计算每列数据的X坐标平均值
    
    参数:
        column_texts: 该列的文本列表
        processed_blocks: 所有处理过的文本块列表（包含X坐标信息）
        
    返回:
        该列的X坐标平均值
    """
    if not column_texts:
        return 0.0
    
    # 创建文本到X坐标的映射
    text_to_x = {}
    for block in processed_blocks:
        text_to_x[block['text']] = block['x_center']
    
    # 计算该列所有文本块X坐标的平均值
    total_x = 0
    count = 0
    
    for text in column_texts:
        if text in text_to_x:
            total_x += text_to_x[text]
            count += 1
    
    if count == 0:
        return 0.0
    
    average_x = total_x / count
    return average_x


def assign_columns_for_row(row_blocks, columns, boundaries, processed_blocks):
    """
    将一行的文本分配到对应的列
    
    参数:
        row_blocks: 当前行的文本块列表
        columns: 列列表
        boundaries: 列边界列表
        processed_blocks: 所有处理过的文本块列表（用于计算列坐标平均值）
    """
    # 按X坐标排序
    row_blocks.sort(key=lambda x: x['x_center'])
    
    for block in row_blocks:
        x_center = block['x_center']
        
        # 确定文本属于哪一列
        col_index = 0
        for i, boundary in enumerate(boundaries):
            if x_center > boundary:
                col_index = i + 1
            else:
                break
        
        # 确保列索引不越界
        if col_index >= len(columns):
            # 如果列数不够，扩展列
            for _ in range(col_index - len(columns) + 1):
                columns.append([])
        
        # 添加到对应的列
        columns[col_index].append(block['text'])


def save_column_results(columns, column_average_x_coordinates, output_path, metadata):
    """
    保存按列组织的结果到JSON文件，排除入院病情代码列
    
    参数:
        columns: 按列组织的文本列表
        column_average_x_coordinates: 每列的X坐标平均值列表
        output_path: 输出文件路径
        metadata: 元数据信息
    """
    # 过滤掉入院病情代码列（通常是最右边的数字列）
    filtered_columns = []
    filtered_x_coordinates = []
    
    for i, column in enumerate(columns):
        # 检查该列是否可能是入院病情代码列
        # 入院病情代码通常是单个数字或简单数字组合
        is_admission_status = True
        
        for text in column:
            # 如果列中有非数字文本或复杂编码，则不是入院病情代码列
            if not text.strip().isdigit() and len(text.strip()) > 3:
                is_admission_status = False
                break
        
        # 保留非入院病情代码列
        if not is_admission_status:
            filtered_columns.append(column)
            if i < len(column_average_x_coordinates):
                filtered_x_coordinates.append(column_average_x_coordinates[i])
    
    print(f"过滤后保留 {len(filtered_columns)} 列（排除了入院病情代码列）")
    
    # 创建二维数组：每个文本元素与其对应的X坐标平均值配对
    paired_columns = []
    for i, column in enumerate(filtered_columns):
        avg_x = filtered_x_coordinates[i] if i < len(filtered_x_coordinates) else 0.0
        paired_column = [[text, avg_x] for text in column]
        paired_columns.append(paired_column)
    
    result = {
        'image_path': metadata.get('image_path', ''),
        'total_text_blocks': metadata.get('extracted_text_count', 0),
        'columns': paired_columns,
        'algorithm': 'advanced_column_based',
        'filtered_admission_status': True
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result


# ================== 主程序 ==================

class GroupTextsByDiagColumn:
    """主程序入口"""
    def __init__(self, input_path):
        self.input_path = input_path
        # if output_dir is None:
        self.output_path = "DRG_model/output/step2.2/step2_2_diag_column.json"
        # else:
        #     self.output_dir = output_dir
        # self.output_path = output_path

        # os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
    # 获取当前脚本所在目录
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 输入输出路径配置（相对于脚本目录）
    # input_path = os.path.join(script_dir, 'output', 'step1', '5_eye_Page1_2.0.json')
    # output_path = os.path.join(script_dir, 'output', 'step2.2', '5_eye_Page1_2.0_column_grouped.json')
    
    def run(self):
        # 确保输出目录存在
        # os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 读取输入文件
        # print("正在读取OCR识别结果文件...")
        with open(self.input_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        print(f"输入数据类型: {type(ocr_data)}")
        print(f"输入数据键: {ocr_data.keys() if isinstance(ocr_data, dict) else 'Not a dict'}")
        
        # 验证数据格式
        if not isinstance(ocr_data, dict):
            raise ValueError("不支持的输入数据格式: 期望字典类型")
        
        # 检查数据格式，支持多种OCR结果格式
        all_text_blocks = []
        
        # 格式1: 包含'pages'键的标准格式
        if 'pages' in ocr_data:
            for page in ocr_data['pages']:
                if 'results' in page:
                    for result in page['results']:
                        text_block = {
                            'text': result.get('text', ''),
                            'bbox': result.get('bbox', [])
                        }
                        all_text_blocks.append(text_block)
        # 格式2: 直接包含'results'键的格式
        elif 'results' in ocr_data:
            for result in ocr_data['results']:
                text_block = {
                    'text': result.get('text', ''),
                    'bbox': result.get('bbox', [])
                }
                all_text_blocks.append(text_block)
        # 格式3: 直接是文本块列表的格式
        elif isinstance(ocr_data, list):
            for item in ocr_data:
                if isinstance(item, dict) and 'text' in item:
                    text_block = {
                        'text': item.get('text', ''),
                        'bbox': item.get('bbox', [])
                    }
                    all_text_blocks.append(text_block)
        else:
            raise ValueError("不支持的输入数据格式: 未找到'pages'或'results'键")
        
        print(f"提取的文本块数: {len(all_text_blocks)}")
        
        # print(f"总文本块数: {len(all_text_blocks)}")
        
        # 提取指定范围内的文本（不包括结束标记行）
        # print(f"正在提取 '{START_MARKER}' 到 '{END_MARKER}' 之间的文本（不包括结束标记）...")
        extracted_texts, start_found, end_found = extract_text_range_excluding_end(
            all_text_blocks, START_MARKER, END_MARKER
        )
        
        # 检查是否找到关键字段
        if not start_found:
            print(f"警告: 未找到开始标记 '{START_MARKER}'")
        if not end_found:
            print(f"警告: 未找到结束标记 '{END_MARKER}'")
        
        print(f"提取到 {len(extracted_texts)} 个文本块")
        
        # 输出提取的文本内容（用于调试）
        if extracted_texts:
            print("提取的文本内容:")
            for i, item in enumerate(extracted_texts):
                text = item.get('text', '')
                bbox = item.get('bbox', [])
                if bbox:
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    x_center = (min(x_coords) + max(x_coords)) / 2
                    y_center = (min(y_coords) + max(y_coords)) / 2
                    print(f"  {i+1}. '{text}' (X: {x_center:.0f}, Y: {y_center:.0f})")
        
        if not extracted_texts:
            print("未提取到任何文本内容，程序结束")
            return
        
        # 按坐标分列
        print("正在按坐标分列...")
        columns, column_average_x_coordinates = group_texts_by_column(extracted_texts)
        
        print(f"识别到 {len(columns)} 列")
        
        # 准备元数据
        metadata = {
            'image_path': ocr_data.get('image_path', self.input_path),
            'recognition_time_sec': ocr_data.get('recognition_time_sec', 0),
            'start_marker': START_MARKER,
            'end_marker': END_MARKER,
            'start_marker_found': start_found,
            'end_marker_found': end_found,
            'extracted_text_count': len(extracted_texts)
        }
        
        # 保存结果
        result = save_column_results(columns, column_average_x_coordinates, self.output_path, metadata)
        
        # 输出处理统计
        print("\n" + "=" * 60)
        print("按列分组完成！")
        print("=" * 60)
        print(f"处理统计:")
        print(f"  - 图片路径: {metadata['image_path']}")
        print(f"  - 识别耗时: {metadata['recognition_time_sec']:.2f}秒")
        print(f"  - 开始标记: {START_MARKER} ({'找到' if start_found else '未找到'})")
        print(f"  - 结束标记: {END_MARKER} ({'找到' if end_found else '未找到'})")
        print(f"  - 提取文本块数: {len(extracted_texts)}")
        print(f"  - 识别列数: {len(columns)}")
        
        # 输出每列的统计信息
        print(f"\n列统计信息:")
        for i, column in enumerate(columns):
            print(f"  第{i+1}列: {len(column)} 个文本")
        
        # 输出保存路径  
        print(f"\n结果文件已保存到: {self.output_path}")
        return self.output_path
   


if __name__ == "__main__":
    input_path = "DRG_model/output/step1/07_page_1.json"
    group_tex = GroupTextsByDiagColumn(input_path)
    out = group_tex.run()
    print(out)