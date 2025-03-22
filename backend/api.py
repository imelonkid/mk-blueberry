import os
import json
import tempfile
import uuid
from typing import Dict, Any, List
from flask import Flask, request, jsonify, send_from_directory, send_file, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
import hashlib
import datetime
import shutil
import logging
import argparse
import requests
import time
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from reportlab.lib import colors
import io
import traceback

from pdf_extractor import PDFExtractor, extract_pdf
from translator import Translator

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用跨域请求支持

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 用于存储正在处理的任务
tasks = {}

# 注册思源宋体(用于中文PDF生成)
try:
    # 尝试使用系统中可能存在的中文字体
    search_fonts = [
        '/System/Library/Fonts/PingFang.ttc',  # macOS中文字体
        '/System/Library/Fonts/STHeiti Light.ttc',  # macOS中文字体
        '/usr/share/fonts/truetype/arphic/uming.ttc',  # Ubuntu上的文泉驿字体
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',  # Noto Sans CJK
        'C:\\Windows\\Fonts\\msyh.ttc',  # Windows中的微软雅黑
        'C:\\Windows\\Fonts\\simsun.ttc',  # Windows中的宋体
    ]
    
    registered = False
    for font_path in search_fonts:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                logging.info(f"已注册中文字体: {font_path}")
                registered = True
                break
            except:
                continue
    
    if not registered:
        logging.warning("无法找到系统中的中文字体，将使用默认字体")
except:
    logging.warning("注册中文字体时出错，将使用默认字体")

def allowed_file(filename: str) -> bool:
    """检查文件是否是允许的扩展名"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    # 检查请求中是否有文件
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
        
    file = request.files['file']
    
    # 检查文件名是否为空
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
        
    # 检查文件类型
    if not allowed_file(file.filename):
        return jsonify({'error': f'不支持的文件类型，请上传{", ".join(ALLOWED_EXTENSIONS)}文件'}), 400
    
    # 安全地获取文件名并保存文件
    filename = secure_filename(file.filename)
    task_id = str(uuid.uuid4())
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
    
    try:
        file.save(file_path)
        
        # 提取PDF内容
        pdf_content = extract_pdf(file_path)
        
        # 保存任务信息
        tasks[task_id] = {
            'status': 'completed',
            'file_path': file_path,
            'filename': filename,
            'content': pdf_content
        }
        
        # 返回任务ID和内容摘要
        return jsonify({
            'task_id': task_id,
            'status': 'completed',
            'filename': filename,
            'content_summary': {
                'title': pdf_content.get('content', {}).get('title', '未检测到标题'),
                'total_pages': pdf_content.get('total_pages', 0),
                'has_abstract': bool(pdf_content.get('content', {}).get('abstract', '')),
                'sections_count': len(pdf_content.get('content', {}).get('sections', [])),
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'处理文件时出错: {str(e)}'}), 500


@app.route('/api/content/<task_id>', methods=['GET'])
def get_content(task_id):
    """获取提取的内容"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
        
    task = tasks[task_id]
    
    if task['status'] != 'completed':
        return jsonify({'error': '任务尚未完成', 'status': task['status']}), 400
        
    # 返回任务内容
    return jsonify({
        'task_id': task_id,
        'status': 'completed',
        'filename': task['filename'],
        'content': task['content']
    }), 200


@app.route('/api/translate', methods=['POST'])
def translate_content():
    """翻译内容"""
    data = request.json
    
    # 验证请求数据
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
        
    if 'content' not in data:
        return jsonify({'error': '请求中缺少内容'}), 400
    
    # 获取目标语言，默认为中文
    target_language = data.get('target_language', '中文')
    
    # 获取API密钥
    api_key = data.get('api_key')
    
    # 获取模型提供商和模型名称
    provider = data.get('provider', 'openai')
    model = data.get('model')
    
    # 根据提供商设置默认模型
    if provider.lower() == 'openai' and not model:
        model = 'gpt-3.5-turbo'
    elif provider.lower() == 'deepseek' and not model:
        model = 'deepseek-chat'
    
    # 根据提供商检查必要的API密钥
    if provider.lower() == 'openai':
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': '缺少OpenAI API密钥'}), 400
    elif provider.lower() == 'deepseek':
        if not api_key:
            api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            return jsonify({'error': '缺少DeepSeek API密钥'}), 400
    else:
        return jsonify({'error': f'不支持的提供商: {provider}，目前支持 "openai" 或 "deepseek"'}), 400
    
    try:
        # 初始化翻译器
        translator = Translator(api_key=api_key, model=model, provider=provider)
        
        # 翻译内容
        try:
            translated_content = translator.translate_document(data['content'], target_language)
            
            return jsonify({
                'status': 'completed',
                'translated_content': translated_content
            }), 200
        except Exception as translation_error:
            # 处理翻译过程中的错误
            error_msg = f'翻译过程中出错: {str(translation_error)}'
            if provider.lower() == 'deepseek' and '422' in str(translation_error):
                error_msg += "\n可能原因：DeepSeek API密钥无效或模型名称不正确，请尝试使用'deepseek-chat'"
            
            return jsonify({'error': error_msg}), 400
        
    except Exception as e:
        # 处理初始化翻译器或其他错误
        return jsonify({'error': f'翻译服务初始化出错: {str(e)}'}), 500


@app.route('/api/translate_section', methods=['POST'])
def translate_section():
    """翻译特定段落或章节"""
    data = request.json
    
    # 验证请求数据
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
        
    if 'text' not in data:
        return jsonify({'error': '请求中缺少文本'}), 400
    
    # 获取目标语言，默认为中文
    target_language = data.get('target_language', '中文')
    
    # 获取API密钥
    api_key = data.get('api_key')
    
    # 获取模型提供商和模型名称
    provider = data.get('provider', 'openai')
    model = data.get('model')
    
    # 根据提供商设置默认模型
    if provider.lower() == 'openai' and not model:
        model = 'gpt-3.5-turbo'
    elif provider.lower() == 'deepseek' and not model:
        model = 'deepseek-chat'
    
    # 根据提供商检查必要的API密钥
    if provider.lower() == 'openai':
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': '缺少OpenAI API密钥'}), 400
    elif provider.lower() == 'deepseek':
        if not api_key:
            api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            return jsonify({'error': '缺少DeepSeek API密钥'}), 400
    else:
        return jsonify({'error': f'不支持的提供商: {provider}，目前支持 "openai" 或 "deepseek"'}), 400
    
    try:
        # 初始化翻译器
        translator = Translator(api_key=api_key, model=model, provider=provider)
        
        # 翻译文本
        translated_text = translator.translate_text(data['text'], target_language)
        
        # 检查是否返回了错误信息
        if translated_text.startswith('翻译错误:') or translated_text.startswith('翻译失败:'):
            error_msg = translated_text
            if 'DeepSeek' in provider and '422' in translated_text:
                error_msg += "\n\n可能原因：\n1. DeepSeek API密钥无效或已过期\n2. 所选模型名称不正确，请尝试使用'deepseek-chat'或其他有效的DeepSeek模型\n3. DeepSeek API服务暂时不可用"
            return jsonify({
                'status': 'error',
                'error': error_msg
            }), 400
        
        return jsonify({
            'status': 'completed',
            'original': data['text'],
            'translated': translated_text
        }), 200
        
    except Exception as e:
        error_msg = f'翻译时出错: {str(e)}'
        return jsonify({'error': error_msg}), 500


@app.route('/api/files/<task_id>', methods=['GET'])
def get_file(task_id):
    """获取上传的文件"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
        
    task = tasks[task_id]
    
    # 发送文件，允许在浏览器中直接显示
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        os.path.basename(task['file_path']),
        as_attachment=False,
        mimetype='application/pdf'
    )


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取所有任务"""
    task_list = []
    
    for task_id, task in tasks.items():
        task_list.append({
            'task_id': task_id,
            'status': task['status'],
            'filename': task['filename'],
            'content_summary': {
                'title': task.get('content', {}).get('content', {}).get('title', '未检测到标题'),
                'total_pages': task.get('content', {}).get('total_pages', 0),
                'has_abstract': bool(task.get('content', {}).get('content', {}).get('abstract', '')),
                'sections_count': len(task.get('content', {}).get('content', {}).get('sections', [])),
            } if task['status'] == 'completed' else {}
        })
    
    return jsonify({'tasks': task_list}), 200


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'ok'}), 200


@app.route('/api/recent_files', methods=['GET'])
def get_recent_files():
    """获取最近上传的文件列表"""
    try:
        files = []
        # 遍历上传目录
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.endswith('.pdf') or '_' in filename and filename.split('_', 1)[1].endswith('.pdf'):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                # 获取文件信息
                stat_info = os.stat(file_path)
                # 创建文件对象
                task_id = filename.split('_')[0] if '_' in filename else 'unknown'
                original_name = filename.split('_', 1)[1] if '_' in filename else filename
                
                files.append({
                    'task_id': task_id,
                    'filename': original_name,
                    'full_path': file_path,
                    'size': stat_info.st_size,
                    'created_time': stat_info.st_ctime,
                    'modified_time': stat_info.st_mtime
                })
        
        # 按修改时间排序（最新的在前）
        files.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'files': files[:10]  # 只返回最新的10个文件
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取文件列表失败: {str(e)}'}), 500


@app.route('/api/latest_file', methods=['GET'])
def get_latest_file():
    """获取最新上传的文件内容"""
    try:
        files = []
        # 遍历上传目录
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.endswith('.pdf') or '_' in filename and filename.split('_', 1)[1].endswith('.pdf'):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                # 获取文件信息
                stat_info = os.stat(file_path)
                # 创建文件对象
                task_id = filename.split('_')[0] if '_' in filename else None
                
                if task_id and task_id != 'unknown':
                    files.append({
                        'task_id': task_id,
                        'filename': filename,
                        'full_path': file_path,
                        'modified_time': stat_info.st_mtime
                    })
        
        if not files:
            return jsonify({'error': '没有找到文件'}), 404
            
        # 按修改时间排序（最新的在前）
        files.sort(key=lambda x: x['modified_time'], reverse=True)
        latest_file = files[0]
        
        # 检查该文件是否已经在任务列表中
        if latest_file['task_id'] in tasks:
            task = tasks[latest_file['task_id']]
            return jsonify({
                'task_id': latest_file['task_id'],
                'status': 'completed',
                'filename': task['filename'],
                'content': task['content']
            }), 200
        else:
            # 如果不在，则提取PDF内容
            try:
                pdf_content = extract_pdf(latest_file['full_path'])
                
                # 保存任务信息
                tasks[latest_file['task_id']] = {
                    'status': 'completed',
                    'file_path': latest_file['full_path'],
                    'filename': latest_file['filename'].split('_', 1)[1] if '_' in latest_file['filename'] else latest_file['filename'],
                    'content': pdf_content
                }
                
                return jsonify({
                    'task_id': latest_file['task_id'],
                    'status': 'completed',
                    'filename': tasks[latest_file['task_id']]['filename'],
                    'content': pdf_content
                }), 200
            except Exception as e:
                return jsonify({'error': f'处理文件时出错: {str(e)}'}), 500
                
    except Exception as e:
        return jsonify({'error': f'获取最新文件失败: {str(e)}'}), 500


@app.route('/api/translate_document', methods=['POST'])
def translate_document():
    """
    翻译文档API
    
    请求体:
    {
        "task_id": "任务ID",
        "provider": "API提供商，例如openai、deepseek等",
        "model": "模型名称，例如gpt-4、deepseek-chat等",
        "api_key": "API密钥（可选，如未提供则使用环境变量）"
    }
    
    返回:
    {
        "success": true/false,
        "message": "成功或错误消息",
        "pdf_url": "PDF文件URL"（如果成功）
    }
    """
    try:
        # 获取请求数据
        data = request.get_json()
        
        # 验证请求数据
        if not data:
            return jsonify({
                'success': False,
                'message': '无效的请求数据'
            }), 400
            
        # 提取请求参数
        task_id = data.get('task_id')
        provider = data.get('provider', 'deepseek')  # 默认使用deepseek
        model = data.get('model')
        api_key = data.get('api_key')
        
        # 检查任务ID
        if not task_id:
            return jsonify({
                'success': False,
                'message': '缺少任务ID'
            }), 400
            
        # 检查任务是否存在
        if task_id not in tasks:
            return jsonify({
                'success': False,
                'message': f'任务 {task_id} 不存在'
            }), 404
            
        # 检查API密钥
        if not api_key:
            # 尝试从环境变量获取API密钥
            if provider.lower() == 'deepseek':
                api_key = os.environ.get('DEEPSEEK_API_KEY')
                if not api_key:
                    logging.warning("未提供DeepSeek API密钥，也未在环境变量中找到")
            elif provider.lower() == 'openai':
                api_key = os.environ.get('OPENAI_API_KEY')
                if not api_key:
                    logging.warning("未提供OpenAI API密钥，也未在环境变量中找到")
                    
        # 设置默认模型（如果未提供）
        if not model:
            if provider.lower() == 'deepseek':
                model = 'deepseek-chat'
            elif provider.lower() == 'openai':
                model = 'gpt-3.5-turbo'
        
        # 先检查任务是否已翻译过
        tasks_dir = os.path.join(os.path.dirname(__file__), 'tasks')
        task_dir = os.path.join(tasks_dir, task_id)
        translated_dir = os.path.join(task_dir, 'translated')
        
        if os.path.exists(translated_dir):
            translation_file = os.path.join(translated_dir, 'translation.json')
            
            if os.path.exists(translation_file):
                logging.info(f"任务 {task_id} 已翻译过，直接返回翻译结果")
                
                # 查找翻译目录中的PDF文件
                pdf_files = [f for f in os.listdir(translated_dir) if f.endswith('.pdf')]
                
                if pdf_files:
                    pdf_file = pdf_files[0]  # 使用第一个找到的PDF文件
                    pdf_url = f"/api/translated_files/{task_id}/{pdf_file}"
                    logging.info(f"已找到翻译后的PDF文件: {pdf_file}")
                    
                    return jsonify({
                        'success': True,
                        'message': '文档已翻译过，直接返回结果',
                        'pdf_url': pdf_url
                    })
                else:
                    # 有翻译文件但没有PDF，需要重新生成PDF
                    logging.info(f"找到翻译文件但未找到PDF，正在生成PDF")
                    
                    # 读取已有的翻译内容
                    with open(translation_file, 'r', encoding='utf-8') as f:
                        translated_content = json.load(f)
                    
                    # 获取原始内容
                    task_data = tasks[task_id]
                    original_content = task_data.get('content', {})
                    content_structure = original_content.get('content', {})
                    if not content_structure:
                        content_structure = original_content
                    
                    # 重新生成PDF
                    try:
                        pdf_path = generate_translated_pdf(content_structure, translated_content, task_dir)
                        pdf_filename = os.path.basename(pdf_path)
                        pdf_url = f"/api/translated_files/{task_id}/{pdf_filename}"
                        
                        logging.info(f"PDF生成成功: {pdf_path}")
                        return jsonify({
                            'success': True,
                            'message': '使用已有翻译内容生成PDF成功',
                            'pdf_url': pdf_url
                        })
                    except Exception as e:
                        logging.error(f"重新生成PDF失败: {str(e)}", exc_info=True)
                        return jsonify({
                            'success': False,
                            'message': f'重新生成PDF失败: {str(e)}'
                        }), 500
        
        # 如果没有找到翻译文件，继续执行翻译流程
        logging.info(f"未找到翻译文件，开始翻译任务: {task_id}")
        
        # 创建任务目录
        tasks_dir = os.path.join(os.path.dirname(__file__), 'tasks')
        task_dir = os.path.join(tasks_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 获取文档内容
        task_data = tasks[task_id]
        logging.info(f"任务数据类型: {type(task_data)}")
        
        # 深入检查content内容结构
        original_content = task_data.get('content', {})
        logging.info(f"原始内容键: {original_content.keys() if isinstance(original_content, dict) else '非字典类型'}")
        
        # 获取内容结构
        content_structure = original_content.get('content', {})
        if not content_structure:
            logging.warning("找不到content.content结构，尝试使用顶层内容")
            content_structure = original_content
            
        logging.info(f"内容结构键: {content_structure.keys() if isinstance(content_structure, dict) else '非字典类型'}")
        
        # 准备翻译内容
        translated_content = {
            'title': '',
            'abstract': '',
            'sections': []
        }
        
        # 标题可能在content.content.title或content.title
        title_text = ""
        if isinstance(content_structure, dict) and content_structure.get('title'):
            title_text = content_structure.get('title')
        elif isinstance(original_content, dict) and original_content.get('title'):
            title_text = original_content.get('title')
            
        # 摘要可能在content.content.abstract或content.abstract
        abstract_text = ""
        if isinstance(content_structure, dict) and content_structure.get('abstract'):
            abstract_text = content_structure.get('abstract')
        elif isinstance(original_content, dict) and original_content.get('abstract'):
            abstract_text = original_content.get('abstract')
            
        # 章节可能在content.content.sections或content.sections
        sections = []
        if isinstance(content_structure, dict) and content_structure.get('sections'):
            sections = content_structure.get('sections')
        elif isinstance(original_content, dict) and original_content.get('sections'):
            sections = original_content.get('sections')
            
        logging.info(f"找到标题: {bool(title_text)}, 摘要: {bool(abstract_text)}, 章节数: {len(sections)}")
        
        # 翻译标题
        if title_text:
            try:
                logging.info(f"翻译标题: {title_text[:50]}...")
                translated_title = translate_text(
                    title_text,
                    provider,
                    api_key,
                    model,
                    "将以下论文标题翻译成中文，保持学术风格："
                )
                translated_content['title'] = translated_title
                logging.info(f"翻译标题成功: {translated_title[:30]}...")
            except Exception as e:
                logging.error(f"翻译标题失败: {str(e)}", exc_info=True)
                translated_content['title'] = "标题翻译失败"
        
        # 翻译摘要
        if abstract_text:
            try:
                logging.info(f"翻译摘要: {abstract_text[:50]}...")
                translated_abstract = translate_text(
                    abstract_text,
                    provider,
                    api_key,
                    model,
                    "将以下论文摘要翻译成中文，保持学术风格和术语准确性："
                )
                translated_content['abstract'] = translated_abstract
                logging.info(f"翻译摘要成功: {translated_abstract[:30]}...")
            except Exception as e:
                logging.error(f"翻译摘要失败: {str(e)}", exc_info=True)
                translated_content['abstract'] = "摘要翻译失败"
        
        # 翻译章节
        for i, section in enumerate(sections):
            try:
                # 创建翻译后的章节
                translated_section = {
                    'title': '',
                    'content': []
                }
                
                # 提取章节标题和内容
                section_title = section.get('title', f"章节 {i+1}")
                section_content = section.get('content', [])
                
                logging.info(f"翻译章节 {i+1}: {section_title}, 段落数: {len(section_content)}")
                
                # 翻译章节标题
                try:
                    translated_title = translate_text(
                        section_title,
                        provider,
                        api_key,
                        model,
                        "将以下论文章节标题翻译成中文，保持专业术语准确性："
                    )
                    translated_section['title'] = translated_title
                    logging.info(f"翻译章节标题成功: {translated_title}")
                except Exception as e:
                    logging.error(f"翻译章节标题失败: {str(e)}", exc_info=True)
                    translated_section['title'] = f"章节 {i+1}"
                
                # 翻译章节内容
                for j, paragraph in enumerate(section_content):
                    if paragraph and isinstance(paragraph, str) and paragraph.strip():
                        try:
                            logging.info(f"翻译段落 {j+1}, 长度: {len(paragraph)}")
                            translated_paragraph = translate_text(
                                paragraph,
                                provider,
                                api_key,
                                model,
                                "将以下学术段落翻译成中文，保持学术风格和术语准确性："
                            )
                            translated_section['content'].append(translated_paragraph)
                            logging.info(f"翻译段落 {j+1} 成功")
                        except Exception as e:
                            logging.error(f"翻译段落失败: {str(e)}", exc_info=True)
                            translated_section['content'].append(f"段落 {j+1} 翻译失败")
                
                # 添加翻译后的章节
                translated_content['sections'].append(translated_section)
                logging.info(f"章节 {i+1} 翻译完成")
                
            except Exception as e:
                logging.error(f"处理章节 {i+1} 失败: {str(e)}", exc_info=True)
                # 添加错误章节
                translated_content['sections'].append({
                    'title': f'章节 {i+1} 处理失败',
                    'content': ['出现错误，无法翻译此章节']
                })
        
        # 如果没有任何内容，添加默认内容
        if not translated_content['title'] and not translated_content['abstract'] and not translated_content['sections']:
            logging.warning("没有找到可翻译的内容，添加默认内容")
            translated_content['title'] = "未能提取出原文内容"
            translated_content['abstract'] = "系统无法从PDF中提取有效内容进行翻译。请确认PDF格式正确且包含可提取的文本。"
            translated_content['sections'] = [{
                'title': '无法翻译',
                'content': ['系统无法从PDF中提取有效内容进行翻译。这可能是因为PDF是扫描件或文本不可提取。']
            }]
        
        # 保存翻译结果
        translated_dir = os.path.join(task_dir, 'translated')
        os.makedirs(translated_dir, exist_ok=True)
        
        translation_file = os.path.join(translated_dir, 'translation.json')
        with open(translation_file, 'w', encoding='utf-8') as f:
            json.dump(translated_content, f, ensure_ascii=False, indent=2)
        
        logging.info(f"翻译结果已保存到: {translation_file}")
        
        # 生成PDF
        try:
            logging.info("开始生成PDF")
            pdf_path = generate_translated_pdf(content_structure, translated_content, task_dir)
            pdf_filename = os.path.basename(pdf_path)
            pdf_url = f"/api/translated_files/{task_id}/{pdf_filename}"
            
            logging.info(f"PDF生成成功: {pdf_path}")
            return jsonify({
                'success': True,
                'message': '文档翻译成功',
                'pdf_url': pdf_url
            })
        except Exception as e:
            logging.error(f"生成PDF失败: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'翻译成功但生成PDF失败: {str(e)}'
            }), 500
        
    except Exception as e:
        logging.error(f"文档翻译过程出错: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'翻译过程出错: {str(e)}'
        }), 500

@app.route('/api/check_translation/<task_id>', methods=['GET'])
def check_translation(task_id):
    """
    检查指定任务ID是否已翻译过
    
    返回:
        JSON对象，包含翻译状态和PDF URL（如果已翻译）
    """
    try:
        tasks_dir = os.path.join(os.path.dirname(__file__), 'tasks')
        task_dir = os.path.join(tasks_dir, task_id)
        translated_dir = os.path.join(task_dir, 'translated')
        
        # 检查任务ID是否有效
        if not os.path.exists(task_dir):
            logging.warning(f"任务目录不存在: {task_dir}")
            return jsonify({
                'success': False,
                'translated': False,
                'message': f'任务 {task_id} 不存在'
            })
        
        # 检查是否有翻译目录和翻译文件
        if os.path.exists(translated_dir):
            translation_file = os.path.join(translated_dir, 'translation.json')
            
            if os.path.exists(translation_file):
                logging.info(f"找到翻译文件: {translation_file}")
                
                # 查找翻译目录中的PDF文件
                pdf_files = [f for f in os.listdir(translated_dir) if f.endswith('.pdf')]
                
                if pdf_files:
                    pdf_file = pdf_files[0]  # 使用第一个找到的PDF文件
                    pdf_url = f"/api/translated_files/{task_id}/{pdf_file}"
                    logging.info(f"已找到翻译后的PDF文件: {pdf_file}")
                    
                    return jsonify({
                        'success': True,
                        'translated': True,
                        'message': '已找到翻译文件',
                        'pdf_url': pdf_url
                    })
                else:
                    # 有翻译文件但没有PDF，可能需要重新生成PDF
                    logging.warning(f"找到翻译文件但未找到PDF: {translation_file}")
                    return jsonify({
                        'success': True,
                        'translated': True,
                        'message': '找到翻译文件但未找到PDF文件，需要重新生成PDF',
                        'needs_pdf_generation': True
                    })
        
        # 没有找到翻译文件
        logging.info(f"任务 {task_id} 未翻译过")
        return jsonify({
            'success': True,
            'translated': False,
            'message': '未找到翻译文件'
        })
    
    except Exception as e:
        logging.error(f"检查翻译状态出错: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'translated': False,
            'message': f'检查翻译状态出错: {str(e)}'
        }), 500

def translate_text(text, provider, api_key, model=None, system_prompt=None):
    """
    翻译文本内容
    
    参数:
        text: 要翻译的文本
        provider: 服务提供商(openai或deepseek)
        api_key: API密钥
        model: 模型名称
        system_prompt: 系统提示词
        
    返回:
        翻译后的文本
    """
    if not text or not text.strip():
        return ""
    
    logging.info(f"翻译文本，长度: {len(text)}, 提供商: {provider}, 模型: {model}")
    
    # 测试模式 - 直接模拟翻译结果
    if api_key == 'sk-test':
        logging.info("使用测试模式，返回模拟翻译")
        # 简单模拟翻译
        if len(text) > 100:
            return f"[测试模式] 这是原文的模拟翻译结果。原文长度: {len(text)}字符。"
        else:
            # 对于短文本，添加一些简单的模拟翻译
            return f"[测试翻译] {text[:30]}..."
    
    # 正常模式 - 使用实际API
    try:
        if provider.lower() == 'openai':
            return translate_with_openai(text, api_key, model, system_prompt)
        elif provider.lower() == 'deepseek':
            return translate_with_deepseek(text, api_key, model, system_prompt)
        else:
            raise ValueError(f"不支持的服务提供商: {provider}")
    except Exception as e:
        logging.error(f"翻译文本失败: {str(e)}", exc_info=True)
        raise

def translate_with_openai(text, api_key, model=None, system_prompt=None):
    """使用OpenAI API翻译文本"""
    if not model:
        model = "gpt-3.5-turbo"
        
    try:
        import openai
        openai.api_key = api_key
        
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": "你是一个专业的学术翻译助手，请将以下内容翻译成中文，保持学术风格和术语准确性。"})
            
        # 添加用户消息
        messages.append({"role": "user", "content": text})
        
        # 发起请求
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=4000
        )
        
        translated_text = response.choices[0].message.content.strip()
        return translated_text
        
    except Exception as e:
        logging.error(f"OpenAI翻译失败: {str(e)}", exc_info=True)
        raise

def translate_with_deepseek(text, api_key, model=None, system_prompt=None):
    """使用DeepSeek API翻译文本"""
    if not model:
        model = "deepseek-chat"
        
    try:
        url = "https://api.deepseek.com/v1/chat/completions"
        
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": "你是一个专业的学术翻译助手，请将以下内容翻译成中文，保持学术风格和术语准确性。"})
            
        # 添加用户消息
        messages.append({"role": "user", "content": text})
        
        # 构建请求体
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        # 发起请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 检查请求是否成功
        
        result = response.json()
        translated_text = result['choices'][0]['message']['content'].strip()
        return translated_text
        
    except Exception as e:
        logging.error(f"DeepSeek翻译失败: {str(e)}", exc_info=True)
        raise

def generate_translated_pdf(original_content, translated_content, task_dir):
    """
    根据翻译内容生成PDF
    """
    try:
        # 创建存放翻译PDF的目录
        translated_dir = os.path.join(task_dir, 'translated')
        os.makedirs(translated_dir, exist_ok=True)
        
        # PDF文件路径
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(translated_dir, f"translated_{timestamp}.pdf")
        
        # 创建PDF文档
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # 创建样式
        styles = getSampleStyleSheet()
        
        # 自定义样式
        # 使用已注册的中文字体，如果没有则使用默认字体
        font_name = 'ChineseFont' if 'ChineseFont' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        logging.info(f"PDF生成使用字体: {font_name}")
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontName=font_name,
            fontSize=14,
            leading=18,
            spaceAfter=10
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=font_name,
            fontSize=12,
            leading=16,
            spaceAfter=8
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            firstLineIndent=20,
            spaceAfter=6
        )
        
        abstract_style = ParagraphStyle(
            'CustomAbstract',
            parent=normal_style,
            fontName=font_name,
            fontSize=10,
            firstLineIndent=0,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=6,
            spaceAfter=10
        )
        
        # 构建PDF内容
        elements = []
        
        # 检查是否有翻译内容，如果没有，则添加默认内容
        if not translated_content.get('title') and not translated_content.get('abstract') and not (translated_content.get('sections') and len(translated_content.get('sections')) > 0):
            logging.warning("翻译内容为空，添加默认内容")
            elements.append(Paragraph("翻译内容为空或未成功翻译", title_style))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("请重试翻译过程", normal_style))
            
            # 添加模拟内容以生成更长的PDF
            elements.append(Spacer(1, 24))
            elements.append(Paragraph("可能的原因", heading_style))
            elements.append(Paragraph("1. 文档内容提取失败 - PDF可能是扫描件或格式不支持", normal_style))
            elements.append(Paragraph("2. 翻译服务暂时不可用 - 请稍后再试", normal_style))
            elements.append(Paragraph("3. API密钥配置错误 - 请检查环境变量或输入的API密钥", normal_style))
        else:
            # 添加标题
            if translated_content.get('title'):
                try:
                    elements.append(Paragraph(translated_content['title'], title_style))
                    elements.append(Spacer(1, 12))
                except Exception as e:
                    logging.error(f"添加标题时出错: {str(e)}")
                    elements.append(Paragraph("标题处理错误", title_style))
            
            # 提取原始元数据
            meta = {}
            if original_content and isinstance(original_content, dict) and original_content.get('metadata'):
                meta = original_content.get('metadata', {})
            
            # 作者信息
            if meta.get('author'):
                try:
                    author_text = f"作者: {meta.get('author')}"
                    elements.append(Paragraph(author_text, subtitle_style))
                    elements.append(Spacer(1, 6))
                except Exception as e:
                    logging.error(f"添加作者信息时出错: {str(e)}")
                
            # 期刊信息
            if meta.get('subject'):
                try:
                    journal_text = f"期刊: {meta.get('subject')}"
                    elements.append(Paragraph(journal_text, subtitle_style))
                    elements.append(Spacer(1, 6))
                except Exception as e:
                    logging.error(f"添加期刊信息时出错: {str(e)}")
            
            # 添加摘要
            if translated_content.get('abstract'):
                try:
                    elements.append(Paragraph("摘要", heading_style))
                    elements.append(Paragraph(translated_content['abstract'], abstract_style))
                    elements.append(Spacer(1, 12))
                except Exception as e:
                    logging.error(f"添加摘要时出错: {str(e)}")
                    elements.append(Paragraph("摘要处理错误", heading_style))
            
            # 添加章节
            for section in translated_content.get('sections', []):
                try:
                    # 章节标题
                    if section.get('title'):
                        elements.append(Paragraph(section['title'], heading_style))
                    
                    # 章节内容
                    if not section.get('content') or len(section['content']) == 0:
                        elements.append(Paragraph("本章节无内容或翻译失败", normal_style))
                    else:
                        for paragraph in section.get('content', []):
                            if paragraph and isinstance(paragraph, str) and paragraph.strip():
                                try:
                                    elements.append(Paragraph(paragraph, normal_style))
                                except Exception as para_err:
                                    logging.error(f"处理段落时出错: {str(para_err)}")
                                    elements.append(Paragraph("段落处理错误", normal_style))
                            elif isinstance(paragraph, dict) and paragraph.get('translated'):
                                try:
                                    elements.append(Paragraph(paragraph['translated'], normal_style))
                                except Exception as para_err:
                                    logging.error(f"处理翻译段落时出错: {str(para_err)}")
                                    elements.append(Paragraph("段落处理错误", normal_style))
                    
                    elements.append(Spacer(1, 12))
                except Exception as section_err:
                    logging.error(f"处理章节时出错: {str(section_err)}")
                    elements.append(Paragraph("章节处理错误", heading_style))
                    elements.append(Spacer(1, 12))
        
        # 构建PDF
        logging.info(f"开始构建PDF: {pdf_path}")
        try:
            doc.build(elements)
            logging.info(f"PDF构建成功: {pdf_path}")
            
            # 验证生成的文件
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                logging.info(f"生成的PDF大小: {file_size} 字节")
                if file_size == 0:
                    logging.error("生成的PDF文件大小为0")
                    raise Exception("生成的PDF文件大小为0")
            else:
                logging.error("PDF文件未生成")
                raise Exception("PDF文件未生成")
                
            return pdf_path
            
        except Exception as pdf_err:
            logging.error(f"构建PDF时出错: {str(pdf_err)}", exc_info=True)
            
            # 尝试生成一个超简单的PDF作为备用
            try:
                logging.info("尝试生成备用简单PDF")
                c = canvas.Canvas(pdf_path, pagesize=letter)
                c.setFont("Helvetica", 12)
                c.drawString(72, 700, "翻译PDF生成失败，请重试。")
                c.drawString(72, 680, f"错误信息: {str(pdf_err)}")
                c.drawString(72, 660, "时间戳: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                c.save()
                
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    logging.info("备用PDF生成成功")
                    return pdf_path
                else:
                    raise Exception("备用PDF生成失败")
            except Exception as backup_err:
                logging.error(f"生成备用PDF时出错: {str(backup_err)}")
                raise
        
    except Exception as e:
        logging.error(f"生成PDF出错: {str(e)}", exc_info=True)
        raise

@app.route('/api/translated_files/<task_id>/<filename>', methods=['GET'])
def get_translated_file(task_id, filename):
    """
    获取翻译后的PDF文件
    """
    try:
        # 修改文件路径，从tasks目录中获取而不是UPLOAD_FOLDER
        tasks_dir = os.path.join(os.path.dirname(__file__), 'tasks')
        task_dir = os.path.join(tasks_dir, task_id)
        translated_dir = os.path.join(task_dir, 'translated')
        file_path = os.path.join(translated_dir, filename)
        
        logging.info(f"请求翻译文件: {task_id}/{filename}")
        logging.info(f"查找文件路径: {file_path}")
        
        if not os.path.exists(task_dir):
            logging.error(f"任务目录不存在: {task_dir}")
            return jsonify({
                'success': False,
                'message': f'任务 {task_id} 不存在'
            }), 404
            
        if not os.path.exists(translated_dir):
            logging.error(f"翻译目录不存在: {translated_dir}")
            
            # 尝试列出任务目录中的内容
            try:
                task_contents = os.listdir(task_dir)
                logging.info(f"任务目录内容: {task_contents}")
            except Exception as e:
                logging.error(f"无法列出任务目录内容: {str(e)}")
            
            return jsonify({
                'success': False,
                'message': f'任务 {task_id} 的翻译目录不存在'
            }), 404
            
        if not os.path.exists(file_path):
            logging.error(f"文件不存在: {file_path}")
            
            # 尝试列出翻译目录中的内容
            try:
                translated_contents = os.listdir(translated_dir)
                logging.info(f"翻译目录内容: {translated_contents}")
            except Exception as e:
                logging.error(f"无法列出翻译目录内容: {str(e)}")
                
            return jsonify({
                'success': False,
                'message': f'文件 {filename} 不存在'
            }), 404
            
        # 返回文件，设置正确的MIME类型和不下载标志
        logging.info(f"发送文件: {file_path}")
        response = send_file(file_path, mimetype='application/pdf', as_attachment=False)
        
        # 添加缓存控制头，防止浏览器缓存
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    except Exception as e:
        logging.error(f"获取翻译文件出错: {str(e)}", exc_info=True)
        abort(500, description=f"获取文件失败: {str(e)}")

if __name__ == '__main__':
    import argparse
    import sys
    
    # 配置参数解析
    parser = argparse.ArgumentParser(description='论文翻译后端服务')
    parser.add_argument('--port', type=int, default=5001, help='服务端口号')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='服务主机地址')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('paper_translator.log')
        ]
    )
    
    # 输出配置信息
    logging.info(f"启动论文翻译后端服务")
    logging.info(f"主机: {args.host}, 端口: {args.port}, 调试模式: {args.debug}")
    
    # 环境变量检查
    openai_key = os.environ.get('OPENAI_API_KEY')
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
    logging.info(f"OPENAI_API_KEY: {'已设置' if openai_key else '未设置'}")
    logging.info(f"DEEPSEEK_API_KEY: {'已设置' if deepseek_key else '未设置'}")
    
    # 创建必要的目录
    os.makedirs('tasks', exist_ok=True)
    
    # 启动应用
    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except Exception as e:
        logging.error(f"启动服务失败: {str(e)}", exc_info=True)
        sys.exit(1) 