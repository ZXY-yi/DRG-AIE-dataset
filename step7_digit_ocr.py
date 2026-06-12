import os
import json
import time
import re
from paddleocr import PaddleOCR
from typing import Dict, List, Tuple

# 定义支持的图像文件格式
SUPPORTED_IMAGE_FORMATS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')

# 文本映射定义
DISCHARGE_MAPPING = {
    "1": "医嘱离院",
    "2": "医嘱转院，拟接收医疗机构名称：",
    "3": "医嘱转社区卫生服务机构/乡镇卫生院，拟接收医疗机构名称：",
    "4": "非医嘱离院",
    "5": "死亡",
    "9": "其他"
}

GENDER_MAPPING = {
    "1": "男",
    "2": "女"
}


def extract_hospital_name_from_json(json_file_path: str, search_pattern: str) -> str:
    """
    从JSON文件中提取医院名称
    
    Args:
        json_file_path: JSON文件路径
        search_pattern: 搜索模式
        
    Returns:
        提取的医院名称，如果未找到则返回空字符串
    """
    try:
        if not os.path.exists(json_file_path):
            print(f"  警告: JSON文件不存在: {json_file_path}")
            return ""
            
        with open(json_file_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        # 提取所有文本内容
        all_texts = []
        
        # 格式1: 包含'pages'键的标准格式
        if 'pages' in ocr_data:
            for page in ocr_data['pages']:
                if 'results' in page:
                    for result in page['results']:
                        text = result.get('text', '')
                        if text:
                            all_texts.append(text)
        # 格式2: 直接包含'results'键的格式
        elif 'results' in ocr_data:
            for result in ocr_data['results']:
                text = result.get('text', '')
                if text:
                    all_texts.append(text)
        # 格式3: 直接是文本块列表的格式
        elif isinstance(ocr_data, list):
            for item in ocr_data:
                if isinstance(item, dict) and 'text' in item:
                    text = item.get('text', '')
                    if text:
                        all_texts.append(text)
        
        print(f"  所有文本内容: {all_texts}")
        
        # 定义OCR容错模式
        fuzzy_patterns = [
            search_pattern,
            search_pattern.replace("医嘱", "医瞩"),  # 处理"医嘱"被识别为"医瞩"的情况
            search_pattern.replace("医嘱", "医瞩").replace("拟", "拟"),  # 其他可能的OCR错误
        ]
        
        # 在所有文本中搜索模式（使用容错模式）
        for pattern in fuzzy_patterns:
            for i, text in enumerate(all_texts):
                if pattern in text:
                    print(f"  找到匹配模式: '{pattern}' 在文本: '{text}'")
                    
                    # 提取模式后面的内容
                    pattern_index = text.find(pattern)
                    if pattern_index != -1:
                        content_start = pattern_index + len(pattern)
                        hospital_name = text[content_start:].strip()
                        
                        # 情况1: 如果当前文本中有内容，检查是否包含"4.非医"
                        if hospital_name:
                            # 检查是否包含"4.非医"，如果包含则只取"4."之前的内容
                            non_medical_index = hospital_name.find("4.非医")
                            if non_medical_index != -1:
                                hospital_name = hospital_name[:non_medical_index].strip()
                                
                            # 清理内容（去除标点符号和多余空格）
                            hospital_name = re.sub(r'[，。；：！？、\s]+$', '', hospital_name)
                            
                            if hospital_name:
                                print(f"  找到医院名称: '{hospital_name}' (当前文本)")
                                return hospital_name
                        
                        # 情况2: 如果当前文本中没有内容，去下一个文本中查找
                        else:
                            # 检查下一个文本
                            if i + 1 < len(all_texts):
                                next_text = all_texts[i + 1].strip()
                                
                                # 检查下一个文本是否包含"4.非医"，如果包含则只取"4."之前的内容
                                non_medical_index = next_text.find("4.非医")
                                if non_medical_index != -1:
                                    hospital_name = next_text[:non_medical_index].strip()
                                else:
                                    hospital_name = next_text
                                
                                # 清理内容
                                hospital_name = re.sub(r'[，。；：！？、\s]+$', '', hospital_name)
                                
                                if hospital_name:
                                    print(f"  找到医院名称: '{hospital_name}' (下一个文本)")
                                    return hospital_name
                            
                            # 情况3: 如果下一个文本也没有内容，继续查找后续文本
                            for j in range(i + 2, min(i + 5, len(all_texts))):  # 最多查找后面3个文本
                                next_text = all_texts[j].strip()
                                if next_text and not next_text.startswith("4."):
                                    # 检查是否包含"4.非医"
                                    non_medical_index = next_text.find("4.非医")
                                    if non_medical_index != -1:
                                        hospital_name = next_text[:non_medical_index].strip()
                                    else:
                                        hospital_name = next_text
                                    
                                    hospital_name = re.sub(r'[，。；：！？、\s]+$', '', hospital_name)
                                    
                                    if hospital_name:
                                        print(f"  找到医院名称: '{hospital_name}' (后续文本{j-i})")
                                        return hospital_name
        
        print(f"  未找到匹配的医院名称")
        return ""
        
    except Exception as e:
        print(f"  提取医院名称时出错: {e}")
        return ""


def get_mapped_text(filename: str, digit: str, step1_dir: str = "DRG_model/output/step1") -> str:
    """
    根据文件名和数字获取映射的文本
    
    Args:
        filename: 图像文件名
        digit: 识别的数字
        step1_dir: step1目录路径
        
    Returns:
        映射的文本描述
    """
    if not digit:
        return ""
    
    # 提取文件前缀（如"09"）
    prefix_match = filename.split('_')[0]
    
    # 构建对应的JSON文件路径
    json_file_path = os.path.join(step1_dir, f"{prefix_match}_page_2.json")
    
    # 出院方式映射
    if "discharge" in filename.lower():
        if digit in DISCHARGE_MAPPING:
            base_text = DISCHARGE_MAPPING[digit]
            
            # 对于需要提取医院名称的情况
            if digit == "2" and "医嘱转院" in base_text:
                hospital_name = extract_hospital_name_from_json(json_file_path, "医嘱转院，拟接收医疗机构名称：")
                if hospital_name:
                    return f"{base_text}{hospital_name}"
                else:
                    return base_text
                    
            elif digit == "3" and "医嘱转社区卫生服务机构" in base_text:
                hospital_name = extract_hospital_name_from_json(json_file_path, "医嘱转社区卫生服务机构/乡镇卫生院，拟接收医疗机构名称：")
                if hospital_name:
                    return f"{base_text}{hospital_name}"
                else:
                    return base_text
                    
            else:
                return base_text
        else:
            return f"未知出院方式({digit})"
    
    # 性别映射
    elif "gender" in filename.lower():
        if digit in GENDER_MAPPING:
            return GENDER_MAPPING[digit]
        else:
            return f"未知性别({digit})"
    
    # 其他情况
    else:
        return f"未知类型({digit})"


def get_all_image_files(directory: str) -> List[str]:
    """
    获取目录下所有支持的图像文件
    
    Args:
        directory: 要遍历的目录路径
        
    Returns:
        所有图像文件的路径列表
    """
    image_files = []
    
    try:
        for file in os.listdir(directory):
            if file.lower().endswith(SUPPORTED_IMAGE_FORMATS):
                full_path = os.path.join(directory, file)
                image_files.append(full_path)
    except Exception as e:
        print(f"遍历目录时出错: {e}")
    
    return image_files


def save_results_to_json(results: Dict, output_path: str) -> None:
    """
    将识别结果保存为JSON文件
    
    Args:
        results: 识别结果字典
        output_path: 输出文件路径
    """
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 保存为JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"识别结果已保存到: {output_path}")
    except Exception as e:
        print(f"保存结果时出错: {e}")


class DigitOCR:
    """
    基于PaddleOCR的数字OCR识别器
    """
    
    def __init__(self, boxed_digits_path: str):
        """
        初始化数字OCR识别器
        
        Args:
            boxed_digits_path: 包含带框数字图像的目录路径
        """
        self.boxed_digits_path = boxed_digits_path
        self.output_dir = "DRG_model/output/step7"
        
        # 初始化PaddleOCR，使用与step1相同的参数
        self.ocr = PaddleOCR(
            use_textline_orientation=True,
            lang="ch"
        )
        
        print("PaddleOCR数字识别引擎已初始化")
        
    def extract_digits_from_ocr_result(self, ocr_result) -> str:
        """
        从OCR结果中提取数字（只保留单个数字）
        
        Args:
            ocr_result: PaddleOCR识别结果
            
        Returns:
            提取的数字字符串（单个数字）
        """
        try:
            if not ocr_result or len(ocr_result) == 0:
                print("  OCR结果为空")
                return ""
            
            # 获取第一个结果（通常是主要识别结果）
            res = ocr_result[0]
            texts = res.get('rec_texts', [])
            scores = res.get('rec_scores', [])
            
            if not texts:
                print("  没有识别到文本")
                return ""
            
            print(f"  原始识别结果: {texts}")
            print(f"  置信度: {scores}")
            
            # 提取数字字符（只保留单个数字）
            digit_candidates = []
            
            for i, text in enumerate(texts):
                score = scores[i] if i < len(scores) else 0.5
                
                # 检查文本是否为单个字符
                clean_text = text.strip()
                if len(clean_text) == 1 and score > 0.3:  # 置信度阈值
                    
                    # 方法1：检查是否为纯数字
                    if clean_text.isdigit():
                        digit_candidates.append((clean_text, score, "single_digit"))
                        print(f"  方法1 - 单个数字: '{clean_text}'")
                    
                    # 方法2：字符映射识别（处理OCR可能识别为其他字符的情况）
                    # 常见OCR误识别：1->l, I, |; 0->O, o; 2->Z; 5->S等
                    text_lower = clean_text.lower()
                    digit_mapping = {
                        'l': '1', 'i': '1', '|': '1',
                        'o': '0', 'O': '0',
                        'z': '2', 'Z': '2',
                        's': '5', 'S': '5'
                    }
                    if text_lower in digit_mapping:
                        mapped_digit = digit_mapping[text_lower]
                        digit_candidates.append((mapped_digit, score, "mapping"))
                        print(f"  方法2 - 字符映射: '{clean_text}' -> '{mapped_digit}'")
                
                # 如果文本包含多个字符，检查是否包含多个数字
                elif len(clean_text) > 1:
                    # 提取所有数字字符
                    digits_in_text = ''.join(filter(str.isdigit, clean_text))
                    if len(digits_in_text) > 1:
                        print(f"  丢弃 - 多个数字: '{clean_text}' 包含数字 '{digits_in_text}'")
                    elif len(digits_in_text) == 1:
                        # 如果文本包含多个字符但只有一个数字，检查数字占比
                        digit_ratio = len(digits_in_text) / len(clean_text)
                        if digit_ratio > 0.5:  # 数字占比超过50%
                            digit_candidates.append((digits_in_text, score, "single_digit_in_text"))
                            print(f"  方法3 - 文本中单个数字: '{clean_text}' -> '{digits_in_text}'")
                        else:
                            print(f"  丢弃 - 数字占比低: '{clean_text}' 数字占比 {digit_ratio:.2f}")
            
            # 选择最佳候选（只保留单个数字）
            if digit_candidates:
                # 按置信度排序
                digit_candidates.sort(key=lambda x: x[1], reverse=True)
                best_digit, best_score, method = digit_candidates[0]
                
                print(f"  最佳数字: {best_digit} (置信度: {best_score:.3f}, 方法: {method})")
                return best_digit
            else:
                print("  未找到有效单个数字")
                return ""
                    
        except Exception as e:
            print(f"提取数字时出错: {e}")
            return ""
        
    def run(self) -> Dict:
        """
        执行数字OCR识别
        
        Returns:
            识别结果字典，格式为{文件名: [数字, 文本描述]}
        """
        print(f"开始处理目录: {self.boxed_digits_path}")
        
        # 获取所有图像文件
        image_files = get_all_image_files(self.boxed_digits_path)
        print(f"找到 {len(image_files)} 个图像文件")
        
        # 存储识别结果
        results = {}
        
        # 按数字前缀分组存储识别结果
        prefix_results = {}
        
        for i, image_path in enumerate(image_files, 1):
            filename = os.path.basename(image_path)
            print(f"处理第 {i}/{len(image_files)} 个文件: {filename}")
            
            try:
                # 执行PaddleOCR识别
                start_time = time.time()
                ocr_result = self.ocr.predict(image_path)
                recognition_time = time.time() - start_time
                
                # 从OCR结果中提取数字
                digit_result = self.extract_digits_from_ocr_result(ocr_result)
                
                # 获取映射的文本描述
                mapped_text = get_mapped_text(filename, digit_result)
                
                # 存储结果（新格式：[数字, 文本描述]）
                results[filename] = [digit_result, mapped_text]
                
                print(f"  识别结果: {digit_result}")
                print(f"  文本映射: {mapped_text}")
                print(f"  处理耗时: {recognition_time:.2f}s")
                
                # 按数字前缀分组存储结果
                prefix_match = filename.split('_')[0]
                if prefix_match not in prefix_results:
                    prefix_results[prefix_match] = {}
                
                # 根据文件名类型存储到对应的字段
                if "discharge" in filename.lower():
                    prefix_results[prefix_match]["离院方式"] = [digit_result, mapped_text]
                elif "gender" in filename.lower():
                    prefix_results[prefix_match]["性别"] = [digit_result, mapped_text]
                
            except Exception as e:
                print(f"  处理文件 {filename} 时出错: {e}")
                results[filename] = ["识别失败", "映射失败"]
        
        # 保存结果
        output_path = os.path.join(self.output_dir, "digit_recognition_results.json")
        save_results_to_json(results, output_path)
        
        # 将识别结果追加到step4 JSON文件中
        self._append_to_step4_json(prefix_results)
        
        # 生成统计报告
        self._generate_report(results)
        
        return results
    
    def _append_to_step4_json(self, prefix_results: Dict) -> None:
        """
        将识别结果追加到step4 JSON文件中
        
        Args:
            prefix_results: 按数字前缀分组的识别结果
        """
        print("\n=== 将识别结果追加到step4 JSON文件 ===")
        
        # step4 JSON文件目录
        step4_dir = "DRG_model/output/step4"
        
        for prefix, fields in prefix_results.items():
            # 构建对应的step4 JSON文件路径
            step4_json_path = os.path.join(step4_dir, f"{prefix}_drg_fields.json")
            
            print(f"处理文件: {step4_json_path}")
            
            try:
                # 检查step4 JSON文件是否存在
                if not os.path.exists(step4_json_path):
                    print(f"  警告: step4 JSON文件不存在: {step4_json_path}")
                    continue
                
                # 读取现有的step4 JSON文件
                with open(step4_json_path, 'r', encoding='utf-8') as f:
                    step4_data = json.load(f)
                
                print(f"  现有字段: {list(step4_data.keys())}")
                
                # 追加新的字段
                for field_name, field_value in fields.items():
                    if field_name in step4_data:
                        print(f"  字段 '{field_name}' 已存在，将覆盖")
                    else:
                        print(f"  添加新字段: '{field_name}'")
                    
                    step4_data[field_name] = field_value
                
                # 保存更新后的JSON文件
                with open(step4_json_path, 'w', encoding='utf-8') as f:
                    json.dump(step4_data, f, ensure_ascii=False, indent=2)
                
                print(f"  ✓ 成功追加字段到: {step4_json_path}")
                print(f"  追加的字段: {list(fields.keys())}")
                
            except Exception as e:
                print(f"  ✗ 处理文件 {step4_json_path} 时出错: {e}")
    
    def _generate_report(self, results: Dict) -> None:
        """
        生成识别结果报告
        
        Args:
            results: 识别结果字典
        """
        print("\n" + "="*50)
        print("\t\tPaddleOCR数字识别报告（带文本映射）")
        print("="*50)
        
        total_files = len(results)
        success_files = sum(1 for result in results.values() if result[0] not in ["", "识别失败"])
        
        print(f"总文件数: {total_files}")
        print(f"成功识别: {success_files}")
        print(f"识别失败: {total_files - success_files}")
        
        print("\n详细结果（格式: [数字, 文本描述]）:")
        print("-"*50)
        for filename, result in results.items():
            print(f"{filename}: {result}")
        
        print("="*50)


def main():
    """主函数，用于独立运行测试"""
    # 定义图像路径
    boxed_digits_path = "DRG_model/output/step6"

    
    # 创建OCR实例
    digit_ocr = DigitOCR(boxed_digits_path)
    
    # 执行OCR识别
    results = digit_ocr.run()
    
    return results


if __name__ == "__main__":
    main()