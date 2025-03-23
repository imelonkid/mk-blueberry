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

# 记录系统信息
echo -e "${BLUE}系统信息:${NC}"
uname -a
cat /etc/os-release 2>/dev/null || echo "无法获取OS发行版信息"
if [ -f /etc/centos-release ]; then
    echo -e "${YELLOW}检测到CentOS系统:${NC}"
    cat /etc/centos-release
fi

# 检查多个可能的pdf2zh路径
PDF2ZH_PATHS=(
    "pdf2zh"
    "$HOME/.local/bin/pdf2zh"
    "$HOME/.pyenv/shims/pdf2zh"
    "$HOME/.pyenv/versions/*/bin/pdf2zh"
    "$SCRIPT_DIR/venv/bin/pdf2zh"
    "/usr/local/bin/pdf2zh"
    "/usr/bin/pdf2zh"
    "/opt/python*/bin/pdf2zh"
    "/root/.local/bin/pdf2zh"
    "$SCRIPT_DIR/bin/pdf2zh"
    "$(dirname $SCRIPT_DIR)/bin/pdf2zh"
)

PDF2ZH_FOUND=false
for path in "${PDF2ZH_PATHS[@]}"; do
    # 处理通配符路径
    if [[ $path == *"*"* ]]; then
        echo -e "${YELLOW}检查通配符路径: $path${NC}"
        # 使用find命令查找匹配的文件
        for found_path in $(find ${path//\*/\*} -type f -name "pdf2zh" 2>/dev/null); do
            if [ -x "$found_path" ]; then
                echo -e "${GREEN}pdf2zh命令可用: $found_path${NC}"
                PDF2ZH_FOUND=true
                export PDF2ZH_PATH="$found_path"
                break 2
            fi
        done
    elif command -v "$path" >/dev/null 2>&1 || [ -x "$path" ]; then
        echo -e "${GREEN}pdf2zh命令可用: $path${NC}"
        PDF2ZH_FOUND=true
        # 将此路径设置为环境变量，供后端使用
        export PDF2ZH_PATH="$path"
        break
    else
        echo -e "${YELLOW}尝试的路径无效: $path${NC}"
    fi
done

if [ "$PDF2ZH_FOUND" = false ]; then
    echo -e "${YELLOW}警告: pdf2zh命令不可用，尝试安装...${NC}"
    
    # 确保Python环境可用
    if ! command -v python3 >/dev/null 2>&1; then
        if command -v python >/dev/null 2>&1; then
            PY_CMD="python"
            echo -e "${YELLOW}未找到python3命令，使用python命令${NC}"
        else
            echo -e "${RED}错误: 未找到python或python3命令，无法继续${NC}"
            
            # 针对CentOS系统提供安装指南
            if [ -f /etc/centos-release ] || grep -q "CentOS" /etc/os-release 2>/dev/null; then
                echo -e "${YELLOW}检测到CentOS系统，尝试安装Python...${NC}"
                echo -e "${YELLOW}您可能需要执行以下命令:${NC}"
                echo -e "  sudo yum install -y python3  # 安装Python 3"
                echo -e "或"
                echo -e "  sudo yum install -y python   # 安装Python 2"
            fi
            
            exit 1
        fi
    else
        PY_CMD="python3"
    fi
    
    # 输出Python版本
    $PY_CMD --version
    
    # 检查pip是否可用
    if ! $PY_CMD -m pip >/dev/null 2>&1; then
        echo -e "${RED}错误: pip不可用，请安装pip${NC}"
        
        # 针对CentOS系统提供安装指南
        if [ -f /etc/centos-release ] || grep -q "CentOS" /etc/os-release 2>/dev/null; then
            echo -e "${YELLOW}检测到CentOS系统，尝试安装pip...${NC}"
            echo -e "${YELLOW}您可能需要执行以下命令:${NC}"
            echo -e "  sudo yum install -y python3-pip  # 对于Python 3"
            echo -e "或"
            echo -e "  sudo yum install -y python-pip   # 对于Python 2"
            echo -e "或使用以下方法安装pip:"
            echo -e "  curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py"
            echo -e "  sudo $PY_CMD get-pip.py"
        fi
        
        exit 1
    fi
    
    # 在CentOS上可能需要额外的开发包
    if [ -f /etc/centos-release ] || grep -q "CentOS" /etc/os-release 2>/dev/null; then
        echo -e "${YELLOW}检测到CentOS系统，检查开发包...${NC}"
        # 检查是否安装了gcc和python开发包
        if ! command -v gcc >/dev/null 2>&1; then
            echo -e "${YELLOW}警告: gcc未安装，可能会影响pdf2zh的安装${NC}"
            echo -e "${YELLOW}建议执行: sudo yum install -y gcc${NC}"
        fi
        
        # 检查python-devel包
        if ! $PY_CMD -c "import distutils.core" >/dev/null 2>&1; then
            echo -e "${YELLOW}警告: Python开发包可能未安装，建议执行:${NC}"
            if [[ "$PY_CMD" == "python3" ]]; then
                echo -e "${YELLOW}sudo yum install -y python3-devel${NC}"
            else
                echo -e "${YELLOW}sudo yum install -y python-devel${NC}"
            fi
        fi
    fi
    
    # 尝试安装pdf2zh - 先使用--user方式安装
    echo -e "${YELLOW}尝试使用--user方式安装pdf2zh...${NC}"
    $PY_CMD -m pip install --user -e git+https://github.com/zouweidong91/paper2translate.git#egg=paper2translate || {
        echo -e "${YELLOW}使用--user方式安装失败，尝试普通安装...${NC}"
        $PY_CMD -m pip install -e git+https://github.com/zouweidong91/paper2translate.git#egg=paper2translate || {
            echo -e "${RED}安装pdf2zh失败。服务可能无法正常工作。${NC}"
            echo -e "${YELLOW}请手动执行: pip install -e git+https://github.com/zouweidong91/paper2translate.git#egg=paper2translate${NC}"
            echo -e "${YELLOW}如果安装失败，可能需要安装开发工具:${NC}"
            if [ -f /etc/centos-release ] || grep -q "CentOS" /etc/os-release 2>/dev/null; then
                echo -e "${YELLOW}sudo yum groupinstall -y 'Development Tools'${NC}"
                echo -e "${YELLOW}sudo yum install -y python3-devel${NC}"
            fi
        }
    }
    
    # 如果安装成功但找不到命令，可能是因为~/.local/bin不在PATH中，尝试修复
    if ! command -v pdf2zh >/dev/null 2>&1; then
        echo -e "${YELLOW}pdf2zh已安装但命令不在PATH中，检查可能的位置...${NC}"
        
        # 检查~/.local/bin
        USER_LOCAL_BIN="$HOME/.local/bin"
        if [ -x "$USER_LOCAL_BIN/pdf2zh" ]; then
            echo -e "${GREEN}在$USER_LOCAL_BIN找到pdf2zh${NC}"
            # 将此路径添加到PATH
            export PATH="$USER_LOCAL_BIN:$PATH"
            export PDF2ZH_PATH="$USER_LOCAL_BIN/pdf2zh"
            echo -e "${GREEN}已将$USER_LOCAL_BIN添加到PATH${NC}"
            
            # 添加到.bashrc或.bash_profile以持久化PATH设置
            if [ -f "$HOME/.bashrc" ]; then
                if ! grep -q "export PATH=.*$USER_LOCAL_BIN" "$HOME/.bashrc"; then
                    echo -e "${YELLOW}添加$USER_LOCAL_BIN到.bashrc...${NC}"
                    echo "export PATH=\"$USER_LOCAL_BIN:\$PATH\"" >> "$HOME/.bashrc"
                    echo -e "${GREEN}PATH设置已添加到.bashrc${NC}"
                fi
            elif [ -f "$HOME/.bash_profile" ]; then
                if ! grep -q "export PATH=.*$USER_LOCAL_BIN" "$HOME/.bash_profile"; then
                    echo -e "${YELLOW}添加$USER_LOCAL_BIN到.bash_profile...${NC}"
                    echo "export PATH=\"$USER_LOCAL_BIN:\$PATH\"" >> "$HOME/.bash_profile"
                    echo -e "${GREEN}PATH设置已添加到.bash_profile${NC}"
                fi
            fi
        else
            echo -e "${YELLOW}在$USER_LOCAL_BIN中未找到pdf2zh${NC}"
            
            # 查找site-packages中的pdf2zh脚本
            SITE_PACKAGES=$($PY_CMD -c "import site; print(site.getusersitepackages())")
            echo -e "${YELLOW}检查site-packages: $SITE_PACKAGES${NC}"
            
            if [ -d "$SITE_PACKAGES" ]; then
                # 查找paper2translate包
                if [ -d "$SITE_PACKAGES/paper2translate" ]; then
                    echo -e "${YELLOW}找到paper2translate包，创建直接执行入口...${NC}"
                    # 在当前目录的bin文件夹下创建pdf2zh脚本
                    mkdir -p "$SCRIPT_DIR/bin"
                    WRAPPER_SCRIPT="$SCRIPT_DIR/bin/pdf2zh"
                    
                    # 创建wrapper脚本
                    cat > "$WRAPPER_SCRIPT" << EOL
#!/bin/sh
$PY_CMD -m paper2translate.cli "\$@"
EOL
                    chmod +x "$WRAPPER_SCRIPT"
                    echo -e "${GREEN}创建了wrapper脚本: $WRAPPER_SCRIPT${NC}"
                    export PDF2ZH_PATH="$WRAPPER_SCRIPT"
                else
                    echo -e "${YELLOW}未找到paper2translate包${NC}"
                    
                    # 检查是否为pip作为模块安装但未创建可执行文件的情况
                    if $PY_CMD -c "import pkgutil; print(pkgutil.find_loader('paper2translate') is not None)" 2>/dev/null | grep -q "True"; then
                        echo -e "${YELLOW}paper2translate包已作为模块安装，创建Python模块执行入口...${NC}"
                        # 创建模块执行脚本
                        mkdir -p "$SCRIPT_DIR/bin"
                        MODULE_SCRIPT="$SCRIPT_DIR/bin/pdf2zh"
                        
                        cat > "$MODULE_SCRIPT" << EOL
#!/bin/sh
$PY_CMD -m paper2translate.cli "\$@"
EOL
                        chmod +x "$MODULE_SCRIPT"
                        echo -e "${GREEN}创建了模块执行脚本: $MODULE_SCRIPT${NC}"
                        export PDF2ZH_PATH="$MODULE_SCRIPT"
                    fi
                fi
            else
                echo -e "${YELLOW}未找到site-packages目录${NC}"
                
                # 尝试通过模块导入路径查找
                MODULE_PATH=$($PY_CMD -c "import importlib.util, sys; spec = importlib.util.find_spec('paper2translate'); print(spec.origin if spec else 'Not found')" 2>/dev/null)
                if [ "$MODULE_PATH" != "Not found" ] && [ -n "$MODULE_PATH" ]; then
                    echo -e "${YELLOW}通过模块导入路径找到paper2translate: $MODULE_PATH${NC}"
                    
                    # 创建执行脚本
                    mkdir -p "$SCRIPT_DIR/bin"
                    MODULE_EXEC="$SCRIPT_DIR/bin/pdf2zh"
                    
                    cat > "$MODULE_EXEC" << EOL
#!/bin/sh
$PY_CMD -m paper2translate.cli "\$@"
EOL
                    chmod +x "$MODULE_EXEC"
                    echo -e "${GREEN}创建了模块执行脚本: $MODULE_EXEC${NC}"
                    export PDF2ZH_PATH="$MODULE_EXEC"
                fi
            fi
        fi
    else
        # 如果命令可用，获取其路径
        PDF2ZH_PATH=$(command -v pdf2zh)
        echo -e "${GREEN}pdf2zh命令安装成功: $PDF2ZH_PATH${NC}"
        export PDF2ZH_PATH="$PDF2ZH_PATH"
    fi
fi

# 再次检查
if command -v pdf2zh >/dev/null 2>&1 || [ ! -z "$PDF2ZH_PATH" ]; then
    if [ ! -z "$PDF2ZH_PATH" ]; then
        echo -e "${GREEN}将使用pdf2zh路径: $PDF2ZH_PATH${NC}"
    else
        PDF2ZH_PATH=$(command -v pdf2zh)
        echo -e "${GREEN}pdf2zh命令可用: $PDF2ZH_PATH${NC}"
        export PDF2ZH_PATH="$PDF2ZH_PATH"
    fi
else
    echo -e "${YELLOW}pdf2zh命令仍不可用，尝试创建Python模块调用脚本...${NC}"
    
    # 创建Python模块调用脚本
    mkdir -p "$SCRIPT_DIR/bin"
    FALLBACK_SCRIPT="$SCRIPT_DIR/bin/pdf2zh"
    
    cat > "$FALLBACK_SCRIPT" << EOL
#!/bin/sh
# 在不同路径尝试查找Python
for py_cmd in python3 python /usr/bin/python3 /usr/bin/python $HOME/.pyenv/shims/python3; do
    if command -v \$py_cmd >/dev/null 2>&1; then
        echo "使用Python: \$py_cmd"
        \$py_cmd -m paper2translate.cli "\$@"
        exit \$?
    fi
done
echo "未找到可用的Python命令"
exit 1
EOL
    chmod +x "$FALLBACK_SCRIPT"
    echo -e "${YELLOW}创建了备用脚本: $FALLBACK_SCRIPT${NC}"
    export PDF2ZH_PATH="$FALLBACK_SCRIPT"
    echo -e "${YELLOW}将尝试在后端中直接调用Python模块${NC}"
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