#!/bin/bash

# 加载环境变量
if [ -f .env ]; then
    echo "从.env文件加载环境变量..."
    export $(grep -v '^#' .env | xargs)
else
    echo "警告：未找到.env文件，使用默认配置..."
fi

# 检查目录
UPLOAD_DIR=${UPLOAD_FOLDER:-"uploads"}
if [ ! -d "$UPLOAD_DIR" ]; then
    echo "创建上传目录: $UPLOAD_DIR"
    mkdir -p "$UPLOAD_DIR"
fi

# 启动服务
echo "启动PaperTrans API服务..."
if [ "$FLASK_ENV" = "production" ]; then
    echo "以生产模式启动..."
    gunicorn -b ${HOST:-0.0.0.0}:${PORT:-5000} api:app
else
    echo "以开发模式启动..."
    python api.py --host ${HOST:-0.0.0.0} --port ${PORT:-5000} --debug
fi 