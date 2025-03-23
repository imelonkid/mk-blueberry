#!/bin/bash

# PaperTrans 停止脚本
# 停止PDF翻译服务

# 定义颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 定义变量
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_FILE="$SCRIPT_DIR/.papertrans.pid"

# 从.env文件中加载环境变量（如果存在）获取PORT
PORT=8000
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

echo -e "${BLUE}停止 PaperTrans 服务...${NC}"

# 方法1：从PID文件中获取进程ID并停止
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null; then
        echo -e "${YELLOW}正在停止进程 $PID...${NC}"
        kill $PID
        sleep 2
        
        # 检查进程是否还在运行，如果是，强制终止
        if ps -p $PID > /dev/null; then
            echo -e "${YELLOW}进程仍在运行，正在强制终止...${NC}"
            kill -9 $PID
            sleep 1
        fi
        
        # 再次检查进程状态
        if ! ps -p $PID > /dev/null; then
            echo -e "${GREEN}服务已成功停止${NC}"
        else
            echo -e "${RED}无法停止进程 $PID${NC}"
        fi
    else
        echo -e "${YELLOW}未找到进程 $PID${NC}"
    fi
    
    # 删除PID文件
    rm -f "$PID_FILE"
fi

# 方法2：根据端口号查找并停止进程
echo -e "${YELLOW}检查端口 $PORT 是否仍被占用...${NC}"
PORT_PID=$(lsof -t -i:$PORT 2>/dev/null)

if [ ! -z "$PORT_PID" ]; then
    echo -e "${YELLOW}找到端口 $PORT 被进程 $PORT_PID 占用，正在终止...${NC}"
    kill $PORT_PID 2>/dev/null
    sleep 2
    
    # 如果进程仍在运行，强制终止
    if lsof -t -i:$PORT >/dev/null 2>&1; then
        echo -e "${YELLOW}进程仍在监听端口，尝试强制终止...${NC}"
        kill -9 $PORT_PID 2>/dev/null
        sleep 1
    fi
    
    # 再次检查端口
    if ! lsof -t -i:$PORT >/dev/null 2>&1; then
        echo -e "${GREEN}端口 $PORT 已成功释放${NC}"
    else
        echo -e "${RED}警告: 无法释放端口 $PORT${NC}"
    fi
fi

# 方法3：查找任何可能的Python进程，它们可能与服务相关
echo -e "${YELLOW}检查可能遗留的PaperTrans Python进程...${NC}"
PYTHON_PIDS=$(ps aux | grep "[p]df_translator_bridge" | awk '{print $2}')

if [ ! -z "$PYTHON_PIDS" ]; then
    echo -e "${YELLOW}找到相关Python进程，正在终止...${NC}"
    for PY_PID in $PYTHON_PIDS; do
        kill $PY_PID 2>/dev/null
        sleep 1
        kill -9 $PY_PID 2>/dev/null 2>&1
    done
    echo -e "${GREEN}已终止所有相关Python进程${NC}"
fi

echo -e "${GREEN}服务已成功停止${NC}" 