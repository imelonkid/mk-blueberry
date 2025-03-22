# PaperTrans 后端服务

这个目录包含PaperTrans论文翻译工具的后端服务代码。后端提供论文PDF解析和翻译功能。

## 功能

- PDF文件上传和文本提取
- 使用OpenAI或DeepSeek API进行学术论文翻译
- 支持多种大语言模型
- RESTful API接口，方便与前端集成

## 依赖

- Python 3.8+
- Flask
- PyMuPDF (用于PDF文本提取)
- OpenAI/DeepSeek API (用于翻译功能)
- 其他依赖项可以查看requirements.txt

## 安装

1. 确保已安装Python 3.8或更高版本

2. 克隆仓库（如果尚未完成）
```
git clone <仓库URL>
cd paper-translator/backend
```

3. 创建并激活虚拟环境（可选但推荐）
```
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

4. 安装依赖项
```
pip install -r requirements.txt
```

5. 配置环境变量
```
cp .env.example .env
```
然后编辑.env文件，添加你的API密钥和其他配置：
- 使用OpenAI API，设置`OPENAI_API_KEY`
- 使用DeepSeek API，设置`DEEPSEEK_API_KEY`和`DEEPSEEK_API_URL`

## 使用方法

### 启动服务器

使用提供的启动脚本：
```
chmod +x start.sh  # 如果需要添加执行权限
./start.sh
```

或手动启动：
```
python api.py
```

默认情况下，服务器将在http://localhost:5000运行

### API端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/upload` | POST | 上传PDF文件并提取内容 |
| `/api/content/<task_id>` | GET | 获取指定任务的提取内容 |
| `/api/translate` | POST | 翻译整个文档 |
| `/api/translate_section` | POST | 翻译特定段落或章节 |
| `/api/files/<task_id>` | GET | 获取上传的PDF文件 |
| `/api/tasks` | GET | 获取所有任务列表 |
| `/api/health` | GET | 健康检查接口 |

### 使用示例

#### 上传PDF文件
```
curl -X POST -F "file=@path/to/your/paper.pdf" http://localhost:5000/api/upload
```

#### 获取内容
```
curl http://localhost:5000/api/content/your-task-id
```

#### 翻译文本（使用OpenAI）
```
curl -X POST -H "Content-Type: application/json" -d '{"text": "Your text here", "api_key": "your-openai-api-key", "provider": "openai"}' http://localhost:5000/api/translate_section
```

#### 翻译文本（使用DeepSeek）
```
curl -X POST -H "Content-Type: application/json" -d '{"text": "Your text here", "api_key": "your-deepseek-api-key", "provider": "deepseek", "model": "deepseek-chat"}' http://localhost:5000/api/translate_section
```

## 目录结构

- `api.py` - Flask API服务
- `pdf_extractor.py` - PDF文本提取功能
- `translator.py` - 翻译功能，支持OpenAI和DeepSeek模型
- `requirements.txt` - 依赖项列表
- `.env.example` - 环境变量配置模板
- `start.sh` - 启动脚本

## 注意事项

- 请确保有足够的API配额，翻译功能依赖于第三方API
- 上传的PDF文件将存储在`uploads`目录中
- 对于大型文件或长篇文章，翻译过程可能需要较长时间
- 使用DeepSeek API需要正确配置API URL 