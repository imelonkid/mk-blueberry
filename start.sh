#!/bin/bash

# PaperTrans 启动脚本
# 启动后端服务和提供静态文件访问

# 定义颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 定义变量
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR"
LOG_FILE="$SCRIPT_DIR/papertrans.log"
PID_FILE="$SCRIPT_DIR/.papertrans.pid"

# 设置默认端口
PORT=8000

# 从.env文件中加载环境变量（如果存在）
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${BLUE}从.env文件加载配置...${NC}"
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# 如果环境变量中设置了PORT，则使用该值
if [ ! -z "${PORT}" ]; then
    echo -e "${BLUE}使用端口: ${PORT}${NC}"
fi

# 激活Python 3.10环境
export PATH="/Users/melonkid/opt/anaconda3/bin:$PATH"
source /Users/melonkid/opt/anaconda3/etc/profile.d/conda.sh
conda activate py310

# 设置API密钥（如果.env中未设置则使用默认值）
if [ -z "${DEEPSEEK_API_KEY}" ]; then
    echo -e "${YELLOW}未在.env中找到DEEPSEEK_API_KEY，请在.env文件中配置${NC}"
fi

if [ -z "${OPENAI_API_KEY}" ]; then
    # 如果设置了DEEPSEEK_API_KEY，同时将其用于OPENAI_API_KEY
    if [ ! -z "${DEEPSEEK_API_KEY}" ]; then
        echo -e "${YELLOW}未设置OPENAI_API_KEY，使用DEEPSEEK_API_KEY作为替代${NC}"
        export OPENAI_API_KEY="${DEEPSEEK_API_KEY}"
    else
        echo -e "${YELLOW}未在.env中找到OPENAI_API_KEY，请在.env文件中配置${NC}"
    fi
fi

# 显示启动标识
echo -e "
  ${BLUE}_____                      _______                    ${NC}
 ${BLUE}|  __ \\                    |__   __|                   ${NC}
 ${BLUE}| |__) |__ _ _ __   ___ _ __  | |_ __ __ _ _ __  ___  ${NC}
 ${BLUE}|  ___/ _\` | '_ \\ / _ \\ '__| | | '__/ _\` | '_ \\/ __| ${NC}
 ${BLUE}| |  | (_| | |_) |  __/ |    | | | | (_| | | | \\__ \\ ${NC}
 ${BLUE}|_|   \\__,_| .__/ \\___|_|    |_|_|  \\__,_|_| |_|___/ ${NC}
 ${BLUE}           | |                                        ${NC}
 ${BLUE}           |_|                                        ${NC}
    "
echo -e "${BLUE}PDF论文翻译工具 - 启动脚本${NC}\n"

# 检查pid文件是否存在，如果存在则表示服务可能已运行
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null; then
        echo -e "${YELLOW}检测到PaperTrans服务可能已在运行（PID: $PID）${NC}"
        read -p "是否继续启动新实例？ (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}操作已取消${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}检测到过时的PID文件，将继续启动服务${NC}"
    fi
fi

echo -e "${BLUE}启动PDF翻译后端服务...${NC}"

# 清除日志文件
> "$LOG_FILE"

# 启动后端服务 - 直接调用pdf_translator_bridge.py
cd "$BACKEND_DIR"
nohup python pdf_translator_bridge.py --port "$PORT" > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

# 等待服务启动
echo -e "${YELLOW}等待服务启动...${NC}"
sleep 3

# 检查服务是否成功启动
if ps -p $PID > /dev/null; then
    echo -e "${GREEN}PDF翻译服务已成功启动 (PID: $PID)${NC}"
    echo -e "${YELLOW}日志文件: $LOG_FILE${NC}\n"
    echo -e "${GREEN}服务已启动!${NC}"
    echo -e "${BLUE}请在浏览器中访问: http://localhost:$PORT/translate.html${NC}\n"
    echo -e "${YELLOW}要停止服务，请运行 stop.sh 脚本或关闭服务窗口${NC}"
else
    echo -e "${RED}服务启动失败，请检查日志文件了解详情: $LOG_FILE${NC}"
    exit 1
fi 