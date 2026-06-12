"""
高级表格文本按行分组脚本 - step2_group_line_diag_advanced.py
功能：基于几何中心线的精确同行合并检测
"""

import json
import os
from typing import List, Dict, Tuple
import numpy as np


# =========================================================
# 算法函数区（纯函数，不依赖类）
# =========================================================

def calculate_geometric_centerline(bbox: List[List[float]]) -> float:
    """计算文本框几何中心线 Y 坐标"""
    if not bbox or len(bbox) < 4:
        return 0.0
    y_coords = [p[1] for p in bbox]
    return sum(y_coords) / len(y_coords)


def extract_text_blocks_with_precision(ocr_results: List[Dict]) -> List[Dict]:
    """提取文本块并计算几何属性"""
    blocks = []
    for item in ocr_results:
        text = item.get("text", "").strip()
        bbox = item.get("bbox", [])
        if not text or len(bbox) < 4:
            continue

        x_coords = [p[0] for p in bbox]
        y_coords = [p[1] for p in bbox]

        blocks.append({
            "text": text,
            "bbox": bbox,
            "centerline_y": calculate_geometric_centerline(bbox),
            "x_min": min(x_coords),
            "x_max": max(x_coords),
            "y_min": min(y_coords),
            "y_max": max(y_coords),
        })
    return blocks


def group_texts_by_centerline(
    text_blocks: List[Dict],
    threshold: int = 40
) -> List[List[Dict]]:
    """基于中心线的初始行聚类"""
    if not text_blocks:
        return []

    text_blocks = sorted(text_blocks, key=lambda x: x["centerline_y"])
    lines = []
    current_line = [text_blocks[0]]
    current_y = text_blocks[0]["centerline_y"]

    for block in text_blocks[1:]:
        if abs(block["centerline_y"] - current_y) <= threshold:
            current_line.append(block)
            current_y = np.mean([b["centerline_y"] for b in current_line])
        else:
            lines.append(sorted(current_line, key=lambda b: b["x_min"]))
            current_line = [block]
            current_y = block["centerline_y"]

    lines.append(sorted(current_line, key=lambda b: b["x_min"]))
    return lines


def group_texts_by_line_advanced(
    ocr_results: List[Dict],
    centerline_threshold: int = 40
) -> List[List[List]]:
    """
    高级按行分组主算法
    """
    blocks = extract_text_blocks_with_precision(ocr_results)
    if not blocks:
        return []

    lines_blocks = group_texts_by_centerline(blocks, centerline_threshold)

    # 创建二维数组：每个文本元素与其对应的平均Y坐标配对
    paired_lines = []
    for line in lines_blocks:
        avg_y = np.mean([b["centerline_y"] for b in line])
        paired_line = [[b["text"], avg_y] for b in line]
        paired_lines.append(paired_line)

    return paired_lines

# =========================================================
# Pipeline 类
# =========================================================

class GroupLineDiagAdvanced:
    def __init__(self, input_json_path: str):
        """
        参数:
            input_json_path: step1 输出的单个 OCR JSON 文件路径
        """
        self.input_json_path = input_json_path
        if not os.path.isfile(self.input_json_path):
            raise FileNotFoundError(f"输入 JSON 不存在: {self.input_json_path}")

        
        # self.output_dir = os.path.join("DRG_model","output", "step2")
        # os.makedirs(self.output_dir, exist_ok=True)

    def run(self) -> str:
        # ---------- 读取 OCR JSON ----------
        with open(self.input_json_path, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)

        # ---------- 提取 OCR 文本块 ----------
        recognized_texts = []
        for page in ocr_data.get("pages", []):
            for result in page.get("results", []):
                recognized_texts.append({
                    "text": result.get("text", ""),
                    "bbox": result.get("bbox", [])
                })

        # ---------- 行分组（关键修复点） ----------
        paired_lines = group_texts_by_line_advanced(recognized_texts)

        # ---------- 构建输出 ----------
        output_data = {
            "image_path": ocr_data.get("image_path"),
            "total_text_blocks": len(recognized_texts),
            "lines": paired_lines,
            "algorithm": "advanced_centerline_based"
        }

        # 创建输出目录
        self.output_dir = os.path.join("DRG_model", "output", "step2")
        os.makedirs(self.output_dir, exist_ok=True)

        # 使用与step2_group_line_proc_advanced.py相同的文件名格式
        base_name = os.path.splitext(os.path.basename(self.input_json_path))[0]
        output_path = os.path.join(
            self.output_dir,
            f"{base_name}_line_diag_grouped.json"
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"[Step2] 输出完成: {output_path}")
        return output_path

if __name__ == "__main__":
    step1_output_json = "DRG_model\output\step1\\21_page_1.json"
    group_line_diag_advanced = GroupLineDiagAdvanced(step1_output_json)
    out=group_line_diag_advanced.run()
    print(out)