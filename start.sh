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

# 预检查：确保端口未被占用
PORT_PID=$(lsof -t -i:$PORT 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo -e "${YELLOW}警告: 端口 $PORT 已被进程 $PORT_PID 占用${NC}"
    read -p "是否尝试释放端口并继续? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}尝试释放端口...${NC}"
        kill $PORT_PID 2>/dev/null
        sleep 2
        
        # 如果正常终止失败，尝试强制终止
        if lsof -t -i:$PORT >/dev/null 2>&1; then
            echo -e "${YELLOW}正常终止失败，尝试强制终止...${NC}"
            kill -9 $PORT_PID 2>/dev/null
            sleep 1
            
            # 再次检查
            if lsof -t -i:$PORT >/dev/null 2>&1; then
                echo -e "${RED}错误: 无法释放端口 $PORT，请手动关闭占用该端口的程序或更改端口号${NC}"
                exit 1
            else
                echo -e "${GREEN}端口已成功释放${NC}"
            fi
        else
            echo -e "${GREEN}端口已成功释放${NC}"
        fi
    else
        echo -e "${RED}操作已取消${NC}"
        exit 1
    fi
fi

# Python环境激活
echo -e "${BLUE}准备Python环境...${NC}"

# 首先尝试检查虚拟环境
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo -e "${GREEN}发现虚拟环境，尝试激活...${NC}"
    if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
        source "$SCRIPT_DIR/venv/bin/activate"
        echo -e "${GREEN}虚拟环境激活成功${NC}"
    else
        echo -e "${YELLOW}警告: 虚拟环境目录存在，但无法找到激活脚本${NC}"
    fi
fi

# 然后尝试conda环境（作为备选）
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${YELLOW}未找到python3命令，尝试激活conda环境...${NC}"
    
    # 优先使用本地安装的conda
    CONDA_PATHS=(
        "/Users/melonkid/opt/anaconda3/etc/profile.d/conda.sh"
        "$HOME/anaconda3/etc/profile.d/conda.sh"
        "$HOME/miniconda3/etc/profile.d/conda.sh"
        "/opt/anaconda3/etc/profile.d/conda.sh"
        "/usr/local/anaconda3/etc/profile.d/conda.sh"
        "/usr/local/opt/conda/etc/profile.d/conda.sh"
    )
    
    for CONDA_SH in "${CONDA_PATHS[@]}"; do
        if [ -f "$CONDA_SH" ]; then
            echo -e "${GREEN}找到conda: $CONDA_SH${NC}"
            source "$CONDA_SH"
            # 尝试激活环境
            if conda info --envs | grep -q "py310"; then
                conda activate py310
                echo -e "${GREEN}已激活conda环境: py310${NC}"
            elif conda info --envs | grep -q "base"; then
                conda activate base
                echo -e "${GREEN}已激活conda基础环境${NC}"
            else
                echo -e "${YELLOW}未找到匹配的conda环境，使用系统Python${NC}"
            fi
            break
        fi
    done
fi

# 检查pdf2zh命令是否可用
echo -e "${BLUE}检查pdf2zh命令是否可用...${NC}"
if command -v pdf2zh >/dev/null 2>&1; then
    echo -e "${GREEN}pdf2zh命令可用: $(which pdf2zh)${NC}"
else
    echo -e "${YELLOW}警告: pdf2zh命令不可用，尝试安装...${NC}"
    pip install -e git+https://github.com/zouweidong91/paper2translate.git#egg=paper2translate || {
        echo -e "${RED}安装pdf2zh失败。服务可能无法正常工作。${NC}"
        echo -e "${YELLOW}请手动执行: pip install -e git+https://github.com/zouweidong91/paper2translate.git#egg=paper2translate${NC}"
    }
    
    # 再次检查
    if command -v pdf2zh >/dev/null 2>&1; then
        echo -e "${GREEN}pdf2zh命令安装成功: $(which pdf2zh)${NC}"
    else
        echo -e "${YELLOW}pdf2zh命令仍不可用，但将继续启动服务${NC}"
    fi
fi

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

# 显示当前环境信息
echo -e "${BLUE}当前Python环境:${NC} $(which python)"
echo -e "${BLUE}Python版本:${NC} $(python --version 2>&1)"
echo -e "${BLUE}PATH环境变量:${NC} $PATH"
echo -e "${BLUE}当前工作目录:${NC} $(pwd)"

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
    # 进一步验证端口是否被我们的进程监听
    LISTENING_PID=$(lsof -t -i:$PORT 2>/dev/null)
    if [ "$LISTENING_PID" = "$PID" ] || [ -z "$LISTENING_PID" ]; then
        echo -e "${GREEN}PDF翻译服务已成功启动 (PID: $PID)${NC}"
        echo -e "${YELLOW}日志文件: $LOG_FILE${NC}\n"
        echo -e "${GREEN}服务已启动!${NC}"
        echo -e "${BLUE}请在浏览器中访问: http://localhost:$PORT/translate.html${NC}\n"
        echo -e "${YELLOW}要停止服务，请运行 stop.sh 脚本或关闭服务窗口${NC}"
    else
        echo -e "${RED}服务进程已启动，但不是监听端口 $PORT 的进程${NC}"
        echo -e "${YELLOW}日志文件: $LOG_FILE${NC}"
        # 检查日志文件中的错误
        if [ -f "$LOG_FILE" ]; then
            echo -e "${YELLOW}日志文件最后几行:${NC}"
            tail -n 10 "$LOG_FILE"
        fi
        exit 1
    fi
else
    echo -e "${RED}服务启动失败，请检查日志文件了解详情: $LOG_FILE${NC}"
    # 显示日志文件的最后几行
    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}日志文件最后几行:${NC}"
        tail -n 10 "$LOG_FILE"
    fi
    exit 1
fi 