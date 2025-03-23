# PaperTrans - PDF论文翻译工具

PaperTrans是一个强大的学术论文翻译工具，可以将外文PDF论文翻译成中文，并提供双栏对照查看功能。本工具基于开源的PDFMathTranslate项目，支持数学公式、图表和专业术语的准确翻译。

## 功能特点

- **PDF论文翻译**：将英文等外语论文翻译成中文
- **双栏对照查看**：原文和译文并排显示，方便对照阅读
- **数学公式保留**：翻译过程中保留原始数学公式和图表
- **快速部署**：简单的启动脚本，一键运行服务
- **多种翻译引擎**：支持Google、DeepL、OpenAI等多种翻译服务

## 系统要求

- Python 3.8或更高版本
- 支持PDF查看的现代浏览器（Chrome/Firefox/Safari等）
- 约500MB的磁盘空间（用于存储PDF和翻译模型）

## 安装和使用

### 前提条件

确保PDFMathTranslate工具已下载到backend目录：

```bash
# 如果尚未下载PDFMathTranslate，请执行以下命令
cd backend
git clone https://github.com/Byaidu/PDFMathTranslate.git
cd PDFMathTranslate
pip install -e .
```

### 启动服务

#### 方法一：使用Python脚本启动（推荐，支持所有操作系统）

```bash
# Windows/macOS/Linux通用
python start.py
```

#### 方法二：使用Shell脚本启动（仅支持macOS/Linux）

```bash
chmod +x start.sh stop.sh  # 确保脚本有执行权限
./start.sh
```

服务启动后，会自动打开浏览器访问：http://localhost:5000/translate.html

然后：
1. 上传PDF文件并点击"开始翻译"按钮
2. 翻译完成后，可以在左右双栏中分别查看原文和译文

### 停止服务

#### 方法一：使用Python脚本停止

```bash
python stop.py
```

#### 方法二：使用Shell脚本停止（仅支持macOS/Linux）

```bash
./stop.sh
```

## 使用的翻译服务

默认使用Google翻译服务，无需API密钥。如需使用其他服务（如OpenAI、DeepL等），请参考[PDFMathTranslate文档](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#services)设置相应的环境变量。

例如，要使用OpenAI的GPT模型，需要设置：

```bash
export OPENAI_API_KEY=your_api_key
export OPENAI_MODEL=gpt-4o-mini
```

## 目录结构

```
paper-translator/
├── backend/                    # 后端代码
│   ├── PDFMathTranslate/       # PDF翻译核心工具
│   ├── pdf_translator_bridge.py # 桥接服务
│   ├── uploads/                # 上传的PDF文件存放目录
│   └── translated/             # 翻译后的PDF文件存放目录
├── css/                        # 样式文件
├── translate.html              # 主页面
├── start.sh                    # Shell启动脚本（Unix系统）
├── stop.sh                     # Shell停止脚本（Unix系统）
├── start.py                    # Python启动脚本（跨平台）
└── stop.py                     # Python停止脚本（跨平台）
```

## 常见问题

**问：翻译速度慢怎么办？**

答：翻译速度取决于PDF大小、所选翻译服务和网络状况。对于大型文档，建议使用OpenAI等高性能API，并增加线程数（在pdf_translator_bridge.py中修改`-t`参数）。

**问：如何修改服务端口？**

答：在start.sh或start.py中修改PORT变量（默认为5000）。

**问：如何保存翻译结果？**

答：翻译完成后，可以使用浏览器的打印功能将PDF保存到本地。也可以在backend/translated/目录中找到翻译后的文件。

**问：在Windows系统上无法运行Shell脚本怎么办？**

答：Windows用户请使用Python脚本（start.py和stop.py）来启动和停止服务。

**问：找不到PDFMathTranslate工具怎么办？**

答：请检查backend目录下是否存在PDFMathTranslate目录。如果不存在，请按照「前提条件」部分的指令下载安装。

## 许可证

本项目基于PDFMathTranslate开源项目，遵循MIT开源许可证。 