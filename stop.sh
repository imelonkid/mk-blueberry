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

# 激活Python 3.10环境
export PATH="/Users/melonkid/opt/anaconda3/bin:$PATH"
source /Users/melonkid/opt/anaconda3/etc/profile.d/conda.sh
conda activate py310

echo -e "${BLUE}停止 PaperTrans 服务...${NC}"

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}未找到PID文件，服务可能未运行${NC}"
    exit 0
fi

# 读取PID文件
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ! ps -p $PID > /dev/null; then
    echo -e "${YELLOW}进程 $PID 不存在，可能已停止${NC}"
    rm -f "$PID_FILE"
    exit 0
fi

# 直接停止进程
echo -e "${YELLOW}正在停止进程 $PID...${NC}"
kill $PID

# 等待进程停止
MAX_WAIT=10
for i in $(seq 1 $MAX_WAIT); do
    if ! ps -p $PID > /dev/null; then
        echo -e "${GREEN}服务已成功停止${NC}"
        rm -f "$PID_FILE"
        exit 0
    fi
    echo -e "${YELLOW}等待进程停止 ($i/$MAX_WAIT)...${NC}"
    sleep 1
done

# 如果进程仍在运行，强制终止
if ps -p $PID > /dev/null; then
    echo -e "${RED}服务未响应，尝试强制终止...${NC}"
    kill -9 $PID
    sleep 1
    if ! ps -p $PID > /dev/null; then
        echo -e "${GREEN}服务已强制停止${NC}"
    else
        echo -e "${RED}无法停止服务，请手动终止进程 $PID${NC}"
    fi
fi

# 清除PID文件
rm -f "$PID_FILE" 