import cv2
import numpy as np
import os

class BoxedDigitDetector:
    def __init__(self, discharge_img_path, gender_img_path, ocr_diag_dir):
        """
        初始化带框数字检测器
        
        参数:
            discharge_img_path: 出院方式图像路径
            gender_img_path: 性别图像路径
            ocr_diag_dir: OCR诊断目录
        """
        # 清空DRG_model\output\step6目录下的所有文件
        # output_dir = "DRG_model/output/step6"
        # for file in os.listdir(output_dir):
        #     file_path = os.path.join(output_dir, file)
        #     try:
        #         if os.path.isfile(file_path):
        #             os.unlink(file_path)
        #             print(f"删除文件: {file_path}")
        #     except Exception as e:
        #         print(f"删除文件 {file_path} 时出错: {e}")

        self.discharge_img_path = discharge_img_path
        self.gender_img_path = gender_img_path
        self.ocr_diag_dir = ocr_diag_dir
    
    def crop_inner_white_region(self, img, border_margin=2):
        """
        去除黑色外边框，仅保留白底数字区域
        
        参数:
            img: 输入图像
            border_margin: 边框边距
            
        返回:
            numpy.ndarray: 去除黑框后的图像，如果未检测到黑框则返回None
        """
        h_img, w_img = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 黑框 -> 白
        _, binary = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        best = None
        best_area = 0

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h

            # 排除小噪声
            if area < 0.1 * w_img * h_img:
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            if len(approx) == 4 and area > best_area:
                best_area = area
                best = (x, y, w, h)

        if best is None:
            return None

        x, y, w, h = best

        # 向内收缩，去掉黑框
        x1 = max(x + border_margin, 0)
        y1 = max(y + border_margin, 0)
        x2 = min(x + w - border_margin, w_img)
        y2 = min(y + h - border_margin, h_img)

        return img[y1:y2, x1:x2]
        
    def _extract_digit_prefix_from_dir(self):
        """
        从ocr_diag_dir中提取数字前缀
        
        返回:
            str: 提取的数字前缀，如果未找到则返回空字符串
        """
        import re
        
        # 检查ocr_diag_dir是否为空
        if not self.ocr_diag_dir:
            print("警告: ocr_diag_dir为空，无法提取数字前缀")
            return ""
            
        # 从目录路径中提取数字前缀
        # 假设ocr_diag_dir格式如: "DRG_model/output/step0-discribe-100kb"
        # 或者目录中包含类似"01_page_1.png"的文件
        
        # 方法1: 从目录名中提取数字
        dir_name = os.path.basename(self.ocr_diag_dir)
        print(f"目录名: {dir_name}")
        
        # 查找目录名中的数字前缀
        match = re.search(r'^(\d+)', dir_name)
        if match:
            digit_prefix = match.group(1)
            print(f"从目录名中提取数字前缀: {digit_prefix}")
            return digit_prefix
            
        # 方法2: 从目录中的文件提取数字前缀
        try:
            # 查找目录中的PNG文件
            png_files = [f for f in os.listdir(self.ocr_diag_dir) if f.lower().endswith('.png')]
            
            if png_files:
                # 取第一个PNG文件
                first_png = png_files[0]
                print(f"找到PNG文件: {first_png}")
                
                # 从文件名中提取数字前缀
                match = re.search(r'^(\d+)', first_png)
                if match:
                    digit_prefix = match.group(1)
                    print(f"从文件名中提取数字前缀: {digit_prefix}")
                    return digit_prefix
        except Exception as e:
            print(f"从文件提取数字前缀时出错: {e}")
            
        # 方法3: 从目录路径中提取数字
        path_parts = self.ocr_diag_dir.split(os.sep)
        for part in path_parts:
            match = re.search(r'^(\d+)', part)
            if match:
                digit_prefix = match.group(1)
                print(f"从路径中提取数字前缀: {digit_prefix}")
                return digit_prefix
                
        print("警告: 无法从ocr_diag_dir中提取数字前缀")
        return ""
        
    def detect_boxed_digits(self, image_path, image_type):
        """
        检测单张图像中的带框数字
        
        参数:
            image_path: 图像路径
            image_type: 图像类型（'discharge' 或 'gender'）
            
        返回:
            str: 检测到的带框数字图像路径
        """
        # 读取图像
        image = cv2.imread(image_path)
        if image is None:
            print(f"无法读取图像: {image_path}")
            return None
            
        # 确保输出目录存在
        self.output_dir = "DRG_model/output/step6"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"创建输出目录: {self.output_dir}")
            
        # 从ocr_diag_dir中提取数字前缀
        # 假设ocr_diag_dir格式如: "DRG_model/output/step0-discribe-100kb"
        # 提取数字前缀，如从"01_page_1.png"中提取"01"
        digit_prefix = self._extract_digit_prefix_from_dir()
        print(f"提取的数字前缀: {digit_prefix}")

        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 高斯模糊，减少噪声
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 二值化处理
        _, binary = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 形态学操作：膨胀和腐蚀，改善轮廓
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # 查找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 矩形度计算函数
        def calculate_rectangularity(contour):
            # 计算轮廓面积
            area = cv2.contourArea(contour)
            if area == 0:
                return 0
            # 计算最小外接矩形
            x, y, w, h = cv2.boundingRect(contour)
            # 计算外接矩形面积
            rect_area = w * h
            # 计算矩形度
            rectangularity = area / rect_area
            return rectangularity

        # 筛选带框数字区域
        boxed_digits = []
        print(f"在{image_type}图像中共找到 {len(contours)} 个轮廓")
        for i, contour in enumerate(contours):
            # 计算矩形度
            rectangularity = calculate_rectangularity(contour)
            # 计算轮廓面积
            area = cv2.contourArea(contour)
            # 计算最小外接矩形
            x, y, w, h = cv2.boundingRect(contour)
            # 计算宽高比
            aspect_ratio = w/h if h > 0 else 0
            
            # 筛选条件：矩形度高、面积适中、宽高比合理
            # 进一步优化，确保只检测到真正的带框数字区域
            if (0.8 < rectangularity < 1.0 and 
                1000 < area < 3000 and 
                0.8 < aspect_ratio < 1.2):
                boxed_digits.append((x, y, w, h))
                print(f"{image_type}图像轮廓 {i+1}: 矩形度={rectangularity:.2f}, 面积={area:.0f}, 宽高比={aspect_ratio:.2f}, 位置=({x},{y},{w},{h}) - 符合条件")
            else:
                print(f"{image_type}图像轮廓 {i+1}: 矩形度={rectangularity:.2f}, 面积={area:.0f}, 宽高比={aspect_ratio:.2f}, 位置=({x},{y},{w},{h}) - 不符合条件")

        # 绘制边界框
        result = image.copy()
        for (x, y, w, h) in boxed_digits:
            cv2.rectangle(result, (x, y), (x+w, y+h), (0, 255, 0), 2)

        # 分割提取带框数字区域
        digit_paths = []
        for i, (x, y, w, h) in enumerate(boxed_digits):
            # 提取区域
            digit_region = image[y:y+h, x:x+w]
            
            # 检查图像尺寸是否过小
            if h < 10 or w < 10:
                print(f"{image_type}带框数字区域 {i+1} 尺寸过小 ({w}x{h})，跳过保存")
                continue
            
            # 去除黑框
            cropped_region = self.crop_inner_white_region(digit_region)
            if cropped_region is not None:
                print(f"{image_type}带框数字区域 {i+1} 成功去除黑框")
                final_region = cropped_region
            else:
                print(f"{image_type}带框数字区域 {i+1} 未检测到黑框，使用原区域")
                final_region = digit_region
                
            # 保存为单独的文件（包含数字前缀）
            if digit_prefix:
                digit_path = f'{self.output_dir}/{digit_prefix}_{image_type}_boxed_digit_{i+1}.png'
            else:
                digit_path = f'{self.output_dir}/{image_type}_boxed_digit_{i+1}.png'
            cv2.imwrite(digit_path, final_region)
            
            # 检查文件大小是否大于1KB
            file_size = os.path.getsize(digit_path)
            file_size_kb = file_size / 1024
            
            if file_size_kb > 1:
                digit_paths.append(digit_path)
                print(f"{image_type}带框数字区域 {i+1} 已保存到: {digit_path} (大小: {file_size_kb:.1f}KB)")
            else:
                # 文件太小，删除该文件
                os.remove(digit_path)
                print(f"{image_type}带框数字区域 {i+1} 文件过小 ({file_size_kb:.1f}KB)，已删除")

        print(f"在{image_type}图像中检测到 {len(boxed_digits)} 个带框数字区域，成功保存 {len(digit_paths)} 个大于1KB的图像")
        
        # 返回第一个检测到的区域路径（如果有的话）
        if digit_paths:
            return digit_paths[0]
        else:
            return None
        
    def run(self):
        """
        执行带框数字检测，处理两张图像
        
        返回:
            tuple: (discharge_digit_path, gender_digit_path)
        """
        print("开始处理出院方式图像...")
        self.discharge_digit_path = self.detect_boxed_digits(self.discharge_img_path, 'discharge')
        
        print("\n开始处理性别图像...")
        self.gender_digit_path = self.detect_boxed_digits(self.gender_img_path, 'gender')
        
        return self.discharge_digit_path, self.gender_digit_path, self.output_dir
        # # 返回检测结果
        # return {
        #     'detected_regions': boxed_digits,
        #     'digit_paths': digit_paths,
        #     'image_path': self.discharge_img_path
        # }


def main():
    """主函数，用于独立运行测试"""
    # 定义图像路径
    discharge_img_path = "DRG_model/output/step5-discharge_method/discharge_method_adjusted_crop.png"
    gender_img_path = "DRG_model/output/step5-gender/gender_adjusted_crop.png"
    step1_ocr_diag_dir = "DRG_model/output/step1/21_page_1.json"
    
    # 创建检测器实例
    detector = BoxedDigitDetector(discharge_img_path, gender_img_path, step1_ocr_diag_dir)
    
    # 执行检测
    discharge_digit_path, gender_digit_path, output_dir = detector.run()
    
    # 输出结果
    print(f"\n检测结果:")
    print(f"出院方式带框数字路径: {discharge_digit_path}")
    print(f"性别带框数字路径: {gender_digit_path}")
    print(f"输出目录: {output_dir}")
    
    return discharge_digit_path, gender_digit_path, output_dir  


if __name__ == "__main__":
    main()