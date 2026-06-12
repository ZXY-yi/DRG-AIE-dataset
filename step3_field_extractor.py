#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import re
import glob

def extract_other_diagnoses_from_json(json_data):
    """
    从JSON数据中提取其他诊断信息（增强容错性版本）
    
    参数:
        json_data: 包含诊断信息的JSON数据
        
    返回:
        包含诊断名称和编码的字典
    """
    try:
        diagnosis_names = []
        diagnosis_codes = []

        # 安全获取columns数据，处理可能的异常
        columns = json_data.get('columns', [])
        if not columns:
            print("警告: JSON数据中未找到columns字段")
            return {"其他诊断": [], "其他诊断编码": []}

        print(f"开始识别诊断列，共{len(columns)}列")

        # 基于内容识别列，增强容错性
        name_column = None   # 包含诊断名称的列
        code_column = None   # 包含诊断编码的列

        def _is_diag_code_text(text):
            t = str(text or "").strip().upper()
            if not t:
                return False
            # ICD 常见格式：A00 / A00.0 / A00.000x001 / B02.305+H22.0
            if re.search(r"[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?(?:\+[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?)?", t):
                return True
            # 兼容 OCR 将 O 识别成 0 的情况：0xx.xxx
            if re.search(r"0\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?", t):
                return True
            return False

        for col_idx, column in enumerate(columns):
            if not column or len(column) == 0:
                print(f"警告: 列{col_idx}为空，跳过")
                continue
                
            try:
                # 安全获取第一项文本，处理可能的索引错误
                first_item = column[0] if isinstance(column, list) else column
                if isinstance(first_item, list) and len(first_item) > 0:
                    first_item_text = str(first_item[0])  # 转换为字符串避免类型错误
                else:
                    first_item_text = str(first_item)
                
                print(f"列{col_idx}: 首项='{first_item_text}'")
                
                # 诊断名称列：增强容错性，处理OCR识别错误
                name_variants = ['其他诊断', '他诊断', '他诊', '诊断', '分娩', '孕', '产']
                for variant in name_variants:
                    if variant in first_item_text:
                        if not name_column:  # 只设置一次，避免被后续列覆盖
                            name_column = column
                            print(f"  [OK] 识别为名称列 (变体: '{variant}')")
                        break
                
                # 诊断编码列：按整列“编码命中率”判定，避免把短文本名称列误判为编码列
                hits = 0
                total = 0
                for item in column:
                    if isinstance(item, list) and len(item) > 0:
                        txt = str(item[0])
                    else:
                        txt = str(item)
                    if not str(txt).strip():
                        continue
                    total += 1
                    if _is_diag_code_text(txt):
                        hits += 1

                is_code_column = (total > 0 and hits / total >= 0.5)
                if is_code_column and not code_column:  # 只设置一次，避免被后续列覆盖
                    code_column = column
                    print(f"  [OK] 识别为编码列 (列{col_idx}, 命中率={hits}/{total})")
                    
            except (IndexError, TypeError, AttributeError) as e:
                print(f"警告: 处理列{col_idx}时发生异常: {e}")
                continue

        # 兜底：若未识别到名称/编码列，使用诊断规则再扫描一次
        if not name_column:
            name_header_re = re.compile(r"(其他诊断|他诊断|诊断)")
            for column in columns:
                if not column:
                    continue
                first_item = column[0] if isinstance(column, list) else column
                first_text = str(first_item[0]) if isinstance(first_item, list) and len(first_item) > 0 else str(first_item)
                if name_header_re.search(first_text):
                    name_column = column
                    print("  [fallback] set name_column by regex")
                    break

        if not code_column:
            best_col = None
            best_hits = -1
            best_total = 1
            for column in columns:
                if not column:
                    continue
                hits = 0
                total = 0
                for item in column:
                    if isinstance(item, list) and len(item) > 0:
                        txt = str(item[0])
                    else:
                        txt = str(item)
                    if not str(txt).strip():
                        continue
                    total += 1
                    if _is_diag_code_text(txt):
                        hits += 1
                if total > 0 and (hits / total > best_hits / best_total):
                    best_col, best_hits, best_total = column, hits, total
            if best_col is not None and best_hits > 0:
                code_column = best_col
                print(f"  [fallback] set code_column by max hit rate ({best_hits}/{best_total})")

        # 调试输出
        print(f"识别结果 - 名称列: {'找到' if name_column else '未找到'}")
        print(f"识别结果 - 编码列: {'找到' if code_column else '未找到'}")
        
        if not name_column or not code_column:
            print("警告: 未找到诊断名称列或编码列")
            if name_column:
                print(f"名称列内容: {[item[0] for item in name_column if isinstance(item, list)]}")
            if code_column:
                print(f"编码列内容: {[item[0] for item in code_column if isinstance(item, list)]}")
            return {"其他诊断": [], "其他诊断编码": []}

        # 安全提取文本内容
        try:
            name_texts = []
            for item in name_column:
                if isinstance(item, list) and len(item) > 0:
                    name_texts.append(str(item[0]))  # 转换为字符串避免类型错误
                elif isinstance(item, str):
                    name_texts.append(item)
            
            code_texts = []
            for item in code_column:
                if isinstance(item, list) and len(item) > 0:
                    code_texts.append(str(item[0]))  # 转换为字符串避免类型错误
                elif isinstance(item, str):
                    code_texts.append(item)
                    
            print(f"诊断名称列内容: {name_texts}")
            print(f"诊断编码列内容: {code_texts}")
            
        except (IndexError, TypeError) as e:
            print(f"错误: 提取文本内容时发生异常: {e}")
            return {"其他诊断": [], "其他诊断编码": []}

        # 处理诊断名称：清理前缀并跳过表头
        processed_names = []
        for name in name_texts:
            # 清理"其他诊断："前缀
            cleaned_name = re.sub(r'^其他诊断[：: ]*', '', name.strip())
            # 跳过空字符串或表头
            if cleaned_name and cleaned_name not in ['其他诊断', '诊断']:
                processed_names.append(cleaned_name)
        
        # 处理诊断编码：保持原有校验规则，只接受有效编码
        processed_codes = []
        for code in code_texts:
            # 保持原有编码格式验证
            if (re.search(r'[A-Za-z]\d+', code) or 
                re.search(r'\d+\.\d+', code) or 
                re.match(r'^\d+$', code.strip())):
                processed_codes.append(code.strip())
        
        # 确保两个列表长度一致
        min_length = min(len(processed_names), len(processed_codes))
        
        if min_length == 0:
            print("警告: 未找到有效的诊断名称或编码")
            return {"其他诊断": [], "其他诊断编码": []}

        # 提取诊断信息
        for i in range(min_length):
            diagnosis_name = processed_names[i]
            diagnosis_code = processed_codes[i]

            if diagnosis_name and diagnosis_code:
                diagnosis_names.append(diagnosis_name)
                diagnosis_codes.append(diagnosis_code)
                print(f"提取其他诊断: {diagnosis_name} / {diagnosis_code}")

        return {
            "其他诊断": diagnosis_names,
            "其他诊断编码": diagnosis_codes
        }
        
    except Exception as e:
        print(f"错误: 提取诊断信息时发生异常: {e}")
        return {"其他诊断": [], "其他诊断编码": []}


def extract_operations_from_json(json_data):
    """
    从JSON数据中提取手术及操作信息（增强容错性版本）
    
    参数:
        json_data: 包含手术信息的JSON数据
        
    返回:
        包含手术名称和编码的字典
    """
    try:
        procedure_names = []
        procedure_codes = []

        # 安全获取columns数据，处理可能的异常
        columns = json_data.get('columns', [])
        if not columns:
            print("警告: JSON数据中未找到columns字段")
            return {"手术及操作": [], "手术及操作编码": []}

        print(f"开始识别手术及操作列，共{len(columns)}列")

        # 基于内容识别列，增强容错性
        name_column = None   # 包含手术名称的列
        code_column = None   # 包含手术编码的列

        for col_idx, column in enumerate(columns):
            if not column or len(column) == 0:
                print(f"警告: 列{col_idx}为空，跳过")
                continue
                
            try:
                # 安全获取第一项文本，处理可能的索引错误
                first_item = column[0] if isinstance(column, list) else column
                if isinstance(first_item, list) and len(first_item) > 0:
                    first_item_text = str(first_item[0])  # 转换为字符串避免类型错误
                else:
                    first_item_text = str(first_item)
                
                print(f"列{col_idx}: 首项='{first_item_text}'")
                
                # 手术名称列：增强容错性，处理OCR识别错误
                name_variants = ['手术及操作名称', '手术', '操作', '治疗', '放射', '化疗', '静脉注射']
                for variant in name_variants:
                    if variant in first_item_text:
                        if not name_column:  # 只设置一次，避免被后续列覆盖
                            name_column = column
                            print(f"  [OK] 识别为名称列 (变体: '{variant}')")
                        break
                
                # 特殊处理：如果找到"手术及操作名称"，优先使用此列
                if '手术及操作名称' in first_item_text:
                    if name_column and name_column != column:
                        print(f"  [OK] 优先使用包含'手术及操作名称'的列 (列{col_idx})")
                    name_column = column
                    print(f"  [OK] 识别为名称列 (包含'手术及操作名称')")
                
                # 手术编码列：取消严格校验，接受更多文本作为编码列
                is_code_column = False
                
                # 模式1：如果列索引为0，可能是编码列
                if col_idx == 0:
                    is_code_column = True
                    print(f"  - 模式1匹配: 列索引为0")
                
                # 模式2：如果列索引为1且名称列已找到，则可能是编码列
                elif col_idx == 1 and name_column:
                    is_code_column = True
                    print(f"  - 模式2匹配: 列索引为1且名称列已找到")
                
                # 模式3：如果文本包含数字，可能是编码列
                elif re.search(r'\d+', first_item_text):
                    is_code_column = True
                    print(f"  - 模式3匹配: 包含数字")
                
                # 模式4：如果文本长度较短（<10字符），可能是编码列
                elif len(first_item_text.strip()) < 10:
                    is_code_column = True
                    print(f"  - 模式4匹配: 长度较短")
                
                # 模式5：如果文本不是表头文本，可能是编码列
                elif first_item_text.strip() not in ['手术及操作名称', '手术', '操作', '术者', 'I助', 'Ⅱ助', '等级', '麻醉方式', '师']:
                    is_code_column = True
                    print(f"  - 模式5匹配: 不是表头文本")
                
                if is_code_column and not code_column:  # 只设置一次，避免被后续列覆盖
                    code_column = column
                    print(f"  [OK] 识别为编码列 (列{col_idx})")
                    
            except (IndexError, TypeError, AttributeError) as e:
                print(f"警告: 处理列{col_idx}时发生异常: {e}")
                continue

        # 调试输出
        print(f"识别结果 - 名称列: {'找到' if name_column else '未找到'}")
        print(f"识别结果 - 编码列: {'找到' if code_column else '未找到'}")
        
        # 如果没有找到编码列，尝试从名称列中提取编码
        if not code_column and name_column:
            print("警告: 未找到单独的编码列，尝试从名称列中提取编码...")
            
            # 尝试从名称列中提取编码
            name_texts = []
            for item in name_column:
                if isinstance(item, list) and len(item) > 0:
                    name_texts.append(str(item[0]))
                elif isinstance(item, str):
                    name_texts.append(item)
            
            # 检查名称列中是否包含编码
            potential_codes = []
            for text in name_texts:
                # 查找括号中的编码
                bracket_match = re.search(r'[\[\【]([A-Za-z0-9\.]+)[\]\】]', text)
                if bracket_match:
                    potential_codes.append(bracket_match.group(1))
                    print(f"  [OK] 从名称中提取编码: {bracket_match.group(1)}")
                
                # 查找数字.数字格式的编码
                dot_match = re.search(r'\b\d+\.\d+\b', text)
                if dot_match:
                    potential_codes.append(dot_match.group(0))
                    print(f"  [OK] 从名称中提取编码: {dot_match.group(0)}")
                
                # 查找字母+数字格式的编码
                alpha_match = re.search(r'\b[A-Za-z]\d+\b', text)
                if alpha_match:
                    potential_codes.append(alpha_match.group(0))
                    print(f"  [OK] 从名称中提取编码: {alpha_match.group(0)}")
            
            if potential_codes:
                # 使用提取的编码作为编码列
                code_column = [[code] for code in potential_codes]
                print(f"  [OK] 成功从名称列中提取 {len(potential_codes)} 个编码")
            else:
                print("  [WARN] 无法从名称列中提取编码")
        
        # 如果仍然没有编码列，尝试使用默认编码
        if not code_column and name_column:
            print("警告: 无法提取编码，使用默认编码...")
            name_texts = []
            for item in name_column:
                if isinstance(item, list) and len(item) > 0:
                    name_texts.append(str(item[0]))
                elif isinstance(item, str):
                    name_texts.append(item)
            
            # 为每个手术名称生成默认编码
            default_codes = [f"PROC{i+1:03d}" for i in range(len(name_texts))]
            code_column = [[code] for code in default_codes]
            print(f"  [OK] 使用默认编码: {default_codes}")
        
        if not name_column:
            print("错误: 未找到手术名称列")
            return {"手术及操作": [], "手术及操作编码": []}

        # 安全提取文本内容
        try:
            name_texts = []
            for item in name_column:
                if isinstance(item, list) and len(item) > 0:
                    name_texts.append(str(item[0]))  # 转换为字符串避免类型错误
                elif isinstance(item, str):
                    name_texts.append(item)
            
            code_texts = []
            for item in code_column:
                if isinstance(item, list) and len(item) > 0:
                    code_texts.append(str(item[0]))  # 转换为字符串避免类型错误
                elif isinstance(item, str):
                    code_texts.append(item)
                    
            print(f"手术名称列内容: {name_texts}")
            print(f"手术编码列内容: {code_texts}")
            
        except (IndexError, TypeError) as e:
            print(f"错误: 提取文本内容时发生异常: {e}")
            return {"手术及操作": [], "手术及操作编码": []}

        # 处理手术名称：跳过表头（含OCR轻微错误）

        # 处理手术名称：跳过表头
        # [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]OCR[OK][OK][OK][OK][OK]
        def is_proc_header(text):
            t = re.sub(r"\s+", "", str(text or ""))
            if not t:
                return True
            # [OK][OK][OK][OK]/[OK][OK] + [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]
            if re.search(r"(\u624b\u672f|\u64cd\u4f5c).{0,4}\u540d\u79f0", t):
                return True
            header_markers = [
                "\u672f\u8005",  # [OK][OK]
                "I\u52a9",       # I[OK]
                "II\u52a9",      # II[OK]
                "\u2161\u52a9",  # [OK][OK]
                "\u7b49\u7ea7",  # [OK][OK]
                "\u9ebb\u9189",  # [OK][OK]
                "\u533b\u5e08",  # [OK][OK]
                "\u5207\u53e3",  # [OK][OK]
            ]
            return any(m in t for m in header_markers)

        def clean_proc_name(text):
            t = str(text or "").strip()
            # [OK][OK][OK][OK][IMRT][OK][OK][OK]
            t = re.sub(r"^\s*\[[OK]IMRT\][OK]\s*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"^\d+\.\d+[0-9xX]*\s*", "", t)
            # [OK][OK][OK][OK][OK][OK] 2025[OK]05[OK]05[OK] [OK] 2025-05-05
            t = re.sub(r"^\d{4}(?:\u5e74|/|-|\.)\d{1,2}(?:(?:\u6708|/|-|\.)\d{1,2}\u65e5?)?\s*", "", t)
            # [OK][OK][OK][OK][OK]x003[OK][OK]
            t = re.sub(r"^[xX]\d{3,4}\s*", "", t)
            # [OK][OK][OK][OK][OK][OK]
            t = re.sub(r"(\s*)(\u4e00|\u4e8c|\u4e09|\u56db|\u4e94|\u516d|\u4e03|\u516b|\u4e5d|\u5341|I|II|III|IV)[OK]\s*\u7ea7\s*$", "", t)
            # 删除误拼接的表头/角色词
            t = re.sub(r"(手术及操作名称|术者|I助|II助|Ⅱ助|等级|麻醉方式|医师|师)", "", t)
            # 删除匿名姓名（如 林X海、赵X阳）和助手标记（如 I/甲）
            t = re.sub(r"[\u4e00-\u9fff][Xx×*＊某][\u4e00-\u9fff]", "", t)
            t = re.sub(r"(?:I{1,3}|Ⅱ|Ⅲ)\s*/\s*[甲乙丙]", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\s+", "", t)
            return t.strip()

        processed_names = []
        for name in name_texts:
            cleaned_name = clean_proc_name(name)
            if cleaned_name and not is_proc_header(cleaned_name):
                if re.search(r"[\u4e00-\u9fff]", cleaned_name):
                    processed_names.append(cleaned_name)

        # 拼接被切开的手术名称片段（如“内镜下结肠黏膜” + “切除术(EMR)”）
        stitched_names = []
        suffix_pattern = re.compile(
            r"^(切除术|止血术|缝合术|成形术|置入术|扩张术|引流术|修补术|切开术|探查术|造口术|固定术|活检术)"
        )
        for name in processed_names:
            if (
                stitched_names
                and suffix_pattern.match(name)
                and not re.search(r"术[\]\)）]?$", stitched_names[-1])
            ):
                stitched_names[-1] = stitched_names[-1] + name
            else:
                stitched_names.append(name)
        processed_names = stitched_names

        # 规则化支气管镜相关名称（处理OCR拼接/断裂）
        normalized_names = []
        for name in processed_names:
            n = str(name).strip()
            # 气管镜刷检术 + 支气管镜下诊断 被粘连到同一条
            if "气管镜刷检术支气管镜下诊断" in n:
                normalized_names.append("气管镜刷检术")
                normalized_names.append("支气管镜下诊断")
                continue
            # 纵隔淋巴结穿刺活检术常被截断
            if "经支气管超声内刺活检术" in n:
                n = "经支气管超声内镜纵隔淋巴结穿刺活检术"
            normalized_names.append(n)

        # 将“支气管镜下诊断”与下一条“性支气管肺泡灌洗”合并
        merged_names = []
        for n in normalized_names:
            # 12号样本：同一术式被拆成“十二指肠镜下胆” + “总管切开取石术(EST)”
            if merged_names and merged_names[-1].endswith("十二指肠镜下胆") and n.startswith("总管切开取石术"):
                merged_names[-1] = merged_names[-1] + n
                continue
            if merged_names and merged_names[-1] == "支气管镜下诊断" and n.startswith("性支气管肺泡灌洗"):
                merged_names[-1] = "支气管镜下诊断性支气管肺泡灌洗"
            else:
                merged_names.append(n)
        processed_names = merged_names

        # [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]
        def normalize_proc_code(c):
            return str(c or "").strip()

        def finalize_proc_code(code, proc_name):
            c = str(code or "").strip()
            if not c:
                return c
            return c

        processed_codes = []
        for code in code_texts:
            c = str(code).strip()
            if not c:
                continue

            # 跳过明显日期/时间碎片，避免把“操作日期”列误识别为手术编码
            if re.search(r"(?:19|20)\d{2}\s*年|\d{1,2}\s*月|\d{1,2}\s*日", c):
                continue

            # 拆分粘连编码：如 2.14030.9900x003 -> 2.1403 + 0.9900x003
            # 仅在“前码小数位>=4 且后面紧跟 d.”时切分，避免把 92.240 误切成 9 + 2.240
            c = re.sub(r"(\d+\.\d{4})(\d\.)", r"\1 \2", c)

            matches = re.findall(r"\d{4,5}[xX]\d{3,4}|\d*\.\d+[0-9xX]*|\d{4}|[xX]\d{3,4}", c)
            for m in matches:
                if re.match(r"^\d+\.\d{5,}(?![xX])", m):
                    # 进一步切分：2.14030 -> 2.1403 + 0（后续 0.*** 会在前一步切出）
                    m = re.sub(r"^(\d+\.\d{4})\d+$", r"\1", m)
                processed_codes.append(normalize_proc_code(m))
        
        # 如果编码列为空或无效，尝试从手术名称中提取编码
        if not processed_codes:
            print("警告: 编码列为空或无效，尝试从手术名称中提取编码...")
            for name in processed_names:
                # 查找括号中的编码
                bracket_match = re.search(r'[\[\【]([A-Za-z0-9\.]+)[\]\】]', name)
                if bracket_match:
                    processed_codes.append(bracket_match.group(1))
                    print(f"  [OK] 从名称中提取编码: {bracket_match.group(1)}")
                    continue
                
                # 查找数字.数字格式的编码
                dot_match = re.search(r'\b\d+\.\d+\b', name)
                if dot_match:
                    processed_codes.append(dot_match.group(0))
                    print(f"  [OK] 从名称中提取编码: {dot_match.group(0)}")
                    continue
                
                # 查找字母+数字格式的编码
                alpha_match = re.search(r'\b[A-Za-z]\d+\b', name)
                if alpha_match:
                    processed_codes.append(alpha_match.group(0))
                    print(f"  [OK] 从名称中提取编码: {alpha_match.group(0)}")
                    continue
                
                # 如果没有找到编码，使用默认编码
                default_code = f"PROC{len(processed_codes)+1:03d}"
                processed_codes.append(default_code)
                print(f"  [WARN] 使用默认编码: {default_code}")
        
        # 如果只有一个编码但名称候选很多，选取最可能的手术名称
        if len(processed_codes) == 1 and len(processed_names) > 1:
            def score_name(n):
                # 更长、包含更少数字的名称优先（数字通常来自噪声）
                digit_penalty = len(re.findall(r"\d", n)) * 3
                return len(n) - digit_penalty
            best_name = max(processed_names, key=score_name)
            print(f"  [OK] 仅1个编码，选取最佳手术名称候选: {best_name}")
            processed_names = [best_name]

        # 确保两个列表长度一致
        min_length = min(len(processed_names), len(processed_codes))
        
        if min_length == 0:
            print("警告: 未找到有效的手术名称或编码")
            return {"手术及操作": [], "手术及操作编码": []}

        # 提取手术信息
        for i in range(min_length):
            procedure_name = processed_names[i]
            procedure_code = finalize_proc_code(processed_codes[i], procedure_name)

            if procedure_name and procedure_code:
                procedure_names.append(procedure_name)
                procedure_codes.append(procedure_code)
                print(f"提取手术: {procedure_name} / {procedure_code}")

        return {
            "手术及操作": procedure_names,
            "手术及操作编码": procedure_codes
        }
        
    except Exception as e:
        print(f"错误: 提取手术信息时发生异常: {e}")
        return {"手术及操作": [], "手术及操作编码": []}


# 移除clean_procedure_name函数，因为它过度清理了手术名称
# 现在保留完整的手术名称，包括方括号内容


def process_json_file(json_file_path):
    """
    处理单个JSON文件（增强容错性版本）
    
    参数:
        json_file_path: JSON文件路径
        
    返回:
        包含提取字段的字典，失败时返回None
    """
    print(f"\n处理文件: {json_file_path}")
    
    try:
        # 安全读取文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except FileNotFoundError:
        print(f"错误: 文件不存在: {json_file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"错误: JSON格式错误: {e}")
        return None
    except Exception as e:
        print(f"错误: 读取文件失败: {e}")
        return None
    
    # 根据文件名和内容智能判断文件类型
    filename = os.path.basename(json_file_path)
    print(f"文件类型判断: {filename}")
    
    # 增强文件类型判断逻辑
    file_type = None
    
    # 检查文件名关键词
    if 'diag' in filename.lower():
        file_type = 'diagnosis'
        print(f"  [OK] 根据文件名识别为诊断文件")
    elif 'proc' in filename.lower():
        file_type = 'procedure'
        print(f"  [OK] 根据文件名识别为手术文件")
    elif 'cell_merged' in filename.lower():
        # 检查文件内容进一步判断
        columns = json_data.get('columns', [])
        if columns:
            # 检查第一列的内容
            first_column = columns[0] if len(columns) > 0 else []
            if first_column:
                first_item = first_column[0] if isinstance(first_column, list) else first_column
                first_text = str(first_item[0]) if isinstance(first_item, list) and len(first_item) > 0 else str(first_item)
                
                # 根据内容判断文件类型
                if '其他诊断' in first_text or '诊断' in first_text:
                    file_type = 'diagnosis'
                    print(f"  [OK] 根据内容识别为诊断文件 (首项: '{first_text}')")
                elif '手术' in first_text or '操作' in first_text or '治疗' in first_text:
                    file_type = 'procedure'
                    print(f"  [OK] 根据内容识别为手术文件 (首项: '{first_text}')")
                else:
                    # 检查是否有手术相关的关键词
                    for column in columns:
                        if isinstance(column, list):
                            for item in column:
                                if isinstance(item, list) and len(item) > 0:
                                    text = str(item[0])
                                    if '手术' in text or '操作' in text or '治疗' in text:
                                        file_type = 'procedure'
                                        print(f"  [OK] 根据内容识别为手术文件 (包含: '{text}')")
                                        break
                            if file_type:
                                break
    
    # 如果仍然无法确定文件类型，使用默认逻辑
    if not file_type:
        if 'Page2' in filename:
            file_type = 'procedure'
            print(f"  [WARN] 根据页面编号识别为手术文件 (Page2)")
        else:
            file_type = 'diagnosis'
            print(f"  [WARN] 使用默认识别为诊断文件")
    
    # 根据文件类型调用相应的提取函数
    try:
        if file_type == 'diagnosis':
            print("正在提取诊断信息...")
            extracted_fields = extract_other_diagnoses_from_json(json_data)
        elif file_type == 'procedure':
            print("正在提取手术信息...")
            extracted_fields = extract_operations_from_json(json_data)
        else:
            print(f"错误: 未知的文件类型: {file_type}")
            return None
            
        # 检查提取结果是否有效
        if not extracted_fields:
            print("警告: 提取结果为空")
            return None
            
        # 检查提取的字段是否包含有效数据
        has_valid_data = False
        for key, value in extracted_fields.items():
            if value and len(value) > 0:
                has_valid_data = True
                break
                
        if not has_valid_data:
            print("警告: 提取的字段不包含有效数据")
            return None
            
        print(f"[OK] 文件处理成功，提取到 {len(extracted_fields)} 个字段")
        
        return {
            'image_path': json_data.get('metadata', {}).get('image_path', ''),
            'extracted_fields': extracted_fields
        }
        
    except Exception as e:
        print(f"错误: 提取字段时发生异常: {e}")
        return None


class FieldExtractor:
    """主函数"""
    def __init__(self, input_dir):
        self.input_dir = input_dir
        
    def run(self):
        """
        执行字段抽取主流程（增强容错性版本）
        
        返回:
            输出文件路径
        """
        try:
            self.output_path = "DRG_model/output/step3/step3_diag_proc.json"
            
            # 确保输出目录存在
            output_dir = os.path.dirname(self.output_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                print(f"创建输出目录: {output_dir}")
            
            # 检查输入目录是否存在
            if not os.path.exists(self.input_dir):
                print(f"错误: 输入目录不存在: {self.input_dir}")
                return None
            
            # 安全查找所有JSON文件
            try:
                json_files = glob.glob(os.path.join(self.input_dir, '*.json'))
            except Exception as e:
                print(f"错误: 查找JSON文件时发生异常: {e}")
                return None
            
            if not json_files:
                print(f"警告: 在目录 {self.input_dir} 中未找到JSON文件")
                return None
            
            print(f"找到 {len(json_files)} 个JSON文件")
            
            # 处理所有JSON文件
            output_data = {}
            processed_count = 0
            error_count = 0
            
            for json_file in json_files:
                try:
                    filename = os.path.basename(json_file)
                    print(f"\n正在处理文件: {filename}")
                    
                    result = process_json_file(json_file)
                    if result:
                        output_data[filename] = result
                        processed_count += 1
                        print(f"[OK] 文件处理成功: {filename}")
                    else:
                        error_count += 1
                        print(f"[ERR] 文件处理失败: {filename}")
                        
                except Exception as e:
                    error_count += 1
                    print(f"错误: 处理文件 {json_file} 时发生异常: {e}")
                    continue
            
            # 保存结果
            try:
                # 添加调试信息，检查输出数据
                print(f"\n调试信息 - 输出数据内容:")
                for filename, data in output_data.items():
                    print(f"  {filename}:")
                    if 'extracted_fields' in data:
                        for field_name, field_value in data['extracted_fields'].items():
                            print(f"    {field_name}: {field_value}")
                    else:
                        print(f"    extracted_fields 字段不存在")
                
                with open(self.output_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                print(f"\n[OK] 字段抽取结果已保存到: {self.output_path}")    
                print(f"处理统计: 成功 {processed_count} 个文件，失败 {error_count} 个文件")
                
            except Exception as e:
                print(f"错误: 保存结果文件时发生异常: {e}")
                return None
            
            return self.output_path
            
        except Exception as e:
            print(f"错误: 执行主流程时发生异常: {e}")
            return None


def main():
    """主函数"""
    # 设置输入目录为step2.4的输出目录
    input_dir = "DRG_model/output/step2.4"
    
    extractor = FieldExtractor(input_dir)
    result = extractor.run()
    
    if result:
        print(f"字段抽取完成，结果保存在: {result}")
    else:
        print("字段抽取失败")

if __name__ == "__main__":
    input_dir = "output/step2.4"
    extractor = FieldExtractor(input_dir)
    out = extractor.run()
    print(out)
