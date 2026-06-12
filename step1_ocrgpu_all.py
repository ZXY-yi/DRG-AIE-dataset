# step1_ocrgpu.py
import os
import json
import time
from paddleocr import PaddleOCR


class OCRGPU:
    """
    Step1：GPU OCR
    - 批量识别 DRG_model/output/step0 下的所有图片
    - 保存 JSON 到 DRG_model/output/step1
    - 文件名与输入文件保持一致
    - 记录识别总时长
    """

    def __init__(self):
        # ================== 初始化 OCR ==================
        self.ocr = PaddleOCR(
            use_textline_orientation=True,
            lang="ch"
            # 针对数字识别优化的参数
            # rec_algorithm="SVTR_LCNet",  # 使用更先进的识别算法
            # rec_image_shape="3, 48, 320",  # 调整图像输入尺寸，更适合数字
            # rec_batch_num=1,  # 单批次处理，提高精度
            # drop_score=0.3,  # 降低置信度阈值，识别更多字符
            # # 检测器参数优化
            # det_db_thresh=0.3,  # 降低检测阈值
            # det_db_box_thresh=0.5,  # 提高框检测阈值
            # det_db_unclip_ratio=1.6,  # 调整框扩展比例
            # # 识别器参数优化
            # rec_char_dict_path=None,  # 使用默认字典
            # use_space_char=False  # 不识别空格
        )

        # ================== 路径设置 ==================
        self.input_dir = r'DRG_model\output\step0-digit-600kb'
        self.output_dir = r'DRG_model\output\step1'
        os.makedirs(self.output_dir, exist_ok=True)

        # ================== 获取图片列表 ==================
        self.img_files = [
            f for f in os.listdir(self.input_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]

        print(f"共发现 {len(self.img_files)} 张图片，开始批量OCR识别...")

    def run(self):
        """
        执行批量OCR识别

        Returns:
            dict: 包含总时长和识别结果的字典
        """
        # 记录总开始时间
        total_start_time = time.time()
        
        ocr_results = []
        processed_count = 0
        total_files = len(self.img_files)

        for img_file in self.img_files:
            img_path = os.path.join(self.input_dir, img_file)

            # ================== 单个文件OCR ==================
            start_time = time.time()
            result = self.ocr.predict(img_path)
            recognition_time = time.time() - start_time

            # predict 新接口：result[0] 是 dict
            res = result[0]
            texts = res.get('rec_texts', [])
            scores = res.get('rec_scores', [])
            boxes = res.get('rec_boxes', [])

            # ================== 构建页面结果 ==================
            page_results = []
            for i in range(len(texts)):
                x_min, y_min, x_max, y_max = boxes[i].tolist()

                bbox = [
                    [int(x_min), int(y_min)],
                    [int(x_max), int(y_min)],
                    [int(x_max), int(y_max)],
                    [int(x_min), int(y_max)]
                ]

                page_results.append({
                    "text": texts[i],
                    "score": float(scores[i]),
                    "bbox": bbox
                })

            # ================== OCR JSON 结构 ==================
            output_json = {
                "image_path": img_path.replace("\\", "\\\\"),
                "recognition_time_sec": recognition_time,
                "pages": [
                    {
                        "page_index": 1,
                        "results": page_results
                    }
                ]
            }

            # ================== 保存 JSON ==================
            # 保持与输入文件相同的文件名（仅扩展名改为.json）
            json_name = os.path.splitext(img_file)[0] + ".json"
            json_path = os.path.join(self.output_dir, json_name)

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(output_json, f, ensure_ascii=False, indent=4)

            processed_count += 1
            print(f"[{processed_count}/{total_files}] ✓ {img_file} 完成，耗时 {recognition_time:.2f}s → {json_path}")

            # ================== 缓存到内存（关键） ==================
            ocr_results.append({
                "image_path": img_path,
                "json_path": json_path,
                "recognition_time_sec": recognition_time,
                "ocr_data": output_json
            })

        # 计算总时长
        total_time = time.time() - total_start_time
        
        # ================== 生成统计报告 ==================
        print("\n" + "="*60)
        print("\t\tOCR批量识别完成报告")
        print("="*60)
        print(f"📁 输入目录: {self.input_dir}")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"📋 总文件数: {total_files}")
        print(f"✅ 成功处理: {processed_count}")
        print(f"⏱️  总耗时: {total_time:.2f}秒")
        print(f"📊 平均每文件: {total_time/total_files:.2f}秒" if total_files > 0 else "📊 平均每文件: 0秒")
        print("="*60)

        # 保存总时长统计
        stats_path = os.path.join(self.output_dir, "ocr_statistics.json")
        stats_data = {
            "total_files": total_files,
            "processed_files": processed_count,
            "total_time_seconds": total_time,
            "average_time_per_file": total_time/total_files if total_files > 0 else 0,
            "input_directory": self.input_dir,
            "output_directory": self.output_dir,
            "processed_files_list": [os.path.basename(r['image_path']) for r in ocr_results]
        }
        
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        print(f"📊 统计信息已保存到: {stats_path}")

        return {
            "total_time_seconds": total_time,
            "processed_count": processed_count,
            "total_files": total_files,
            "ocr_results": ocr_results,
            "output_dir": self.output_dir
        }


def main():
    """主函数，用于独立运行测试"""
    # 创建OCR实例
    ocr_gpu = OCRGPU()
    
    # 执行批量OCR识别
    result = ocr_gpu.run()
    
    # 输出摘要信息
    print(f"\n🎉 批量OCR识别完成!")
    print(f"总耗时: {result['total_time_seconds']:.2f}秒")
    print(f"处理文件数: {result['processed_count']}/{result['total_files']}")
    print(f"输出目录: {result['output_dir']}")
    
    return result


if __name__ == "__main__":
    main()