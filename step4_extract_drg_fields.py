#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import re

CODE_PATTERN = re.compile(r"[A-Z]\d+(?:\.\d+)?(?:x\d+)?(?:\+[A-Z0-9.]+)?")
DIAG_CODE_PATTERN = re.compile(
    r"[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?(?:\+[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?)?"
)


def _unique_keep_order(items):
    seen = set()
    out = []
    for item in items:
        if item is None:
            continue
        s = str(item).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _clean_dates(text):
    if not text:
        return ""
    t = str(text)
    # full dates first
    t = re.sub(r"(?:19|20)\d{2}\s*(?:-|/|\.|\u5e74)\s*\d{1,2}\s*(?:-|/|\.|\u6708)\s*\d{1,2}\s*\u65e5?", " ", t)
    t = re.sub(r"(?:19|20)\d{2}\s*\u5e74\s*\d{1,2}\s*\u6708", " ", t)
    # remove any remaining number + 年/月/日 fragments
    t = re.sub(r"\d{1,4}\s*\u5e74", " ", t)
    t = re.sub(r"\d{1,2}\s*\u6708", " ", t)
    t = re.sub(r"\d{1,2}\s*\u65e5", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _clean_diag_text(text):
    if not text:
        return ""
    t = _clean_dates(text)
    t = t.replace("\u51fa\u9662\u8bca\u65ad", " ")
    t = re.sub(r"[\(\)\[\]\u3010\u3011:：;,，。]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _clean_main_diag_text(text):
    if not text:
        return ""
    t = _clean_dates(text)
    t = t.replace("\u51fa\u9662\u8bca\u65ad", " ")
    # 主诊断文本保留中文逗号
    t = re.sub(r"[\(\)\[\]\u3010\u3011:：;。]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _clean_pathology_text(text):
    if not text:
        return ""
    t = str(text).replace("\u75c5\u7406\u53f7", " ")
    t = re.sub(r"[\(\)\[\]\u3010\u3011:：;,，。]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _clean_other_diag_name(text):
    if not text:
        return ""
    t = str(text).strip()
    # 若出现“诊断：”，仅保留其后的内容
    t = re.sub(r"^.*?诊断[：:]\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _find_key_by_patterns(data, patterns):
    for key in data.keys():
        for p in patterns:
            if re.search(p, key):
                return key
    return None


def _normalize_diag_code(code_text):
    if not code_text:
        return ""
    code = str(code_text).upper()

    # 复合诊断码：保留“+”两侧编码（如 B02.305+H22.0）
    if "+" in code:
        parts = [p.strip() for p in code.split("+") if p.strip()]
        norm_parts = []
        for p in parts:
            n = _normalize_diag_code(p)
            if n:
                norm_parts.append(n)
        return "+".join(norm_parts) if norm_parts else ""

    if "." not in code:
        m = re.search(r"[A-Z]\d{2}", code)
        return m.group(0) if m else ""

    # 兼容如 H40.000x004 这种合法后缀，不再误截断 x004
    m = re.search(r"([A-Z]\d{2})\.([A-Z0-9]{1,8}?)(X\d{1,4})?$", code)
    if not m:
        m = re.search(r"([A-Z]\d{2})\.([A-Z0-9]{1,8})(X\d{1,4})?", code)
    if not m:
        m2 = re.search(r"[A-Z]\d{2}", code)
        return m2.group(0) if m2 else ""

    head = m.group(1)
    tail = m.group(2) or ""
    suffix = m.group(3) or ""

    if suffix:
        suffix_digits = re.sub(r"\D", "", suffix)
        return f"{head}.{tail}x{suffix_digits}"

    if tail.isdigit():
        tail = tail[:3]
    elif re.fullmatch(r"[A-Z]\d{1,3}", tail):
        pass
    else:
        leading_digits = re.match(r"\d{1,3}", tail)
        if leading_digits:
            tail = leading_digits.group(0)
        else:
            tail = tail[:4]
    return f"{head}.{tail}"


def _extract_diag_codes(text):
    if not text:
        return []
    s = str(text).upper()
    # 粘连码拆分：在后续编码起点前插入空格
    # 注意：复合码中的 '+' 不能拆（如 B02.305+H22.0）
    s = re.sub(r"(?<!^)(?<!\+)(?=[A-Z]\d{2}\.)", " ", s)
    raw = DIAG_CODE_PATTERN.findall(s)
    out = []
    for r in raw:
        n = _normalize_diag_code(r)
        if n:
            out.append(n)
    return _unique_keep_order(out)


def _extract_main_diag_codes(text):
    # 常规提取（字母开头编码）
    out = _extract_diag_codes(text)
    if out:
        return out
    # 主诊码兜底：允许 OCR 把首字母 O 识别为 0（如 062.100）
    s = str(text).upper()
    raw = re.findall(
        r"0\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?(?:\+[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?)?",
        s
    )
    return _unique_keep_order(raw)


def _extract_pathology_codes(text):
    if not text:
        return []
    s = str(text).strip()
    # 优先匹配特殊病理编码，再匹配常规诊断编码
    raw = re.findall(
        r"M\d{5}/\d|[A-Z]\d{2}\.[xX]\d{2,4}|[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:[xX]\d{1,4})?)?",
        s.upper()
    )
    out = []
    for c in raw:
        c = str(c).strip()
        if not c:
            continue
        if re.fullmatch(r"[A-Z]\d{2}\.[xX]\d{2,4}", c):
            # 规范为小写 x（如 J60.x00）
            c = c[:4] + "x" + c[5:]
        out.append(c)
    return _unique_keep_order(out)


def _postprocess_results(results, finalize_main_diag=True):
    other_name_key = _find_key_by_patterns(results, [r"\u5176\u4ed6\u8bca\u65ad\u540d\u79f0"])
    if other_name_key and isinstance(results.get(other_name_key), list):
        results[other_name_key] = [x for x in (_clean_other_diag_name(v) for v in results[other_name_key]) if x]

    path_key = _find_key_by_patterns(results, [r"\u75c5\u7406\u8bca\u65ad"])
    if path_key and isinstance(results.get(path_key), list):
        results[path_key] = [x for x in (_clean_pathology_text(v) for v in results[path_key]) if x]
    path_code_key = _find_key_by_patterns(results, [r"\u75c5\u7406\u8bca\u65ad\u7f16\u7801"])
    if path_code_key and isinstance(results.get(path_code_key), list):
        path_codes = []
        for c in results.get(path_code_key, []):
            path_codes.extend(_extract_pathology_codes(c))
        results[path_code_key] = _unique_keep_order(path_codes[:1])

    out_diag_key = _find_key_by_patterns(results, [r"\u95e8.*\u8bca\u8bca\u65ad"])
    if out_diag_key and isinstance(results.get(out_diag_key), list):
        results[out_diag_key] = [x for x in (_clean_diag_text(v) for v in results[out_diag_key]) if x]
        out_code_key = _find_key_by_patterns(results, [r"\u95e8.*\u8bca\u8bca\u65ad\u7f16\u7801"])
        if out_code_key and isinstance(results.get(out_code_key), list):
            diag_items = _split_outpatient_diagnoses(results[out_diag_key])
            diag_count = len(diag_items) if diag_items else 0
            code_items = _split_outpatient_codes(results[out_code_key])
            selected_codes = list(code_items)

            if diag_count <= 1:
                # 高优先级规则1：诊断<=1个时，仅保留首个“字母开头”编码
                letter_codes = [c for c in code_items if re.match(r"^[A-Z]", c)]
                selected_codes = letter_codes[:1]
                # 次级规则：若没有字母开头编码，再做 0->O 兜底
                if not selected_codes:
                    converted = [_normalize_outpatient_code_leading_zero(c) for c in code_items]
                    letter_codes = [c for c in converted if re.match(r"^[A-Z]", c)]
                    selected_codes = letter_codes[:1]
            elif diag_count == 2 and len(code_items) > 2:
                # 诊断2个时，编码从第3个开始丢弃
                selected_codes = code_items[:2]
            elif diag_count > 0 and len(code_items) > diag_count:
                selected_codes = code_items[:diag_count]

            # 次级规则：在完成高优先级截断后，再做门急诊编码首位 0->O
            selected_codes = [_normalize_outpatient_code_leading_zero(c) for c in selected_codes]
            selected_codes = [_normalize_code_x_case(c) for c in selected_codes]

            results[out_code_key] = ["、".join(selected_codes)] if selected_codes else []

    main_code_key = _find_key_by_patterns(results, [r"\u4e3b\u8981\u8bca\u65ad\u7f16\u7801"])
    other_code_key = _find_key_by_patterns(results, [r"\u5176\u4ed6\u8bca\u65ad\u7f16\u7801"])
    if main_code_key and isinstance(results.get(main_code_key), list):
        main_codes = []
        for c in results.get(main_code_key, []):
            extracted = _extract_diag_codes(c)
            # 主诊码兜底：OCR把首字母 O 识别为 0 时（如 062.100），先识别再在末端保留 0->O 规则
            if not extracted:
                raw = str(c).upper()
                fallback = re.findall(
                    r"0\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?(?:\+[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?)?",
                    raw
                )
                extracted.extend(fallback)
            main_codes.extend(extracted)
        main_codes = _unique_keep_order(main_codes)

        other_codes = set()
        if other_code_key and isinstance(results.get(other_code_key), list):
            for c in results.get(other_code_key, []):
                for norm in _extract_diag_codes(c):
                    other_codes.add(_normalize_diag_code_leading_zero_for_compare(norm))
                # 兼容其他诊断编码为数字开头（如 072.101）的情况
                raw = str(c).upper()
                fallback = re.findall(
                    r"0\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?(?:\+[A-Z]\d{2}(?:\.[A-Z0-9]{1,8}(?:X\d{1,4})?)?)?",
                    raw
                )
                for fb in fallback:
                    other_codes.add(_normalize_diag_code_leading_zero_for_compare(fb))

        if len(main_codes) > 1 and other_codes:
            filtered = [
                c for c in main_codes
                if _normalize_diag_code_leading_zero_for_compare(c) not in other_codes
            ]
            if len(filtered) == 1:
                main_codes = filtered
            elif len(filtered) > 1:
                # 仍有多个候选时，保持原顺序，后续统一取首个
                main_codes = filtered

        # extract_info_from_ocr 阶段先不强行截断主诊码，
        # 让 run() 合并 step3 后再做最终裁决，避免把首个候选误锁定。
        final_main_codes = main_codes[:1] if finalize_main_diag else main_codes
        if final_main_codes and final_main_codes[0] and final_main_codes[0][0] == "0":
            final_main_codes[0] = "O" + final_main_codes[0][1:]
        final_main_codes = [_normalize_code_x_case(c) for c in final_main_codes]
        results[main_code_key] = final_main_codes

    return results


def fuzzy_match(text, pattern, max_errors=2):
    """
    模糊匹配函数，允许一定数量的字符错误
    
    参数:
        text: 待匹配的文本
        pattern: 匹配模式
        max_errors: 允许的最大错误字符数
        
    返回:
        bool: 是否匹配成功
    """
    # 简单的模糊匹配实现：检查模式中的字符是否按顺序出现在文本中
    pattern_chars = list(pattern)
    text_chars = list(text)
    
    i = 0  # 文本索引
    j = 0  # 模式索引
    errors = 0
    
    while i < len(text_chars) and j < len(pattern_chars):
        if text_chars[i] == pattern_chars[j]:
            j += 1
        else:
            errors += 1
            if errors > max_errors:
                return False
        i += 1
    
    # 检查是否匹配了足够的模式字符
    matched_ratio = j / len(pattern_chars)
    return matched_ratio >= 0.7  # 至少匹配70%的模式字符


def _extract_outpatient_codes(text):
    """
    门（急）诊编码抽取（兼容 OCR 丢字母前缀）：
    例如 "002.001、Q51.201" -> "002.001、Q51.201"
    """
    if not text:
        return ""
    s = str(text).upper()
    s = re.sub(r"[，,;；/]+", "、", s)
    tokens = re.findall(r"[A-Z]?\d{2,3}(?:\.\d+)?(?:X\d+)?", s)
    uniq = []
    seen = set()
    for t in tokens:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return "、".join(uniq)


def _split_outpatient_diagnoses(diag_values):
    items = []
    for v in diag_values:
        s = str(v).strip()
        if not s:
            continue
        s = re.sub(r"[，,;；/]+", "、", s)
        parts = [p.strip() for p in s.split("、") if p.strip()]
        if len(parts) == 1:
            # 兼容清洗后由顿号变空格的场景，如“头晕 步态不稳”
            sp = [p.strip() for p in re.split(r"\s+", parts[0]) if p.strip()]
            if len(sp) > 1:
                parts = sp
        items.extend(parts)
    return _unique_keep_order(items)


def _split_outpatient_codes(code_values):
    items = []
    for v in code_values:
        s = str(v).upper().strip()
        if not s:
            continue
        s = re.sub(r"[，,;；/]+", "、", s)
        parts = [p.strip() for p in s.split("、") if p.strip()]
        for p in parts:
            items.append(p)
    return _unique_keep_order(items)


def _normalize_outpatient_code_leading_zero(code):
    if not code:
        return code
    return ("O" + code[1:]) if code[0] == "0" else code


def _normalize_diag_code_leading_zero_for_compare(code):
    if not code:
        return code
    s = str(code).strip()
    return ("O" + s[1:]) if s and s[0] == "0" else s


def _normalize_code_x_case(code):
    if not code:
        return code
    return re.sub(r"X(?=\d)", "x", str(code))


def extract_diagnosis_with_disease_code(line_text, line_items):
    """
    提取门（急）诊诊断结果和编码，支持多种格式变体
    
    参数:
        line_text: 整行文本内容
        line_items: 行的各个字段列表
        
    返回:
        tuple: (诊断结果, 疾病编码)
    """
    diagnosis_result = ""
    diagnosis_code = ""
    
    print(f"DEBUG: 开始处理门（急）诊诊断行: {line_text}")
    print(f"DEBUG: 行字段: {[str(item[0]) if isinstance(item, list) else str(item) for item in line_items]}")
    
    # 扩展关键词匹配，处理OCR识别错误（如"门"识别为"了"）
    diagnosis_keywords = ["诊诊断", "（急）诊诊断", "(急)诊诊断", "了（急）诊诊断", "了(急)诊诊断"]
    has_diagnosis_keyword = any(keyword in line_text for keyword in diagnosis_keywords)
    
    # 情况1："诊诊断"和"疾病编码"在同一字段内
    if has_diagnosis_keyword and "疾病编码" in line_text:
        print("DEBUG: 情况1 - 诊诊断和疾病编码在同一字段内")
        
        # 查找诊断关键词和"疾病编码"的位置
        diagnosis_start = -1
        actual_keyword = ""
        for keyword in diagnosis_keywords:
            pos = line_text.find(keyword)
            if pos != -1:
                diagnosis_start = pos
                actual_keyword = keyword
                break
        
        disease_code_start = line_text.find("疾病编码")
        
        if diagnosis_start < disease_code_start:
            # 提取诊断关键词和"疾病编码"之间的内容作为诊断结果
            diagnosis_text_start = diagnosis_start + len(actual_keyword)
            diagnosis_text = line_text[diagnosis_text_start:disease_code_start].strip()
            
            # 清理诊断文本：去除多余标点符号
            diagnosis_text = re.sub(r'[、，。；：！？]', ' ', diagnosis_text).strip()
            diagnosis_result = re.sub(r'\s+', ' ', diagnosis_text)
            
            # 提取"疾病编码"之后的编码内容
            code_start = disease_code_start + len("疾病编码")
            code_text = line_text[code_start:].strip()
            
            diagnosis_code = _extract_outpatient_codes(code_text)
            if diagnosis_code:
                print(f"DEBUG: 情况1 - 提取诊断结果: {diagnosis_result}, 编码: {diagnosis_code}")
            else:
                print("DEBUG: 情况1 - 未找到符合格式的编码")
    
    # 情况2："诊诊断"和"疾病编码"不在同一字段内
    elif has_diagnosis_keyword:
        print("DEBUG: 情况2 - 诊诊断和疾病编码不在同一字段内")
        
        # 查找"诊诊断"字段的位置
        diagnosis_field_idx = -1
        for idx, item in enumerate(line_items):
            item_text = str(item[0]) if isinstance(item, list) else str(item)
            if any(keyword in item_text for keyword in diagnosis_keywords):
                diagnosis_field_idx = idx
                break
        
        if diagnosis_field_idx != -1:
            # 子情况①："诊诊断"字段后无其他内容
            diagnosis_field_text = str(line_items[diagnosis_field_idx][0]) if isinstance(line_items[diagnosis_field_idx], list) else str(line_items[diagnosis_field_idx])
            
            if len(diagnosis_field_text.strip()) <= len("诊诊断"):
                print("DEBUG: 情况2-① - 诊诊断字段后无其他内容")
                
                # 将"诊诊断"字段的下一个字段内容作为诊断结果
                if diagnosis_field_idx + 1 < len(line_items):
                    next_item = line_items[diagnosis_field_idx + 1]
                    next_item_text = str(next_item[0]) if isinstance(next_item, list) else str(next_item)
                    
                    # 检查是否为非编码格式的诊断名称
                    if not re.match(r'^[A-Z]\d+', next_item_text) and len(next_item_text) > 1:
                        diagnosis_result = next_item_text.strip()
                        
                        # 查找"疾病编码"字段
                        disease_code_field_idx = -1
                        for idx in range(diagnosis_field_idx + 1, len(line_items)):
                            item_text = str(line_items[idx][0]) if isinstance(line_items[idx], list) else str(line_items[idx])
                            if "疾病编码" in item_text:
                                disease_code_field_idx = idx
                                break
                        
                        if disease_code_field_idx != -1:
                            # 提取"疾病编码"字段中的非汉字部分
                            disease_code_text = str(line_items[disease_code_field_idx][0]) if isinstance(line_items[disease_code_field_idx], list) else str(line_items[disease_code_field_idx])
                            diagnosis_code = _extract_outpatient_codes(disease_code_text)
                            if not diagnosis_code:
                                # 如果"疾病编码"字段后还有内容，尝试提取下一个字段
                                if disease_code_field_idx + 1 < len(line_items):
                                    code_item = line_items[disease_code_field_idx + 1]
                                    code_text = str(code_item[0]) if isinstance(code_item, list) else str(code_item)
                                    diagnosis_code = _extract_outpatient_codes(code_text)
            
            # 子情况②："诊诊断"字段后还有其他内容
            else:
                print("DEBUG: 情况2-② - 诊诊断字段后还有其他内容")
                
                # 将"诊诊断"字段后紧接的内容作为诊断结果
                diagnosis_field_text = str(line_items[diagnosis_field_idx][0]) if isinstance(line_items[diagnosis_field_idx], list) else str(line_items[diagnosis_field_idx])
                
                # 提取诊断关键词之后的内容
                actual_keyword = ""
                for keyword in diagnosis_keywords:
                    if keyword in diagnosis_field_text:
                        actual_keyword = keyword
                        break
                
                diagnosis_start = diagnosis_field_text.find(actual_keyword) + len(actual_keyword)
                diagnosis_text = diagnosis_field_text[diagnosis_start:].strip()
                
                if diagnosis_text:
                    diagnosis_result = diagnosis_text
                    
                    # 查找"疾病编码"字段
                    disease_code_field_idx = -1
                    for idx in range(diagnosis_field_idx + 1, len(line_items)):
                        item_text = str(line_items[idx][0]) if isinstance(line_items[idx], list) else str(line_items[idx])
                        if "疾病编码" in item_text:
                            disease_code_field_idx = idx
                            break
                    
                    if disease_code_field_idx != -1:
                        disease_code_text = str(line_items[disease_code_field_idx][0]) if isinstance(line_items[disease_code_field_idx], list) else str(line_items[disease_code_field_idx])
                        
                        # 检查"疾病编码"后是否还有内容
                        code_start = disease_code_text.find("疾病编码") + len("疾病编码")
                        code_after_disease = disease_code_text[code_start:].strip()
                        
                        if code_after_disease:
                            # "疾病编码"后还有内容，提取后续的字母+数字组合
                            diagnosis_code = _extract_outpatient_codes(code_after_disease)
                        else:
                            # "疾病编码"后无内容，将下一个字段内容作为编码
                            if disease_code_field_idx + 1 < len(line_items):
                                code_item = line_items[disease_code_field_idx + 1]
                                code_text = str(code_item[0]) if isinstance(code_item, list) else str(code_item)
                                diagnosis_code = _extract_outpatient_codes(code_text)
    
    # 异常处理：如果仍未找到诊断结果或编码，使用备用方法
    if not diagnosis_result:
        print("DEBUG: 使用备用方法提取诊断结果")
        # 尝试从字段中提取非编码格式的文本作为诊断结果
        for item in line_items:
            item_text = str(item[0]) if isinstance(item, list) else str(item)
            
            # 跳过包含"疾病编码"或编码格式的字段
            if "疾病编码" not in item_text and not re.match(r'^[A-Z]\d+', item_text):
                if item_text and len(item_text) > 1 and item_text.strip() not in ["诊诊断", "门（急）诊诊断"]:
                    diagnosis_result = item_text.strip()
                    break
    
    if not diagnosis_code:
        print("DEBUG: 使用备用方法提取编码")
        # 在整个行文本中查找编码模式
        diagnosis_code = _extract_outpatient_codes(line_text)
    
    print(f"DEBUG: 最终提取结果 - 诊断: {diagnosis_result}, 编码: {diagnosis_code}")
    return diagnosis_result, diagnosis_code


def extract_diagnosis_with_disease_code_generic(line_text, line_items, diagnosis_type):
    """
    通用的诊断提取函数，支持多种诊断类型
    
    参数:
        line_text: 整行文本内容
        line_items: 行的各个字段列表
        diagnosis_type: 诊断类型（如"病理诊断"、"门（急）诊诊断"等）
        
    返回:
        tuple: (诊断结果, 疾病编码)
    """
    diagnosis_result = ""
    diagnosis_code = ""
    
    print(f"DEBUG: 开始处理{diagnosis_type}行: {line_text}")
    print(f"DEBUG: 行字段: {[str(item[0]) if isinstance(item, list) else str(item) for item in line_items]}")
    
    # 根据诊断类型构建关键词
    if diagnosis_type == "病理诊断":
        diagnosis_keywords = ["病理诊断", "病理诊断：", "病理诊断:"]
    elif diagnosis_type == "门（急）诊诊断":
        diagnosis_keywords = ["诊诊断", "（急）诊诊断", "(急)诊诊断", "了（急）诊诊断", "了(急)诊诊断"]
    else:
        diagnosis_keywords = [diagnosis_type]
    
    has_diagnosis_keyword = any(keyword in line_text for keyword in diagnosis_keywords)
    
    # 情况1：诊断关键词和"疾病编码"在同一字段内
    if has_diagnosis_keyword and "疾病编码" in line_text:
        print(f"DEBUG: 情况1 - {diagnosis_type}和疾病编码在同一字段内")
        
        # 查找诊断关键词和"疾病编码"的位置
        diagnosis_start = -1
        actual_keyword = ""
        for keyword in diagnosis_keywords:
            pos = line_text.find(keyword)
            if pos != -1:
                diagnosis_start = pos
                actual_keyword = keyword
                break
        
        disease_code_start = line_text.find("疾病编码")
        
        if diagnosis_start < disease_code_start:
            # 提取诊断关键词和"疾病编码"之间的内容作为诊断结果
            diagnosis_text_start = diagnosis_start + len(actual_keyword)
            diagnosis_text = line_text[diagnosis_text_start:disease_code_start].strip()
            
            # 清理诊断文本：去除多余标点符号
            diagnosis_text = re.sub(r'[、，。；：！？]', ' ', diagnosis_text).strip()
            diagnosis_result = re.sub(r'\s+', ' ', diagnosis_text)
            
            # 提取"疾病编码"之后的编码内容
            code_start = disease_code_start + len("疾病编码")
            code_text = line_text[code_start:].strip()
            
            # 查找编码
            if diagnosis_type == "病理诊断":
                codes = _extract_pathology_codes(code_text)
                diagnosis_code = codes[0] if codes else ""
            else:
                code_pattern = r'[A-Z]\d+(?:\.\d+)?(?:x\d+)?(?:、[A-Z]\d+(?:\.\d+)?(?:x\d+)?)*'
                code_match = re.search(code_pattern, code_text)
                diagnosis_code = code_match.group(0) if code_match else ""

            if diagnosis_code:
                print(f"DEBUG: 情况1 - 提取诊断结果: {diagnosis_result}, 编码: {diagnosis_code}")
            else:
                print("DEBUG: 情况1 - 未找到符合格式的编码")
    
    # 情况2：诊断关键词和"疾病编码"不在同一字段内
    elif has_diagnosis_keyword:
        print(f"DEBUG: 情况2 - {diagnosis_type}和疾病编码不在同一字段内")
        
        # 查找诊断关键词字段的位置
        diagnosis_field_idx = -1
        for idx, item in enumerate(line_items):
            item_text = str(item[0]) if isinstance(item, list) else str(item)
            if any(keyword in item_text for keyword in diagnosis_keywords):
                diagnosis_field_idx = idx
                break
        
        if diagnosis_field_idx != -1:
            # 子情况①：诊断关键词字段后无其他内容
            diagnosis_field_text = str(line_items[diagnosis_field_idx][0]) if isinstance(line_items[diagnosis_field_idx], list) else str(line_items[diagnosis_field_idx])
            
            if len(diagnosis_field_text.strip()) <= len(diagnosis_type):
                print("DEBUG: 情况2-① - 诊断关键词字段后无其他内容")
                
                # 将诊断关键词字段的下一个字段内容作为诊断结果
                if diagnosis_field_idx + 1 < len(line_items):
                    next_item = line_items[diagnosis_field_idx + 1]
                    next_item_text = str(next_item[0]) if isinstance(next_item, list) else str(next_item)
                    
                    # 检查是否为非编码格式的诊断名称
                    if not re.match(r'^[A-Z]\d+', next_item_text) and len(next_item_text) > 1:
                        diagnosis_result = next_item_text.strip()
                        
                        # 查找"疾病编码"字段
                        disease_code_field_idx = -1
                        for idx in range(diagnosis_field_idx + 1, len(line_items)):
                            item_text = str(line_items[idx][0]) if isinstance(line_items[idx], list) else str(line_items[idx])
                            if "疾病编码" in item_text:
                                disease_code_field_idx = idx
                                break
                        
                        if disease_code_field_idx != -1:
                            # 提取"疾病编码"字段中的非汉字部分
                            disease_code_text = str(line_items[disease_code_field_idx][0]) if isinstance(line_items[disease_code_field_idx], list) else str(line_items[disease_code_field_idx])
                            if diagnosis_type == "病理诊断":
                                codes = _extract_pathology_codes(disease_code_text)
                                diagnosis_code = codes[0] if codes else ""
                            else:
                                code_match = re.search(r'[A-Z]\d+(?:\.\d+)?(?:x\d+)?', disease_code_text)
                                if code_match:
                                    diagnosis_code = code_match.group(0)
                            # 如果"疾病编码"字段后还有内容，尝试提取下一个字段
                            if not diagnosis_code and disease_code_field_idx + 1 < len(line_items):
                                code_item = line_items[disease_code_field_idx + 1]
                                code_text = str(code_item[0]) if isinstance(code_item, list) else str(code_item)
                                if diagnosis_type == "病理诊断":
                                    codes = _extract_pathology_codes(code_text)
                                    diagnosis_code = codes[0] if codes else ""
                                else:
                                    code_match = re.search(r'[A-Z]\d+(?:\.\d+)?(?:x\d+)?', code_text)
                                    if code_match:
                                        diagnosis_code = code_match.group(0)
            
            # 子情况②：诊断关键词字段后还有其他内容
            else:
                print("DEBUG: 情况2-② - 诊断关键词字段后还有其他内容")
                
                # 将诊断关键词字段后紧接的内容作为诊断结果
                diagnosis_field_text = str(line_items[diagnosis_field_idx][0]) if isinstance(line_items[diagnosis_field_idx], list) else str(line_items[diagnosis_field_idx])
                
                # 提取诊断关键词之后的内容
                actual_keyword = ""
                for keyword in diagnosis_keywords:
                    if keyword in diagnosis_field_text:
                        actual_keyword = keyword
                        break
                
                diagnosis_start = diagnosis_field_text.find(actual_keyword) + len(actual_keyword)
                diagnosis_text = diagnosis_field_text[diagnosis_start:].strip()
                
                if diagnosis_text:
                    diagnosis_result = diagnosis_text
                    
                    # 查找"疾病编码"字段
                    disease_code_field_idx = -1
                    for idx in range(diagnosis_field_idx + 1, len(line_items)):
                        item_text = str(line_items[idx][0]) if isinstance(line_items[idx], list) else str(line_items[idx])
                        if "疾病编码" in item_text:
                            disease_code_field_idx = idx
                            break
                    
                    if disease_code_field_idx != -1:
                        disease_code_text = str(line_items[disease_code_field_idx][0]) if isinstance(line_items[disease_code_field_idx], list) else str(line_items[disease_code_field_idx])
                        
                        # 检查"疾病编码"后是否还有内容
                        code_start = disease_code_text.find("疾病编码") + len("疾病编码")
                        code_after_disease = disease_code_text[code_start:].strip()
                        
                        if code_after_disease:
                            # "疾病编码"后还有内容，提取后续的字母+数字组合
                            if diagnosis_type == "病理诊断":
                                codes = _extract_pathology_codes(code_after_disease)
                                diagnosis_code = codes[0] if codes else ""
                            else:
                                code_match = re.search(r'[A-Z]\d+(?:\.\d+)?(?:x\d+)?', code_after_disease)
                                if code_match:
                                    diagnosis_code = code_match.group(0)
                        else:
                            # "疾病编码"后无内容，将下一个字段内容作为编码
                            if disease_code_field_idx + 1 < len(line_items):
                                code_item = line_items[disease_code_field_idx + 1]
                                code_text = str(code_item[0]) if isinstance(code_item, list) else str(code_item)
                                if diagnosis_type == "病理诊断":
                                    codes = _extract_pathology_codes(code_text)
                                    diagnosis_code = codes[0] if codes else ""
                                else:
                                    code_match = re.search(r'[A-Z]\d+(?:\.\d+)?(?:x\d+)?', code_text)
                                    if code_match:
                                        diagnosis_code = code_match.group(0)
    
    # 异常处理：如果仍未找到诊断结果或编码，使用备用方法（严格限定在同一行内）
    if not diagnosis_result:
        print("DEBUG: 使用备用方法提取诊断结果（同一行内）")
        # 尝试从同一行的字段中提取非编码格式的文本作为诊断结果
        for item in line_items:
            item_text = str(item[0]) if isinstance(item, list) else str(item)
            
            # 跳过包含"疾病编码"或编码格式的字段
            if "疾病编码" not in item_text and not re.match(r'^[A-Z]\d+', item_text):
                # 更严格的过滤条件：排除无关字符和字段
                if (item_text and len(item_text) > 1 and 
                    item_text.strip() not in diagnosis_keywords and
                    not re.match(r'^[：:、，。；！？]', item_text) and  # 排除以标点开头的字段
                    not re.match(r'^[费药检]', item_text) and  # 排除以无关字符开头的字段
                    len(item_text.strip()) > 2):  # 要求字段长度至少3个字符
                    
                    # 进一步检查：排除包含无关关键词的字段
                    irrelevant_keywords = ["费", "药", "检查", "化验", "检验", "治疗", "手术"]
                    if not any(keyword in item_text for keyword in irrelevant_keywords):
                        diagnosis_result = item_text.strip()
                        print(f"DEBUG: 备用方法提取到诊断结果: {diagnosis_result}")
                        break
    
    if not diagnosis_code:
        print("DEBUG: 使用备用方法提取编码")
        # 在整个行文本中查找编码模式
        if diagnosis_type == "病理诊断":
            all_codes = _extract_pathology_codes(line_text)
            if all_codes:
                diagnosis_code = all_codes[-1]  # 取最后一个编码
        else:
            code_pattern = r'[A-Z]\d+(?:\.\d+)?(?:x\d+)?'
            all_codes = re.findall(code_pattern, line_text)
            if all_codes:
                diagnosis_code = all_codes[-1]  # 取最后一个编码
    
    print(f"DEBUG: 最终提取结果 - {diagnosis_type}: {diagnosis_result}, 编码: {diagnosis_code}")
    return diagnosis_result, diagnosis_code


def extract_info_from_ocr(ocr_data):
    results = {
        "年龄": [],
        "年龄不足一周岁的年龄": [],
        "新生儿出生体重": [],
        "新生儿入院体重": [],
        "实际住院天数": [],
        "门（急）诊诊断": [],
        "门（急）诊诊断编码": [],
        "主要诊断": [],
        "主要诊断编码": [],
        "其他诊断名称": [],
        "其他诊断编码": [],
        "手术及操作名称": [],
        "手术及操作编码": [],
        "病理诊断": [],
        "病理诊断编码": [],
        "住院费用（元）：总费用": []
    }

    for image_key, image_data in ocr_data.items():
        lines = image_data.get("lines", [])

        for line in lines:
            # 提取每行的文本内容（每个item是[text, coordinate]格式）
            line_texts = []
            for item in line:
                if isinstance(item, list) and len(item) > 0:
                    # 提取文本部分
                    line_texts.append(str(item[0]))
                else:
                    line_texts.append(str(item))
            
            line_text = "".join(line_texts)
            
            # 调试：显示所有行的内容
            if "(急)诊诊断" in line_text or "门（急）诊诊断" in line_text:
                print(f"DEBUG: 找到包含门（急）诊诊断的行: {line_text}")
                print(f"DEBUG: 行内容: {line}")

            diagnosis_keywords = ["诊诊断", "（急）诊诊断", "(急)诊诊断", "了（急）诊诊断", "了(急)诊诊断"]
            has_diagnosis_keyword = any(keyword in line_text for keyword in diagnosis_keywords)
            
            if has_diagnosis_keyword:
                print(f"找到门（急）诊诊断行: {line_text}")
                
                # 新增：检查是否包含"疾病编码"关键词
                if "疾病编码" in line_text:
                    print("检测到包含'疾病编码'关键词的门（急）诊诊断字段")
                    
                    # 提取门（急）诊诊断结果和编码
                    diagnosis_result, diagnosis_code = extract_diagnosis_with_disease_code(line_text, line)
                    
                    if diagnosis_result:
                        print(f"提取门（急）诊诊断结果: {diagnosis_result}")
                        results["门（急）诊诊断"].append(diagnosis_result)
                    
                    if diagnosis_code:
                        print(f"提取门（急）诊诊断编码: {diagnosis_code}")
                        results["门（急）诊诊断编码"].append(diagnosis_code)
                else:
                    # 原有的门（急）诊诊断提取逻辑
                    for idx, item in enumerate(line):
                        # 处理嵌套的[text, coordinate]结构
                        if isinstance(item, list) and len(item) > 0:
                            item_text = str(item[0])
                        else:
                            item_text = str(item)
                            
                        print(f"检查字段 {idx}: '{item_text}'")
                        
                        # 如果找到门（急）诊诊断标签，提取同一行的下一个字段作为诊断名称
                        diagnosis_keywords = ["诊诊断", "（急）诊诊断", "(急)诊诊断", "了（急）诊诊断", "了(急)诊诊断"]
                        has_diagnosis_keyword = any(keyword in item_text for keyword in diagnosis_keywords)
                        
                        if has_diagnosis_keyword:
                            print(f"找到门（急）诊诊断标签: '{item_text}'")
                            # 提取同一行中的诊断名称（下一个字段）
                            if idx + 1 < len(line):
                                next_item = line[idx + 1]
                                # 处理嵌套结构
                                if isinstance(next_item, list) and len(next_item) > 0:
                                    next_item_text = str(next_item[0])
                                else:
                                    next_item_text = str(next_item)
                                
                                print(f"下一个字段: {next_item_text}")
                                
                                # 简化条件：只要不是编码格式，就作为诊断名称
                                if not re.match(r'^[A-Z]', next_item_text) and len(next_item_text) > 1:
                                    print(f"提取门（急）诊诊断: {next_item_text}")
                                    results["门（急）诊诊断"].append(next_item_text)
                                    
                                    # 同时尝试提取编码（再下一个字段）
                                    if idx + 2 < len(line):
                                        code_item = line[idx + 2]
                                        if isinstance(code_item, list) and len(code_item) > 0:
                                            code_item_text = str(code_item[0])
                                        else:
                                            code_item_text = str(code_item)
                                        
                                        print(f"编码字段: {code_item_text}")
                                        # 查找疾病编码
                                        code_match = re.search(r'[A-Z]\d+\.?\d*', code_item_text)
                                        if code_match:
                                            code = code_match.group(0)
                                            print(f"提取门（急）诊诊断编码: {code}")
                                            results["门（急）诊诊断编码"].append(code)
                                else:
                                    print(f"字段 {next_item_text} 不符合条件")
                            else:
                                print("没有下一个字段")
                            break
                
                # 移除重复的编码提取逻辑，避免编码重复添加

            if "主要诊断" in line_text:
                # 主诊编码提取：兼容“门诊+主诊同一行”和“主诊+其他诊断同一行”
                code_candidates = []
                line_codes = []
                for item in line:
                    item_text = str(item[0]) if isinstance(item, list) and len(item) > 0 else str(item)
                    line_codes.extend(_extract_main_diag_codes(item_text))
                line_codes = _unique_keep_order(line_codes)

                m = re.search(r"主要诊断[：:]?", line_text)
                if m:
                    tail = line_text[m.end():]
                    stop_keywords = ["入院病情", "损伤、中毒", "病理诊断"]
                    stop_pos = len(tail)
                    for kw in stop_keywords:
                        p = tail.find(kw)
                        if p != -1 and p < stop_pos:
                            stop_pos = p
                    seg = tail[:stop_pos]
                    code_candidates.extend(_extract_main_diag_codes(seg))

                code_candidates = _unique_keep_order(code_candidates)
                if len(line_codes) == 1:
                    # 字段级结果优先，避免整行拼接把编码与后续“1”粘连成 H22.01 这类误码
                    code_candidates = [line_codes[0]]
                elif "其他诊断" in line_text and len(line_codes) >= 2:
                    # 主诊和其他诊断同一行时，不在此处硬选“首个/末个”。
                    # 保留整行候选，交由后处理结合“其他诊断编码”做差集裁决，
                    # 可避免把其他诊断码误判为主诊码（如 S01.101 抢占 S04.000x001）。
                    code_candidates = list(line_codes)
                elif not code_candidates and line_codes:
                    # 片段未命中时，兜底取该行最后一个编码（可避开门诊码前缀）
                    code_candidates = [line_codes[-1]]

                if code_candidates:
                    # 先全部保留给后处理裁决，不在这里截断
                    results["主要诊断编码"].extend(code_candidates)

                # 提取主要诊断文本
                for item in line:
                    if isinstance(item, list) and len(item) > 0:
                        item_text = str(item[0])
                    else:
                        item_text = str(item)

                    if "主要诊断：" in item_text or "主要诊断:" in item_text:
                        diagnosis = item_text.replace("主要诊断：", "").replace("主要诊断:", "").strip()
                        diagnosis = _clean_main_diag_text(diagnosis)
                        if diagnosis and not CODE_PATTERN.match(diagnosis):
                            results["主要诊断"].append(diagnosis)
                        break

            if "病理诊断" in line_text:
                print(f"找到病理诊断行: {line_text}")
                
                # 使用通用函数提取病理诊断结果和编码
                diagnosis_result, diagnosis_code = extract_diagnosis_with_disease_code_generic(line_text, line, "病理诊断")
                
                # 检查是否为无效的病理诊断结果，如果是则直接抛弃
                invalid_results = ["费：", "费", "费:", "一", "E", "二", "-", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"]
                if diagnosis_result and diagnosis_result.strip() in invalid_results:
                    print(f"抛弃无效的病理诊断结果: {diagnosis_result}")
                    diagnosis_result = ""
                
                # 只保留第一个有效的病理诊断结果
                if diagnosis_result and not results["病理诊断"]:
                    print(f"提取病理诊断结果: {diagnosis_result}")
                    results["病理诊断"].append(diagnosis_result)
                elif diagnosis_result:
                    print(f"跳过后续病理诊断结果，只保留第一个: {diagnosis_result}")
                
                # 只保留第一个有效的病理诊断编码
                if diagnosis_code and not results["病理诊断编码"]:
                    print(f"提取病理诊断编码: {diagnosis_code}")
                    results["病理诊断编码"].append(diagnosis_code)
                elif diagnosis_code:
                    print(f"跳过后续病理诊断编码，只保留第一个: {diagnosis_code}")

            if "年龄不足1周岁" in line_text or "(年龄不足1周岁的)年龄" in line_text:
                for item in line:
                    # 处理嵌套结构
                    if isinstance(item, list) and len(item) > 0:
                        item_text = str(item[0])
                    else:
                        item_text = str(item)
                    
                    if item_text.isdigit():
                        results["年龄不足一周岁的年龄"].append(item_text)
                        break

            if "年龄" in line_text:
                if "不足1周岁" not in line_text and "(年龄不足1周岁的)年龄" not in line_text:
                    for idx, item in enumerate(line):
                        # 处理嵌套结构
                        if isinstance(item, list) and len(item) > 0:
                            item_text = str(item[0])
                        else:
                            item_text = str(item)
                        
                        if item_text == "年龄" or "年龄" in item_text:
                            if idx + 1 < len(line):
                                next_item = line[idx + 1]
                                # 处理嵌套结构
                                if isinstance(next_item, list) and len(next_item) > 0:
                                    next_item_text = str(next_item[0])
                                else:
                                    next_item_text = str(next_item)
                                
                                if next_item_text.isdigit() and len(next_item_text) <= 3:
                                    results["年龄"].append(next_item_text)
                            age_match = re.search(r'(\d{2,3})$', item_text)
                            if age_match and len(age_match.group(1)) <= 3:
                                results["年龄"].append(age_match.group(1))
                            break

            if "新生儿出生体重" in line_text:
                for item in line:
                    # 处理嵌套结构
                    if isinstance(item, list) and len(item) > 0:
                        item_text = str(item[0])
                    else:
                        item_text = str(item)
                    
                    if item_text.isdigit():
                        results["新生儿出生体重"].append(item_text)
                        break

            if "新生儿入院体重" in line_text:
                for item in line:
                    # 处理嵌套结构
                    if isinstance(item, list) and len(item) > 0:
                        item_text = str(item[0])
                    else:
                        item_text = str(item)
                    
                    if item_text.isdigit():
                        results["新生儿入院体重"].append(item_text)
                        break

            # 改进实际住院天数提取：从"实际住院21"格式中提取数字
            if "实际住院" in line_text:
                # 使用正则表达式提取"实际住院XX"中的数字（去掉对"天"字的匹配要求）
                days_match = re.search(r'实际住院\s*(\d+)', line_text)
                if days_match:
                    results["实际住院天数"].append(days_match.group(1))
                else:
                    # 备用方案：逐个检查字段
                    for idx, item in enumerate(line):
                        # 处理嵌套结构
                        if isinstance(item, list) and len(item) > 0:
                            item_text = str(item[0])
                        else:
                            item_text = str(item)
                        
                        if item_text == "实际住院":
                            if idx + 1 < len(line):
                                next_item = line[idx + 1]
                                # 处理嵌套结构
                                if isinstance(next_item, list) and len(next_item) > 0:
                                    next_item_text = str(next_item[0])
                                else:
                                    next_item_text = str(next_item)
                                
                                if next_item_text.isdigit():
                                    results["实际住院天数"].append(next_item_text)
                            break

            # 总费用提取：用结构化正则替代 fuzzy_match，兼容缺字和字段错位
            fee_amount = ""
            m = re.search(r"总费用[^0-9]{0,20}([0-9][0-9,]*\.[0-9]{2})", line_text)
            if not m:
                m = re.search(r"([0-9][0-9,]*\.[0-9]{2})[^0-9]{0,12}自付金额", line_text)
            if not m and ("费用" in line_text or "总费" in line_text):
                nums = re.findall(r"[0-9][0-9,]*\.[0-9]{2}", line_text)
                if nums:
                    fee_amount = max(nums, key=lambda x: float(x.replace(",", "")))
            elif m:
                fee_amount = m.group(1)
            if fee_amount:
                results["住院费用（元）：总费用"].append(fee_amount.replace(",", ""))

    return _postprocess_results(results, finalize_main_diag=False)


class DRGFieldExtractor:
    def __init__(self, input_dir1, input_dir2, input_dir3, order1):
        self.input_dir1 = input_dir1
        self.input_dir2 = input_dir2
        self.input_dir3 = input_dir3
        self.order = order1
    # script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 使用step2目录中的文件作为OCR数据输入（包含Page1和Page2）
    # self.input_dir1 = "DRG_model\output\step2\\5_eye_Page1_2.0_line_diag_grouped_advanced.json"
    # self.input_dir2 = "DRG_model\output\step2\\5_eye_Page2_2.0_line_proc_grouped_advanced.json"
    # input_dir3 = "DRG_model\output\step3\\extracted_fields2.json"
    def run(self):
        # 确保输出目录存在
        # 从order参数中提取文件名前缀数字
        order_filename = os.path.basename(self.order)
        prefix_match = re.search(r'^(\d+)', order_filename)
        if prefix_match:
            prefix = prefix_match.group(1)
            self.output_path = f"DRG_model/output/step4/{prefix}_drg_fields.json"
        else:
            self.output_path = "DRG_model/output/step4/drg_fields.json"
            
        output_dir = os.path.dirname(self.output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            print(f"创建输出目录: {output_dir}")
        print(f"输出文件路径: {self.output_path}")
        
        # 检查输入目录是否存在
        if not os.path.exists(self.input_dir1):
            print(f"输入目录不存在: {self.input_dir1}")
            return
        if not os.path.exists(self.input_dir2):
            print(f"输入目录不存在: {self.input_dir2}")
            return
        
        # 查找所有JSON文件
        # json_files1 = glob.glob(os.path.join(self.input_dir1, '*.json'))
        # json_files2 = glob.glob(os.path.join(self.input_dir2, '*.json'))
        # json_files3 = glob.glob(os.path.join(self.input_dir3, '*.json'))
        
        # if not json_files1:
        #     print(f"在目录 {self.input_dir1} 中未找到JSON文件")
        #     return
        # if not json_files2:
        #     print(f"在目录 {self.input_dir2} 中未找到JSON文件")
        #     return
        # if not json_files3:
        #     print(f"在目录 {self.input_dir3} 中未找到JSON文件")
        #     return
       
        # 加载Page1 OCR数据
        with open(self.input_dir1, 'r', encoding='utf-8') as f:
            ocr_data_page1 = json.load(f)

        # 加载Page2 OCR数据
        with open(self.input_dir2, 'r', encoding='utf-8') as f:
            ocr_data_page2 = json.load(f)

        # 加载提取的字段数据
        with open(self.input_dir3, 'r', encoding='utf-8') as f:
            extracted_data = json.load(f)

        # 检查OCR数据结构是否包含lines字段
        if 'lines' in ocr_data_page1:
            # 将OCR数据转换为与extract_info_from_ocr函数兼容的格式
            processed_ocr_data = {
                '5_eye_Page1': {
                    'lines': ocr_data_page1.get('lines', [])
                },
                '5_eye_Page2': {
                    'lines': ocr_data_page2.get('lines', [])
                }
            }
            results = extract_info_from_ocr(processed_ocr_data)
        else:
            # 如果OCR数据已经是提取后的格式，直接使用空结果
            results = {
                "年龄": [],
                "年龄不足一周岁的年龄": [],
                "新生儿出生体重": [],
                "新生儿入院体重": [],
                "实际住院天数": [],
                "门（急）诊诊断": [],
                "门（急）诊诊断编码": [],
                "主要诊断": [],
                "主要诊断编码": [],
                "其他诊断名称": [],
                "其他诊断编码": [],
                "手术及操作名称": [],
                "手术及操作编码": [],
                "病理诊断": [],
                "病理诊断编码": [],
                "住院费用（元）：总费用": []
            }

        # 处理提取的字段数据
        for image_key, image_data in extracted_data.items():
            extracted_fields = image_data.get("extracted_fields", {})

            # 从extracted_fields.json获取其他诊断名称和编码（分开的数组）
            other_diagnoses = extracted_fields.get("其他诊断", [])
            other_diagnoses_codes = extracted_fields.get("其他诊断编码", [])
            
            # 将其他诊断名称添加到结果中
            for diag in other_diagnoses:
                results["其他诊断名称"].append(diag)
            
            # 将其他诊断编码添加到结果中，确保与名称顺序对应
            for code in other_diagnoses_codes:
                results["其他诊断编码"].append(code)

            # 从extracted_fields.json获取手术及操作名称和编码（分开的数组）
            operations = extracted_fields.get("手术及操作", [])
            operations_codes = extracted_fields.get("手术及操作编码", [])
            
            # 将手术及操作名称添加到结果中
            for op in operations:
                results["手术及操作名称"].append(op)
            
            # 将手术及操作编码添加到结果中，确保与名称顺序对应
            for code in operations_codes:
                results["手术及操作编码"].append(code)

        # 二次后处理：融合step3结果后再次清洗和主诊编码裁决
        results = _postprocess_results(results)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"DRG字段抽取结果已保存到: {self.output_path}")
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 设置输入目录，使用正确的路径格式
    input_dir1 = os.path.join("DRG_model", "output", "step2", "page_1_line_diag_grouped.json")
    input_dir2 = os.path.join("DRG_model", "output", "step2", "page_2_line_proc_grouped.json")
    input_dir3 = os.path.join("DRG_model", "output", "step3", "step3_diag_proc.json")
    order = os.path.join("DRG_model", "output", "step1", "09_page_1.json")
    
    print(f"输入文件1: {input_dir1}")
    print(f"输入文件2: {input_dir2}")
    print(f"输入文件3: {input_dir3}")
    print(f"Order文件: {order}")
    
    extractor = DRGFieldExtractor(input_dir1, input_dir2, input_dir3, order)
    extractor.run()
