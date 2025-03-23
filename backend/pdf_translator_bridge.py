#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import logging
import subprocess
import argparse
import shutil
from pathlib import Path

# 导入PDF后处理模块
from pdf_post_process import remove_slash_marks

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("pdf_translator_bridge")

# 结果文件夹
RESULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(RESULT_FOLDER, exist_ok=True)

def translate_document(pdf_path, task_id=None, source_lang='en', target_lang='zh', provider='deepseek', model='deepseek-chat', format='dual', post_process=True, force=False):
    """
    翻译PDF文档
    
    参数:
        pdf_path (str): PDF文件路径
        task_id (str): 任务ID，用于生成结果文件名
        source_lang (str): 源语言
        target_lang (str): 目标语言
        provider (str): 翻译提供商 ('deepseek'/'gpt'/'anthropic'/'azure'等)
        model (str): 模型名称
        format (str): 输出格式, 'dual'表示中英对照, 'mono'表示仅中文
        post_process (bool): 是否进行后处理去除斜杠标记
        force (bool): 是否强制重新翻译，即使已有翻译结果
        
    返回:
        str: 翻译后的PDF文件路径，如果失败则返回None
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF文件不存在: {pdf_path}")
        return None
    
    if not task_id:
        logger.warning("未提供任务ID，将使用PDF文件名")
        task_id = os.path.basename(pdf_path).split('.')[0]
    
    logger.info(f"开始翻译文档: {pdf_path}")
    logger.info(f"任务ID: {task_id}")
    logger.info(f"源语言: {source_lang}, 目标语言: {target_lang}")
    logger.info(f"提供商: {provider}, 模型: {model}")
    logger.info(f"输出格式: {format}")
    logger.info(f"强制重新翻译: {force}")
    
    # 结果文件路径
    result_folder = os.path.join(RESULT_FOLDER, task_id)
    os.makedirs(result_folder, exist_ok=True)
    
    # 根据格式确定最终的文件名
    if format == 'mono':
        result_filename = f"{task_id}_translated_mono.pdf"  # 仅中文版
        expected_generated_filename = f"{os.path.basename(pdf_path).rsplit('.', 1)[0]}-mono.pdf"
    else:  # dual or default
        result_filename = f"{task_id}_translated_dual.pdf"  # 中英对照版
        expected_generated_filename = f"{os.path.basename(pdf_path).rsplit('.', 1)[0]}-dual.pdf"
        
    result_path = os.path.join(result_folder, result_filename)
    
    # 如果不是强制重新翻译，检查是否已有翻译结果
    if not force and os.path.exists(result_path):
        logger.info(f"已找到现有翻译结果: {result_path}，直接返回")
        return result_path
    
    try:
        # 构建pdf2zh命令 - 根据pdf2zh的帮助信息调整参数格式
        pdf2zh_cmd = [
            "pdf2zh",
            pdf_path,  # 文件路径作为位置参数
            "--lang-in", source_lang,
            "--lang-out", target_lang,
            "--service", f"{provider}:{model}" if model else provider,
            "--output", result_folder,  # 指定输出目录而不是文件
            "--thread", "2",
            "--debug"  # 添加调试标志
        ]
        
        logger.info(f"执行命令: {' '.join(pdf2zh_cmd)}")
        logger.info(f"环境变量: DEEPSEEK_API_KEY={os.environ.get('DEEPSEEK_API_KEY', '未设置')[:5]}..., OPENAI_API_KEY={os.environ.get('OPENAI_API_KEY', '未设置')[:5]}...")
        
        # 执行pdf2zh命令，设置超时
        try:
            process = subprocess.run(
                pdf2zh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,  # 设为False，我们自己处理错误
                env=os.environ.copy(),  # 传递当前环境变量，包括API密钥
                timeout=300  # 设置5分钟超时
            )
        except subprocess.TimeoutExpired:
            logger.error("pdf2zh执行超时（5分钟）")
            return None
        
        # 检查返回码
        if process.returncode != 0:
            logger.error(f"pdf2zh执行失败 (返回码 {process.returncode})")
            logger.error(f"错误信息: {process.stderr}")
            return None
        
        logger.info(f"pdf2zh执行成功")
        
        # 验证结果文件是否存在
        if os.path.exists(result_path):
            logger.info(f"翻译完成，文件保存在: {result_path}")
            
            # 后处理：去除斜杠标记
            if post_process and format == 'mono':
                try:
                    logger.info(f"开始对文件进行后处理以去除斜杠标记: {result_path}")
                    post_processed_path = os.path.join(result_folder, f"{task_id}_processed.pdf")
                    if remove_slash_marks(result_path, post_processed_path):
                        logger.info(f"后处理成功，更新结果文件: {post_processed_path}")
                        # 备份原始翻译文件
                        original_backup = os.path.join(result_folder, f"{task_id}_original.pdf")
                        shutil.copy2(result_path, original_backup)
                        # 用后处理结果替换原始结果
                        shutil.move(post_processed_path, result_path)
                    else:
                        logger.warning(f"后处理失败，将使用原始翻译结果")
                except Exception as e:
                    logger.exception(f"后处理过程中发生错误: {str(e)}")
            
            return result_path
        else:
            # 检查输出目录下是否有生成的PDF
            base_name = os.path.basename(pdf_path).rsplit('.', 1)[0]
            
            # 首先检查预期的特定格式文件名
            expected_file_path = os.path.join(result_folder, expected_generated_filename)
            if os.path.exists(expected_file_path):
                # 找到对应格式的文件，移动到标准位置
                shutil.move(expected_file_path, result_path)
                logger.info(f"找到并移动生成的{format}格式文件: {expected_file_path} -> {result_path}")
                return result_path
            
            # 然后检查其他可能的文件名
            potential_files = [
                f"{task_id}_translated.pdf",
                f"{task_id}_{base_name}_translated.pdf",
                f"{task_id}_{base_name}-translated.pdf",
                f"{base_name}-dual.pdf",
                f"{base_name}-mono.pdf"
            ]
            
            # 检查指定的结果目录
            for filename in potential_files:
                pdf_path = os.path.join(result_folder, filename)
                if os.path.exists(pdf_path):
                    # 找到文件，移动到标准位置
                    if pdf_path != result_path:
                        shutil.move(pdf_path, result_path)
                        logger.info(f"找到并移动生成的文件: {pdf_path} -> {result_path}")
                    else:
                        logger.info(f"找到生成的文件: {pdf_path}")
                    
                    # 后处理：去除斜杠标记
                    if post_process and format == 'mono':
                        try:
                            logger.info(f"开始对文件进行后处理以去除斜杠标记: {result_path}")
                            post_processed_path = os.path.join(result_folder, f"{task_id}_processed.pdf")
                            if remove_slash_marks(result_path, post_processed_path):
                                logger.info(f"后处理成功，更新结果文件: {post_processed_path}")
                                # 备份原始翻译文件
                                original_backup = os.path.join(result_folder, f"{task_id}_original.pdf")
                                shutil.copy2(result_path, original_backup)
                                # 用后处理结果替换原始结果
                                shutil.move(post_processed_path, result_path)
                            else:
                                logger.warning(f"后处理失败，将使用原始翻译结果")
                        except Exception as e:
                            logger.exception(f"后处理过程中发生错误: {str(e)}")
                    
                    return result_path
            
            # 然后检查当前工作目录
            for filename in potential_files:
                curr_dir_path = os.path.join(os.getcwd(), filename)
                if os.path.exists(curr_dir_path):
                    # 移动文件到结果目录
                    shutil.move(curr_dir_path, result_path)
                    logger.info(f"在当前目录找到并移动生成的文件: {curr_dir_path} -> {result_path}")
                    
                    # 后处理：去除斜杠标记
                    if post_process and format == 'mono':
                        try:
                            logger.info(f"开始对文件进行后处理以去除斜杠标记: {result_path}")
                            post_processed_path = os.path.join(result_folder, f"{task_id}_processed.pdf")
                            if remove_slash_marks(result_path, post_processed_path):
                                logger.info(f"后处理成功，更新结果文件: {post_processed_path}")
                                # 备份原始翻译文件
                                original_backup = os.path.join(result_folder, f"{task_id}_original.pdf")
                                shutil.copy2(result_path, original_backup)
                                # 用后处理结果替换原始结果
                                shutil.move(post_processed_path, result_path)
                            else:
                                logger.warning(f"后处理失败，将使用原始翻译结果")
                        except Exception as e:
                            logger.exception(f"后处理过程中发生错误: {str(e)}")
                    
                    return result_path
            
            logger.error(f"pdf2zh成功执行，但结果文件不存在: {result_path}")
            logger.error(f"已检查输出目录: {result_folder}")
            logger.error(f"已检查当前目录: {os.getcwd()}")
            return None
            
    except Exception as e:
        logger.exception(f"翻译过程中发生错误: {str(e)}")
        return None

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PDF翻译桥接服务')
    parser.add_argument('--port', type=int, default=5000, help='服务端口号')
    parser.add_argument('pdf_file', nargs='?', help='要翻译的PDF文件路径')
    
    args = parser.parse_args()
    
    if args.pdf_file:
        # 如果提供了PDF文件，直接翻译它
        result = translate_document(args.pdf_file)
        if result:
            print(f"翻译完成，结果保存在: {result}")
            return 0
        else:
            print("翻译失败")
            return 1
    else:
        # 导入Flask并启动服务
        try:
            from flask import Flask, request, jsonify, send_from_directory
            from flask_cors import CORS
            from werkzeug.utils import secure_filename
            import uuid
            
            # 项目根目录，用于服务静态文件
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 上传目录
            UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # 保存任务状态
            tasks = {}
            
            app = Flask(__name__, static_folder=project_root, static_url_path='')
            CORS(app)
            
            # 允许上传的文件类型
            ALLOWED_EXTENSIONS = {'pdf'}
            
            def allowed_file(filename):
                return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
            
            @app.route('/')
            def index():
                return app.send_static_file('index.html')
                
            @app.route('/translate.html')
            def translate_page():
                return app.send_static_file('translate.html')
            
            @app.route('/api/health')
            def health():
                return jsonify({"message": "PDF翻译服务后端", "status": "运行中"})
            
            @app.route('/api/upload', methods=['POST'])
            def upload_file():
                # 检查是否有文件
                if 'file' not in request.files:
                    return jsonify({"error": "没有文件"}), 400
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({"error": "未选择文件"}), 400
                
                if file and allowed_file(file.filename):
                    # 生成唯一的任务ID
                    task_id = str(uuid.uuid4())
                    
                    # 安全地获取文件名
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
                    
                    # 保存文件
                    file.save(file_path)
                    
                    # 初始化任务状态
                    tasks[task_id] = {
                        "id": task_id,
                        "filename": filename,
                        "original_path": file_path,
                        "result_path": None,
                        "status": "pending",
                        "message": "任务已创建"
                    }
                    
                    logger.info(f"文件已上传: {file_path}, 任务ID: {task_id}")
                    
                    return jsonify({
                        "task_id": task_id,
                        "status": "pending",
                        "message": "文件上传成功，等待处理"
                    })
                
                return jsonify({"error": "不支持的文件类型"}), 400
            
            @app.route('/api/translate', methods=['POST'])
            def api_translate():
                data = request.json
                if not data:
                    return jsonify({"error": "无效的请求数据"}), 400
                
                task_id = data.get('task_id')
                source_lang = data.get('source_lang', 'en')
                target_lang = data.get('target_lang', 'zh')
                provider = data.get('provider', 'deepseek')
                model = data.get('model', 'deepseek-chat')
                output_format = data.get('format', 'dual')  # 新增格式参数
                post_process = data.get('post_process', True)  # 新增后处理参数
                force = data.get('force', False)  # 新增强制重新翻译参数
                
                if output_format not in ['mono', 'dual']:
                    output_format = 'dual'  # 默认使用中英对照格式
                
                if not task_id or task_id not in tasks:
                    return jsonify({"error": "无效的任务ID"}), 400
                
                task = tasks[task_id]
                
                if task['status'] not in ['pending', 'failed'] and not force:
                    # 如果任务已经完成，并且不是强制重新翻译，则直接返回现有结果
                    if task['status'] == 'completed':
                        return jsonify({
                            "task_id": task_id,
                            "status": task['status'],
                            "message": "翻译已完成",
                            "reused": True
                        })
                    return jsonify({"error": f"任务状态为 {task['status']}，无法开始翻译"}), 400
                
                # 更新任务状态
                task['status'] = 'processing'
                task['message'] = "翻译处理中..."
                
                logger.info(f"开始翻译任务 {task_id}, 源语言: {source_lang}, 目标语言: {target_lang}, 提供商: {provider}, 格式: {output_format}, 后处理: {post_process}, 强制重新翻译: {force}")
                
                try:
                    # 调用翻译函数
                    result_path = translate_document(
                        task['original_path'],
                        task_id=task_id,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        provider=provider,
                        model=model,
                        format=output_format,
                        post_process=post_process,
                        force=force
                    )
                    
                    if result_path:
                        task['result_path'] = result_path
                        task['status'] = 'completed'
                        task['message'] = "翻译完成"
                        logger.info(f"任务 {task_id} 翻译完成: {result_path}")
                    else:
                        task['status'] = 'failed'
                        task['message'] = "翻译失败"
                        logger.error(f"任务 {task_id} 翻译失败")
                    
                    return jsonify({
                        "task_id": task_id,
                        "status": task['status'],
                        "message": task['message']
                    })
                except Exception as e:
                    logger.exception(f"启动翻译任务 {task_id} 时出错: {str(e)}")
                    task['status'] = 'failed'
                    task['message'] = f"启动翻译失败: {str(e)}"
                    return jsonify({"error": str(e)}), 500
            
            # 添加/api/translate_document路径（与/api/translate功能相同，用于兼容）
            @app.route('/api/translate_document', methods=['POST'])
            def api_translate_document():
                return api_translate()
            
            @app.route('/api/files/<task_id>', methods=['GET'])
            def get_original_file(task_id):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                if not os.path.exists(task['original_path']):
                    return jsonify({"error": "原始文件不存在"}), 404
                
                return send_from_directory(
                    os.path.dirname(task['original_path']), 
                    os.path.basename(task['original_path']), 
                    as_attachment=False
                )
            
            @app.route('/api/translated_files/<task_id>/<filename>', methods=['GET'])
            def get_translated_file(task_id, filename):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                
                if task['status'] != 'completed':
                    return jsonify({"error": "翻译尚未完成"}), 400
                
                if not task['result_path'] or not os.path.exists(task['result_path']):
                    return jsonify({"error": "翻译结果不存在"}), 404
                
                # 根据filename参数决定返回哪个版本的翻译文件
                result_folder = os.path.join(RESULT_FOLDER, task_id)
                
                # 根据请求的文件名确定要返回的文件
                if filename == 'mono.pdf':
                    # 请求单语言版本
                    mono_filename = f"{task_id}_translated_mono.pdf"
                    mono_path = os.path.join(result_folder, mono_filename)
                    if os.path.exists(mono_path):
                        return send_from_directory(result_folder, mono_filename, as_attachment=False)
                elif filename == 'dual.pdf':
                    # 请求双语言版本
                    dual_filename = f"{task_id}_translated_dual.pdf"
                    dual_path = os.path.join(result_folder, dual_filename)
                    if os.path.exists(dual_path):
                        return send_from_directory(result_folder, dual_filename, as_attachment=False)
                
                # 如果找不到特定版本，返回默认结果
                return send_from_directory(
                    os.path.dirname(task['result_path']), 
                    os.path.basename(task['result_path']), 
                    as_attachment=False
                )
            
            @app.route('/api/tasks/<task_id>', methods=['GET'])
            def get_task(task_id):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                return jsonify({
                    "task_id": task['id'],
                    "filename": task['filename'],
                    "status": task['status'],
                    "message": task['message']
                })
            
            @app.route('/api/download/<task_id>', methods=['GET'])
            def download_result(task_id):
                if task_id not in tasks:
                    return jsonify({"error": "任务不存在"}), 404
                
                task = tasks[task_id]
                
                if task['status'] != 'completed':
                    return jsonify({"error": "翻译尚未完成"}), 400
                
                if not task['result_path'] or not os.path.exists(task['result_path']):
                    return jsonify({"error": "结果文件不存在"}), 404
                
                result_dir = os.path.dirname(task['result_path'])
                result_filename = os.path.basename(task['result_path'])
                
                return send_from_directory(result_dir, result_filename, as_attachment=True)
            
            @app.route('/api/check_translation/<task_id>', methods=['GET'])
            def check_translation(task_id):
                """检查特定任务是否已经有翻译结果"""
                if task_id not in tasks:
                    # 尝试检查结果目录是否有对应的文件，可能是从之前的会话保存的
                    result_folder = os.path.join(RESULT_FOLDER, task_id)
                    
                    if os.path.exists(result_folder):
                        # 如果结果文件夹存在，检查是否有翻译文件
                        mono_path = os.path.join(result_folder, f"{task_id}_translated_mono.pdf")
                        dual_path = os.path.join(result_folder, f"{task_id}_translated_dual.pdf")
                        
                        has_mono = os.path.exists(mono_path)
                        has_dual = os.path.exists(dual_path)
                        
                        if has_mono or has_dual:
                            # 找到了翻译文件，将任务添加到tasks字典
                            # 尝试找到原始文件
                            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
                            original_files = [f for f in os.listdir(uploads_dir) if f.startswith(task_id)]
                            
                            original_path = None
                            filename = "unknown.pdf"
                            
                            if original_files:
                                original_path = os.path.join(uploads_dir, original_files[0])
                                filename = original_files[0].replace(f"{task_id}_", "")
                            
                            # 创建任务记录
                            tasks[task_id] = {
                                "id": task_id,
                                "filename": filename,
                                "original_path": original_path,
                                "result_path": dual_path if has_dual else mono_path,
                                "status": "completed",
                                "message": "已从之前的会话恢复任务"
                            }
                            
                            logger.info(f"从结果目录恢复了任务 {task_id}")
                            
                            return jsonify({
                                "exists": True,
                                "formats": {
                                    "mono": has_mono,
                                    "dual": has_dual
                                },
                                "status": "completed"
                            })
                
                task = tasks[task_id]
                
                # 检查是否有结果文件
                result_folder = os.path.join(RESULT_FOLDER, task_id)
                
                # 检查mono和dual两种格式
                mono_path = os.path.join(result_folder, f"{task_id}_translated_mono.pdf")
                dual_path = os.path.join(result_folder, f"{task_id}_translated_dual.pdf")
                
                has_mono = os.path.exists(mono_path)
                has_dual = os.path.exists(dual_path)
                
                if has_mono or has_dual:
                    # 如果找到了翻译文件，但任务状态不是completed，更新状态
                    if task['status'] != 'completed':
                        task['status'] = 'completed'
                        task['message'] = '翻译完成'
                        task['result_path'] = dual_path if has_dual else mono_path
                    
                    return jsonify({
                        "exists": True,
                        "formats": {
                            "mono": has_mono,
                            "dual": has_dual
                        },
                        "status": task['status']
                    })
                
                return jsonify({"exists": False, "status": task['status']})
            
            @app.route('/api/latest_file', methods=['GET'])
            def get_latest_file():
                """获取最新上传的文件信息"""
                if not tasks:
                    # 尝试从结果目录获取文件信息
                    try:
                        result_dirs = os.listdir(RESULT_FOLDER)
                        if not result_dirs:
                            return jsonify({"error": "没有上传的文件"}), 404
                        
                        # 按照修改时间排序
                        result_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(RESULT_FOLDER, x)), reverse=True)
                        
                        # 检查第一个（最新的）目录
                        latest_dir = result_dirs[0]
                        latest_task_id = latest_dir
                        
                        # 查找是否有翻译文件
                        dual_path = os.path.join(RESULT_FOLDER, latest_dir, f"{latest_task_id}_translated_dual.pdf")
                        mono_path = os.path.join(RESULT_FOLDER, latest_dir, f"{latest_task_id}_translated_mono.pdf")
                        
                        # 如果没有找到文件，返回错误
                        if not (os.path.exists(dual_path) or os.path.exists(mono_path)):
                            return jsonify({"error": "未找到翻译文件"}), 404
                        
                        # 尝试找到原始文件
                        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
                        original_files = [f for f in os.listdir(uploads_dir) if f.startswith(latest_task_id)]
                        
                        filename = "unknown.pdf"
                        original_path = None
                        
                        if original_files:
                            original_path = os.path.join(uploads_dir, original_files[0])
                            filename = original_files[0].replace(f"{latest_task_id}_", "")
                        
                        # 将任务添加到tasks字典
                        tasks[latest_task_id] = {
                            "id": latest_task_id,
                            "filename": filename,
                            "original_path": original_path,
                            "result_path": dual_path if os.path.exists(dual_path) else mono_path,
                            "status": "completed",
                            "message": "已从结果目录恢复任务"
                        }
                        
                        logger.info(f"从结果目录恢复了最新任务 {latest_task_id}")
                        
                        # 返回任务信息
                        content_summary = {
                            "title": os.path.splitext(filename)[0],
                            "total_pages": "未知",
                            "has_abstract": False,
                            "sections_count": 0
                        }
                        
                        return jsonify({
                            "task_id": latest_task_id,
                            "filename": filename,
                            "status": "completed",
                            "content_summary": content_summary
                        })
                    except Exception as e:
                        logger.exception(f"从结果目录恢复任务出错: {str(e)}")
                        return jsonify({"error": "没有上传的文件"}), 404
                
                # 按照上传时间排序，获取最新的任务
                latest_task_id = None
                latest_task = None
                latest_time = 0
                
                for task_id, task in tasks.items():
                    # 获取文件的创建时间
                    try:
                        file_time = os.path.getctime(task['original_path']) if task['original_path'] else 0
                        if file_time > latest_time:
                            latest_time = file_time
                            latest_task_id = task_id
                            latest_task = task
                    except (OSError, KeyError):
                        continue
                
                if not latest_task_id:
                    return jsonify({"error": "无法确定最新文件"}), 404
                
                # 获取文件信息
                try:
                    # 这里可以添加更多的文件信息，如标题，页数等
                    content_summary = {
                        "title": os.path.splitext(latest_task['filename'])[0],
                        "total_pages": "未知",  # 这里可以用PyPDF2等工具获取实际页数
                        "has_abstract": False,
                        "sections_count": 0
                    }
                    
                    return jsonify({
                        "task_id": latest_task_id,
                        "filename": latest_task['filename'],
                        "status": latest_task['status'],
                        "content_summary": content_summary
                    })
                except Exception as e:
                    logger.exception(f"获取最新文件信息出错: {str(e)}")
                    return jsonify({"error": str(e)}), 500
            
            logger.info(f"启动服务于端口 {args.port}")
            app.run(host='0.0.0.0', port=args.port)
            
        except ImportError:
            logger.error("无法导入Flask或CORS，请安装它们: pip install flask flask-cors")
            return 1

if __name__ == "__main__":
    import sys
    sys.exit(main()) 