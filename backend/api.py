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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
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
        "translation": { 翻译后的内容 }, // 修改为直接返回翻译内容，而不是PDF URL
        "original": { 原始内容 } // 添加原始内容方便前端显示双栏对照
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
                
                # 读取已有的翻译内容
                with open(translation_file, 'r', encoding='utf-8') as f:
                    translated_content = json.load(f)
                
                # 获取原始内容
                task_data = tasks[task_id]
                original_content = task_data.get('content', {})
                content_structure = original_content.get('content', {})
                if not content_structure:
                    content_structure = original_content
                
                # 返回翻译结果和原始内容，以便前端显示双栏对照
                return jsonify({
                    'success': True,
                    'message': '文档已翻译过，直接返回结果',
                    'translation': translated_content,
                    'original': content_structure
                })
        
        # 如果没有找到翻译文件，继续执行翻译流程
        logging.info(f"未找到翻译文件，开始翻译任务: {task_id}")
        
        # 创建任务目录
        tasks_dir = os.path.join(os.path.dirname(__file__), 'tasks')
        task_dir = os.path.join(tasks_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 获取文档内容
        task_data = tasks[task_id]
        logging.info(f"任务数据类型: {type(task_data)}")
        
        # 复制原始PDF文件到任务目录中
        original_pdf_path = task_data.get('file_path')
        if original_pdf_path and os.path.exists(original_pdf_path):
            logging.info(f"找到原始PDF文件: {original_pdf_path}")
            pdf_filename = os.path.basename(original_pdf_path).split('_', 1)[1] if '_' in os.path.basename(original_pdf_path) else os.path.basename(original_pdf_path)
            new_pdf_path = os.path.join(task_dir, pdf_filename)
            
            # 如果任务目录中还没有此PDF，则复制
            if not os.path.exists(new_pdf_path):
                try:
                    shutil.copy2(original_pdf_path, new_pdf_path)
                    original_pdf_path = new_pdf_path
                    logging.info(f"已将原始PDF文件从上传目录复制到任务目录: {new_pdf_path}")
                except Exception as copy_err:
                    logging.error(f"复制PDF文件时出错: {str(copy_err)}", exc_info=True)
        else:
            logging.warning(f"未找到原始PDF文件或文件路径无效: {original_pdf_path}")
            
        # 深入检查content内容结构
        original_content = task_data.get('content', {})
        logging.info(f"原始内容键: {original_content.keys() if isinstance(original_content, dict) else '非字典类型'}")
        
        # 获取内容结构
        content_structure = original_content.get('content', {})
        if not content_structure:
            content_structure = original_content
            
        # 检查内容结构
        if not content_structure:
            return jsonify({
                'success': False,
                'message': '无法提取PDF内容结构'
            }), 400
            
        # 检查是否已有提取的标题、摘要和章节
        title = content_structure.get('title', '')
        abstract = content_structure.get('abstract', '')
        sections = content_structure.get('sections', [])
        
        logging.info(f"提取的内容: 标题长度={len(title)}, 摘要长度={len(abstract)}, 章节数={len(sections)}")
        
        if not title and not abstract and not sections:
            logging.warning("没有提取到任何内容，无法进行翻译")
            return jsonify({
                'success': False,
                'message': '无法从PDF中提取有效内容进行翻译'
            }), 400
            
        # 确定是否为测试模式
        is_test_mode = False
        if api_key and api_key.startswith('sk-test'):
            is_test_mode = True
            logging.warning("检测到测试API密钥，将使用测试模式")
            
        # 准备翻译结果
        translated_content = {
            'title': '',
            'abstract': '',
            'sections': []
        }
        
        # 创建翻译目录
        translated_dir = os.path.join(task_dir, 'translated')
        os.makedirs(translated_dir, exist_ok=True)
        
        # 准备翻译器
        from translator import Translator
        translator = Translator(provider=provider, model=model, api_key=api_key)
        
        try:
            # 翻译标题
            if title:
                # 先检查缓存
                cached_title = get_cached_translation(title, provider, model)
                if cached_title:
                    logging.info(f"从缓存获取标题翻译: {cached_title[:50]}...")
                    translated_title = cached_title
                else:
                    # 直接使用translate_text函数（内部已实现缓存优先）
                    logging.info(f"开始翻译标题: {title[:50]}...")
                    translated_title = translate_text(title, provider, api_key, model)
                    logging.info(f"标题翻译完成: {translated_title[:50]}...")
                
                translated_content['title'] = translated_title
            
            # 翻译摘要
            if abstract:
                # 先检查缓存
                cached_abstract = get_cached_translation(abstract, provider, model)
                if cached_abstract:
                    logging.info(f"从缓存获取摘要翻译: {cached_abstract[:50]}...")
                    translated_abstract = cached_abstract
                else:
                    # 直接使用translate_text函数（内部已实现缓存优先）
                    logging.info(f"开始翻译摘要: {abstract[:50]}...")
                    translated_abstract = translate_text(abstract, provider, api_key, model)
                    logging.info(f"摘要翻译完成: {translated_abstract[:50]}...")
                
                translated_content['abstract'] = translated_abstract
            
            # 翻译章节 - 使用缓存优先翻译
            has_translation_errors = False
            for section in sections:
                section_title = section.get('title', '')
                section_content = section.get('content', [])
                
                logging.info(f"处理章节: {section_title[:30]}... (内容段落数: {len(section_content)})")
                
                translated_section = {
                    'title': '',
                    'content': []
                }
                
                # 翻译章节标题
                if section_title:
                    # 先检查缓存
                    cached_section_title = get_cached_translation(section_title, provider, model)
                    if cached_section_title:
                        logging.info(f"从缓存获取章节标题翻译: {cached_section_title}")
                        translated_section_title = cached_section_title
                    else:
                        # 直接使用translate_text函数（内部已实现缓存优先）
                        logging.info(f"翻译章节标题: {section_title}")
                        translated_section_title = translate_text(section_title, provider, api_key, model)
                        logging.info(f"章节标题翻译完成: {translated_section_title}")
                    
                    translated_section['title'] = translated_section_title
                
                # 翻译章节内容 - 使用缓存优先
                translated_paragraphs = []
                for paragraph in section_content:
                    if not paragraph or not isinstance(paragraph, str):
                        translated_paragraphs.append('')
                        continue
                    
                    # 跳过空内容
                    if paragraph.strip() == '':
                        translated_paragraphs.append('')
                        continue
                    
                    # 先检查缓存
                    cached_para = get_cached_translation(paragraph, provider, model)
                    if cached_para:
                        logging.info(f"从缓存获取段落翻译，原文长度: {len(paragraph)}，翻译长度: {len(cached_para)}")
                        translated_paragraphs.append(cached_para)
                    else:
                        try:
                            # 直接使用translate_text函数（内部已实现缓存优先）
                            logging.info(f"翻译段落，长度: {len(paragraph)}")
                            translated_para = translate_text(paragraph, provider, api_key, model)
                            logging.info(f"段落翻译完成，翻译长度: {len(translated_para)}")
                            translated_paragraphs.append(translated_para)
                        except Exception as para_err:
                            logging.error(f"翻译段落失败: {str(para_err)}", exc_info=True)
                            translated_paragraphs.append(f"[翻译错误: {str(para_err)}]")
                            has_translation_errors = True
                
                translated_section['content'] = translated_paragraphs
                translated_content['sections'].append(translated_section)
            
            # 设置状态消息
            status_message = '文档翻译成功'
            if has_translation_errors:
                status_message = '文档翻译部分成功，有些段落翻译失败'
            
            # 保存翻译结果
            translation_file = os.path.join(translated_dir, 'translation.json')
            with open(translation_file, 'w', encoding='utf-8') as f:
                json.dump(translated_content, f, ensure_ascii=False, indent=2)
            
            logging.info(f"翻译结果已保存到: {translation_file}")
            
            # 提取原始PDF中的图片，供前端使用
            images_dir = os.path.join(translated_dir, 'images')
            os.makedirs(images_dir, exist_ok=True)
            
            # 从原始PDF中提取图片
            images = []
            if original_pdf_path and os.path.exists(original_pdf_path):
                try:
                    # 尝试提取图片
                    import fitz  # PyMuPDF
                    doc = fitz.open(original_pdf_path)
                    
                    for page_idx, page in enumerate(doc):
                        try:
                            image_list = page.get_images(full=True)
                            for img_idx, img in enumerate(image_list):
                                xref = img[0]
                                if xref > 0:
                                    try:
                                        pix = fitz.Pixmap(doc, xref)
                                        img_filename = f"image_p{page_idx+1}_{img_idx+1}.png"
                                        img_path = os.path.join(images_dir, img_filename)
                                        pix.save(img_path)
                                        
                                        # 记录图片信息
                                        images.append({
                                            "filename": img_filename,
                                            "page": page_idx + 1,
                                            "index": img_idx + 1,
                                            "url": f"/api/translated_files/{task_id}/images/{img_filename}"
                                        })
                                    except Exception as img_err:
                                        logging.error(f"保存图片失败: {str(img_err)}")
                        except Exception as page_err:
                            logging.error(f"处理页面 {page_idx+1} 上的图片时出错: {str(page_err)}")
                            
                    doc.close()
                    logging.info(f"从PDF中提取了 {len(images)} 张图片")
                except Exception as extract_err:
                    logging.error(f"提取图片时出错: {str(extract_err)}")
            
            # 返回翻译内容和原始内容，支持双栏对照显示
            return jsonify({
                'success': True,
                'message': status_message,
                'translation': translated_content,
                'original': content_structure,
                'images': images  # 返回提取的图片信息
            })
            
        except Exception as e:
            logging.error(f"翻译过程中出错: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'翻译过程中出错: {str(e)}'
            }), 500
    
    except Exception as e:
        logging.error(f"翻译文档时出错: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'翻译文档时出错: {str(e)}'
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

def generate_translated_pdf_with_original_layout(original_pdf_path, original_content, translated_content, output_pdf_path):
    """
    使用PyMuPDF直接生成翻译后的PDF文件，将英文内容替换为中文翻译
    
    参数:
    - original_pdf_path: 原始PDF路径
    - original_content: 原始文档内容
    - translated_content: 翻译内容
    - output_pdf_path: 输出的PDF路径
    
    返回:
    - 生成的PDF路径
    """
    try:
        import fitz  # PyMuPDF
        
        # 打开原始PDF
        logging.info(f"打开原始PDF: {original_pdf_path}")
        doc = fitz.open(original_pdf_path)
        
        # 提取翻译内容
        title = translated_content.get('title', '')
        abstract = translated_content.get('abstract', '')
        sections = translated_content.get('sections', [])
        
        logging.info(f"翻译标题: '{title[:50]}...'")
        logging.info(f"翻译摘要: '{abstract[:50]}...'")
        logging.info(f"翻译章节数: {len(sections)}")
        
        # 检查是否有翻译内容
        if not title and not abstract and len(sections) == 0:
            logging.warning("未找到有效的翻译内容，将使用备用方法生成PDF")
            return generate_simple_translated_pdf(translated_content, output_pdf_path)
        
        # 使用安全的内置字体，确保可以在任何系统上运行
        font_name = "helv"  # Helvetica是PyMuPDF中的内置字体
        logging.info(f"使用字体: {font_name}")
        
        # 创建新的PDF文档
        new_doc = fitz.open()
        
        # 为每一页创建翻译版本
        logging.info(f"原始PDF有 {len(doc)} 页")
        
        # 处理第一页 - 转换标题和摘要
        if len(doc) > 0:
            # 复制第一页
            new_doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
            first_page = new_doc[0]
            
            # 设置背景为白色
            first_page.draw_rect(first_page.rect, color=(1, 1, 1), fill=(1, 1, 1))
            
            # 绘制标题
            if title:
                # 居中显示标题 - 计算文本宽度并居中
                text_width = 7 * len(title)  # 简单估算文本宽度
                x_pos = (first_page.rect.width - text_width) / 2
                if x_pos < 72:
                    x_pos = 72  # 最小左边距
                first_page.insert_text(
                    fitz.Point(x_pos, 100),
                    title,
                    fontsize=16,
                    color=(0, 0, 0),
                    fontname=font_name
                )
            
            # 绘制日期和作者信息
            if doc[0].get_text():
                meta_text = "翻译版本 - " + datetime.datetime.now().strftime("%Y-%m-%d")
                first_page.insert_text(
                    fitz.Point(first_page.rect.width-150, 50),
                    meta_text,
                    fontsize=10,
                    color=(0.5, 0.5, 0.5),
                    fontname=font_name
                )
            
            # 绘制摘要
            if abstract:
                first_page.insert_text(
                    fitz.Point(72, 150),
                    "摘要:",
                    fontsize=14,
                    color=(0, 0, 0),
                    fontname=font_name
                )
                
                # 创建摘要文本框
                abstract_rect = fitz.Rect(72, 170, first_page.rect.width-72, 350)
                # 移除不兼容的align参数，使用默认对齐
                text_height = first_page.insert_textbox(
                    abstract_rect,
                    abstract,
                    fontsize=12,
                    color=(0, 0, 0),
                    fontname=font_name
                )
        
        # 处理翻译章节
        y_pos = 380  # 初始Y位置
        current_page = 0
        
        for section_idx, section in enumerate(sections):
            section_title = section.get('title', '')
            section_content = section.get('content', [])
            
            # 如果当前页空间不足，创建新页面
            if y_pos > new_doc[current_page].rect.height - 100:
                current_page = len(new_doc)
                new_doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
                new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))  # 白色背景
                y_pos = 72  # 重置Y位置
            
            # 绘制章节标题
            if section_title:
                # 确保当前页有足够空间
                if y_pos > new_doc[current_page].rect.height - 150:
                    current_page = len(new_doc)
                    new_doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
                    new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))  # 白色背景
                    y_pos = 72  # 重置Y位置
                
                new_doc[current_page].insert_text(
                    fitz.Point(72, y_pos),
                    section_title,
                    fontsize=14,
                    color=(0, 0, 0),
                    fontname=font_name
                )
                y_pos += 25
            
            # 绘制章节内容
            for para in section_content:
                if not para or not isinstance(para, str):
                    continue
                
                # 确保当前页有足够空间
                if y_pos > new_doc[current_page].rect.height - 120:
                    current_page = len(new_doc)
                    new_doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
                    new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))  # 白色背景
                    y_pos = 72  # 重置Y位置
                
                # 创建段落文本框
                para_rect = fitz.Rect(72, y_pos, new_doc[current_page].rect.width-72, y_pos + 300)
                # 移除不兼容的align参数
                text_height = new_doc[current_page].insert_textbox(
                    para_rect,
                    para,
                    fontsize=12,
                    color=(0, 0, 0),
                    fontname=font_name
                )
                
                if text_height < 0:  # 文本太长，没有完全放入
                    # 创建新页面并继续
                    current_page = len(new_doc)
                    new_doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
                    new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))  # 白色背景
                    y_pos = 72
                    
                    # 尝试在新页面继续
                    para_rect = fitz.Rect(72, y_pos, new_doc[current_page].rect.width-72, y_pos + 300)
                    text_height = new_doc[current_page].insert_textbox(
                        para_rect,
                        para,
                        fontsize=12,
                        color=(0, 0, 0),
                        fontname=font_name
                    )
                    y_pos += abs(text_height) + 15
                else:
                    y_pos += abs(text_height) + 15
            
            # 章节之间添加一些空间
            y_pos += 20
        
        # 尝试复制原文PDF中的图片
        try:
            # 从原始PDF提取图片
            image_list = []
            for i, page in enumerate(doc):
                try:
                    page_images = page.get_images(full=True)
                    image_list.extend(page_images)
                except Exception as e:
                    logging.error(f"从页面 {i+1} 提取图片时出错: {str(e)}")
                
            if image_list:
                logging.info(f"从原始PDF中提取了 {len(image_list)} 个图片对象")
                
                # 添加图片页面
                if len(new_doc) > 0:
                    current_page = len(new_doc)
                    new_doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
                    new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))
                    
                    # 添加图片标题 - 居中显示
                    image_title = "原文图片"
                    # 计算文本宽度并居中
                    text_width = 7 * len(image_title)  # 简单估算
                    x_pos = (new_doc[current_page].rect.width - text_width) / 2
                    if x_pos < 72:
                        x_pos = 72  # 最小左边距
                    new_doc[current_page].insert_text(
                        fitz.Point(x_pos, 72),
                        image_title,
                        fontsize=16,
                        color=(0, 0, 0),
                        fontname=font_name
                    )
                    
                    y_pos = 100
                    added_images = 0
                    
                    # 遍历图片
                    for img in image_list[:4]:  # 限制为前4张图片
                        try:
                            xref = img[0]
                            if xref >= 0:
                                # 获取图片信息
                                pix = fitz.Pixmap(doc, xref)
                                
                                # 调整图片大小 - 使用兼容方式
                                max_width = new_doc[current_page].rect.width - 144  # 左右各72点余量
                                if pix.width > max_width:
                                    scale = max_width / pix.width
                                    # 使用更安全的图像处理方法
                                    try:
                                        # 简化图像处理逻辑，避免使用可能导致clip参数错误的方法
                                        # 不进行缩放，仅控制插入图像的矩形大小
                                        scaled_width = int(pix.width * scale)
                                        scaled_height = int(pix.height * scale)
                                        # 不处理图像，只记录尺寸
                                        logging.info(f"使用图像原始尺寸 {pix.width}x{pix.height}，显示尺寸 {scaled_width}x{scaled_height}")
                                    except Exception as scale_err:
                                        logging.error(f"处理图像尺寸时出错: {str(scale_err)}")
                                        scaled_width = pix.width
                                        scaled_height = pix.height
                                else:
                                    scaled_width = pix.width
                                    scaled_height = pix.height
                                
                                # 如果页面空间不足，创建新页面
                                if y_pos + scaled_height > new_doc[current_page].rect.height - 72:
                                    current_page = len(new_doc)
                                    new_doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
                                    new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))
                                    y_pos = 72
                                
                                # 将图片插入页面 - 简化处理方式，避免不必要的图像转换
                                try:
                                    # 方法1: 直接使用原始图像，通过控制插入矩形的大小来缩放显示
                                    new_doc[current_page].insert_image(
                                        fitz.Rect(72, y_pos, 72 + scaled_width, y_pos + scaled_height),
                                        pixmap=pix
                                    )
                                except Exception as e1:
                                    logging.error(f"插入图像方法1失败: {str(e1)}")
                                    try:
                                        # 方法2: 使用更基本的绘图方法
                                        new_doc[current_page].draw_rect(
                                            fitz.Rect(72, y_pos, 72 + scaled_width, y_pos + scaled_height),
                                            color=(1, 1, 1),
                                            fill=(1, 1, 1)
                                        )
                                        # 注意: 不进行图像插入，仅留白
                                        logging.info("无法插入图像，已用白色矩形代替")
                                    except Exception as e2:
                                        logging.error(f"创建替代矩形也失败: {str(e2)}")
                                
                                y_pos += scaled_height + 20
                                added_images += 1
                                
                                # 释放pixmap资源
                                pix = None
                                
                        except Exception as img_err:
                            logging.error(f"处理图片时出错: {str(img_err)}")
                    
                    logging.info(f"成功添加了 {added_images} 张图片")
        except Exception as img_err:
            logging.error(f"提取和处理图片时出错: {str(img_err)}")
        
        # 添加水印
        for page in new_doc:
            page.insert_text(
                fitz.Point(page.rect.width - 150, 30),
                "翻译版本 - " + datetime.datetime.now().strftime("%Y-%m-%d"),
                fontsize=8,
                color=(0.7, 0.7, 0.7),
                fontname=font_name
            )
        
        # 保存翻译后的PDF
        new_doc.save(output_pdf_path)
        new_doc.close()
        doc.close()
        
        logging.info(f"成功生成翻译PDF: {output_pdf_path}")
        return output_pdf_path
    
    except ImportError:
        logging.error("未安装PyMuPDF库，无法使用此方法生成PDF")
        return generate_simple_translated_pdf(translated_content, output_pdf_path)
    except Exception as e:
        logging.error(f"生成翻译PDF时出错: {str(e)}", exc_info=True)
        return generate_simple_translated_pdf(translated_content, output_pdf_path)

# 移到文件顶部导入区域
import hashlib
import os.path

# 添加缓存相关函数 - 将导入和缓存功能移到顶部
def get_translation_cache_dir():
    """获取翻译缓存目录"""
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'translation_cache')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_cache_key(text, provider, model):
    """生成缓存键"""
    # 使用文本内容、提供商和模型名称的哈希值作为缓存键
    hash_obj = hashlib.md5(f"{text}_{provider}_{model}".encode('utf-8'))
    return hash_obj.hexdigest()

def get_cached_translation(text, provider, model):
    """获取缓存的翻译结果"""
    if not text:
        return None
        
    cache_key = get_cache_key(text, provider, model)
    cache_file = os.path.join(get_translation_cache_dir(), f"{cache_key}.txt")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_text = f.read()
                logging.info(f"从缓存读取翻译，长度: {len(cached_text)} 字符")
                return cached_text
        except Exception as e:
            logging.error(f"读取翻译缓存失败: {str(e)}")
    
    return None

def save_translation_cache(text, translated_text, provider, model):
    """保存翻译结果到缓存"""
    if not text or not translated_text:
        return
        
    try:
        cache_key = get_cache_key(text, provider, model)
        cache_file = os.path.join(get_translation_cache_dir(), f"{cache_key}.txt")
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        logging.info(f"翻译结果已缓存: {cache_file}, 长度: {len(translated_text)} 字符")
    except Exception as e:
        logging.error(f"保存翻译缓存失败: {str(e)}")

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
    
    # 检查缓存
    cached_result = get_cached_translation(text, provider, model)
    if cached_result:
        logging.info(f"找到翻译缓存，使用缓存结果")
        return cached_result
    
    # 测试模式 - 直接模拟翻译结果
    if api_key == 'sk-test':
        logging.info("使用测试模式，返回模拟翻译")
        
        # 生成模拟翻译
        if len(text) > 100:
            # 对于长文本，生成更丰富的模拟翻译
            paragraphs = text.split('\n\n')
            if len(paragraphs) > 1:
                # 处理多段落文本
                translated = ""
                for i, para in enumerate(paragraphs):
                    if para.strip():
                        if i == 0:
                            # 第一段落更详细处理
                            translated += f"[测试翻译] 这是第{i+1}段翻译: {para[:30]}...\n\n"
                        else:
                            translated += f"[测试] 段落{i+1}的翻译内容 ({len(para)} 字符)\n\n"
                translated = translated.strip()
            else:
                translated = f"[测试模式] 这是原文的模拟翻译结果。原文长度: {len(text)}字符。"
        else:
            # 对于短文本，添加一些简单的模拟翻译
            translated = f"[测试翻译] {text[:30]}..."
            
        # 保存到缓存
        save_translation_cache(text, translated, provider, model)
        return translated
    
    # 正常模式 - 使用实际API
    try:
        if provider.lower() == 'openai':
            translated = translate_with_openai(text, api_key, model, system_prompt)
        elif provider.lower() == 'deepseek':
            translated = translate_with_deepseek(text, api_key, model, system_prompt)
        else:
            raise ValueError(f"不支持的服务提供商: {provider}")
            
        # 保存到缓存
        save_translation_cache(text, translated, provider, model)
        return translated
    except Exception as e:
        logging.error(f"翻译文本失败: {str(e)}", exc_info=True)
        # 翻译失败时返回错误信息，而不是引发异常，以避免整个流程中断
        error_msg = f"翻译失败: {str(e)}"
        return error_msg

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
    根据翻译内容生成PDF，保留原始PDF的格式和图像
    """
    try:
        # 创建存放翻译PDF的目录
        translated_dir = os.path.join(task_dir, 'translated')
        os.makedirs(translated_dir, exist_ok=True)
        
        # 创建图片目录
        images_dir = os.path.join(translated_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # PDF文件路径
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(translated_dir, f"translated_{timestamp}.pdf")
        
        # 查找原始PDF文件路径
        original_pdf_path = None
        # 首先在task_dir中寻找PDF文件
        for filename in os.listdir(task_dir):
            if filename.endswith('.pdf'):
                original_pdf_path = os.path.join(task_dir, filename)
                logging.info(f"在任务目录中找到原始PDF文件: {original_pdf_path}")
                break
        
        # 如果在task_dir中找不到，尝试在上传目录中寻找
        if not original_pdf_path or not os.path.exists(original_pdf_path):
            # 检查task对象是否可用
            task_id = os.path.basename(task_dir)
            if task_id in tasks and 'file_path' in tasks[task_id]:
                file_path = tasks[task_id]['file_path']
                if os.path.exists(file_path):
                    original_pdf_path = file_path
                    logging.info(f"在上传目录中找到原始PDF文件: {original_pdf_path}")
                    
                    # 复制到任务目录
                    pdf_filename = os.path.basename(file_path).split('_', 1)[1] if '_' in os.path.basename(file_path) else os.path.basename(file_path)
                    new_pdf_path = os.path.join(task_dir, pdf_filename)
                    # 如果任务目录中还没有此PDF，则复制
                    if not os.path.exists(new_pdf_path):
                        try:
                            shutil.copy2(original_pdf_path, new_pdf_path)
                            original_pdf_path = new_pdf_path
                            logging.info(f"已将原始PDF文件从上传目录复制到任务目录: {new_pdf_path}")
                        except Exception as copy_err:
                            logging.error(f"复制PDF文件时出错: {str(copy_err)}", exc_info=True)
        
        if not original_pdf_path or not os.path.exists(original_pdf_path):
            logging.error(f"找不到原始PDF文件，无法提取图像和布局。尝试过的路径: {task_dir}")
            logging.error(f"任务目录内容: {os.listdir(task_dir)}")
            return generate_simple_translated_pdf(translated_content, pdf_path)
        
        logging.info(f"使用原始PDF文件: {original_pdf_path}")
        
        # 优先尝试使用双栏对照模式生成PDF
        try:
            logging.info("尝试使用双栏对照模式生成翻译PDF")
            return generate_dual_column_pdf(original_pdf_path, original_content, translated_content, pdf_path)
        except Exception as dual_column_err:
            logging.error(f"使用双栏对照模式生成PDF失败: {str(dual_column_err)}", exc_info=True)
            # 回退到其他模式
            logging.info("回退到尝试保留原始布局的模式")
        
        # 尝试使用保留原始布局的方式生成翻译PDF
        try:
            # 首先尝试使用PyMuPDF保留原始布局生成PDF
            logging.info("尝试使用PyMuPDF保留原始布局生成翻译PDF")
            return generate_translated_pdf_with_original_layout(original_pdf_path, original_content, translated_content, pdf_path)
        except Exception as pymupdf_err:
            logging.error(f"使用PyMuPDF保留原始布局生成PDF失败: {str(pymupdf_err)}", exc_info=True)
            # 如果使用PyMuPDF失败，回退到使用提取的布局信息
            logging.info("回退到使用提取的布局信息生成PDF")
        
        # 从原始PDF中提取图片和布局
        layout_info = None
        images = []
        try:
            # 使用PDFExtractor提取图片和布局
            logging.info(f"从原始PDF提取图片和布局: {original_pdf_path}")
            pdf_extractor = PDFExtractor(original_pdf_path)
            
            # 提取布局信息
            layout_info = pdf_extractor.extract_layout()
            logging.info(f"成功提取布局信息，共 {len(layout_info)} 页")
            
            # 提取图片
            image_paths = pdf_extractor.extract_images(images_dir)
            logging.info(f"成功提取 {len(image_paths)} 张图片: {image_paths[:3] if len(image_paths) > 3 else image_paths}...")
            
            # 整理图片信息，用于PDF生成时插入
            for i, img_path in enumerate(image_paths):
                try:
                    img_info = {
                        'path': img_path,
                        'index': i,
                        'page': int(os.path.basename(img_path).split('_page')[1].split('_')[0]) - 1 if '_page' in os.path.basename(img_path) else 0,
                        'filename': os.path.basename(img_path)
                    }
                    images.append(img_info)
                except Exception as img_err:
                    logging.error(f"处理图片路径时出错: {str(img_err)}, 路径: {img_path}")
            
            # 关闭extractor
            pdf_extractor.close()
        except Exception as extract_err:
            logging.error(f"提取图片和布局过程中出错: {str(extract_err)}", exc_info=True)
            # 如果提取失败，使用简单版本的PDF生成
            return generate_simple_translated_pdf(translated_content, pdf_path)
        
        # 尝试使用布局信息生成PDF
        try:
            if layout_info and len(layout_info) > 0:
                logging.info(f"使用布局信息生成PDF，布局页数: {len(layout_info)}")
                return generate_layout_translated_pdf(original_content, translated_content, layout_info, images, pdf_path)
            else:
                logging.warning("无法获取布局信息或布局为空，使用简单版本生成PDF")
                return generate_simple_translated_pdf(translated_content, pdf_path)
        except Exception as pdf_err:
            logging.error(f"使用布局生成PDF失败: {str(pdf_err)}", exc_info=True)
            # 如果使用布局生成失败，回退到简单版本
            return generate_simple_translated_pdf(translated_content, pdf_path)
    
    except Exception as e:
        logging.error(f"生成PDF出错: {str(e)}", exc_info=True)
        # 尝试生成一个超简单的PDF作为备用
        try:
            logging.info("尝试生成备用简单PDF")
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.setFont("Helvetica", 12)
            c.drawString(72, 700, "翻译PDF生成失败，请重试。")
            c.drawString(72, 680, f"错误信息: {str(e)}")
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
        
        raise

def generate_layout_translated_pdf(original_content, translated_content, layout_info, images, pdf_path):
    """
    使用原始PDF的布局信息生成翻译后的PDF
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, Flowable
        from reportlab.lib.units import inch, cm, mm
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
        
        # 使用已注册的中文字体，如果没有则使用默认字体
        font_name = 'ChineseFont' if 'ChineseFont' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        logging.info(f"PDF生成使用字体: {font_name}")
        
        # 确定页面大小，尝试使用原始PDF的页面大小
        page_width = layout_info[0]['width'] if layout_info and layout_info[0].get('width') else letter[0]
        page_height = layout_info[0]['height'] if layout_info and layout_info[0].get('height') else letter[1]
        pagesize = (page_width, page_height)
        logging.info(f"使用页面尺寸: {pagesize}")
        
        # 创建一个带页面模板的文档
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=pagesize,
            rightMargin=36,  # 0.5 inch
            leftMargin=36,   # 0.5 inch
            topMargin=36,    # 0.5 inch
            bottomMargin=36  # 0.5 inch
        )
        
        # 创建样式
        styles = getSampleStyleSheet()
        
        # 定义自定义样式
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
        
        # 创建自定义水平线类
        class MCLine(Flowable):
            def __init__(self, width, thickness=0.5, color=colors.black, spaceBefore=1, spaceAfter=1):
                Flowable.__init__(self)
                self.width = width
                self.thickness = thickness
                self.color = color
                self.spaceBefore = spaceBefore
                self.spaceAfter = spaceAfter
                
            def wrap(self, availWidth, availHeight):
                self.availWidth = availWidth
                return (self.availWidth, self.thickness + self.spaceBefore + self.spaceAfter)
                
            def draw(self):
                self.canv.setLineWidth(self.thickness)
                self.canv.setStrokeColor(self.color)
                self.canv.line(0, self.spaceBefore, self.availWidth, self.spaceBefore)
        
        # 检查是否有翻译内容
        if not translated_content.get('title') and not translated_content.get('abstract') and not (translated_content.get('sections') and len(translated_content.get('sections')) > 0):
            logging.warning("翻译内容为空，使用简单版本生成PDF")
            return generate_simple_translated_pdf(translated_content, pdf_path)
            
        # 构建PDF内容
        elements = []
        
        # 添加标题
        if translated_content.get('title'):
            elements.append(Paragraph(translated_content['title'], title_style))
            elements.append(Spacer(1, 12))
        
        # 提取原始元数据
        meta = {}
        if original_content and isinstance(original_content, dict) and original_content.get('metadata'):
            meta = original_content.get('metadata', {})
        
        # 作者信息
        if meta.get('author'):
            elements.append(Paragraph(f"作者: {meta.get('author')}", subtitle_style))
            elements.append(Spacer(1, 6))
                
        # 期刊信息
        if meta.get('subject'):
            elements.append(Paragraph(f"期刊: {meta.get('subject')}", subtitle_style))
            elements.append(Spacer(1, 6))
        
        # 添加摘要
        if translated_content.get('abstract'):
            elements.append(Paragraph("摘要", heading_style))
            elements.append(Paragraph(translated_content['abstract'], ParagraphStyle(
                'CustomAbstract',
                parent=normal_style,
                fontSize=10,
                firstLineIndent=0,
                leftIndent=20,
                rightIndent=20,
                spaceBefore=6,
                spaceAfter=10
            )))
            elements.append(Spacer(1, 12))
        
        # 添加水平分割线
        elements.append(Spacer(1, 6))
        elements.append(MCLine(width="100%", thickness=1, color=colors.gray, spaceBefore=3, spaceAfter=3))
        elements.append(Spacer(1, 6))
        
        # 根据原始布局信息找到可能的图形位置和表格位置
        image_positions = []
        table_positions = []
        
        # 验证图片是否来自原始论文
        verified_images = []
        if images:
            # 检查图片路径格式，确保只使用从原始PDF提取的图片
            for img in images:
                if 'path' in img and os.path.exists(img['path']):
                    file_name = os.path.basename(img['path'])
                    # 确认图片来自PDF提取的目录
                    if '_page' in file_name and img['path'].find('/images/') > 0:
                        verified_images.append(img)
                        logging.info(f"验证通过的图片: {file_name}")
                    else:
                        logging.warning(f"图片未通过验证: {file_name}，可能不是原论文图片")
            
            # 如果没有有效图片，记录警告
            if not verified_images and images:
                logging.warning(f"未找到有效的原论文图片，原始图片列表: {[os.path.basename(img['path']) for img in images if 'path' in img]}")
            
            # 替换原始图片列表为验证过的列表
            images = verified_images
        
        # 分析布局，找出可能的图像和表格
        logging.info("分析布局，识别图像和表格位置")
        for page_idx, page_layout in enumerate(layout_info):
            for block_idx, block in enumerate(page_layout.get('blocks', [])):
                # 识别图像块
                if block.get('type') == 'image':
                    bbox = block.get('bbox', [0, 0, 0, 0])
                    image_positions.append({
                        'page': page_idx,
                        'bbox': bbox,
                        'block_idx': block_idx,
                        'width': bbox[2] - bbox[0],
                        'height': bbox[3] - bbox[1],
                        'used': False
                    })
                    logging.info(f"找到图像块: 页面={page_idx+1}, 位置={bbox}")
                
                # 尝试识别表格（通常表格由多个对齐的文本块组成）
                elif block.get('type') == 'text':
                    lines = block.get('lines', [])
                    if len(lines) > 1:
                        # 检查是否有表格特征（例如，多行且每行有相似数量的单词/字符）
                        line_words = [len(line.get('text', '').split()) for line in lines]
                        line_chars = [len(line.get('text', '')) for line in lines]
                        
                        # 如果多行文本的长度相似，可能是表格
                        if len(line_chars) > 3 and max(line_chars) - min(line_chars) < 20:
                            bbox = block.get('bbox', [0, 0, 0, 0])
                            table_positions.append({
                                'page': page_idx,
                                'bbox': bbox,
                                'block_idx': block_idx,
                                'lines': lines,
                                'used': False
                            })
                            logging.info(f"发现可能的表格: 页面={page_idx+1}, 行数={len(lines)}")
        
        logging.info(f"从布局中识别出 {len(image_positions)} 个图像位置, {len(table_positions)} 个可能的表格位置")
        logging.info(f"验证通过的原论文图片数量: {len(images)}")
        
        # 添加章节和图片
        section_count = 0
        current_page_estimate = 0
        
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
                            # 检查是否是表格标题
                            is_table_caption = False
                            if len(paragraph) < 150 and ("表" in paragraph or "Table" in paragraph or "tab" in paragraph.lower()):
                                is_table_caption = True
                                # 估计当前位置对应的页面
                                current_page_estimate = min(section_count, len(layout_info)-1)
                                
                                # 查找当前页面附近未使用的表格位置
                                nearby_tables = []
                                for pos in table_positions:
                                    if not pos['used'] and abs(pos['page'] - current_page_estimate) <= 2:
                                        nearby_tables.append(pos)
                                
                                # 如果找到表格位置，尝试创建表格
                                if nearby_tables:
                                    pos = nearby_tables[0]
                                    pos['used'] = True  # 标记为已使用
                                    
                                    try:
                                        # 从文本行创建表格
                                        lines = pos['lines']
                                        table_data = []
                                        
                                        # 分析表格结构
                                        for line in lines:
                                            line_text = line.get('text', '').strip()
                                            if line_text:
                                                # 尝试根据空格或制表符分割
                                                cells = line_text.split('\t') if '\t' in line_text else line_text.split('  ')
                                                if len(cells) == 1:  # 如果没有明显的分隔，尝试按空格分割
                                                    cells = line_text.split(' ')
                                                
                                                # 过滤掉空白单元格
                                                cells = [cell.strip() for cell in cells if cell.strip()]
                                                if cells:
                                                    table_data.append(cells)
                                        
                                        # 确保所有行有相同数量的单元格
                                        max_cols = max(len(row) for row in table_data) if table_data else 0
                                        for i in range(len(table_data)):
                                            while len(table_data[i]) < max_cols:
                                                table_data[i].append('')
                                        
                                        # 创建表格
                                        if table_data and max_cols > 1:  # 确保至少有2列才创建表格
                                            table = Table(table_data, repeatRows=1)
                                            
                                            # 设置表格样式
                                            style = TableStyle([
                                                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                                                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                                ('FONTNAME', (0, 0), (-1, 0), font_name),
                                                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                                                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                                            ])
                                            table.setStyle(style)
                                            
                                            # 添加表格和说明
                                            elements.append(Spacer(1, 12))
                                            elements.append(table)
                                            elements.append(Spacer(1, 6))
                                            elements.append(Paragraph(paragraph, ParagraphStyle(
                                                'TableCaption',
                                                parent=normal_style,
                                                fontName=font_name,
                                                fontSize=9,
                                                alignment=TA_CENTER,
                                                firstLineIndent=0
                                            )))
                                            elements.append(Spacer(1, 12))
                                            
                                            continue  # 跳过下面的文本添加
                                    except Exception as table_err:
                                        logging.error(f"创建表格时出错: {str(table_err)}")
                                        # 失败时退回到普通段落
                                        is_table_caption = False
                            
                            # 检查是否是图片说明
                            is_figure_caption = False
                            if len(paragraph) < 150 and ("图" in paragraph or "Fig" in paragraph or "figure" in paragraph.lower()):
                                is_figure_caption = True
                                # 估计当前位置对应的页面
                                current_page_estimate = min(section_count, len(layout_info)-1)
                                
                                # 查找当前页面附近未使用的图像位置
                                nearby_positions = []
                                for pos in image_positions:
                                    if not pos['used'] and abs(pos['page'] - current_page_estimate) <= 3:
                                        nearby_positions.append(pos)
                                
                                # 如果找到图像位置，尝试找到对应的图片文件
                                if nearby_positions and images:
                                    pos = nearby_positions[0]
                                    pos['used'] = True  # 标记为已使用
                                    
                                    # 找到最近的图片
                                    nearby_images = [img for img in images if abs(img['page'] - pos['page']) <= 2]
                                    if nearby_images:
                                        img_info = nearby_images[0]
                                        # 从列表中移除，但保留引用以便其他部分仍能获取到图片信息
                                        image_used = images.pop(images.index(img_info))
                                        
                                        # 插入图片
                                        try:
                                            # 计算图片尺寸，保持原始宽高比
                                            img_width = min(450, pos['width'] * 0.8)
                                            img_height = min(300, pos['height'] * 0.8)
                                            
                                            # 再次验证图片路径
                                            if os.path.exists(img_info['path']):
                                                logging.info(f"插入图片: {os.path.basename(img_info['path'])}, 页面: {img_info['page']+1}")
                                                img = Image(img_info['path'], width=img_width, height=img_height, kind='proportional')
                                                elements.append(Spacer(1, 12))
                                                elements.append(img)
                                                elements.append(Spacer(1, 6))
                                                elements.append(Paragraph(paragraph, ParagraphStyle(
                                                    'ImageCaption',
                                                    parent=normal_style,
                                                    fontName=font_name,
                                                    fontSize=9,
                                                    alignment=TA_CENTER,
                                                    firstLineIndent=0
                                                )))
                                                elements.append(Spacer(1, 12))
                                                
                                                continue  # 跳过下面的文本添加
                                            else:
                                                logging.error(f"图片文件不存在: {img_info['path']}")
                                        except Exception as img_err:
                                            logging.error(f"插入图片失败: {str(img_err)}")
                                            # 失败时退回到普通段落
                                            is_figure_caption = False
                                    else:
                                        logging.warning(f"附近没有找到合适的图片，页面: {current_page_estimate+1}")
                            
                            # 如果不是表格标题或图片说明，或者处理它们失败了，则作为普通段落添加
                            if not is_table_caption and not is_figure_caption:
                                elements.append(Paragraph(paragraph, normal_style))
                        elif isinstance(paragraph, dict) and paragraph.get('translated'):
                            elements.append(Paragraph(paragraph['translated'], normal_style))
                
                # 添加章节间隔
                elements.append(Spacer(1, 12))
                elements.append(MCLine(width="100%", thickness=1, color=colors.lightgrey, spaceBefore=3, spaceAfter=3))
                elements.append(Spacer(1, 12))
                section_count += 1
                # 更新当前页面估计值
                current_page_estimate = min(section_count, len(layout_info)-1)
                
            except Exception as section_err:
                logging.error(f"处理章节时出错: {str(section_err)}")
                elements.append(Paragraph("章节处理错误", heading_style))
                elements.append(Spacer(1, 12))
        
        # 构建PDF
        logging.info(f"开始构建布局PDF: {pdf_path}")
        doc.build(elements)
        
        # 验证PDF
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            logging.info(f"布局PDF构建成功: {pdf_path}, 大小: {os.path.getsize(pdf_path)} 字节")
            return pdf_path
        else:
            logging.error("布局PDF生成失败")
            return generate_simple_translated_pdf(translated_content, pdf_path)
            
    except Exception as e:
        logging.error(f"生成布局PDF出错: {str(e)}", exc_info=True)
        # 失败时回退到简单版本
        return generate_simple_translated_pdf(translated_content, pdf_path)

def generate_simple_translated_pdf(translated_content, pdf_path):
    """
    生成简单版本的翻译PDF，不包含复杂布局
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
        from reportlab.lib import colors
        
        # 使用已注册的中文字体，如果没有则使用默认字体
        font_name = 'ChineseFont' if 'ChineseFont' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        logging.info(f"简单PDF生成使用字体: {font_name}")
        
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
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=12
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
                elements.append(Paragraph(translated_content['title'], title_style))
                elements.append(Spacer(1, 12))
            
            # 添加摘要
            if translated_content.get('abstract'):
                elements.append(Paragraph("摘要", heading_style))
                elements.append(Paragraph(translated_content['abstract'], ParagraphStyle(
                    'CustomAbstract',
                    parent=normal_style,
                    fontSize=10,
                    firstLineIndent=0,
                    leftIndent=20,
                    rightIndent=20,
                    spaceBefore=6,
                    spaceAfter=10
                )))
                elements.append(Spacer(1, 12))
            
            # 添加水平分割线
            elements.append(Spacer(1, 6))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.gray, spaceBefore=6, spaceAfter=6))
            elements.append(Spacer(1, 6))
            
            # 添加章节
            for section in translated_content.get('sections', []):
                # 章节标题
                if section.get('title'):
                    elements.append(Paragraph(section['title'], heading_style))
                
                # 章节内容
                if not section.get('content') or len(section['content']) == 0:
                    elements.append(Paragraph("本章节无内容或翻译失败", normal_style))
                else:
                    for paragraph in section.get('content', []):
                        if paragraph and isinstance(paragraph, str) and paragraph.strip():
                            elements.append(Paragraph(paragraph, normal_style))
                        elif isinstance(paragraph, dict) and paragraph.get('translated'):
                            elements.append(Paragraph(paragraph['translated'], normal_style))
                
                # 添加章节间隔
                elements.append(Spacer(1, 12))
        
        # 构建PDF
        logging.info(f"开始构建简单PDF: {pdf_path}")
        doc.build(elements)
        
        # 验证生成的文件
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            logging.info(f"生成的简单PDF大小: {file_size} 字节")
            if file_size == 0:
                raise Exception("生成的PDF文件大小为0")
            return pdf_path
        else:
            raise Exception("PDF文件未生成")
            
    except Exception as e:
        logging.error(f"生成简单PDF出错: {str(e)}", exc_info=True)
        
        # 尝试生成一个超简单的PDF作为备用
        try:
            logging.info("尝试生成备用超简单PDF")
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.setFont("Helvetica", 12)
            c.drawString(72, 700, "翻译PDF生成失败，请重试。")
            c.drawString(72, 680, f"错误信息: {str(e)}")
            c.drawString(72, 660, "时间戳: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            c.save()
            
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                logging.info("备用超简单PDF生成成功")
                return pdf_path
            else:
                raise Exception("备用PDF生成失败")
        except Exception as backup_err:
            logging.error(f"生成备用超简单PDF时出错: {str(backup_err)}")
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

def generate_dual_column_pdf(original_pdf_path, original_content, translated_content, output_pdf_path):
    """
    生成双栏对照PDF，左侧显示原文，右侧显示译文，保留原始PDF的标题、段落和图片
    
    参数:
    - original_pdf_path: 原始PDF路径
    - original_content: 原始文档内容
    - translated_content: 翻译内容
    - output_pdf_path: 输出的PDF路径
    
    返回:
    - 生成的PDF路径
    """
    try:
        import fitz  # PyMuPDF
        
        # 打开原始PDF
        logging.info(f"打开原始PDF: {original_pdf_path}")
        orig_doc = fitz.open(original_pdf_path)
        
        # 提取翻译内容
        title = translated_content.get('title', '')
        abstract = translated_content.get('abstract', '')
        sections = translated_content.get('sections', [])
        
        logging.info(f"翻译标题: '{title[:50]}...'")
        logging.info(f"翻译摘要: '{abstract[:50]}...'")
        logging.info(f"翻译章节数: {len(sections)}")
        
        # 检查是否有翻译内容
        if not title and not abstract and len(sections) == 0:
            logging.warning("未找到有效的翻译内容，将使用备用方法生成PDF")
            return generate_simple_translated_pdf(translated_content, output_pdf_path)
        
        # 创建新的PDF文档 - 使用A4纸张大小
        new_doc = fitz.open()
        paper_width, paper_height = 595, 842  # A4纸张大小，单位为点
        margin = 40  # 页边距
        column_gap = 15  # 双栏之间的间距
        column_width = (paper_width - 2 * margin - column_gap) / 2  # 每栏宽度
        
        # 使用安全的内置字体
        font_name = "helv"  # Helvetica是PyMuPDF中的内置字体
        
        # 创建第一页并设置标题
        new_doc.new_page(width=paper_width, height=paper_height)
        first_page = new_doc[0]
        
        # 设置背景为白色
        first_page.draw_rect(first_page.rect, color=(1, 1, 1), fill=(1, 1, 1))
        
        # 页面标题 - 居中显示
        header_text = "论文双语对照版"
        header_y = 30
        text_width = 7 * len(header_text)
        x_pos = (paper_width - text_width) / 2
        first_page.insert_text(
            fitz.Point(x_pos, header_y),
            header_text,
            fontsize=14,
            color=(0, 0, 0),
            fontname=font_name
        )
        
        # 绘制分隔线
        first_page.draw_line(
            fitz.Point(margin, header_y + 15),
            fitz.Point(paper_width - margin, header_y + 15),
            color=(0.5, 0.5, 0.5),
            width=0.5
        )
        
        # 定义起始Y坐标
        y_pos = header_y + 40
        
        # 左侧显示原标题
        orig_title = original_content.get('title', '')
        if orig_title:
            first_page.insert_text(
                fitz.Point(margin, y_pos),
                "原文标题:",
                fontsize=10,
                color=(0.5, 0.5, 0.5),
                fontname=font_name
            )
            y_pos += 15
            
            # 插入原标题
            title_rect = fitz.Rect(margin, y_pos, margin + column_width, y_pos + 60)
            title_height = first_page.insert_textbox(
                title_rect,
                orig_title,
                fontsize=12,
                color=(0, 0, 0),
                fontname=font_name
            )
            y_pos += abs(title_height) + 10
        
        # 右侧显示翻译标题
        if title:
            first_page.insert_text(
                fitz.Point(margin + column_width + column_gap, header_y + 40),
                "翻译标题:",
                fontsize=10,
                color=(0.5, 0.5, 0.5),
                fontname=font_name
            )
            
            # 插入翻译标题
            trans_title_rect = fitz.Rect(
                margin + column_width + column_gap,
                header_y + 55,
                paper_width - margin,
                header_y + 115
            )
            first_page.insert_textbox(
                trans_title_rect,
                title,
                fontsize=12,
                color=(0, 0, 0),
                fontname=font_name
            )
        
        # 绘制分隔线
        first_page.draw_line(
            fitz.Point(margin, y_pos),
            fitz.Point(paper_width - margin, y_pos),
            color=(0.8, 0.8, 0.8),
            width=0.2
        )
        y_pos += 15
        
        # 左侧显示原摘要
        orig_abstract = original_content.get('abstract', '')
        if orig_abstract:
            first_page.insert_text(
                fitz.Point(margin, y_pos),
                "原文摘要:",
                fontsize=10,
                color=(0.5, 0.5, 0.5),
                fontname=font_name
            )
            y_pos += 15
            
            # 插入原摘要
            abstract_rect = fitz.Rect(margin, y_pos, margin + column_width, y_pos + 200)
            abstract_height = first_page.insert_textbox(
                abstract_rect,
                orig_abstract,
                fontsize=11,
                color=(0, 0, 0),
                fontname=font_name
            )
            y_pos += abs(abstract_height) + 15
        
        # 右侧显示翻译摘要
        if abstract:
            first_page.insert_text(
                fitz.Point(margin + column_width + column_gap, y_pos - abstract_height - 15),
                "翻译摘要:",
                fontsize=10,
                color=(0.5, 0.5, 0.5),
                fontname=font_name
            )
            
            # 插入翻译摘要
            trans_abstract_rect = fitz.Rect(
                margin + column_width + column_gap,
                y_pos - abstract_height,
                paper_width - margin,
                y_pos
            )
            first_page.insert_textbox(
                trans_abstract_rect,
                abstract,
                fontsize=11,
                color=(0, 0, 0),
                fontname=font_name
            )
        
        # 绘制分隔线
        first_page.draw_line(
            fitz.Point(margin, y_pos),
            fitz.Point(paper_width - margin, y_pos),
            color=(0.8, 0.8, 0.8),
            width=0.2
        )
        y_pos += 15
        
        # 处理正文内容 - 段落对照显示
        current_page = 0
        
        for section_idx, section in enumerate(sections):
            orig_section_title = original_content.get('sections', [])[section_idx].get('title', '') if section_idx < len(original_content.get('sections', [])) else ''
            section_title = section.get('title', '')
            
            # 原文段落内容
            orig_section_content = original_content.get('sections', [])[section_idx].get('content', []) if section_idx < len(original_content.get('sections', [])) else []
            section_content = section.get('content', [])
            
            # 检查是否需要新页面
            if y_pos > new_doc[current_page].rect.height - 100:
                current_page = len(new_doc)
                new_doc.new_page(width=paper_width, height=paper_height)
                new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))  # 白色背景
                
                # 绘制页眉
                header_y = 30
                new_doc[current_page].insert_text(
                    fitz.Point((paper_width - text_width) / 2, header_y),
                    header_text,
                    fontsize=14,
                    color=(0, 0, 0),
                    fontname=font_name
                )
                
                # 绘制分隔线
                new_doc[current_page].draw_line(
                    fitz.Point(margin, header_y + 15),
                    fitz.Point(paper_width - margin, header_y + 15),
                    color=(0.5, 0.5, 0.5),
                    width=0.5
                )
                
                y_pos = header_y + 40
            
            # 显示章节标题
            if orig_section_title or section_title:
                # 原文章节标题
                if orig_section_title:
                    new_doc[current_page].insert_text(
                        fitz.Point(margin, y_pos),
                        "原文:",
                        fontsize=9,
                        color=(0.5, 0.5, 0.5),
                        fontname=font_name
                    )
                    y_pos += 12
                    
                    # 插入原文标题
                    title_rect = fitz.Rect(margin, y_pos, margin + column_width, y_pos + 40)
                    title_height = new_doc[current_page].insert_textbox(
                        title_rect,
                        orig_section_title,
                        fontsize=11,
                        color=(0, 0, 0),
                        fontname=font_name
                    )
                    orig_title_y = y_pos
                    orig_title_height = abs(title_height)
                
                # 翻译章节标题
                if section_title:
                    new_doc[current_page].insert_text(
                        fitz.Point(margin + column_width + column_gap, y_pos - 12),
                        "翻译:",
                        fontsize=9,
                        color=(0.5, 0.5, 0.5),
                        fontname=font_name
                    )
                    
                    # 插入翻译标题
                    trans_title_rect = fitz.Rect(
                        margin + column_width + column_gap,
                        y_pos,
                        paper_width - margin,
                        y_pos + 40
                    )
                    trans_title_height = new_doc[current_page].insert_textbox(
                        trans_title_rect,
                        section_title,
                        fontsize=11,
                        color=(0, 0, 0),
                        fontname=font_name
                    )
                    
                    # 调整y_pos到两个标题中较长的那个
                    title_height = max(orig_title_height if orig_section_title else 0, 
                                     abs(trans_title_height) if section_title else 0)
                    y_pos += title_height + 10
                else:
                    y_pos += orig_title_height + 10
            
            # 绘制段落内容
            for para_idx, para in enumerate(section_content):
                # 获取原文段落
                orig_para = orig_section_content[para_idx] if para_idx < len(orig_section_content) else ""
                
                # 检查是否需要新页面
                if y_pos > new_doc[current_page].rect.height - 100:
                    current_page = len(new_doc)
                    new_doc.new_page(width=paper_width, height=paper_height)
                    new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))  # 白色背景
                    
                    # 绘制页眉
                    header_y = 30
                    new_doc[current_page].insert_text(
                        fitz.Point((paper_width - text_width) / 2, header_y),
                        header_text,
                        fontsize=14,
                        color=(0, 0, 0),
                        fontname=font_name
                    )
                    
                    # 绘制分隔线
                    new_doc[current_page].draw_line(
                        fitz.Point(margin, header_y + 15),
                        fitz.Point(paper_width - margin, header_y + 15),
                        color=(0.5, 0.5, 0.5),
                        width=0.5
                    )
                    
                    y_pos = header_y + 40
                
                # 原文段落
                if orig_para:
                    para_rect = fitz.Rect(margin, y_pos, margin + column_width, y_pos + 300)
                    para_height = new_doc[current_page].insert_textbox(
                        para_rect,
                        orig_para,
                        fontsize=10,
                        color=(0, 0, 0),
                        fontname=font_name
                    )
                    orig_para_height = abs(para_height)
                else:
                    orig_para_height = 0
                
                # 翻译段落
                if para:
                    trans_para_rect = fitz.Rect(
                        margin + column_width + column_gap,
                        y_pos,
                        paper_width - margin,
                        y_pos + 300
                    )
                    trans_para_height = new_doc[current_page].insert_textbox(
                        trans_para_rect,
                        para,
                        fontsize=10,
                        color=(0, 0, 0),
                        fontname=font_name
                    )
                    
                    # 调整y_pos到两个段落中较长的那个
                    para_height = max(orig_para_height, abs(trans_para_height))
                    y_pos += para_height + 10
                else:
                    y_pos += orig_para_height + 10
                
                # 如果文本太长，添加更多空间
                if orig_para_height > 300 or abs(trans_para_height if para else 0) > 300:
                    y_pos += 10
        
        # 尝试从原始PDF提取图片并添加到新PDF
        try:
            # 添加图片页
            current_page = len(new_doc)
            new_doc.new_page(width=paper_width, height=paper_height)
            new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))
            
            # 页面标题
            img_title = "原文图片"
            title_width = 7 * len(img_title)
            new_doc[current_page].insert_text(
                fitz.Point((paper_width - title_width) / 2, 50),
                img_title,
                fontsize=14,
                color=(0, 0, 0),
                fontname=font_name
            )
            
            # 从原始PDF中提取图片
            img_y_pos = 80
            img_count = 0
            
            for page_idx in range(len(orig_doc)):
                try:
                    page = orig_doc[page_idx]
                    image_list = page.get_images(full=True)
                    
                    for img_idx, img in enumerate(image_list):
                        try:
                            xref = img[0]
                            if xref > 0:
                                # 提取图片
                                pix = fitz.Pixmap(orig_doc, xref)
                                
                                # 计算缩放比例，确保图片不超过页宽
                                max_width = paper_width - 2 * margin
                                scale = 1.0
                                if pix.width > max_width:
                                    scale = max_width / pix.width
                                
                                # 计算显示尺寸
                                display_width = int(pix.width * scale)
                                display_height = int(pix.height * scale)
                                
                                # 检查是否需要新页面
                                if img_y_pos + display_height > new_doc[current_page].rect.height - margin:
                                    current_page = len(new_doc)
                                    new_doc.new_page(width=paper_width, height=paper_height)
                                    new_doc[current_page].draw_rect(new_doc[current_page].rect, color=(1, 1, 1), fill=(1, 1, 1))
                                    
                                    new_doc[current_page].insert_text(
                                        fitz.Point((paper_width - title_width) / 2, 50),
                                        img_title,
                                        fontsize=14,
                                        color=(0, 0, 0),
                                        fontname=font_name
                                    )
                                    
                                    img_y_pos = 80
                                
                                # 居中显示图片
                                img_x_pos = (paper_width - display_width) / 2
                                
                                # 插入图片
                                try:
                                    new_doc[current_page].insert_image(
                                        fitz.Rect(img_x_pos, img_y_pos, img_x_pos + display_width, img_y_pos + display_height),
                                        pixmap=pix
                                    )
                                    
                                    # 添加图片说明
                                    img_caption = f"图 {img_count + 1} (页面 {page_idx + 1})"
                                    caption_width = 7 * len(img_caption)
                                    new_doc[current_page].insert_text(
                                        fitz.Point((paper_width - caption_width) / 2, img_y_pos + display_height + 15),
                                        img_caption,
                                        fontsize=10,
                                        color=(0, 0, 0),
                                        fontname=font_name
                                    )
                                    
                                    img_y_pos += display_height + 40
                                    img_count += 1
                                except Exception as e:
                                    logging.error(f"插入图片失败: {str(e)}")
                                    # 添加白色矩形代替图片
                                    new_doc[current_page].draw_rect(
                                        fitz.Rect(img_x_pos, img_y_pos, img_x_pos + display_width, img_y_pos + display_height),
                                        color=(1, 1, 1),
                                        fill=(1, 1, 1),
                                        width=1,
                                        stroke_opacity=0.3
                                    )
                                    img_y_pos += display_height + 40
                        except Exception as e:
                            logging.error(f"处理图片 {img_idx} 失败: {str(e)}")
                except Exception as e:
                    logging.error(f"获取页面 {page_idx} 的图像失败: {str(e)}")
            
            logging.info(f"成功添加 {img_count} 张图片")
        except Exception as e:
            logging.error(f"提取和添加图片失败: {str(e)}")
        
        # 添加页脚
        for page_idx in range(len(new_doc)):
            page = new_doc[page_idx]
            footer_text = f"第 {page_idx + 1} 页 / 共 {len(new_doc)} 页  •  由Paper Translator生成"
            footer_width = 5 * len(footer_text)
            page.insert_text(
                fitz.Point((paper_width - footer_width) / 2, paper_height - 20),
                footer_text,
                fontsize=8,
                color=(0.5, 0.5, 0.5),
                fontname=font_name
            )
        
        # 保存PDF
        new_doc.save(output_pdf_path)
        new_doc.close()
        orig_doc.close()
        
        logging.info(f"成功生成双栏对照PDF: {output_pdf_path}")
        return output_pdf_path
    
    except ImportError:
        logging.error("未安装PyMuPDF库，无法使用此方法生成PDF")
        return generate_simple_translated_pdf(translated_content, output_pdf_path)
    except Exception as e:
        logging.error(f"生成双栏对照PDF时出错: {str(e)}", exc_info=True)
        return generate_simple_translated_pdf(translated_content, output_pdf_path)

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