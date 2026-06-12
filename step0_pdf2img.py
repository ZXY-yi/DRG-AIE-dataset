import os
import json
import io
from pdf2image import convert_from_path
from PIL import Image, ImageOps
import numpy as np


def compress_image_to_size(image, max_size_kb=150, min_size_kb=None, quality_step=5):
    """
    压缩图像到指定大小范围
    
    Args:
        image: PIL图像对象
        max_size_kb: 最大文件大小（KB）
        min_size_kb: 最小文件大小（KB），如果为None则只限制最大大小
        quality_step: 每次压缩的质量步长
        
    Returns:
        压缩后的图像数据（bytes）
    """
    # 转换为RGB模式（如果需要）
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # 初始质量设置
    quality = 95
    
    # 根据目标文件大小调整缩放策略
    if min_size_kb is not None and min_size_kb >= 600:
        # 对于大文件（600KB+），减少缩放程度
        max_dimension_limit = 2500  # 提高最大尺寸限制
        secondary_limit = 2000      # 提高二次缩放限制
    else:
        # 对于小文件，保持原有缩放策略
        max_dimension_limit = 1500
        secondary_limit = 1200
    
    # 如果图像尺寸太大，先进行缩放
    width, height = image.size
    max_dimension = max(width, height)
    
    if max_dimension > max_dimension_limit:
        scale_factor = max_dimension_limit / max_dimension
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        image = image.resize((new_width, new_height), Image.LANCZOS)
        print(f"   图像尺寸过大 ({width}x{height})，缩放到 {new_width}x{new_height}")
    
    # 如果图像尺寸仍然太大，进行二次缩放
    width, height = image.size
    max_dimension = max(width, height)
    
    if max_dimension > secondary_limit:
        scale_factor = secondary_limit / max_dimension
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        image = image.resize((new_width, new_height), Image.LANCZOS)
        print(f"   图像尺寸仍然过大 ({width}x{height})，二次缩放到 {new_width}x{new_height}")
    
    while True:
        # 将图像保存到内存缓冲区
        buffer = io.BytesIO()
        
        # 使用JPEG格式进行压缩，因为JPEG支持quality参数
        image.save(buffer, format='JPEG', quality=quality, optimize=True, subsampling=1)
        
        # 获取文件大小（字节）
        file_size = buffer.tell()
        file_size_kb = file_size / 1024
        
        # 检查是否满足要求
        if min_size_kb is not None:
            # 有最小大小限制的情况：需要在指定范围内
            if min_size_kb <= file_size_kb <= max_size_kb:
                print(f"   压缩完成: {file_size_kb:.1f}KB (质量: {quality})")
                return buffer.getvalue()
            elif file_size_kb < min_size_kb:
                # 文件太小，需要提高质量
                if quality >= 95:
                    # 已经达到最高质量，无法再提高
                    print(f"   已达到最高质量，文件大小: {file_size_kb:.1f}KB")
                    return buffer.getvalue()
                quality += quality_step
                if quality > 95:
                    quality = 95
                print(f"   文件太小: {file_size_kb:.1f}KB -> 提高质量到 {quality}")
                continue
        else:
            # 只有最大大小限制的情况
            if file_size_kb <= max_size_kb or quality <= 10:
                print(f"   压缩完成: {file_size_kb:.1f}KB (质量: {quality})")
                return buffer.getvalue()
        
        # 降低质量继续压缩
        quality -= quality_step
        if quality < 10:
            quality = 10
            
        print(f"   压缩中: {file_size_kb:.1f}KB -> 降低质量到 {quality}")


def save_compressed_image(image, output_path, max_size_kb=150, min_size_kb=None):
    """
    保存压缩后的图像
    
    Args:
        image: PIL图像对象
        output_path: 输出文件路径
        max_size_kb: 最大文件大小（KB）
        min_size_kb: 最小文件大小（KB），如果为None则只限制最大大小
    """
    try:
        # 压缩图像
        compressed_data = compress_image_to_size(image, max_size_kb, min_size_kb)
        
        # 保存压缩后的图像
        with open(output_path, 'wb') as f:
            f.write(compressed_data)
        
        # 检查最终文件大小
        file_size_kb = os.path.getsize(output_path) / 1024
        print(f"   最终文件大小: {file_size_kb:.1f}KB")
        
        return True
        
    except Exception as e:
        print(f"❌ 保存压缩图像时出错: {e}")
        return False


def convert_pdf_to_images(pdf_path, dpi=300):
    """
    将PDF转换为图像列表
    :param pdf_path: PDF文件路径
    :param dpi: 转换分辨率
    :return: 图像列表
    """
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
        print(f"✅ 成功将PDF转换为 {len(images)} 页图像")
        return images
    except Exception as e:
        print(f"❌ PDF转图像失败: {e}")
        return []


def load_images_from_directory(image_dir, image_patterns):
    """
    从目录中加载图像文件
    :param image_dir: 图像目录
    :param image_patterns: 图像文件名模式列表
    :return: 图像列表
    """
    images = []
    
    for pattern in image_patterns:
        image_path = os.path.join(image_dir, pattern)
        if os.path.exists(image_path):
            try:
                image = Image.open(image_path)
                images.append(image)
                print(f"✅ 成功加载图像: {pattern}")
            except Exception as e:
                print(f"❌ 加载图像失败 {pattern}: {e}")
        else:
            print(f"❌ 未找到图像文件: {pattern}")
    
    print(f"📋 共加载 {len(images)} 页图像")
    return images


def crop_white_margins(image, margins, max_length=3000):
    """
    裁剪图像的白色边缘
    :param image: 输入图像
    :param margins: 裁剪阈值，格式为 [left, top, right, bottom]
    :param max_length: 最长边限制
    :return: 裁剪后的图像
    """
    left, top, right, bottom = margins
    
    # 获取图像尺寸
    width, height = image.size
    
    # 应用裁剪阈值
    crop_box = (
        max(0, left),
        max(0, top),
        min(width, width - right),
        min(height, height - bottom)
    )
    
    # 裁剪图像
    cropped = image.crop(crop_box)
    
    # 检查最长边是否超过限制
    crop_width, crop_height = cropped.size
    max_dimension = max(crop_width, crop_height)
    
    if max_dimension > max_length:
        # 计算缩放比例
        scale = max_length / max_dimension
        new_width = int(crop_width * scale)
        new_height = int(crop_height * scale)
        
        # 缩放图像
        cropped = cropped.resize((new_width, new_height), Image.LANCZOS)
        print(f"📏 图像已缩放到 {new_width}x{new_height} 像素")
    
    return cropped


def process_pdf_dual_output(pdf_path, output_dir_600kb, output_dir_100kb, page_margins, number_prefix, dpi=300):
    """
    处理PDF文件，按页裁剪并保存两种分辨率的图像
    :param pdf_path: PDF文件路径
    :param output_dir_600kb: 600KB输出目录
    :param output_dir_100kb: 100KB输出目录
    :param page_margins: 每页的裁剪阈值，格式为 {page_num: [left, top, right, bottom]}
    :param number_prefix: 数字前缀
    :param dpi: 转换分辨率
    """
    # 创建输出目录
    os.makedirs(output_dir_600kb, exist_ok=True)
    os.makedirs(output_dir_100kb, exist_ok=True)
    
    # 转换PDF为图像
    images = convert_pdf_to_images(pdf_path, dpi)
    
    if not images:
        return
    
    # 处理每一页
    for page_num, image in enumerate(images):
        page_key = page_num + 1  # 页码从1开始
        
        # 获取当前页的裁剪阈值
        if page_key in page_margins:
            margins = page_margins[page_key]
        else:
            # 如果没有指定当前页的阈值，使用默认值
            margins = [0, 0, 0, 0]
            print(f"⚠️  第 {page_key} 页未指定裁剪阈值，使用默认值")
        
        print(f"\n📄 处理第 {page_key} 页:")
        print(f"   原始尺寸: {image.size[0]}x{image.size[1]} 像素")
        print(f"   裁剪阈值: 左-{margins[0]}px, 上-{margins[1]}px, 右-{margins[2]}px, 下-{margins[3]}px")
        
        # 裁剪图像
        cropped_image = crop_white_margins(image, margins)
        
        # 600KB版本输出路径
        output_path_600kb = os.path.join(output_dir_600kb, f"{number_prefix}_page_{page_key}.png")
        
        print(f"✅ 裁剪完成")
        print(f"   裁剪后尺寸: {cropped_image.size[0]}x{cropped_image.size[1]} 像素")
        
        # 保存600KB版本（控制在600-700KB范围内）
        print(f"   开始600KB版本压缩...")
        save_compressed_image(cropped_image, output_path_600kb, max_size_kb=700, min_size_kb=600)
        
        # 100KB版本输出路径
        output_path_100kb = os.path.join(output_dir_100kb, f"{number_prefix}_page_{page_key}.png")
        
        # 保存100KB版本（重度压缩）
        print(f"   开始100KB版本压缩...")
        save_compressed_image(cropped_image, output_path_100kb, max_size_kb=100)

def process_images(image_dir, image_patterns, output_dir, page_margins, number_prefix):
    """
    处理图像文件，按页裁剪并保存
    :param image_dir: 图像目录
    :param image_patterns: 图像文件名模式列表
    :param output_dir: 输出目录
    :param page_margins: 每页的裁剪阈值，格式为 {page_num: [left, top, right, bottom]}
    :param number_prefix: 数字前缀
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 加载图像
    images = load_images_from_directory(image_dir, image_patterns)
    
    if not images:
        return
    
    # 处理每一页
    for page_num, image in enumerate(images):
        page_key = page_num + 1  # 页码从1开始
        
        # 获取当前页的裁剪阈值
        if page_key in page_margins:
            margins = page_margins[page_key]
        else:
            # 如果没有指定当前页的阈值，使用默认值
            margins = [0, 0, 0, 0]
            print(f"⚠️  第 {page_key} 页未指定裁剪阈值，使用默认值")
        
        print(f"\n📄 处理第 {page_key} 页:")
        print(f"   原始尺寸: {image.size[0]}x{image.size[1]} 像素")
        print(f"   裁剪阈值: 左-{margins[0]}px, 上-{margins[1]}px, 右-{margins[2]}px, 下-{margins[3]}px")
        
        # 裁剪图像
        cropped_image = crop_white_margins(image, margins)
        
        # 保存裁剪后的图像，使用数字前缀命名，并进行压缩
        output_path = os.path.join(output_dir, f"{number_prefix}_page_{page_key}.png")
        
        print(f"✅ 裁剪完成，保存至: {output_path}")
        print(f"   裁剪后尺寸: {cropped_image.size[0]}x{cropped_image.size[1]} 像素")
        print(f"   开始压缩图像...")
        
        # 使用压缩保存函数
        save_compressed_image(cropped_image, output_path, max_size_kb=150)


def extract_number_from_filename(filename):
    """
    从文件名中提取数字前缀
    
    Args:
        filename: 文件名
        
    Returns:
        提取的数字前缀字符串，如果未找到数字则返回空字符串
    """
    import re
    
    # 匹配文件名开头的数字
    match = re.match(r'^(\d+)', filename)
    if match:
        return match.group(1)
    else:
        return ""


def get_all_pdf_files(directory):
    """
    获取目录下所有PDF文件
    
    Args:
        directory: 目录路径
        
    Returns:
        PDF文件路径列表
    """
    pdf_files = []
    
    try:
        for file in os.listdir(directory):
            if file.lower().endswith('.pdf'):
                full_path = os.path.join(directory, file)
                pdf_files.append(full_path)
    except Exception as e:
        print(f"❌ 遍历目录时出错: {e}")
    
    return sorted(pdf_files)  # 按文件名排序


def process_single_pdf_dual_output(pdf_path, output_dir_600kb, output_dir_100kb, page_margins, dpi=300):
    """
    处理单个PDF文件，输出两种分辨率的图像
    
    Args:
        pdf_path: PDF文件路径
        output_dir_600kb: 600KB输出目录
        output_dir_100kb: 100KB输出目录
        page_margins: 每页的裁剪阈值
        dpi: 转换分辨率
        
    Returns:
        处理是否成功
    """
    try:
        # 从文件名中提取数字前缀
        filename = os.path.basename(pdf_path)
        number_prefix = extract_number_from_filename(filename)
        
        if not number_prefix:
            print(f"⚠️  无法从文件名 '{filename}' 中提取数字前缀，跳过处理")
            return False
        
        print(f"\n📄 处理PDF文件: {filename}")
        print(f"🔢 提取的数字前缀: {number_prefix}")
        print(f"📁 600KB输出目录: {output_dir_600kb}")
        print(f"📁 100KB输出目录: {output_dir_100kb}")
        
        # 处理PDF，传递双目录参数
        process_pdf_dual_output(pdf_path, output_dir_600kb, output_dir_100kb, page_margins, number_prefix, dpi)
        
        print(f"✅ 成功处理PDF文件: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ 处理PDF文件 '{pdf_path}' 时出错: {e}")
        return False


if __name__ == "__main__":
    # -------------------------- 配置参数 --------------------------
    # PDF文件目录
    PDF_DIR = "dataset"
    
    # 双输出目录配置
    OUTPUT_DIR_600KB = "DRG_model\output\step0-digit-600kb"  # 600-700KB的图像
    OUTPUT_DIR_100KB = "DRG_model\output\step0-discribe-100kb"  # 不大于100KB的图像
    
    # 每页的裁剪阈值 [left, top, right, bottom]，单位：像素
    # 第一页和第二页使用不同的阈值
    PAGE_MARGINS = {
        1: [142, 167, 142, 635],   # 第一页裁剪阈值 左上右下
        2: [248, 148, 248, 635]     # 第二页裁剪阈值
    }
    
    # 转换分辨率
    DPI = 300
    
    # -------------------------- 执行流程 --------------------------
    print("🚀 PDF批量裁剪工具启动（双目录输出）")
    print(f"📁 输入PDF目录: {PDF_DIR}")
    print(f"📁 600KB输出目录: {OUTPUT_DIR_600KB}")
    print(f"📁 100KB输出目录: {OUTPUT_DIR_100KB}")
    print("📝 输出文件命名格式: 数字前缀_page_页码.png")
    
    # 获取所有PDF文件
    pdf_files = get_all_pdf_files(PDF_DIR)
    
    if not pdf_files:
        print("❌ 未找到任何PDF文件")
        exit(1)
    
    print(f"📋 找到 {len(pdf_files)} 个PDF文件:")
    for pdf_file in pdf_files:
        print(f"   - {os.path.basename(pdf_file)}")
    
    # 批量处理PDF文件
    success_count = 0
    error_count = 0
    
    for pdf_path in pdf_files:
        if process_single_pdf_dual_output(pdf_path, OUTPUT_DIR_600KB, OUTPUT_DIR_100KB, PAGE_MARGINS, DPI):
            success_count += 1
        else:
            error_count += 1
    
    # 输出统计信息
    print(f"\n📊 批量处理完成:")
    print(f"✅ 成功处理: {success_count} 个文件")
    print(f"❌ 处理失败: {error_count} 个文件")
    
    if success_count > 0:
        print("\n🎉 批量处理完成!")
        print(f"📁 600KB版本文件保存在: {OUTPUT_DIR_600KB}")
        print(f"📁 100KB版本文件保存在: {OUTPUT_DIR_100KB}")
        print("📝 文件命名示例: 01_page_1.png, 01_page_2.png, 02_page_1.png, ...")
    else:
        print("\n⚠️  所有文件处理失败，请检查配置和文件格式")
