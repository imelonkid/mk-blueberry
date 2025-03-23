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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("pdf_translator_bridge")

# 结果文件夹
RESULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(RESULT_FOLDER, exist_ok=True)

def translate_document(pdf_path, task_id=None, source_lang='en', target_lang='zh', provider='deepseek', model='deepseek-chat', format='dual'):
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
                    return result_path
            
            # 然后检查当前工作目录
            for filename in potential_files:
                curr_dir_path = os.path.join(os.getcwd(), filename)
                if os.path.exists(curr_dir_path):
                    # 移动文件到结果目录
                    shutil.move(curr_dir_path, result_path)
                    logger.info(f"在当前目录找到并移动生成的文件: {curr_dir_path} -> {result_path}")
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
                
                if output_format not in ['mono', 'dual']:
                    output_format = 'dual'  # 默认使用中英对照格式
                
                if not task_id or task_id not in tasks:
                    return jsonify({"error": "无效的任务ID"}), 400
                
                task = tasks[task_id]
                
                if task['status'] not in ['pending', 'failed']:
                    return jsonify({"error": f"任务状态为 {task['status']}，无法开始翻译"}), 400
                
                # 更新任务状态
                task['status'] = 'processing'
                task['message'] = "翻译处理中..."
                
                logger.info(f"开始翻译任务 {task_id}, 源语言: {source_lang}, 目标语言: {target_lang}, 提供商: {provider}, 格式: {output_format}")
                
                try:
                    # 调用翻译函数
                    result_path = translate_document(
                        task['original_path'],
                        task_id=task_id,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        provider=provider,
                        model=model,
                        format=output_format  # 传递格式参数
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
                
                # 由于我们只生成了一个翻译文件，这里暂时假设要无论请求的是哪个文件，都返回唯一的翻译结果
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
            
            logger.info(f"启动服务于端口 {args.port}")
            app.run(host='0.0.0.0', port=args.port)
            
        except ImportError:
            logger.error("无法导入Flask或CORS，请安装它们: pip install flask flask-cors")
            return 1

if __name__ == "__main__":
    import sys
    sys.exit(main()) 