#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pdf_translator_bridge

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
RESULT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 限制上传文件大小为50MB

# 存储任务状态
# 状态: 'pending', 'processing', 'completed', 'failed'
TASKS = {}

# 获取环境变量
def get_env_variable(var_name, default_value=None):
    value = os.environ.get(var_name, default_value)
    if value is None:
        logger.warning(f"环境变量 {var_name} 未设置，使用None值")
    return value

# 路由：首页
@app.route('/')
def index():
    return jsonify({"message": "PDF翻译服务后端API", "status": "运行中"})

# 路由：上传PDF文件
@app.route('/upload', methods=['POST'])
def upload_file():
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400
    
    if file:
        # 生成唯一的任务ID
        task_id = str(uuid.uuid4())
        
        # 安全地获取文件名
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
        
        # 保存文件
        file.save(file_path)
        
        # 初始化任务状态
        TASKS[task_id] = {
            "id": task_id,
            "filename": filename,
            "original_path": file_path,
            "result_path": None,
            "status": "pending",
            "message": "任务已创建",
            "created_at": datetime.now().isoformat(),
            "completed_at": None
        }
        
        logger.info(f"文件已上传: {file_path}, 任务ID: {task_id}")
        
        return jsonify({
            "task_id": task_id,
            "message": "文件上传成功，等待处理"
        })

# 路由：开始翻译
@app.route('/translate', methods=['POST'])
def translate():
    data = request.json
    task_id = data.get('task_id')
    source_lang = data.get('source_lang', 'en')
    target_lang = data.get('target_lang', 'zh')
    provider = data.get('provider', 'deepseek')
    model = data.get('model', 'deepseek-chat')
    
    if not task_id or task_id not in TASKS:
        return jsonify({"error": "无效的任务ID"}), 400
    
    task = TASKS[task_id]
    
    if task['status'] not in ['pending', 'failed']:
        return jsonify({"error": f"任务状态为 {task['status']}，无法开始翻译"}), 400
    
    # 更新任务状态
    task['status'] = 'processing'
    task['message'] = "翻译处理中..."
    
    logger.info(f"开始翻译任务 {task_id}, 源语言: {source_lang}, 目标语言: {target_lang}, 提供商: {provider}")
    
    try:
        # 异步调用翻译（实际上是同步的，但是我们假装它是异步的）
        def process_translation():
            try:
                result_path = pdf_translator_bridge.translate_document(
                    task['original_path'],
                    task_id=task_id,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    provider=provider,
                    model=model
                )
                
                if result_path:
                    task['result_path'] = result_path
                    task['status'] = 'completed'
                    task['message'] = "翻译完成"
                    task['completed_at'] = datetime.now().isoformat()
                    logger.info(f"任务 {task_id} 翻译完成: {result_path}")
                else:
                    task['status'] = 'failed'
                    task['message'] = "翻译失败"
                    logger.error(f"任务 {task_id} 翻译失败")
            except Exception as e:
                task['status'] = 'failed'
                task['message'] = f"翻译出错: {str(e)}"
                logger.exception(f"任务 {task_id} 翻译出错: {str(e)}")
        
        # 实际上同步执行，但为了API设计一致性，我们假装它是异步的
        process_translation()
        
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

# 路由：获取任务状态
@app.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    if task_id not in TASKS:
        return jsonify({"error": "任务不存在"}), 404
    
    task = TASKS[task_id]
    return jsonify({
        "task_id": task['id'],
        "filename": task['filename'],
        "status": task['status'],
        "message": task['message'],
        "created_at": task['created_at'],
        "completed_at": task['completed_at']
    })

# 路由：下载翻译结果
@app.route('/download/<task_id>', methods=['GET'])
def download_result(task_id):
    if task_id not in TASKS:
        return jsonify({"error": "任务不存在"}), 404
    
    task = TASKS[task_id]
    
    if task['status'] != 'completed':
        return jsonify({"error": "翻译尚未完成"}), 400
    
    if not task['result_path'] or not os.path.exists(task['result_path']):
        return jsonify({"error": "结果文件不存在"}), 404
    
    result_dir = os.path.dirname(task['result_path'])
    result_filename = os.path.basename(task['result_path'])
    
    return send_from_directory(result_dir, result_filename, as_attachment=True)

# 路由：获取所有任务列表
@app.route('/tasks', methods=['GET'])
def list_tasks():
    tasks_list = []
    for task_id, task in TASKS.items():
        tasks_list.append({
            "task_id": task['id'],
            "filename": task['filename'],
            "status": task['status'],
            "message": task['message'],
            "created_at": task['created_at'],
            "completed_at": task['completed_at']
        })
    
    return jsonify({"tasks": tasks_list})

# 启动服务
if __name__ == '__main__':
    logger.info("PDF翻译服务后端启动中...")
    
    # 获取端口配置
    port = int(get_env_variable('PORT', 5000))
    host = get_env_variable('HOST', '0.0.0.0')
    
    logger.info(f"服务将在 {host}:{port} 上启动")
    app.run(host=host, port=port, debug=False) 