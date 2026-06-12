import json
import os
from PIL import Image
import numpy as np



# -------------------------- 配置参数 --------------------------
# # 原图像路径（使用已有的裁剪好的图像）
# ORIGINAL_IMAGE_PATH = r"dataset\pngdata\page_1.png"
# # OCR结果路径
# OCR_JSON_PATH = r"DRG_model\output\step1\page_1.json"
# # 保存目录
# SAVE_DIR = r"DRG_model\output\step5-gender"


def find_gender_block(ocr_data):
    """
    从OCR结果中找到性别文本块（增强容错性）
    :param ocr_data: OCR结果数据
    :return: 性别文本块字典
    """
    # 检查OCR数据格式
    if 'pages' not in ocr_data:
        raise ValueError("❌ OCR结果格式不正确，缺少'pages'字段")
    
    # 获取第一个页面的结果
    if len(ocr_data['pages']) == 0:
        raise ValueError("❌ OCR结果中没有页面数据")
    
    page_data = ocr_data['pages'][0]
    all_blocks = page_data.get('results', [])
    
    print(f"🔍 在OCR结果中搜索性别相关文本块...")
    print(f"   共找到 {len(all_blocks)} 个文本块")
    
    gender_blocks = []
    
    # 多种匹配模式，提高容错性
    for i, block in enumerate(all_blocks):
        text = block['text'].strip()
        
        # 调试信息：显示前几个文本块内容
        if i < 10:  # 只显示前10个文本块以控制输出
            print(f"   文本块 {i+1}: '{text}'")
        
        # 多种匹配模式
        if '性别' in text:
            gender_blocks.append(block)
            print(f"✅ 找到匹配'性别'的文本块: '{text}'")
        elif '别' in text and len(text) <= 5:  # 简短的包含"别"字的文本
            gender_blocks.append(block)
            print(f"⚠️  找到可能匹配的文本块: '{text}'")
        elif '男' in text or '女' in text:  # 包含性别内容的文本
            gender_blocks.append(block)
            print(f"⚠️  找到包含性别内容的文本块: '{text}'")
    
    if not gender_blocks:
        # 如果没找到，尝试更宽松的匹配
        print("⚠️  未找到直接匹配的性别文本块，尝试宽松匹配...")
        for block in all_blocks:
            text = block['text'].strip()
            # 查找包含"性"或"别"的短文本
            if ('性' in text or '别' in text) and len(text) <= 10:
                gender_blocks.append(block)
                print(f"⚠️  找到宽松匹配的文本块: '{text}'")
    
    if not gender_blocks:
        # 如果仍然没找到，显示更多调试信息
        print("❌ 在OCR结果中未找到包含'性别'的文本块")
        print("📋 前20个文本块内容:")
        for i, block in enumerate(all_blocks[:20]):
            print(f"   {i+1}: '{block['text'].strip()}'")
        raise ValueError("❌ 在OCR结果中未找到包含'性别'的文本块")
    
    # 如果有多个匹配，选择最可能的一个
    if len(gender_blocks) > 1:
        print(f"⚠️  找到 {len(gender_blocks)} 个可能的性别文本块")
        # 优先选择包含"性别"的完整文本
        for block in gender_blocks:
            if '性别' in block['text']:
                print(f"✅ 选择完整匹配: '{block['text']}'")
                return block
        # 否则选择文本最短的（通常性别字段较短）
        gender_blocks.sort(key=lambda x: len(x['text']))
        print(f"⚠️  选择最短文本: '{gender_blocks[0]['text']}'")
    
    return gender_blocks[0]


def get_adjusted_coordinates(gender_block):
    """
    根据性别文本块的Y坐标范围，计算调整后的裁剪范围
    :param gender_block: 性别文本块字典
    :return: 调整后的Y坐标范围 (y_min_adjusted, y_max_adjusted)
    """
    bbox = gender_block['bbox']
    
    # 检查bbox格式：如果是4个整数的列表 [x_min, y_min, x_max, y_max]
    if isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(coord, int) for coord in bbox):
        # 直接从bbox中提取Y坐标范围
        y_min_original = bbox[1]
        y_max_original = bbox[3]
    else:
        # 尝试兼容其他格式
        try:
            # 从bbox中提取所有Y坐标
            y_coords = [point[1] for point in bbox]
            y_min_original = min(y_coords)
            y_max_original = max(y_coords)
        except Exception as e:
            print(f"⚠️  bbox格式异常: {bbox}")
            raise ValueError(f"bbox格式不支持: {str(e)}")
    
    print(f"\n=== 性别文本块信息 ===")
    print(f"文本内容: {gender_block['text']}")
    print(f"原始Y坐标范围: Y[{y_min_original}-{y_max_original}]px")
    
    # 按照要求调整Y坐标范围：最小值增加20像素，最大值增加60像素
    y_min_adjusted = y_min_original + 40
    y_max_adjusted = y_max_original + 300
    
    print(f"\n=== 调整后的Y坐标范围 ===")
    print(f"Y最小值: {y_min_adjusted}px (原始+20px)")
    print(f"Y最大值: {y_max_adjusted}px (原始+60px)")
    print(f"调整后范围: Y[{y_min_adjusted}-{y_max_adjusted}]px")
    
    return y_min_adjusted, y_max_adjusted


def crop_and_save_image(img, y_min_adjusted, y_max_adjusted, save_path):
    """
    在调整后的Y坐标范围内裁剪图像并保存
    :param img: 原始图像
    :param y_min_adjusted: 调整后的Y最小值
    :param y_max_adjusted: 调整后的Y最大值
    :param save_path: 保存路径
    :return: 裁剪后的图像
    """
    # 获取图像尺寸
    w, h = img.size
    
    # 确保裁剪范围在图像尺寸内
    y_min_adjusted = max(0, int(y_min_adjusted))
    y_max_adjusted = min(h, int(y_max_adjusted))
    
    if y_min_adjusted >= y_max_adjusted:
        raise ValueError(f"❌ 裁剪范围无效: Y[{y_min_adjusted}-{y_max_adjusted}]px")
    
    # 裁剪图像 (left, upper, right, lower)
    cropped_img = img.crop((0, y_min_adjusted, w, y_max_adjusted))
    
    # 保存裁剪后的图像
    cropped_img.save(save_path)
    
    # 获取裁剪后的尺寸
    crop_w, crop_h = cropped_img.size
    
    print(f"\n=== 裁剪结果 ===")
    print(f"原始图像尺寸: {w}x{h}px")
    print(f"裁剪区域: X[0-{w}], Y[{y_min_adjusted}-{y_max_adjusted}]px")
    print(f"裁剪后图像尺寸: {crop_w}x{crop_h}px")
    print(f"裁剪图像已保存至: {save_path}")
    
    return cropped_img


class GenderExtractor:
    def __init__(self, ocr_json_path, original_img_path, ocr_diag_png_desc):
        self.ocr_json_path = ocr_json_path
        self.original_img_path = original_img_path
        self.ocr_diag_png_desc = ocr_diag_png_desc
        
    
    def run(self):
        self.save_dir = "DRG_model\output\step5-gender"
        # 读取OCR JSON文件
        print(f"\n📖 正在读取OCR结果文件: {self.ocr_json_path}")
        with open(self.ocr_json_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        # 找到性别文本块
        gender_block = find_gender_block(ocr_data)
        
        # 计算调整后的Y坐标范围
        y_min_adjusted, y_max_adjusted = get_adjusted_coordinates(gender_block)
        
        # 读取原始图像
        print(f"\n🖼️  正在读取原始图像: {self.original_img_path}")
        img = Image.open(self.original_img_path)
        if img is None:
            raise ValueError(f"❌ 无法读取图像: {self.original_img_path}")
        
        # 生成保存路径
        save_filename = "gender_adjusted_crop.png"
        save_path = os.path.join(self.save_dir, save_filename)  
        
        # 裁剪并保存图像
        crop_and_save_image(img, y_min_adjusted-20, y_max_adjusted-180, save_path)
        
        print(f"\n✅ 所有操作完成！")
        return save_path



# if __name__ == "__main__":
#     main()