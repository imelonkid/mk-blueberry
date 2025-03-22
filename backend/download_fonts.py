#!/usr/bin/env python3
"""
下载思源宋体字体文件，用于PDF生成
"""

import os
import requests
import shutil
import zipfile
import io
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 思源宋体下载链接 (简体中文版)
FONT_URL = "https://github.com/adobe-fonts/source-han-serif/releases/download/2.001R/SourceHanSerifCN.zip"

# 目标目录
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

def main():
    # 确保字体目录存在
    os.makedirs(FONT_DIR, exist_ok=True)
    
    # 检查字体文件是否已存在
    target_file = os.path.join(FONT_DIR, "SourceHanSerifCN-Regular.otf")
    if os.path.exists(target_file):
        logging.info(f"字体文件已存在: {target_file}")
        return
    
    try:
        # 下载字体文件
        logging.info(f"开始下载思源宋体字体: {FONT_URL}")
        response = requests.get(FONT_URL, stream=True)
        
        if response.status_code != 200:
            logging.error(f"下载失败，HTTP状态码: {response.status_code}")
            return
        
        # 解压缩字体文件
        logging.info("下载完成，开始解压缩")
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            for file_info in z.infolist():
                # 只提取Regular字重的字体文件
                if "Regular" in file_info.filename and file_info.filename.endswith(".otf"):
                    logging.info(f"提取字体文件: {file_info.filename}")
                    
                    # 重命名为标准文件名
                    with z.open(file_info) as source, open(target_file, "wb") as target:
                        shutil.copyfileobj(source, target)
                    
                    logging.info(f"字体文件已保存到: {target_file}")
                    break
        
        # 验证文件是否存在
        if not os.path.exists(target_file):
            logging.error("字体文件未成功提取")
            return
        
        logging.info("字体文件已成功下载并解压")
        
    except Exception as e:
        logging.error(f"下载或解压字体时出错: {str(e)}")
        
if __name__ == "__main__":
    main() 