# PaperTrans - PDF学术论文翻译工具

PaperTrans是一个专为研究人员设计的强大学术论文翻译工具，可以将外文PDF论文精准翻译成中文，并提供双栏对照查看功能。本工具基于开源的PDFMathTranslate项目，特别优化了对数学公式、图表和专业术语的处理，为学术阅读提供便捷的语言支持。

[![PaperTrans Screenshot](https://via.placeholder.com/800x400?text=PaperTrans界面预览)](http://localhost:8000/translate.html)

## 功能特点

- **PDF论文翻译**：将英文等外语论文翻译成中文，保留原始排版
- **双栏对照查看**：原文和译文并排显示，支持同步滚动，方便对照阅读
- **数学公式完美保留**：翻译过程中保留原始数学公式格式和内容
- **专业术语优化**：针对学术领域的专业术语进行特殊处理，提高翻译准确性
- **多种查看模式**：支持双栏对照、单栏专注、原文优先等多种阅读模式
- **历史记录管理**：自动保存翻译历史，方便随时查阅和管理
- **多种翻译引擎**：支持Google、DeepL、OpenAI等多种翻译服务
- **用户友好界面**：简洁直观的Web界面，操作简单

## 系统要求

- **操作系统**：支持Windows、macOS、Linux
- **Python**：Python 3.8或更高版本
- **浏览器**：支持现代浏览器（Chrome、Firefox、Safari、Edge等）
- **磁盘空间**：约500MB（用于存储PDF和翻译相关资源）
- **网络连接**：需要互联网连接以使用在线翻译服务

## 详细安装指南

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/mk-blueberry.git
cd mk-blueberry/paper-translator
```

### 2. 创建并激活Python虚拟环境（推荐）

#### Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 安装PDFMathTranslate

确保PDFMathTranslate工具已正确安装在backend目录：

```bash
cd backend
git clone https://github.com/Byaidu/PDFMathTranslate.git
cd PDFMathTranslate
pip install -e .
cd ../..
```

### 5. 配置翻译服务（可选）

默认情况下，PaperTrans使用Google翻译服务，无需API密钥。如果您想使用其他翻译服务，请设置相应的环境变量：

#### OpenAI GPT服务

```bash
# Windows (CMD)
set OPENAI_API_KEY=your_api_key
set OPENAI_MODEL=gpt-4o-mini

# Windows (PowerShell)
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_MODEL="gpt-4o-mini"

# macOS/Linux
export OPENAI_API_KEY=your_api_key
export OPENAI_MODEL=gpt-4o-mini
```

#### DeepL服务

```bash
# Windows (CMD)
set DEEPL_API_KEY=your_api_key

# Windows (PowerShell)
$env:DEEPL_API_KEY="your_api_key"

# macOS/Linux
export DEEPL_API_KEY=your_api_key
```

## 启动指南

### 方法一：使用Shell脚本启动（推荐用于macOS/Linux）

```bash
# 确保脚本有执行权限
chmod +x start.sh stop.sh

# 启动服务
./start.sh

# 或者通过环境变量指定端口
PORT=8080 ./start.sh
```

### 方法二：使用Python脚本启动（适用于所有操作系统）

```bash
# 启动服务
python start.py

# 或者通过环境变量指定端口
PORT=8080 python start.py

# 或者通过命令行参数指定端口
python start.py --port 8080
```

系统将自动启动PDF翻译服务，并在控制台输出相关信息。服务启动后，您可以通过浏览器访问：
```
http://localhost:8000/translate.html
```
默认端口为8000，如果您修改了端口，请相应地调整访问地址。

## 使用指南

1. **上传PDF**：
   - 在首页点击"上传论文"或直接拖拽PDF文件到上传区域
   - 您也可以通过URL输入框提供论文的下载链接

2. **开始翻译**：
   - 上传完成后，点击"开始翻译"按钮
   - 系统将显示翻译进度，请耐心等待翻译完成

3. **查看翻译结果**：
   - 翻译完成后，系统会以双栏方式显示原文和译文
   - 左侧为原文PDF，右侧为译文PDF
   - 两侧可同步滚动，便于对照阅读

4. **调整显示模式**：
   - 使用顶部工具栏中的"视图"选项切换显示模式
   - 支持双栏对照、单栏专注等多种模式

5. **访问历史记录**：
   - 点击顶部导航栏的"历史记录"访问之前的翻译
   - 可以按状态筛选（全部、已翻译、未翻译）

6. **下载翻译结果**：
   - 点击页面上的"下载PDF"按钮保存译文
   - 或使用浏览器的打印功能将页面保存为PDF

## 高级配置

### 通过.env文件进行配置（推荐）

您可以在项目根目录创建一个`.env`文件，并在其中设置各种配置参数：

```bash
# .env文件配置示例

# 服务端口
PORT=8080

# API密钥设置
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key

# 其他配置
OPENAI_MODEL=gpt-4o-mini
DEEPL_API_KEY=your_deepl_api_key
TERMS_FILE=my_terms.txt
```

系统将在启动时自动读取该文件中的配置并应用。这是管理所有配置的最佳方式，避免了在命令行中暴露敏感信息。

### 自定义端口

您可以通过多种方式修改默认的8000端口：

#### 通过.env文件设置（最推荐）

您可以在项目根目录创建一个`.env`文件，并在其中设置环境变量：

```bash
# .env文件内容
PORT=8080
```

系统将自动读取该文件中的配置并应用。

#### 通过环境变量设置

```bash
# Windows (CMD)
set PORT=8080
python start.py

# Windows (PowerShell)
$env:PORT=8080
python start.py

# macOS/Linux
export PORT=8080
python start.py

# 或者在启动命令中直接指定
PORT=8080 ./start.sh
PORT=8080 python start.py
```

#### 通过命令行参数

```bash
python start.py --port 8080
```

#### 通过修改启动脚本

您也可以直接修改启动脚本中的默认端口：

```bash
# 在start.py或start.sh中修改端口变量
```

### 调整性能参数

对于大型论文或需要更快翻译速度的情况，可以调整线程数：

```bash
# 修改backend/pdf_translator_bridge.py中的启动参数
# 将 "-t 4" 修改为更高的值，例如 "-t 8"
```

### 配置专业术语库（针对特定领域）

如果您需要针对特定学科领域优化翻译效果，可以自定义术语库：

1. 在backend/PDFMathTranslate/terms/目录下创建自定义术语文件(my_terms.txt)
2. 按照"英文术语|中文术语"的格式添加专业术语对
3. 在启动服务前设置环境变量：
   ```bash
   export TERMS_FILE=my_terms.txt
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
│   └── styles.css              # 主样式文件
├── js/                         # JavaScript文件
│   └── script.js               # 交互脚本
├── index.html                  # 首页
├── translate.html              # 翻译页面
├── history.html                # 历史记录页面
├── guide.html                  # 使用指南页面
├── about.html                  # 关于我们页面
├── start.sh                    # Shell启动脚本（Unix系统）
├── stop.sh                     # Shell停止脚本（Unix系统）
├── start.py                    # Python启动脚本（跨平台）
└── stop.py                     # Python停止脚本（跨平台）
```

## 故障排除

### 启动问题

1. **服务无法启动**
   - 检查Python版本是否≥3.8: `python --version`
   - 确认依赖已正确安装: `pip install -r requirements.txt`
   - 检查端口是否被占用: `lsof -i :8000` (Linux/macOS) 或 `netstat -ano | findstr 8000` (Windows)

2. **PDFMathTranslate相关错误**
   - 确认PDFMathTranslate已正确安装: `cd backend/PDFMathTranslate && pip install -e .`
   - 检查是否缺少依赖: `pip install pdf2image pytesseract pdfplumber`

### 翻译问题

1. **翻译速度慢**
   - 考虑更换更快的翻译API (如OpenAI)
   - 增加线程数 (修改pdf_translator_bridge.py中的-t参数)
   - 检查网络连接状态

2. **翻译质量不佳**
   - 尝试配置专业领域的术语库
   - 切换到更专业的翻译API (如OpenAI的GPT-4模型)
   - 确保PDF文本可提取 (非扫描版PDF)

3. **无法识别特定语言**
   - 确保添加了正确的源语言支持
   - 对于非常见语言，建议使用OpenAI等支持多语言的API

### 浏览器问题

1. **页面加载缓慢**
   - 检查是否为大型PDF (>50MB)
   - 尝试清除浏览器缓存
   - 确认系统内存充足

2. **同步滚动失效**
   - 尝试在页面加载完成后刷新页面
   - 检查控制台是否有跨域相关错误
   - 尝试使用Chrome浏览器

## API接口文档

如果您想将PaperTrans整合到自己的系统中，可以使用以下API接口：

### 上传PDF
```
POST /api/upload
Content-Type: multipart/form-data

请求体:
- file: PDF文件
```

### 检查翻译状态
```
GET /api/check_translation/<task_id>
```

### 获取翻译结果
```
GET /api/get_translation/<task_id>
```

完整API文档请参考backend/README.md文件。

## 贡献指南

我们欢迎您为PaperTrans项目做出贡献！以下是参与贡献的步骤：

1. Fork本仓库
2. 创建您的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开Pull Request

## 常见问题解答

**问：支持哪些语言之间的翻译？**

答：目前主要支持英文到中文的翻译，但也可以通过配置支持其他语言（如日语、德语、法语等）到中文的翻译。

**问：是否有批量翻译功能？**

答：当前版本需要逐个上传PDF进行翻译。我们计划在未来版本中添加批量翻译功能。

**问：翻译后的文件保存在哪里？**

答：翻译后的文件保存在backend/translated/目录中，同时也可以通过web界面下载。

**问：如何提高翻译质量？**

答：可以通过以下方式提高翻译质量：
- 使用高质量的翻译API（如OpenAI的GPT-4）
- 配置专业领域的术语库
- 选择合适的预处理和后处理选项
- 确保上传的PDF文本质量良好（非扫描版）

**问：翻译过程中数据是否安全？**

答：PaperTrans在本地处理和存储PDF文件，数据不会上传到第三方服务器。当使用第三方翻译API时，只有提取的文本会传输到相应的翻译服务。

## 许可证

本项目基于PDFMathTranslate开源项目开发，遵循MIT开源许可证。

## 致谢

- [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate)项目提供了核心的PDF翻译功能
- 特别感谢所有贡献者和用户的支持与反馈 