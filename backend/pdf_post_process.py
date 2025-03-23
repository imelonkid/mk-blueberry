#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
import tempfile
import re
from pathlib import Path
from io import BytesIO

# 使用PyPDF2处理PDF
from PyPDF2 import PdfReader, PdfWriter
import PyPDF2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("pdf_post_process")

def remove_slash_marks(input_pdf_path, output_pdf_path):
    """
    尝试使用PyPDF2直接处理PDF内容来去除斜线标记
    
    参数:
        input_pdf_path (str): 输入PDF文件的路径
        output_pdf_path (str): 输出PDF文件的路径
    
    返回:
        bool: 处理成功返回True，否则返回False
    """
    try:
        logger.info(f"开始处理PDF: {input_pdf_path}")
        
        # 读取源PDF
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()
        
        # 处理每一页
        page_count = len(reader.pages)
        logger.info(f"PDF共有 {page_count} 页")
        
        for i in range(page_count):
            page = reader.pages[i]
            logger.info(f"处理第 {i+1}/{page_count} 页")
            
            try:
                # 提取页面文本
                text = page.extract_text()
                if text:
                    # 去除文本中的斜线
                    cleaned_text = remove_slashes(text)
                    
                    # 如果不使用pdf2image和reportlab，我们可以尝试修改页面的内容流
                    # 这是一个实验性功能，可能对某些PDF不起作用
                    try:
                        if hasattr(page, '/Contents'):
                            content_object = page['/Contents']
                            if content_object:
                                # 获取内容流数据
                                if isinstance(content_object, list):
                                    # 如果是内容流数组
                                    for j, obj in enumerate(content_object):
                                        if hasattr(obj, 'get_data'):
                                            data = obj.get_data()
                                            # 替换常见的斜线模式
                                            data = data.replace(b'/', b' ')
                                            data = data.replace(b'\\', b' ')
                                            obj.write(data)
                                else:
                                    # 单个内容流
                                    if hasattr(content_object, 'get_data'):
                                        data = content_object.get_data()
                                        # 替换常见的斜线模式
                                        data = data.replace(b'/', b' ')
                                        data = data.replace(b'\\', b' ')
                                        content_object.write(data)
                    except Exception as e:
                        logger.warning(f"修改内容流时出错: {str(e)}")
            except Exception as e:
                logger.warning(f"处理第 {i+1} 页文本时出错: {str(e)}")
            
            # 将处理后的页面添加到新PDF
            writer.add_page(page)
        
        # 保存处理后的PDF
        logger.info(f"保存处理后的PDF: {output_pdf_path}")
        with open(output_pdf_path, 'wb') as f:
            writer.write(f)
        
        logger.info(f"PDF处理完成，已保存到: {output_pdf_path}")
        logger.warning("注意：当前的斜线去除功能是实验性的，可能对某些PDF文件效果不佳。")
        
        return True
    except Exception as e:
        logger.exception(f"处理PDF时出错: {str(e)}")
        return False

def remove_slashes(text):
    """
    从文本中移除斜线
    """
    # 尝试不同的模式来识别和去除斜线
    # 1. 替换单独的斜线
    text = text.replace(' / ', ' ')
    
    # 2. 替换文本中间的斜线，但保留URL和文件路径中的斜线
    text = re.sub(r'(?<![a-zA-Z0-9])\/(?![a-zA-Z0-9])', ' ', text)
    
    # 3. 替换两个单词之间的斜线
    text = re.sub(r'(\w+)\s*\/\s*(\w+)', r'\1 \2', text)
    
    return text

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python pdf_post_process.py 输入PDF文件 输出PDF文件")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    
    if not os.path.exists(input_pdf):
        print(f"错误: 输入文件 {input_pdf} 不存在")
        sys.exit(1)
    
    success = remove_slash_marks(input_pdf, output_pdf)
    if success:
        print(f"成功: PDF处理完成，已保存到 {output_pdf}")
        sys.exit(0)
    else:
        print("错误: PDF处理失败")
        sys.exit(1) 