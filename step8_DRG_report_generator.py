#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import json
import os
import re


class HTMLReportGenerator:
    """HTML报告生成器，复用实验组报告模板以保持样式和交互一致。"""

    def __init__(
        self,
        step4_dir="原始未经扰动的数据跑出的结果step4",
        output_file="output/drg_reports/all_combined_report.html",
        template_file=r"DRG_model\output\drg_reports\combined_report.html",
    ):
        self.step4_dir = step4_dir
        self.output_file = output_file
        self.template_file = template_file
        self.json_files = []

    def load_json_files(self):
        """加载step4目录下的所有JSON文件。"""
        pattern = os.path.join(self.step4_dir, "*_drg_fields.json")
        self.json_files = glob.glob(pattern)
        self.json_files.sort()
        print(f"找到 {len(self.json_files)} 个JSON文件")
        return self.json_files

    def format_diagnosis_with_codes(self, names, codes):
        """
        格式化名称+编码列表为 list[dict]。
        支持组合文本拆分（名称空格分隔、编码使用'、'分隔）。
        """
        names = names or []
        codes = codes or []
        if not names and not codes:
            return []

        result = []
        max_len = max(len(names), len(codes))
        for i in range(max_len):
            name = names[i] if i < len(names) else ""
            code = codes[i] if i < len(codes) else ""

            name = "" if name is None else str(name).strip()
            code = "" if code is None else str(code).strip()

            if not name and not code:
                continue

            if code and ("、" in code) and name and (" " in name):
                code_list = [c.strip() for c in code.split("、") if c.strip()]
                name_list = [n.strip() for n in name.split(" ") if n.strip()]
                min_length = min(len(name_list), len(code_list))
                if min_length > 0:
                    for j in range(min_length):
                        result.append({"name": name_list[j], "code": code_list[j], "is_combined": True})
                    for j in range(min_length, len(name_list)):
                        result.append({"name": name_list[j], "code": "", "is_combined": True})
                    for j in range(min_length, len(code_list)):
                        result.append({"name": "", "code": code_list[j], "is_combined": True})
                    continue

            result.append({"name": name, "code": code, "is_combined": False})

        return result

    def format_drg_data(self, drg_data):
        """格式化DRG数据为前端结构：[field, value, type]。"""

        def format_single_value(values):
            values = values or []
            if not values:
                return ""
            return "；".join([str(v) for v in values])

        gender = format_single_value(drg_data.get("性别", []))
        age = format_single_value(drg_data.get("年龄", []))
        neonatal_age = format_single_value(drg_data.get("年龄不足一周岁的年龄", []))
        discharge_method = format_single_value(drg_data.get("离院方式", []))
        hospitalization_days = format_single_value(drg_data.get("实际住院天数", []))
        total_cost = format_single_value(drg_data.get("住院费用（元）：总费用", []))

        outpatient_diagnosis = self.format_diagnosis_with_codes(
            drg_data.get("门（急）诊诊断", []),
            drg_data.get("门（急）诊诊断编码", []),
        )
        primary_diagnosis = self.format_diagnosis_with_codes(
            drg_data.get("主要诊断", []),
            drg_data.get("主要诊断编码", []),
        )
        other_diagnoses = self.format_diagnosis_with_codes(
            drg_data.get("其他诊断名称", []),
            drg_data.get("其他诊断编码", []),
        )
        procedures = self.format_diagnosis_with_codes(
            drg_data.get("手术及操作名称", []),
            drg_data.get("手术及操作编码", []),
        )
        pathology = self.format_diagnosis_with_codes(
            drg_data.get("病理诊断", []),
            drg_data.get("病理诊断编码", []),
        )

        report_data = [
            ("门（急）诊诊断名称与编码", outpatient_diagnosis, "diagnosis"),
            ("主要诊断名称与编码", primary_diagnosis, "diagnosis"),
            ("其他诊断名称与编码", other_diagnoses, "diagnosis"),
            ("手术及操作名称与编码", procedures, "diagnosis"),
            ("病理诊断名称与编码", pathology, "diagnosis"),
            ("性别", gender, "single"),
            ("年龄", age, "single"),
            ("年龄不足一周岁的年龄", neonatal_age, "single"),
            ("实际住院天数", hospitalization_days, "single"),
            ("离院方式", discharge_method, "single"),
            ("住院费用（元）：总费用", total_cost, "single"),
        ]
        return report_data

    def _build_sidebar_html(self, file_names):
        """生成左侧文件列表HTML。"""
        lines = []
        for i, file_name in enumerate(file_names, 1):
            active_class = "active" if i == 1 else ""
            prefix = file_name.split("_")[0]
            display_name = f"{i:02d}_{prefix}_DRG Report"
            lines.append(
                f'            <li class="file-item {active_class}" onclick="showReport(\'{file_name}\')">{display_name}</li>'
            )
        return "\n".join(lines)

    def _inject_template(self, template_html, file_list_html, file_count, report_data_json):
        """将动态数据注入实验组模板。"""
        # 替换侧边栏文件列表
        template_html = re.sub(
            r'(<ul class="file-list" id="fileList">)([\s\S]*?)(</ul>)',
            r"\1\n" + file_list_html + r"\n        \3",
            template_html,
            count=1,
        )

        # 替换文件计数
        template_html = re.sub(r"共\s*\d+\s*个文件", f"共 {file_count} 个文件", template_html, count=1)

        # 替换报告数据对象
        template_html = re.sub(
            r"const reportData = \{[\s\S]*?\};",
            "const reportData = " + report_data_json + ";",
            template_html,
            count=1,
        )

        return template_html

    def generate_html_content(self):
        """生成HTML内容。"""
        file_data = {}
        for file_path in self.json_files:
            file_name = os.path.basename(file_path)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    drg_data = json.load(f)
                file_data[file_name] = self.format_drg_data(drg_data)
            except Exception as e:
                print(f"加载文件 {file_name} 时出错: {e}")
                file_data[file_name] = []

        if not os.path.exists(self.template_file):
            raise FileNotFoundError(f"模板文件不存在: {self.template_file}")

        with open(self.template_file, "r", encoding="utf-8") as f:
            template_html = f.read()

        file_names = list(file_data.keys())
        file_list_html = self._build_sidebar_html(file_names)
        report_data_json = json.dumps(file_data, ensure_ascii=False, indent=12)

        return self._inject_template(
            template_html=template_html,
            file_list_html=file_list_html,
            file_count=len(file_data),
            report_data_json=report_data_json,
        )

    def run(self):
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        self.load_json_files()
        if not self.json_files:
            print("没有找到JSON文件，无法生成HTML报告")
            return None

        html_content = self.generate_html_content()
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"HTML报告已生成: {self.output_file}")
        return self.output_file


if __name__ == "__main__":
    generator = HTMLReportGenerator(
        step4_dir=r"原始未经扰动的数据跑出的结果step4",
        output_file=r"output/drg_reports/all_combined_report.html",
        template_file=r"DRG_model\\output\\drg_reports\\combined_report.html",
    )
    result_file = generator.run()
    if result_file:
        print(f"报告文件路径: {result_file}")
        print("请在浏览器中打开该文件查看报告")
