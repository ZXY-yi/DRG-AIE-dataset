# step2_group_texts_by_line_advanced.py
"""
Step2：高级表格文本按行分组（基于几何中心线）
"""

import json
import os
from typing import List, Dict, Tuple


class GroupTextsByLineAdvanced:
    def __init__(
        self,
        step1_output_json: str,
        output_dir: str = "DRG_model\output\step2",
        centerline_threshold: int = 40,
        merge_threshold: int = 40
    ):
        self.step1_output_json = step1_output_json
        self.centerline_threshold = centerline_threshold
        self.merge_threshold = merge_threshold
        self.output_dir = output_dir
        # if output_dir is None:
        #     self.output_dir = "DRG_model\output\step2"
        # else:
        #     self.output_dir = output_dir

        # os.makedirs(self.output_dir, exist_ok=True)

    # ==================== 几何与分组算法 ====================

    @staticmethod
    def calculate_geometric_centerline(bbox):
        y_coords = [p[1] for p in bbox]
        return round(sum(y_coords) / len(y_coords))

    def extract_text_blocks(self, ocr_results):
        blocks = []
        for item in ocr_results:
            text = item.get("text", "").strip()
            bbox = item.get("bbox", [])
            if not text or len(bbox) < 4:
                continue

            center_y = self.calculate_geometric_centerline(bbox)
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]

            blocks.append({
                "text": text,
                "bbox": bbox,
                "centerline_y": center_y,
                "x_min": min(xs),
                "x_max": max(xs),
                "y_min": min(ys),
                "y_max": max(ys),
            })
        return blocks

    def group_by_centerline(self, blocks):
        blocks = sorted(blocks, key=lambda x: x["centerline_y"])
        lines, current, current_y = [], [], None

        for b in blocks:
            if current_y is None or abs(b["centerline_y"] - current_y) <= self.centerline_threshold:
                current.append(b)
                current_y = sum(x["centerline_y"] for x in current) / len(current)
            else:
                lines.append(sorted(current, key=lambda x: x["x_min"]))
                current = [b]
                current_y = b["centerline_y"]

        if current:
            lines.append(sorted(current, key=lambda x: x["x_min"]))
        return lines

    def process(self, recognized_texts):
        blocks = self.extract_text_blocks(recognized_texts)
        lines = self.group_by_centerline(blocks)

        # 创建二维数组：每个文本元素与其对应的平均Y坐标配对
        paired_lines = []
        for line in lines:
            avg_y = sum(b["centerline_y"] for b in line) / len(line)
            paired_line = [[b["text"], avg_y] for b in line]
            paired_lines.append(paired_line)

        return paired_lines

    # ==================== 对外主接口 ====================

    def run(self) -> str:
        with open(self.step1_output_json, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)

        recognized_texts = []
        for page in ocr_data.get("pages", []):
            for r in page.get("results", []):
                recognized_texts.append({
                    "text": r.get("text", ""),
                    "bbox": r.get("bbox", [])
                })

        paired_lines = self.process(recognized_texts)

        output_data = {
            "image_path": ocr_data.get("image_path"),
            "total_text_blocks": len(recognized_texts),
            "lines": paired_lines,
            "algorithm": "advanced_centerline_based"
        }

        base_name = os.path.splitext(os.path.basename(self.step1_output_json))[0]
        output_path = os.path.join(
            self.output_dir,
            f"{base_name}_line_proc_grouped.json"
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"[Step2] 输出完成: {output_path}")
        return output_path

if __name__ == "__main__":
    step1_output_json = "DRG_model\output\step1\\21_page_2.json"
    group_line_proc_advanced = GroupTextsByLineAdvanced(step1_output_json)
    out=group_line_proc_advanced.run()
    print(out)