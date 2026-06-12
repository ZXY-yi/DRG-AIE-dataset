# main.py
import os
import glob
import importlib.util
import step2_group_line_diag_advanced as step2_diag
import step2_group_line_proc_advanced as step2_proc
import step2_2_group_texts_by_diag_column as step2_2_diag
import step2_3_group_texts_by_procedure_column as step2_3_proc
import step2_4_cell_diag_recognition_simple as step2_4_diag
import step2_4_cell_proc_recognition_simple as step2_4_proc
import step3_field_extractor as step3_field
import step4_extract_drg_fields as step4_drg
import step5_extract_discharge_img as step5_discharge
import step5_extract_gender_img as step5_gender
import DRG_model.step6_detect_boxed_digits as step6_boxed_digits
import step7_digit_ocr as step7_digit_ocr
import DRG_model.step8_DRG_report_generator as step8_DRG_report_generator


def run_step1_ocr_all():
    """
    执行Step1 OCR批量识别（step1_ocrgpu_all.py）
    """
    print("\n=== 开始执行Step1 OCR批量识别 ===")
    module_path = os.path.join("DRG_model", "step1_ocrgpu_all.py")
    spec = importlib.util.spec_from_file_location("step1_ocrgpu_all_module", module_path)
    if spec is None or spec.loader is None:
        print(f"无法加载模块: {module_path}")
        return False
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        ocr_runner = module.OCRGPU()
        result = ocr_runner.run()
        print(
            f"Step1 OCR完成: 处理 {result.get('processed_count', 0)}/{result.get('total_files', 0)} 个文件, "
            f"总耗时 {result.get('total_time_seconds', 0):.2f}s"
        )
        return True
    except Exception as e:
        import traceback
        print(f"Step1 OCR执行失败: {e}")
        print(traceback.format_exc())
        return False

def run_step8_html_report():
    """
    执行Step8 HTML报告生成（step8_html_report_generator.py）
    """
    print("\n=== 开始执行Step8 HTML报告生成 ===")
    try:
        generator = step8_DRG_report_generator.HTMLReportGenerator(
            step4_dir="DRG_model/output/step4",
            output_file="DRG_model/output/drg_reports/combined_report.html",
            template_file=r"DRG_model\output\drg_reports\实验组_combined_report.html",
        )
        result = generator.run()
        return bool(result)
    except Exception as e:
        import traceback
        print(f"Step8 HTML报告生成失败: {e}")
        print(traceback.format_exc())
        return False

def get_file_pairs():
    """
    获取需要处理的文件对
    
    返回:
        list: 包含文件对信息的列表，每个元素为字典
    """
    # 基础目录路径（相对于当前工作目录DRG_model）
    step1_ocr_diag_dir = "DRG_model/output/step1"
    step1_ocr_proc_dir = "DRG_model/output/step1"
    ocr_gender_png_digit = "DRG_model/output/step0-digit-600kb"
    ocr_discharge_png_digit = "DRG_model/output/step0-digit-600kb"
    ocr_diag_png_desc = "DRG_model/output/step0-discribe-100kb"
    ocr_proc_png_desc = "DRG_model/output/step0-discribe-100kb"
    
    # 获取step1目录下的所有诊断页JSON文件（后缀为_page_1.json）
    step1_diag_files = glob.glob(os.path.join(step1_ocr_diag_dir, "*_page_1.json"))
    
    file_pairs = []
    
    for step1_diag_file in step1_diag_files:
        # 从文件名中提取基础名称（如"01_page_1"）
        base_name = os.path.basename(step1_diag_file)
        
        # 提取文件前缀（如"01"）
        prefix_match = base_name.split('_')[0]
        
        # 生成对应的手术页文件路径
        step1_proc_file = step1_diag_file.replace('_page_1.json', '_page_2.json')
        
        # 构建文件对
        file_pair = {
            'prefix': prefix_match,
            'step1_ocr_diag_dir': step1_diag_file,  # 后缀为1的JSON文件（诊断页）
            'step1_ocr_proc_dir': step1_proc_file,  # 后缀为2的JSON文件（手术页）
            'ocr_gender_png_digit': os.path.join(ocr_gender_png_digit, f"{prefix_match}_page_1.png"),  # 后缀为1的PNG文件
            'ocr_discharge_png_digit': os.path.join(ocr_discharge_png_digit, f"{prefix_match}_page_2.png"),  # 后缀为2的PNG文件
            'ocr_diag_png_desc': os.path.join(ocr_diag_png_desc, f"{prefix_match}_page_1.png"),  # 后缀为1的PNG文件
            'ocr_proc_png_desc': os.path.join(ocr_proc_png_desc, f"{prefix_match}_page_2.png")   # 后缀为2的PNG文件
        }
        
        # 检查所有文件是否存在
        all_files_exist = True
        for key, file_path in file_pair.items():
            if key.startswith('step1_') and not os.path.exists(file_path):
                print(f"警告: 文件不存在，跳过处理: {file_path}")
                all_files_exist = False
                break
        
        if all_files_exist:
            file_pairs.append(file_pair)
    
    return file_pairs

def process_single_pair(file_pair):
    """
    处理单个文件对（step2~step6）
    
    参数:
        file_pair: 文件对信息字典
    
    返回:
        tuple: (是否成功, 错误信息)
    """
    prefix = file_pair['prefix']
    print(f"\n=== 开始处理文件对: {prefix} ===")
    
    try:
        # Step2: 行分组
        # print(f"[{prefix}] Step2: 行分组处理...")
        step2_instance_diag = step2_diag.GroupLineDiagAdvanced(file_pair['step1_ocr_diag_dir'])
        step2_line_diag = step2_instance_diag.run()  # Line diag
        
        step2_instance_proc = step2_proc.GroupTextsByLineAdvanced(file_pair['step1_ocr_proc_dir'])    
        step2_line_proc = step2_instance_proc.run()  # Line proc
        print(f"[{prefix}] step2_line_diag:", step2_line_diag)
        print(f"[{prefix}] step2_line_proc:", step2_line_proc)
        # Step2.2 & 2.3: 列分组
        # print(f"[{prefix}] Step2.2 & 2.3: 列分组处理...")
        step2_column_diag = step2_2_diag.GroupTextsByDiagColumn(file_pair['step1_ocr_diag_dir']).run()  # Column diag
        step2_column_proc = step2_3_proc.GroupTextsByProcColumn(file_pair['step1_ocr_proc_dir']).run()  # Column proc
        
        # print(f"[{prefix}] step2_column_diag:", step2_column_diag)
        
        # 检查列分组结果是否有效
        if step2_column_diag is None:
            error_msg = f"诊断列分组失败"
            # print(f"[{prefix}] 错误: {error_msg}")
            return False, error_msg
        if step2_column_proc is None:
            error_msg = f"手术列分组失败"
            # print(f"[{prefix}] 错误: {error_msg}")
            return False, error_msg
        
        # Step2.4: 单元格识别
        # print(f"[{prefix}] Step2.4: 单元格识别处理...")
        step2_4_diag.CellDiagRecognitionSimple(step2_line_diag, step2_column_diag, file_pair['step1_ocr_diag_dir']).run()  # Cell diag        
        step2_4_cell_diag_proc_path = step2_4_proc.CellProcRecognitionSimple(step2_line_proc, step2_column_proc, file_pair['step1_ocr_proc_dir']).run()  # Cell proc   
        
        # Step3: 字段提取
        # print(f"[{prefix}] Step3: 字段提取处理...")
        # FieldExtractor 需要目录，保证同时读取诊断/手术的 step2.4 输出
        if step2_4_cell_diag_proc_path and os.path.isdir(step2_4_cell_diag_proc_path):
            step2_4_dir = step2_4_cell_diag_proc_path
        else:
            step2_4_dir = os.path.dirname(step2_4_cell_diag_proc_path) if step2_4_cell_diag_proc_path else "DRG_model/output/step2.4"
        step3_diag_proc_json = step3_field.FieldExtractor(step2_4_dir).run()  # Field extractor
        
        # Step4: DRG字段提取
        # print(f"[{prefix}] Step4: DRG字段提取处理...")
        step4_instance = step4_drg.DRGFieldExtractor(step2_line_diag, step2_line_proc, step3_diag_proc_json, file_pair['step1_ocr_diag_dir'])
        step4_output_json = step4_instance.run()  # DRG field extractor
        # print(f"[{prefix}] step4_output_json:", step4_output_json)
        
        # Step5: 图像提取
        # print(f"[{prefix}] Step5: 图像提取处理...")
        step5_discharge_instance = step5_discharge.DischargeMethodExtractor(file_pair['step1_ocr_proc_dir'], file_pair['ocr_discharge_png_digit'], file_pair['ocr_proc_png_desc'])
        step5_discharge_img = step5_discharge_instance.run()  # Discharge method extractor
        # print(f"[{prefix}] step5_discharge_img:", step5_discharge_img)
        
        step5_gender_instance = step5_gender.GenderExtractor(file_pair['step1_ocr_diag_dir'], file_pair['ocr_gender_png_digit'], file_pair['ocr_diag_png_desc'])
        step5_gender_img = step5_gender_instance.run()  # Gender extractor
        # print(f"[{prefix}] step5_gender_img:", step5_gender_img)
        
        # Step6: 带框数字检测
        # print(f"[{prefix}] Step6: 带框数字检测处理...")
        step6_boxed_digits_instance = step6_boxed_digits.BoxedDigitDetector(step5_discharge_img, step5_gender_img, file_pair['step1_ocr_diag_dir'])
        step6_boxed_digits_img = step6_boxed_digits_instance.run()  # Boxed digit detector
        # print(f"[{prefix}] step6_boxed_digits_img:", step6_boxed_digits_img)
        
        # Step7: 数字OCR
        
        
        print(f"[{prefix}] ✓ 处理完成")
        return True, ""
        
    except Exception as e:
        import traceback
        error_msg = f"处理异常: {str(e)}\n{traceback.format_exc()}"
        print(f"[{prefix}] ✗ 处理失败: {error_msg}")
        return False, error_msg

def main():
    """主函数 - 批量处理所有文件对"""
    print("开始批量处理文件对...")
    
    # 清空输出目录
    print("清空输出目录...")
    clear_output_directories()

    # 执行Step1 OCR批量识别
    if not run_step1_ocr_all():
        print("Step1 OCR失败，终止后续处理。")
        return
    
    # 获取所有文件对
    file_pairs = get_file_pairs()
    
    if not file_pairs:
        print("未找到可处理的文件对")
        return
    
    print(f"找到 {len(file_pairs)} 个文件对需要处理")
    
    # 统计处理结果和错误信息
    success_count = 0
    fail_count = 0
    error_reports = []
    
    # 循环处理每个文件对
    for i, file_pair in enumerate(file_pairs, 1):
        print(f"\n处理进度: {i}/{len(file_pairs)}")
        
        success, error_msg = process_single_pair(file_pair)
        if success:
            success_count += 1
        else:
            fail_count += 1
            error_reports.append({
                'prefix': file_pair['prefix'],
                'error': error_msg,
                'files': {
                    'diagnosis_json': file_pair['step1_ocr_diag_dir'],
                    'procedure_json': file_pair['step1_ocr_proc_dir'],
                    'gender_png': file_pair['ocr_gender_png_digit'],
                    'discharge_png': file_pair['ocr_discharge_png_digit'],
                    'diagnosis_desc_png': file_pair['ocr_diag_png_desc'],
                    'procedure_desc_png': file_pair['ocr_proc_png_desc']
                }
            })
    
    # 输出处理统计
    print(f"\n=== 批量处理完成 ===")
    print(f"成功处理: {success_count} 个文件对")
    print(f"处理失败: {fail_count} 个文件对")
    print(f"总处理数: {len(file_pairs)} 个文件对")
    
    # 输出详细的错误报告
    if error_reports:
        print(f"\n=== 详细错误报告 ===")
        for i, report in enumerate(error_reports, 1):
            print(f"\n错误 {i} - 文件前缀: {report['prefix']}")
            print(f"  诊断JSON文件: {report['files']['diagnosis_json']}")
            print(f"  手术JSON文件: {report['files']['procedure_json']}")
            print(f"  性别PNG文件: {report['files']['gender_png']}")
            print(f"  出院PNG文件: {report['files']['discharge_png']}")
            print(f"  诊断描述PNG文件: {report['files']['diagnosis_desc_png']}")
            print(f"  手术描述PNG文件: {report['files']['procedure_desc_png']}")
            print(f"  错误原因: {report['error']}")
    
    # 生成错误报告文件
    generate_error_report(error_reports, success_count, fail_count, len(file_pairs))

    # Step8: HTML报告生成
    if not run_step8_html_report():
        print("Step8 HTML报告生成失败。")

def generate_error_report(error_reports, success_count, fail_count, total_count):
    """
    生成详细的错误报告文件
    
    参数:
        error_reports: 错误报告列表
        success_count: 成功处理数量
        fail_count: 失败处理数量
        total_count: 总处理数量
    """
    if not error_reports:
        print("没有错误需要报告")
        return
    
    # 创建错误报告目录
    report_dir = "output/error_reports"
    os.makedirs(report_dir, exist_ok=True)
    
    # 生成报告文件名（包含时间戳）
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(report_dir, f"batch_processing_report_{timestamp}.txt")
    
    # 写入错误报告
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=== 批量处理错误报告 ===\n")
        f.write(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"成功处理: {success_count} 个文件对\n")
        f.write(f"处理失败: {fail_count} 个文件对\n")
        f.write(f"总处理数: {total_count} 个文件对\n")
        f.write(f"成功率: {success_count/total_count*100:.2f}%\n")
        f.write("\n" + "="*50 + "\n\n")
        
        # 写入每个错误的详细信息
        for i, report in enumerate(error_reports, 1):
            f.write(f"错误 {i} - 文件前缀: {report['prefix']}\n")
            f.write(f"诊断JSON文件: {report['files']['diagnosis_json']}\n")
            f.write(f"手术JSON文件: {report['files']['procedure_json']}\n")
            f.write(f"性别PNG文件: {report['files']['gender_png']}\n")
            f.write(f"出院PNG文件: {report['files']['discharge_png']}\n")
            f.write(f"诊断描述PNG文件: {report['files']['diagnosis_desc_png']}\n")
            f.write(f"手术描述PNG文件: {report['files']['procedure_desc_png']}\n")
            f.write(f"错误原因:\n{report['error']}\n")
            f.write("\n" + "-"*50 + "\n\n")
    
    print(f"错误报告已保存到: {report_file}")
    
    # 生成错误统计摘要
    generate_error_summary(error_reports, report_dir, timestamp)

def clear_output_directories():
    """清空指定的输出目录"""
    # 需要清空的目录列表
    directories_to_clear = [
        "DRG_model/output/step2",
        "DRG_model/output/step2.2", 
        "DRG_model/output/step2.3",
        "DRG_model/output/step2.4",
        "DRG_model/output/step3",
        "DRG_model/output/step4",
        "DRG_model/output/step5-discharge_method",
        "DRG_model/output/step5-gender",
        "DRG_model/output/step6",
        "DRG_model\output\step7"
    ]
    
    for directory in directories_to_clear:
        try:
            # 检查目录是否存在
            if os.path.exists(directory):
                # 删除目录中的所有文件
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            print(f"  删除文件: {file_path}")
                        elif os.path.isdir(file_path):
                            import shutil
                            shutil.rmtree(file_path)
                            print(f"  删除目录: {file_path}")
                    except Exception as e:
                        print(f"  删除失败 {file_path}: {e}")
                print(f"✓ 清空目录: {directory}")
            else:
                print(f"⚠ 目录不存在: {directory}")
        except Exception as e:
            print(f"✗ 清空目录失败 {directory}: {e}")

def generate_error_summary(error_reports, report_dir, timestamp):
    """
    生成错误统计摘要
    
    参数:
        error_reports: 错误报告列表
        report_dir: 报告目录
        timestamp: 时间戳
    """
    import datetime
    
    # 统计错误类型
    error_types = {}
    for report in error_reports:
        error_msg = report['error']
        
        # 分类错误类型
        if "诊断列分组失败" in error_msg:
            error_type = "诊断列分组失败"
        elif "手术列分组失败" in error_msg:
            error_type = "手术列分组失败"
        elif "ModuleNotFoundError" in error_msg:
            error_type = "模块导入错误"
        elif "FileNotFoundError" in error_msg:
            error_type = "文件不存在"
        elif "JSONDecodeError" in error_msg:
            error_type = "JSON解析错误"
        elif "KeyError" in error_msg:
            error_type = "键错误"
        elif "IndexError" in error_msg:
            error_type = "索引错误"
        elif "AttributeError" in error_msg:
            error_type = "属性错误"
        else:
            error_type = "其他错误"
        
        error_types[error_type] = error_types.get(error_type, 0) + 1
    
    # 生成摘要文件
    summary_file = os.path.join(report_dir, f"error_summary_{timestamp}.txt")
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("=== 错误统计摘要 ===\n")
        f.write(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总错误数: {len(error_reports)}\n\n")
        
        f.write("错误类型统计:\n")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(error_reports) * 100
            f.write(f"  {error_type}: {count} 次 ({percentage:.1f}%)\n")
        
        f.write("\n建议解决方案:\n")
        
        if "模块导入错误" in error_types:
            f.write("  1. 模块导入错误: 请检查是否安装了所有必需的Python包\n")
            f.write("     运行: pip install opencv-python numpy pillow\n")
        
        if "文件不存在" in error_types:
            f.write("  2. 文件不存在: 请检查文件路径和文件名是否正确\n")
        
        if "诊断列分组失败" in error_types or "手术列分组失败" in error_types:
            f.write("  3. 列分组失败: 可能是OCR识别质量问题，建议检查原始图像质量\n")
        
        if "JSON解析错误" in error_types:
            f.write("  4. JSON解析错误: 请检查JSON文件格式是否正确\n")
        
        f.write("\n详细错误信息请查看完整错误报告文件。\n")
    
    print(f"错误统计摘要已保存到: {summary_file}")

class AdvancedHTMLReportGenerator:
    """
    高级HTML报告生成器
    基于step4目录下的JSON文件生成响应式HTML报告
    """
    
    def __init__(self, step4_dir="DRG_model/output/step4", output_file="DRG_model/output/drg_reports/advanced_report.html"):
        self.step4_dir = step4_dir
        self.output_file = output_file
        self.json_files = []
        self.report_data = {}
    
    def load_json_files(self):
        """加载step4目录下的所有JSON文件，处理编码和读取异常"""
        import glob
        
        try:
            # 检查目录是否存在
            if not os.path.exists(self.step4_dir):
                print(f"错误: 目录不存在 - {self.step4_dir}")
                return []
            
            # 获取所有JSON文件
            pattern = os.path.join(self.step4_dir, "*_drg_fields.json")
            self.json_files = glob.glob(pattern)
            self.json_files.sort()  # 按文件名排序
            
            print(f"找到 {len(self.json_files)} 个JSON文件")
            return self.json_files
            
        except Exception as e:
            print(f"加载JSON文件时发生错误: {e}")
            return []
    
    def parse_json_file(self, file_path):
        """解析单个JSON文件，处理编码和格式异常"""
        try:
            # 尝试多种编码方式读取文件
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read().strip()
                        
                    # 检查文件内容是否为空
                    if not content:
                        print(f"警告: 文件为空 - {file_path}")
                        return None
                        
                    # 解析JSON
                    data = json.loads(content)
                    return data
                    
                except UnicodeDecodeError:
                    continue
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误 ({encoding}): {file_path} - {e}")
                    return None
            
            print(f"错误: 无法解析文件编码 - {file_path}")
            return None
            
        except Exception as e:
            print(f"读取文件时发生未知错误: {file_path} - {e}")
            return None
    
    def generate_html_report(self):
        """生成响应式HTML报告"""
        
        # 加载所有JSON数据
        json_files = self.load_json_files()
        if not json_files:
            print("没有找到JSON文件，无法生成报告")
            return None
        
        # 解析所有JSON文件
        report_data = {}
        for file_path in json_files:
            file_name = os.path.basename(file_path)
            data = self.parse_json_file(file_path)
            if data:
                report_data[file_name] = data
        
        if not report_data:
            print("没有成功解析任何JSON文件")
            return None
        
        # 生成HTML内容
        html_content = self._generate_html_content(report_data)
        
        # 确保输出目录存在
        output_dir = os.path.dirname(self.output_file)
        os.makedirs(output_dir, exist_ok=True)
        
        # 写入HTML文件
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✓ 高级HTML报告已生成: {self.output_file}")
            return self.output_file
            
        except Exception as e:
            print(f"生成HTML文件时发生错误: {e}")
            return None
    
    def _generate_html_content(self, report_data):
        """生成HTML内容"""
        
        # 生成文件列表HTML
        file_list_html = ''
        for i, file_name in enumerate(report_data.keys()):
            active_class = 'active' if i == 0 else ''
            file_list_html += f'''
            <li class="file-item {active_class}" onclick="showReport('{file_name}')">{file_name.replace('_drg_fields.json', '')}</li>'''
        
        # 生成报告数据JavaScript
        report_data_js = 'const reportData = {\n'
        for file_name, data in report_data.items():
            # 将数据转换为JSON字符串，确保正确处理中文字符
            data_str = json.dumps(data, ensure_ascii=False, indent=2)
            report_data_js += f'    "{file_name}": {data_str},\n'
        report_data_js = report_data_js.rstrip(',\n') + '\n};'
        
        html_template = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DRG高级报告汇总</title>
    <style>
        /* 响应式设计 */
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }}
        
        .header {{
            background-color: #3498db;
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 24px;
            font-weight: bold;
        }}
        
        .container {{
            display: flex;
            flex: 1;
            flex-direction: row;
        }}
        
        .sidebar {{
            width: 250px;
            background-color: #2c3e50;
            color: white;
            overflow-y: auto;
            box-shadow: 2px 0 5px rgba(0,0,0,0.1);
        }}
        
        .sidebar-header {{
            padding: 20px;
            background-color: #3498db;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
        }}
        
        .file-list {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        
        .file-item {{
            padding: 12px 20px;
            border-bottom: 1px solid #34495e;
            cursor: pointer;
            transition: background-color 0.2s;
        }}
        
        .file-item:hover {{
            background-color: #34495e;
        }}
        
        .file-item.active {{
            background-color: #3498db;
            font-weight: bold;
        }}
        
        .main-content {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background-color: white;
        }}
        
        .report-container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 8px;
            padding: 20px;
        }}
        
        h1 {{
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 500;
        }}
        
        td {{
            padding: 12px;
            border: 1px solid #ddd;
            background-color: white;
            vertical-align: middle;
        }}
        
        tr:hover td {{
            background-color: #f8f9fa;
        }}
        
        .field-name {{
            font-weight: 500;
            color: #2c3e50;
            background-color: #f0f7ff;
        }}
        
        .no-data {{
            text-align: center;
            color: #999;
            padding: 40px;
            font-size: 16px;
        }}
        
        .file-count {{
            padding: 10px 20px;
            font-size: 12px;
            color: #bdc3c7;
            border-top: 1px solid #34495e;
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .container {{
                flex-direction: column;
            }}
            
            .sidebar {{
                width: 100%;
                max-height: 200px;
            }}
            
            .header {{
                font-size: 20px;
                padding: 15px;
            }}
            
            table {{
                font-size: 14px;
            }}
            
            th, td {{
                padding: 8px;
            }}
        }}
        
        @media (max-width: 480px) {{
            .header {{
                font-size: 18px;
                padding: 10px;
            }}
            
            table {{
                font-size: 12px;
            }}
            
            th, td {{
                padding: 6px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        DRG高级报告汇总
    </div>
    
    <div class="container">
        <div class="sidebar">
            <div class="sidebar-header">
                文件列表
            </div>
            <ul class="file-list" id="fileList">
                {file_list_html}
            </ul>
            <div class="file-count">
                共 {len(report_data)} 个文件
            </div>
        </div>
        
        <div class="main-content">
            <div class="report-container" id="reportContainer">
                <div class="no-data">请从左侧选择文件查看报告</div>
            </div>
        </div>
    </div>
    
    <script>
        // 存储所有报告数据
        {report_data_js}
        
        function showReport(fileName) {{
            const data = reportData[fileName];
            const container = document.getElementById('reportContainer');
            
            if (!data) {{
                container.innerHTML = '<div class="no-data">数据加载失败</div>';
                return;
            }}
            
            // 更新活跃的文件项
            document.querySelectorAll('.file-item').forEach(item => {{
                item.classList.remove('active');
            }});
            document.querySelector(`[onclick="showReport('${{fileName}}')"]`).classList.add('active');
            
            // 生成报告内容
            let html = '<h1>' + fileName.replace('_drg_fields.json', '') + ' - 详细报告</h1>';
            
            // 根据数据结构生成表格
            if (Array.isArray(data)) {{
                html += '<table>';
                html += '<tr><th>字段名</th><th>值</th></tr>';
                
                data.forEach(item => {{
                    if (Array.isArray(item) && item.length >= 2) {{
                        html += `<tr><td class="field-name">${{item[0]}}</td><td>${{this.formatValue(item[1])}}</td></tr>`;
                    }}
                }});
                
                html += '</table>';
            }} else if (typeof data === 'object') {{
                html += '<table>';
                html += '<tr><th>字段名</th><th>值</th></tr>';
                
                Object.entries(data).forEach(([key, value]) => {{
                    html += `<tr><td class="field-name">${{key}}</td><td>${{this.formatValue(value)}}</td></tr>`;
                }});
                
                html += '</table>';
            }}
            
            container.innerHTML = html;
        }}
        
        function formatValue(value) {{
            if (Array.isArray(value)) {{
                return value.map(item => this.formatValue(item)).join('<br>');
            }} else if (typeof value === 'object' && value !== null) {{
                return JSON.stringify(value, null, 2).replace(/\\n/g, '<br>').replace(/ /g, '&nbsp;');
            }}
            return value;
        }}
        
        // 默认显示第一个文件
        if (Object.keys(reportData).length > 0) {{
            showReport(Object.keys(reportData)[0]);
        }}
    </script>
</body>
</html>'''
        
        return html_template
    
    def run(self):
        """运行报告生成器"""
        print("=== 开始生成高级HTML报告 ===")
        
        try:
            result = self.generate_html_report()
            if result:
                print("✓ 高级HTML报告生成完成")
            else:
                print("✗ 高级HTML报告生成失败")
            
            return result
            
        except Exception as e:
            print(f"生成高级HTML报告时发生错误: {e}")
            return None


def generate_advanced_report():
    """生成高级HTML报告的便捷函数"""
    generator = AdvancedHTMLReportGenerator()
    return generator.run()


if __name__ == '__main__':
    main()
    # print(f"[{prefix}] Step7: 数字OCR处理...")
    
    # 获取step6输出的带框数字图像目录
    step6_output_dir = "DRG_model\output\step6"
    
    # 创建step7实例并执行OCR识别
    step7_digit_ocr_instance = step7_digit_ocr.DigitOCR(step6_output_dir)
    step7_digit_ocr_results = step7_digit_ocr_instance.run()  # Digit OCR
    # print(f"[{prefix}] step7_digit_ocr_results:", step7_digit_ocr_results)

    # 可选：生成高级HTML报告
    # generate_advanced_report()
