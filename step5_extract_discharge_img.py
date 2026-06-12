import json
import os
from PIL import Image
import numpy as np

# -------------------------- 配置参数 --------------------------
# 原图像路径（使用Page2图像）
# self.original_img_path = r"dataset\pngdata\page_2.png"
# # OCR结果路径（使用Page2图像）
# OCR_JSON_PATH = r"DRG_model\output\step1\page_2.json"
# # 保存目录
# SAVE_DIR = r"DRG_model\output\step5-discharge_method"

# -------------------------- 工具函数 --------------------------
def find_discharge_method_block(ocr_data):
    """
    从OCR结果中找到离院方式文本块（增强版）
    :param ocr_data: OCR结果数据
    :return: 离院方式文本块字典
    """
    # 检查OCR数据格式
    if 'pages' not in ocr_data:
        raise ValueError("❌ OCR结果格式不正确，缺少'pages'字段")
    
    # 获取第一个页面的结果
    if len(ocr_data['pages']) == 0:
        raise ValueError("❌ OCR结果中没有页面数据")
    
    page_data = ocr_data['pages'][0]
    all_blocks = page_data.get('results', [])
    
    discharge_blocks = []
    for block in all_blocks:
        text = block['text'].strip()
        # 多种匹配模式，提高容错性
        if '离院' in text or '出院' in text or '方式' in text:
            discharge_blocks.append(block)
    
    if not discharge_blocks:
        raise ValueError("❌ 在OCR结果中未找到包含'离院'、'出院'或'方式'的文本块")
    
    # 如果有多个匹配，选择最可能的一个
    if len(discharge_blocks) > 1:
        # 优先选择包含"离院方式"的完整文本
        for block in discharge_blocks:
            if '离院方式' in block['text']:
                print(f"✅ 找到完整匹配: {block['text']}")
                return block
        # 否则选择文本最长的
        discharge_blocks.sort(key=lambda x: len(x['text']), reverse=True)
        print(f"⚠️  多个匹配，选择最长的: {discharge_blocks[0]['text']}")
    
    print(f"✅ 找到匹配: {discharge_blocks[0]['text']}")
    return discharge_blocks[0]

def get_adjusted_coordinates(discharge_block, ocr_diag_png_desc_height, original_img_height):
    """
    根据离院方式文本块的Y坐标范围，计算调整后的裁剪范围
    :param discharge_block: 离院方式文本块字典
    :param ocr_diag_png_desc_height: OCR诊断图像的高度
    :param original_img_height: 原始图像的高度
    :return: 调整后的Y坐标范围 (y_min_adjusted, y_max_adjusted)
    """
    bbox = discharge_block['bbox']
    
    # 从bbox中提取所有Y坐标
    y_coords = [point[1] for point in bbox]
    y_min_original = min(y_coords)
    y_max_original = max(y_coords)
    
    # 计算在OCR诊断图像中的Y坐标占比
    y_min_ratio = y_min_original / ocr_diag_png_desc_height
    y_max_ratio = y_max_original / ocr_diag_png_desc_height
    
    # 将同样的比例应用到原始图像中
    y_min_adjusted = y_min_ratio * original_img_height
    y_max_adjusted = y_max_ratio * original_img_height
    
    # 添加固定像素调整，类似于gender文件的做法，提高稳定性
    y_min_adjusted = max(0, y_min_adjusted - 20)  # 向上扩展20像素
    y_max_adjusted = y_max_adjusted + 60  # 向下扩展60像素
    
    print(f"比例计算: Y[{y_min_original}-{y_max_original}]px -> 占比[{y_min_ratio:.3f}-{y_max_ratio:.3f}] -> 调整后[{y_min_adjusted:.1f}-{y_max_adjusted:.1f}]px")
    
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

def read_image_with_chinese_path(img_path):
    try:
        img = Image.open(img_path)
        return img
    except Exception as e:
        print(f"读取图像失败：{img_path}，错误：{e}")
        return None

class DischargeMethodExtractor:
    """
    离院方式行提取器
    """
    def __init__(self, ocr_json_path, original_img_path, ocr_proc_png_desc):
        self.ocr_json_path = ocr_json_path
        self.original_img_path = original_img_path
        self.ocr_proc_png_desc = ocr_proc_png_desc
    
    def run(self):
        self.save_dir = r"DRG_model\output\step5-discharge_method"
        
        # 读取OCR诊断图像获取高度
        print(f"\n🖼️  正在读取OCR诊断图像: {self.ocr_proc_png_desc}")
        ocr_diag_img = Image.open(self.ocr_proc_png_desc)
        if ocr_diag_img is None:
            raise ValueError(f"❌ 无法读取OCR诊断图像: {self.ocr_proc_png_desc}")
        ocr_diag_img_height = ocr_diag_img.height
        print(f"OCR诊断图像高度: {ocr_diag_img_height}px")
        
        # 读取原始图像获取高度
        print(f"\n🖼️  正在读取原始图像: {self.original_img_path}")
        original_img = Image.open(self.original_img_path)
        if original_img is None:
            raise ValueError(f"❌ 无法读取原始图像: {self.original_img_path}")
        original_img_height = original_img.height
        print(f"原始图像高度: {original_img_height}px")
        
        # 读取OCR JSON文件
        print(f"\n📖 正在读取OCR结果文件: {self.ocr_json_path}")
        with open(self.ocr_json_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        # 找到离院方式文本块
        discharge_block = find_discharge_method_block(ocr_data)
        
        print(f"\n=== 离院方式文本块详细信息 ===")
        print(f"文本内容: {discharge_block['text']}")
        print(f"置信度: {discharge_block.get('score', 'N/A')}")
        print(f"bbox坐标: {discharge_block['bbox']}")
        
        # 从bbox中提取所有Y坐标
        y_coords = [point[1] for point in discharge_block['bbox']]
        y_min_original = min(y_coords)
        y_max_original = max(y_coords)
        
        # 使用比例计算调整后的Y坐标范围
        y_min_adjusted, y_max_adjusted = get_adjusted_coordinates(
            discharge_block, ocr_diag_img_height, original_img_height
        )
        
        print(f"\n=== 坐标计算详情 ===")
        print(f"在OCR诊断图像中的Y坐标范围: Y[{y_min_original}-{y_max_original}]px")
        print(f"OCR诊断图像高度: {ocr_diag_img_height}px")
        print(f"Y最小值占比: {y_min_original/ocr_diag_img_height:.4f}")
        print(f"Y最大值占比: {y_max_original/ocr_diag_img_height:.4f}")
        print(f"原始图像高度: {original_img_height}px")
        print(f"调整后Y最小值: {y_min_adjusted:.1f}px")
        print(f"调整后Y最大值: {y_max_adjusted:.1f}px")
        print(f"调整后范围: Y[{y_min_adjusted:.1f}-{y_max_adjusted:.1f}]px")
        
        # 生成保存路径
        save_filename = "discharge_method_adjusted_crop.png"
        save_path = os.path.join(self.save_dir, save_filename)
        
        # 裁剪并保存图像
        crop_and_save_image(original_img, y_min_adjusted+7, y_max_adjusted-10, save_path)
        
        print(f"\n✅ 所有操作完成！")
        return save_path



# if __name__ == "__main__":
#     main()
