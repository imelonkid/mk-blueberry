import os
import fitz  # PyMuPDF
import json
from typing import Dict, List, Any, Tuple
import io
from PIL import Image as PILImage
import logging
import re

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
        将文本分割成段落，更智能地处理段落结构
        
        参数:
            text: 要分割的文本
            
        返回:
            段落列表
        """
        # 预处理：规范化换行符
        text = text.replace('\r\n', '\n')
        
        # 按可能的段落分隔符分割
        raw_paragraphs = []
        
        # 尝试使用连续两个换行符分割
        if '\n\n' in text:
            raw_paragraphs = text.split('\n\n')
        else:
            # 如果没有连续的换行符，尝试使用单个换行符分割，但更加谨慎
            lines = text.split('\n')
            current_paragraph = []
            
            for line in lines:
                stripped_line = line.strip()
                # 如果是空行，且已经收集了一些内容，则完成当前段落
                if not stripped_line and current_paragraph:
                    raw_paragraphs.append('\n'.join(current_paragraph))
                    current_paragraph = []
                # 如果是新段落的开始标志（缩进或特殊符号开头）
                elif (stripped_line and current_paragraph and 
                      (stripped_line[0].isdigit() and '.' in stripped_line[:5]) or  # 编号项
                       stripped_line.startswith('•') or                             # 项目符号
                       (len(stripped_line) > 30 and                                 # 较长的行，可能是新段落
                        not any(marker in stripped_line.lower() for marker in ['fig.', 'table', 'fig ', 'tab.']))): 
                    # 完成当前段落并开始新段落
                    if current_paragraph:
                        raw_paragraphs.append('\n'.join(current_paragraph))
                    current_paragraph = [stripped_line]
                elif stripped_line:
                    # 将行添加到当前段落
                    current_paragraph.append(stripped_line)
            
            # 添加最后一个段落
            if current_paragraph:
                raw_paragraphs.append('\n'.join(current_paragraph))
        
        # 后处理：清理段落并过滤无意义的短行
        processed_paragraphs = []
        for para in raw_paragraphs:
            # 清理段落文本
            para = para.strip()
            
            # 跳过空段落
            if not para:
                continue
                
            # 跳过可能是页眉、页脚或其他无意义内容的特别短的行
            if len(para) < 5:
                continue
                
            # 处理可能的列表项（如多行显示的技术参数或表格行）
            # 这里我们认为除了章节标题外，有意义的段落通常有一定长度
            if len(para) < 15 and not any(marker in para.lower() for marker in [
                "introduction", "background", "methodology", "results", 
                "discussion", "conclusion", "references", "引言", "方法", 
                "结果", "讨论", "结论", "参考文献", "abstract", "摘要"
            ]):
                # 检查是否像是列表项
                if para[0].isdigit() or para.startswith('•') or para.startswith('-'):
                    # 这是列表项，保留
                    processed_paragraphs.append(para)
                # 不合并超短段落，因为可能导致结构混乱
                continue
                
            # 添加有效段落
            processed_paragraphs.append(para)
        
        # 智能合并可能属于同一段落但被错误分割的部分
        merged_paragraphs = []
        i = 0
        while i < len(processed_paragraphs):
            current = processed_paragraphs[i]
            
            # 判断当前段落是否应该和下一段合并
            if i + 1 < len(processed_paragraphs):
                next_para = processed_paragraphs[i + 1]
                
                # 如果当前段落不以句号、问号或感叹号结尾，且下一段不是以大写字母开头
                # 或者当前段落非常短，可能是被错误分割的
                if ((not current[-1] in '.!?:;"\'') and 
                    (not next_para[0].isupper() or len(current) < 50) and
                    not any(marker in current.lower() for marker in [
                        "introduction", "abstract", "摘要", "chapter"
                    ])):
                    # 合并段落
                    merged_paragraphs.append(current + ' ' + next_para)
                    i += 2  # 跳过下一段
                    continue
            
            merged_paragraphs.append(current)
            i += 1
        
        # 最后的清理和过滤
        final_paragraphs = []
        for para in merged_paragraphs:
            # 再次清理
            para = para.strip()
            
            # 规范化空白字符
            para = ' '.join(para.split())
            
            if para:
                final_paragraphs.append(para)
        
        return final_paragraphs
    
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
            
            if paragraphs and len(paragraphs) > 0:
                # 智能处理标题
                # 1. 首先检查是否存在红框中指示的标题模式（arxiv格式常见）
                title_found = False
                
                # 遍历前几段看是否有明显的标题特征
                for i, para in enumerate(paragraphs[:5]): 
                    # 查找文本中可能的标题（通常是较短的独立行，后面可能跟着作者信息）
                    if len(para) < 200 and (
                        # 检查是否有典型的标题前的文本特征
                        (i > 0 and ("proceedings" in paragraphs[i-1].lower() or 
                                   "journal" in paragraphs[i-1].lower() or
                                   "conference" in paragraphs[i-1].lower() or
                                   "symposium" in paragraphs[i-1].lower())) or
                        # 或者直接是标题样式（不带作者等其他信息的短文本）
                        (10 < len(para) < 150 and 
                         not any(marker in para.lower() for marker in ["abstract", "introduction", "university", "department", "doi", "©"]) and
                         not para.startswith('1') and not para.startswith('I.') and
                         not para[0].isdigit() and
                         not para.count('\n') > 2)
                    ):
                        content["title"] = para
                        title_found = True
                        logging.info(f"检测到可能的标题: {para[:50]}...")
                        break
                
                # 2. 如果没有找到明显的标题，尝试更智能的标题提取
                if not title_found:
                    raw_first_para = paragraphs[0]
                    
                    # 检查是否是arxiv格式论文（包含很长的元数据在一段中）
                    if len(raw_first_para) > 200 and '\n' in raw_first_para:
                        # 尝试从多行的第一段中提取标题
                        lines = raw_first_para.split('\n')
                        potential_title = ""
                        
                        # 寻找可能的标题行
                        for line_index, line in enumerate(lines):
                            if 10 < len(line) < 150 and line_index < 10:
                                # 如果是第一行或紧跟在会议名称/期刊名称之后的行
                                if line_index == 0 or any(marker in lines[line_index-1].lower() for marker in ["proceedings", "journal", "symposium"]):
                                    potential_title = line
                                    break
                                # 如果看起来像标题（全部是大小写单词开头，不含特殊字符）
                                if all(word[0].isupper() for word in line.split() if len(word) > 3) and '(' not in line and ')' not in line:
                                    potential_title = line
                                    break
                        
                        if potential_title:
                            content["title"] = potential_title
                            title_found = True
                            logging.info(f"从多行段落中提取到标题: {potential_title}")
                        else:
                            # 尝试查找"The"开头的行，这通常是论文的开始
                            for line_index, line in enumerate(lines):
                                if line.strip().startswith("The ") and len(line) > 15 and line_index < 15:
                                    content["title"] = line
                                    title_found = True
                                    logging.info(f"发现以'The'开头的可能标题: {line}")
                                    break
                    
                # 3. 如果仍然没找到标题，使用第一段作为标题（最后的回退方案）
                if not title_found:
                    # 使用最传统的方法：取第一段作为标题
                    content["title"] = paragraphs[0]
                    logging.info(f"使用第一段作为标题: {paragraphs[0][:50]}...")
                
                # 寻找Abstract或摘要段落
                abstract_found = False
                for i, para in enumerate(paragraphs[1:6], 1):  # 只在前几段寻找摘要
                    if "abstract" in para.lower() or "摘要" in para:
                        # 假设摘要是下一段，但需验证它足够长
                        if i + 1 < len(paragraphs) and len(paragraphs[i + 1]) > 30:
                            content["abstract"] = paragraphs[i + 1]
                            abstract_found = True
                            logging.info(f"找到摘要: {paragraphs[i + 1][:50]}...")
                            break
                
                # 如果没有找到明确的摘要标记，但第二段看起来像摘要（较长的段落）
                if not abstract_found and len(paragraphs) > 1 and len(paragraphs[1]) > 150:
                    content["abstract"] = paragraphs[1]
                    logging.info(f"使用第二段作为摘要: {paragraphs[1][:50]}...")
        
        # 收集所有段落，用于后续处理
        all_paragraphs = []
        for page in pages_content:
            all_paragraphs.extend(page["paragraphs"])
        
        # 从标题和摘要之后开始处理章节
        start_index = 0
        # 跳过标题
        while start_index < len(all_paragraphs) and all_paragraphs[start_index] != content["title"]:
            start_index += 1
        if start_index < len(all_paragraphs):
            start_index += 1  # 跳过标题本身
        
        # 跳过摘要
        if content["abstract"]:
            while start_index < len(all_paragraphs) and all_paragraphs[start_index] != content["abstract"]:
                start_index += 1
            if start_index < len(all_paragraphs):
                start_index += 1  # 跳过摘要本身
        
        # 尝试识别文档结构（章节）
        sections = []
        current_section = {"title": "", "content": []}
        
        # 章节编号模式
        section_number_patterns = [
            r"^\d+\.\s",                # "1. "
            r"^[IVXivx]+\.\s",          # "I. ", "IV. "
            r"^\d+\.\d+\.\s",           # "1.1. "
            r"^Chapter\s+\d+\s*[:\.]*\s", # "Chapter 1: ", "Chapter 2."
            r"^Section\s+\d+\s*[:\.]*\s", # "Section 1: ", "Section 2."
        ]
        
        # 常见章节标题关键词
        section_keywords = [
            "introduction", "abstract", "background", "methodology", "methods", 
            "results", "discussion", "conclusion", "conclusions", "references", 
            "acknowledgment", "acknowledgments", "acknowledgements", "experimental", 
            "materials", "algorithm", "implementation", "evaluation", "related work",
            "future work", "implications", "limitations", "procedure", "experiment",
            "case study", "analysis", "appendix", "supplement", "figure", "table",
            "引言", "摘要", "背景", "方法", "结果", "讨论", "结论", "参考文献", 
            "致谢", "实验", "材料", "算法", "实现", "评估", "相关工作", "未来工作"
        ]
        
        # 记录已识别的章节标题，防止重复
        seen_section_titles = set()
        
        # 开始处理正文部分
        in_references_section = False  # 标记是否在参考文献部分
        
        for i, para in enumerate(all_paragraphs[start_index:], start_index):
            para_text = para.strip()
            
            # 跳过过短的段落（可能是页眉页脚或其他噪声）
            if len(para_text) < 5:
                continue
            
            # 检查是否为新章节标题
            is_section_title = False
            
            # 判断依据1：段落较短，且包含章节编号模式
            if len(para_text) < 100:
                for pattern in section_number_patterns:
                    if re.match(pattern, para_text):
                        is_section_title = True
                        break
            
            # 判断依据2：段落较短，且完全由章节关键词组成（如"Introduction"）
            if not is_section_title and len(para_text) < 50:
                words = para_text.lower().split()
                main_word = words[0] if words else ""
                
                # 检查是否是常见章节标题关键词
                if main_word in section_keywords or para_text.lower() in section_keywords:
                    is_section_title = True
                
                # 特殊检查：数字开头且后面跟着关键词（如"1 Introduction"）
                elif len(words) > 1 and words[0].isdigit() and words[1] in section_keywords:
                    is_section_title = True
            
            # 判断依据3：在参考文献之后，且以数字和方括号或圆括号开头（[1], (1)等）可能是参考文献项
            if not is_section_title and (re.match(r"^\[\d+\]", para_text) or re.match(r"^\(\d+\)", para_text)):
                if in_references_section:
                    # 这可能是一个参考文献条目，将其添加到当前章节
                    current_section["content"].append(para_text)
                    continue
            
            # 如果是章节标题
            if is_section_title:
                # 如果已经有一个活动的章节，将其保存
                if current_section["title"] and len(current_section["content"]) > 0:
                    sections.append(current_section)
                
                # 检查是否重复章节标题
                if para_text in seen_section_titles:
                    # 这可能是误判，将其作为普通段落添加到当前章节
                    if current_section["title"]:
                        current_section["content"].append(para_text)
                    continue
                
                # 标记为已见过的章节标题
                seen_section_titles.add(para_text)
                
                # 创建新章节
                current_section = {"title": para_text, "content": []}
                
                # 检查是否进入参考文献部分
                if "reference" in para_text.lower() or "参考文献" in para_text:
                    in_references_section = True
            else:
                # 不是章节标题，添加到当前章节内容
                if current_section["title"]:
                    current_section["content"].append(para_text)
                else:
                    # 如果还没有章节标题，创建一个默认章节
                    current_section = {"title": "Introduction", "content": [para_text]}
        
        # 添加最后一个章节
        if current_section["title"] and len(current_section["content"]) > 0:
            sections.append(current_section)
        
        # 如果没有识别出任何章节，创建一个默认章节
        if len(sections) == 0:
            # 收集所有不是标题和摘要的段落
            default_content = []
            skip_indices = {i for i, p in enumerate(all_paragraphs) if p in [content["title"], content["abstract"]]}
            
            for i, para in enumerate(all_paragraphs):
                if i not in skip_indices and para.strip():
                    default_content.append(para)
            
            if default_content:
                sections.append({
                    "title": "Content",
                    "content": default_content
                })
        
        # 设置到结果中
        content["sections"] = sections
        
        # 记录提取结果
        logging.info(f"提取结构化内容: 标题='{ content['title'][:30]}...', 摘要长度={len(content['abstract'])}, 章节数={len(content['sections'])}")
        for i, section in enumerate(content["sections"]):
            logging.info(f"  章节{i+1}: 标题='{section['title'][:30]}...', 段落数={len(section['content'])}")
        
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
        提取PDF文档中的图片，使用增强的方法确保捕获所有图像
        
        参数:
            output_dir: 图片保存的目录
        
        返回:
            保存的图片文件路径列表
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        image_paths = []
        
        # 方法1：使用get_images提取嵌入图像
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
                    logging.info(f"提取嵌入图片: {image_path}")
                except Exception as e:
                    logging.error(f"提取嵌入图片时出错: {e}")
        
        # 方法2：直接渲染页面为图像，提取可能的图形内容
        if len(image_paths) == 0:
            logging.info("未找到嵌入图像，尝试渲染页面为图像")
            try:
                for page_num in range(self.total_pages):
                    page = self.pdf_document.load_page(page_num)
                    
                    # 渲染页面为图像
                    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # 使用更高分辨率
                    
                    # 保存为PNG
                    image_filename = f"{os.path.basename(self.pdf_path)}_page{page_num+1}_full.png"
                    image_path = os.path.join(output_dir, image_filename)
                    
                    pix.save(image_path)
                    image_paths.append(image_path)
                    logging.info(f"渲染页面为图像: {image_path}")
                    
            except Exception as e:
                logging.error(f"渲染页面为图像时出错: {e}")
        
        return image_paths
    
    def extract_layout(self) -> List[Dict[str, Any]]:
        """
        提取PDF的布局结构，包括文本块、图像位置和表格
        
        返回:
            包含布局结构的字典列表，每页一个字典
        """
        layout = []
        
        for page_num in range(self.total_pages):
            page = self.pdf_document.load_page(page_num)
            
            # 提取页面布局
            blocks = page.get_text("dict")["blocks"]
            
            # 构建页面布局信息
            page_layout = {
                "page_num": page_num + 1,
                "width": page.rect.width,
                "height": page.rect.height,
                "blocks": []
            }
            
            # 处理每个块
            for block in blocks:
                block_type = block.get("type", 0)
                
                if block_type == 0:  # 文本块
                    lines = []
                    for line in block.get("lines", []):
                        line_text = ""
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                        
                        if line_text.strip():
                            lines.append({
                                "text": line_text,
                                "bbox": line.get("bbox", [0, 0, 0, 0]),
                                "font": span.get("font", ""),
                                "size": span.get("size", 0)
                            })
                    
                    if lines:
                        page_layout["blocks"].append({
                            "type": "text",
                            "bbox": block.get("bbox", [0, 0, 0, 0]),
                            "lines": lines
                        })
                
                elif block_type == 1:  # 图像块
                    page_layout["blocks"].append({
                        "type": "image",
                        "bbox": block.get("bbox", [0, 0, 0, 0]),
                        "image_idx": len(page_layout["blocks"])
                    })
            
            layout.append(page_layout)
        
        return layout
    
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
            "total_pages": self.total_pages,
            "layout": self.extract_layout()
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