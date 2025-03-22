import os
import fitz  # PyMuPDF
import json
from typing import Dict, List, Any, Tuple

class PDFExtractor:
    def __init__(self, pdf_path: str):
        """
        初始化PDF提取器
        
        参数:
            pdf_path: PDF文件路径
        """
        self.pdf_path = pdf_path
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        # 打开PDF文件
        try:
            self.pdf_document = fitz.open(pdf_path)
            self.total_pages = len(self.pdf_document)
        except Exception as e:
            raise Exception(f"无法打开PDF文件: {e}")
    
    def extract_text_by_pages(self) -> List[Dict[str, Any]]:
        """
        提取PDF文档的文本内容，按页组织
        
        返回:
            包含每页文本内容的字典列表
        """
        result = []
        
        for page_num in range(self.total_pages):
            page = self.pdf_document.load_page(page_num)
            text = page.get_text("text")
            
            # 将文本按段落分割
            paragraphs = self._split_into_paragraphs(text)
            
            page_data = {
                "page_num": page_num + 1,
                "paragraphs": paragraphs
            }
            
            result.append(page_data)
            
        return result
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        将文本分割成段落
        
        参数:
            text: 要分割的文本
            
        返回:
            段落列表
        """
        # 按照连续的换行符分割文本
        paragraphs = []
        raw_paragraphs = text.split('\n\n')
        
        for para in raw_paragraphs:
            # 去除前后空白
            para = para.strip()
            if para:  # 只添加非空段落
                paragraphs.append(para)
        
        return paragraphs
    
    def extract_structured_content(self) -> Dict[str, Any]:
        """
        提取PDF的结构化内容，包括标题、摘要和正文
        
        返回:
            包含结构化内容的字典
        """
        content = {
            "title": "",
            "abstract": "",
            "sections": []
        }
        
        # 提取所有页面的文本
        pages_content = self.extract_text_by_pages()
        
        # 尝试提取标题和摘要（通常在第一页）
        if pages_content:
            first_page = pages_content[0]
            paragraphs = first_page["paragraphs"]
            
            if paragraphs:
                # 假设第一段是标题
                content["title"] = paragraphs[0]
                
                # 寻找Abstract或摘要段落
                for i, para in enumerate(paragraphs[1:], 1):
                    if "abstract" in para.lower() or "摘要" in para:
                        # 假设摘要是下一段
                        if i + 1 < len(paragraphs):
                            content["abstract"] = paragraphs[i + 1]
                            break
        
        # 尝试识别文档结构（章节）
        section = {"title": "", "content": []}
        
        for page in pages_content:
            for para in page["paragraphs"]:
                # 判断是否是章节标题
                # 章节标题通常较短，可能包含数字和特定单词
                if len(para) < 100 and ("." in para[:10] or 
                                        any(keyword in para.lower() 
                                            for keyword in ["introduction", "background", "methodology", 
                                                            "results", "discussion", "conclusion", 
                                                            "references", "引言", "方法", "结果", "讨论", 
                                                           "结论", "参考文献"])):
                    # 保存之前的章节
                    if section["title"]:
                        content["sections"].append(section)
                    
                    # 开始新章节
                    section = {"title": para, "content": []}
                else:
                    # 添加内容到当前章节
                    if section["title"]:
                        section["content"].append(para)
        
        # 添加最后一个章节
        if section["title"]:
            content["sections"].append(section)
        
        return content
    
    def extract_metadata(self) -> Dict[str, Any]:
        """
        提取PDF文档的元数据
        
        返回:
            包含元数据的字典
        """
        metadata = {}
        
        if hasattr(self.pdf_document, 'metadata'):
            doc_info = self.pdf_document.metadata
            
            if doc_info:
                # 提取一些常见的元数据字段
                fields = ['title', 'author', 'subject', 'keywords', 'creator', 'producer', 'creation_date', 'modification_date']
                
                for field in fields:
                    if field in doc_info:
                        metadata[field] = doc_info[field]
        
        return metadata
    
    def extract_images(self, output_dir: str) -> List[str]:
        """
        提取PDF文档中的图片
        
        参数:
            output_dir: 图片保存的目录
        
        返回:
            保存的图片文件路径列表
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        image_paths = []
        
        for page_num in range(self.total_pages):
            page = self.pdf_document.load_page(page_num)
            
            # 获取页面上的图片
            image_list = page.get_images(full=True)
            
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]  # 图片的xref
                
                try:
                    base_image = self.pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # 确定图片格式
                    image_ext = base_image["ext"]
                    
                    # 保存图片
                    image_filename = f"{os.path.basename(self.pdf_path)}_page{page_num+1}_img{img_index+1}.{image_ext}"
                    image_path = os.path.join(output_dir, image_filename)
                    
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                        
                    image_paths.append(image_path)
                except Exception as e:
                    print(f"提取图片时出错: {e}")
        
        return image_paths
    
    def close(self):
        """关闭PDF文档"""
        if hasattr(self, 'pdf_document'):
            self.pdf_document.close()
    
    def get_document_structure(self) -> Dict[str, Any]:
        """
        获取完整的文档结构，包括元数据、内容和组织
        
        返回:
            包含完整文档结构的字典
        """
        result = {
            "metadata": self.extract_metadata(),
            "content": self.extract_structured_content(),
            "total_pages": self.total_pages
        }
        
        return result
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def extract_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    提取PDF文件的内容
    
    参数:
        pdf_path: PDF文件路径
        
    返回:
        包含PDF内容的字典
    """
    with PDFExtractor(pdf_path) as extractor:
        result = extractor.get_document_structure()
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python pdf_extractor.py <pdf文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    try:
        result = extract_pdf(pdf_path)
        
        # 将结果输出为JSON格式
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1) 