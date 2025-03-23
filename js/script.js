// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
    // 更新API基础URL以使用当前主机和端口号
    const API_BASE_URL = `${window.location.protocol}//${window.location.host}/api`;
    let currentTaskId = null;
    let pdfContent = null;

    // 设置字体
    setupFonts();

    // 检查当前页面是否为翻译页面
    const isTranslatePage = window.location.pathname.includes('translate.html');
    
    // 如果是翻译页面
    if (isTranslatePage) {
        const urlParams = new URLSearchParams(window.location.search);
        const taskId = urlParams.get('task_id');
        
        if (taskId) {
            // 如果URL中有task_id参数，则使用该参数加载内容
            currentTaskId = taskId;
            loadPdfContent(taskId);
        } else {
            // 如果URL中没有task_id参数，则加载最新的文件
            loadLatestFile();
        }
    } else {
        // 在首页处理"查看最近翻译"按钮
        const viewRecentBtn = document.querySelector('.hero-actions a.btn-secondary');
        if (viewRecentBtn) {
            viewRecentBtn.addEventListener('click', function(e) {
                e.preventDefault(); // 阻止默认行为
                
                // 显示加载中提示
                showNotification('正在检查最近翻译...');
                
                // 获取最新文件信息
                fetch(`${API_BASE_URL}/latest_file`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('获取最新文件失败');
                        }
                        return response.json();
                    })
                    .then(data => {
                        // 跳转到翻译页面并传递task_id参数
                        window.location.href = `translate.html?task_id=${data.task_id}`;
                    })
                    .catch(error => {
                        console.error('获取最新文件出错:', error);
                        alert('未找到可查看的翻译文件，请先上传PDF文件');
                    });
            });
        }
    }
    
    // 加载最新的文件
    function loadLatestFile() {
        showLoading('正在加载最新文档...');
        
        fetch(`${API_BASE_URL}/latest_file`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('获取最新文件失败');
                }
                return response.json();
            })
            .then(data => {
                // 更新当前任务ID
                currentTaskId = data.task_id;
                
                // 更新URL，但不刷新页面
                const newUrl = `${window.location.pathname}?task_id=${currentTaskId}`;
                window.history.pushState({ path: newUrl }, '', newUrl);
                
                // 更新内容
                pdfContent = data.content;
                
                // 显示内容 - 改用PDF查看模式
                updatePaperMetadata({ content: data });
                // 使用displayOriginalPdf而非displayPdfContent，确保以PDF格式显示
                displayOriginalPdf(currentTaskId);
                setupDownloadButton(currentTaskId, data.filename);
                
                hideLoading();
                showNotification('已加载最新文档');
            })
            .catch(error => {
                console.error('加载最新文件出错:', error);
                showError('未找到可加载的文件，请先上传PDF文件');
                hideLoading();
                
                // 显示一个上传按钮
                showUploadPrompt();
            });
    }
    
    // 显示上传提示
    function showUploadPrompt() {
        const contentArea = document.querySelector('.paper-content');
        if (contentArea) {
            contentArea.innerHTML = `
                <div class="upload-prompt">
                    <h2>未找到文档</h2>
                    <p>请先上传PDF文件或返回首页上传文件</p>
                    <div class="upload-actions">
                        <a href="index.html" class="btn btn-primary">返回首页上传</a>
                    </div>
                </div>
            `;
        }
    }

    // 首页tab切换
    const tabs = document.querySelectorAll('.tab');
    if (tabs.length > 0) {
        tabs.forEach(tab => {
            tab.addEventListener('click', function() {
                // 移除所有tab的active类
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                // 隐藏所有tab内容
                document.querySelectorAll('.tab-content').forEach(content => content.classList.add('hidden'));
                
                // 添加active类到当前点击的tab
                this.classList.add('active');
                
                // 显示对应的tab内容
                const tabId = this.getAttribute('data-tab');
                document.getElementById(tabId + '-tab').classList.remove('hidden');
            });
        });
    }

    // 文件上传处理
    const fileUpload = document.getElementById('file-upload');
    const uploadArea = document.querySelector('.upload-area');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadStatus = document.getElementById('upload-status');
    
    if (fileUpload && uploadArea && uploadBtn) {
        // 拖拽上传
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('active');
        });
        
        uploadArea.addEventListener('dragleave', function() {
            uploadArea.classList.remove('active');
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('active');
            
            if (e.dataTransfer.files.length) {
                fileUpload.files = e.dataTransfer.files;
                handleFileSelection(e.dataTransfer.files[0]);
            }
        });
        
        // 点击上传
        fileUpload.addEventListener('change', function() {
            if (this.files.length) {
                handleFileSelection(this.files[0]);
            }
        });
        
        // 处理文件选择
        function handleFileSelection(file) {
            // 检查文件类型
            if (file.type !== 'application/pdf') {
                alert('请上传PDF文件！');
                return;
            }
            
            // 显示文件名
            const fileNameElement = document.createElement('p');
            fileNameElement.textContent = `已选择文件: ${file.name}`;
            fileNameElement.classList.add('selected-file');
            
            // 移除之前的文件名(如果有)
            const prevFileName = uploadArea.querySelector('.selected-file');
            if (prevFileName) {
                uploadArea.removeChild(prevFileName);
            }
            
            uploadArea.appendChild(fileNameElement);
            
            // 显示上传按钮
            uploadBtn.classList.remove('hidden');
        }
        
        // 上传按钮点击事件
        uploadBtn.addEventListener('click', function() {
            if (!fileUpload.files.length) {
                alert('请先选择文件');
                return;
            }
            
            const file = fileUpload.files[0];
            uploadFile(file);
        });
        
        // 上传文件到服务器
        function uploadFile(file) {
            updateUploadStatus('上传中...', 'loading');
            
            const formData = new FormData();
            formData.append('file', file);
            
            fetch(`${API_BASE_URL}/upload`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('上传失败');
                }
                return response.json();
            })
            .then(data => {
                currentTaskId = data.task_id;
                updateUploadStatus('上传成功！正在跳转到翻译页面...', 'success');
                
                // 显示文件信息
                displayFileInfo(data);
                
                // 自动跳转到翻译页面
                setTimeout(() => {
                    // 重定向到translate.html页面并传递task_id参数
                    window.location.href = `translate.html?task_id=${currentTaskId}`;
                }, 1000);
            })
            .catch(error => {
                console.error('上传出错:', error);
                updateUploadStatus('上传失败: ' + error.message, 'error');
            });
        }
        
        // 更新上传状态
        function updateUploadStatus(message, status) {
            if (uploadStatus) {
                uploadStatus.textContent = message;
                uploadStatus.className = 'status ' + status;
                uploadStatus.classList.remove('hidden');
            }
        }
        
        // 显示文件信息
        function displayFileInfo(data) {
            const fileInfo = document.createElement('div');
            fileInfo.classList.add('file-info');
            fileInfo.innerHTML = `
                <h3>${data.filename}</h3>
                <p>标题: ${data.content_summary?.title || '未检测到标题'}</p>
                <p>页数: ${data.content_summary?.total_pages || '未知'}</p>
                <p>摘要: ${data.content_summary?.has_abstract ? '有' : '无'}</p>
                <p>章节数: ${data.content_summary?.sections_count || '0'}</p>
            `;
            
            // 添加到上传区域
            const infoContainer = document.querySelector('.file-info-container');
            if (infoContainer) {
                infoContainer.innerHTML = '';
                infoContainer.appendChild(fileInfo);
                infoContainer.classList.remove('hidden');
            }
        }
    }
    
    // 加载PDF内容
    function loadPdfContent(taskId) {
        if (!taskId) return;
        
        showLoading('正在加载文档内容...');
        
        fetch(`${API_BASE_URL}/content/${taskId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('获取内容失败');
                }
                return response.json();
            })
            .then(data => {
                pdfContent = data.content;
                // 更新页面元数据
                updatePaperMetadata(data);
                
                // 始终使用PDF查看器显示原始PDF，不用HTML格式
                displayOriginalPdf(taskId);
                
                // 设置下载PDF按钮
                setupDownloadButton(taskId, data.filename);
                
                // 检查是否已有翻译
                checkAndDisplayTranslation(taskId);
                
                hideLoading();
            })
            .catch(error => {
                console.error('加载内容出错:', error);
                showError('加载内容失败: ' + error.message);
                hideLoading();
            });
    }
    
    // 检查是否已有翻译并显示
    function checkAndDisplayTranslation(taskId) {
        console.log(`检查任务 ${taskId} 是否已翻译过`);
        fetch(`${API_BASE_URL}/check_translation/${taskId}`)
            .then(response => {
                console.log(`检查翻译状态响应: ${response.status}`);
                if (!response.ok) {
                    return response.text().then(text => {
                        throw new Error(`HTTP错误: ${response.status} - ${text || '未知错误'}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("检查翻译状态结果:", data);
                
                if (data.success && data.translated) {
                    // 已翻译过，直接显示PDF
                    console.log("文档已翻译过，自动显示译文");
                    
                    const translationInfoElement = document.querySelector('.content-column.translated .translation-info');
                    if (translationInfoElement) {
                        translationInfoElement.innerHTML = `
                            <div class="translation-progress">
                                <h3>文档已翻译过</h3>
                                <p>正在加载已翻译的PDF...</p>
                                <div class="progress">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                        role="progressbar" style="width: 100%"></div>
                                </div>
                            </div>
                        `;
                    }
                    
                    // 显示翻译后的PDF
                    if (data.pdf_url) {
                        displayTranslatedPdf(data.pdf_url);
                        showNotification("已加载翻译");
                    }
                }
            })
            .catch(error => {
                console.error("检查翻译状态出错:", error);
                // 检查出错，不做任何操作，用户可以手动点击翻译按钮
            });
    }
    
    // 显示原始PDF
    function displayOriginalPdf(taskId) {
        const originalColumn = document.querySelector('.content-column.original');
        const translatedColumn = document.querySelector('.content-column.translated');
        
        if (!originalColumn || !translatedColumn) return;
        
        // 添加PDF查看模式类
        document.querySelector('.paper-content').classList.add('pdf-view-mode');
        
        // 清空内容
        originalColumn.innerHTML = '';
        translatedColumn.innerHTML = '';
        
        // 创建PDF容器
        const pdfContainer = document.createElement('div');
        pdfContainer.style.width = '100%';
        pdfContainer.style.height = '100%';
        pdfContainer.style.position = 'relative';
        pdfContainer.style.overflow = 'hidden';
        
        // 添加加载指示器
        const loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'pdf-loading';
        loadingIndicator.textContent = '正在加载PDF...';
        loadingIndicator.style.position = 'absolute';
        loadingIndicator.style.top = '50%';
        loadingIndicator.style.left = '50%';
        loadingIndicator.style.transform = 'translate(-50%, -50%)';
        loadingIndicator.style.background = 'rgba(255,255,255,0.8)';
        loadingIndicator.style.padding = '15px 25px';
        loadingIndicator.style.borderRadius = '5px';
        loadingIndicator.style.boxShadow = '0 2px 5px rgba(0,0,0,0.1)';
        
        pdfContainer.appendChild(loadingIndicator);
        originalColumn.appendChild(pdfContainer);
        
        // 获取PDF文件并创建blob URL
        const pdfUrl = `${API_BASE_URL}/files/${taskId}`;
        console.log("正在获取PDF:", pdfUrl);
        
        fetch(pdfUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP错误：${response.status}`);
                }
                return response.blob();
            })
            .then(blob => {
                // 创建blob URL
                const blobUrl = URL.createObjectURL(blob);
                
                // 创建PDF查看器
                const pdfViewer = document.createElement('iframe');
                pdfViewer.style.width = '100%';
                pdfViewer.style.height = '100%';
                pdfViewer.style.border = 'none';
                pdfViewer.src = blobUrl;
                
                pdfViewer.onload = function() {
                    // 移除加载指示器
                    if (loadingIndicator.parentNode) {
                        loadingIndicator.parentNode.removeChild(loadingIndicator);
                    }
                };
                
                pdfViewer.onerror = function(e) {
                    console.error("PDF iframe加载失败:", e);
                    loadingIndicator.textContent = 'PDF加载失败，尝试使用嵌入方式显示...';
                    
                    // 使用embed作为备选方案
                    const embedViewer = document.createElement('embed');
                    embedViewer.style.width = '100%';
                    embedViewer.style.height = '100%';
                    embedViewer.src = blobUrl;
                    embedViewer.type = 'application/pdf';
                    
                    // 替换iframe
                    pdfContainer.removeChild(pdfViewer);
                    pdfContainer.appendChild(embedViewer);
                    
                    // 再次尝试移除加载指示器
                    if (loadingIndicator.parentNode) {
                        loadingIndicator.parentNode.removeChild(loadingIndicator);
                    }
                };
                
                pdfContainer.appendChild(pdfViewer);
            })
            .catch(error => {
                console.error('加载PDF出错:', error);
                loadingIndicator.textContent = `PDF加载失败: ${error.message}`;
                loadingIndicator.style.color = 'red';
            });
        
        // 添加右侧栏占位内容
        translatedColumn.innerHTML = `
            <div class="translation-placeholder">
                <div class="translation-info">
                    <h3>翻译准备就绪</h3>
                    <p>请点击"翻译"按钮，将在此处生成并显示翻译后的PDF</p>
                    <div class="translation-steps">
                        <div class="step">
                            <span class="step-number">1</span>
                            <span class="step-text">提取论文内容</span>
                        </div>
                        <div class="step">
                            <span class="step-number">2</span>
                            <span class="step-text">翻译文本内容</span>
                        </div>
                        <div class="step">
                            <span class="step-number">3</span>
                            <span class="step-text">生成翻译PDF</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 显示翻译按钮和API设置
        const translateSettings = document.getElementById('translate-settings');
        if (translateSettings) {
            translateSettings.classList.remove('hidden');
        }
    }
    
    // 更新论文元数据
    function updatePaperMetadata(data) {
        // 检查是否在翻译页面
        if (!isTranslatePage) return;
        
        const paperTitle = document.getElementById('paper-title');
        const paperAuthors = document.getElementById('paper-authors');
        const paperJournal = document.getElementById('paper-journal');
        const paperTags = document.getElementById('paper-tags');
        
        if (paperTitle && data.content && data.content.content) {
            // 设置标题
            const title = data.content.content.title || data.filename || '未检测到标题';
            paperTitle.textContent = title;
            document.title = `${title} | PaperTrans`;
            
            // 设置作者信息（如果API返回的数据中有的话）
            if (paperAuthors) {
                const authors = data.content.metadata && data.content.metadata.author 
                    ? `作者：${data.content.metadata.author}` 
                    : '作者：未检测到';
                paperAuthors.textContent = authors;
            }
            
            // 设置期刊信息（如果API返回的数据中有的话）
            if (paperJournal) {
                const journal = data.content.metadata && data.content.metadata.subject
                    ? `发表于：${data.content.metadata.subject}`
                    : '';
                paperJournal.textContent = journal || '';
                paperJournal.style.display = journal ? 'block' : 'none';
            }
            
            // 设置标签（如果有的话）
            if (paperTags) {
                paperTags.innerHTML = '';
                // 如果有关键词，作为标签显示
                if (data.content.metadata && data.content.metadata.keywords) {
                    const keywords = data.content.metadata.keywords.split(',');
                    keywords.forEach(keyword => {
                        if (keyword.trim()) {
                            const tag = document.createElement('span');
                            tag.className = 'tag';
                            tag.textContent = keyword.trim();
                            paperTags.appendChild(tag);
                        }
                    });
                } else {
                    // 添加一个默认标签
                    const tag = document.createElement('span');
                    tag.className = 'tag';
                    tag.textContent = '学术论文';
                    paperTags.appendChild(tag);
                }
            }
        }
    }
    
    // 设置下载PDF按钮
    function setupDownloadButton(taskId, filename) {
        const downloadBtn = document.getElementById('download-pdf-btn');
        if (downloadBtn && taskId) {
            downloadBtn.addEventListener('click', function() {
                window.open(`${API_BASE_URL}/files/${taskId}`, '_blank');
            });
        }
    }
    
    // 显示双语对照内容
    function displayBilingualContent(originalContent, translatedContent, images) {
        console.log("显示双语对照内容");
        console.log("原始内容:", originalContent);
        console.log("翻译内容:", translatedContent);
        
        const originalColumn = document.querySelector('.content-column.original');
        const translatedColumn = document.querySelector('.content-column.translated');
        
        if (!originalColumn || !translatedColumn) {
            console.error("找不到内容列元素");
            return;
        }
        
        // 清空内容列并添加样式以确保内容正确显示
        originalColumn.innerHTML = '<div class="column-header"><h3>原文</h3></div>';
        translatedColumn.innerHTML = '<div class="column-header"><h3>译文</h3></div>';
        
        // 移除可能导致样式冲突的类
        document.querySelector('.paper-content').classList.remove('pdf-view-mode');
        
        // 修改样式表，强制应用段落样式
        const styleElement = document.createElement('style');
        styleElement.textContent = `
            .content-column p {
                font-size: var(--paper-text-size) !important;
                font-weight: normal !important;
                line-height: 1.7 !important;
                margin-bottom: 16px !important;
                text-align: justify !important;
                color: var(--text-color) !important;
                padding-left: 0 !important;
                position: relative !important;
                text-indent: 2em !important;
            }
            
            .content-column h1 {
                font-size: var(--paper-title-size) !important;
                font-weight: 700 !important;
                color: #222 !important;
                text-align: center !important;
            }
            
            .content-column h2 {
                font-size: var(--paper-heading-size) !important;
                font-weight: 600 !important;
                color: #333 !important;
                margin-top: 25px !important;
                margin-bottom: 15px !important;
                border-bottom: 1px solid #eaeaea !important;
                padding-bottom: 8px !important;
                position: relative !important;
            }
            
            .content-column .paper-section {
                padding: 10px 20px !important;
                border-bottom: 1px solid #f0f0f0 !important;
                font-family: var(--paper-font) !important;
            }
            
            /* 重要：确保内容可滚动 */
            .content-column {
                overflow-y: auto !important;
                height: auto !important;
                min-height: 800px !important;
                padding: 0 !important;
                padding-bottom: 20px !important;
                display: block !important;
            }
        `;
        document.head.appendChild(styleElement);
        
        // 添加标题
        if (originalContent.title) {
            const titleContainer = document.createElement('div');
            titleContainer.classList.add('paper-title-container');
            
            const titleElement = document.createElement('h1');
            titleElement.textContent = originalContent.title;
            titleElement.classList.add('paper-title'); // 添加专门的标题类名
            
            titleContainer.appendChild(titleElement);
            originalColumn.appendChild(titleContainer);
        }
        
        if (translatedContent.title) {
            const titleContainer = document.createElement('div');
            titleContainer.classList.add('paper-title-container');
            
            const translatedTitleElement = document.createElement('h1');
            translatedTitleElement.textContent = translatedContent.title;
            translatedTitleElement.classList.add('paper-title'); // 添加专门的标题类名
            
            titleContainer.appendChild(translatedTitleElement);
            translatedColumn.appendChild(titleContainer);
        }
        
        // 添加摘要
        if (originalContent.abstract) {
            // 创建摘要章节
            const abstractSection = document.createElement('div');
            abstractSection.classList.add('paper-section', 'abstract-section');
            
            const abstractHeader = document.createElement('h2');
            abstractHeader.textContent = 'Abstract';
            abstractHeader.classList.add('section-title'); // 添加专门的章节标题类名
            abstractSection.appendChild(abstractHeader);
            
            const abstractElement = document.createElement('p');
            abstractElement.textContent = originalContent.abstract;
            abstractElement.classList.add('abstract', 'paragraph'); // 添加段落类名
            abstractSection.appendChild(abstractElement);
            
            originalColumn.appendChild(abstractSection);
        }
        
        if (translatedContent.abstract) {
            // 创建译文摘要章节
            const translatedAbstractSection = document.createElement('div');
            translatedAbstractSection.classList.add('paper-section', 'abstract-section');
            
            const translatedAbstractHeader = document.createElement('h2');
            translatedAbstractHeader.textContent = '摘要';
            translatedAbstractHeader.classList.add('section-title'); // 添加专门的章节标题类名
            translatedAbstractSection.appendChild(translatedAbstractHeader);
            
            const translatedAbstractElement = document.createElement('p');
            translatedAbstractElement.textContent = translatedContent.abstract;
            translatedAbstractElement.classList.add('abstract', 'paragraph'); // 添加段落类名
            translatedAbstractSection.appendChild(translatedAbstractElement);
            
            translatedColumn.appendChild(translatedAbstractSection);
        }
        
        // 添加章节
        if (originalContent.sections && translatedContent.sections) {
            for (let i = 0; i < originalContent.sections.length; i++) {
                const origSection = originalContent.sections[i];
                const transSection = i < translatedContent.sections.length ? 
                    translatedContent.sections[i] : { title: '', content: [] };
                
                // 创建原文章节容器
                const origSectionElement = document.createElement('div');
                origSectionElement.classList.add('paper-section');
                origSectionElement.dataset.sectionIndex = i; // 添加索引属性，便于调试
                
                // 创建译文章节容器
                const transSectionElement = document.createElement('div');
                transSectionElement.classList.add('paper-section');
                transSectionElement.dataset.sectionIndex = i; // 添加索引属性，便于调试
                
                // 添加章节标题
                if (origSection.title) {
                    const sectionTitle = document.createElement('h2');
                    sectionTitle.textContent = origSection.title;
                    sectionTitle.classList.add('section-title'); // 添加专门的章节标题类名
                    origSectionElement.appendChild(sectionTitle);
                }
                
                if (transSection.title) {
                    const transSectionTitle = document.createElement('h2');
                    transSectionTitle.textContent = transSection.title;
                    transSectionTitle.classList.add('section-title'); // 添加专门的章节标题类名
                    transSectionElement.appendChild(transSectionTitle);
                }
                
                // 添加章节内容
                if (origSection.content && Array.isArray(origSection.content)) {
                    // 记录当前章节已添加的段落数量
                    let paragraphCount = 0;
                    
                    for (let j = 0; j < origSection.content.length; j++) {
                        const para = origSection.content[j];
                        if (para && para.trim()) {
                            const paraElement = document.createElement('p');
                            paraElement.textContent = para;
                            paraElement.classList.add('paragraph'); // 添加段落类名
                            paraElement.dataset.paraIndex = paragraphCount++; // 添加段落索引
                            
                            // 检查段落是否有缩进，尝试保留
                            if (para.startsWith(' ') || para.startsWith('\t')) {
                                paraElement.style.textIndent = '2em';
                            }
                            
                            // 对特殊段落应用特殊样式
                            if (para.match(/^(References|Bibliography|参考文献)/i)) {
                                paraElement.style.fontWeight = '500';
                            } else if (origSection.title && origSection.title.match(/^(References|Bibliography|参考文献)/i)) {
                                // 处理参考文献项目
                                paraElement.classList.add('references');
                                paraElement.style.textIndent = '0';
                                paraElement.style.paddingLeft = '20px';
                                paraElement.style.textIndent = '-20px';
                            }
                            
                            origSectionElement.appendChild(paraElement);
                        }
                    }
                }
                
                if (transSection.content && Array.isArray(transSection.content)) {
                    // 记录当前章节已添加的段落数量
                    let paragraphCount = 0;
                    
                    for (let j = 0; j < transSection.content.length; j++) {
                        const para = transSection.content[j];
                        if (para && para.trim()) {
                            const paraElement = document.createElement('p');
                            paraElement.textContent = para;
                            paraElement.classList.add('paragraph'); // 添加段落类名
                            paraElement.dataset.paraIndex = paragraphCount++; // 添加段落索引
                            
                            // 保持与原文相同的缩进样式
                            const origPara = j < origSection.content.length ? origSection.content[j] : '';
                            if (origPara && (origPara.startsWith(' ') || origPara.startsWith('\t'))) {
                                paraElement.style.textIndent = '2em';
                            }
                            
                            // 对特殊段落应用特殊样式
                            if (para.match(/^(References|Bibliography|参考文献)/i)) {
                                paraElement.style.fontWeight = '500';
                            } else if (transSection.title && transSection.title.match(/^(References|Bibliography|参考文献)/i)) {
                                // 处理参考文献项目
                                paraElement.classList.add('references');
                                paraElement.style.textIndent = '0';
                                paraElement.style.paddingLeft = '20px';
                                paraElement.style.textIndent = '-20px';
                            }
                            
                            transSectionElement.appendChild(paraElement);
                        }
                    }
                }
                
                // 确保没有空章节
                if (origSectionElement.children.length > 1 || (origSectionElement.children.length === 1 && origSectionElement.querySelector('.section-title'))) {
                    originalColumn.appendChild(origSectionElement);
                }
                
                if (transSectionElement.children.length > 1 || (transSectionElement.children.length === 1 && transSectionElement.querySelector('.section-title'))) {
                    translatedColumn.appendChild(transSectionElement);
                }
            }
        }
        
        // 添加图片展示区
        if (images && images.length > 0) {
            const imagesContainer = document.createElement('div');
            imagesContainer.classList.add('images-container');
            imagesContainer.innerHTML = '<h3>原文图片</h3>';
            
            for (const image of images) {
                const imgElement = document.createElement('img');
                imgElement.src = image.url;
                imgElement.alt = `图 ${image.index} (页面 ${image.page})`;
                imgElement.classList.add('pdf-image');
                
                const figCaption = document.createElement('figcaption');
                figCaption.textContent = imgElement.alt;
                
                const figure = document.createElement('figure');
                figure.appendChild(imgElement);
                figure.appendChild(figCaption);
                
                imagesContainer.appendChild(figure);
            }
            
            // 将图片添加到原文列
            originalColumn.appendChild(imagesContainer);
        }
        
        // 确保内容列是可滚动的
        originalColumn.style.overflowY = 'auto';
        translatedColumn.style.overflowY = 'auto';
        
        // 修改容器样式以确保正确显示内容
        document.querySelector('.content-columns').style.height = 'auto';
        
        // 应用字体样式
        applyFontStyles();
        
        // 设置段落悬停高亮
        setupBilingualParagraphHighlighting();
        
        // 调整列高度，确保两列高度一致
        setTimeout(() => {
            const origHeight = originalColumn.scrollHeight;
            const transHeight = translatedColumn.scrollHeight;
            const maxHeight = Math.max(origHeight, transHeight);
            originalColumn.style.minHeight = `${maxHeight}px`;
            translatedColumn.style.minHeight = `${maxHeight}px`;
        }, 100);
    }
    
    // 设置双语段落悬停高亮
    function setupBilingualParagraphHighlighting() {
        const originalParas = document.querySelectorAll('.content-column.original .paper-section p');
        const translatedParas = document.querySelectorAll('.content-column.translated .paper-section p');
        
        // 需要确保段落数量一致才能匹配
        const minCount = Math.min(originalParas.length, translatedParas.length);
        
        for (let i = 0; i < minCount; i++) {
            const origPara = originalParas[i];
            const transPara = translatedParas[i];
            
            // 为原文段落添加鼠标悬停事件
            origPara.addEventListener('mouseover', function() {
                this.classList.add('highlight');
                transPara.classList.add('highlight');
            });
            
            origPara.addEventListener('mouseout', function() {
                this.classList.remove('highlight');
                transPara.classList.remove('highlight');
            });
            
            // 为译文段落添加鼠标悬停事件
            transPara.addEventListener('mouseover', function() {
                this.classList.add('highlight');
                origPara.classList.add('highlight');
            });
            
            transPara.addEventListener('mouseout', function() {
                this.classList.remove('highlight');
                origPara.classList.remove('highlight');
            });
        }
    }
    
    // 显示翻译后的PDF - 这个函数保留用于向下兼容
    function displayTranslatedPdf(pdfUrl) {
        // 在新版本中，这个函数不再使用PDF显示，而是改用HTML双栏对照显示
        console.log("PDF显示功能已经被修改为HTML双栏对照显示");
    }
    
    // 设置段落悬停高亮
    function setupParagraphHighlighting() {
        const originalParagraphs = document.querySelectorAll('.content-column.original .paper-section p');
        const translatedParagraphs = document.querySelectorAll('.content-column.translated .paper-section p');
        
        if (originalParagraphs.length > 0 && translatedParagraphs.length > 0) {
            originalParagraphs.forEach(paragraph => {
                const sectionIndex = paragraph.getAttribute('data-section-index');
                const paraIndex = paragraph.getAttribute('data-para-index');
                
                const correspondingTranslation = document.querySelector(`.content-column.translated p[data-section-index="${sectionIndex}"][data-para-index="${paraIndex}"]`);
                
                if (correspondingTranslation) {
                    // 鼠标悬停在原文上，高亮原文和对应的译文
                    paragraph.addEventListener('mouseover', function() {
                        this.classList.add('highlight');
                        correspondingTranslation.classList.add('highlight');
                    });
                    
                    paragraph.addEventListener('mouseout', function() {
                        this.classList.remove('highlight');
                        correspondingTranslation.classList.remove('highlight');
                    });
                    
                    // 鼠标悬停在译文上，高亮译文和对应的原文
                    correspondingTranslation.addEventListener('mouseover', function() {
                        this.classList.add('highlight');
                        paragraph.classList.add('highlight');
                    });
                    
                    correspondingTranslation.addEventListener('mouseout', function() {
                        this.classList.remove('highlight');
                        paragraph.classList.remove('highlight');
                    });
                }
            });
        }
    }
    
    // 翻译页面相关功能
    const viewButtons = document.querySelectorAll('.translate-toolbar .btn');
    if (viewButtons.length > 0) {
        // 双栏/单栏视图切换
        const columnsView = document.querySelector('.content-columns');
        
        viewButtons.forEach(button => {
            button.addEventListener('click', function() {
                // 如果是视图切换按钮
                if (this.innerHTML.includes('双栏视图') || this.innerHTML.includes('单栏视图')) {
                    // 移除所有视图按钮的active类
                    document.querySelectorAll('.toolbar-group:first-child .btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    
                    // 添加active类到当前点击的按钮
                    this.classList.add('active');
                    
                    // 切换视图
                    if (this.innerHTML.includes('单栏视图')) {
                        columnsView.classList.add('content-single');
                    } else {
                        columnsView.classList.remove('content-single');
                    }
                }
            });
        });
        
        // 页面缩放功能
        const zoomOut = document.querySelector('.toolbar-group:nth-child(2) .btn:first-child');
        const zoomIn = document.querySelector('.toolbar-group:nth-child(2) .btn:last-child');
        const zoomDisplay = document.querySelector('.toolbar-group:nth-child(2) span');
        
        if (zoomOut && zoomIn && zoomDisplay) {
            let currentZoom = 100;
            
            zoomOut.addEventListener('click', function() {
                if (currentZoom > 50) {
                    currentZoom -= 10;
                    applyZoom();
                }
            });
            
            zoomIn.addEventListener('click', function() {
                if (currentZoom < 200) {
                    currentZoom += 10;
                    applyZoom();
                }
            });
            
            function applyZoom() {
                zoomDisplay.textContent = currentZoom + '%';
                
                // 获取CSS变量的基础值
                const baseTitleSize = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--paper-title-size'));
                const baseHeadingSize = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--paper-heading-size'));
                const baseTextSize = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--paper-text-size'));
                
                // 应用缩放
                document.querySelectorAll('.paper-section p').forEach(p => {
                    p.style.fontSize = (baseTextSize * currentZoom / 100) + 'px';
                });
                
                document.querySelectorAll('.paper-section h2').forEach(h => {
                    h.style.fontSize = (baseHeadingSize * currentZoom / 100) + 'px';
                });
                
                document.querySelectorAll('.paper-section h1').forEach(h => {
                    h.style.fontSize = (baseTitleSize * currentZoom / 100) + 'px';
                });
                
                document.querySelectorAll('.paper-section .abstract').forEach(a => {
                    a.style.fontSize = (baseTextSize * currentZoom / 100) + 'px';
                });
            }
        }
        
        // 复制全部功能
        const copyBtn = document.querySelector('.toolbar-group:nth-child(3) .btn:first-child');
        if (copyBtn) {
            copyBtn.addEventListener('click', function() {
                const translatedContent = document.querySelector('.content-column.translated').innerText;
                
                // 复制到剪贴板
                navigator.clipboard.writeText(translatedContent)
                    .then(() => {
                        // 显示复制成功提示
                        const originalText = this.innerHTML;
                        this.innerHTML = '<i class="fas fa-check"></i> 复制成功';
                        
                        setTimeout(() => {
                            this.innerHTML = originalText;
                        }, 2000);
                    })
                    .catch(err => {
                        console.error('复制失败: ', err);
                        alert('复制失败，请手动复制');
                    });
            });
        }
    }
    
    // UI辅助函数
    
    // 显示加载状态
    function showLoading(message) {
        // 检查是否已有加载提示
        let loadingElement = document.getElementById('loading-indicator');
        
        if (!loadingElement) {
            loadingElement = document.createElement('div');
            loadingElement.id = 'loading-indicator';
            loadingElement.className = 'loading-indicator';
            
            const spinnerElement = document.createElement('div');
            spinnerElement.className = 'spinner';
            loadingElement.appendChild(spinnerElement);
            
            const messageElement = document.createElement('p');
            messageElement.className = 'loading-message';
            loadingElement.appendChild(messageElement);
            
            document.body.appendChild(loadingElement);
        }
        
        const messageElement = loadingElement.querySelector('.loading-message');
        if (messageElement) {
            messageElement.textContent = message || '加载中...';
        }
        
        loadingElement.style.display = 'flex';
    }
    
    // 隐藏加载状态
    function hideLoading() {
        const loadingElement = document.getElementById('loading-indicator');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }
    
    // 更新加载进度
    function updateLoadingProgress(completed, total) {
        const loadingElement = document.getElementById('loading-indicator');
        if (loadingElement) {
            const messageElement = loadingElement.querySelector('.loading-message');
            if (messageElement) {
                messageElement.textContent = `正在翻译... (${completed}/${total})`;
            }
        }
    }
    
    // 更新加载消息
    function updateLoadingMessage(message) {
        const loadingElement = document.getElementById('loading-indicator');
        if (loadingElement) {
            const messageElement = loadingElement.querySelector('.loading-message');
            if (messageElement) {
                messageElement.textContent = message;
            }
        }
    }
    
    // 显示错误信息
    function showError(message) {
        // 创建错误消息元素
        let errorElement = document.getElementById('error-message');
        
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.id = 'error-message';
            errorElement.className = 'error-message';
            
            const closeBtn = document.createElement('button');
            closeBtn.className = 'close-btn';
            closeBtn.innerHTML = '&times;';
            closeBtn.onclick = function() {
                errorElement.style.display = 'none';
            };
            
            const messageElement = document.createElement('p');
            
            errorElement.appendChild(closeBtn);
            errorElement.appendChild(messageElement);
            
            document.body.appendChild(errorElement);
        }
        
        const messageElement = errorElement.querySelector('p');
        if (messageElement) {
            messageElement.textContent = message;
        }
        
        errorElement.style.display = 'block';
        
        // 自动隐藏
        setTimeout(() => {
            errorElement.style.display = 'none';
        }, 5000);
    }
    
    // 显示通知消息
    function showNotification(message) {
        // 创建通知消息元素
        let notificationElement = document.getElementById('notification-message');
        
        if (!notificationElement) {
            notificationElement = document.createElement('div');
            notificationElement.id = 'notification-message';
            notificationElement.className = 'notification-message';
            
            const closeBtn = document.createElement('button');
            closeBtn.className = 'close-btn';
            closeBtn.innerHTML = '&times;';
            closeBtn.onclick = function() {
                notificationElement.style.display = 'none';
            };
            
            const messageElement = document.createElement('p');
            
            notificationElement.appendChild(closeBtn);
            notificationElement.appendChild(messageElement);
            
            document.body.appendChild(notificationElement);
        }
        
        const messageElement = notificationElement.querySelector('p');
        if (messageElement) {
            messageElement.textContent = message;
        }
        
        notificationElement.style.display = 'block';
        
        // 自动隐藏
        setTimeout(() => {
            notificationElement.style.display = 'none';
        }, 3000);
    }

    // 设置字体
    function setupFonts() {
        // 预加载Noto Serif字体
        const fontLink = document.createElement('link');
        fontLink.rel = 'stylesheet';
        fontLink.href = 'https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,400;0,500;0,600;1,400&display=swap';
        document.head.appendChild(fontLink);
        
        // 应用字体到所有文本元素
        document.addEventListener('DOMContentLoaded', function() {
            const contentElements = document.querySelectorAll('.content-column *');
            contentElements.forEach(el => {
                if (el.tagName.match(/^(H[1-6]|P|SPAN|DIV)$/)) {
                    el.style.fontFamily = getComputedStyle(document.documentElement).getPropertyValue('--paper-font');
                }
            });
        });
    }

    // 全局变量，用于存储翻译信息元素的引用
    let translationInfoEl = null;
    
    // 添加翻译按钮点击事件
    document.addEventListener('click', function(event) {
        // 检查是否点击了翻译按钮
        if (event.target && (event.target.id === 'translateBtn' || 
            event.target.closest('#translateBtn'))) {
            console.log("捕获到翻译按钮点击事件");
            event.preventDefault();
            
            // 如果没有当前任务ID，显示错误
            if (!currentTaskId) {
                showError("没有可翻译的文档，请先上传PDF文件");
                return;
            }
            
            // 获取API密钥和提供商信息
            const provider = 'deepseek';
            const model = 'deepseek-chat';
            const apiKey = ''; // 使用环境变量中的API密钥
            
            // 开始翻译
            console.log("使用任务ID启动翻译:", currentTaskId);
            translateDocumentAndGeneratePdf(apiKey, provider, model);
        }
    });
    
    // 在翻译页面加载完成后，获取翻译信息元素的引用
    if (isTranslatePage) {
        window.addEventListener('load', function() {
            // 获取翻译信息元素
            translationInfoEl = $('.content-column.translated .translation-info');
            
            if (translationInfoEl.length === 0) {
                console.error("无法找到翻译信息元素");
                // 尝试创建该元素
                $('.content-column.translated').append(
                    '<div class="translation-info"><p>准备就绪，点击"开始翻译"按钮开始翻译过程</p></div>'
                );
                translationInfoEl = $('.content-column.translated .translation-info');
            }
            
            console.log("翻译页面加载完成，翻译信息元素:", translationInfoEl);
        });
    }

    // 显示PDF内容
    function displayPdfContent(content) {
        const originalColumn = document.querySelector('.content-column.original');
        const translatedColumn = document.querySelector('.content-column.translated');
        
        if (!originalColumn || !translatedColumn) return;
        
        // 清空内容
        originalColumn.innerHTML = '';
        translatedColumn.innerHTML = '';
        
        if (!content || !content.content) {
            originalColumn.innerHTML = '<p class="error">无法加载内容</p>';
            return;
        }
        
        // 添加标题
        if (content.content.title) {
            const titleElement = document.createElement('h1');
            titleElement.textContent = content.content.title;
            // 保留标题中可能的换行和空格
            titleElement.style.whiteSpace = 'pre-wrap';
            originalColumn.appendChild(titleElement);
            
            // 在译文栏预留标题位置
            const translatedTitle = document.createElement('h1');
            translatedTitle.textContent = '正在翻译...';
            translatedTitle.dataset.type = 'title';
            translatedTitle.classList.add('translating');
            translatedTitle.style.whiteSpace = 'pre-wrap';
            translatedColumn.appendChild(translatedTitle);
        }
        
        // 添加摘要
        if (content.content.abstract) {
            const abstractHeader = document.createElement('h2');
            abstractHeader.textContent = 'Abstract';
            originalColumn.appendChild(abstractHeader);
            
            const abstractElement = document.createElement('p');
            abstractElement.textContent = content.content.abstract;
            abstractElement.classList.add('abstract');
            // 保留摘要中原始的格式
            abstractElement.style.whiteSpace = 'pre-wrap';
            // 检查摘要是否有缩进，尝试保留
            if (content.content.abstract.startsWith(' ') || content.content.abstract.startsWith('\t')) {
                abstractElement.style.textIndent = '2em';
            }
            originalColumn.appendChild(abstractElement);
            
            // 在译文栏预留摘要位置
            const translatedAbstractHeader = document.createElement('h2');
            translatedAbstractHeader.textContent = '摘要';
            translatedColumn.appendChild(translatedAbstractHeader);
            
            const translatedAbstract = document.createElement('p');
            translatedAbstract.textContent = '正在翻译...';
            translatedAbstract.classList.add('abstract', 'translating');
            translatedAbstract.dataset.type = 'abstract';
            translatedAbstract.style.whiteSpace = 'pre-wrap';
            translatedColumn.appendChild(translatedAbstract);
        }
        
        // 添加章节
        if (content.content.sections && content.content.sections.length > 0) {
            content.content.sections.forEach((section, sectionIndex) => {
                // 原文章节
                const sectionElement = document.createElement('div');
                sectionElement.classList.add('paper-section');
                
                const sectionTitle = document.createElement('h2');
                sectionTitle.textContent = section.title;
                sectionTitle.style.whiteSpace = 'pre-wrap';
                sectionElement.appendChild(sectionTitle);
                
                section.content.forEach((paragraph, paraIndex) => {
                    // 确保段落之间有换行并且保留原始格式
                    if (paragraph.trim()) { // 只处理非空段落
                        const paraElement = document.createElement('p');
                        
                        // 保留段落原始格式
                        paraElement.textContent = paragraph;
                        paraElement.style.whiteSpace = 'pre-wrap';
                        
                        // 检查段落是否有缩进，尝试保留
                        if (paragraph.startsWith(' ') || paragraph.startsWith('\t')) {
                            paraElement.style.textIndent = '2em';
                        }
                        
                        // 对特殊段落应用特殊样式
                        if (paragraph.match(/^(References|Bibliography|参考文献)/i)) {
                            paraElement.style.fontWeight = '500';
                        } else if (sectionTitle.textContent.match(/^(References|Bibliography|参考文献)/i)) {
                            // 处理参考文献项目
                            paraElement.classList.add('references');
                            paraElement.style.textIndent = '0';
                            paraElement.style.paddingLeft = '20px';
                            paraElement.style.textIndent = '-20px';
                        }
                        
                        paraElement.dataset.sectionIndex = sectionIndex;
                        paraElement.dataset.paraIndex = paraIndex;
                        sectionElement.appendChild(paraElement);
                    }
                });
                
                originalColumn.appendChild(sectionElement);
                
                // 译文章节（预留位置）
                const translatedSectionElement = document.createElement('div');
                translatedSectionElement.classList.add('paper-section');
                
                const translatedSectionTitle = document.createElement('h2');
                translatedSectionTitle.textContent = '正在翻译...';
                translatedSectionTitle.dataset.type = 'section-title';
                translatedSectionTitle.dataset.sectionIndex = sectionIndex;
                translatedSectionTitle.classList.add('translating');
                translatedSectionTitle.style.whiteSpace = 'pre-wrap';
                translatedSectionElement.appendChild(translatedSectionTitle);
                
                section.content.forEach((paragraph, paraIndex) => {
                    if (paragraph.trim()) { // 只处理非空段落
                        const translatedParaElement = document.createElement('p');
                        translatedParaElement.textContent = '正在翻译...';
                        translatedParaElement.dataset.type = 'paragraph';
                        translatedParaElement.dataset.sectionIndex = sectionIndex;
                        translatedParaElement.dataset.paraIndex = paraIndex;
                        translatedParaElement.classList.add('translating');
                        translatedParaElement.style.whiteSpace = 'pre-wrap';
                        
                        // 保持与原文相同的缩进样式
                        if (paragraph.startsWith(' ') || paragraph.startsWith('\t')) {
                            translatedParaElement.style.textIndent = '2em';
                        }
                        
                        // 对特殊段落应用特殊样式
                        if (paragraph.match(/^(References|Bibliography|参考文献)/i)) {
                            translatedParaElement.style.fontWeight = '500';
                        } else if (sectionTitle.textContent.match(/^(References|Bibliography|参考文献)/i)) {
                            // 处理参考文献项目
                            translatedParaElement.classList.add('references');
                            translatedParaElement.style.textIndent = '0';
                            translatedParaElement.style.paddingLeft = '20px';
                            translatedParaElement.style.textIndent = '-20px';
                        }
                        
                        translatedSectionElement.appendChild(translatedParaElement);
                    }
                });
                
                translatedColumn.appendChild(translatedSectionElement);
            });
        }
        
        // 显示翻译按钮和API设置
        const translateSettings = document.getElementById('translate-settings');
        if (translateSettings) {
            translateSettings.classList.remove('hidden');
        }
        
        // 绑定段落悬停高亮事件
        setupParagraphHighlighting();
        
        // 应用字体样式
        applyFontStyles();
    }
    
    // 应用字体样式
    function applyFontStyles() {
        const contentElements = document.querySelectorAll('.content-column *');
        contentElements.forEach(el => {
            if (el.tagName.match(/^(H[1-6]|P|SPAN|DIV)$/)) {
                el.style.fontFamily = getComputedStyle(document.documentElement).getPropertyValue('--paper-font');
                
                // 标题、章节标题和段落已通过类名设置了样式，这里只需要设置字体
                // 不再直接设置其他样式，避免覆盖CSS中定义的样式
                
                // 为未分类的元素应用基本样式
                if (!el.classList.contains('paper-title') && 
                    !el.classList.contains('section-title') && 
                    !el.classList.contains('paragraph')) {
                    
                    if (el.tagName === 'H1') {
                        el.style.fontSize = getComputedStyle(document.documentElement).getPropertyValue('--paper-title-size');
                    } else if (el.tagName === 'H2') {
                        el.style.fontSize = getComputedStyle(document.documentElement).getPropertyValue('--paper-heading-size');
                    } else if (el.tagName === 'P') {
                        el.style.fontSize = getComputedStyle(document.documentElement).getPropertyValue('--paper-text-size');
                        el.style.lineHeight = '1.7';
                    }
                }
            }
        });
        
        // 检测和处理数学公式及特殊符号
        processSpecialContent();
    }
    
    // 检测和处理数学公式及特殊符号
    function processSpecialContent() {
        // 处理可能的数学公式 (使用正则表达式匹配常见的数学表达式模式)
        const paragraphs = document.querySelectorAll('.content-column p');
        
        paragraphs.forEach(p => {
            const text = p.textContent;
            
            // 检查是否包含数学公式的模式 (简单检测)
            const mathFormulaPatterns = [
                /\$\$.*?\$\$/g,  // 行间公式 $$...$$
                /\$.*?\$/g,      // 行内公式 $...$
                /\\frac{.*?}{.*?}/g, // 分数
                /\\sum_/g,       // 求和
                /\\int_/g,       // 积分
                /\\lim_/g,       // 极限
                /\\begin{equation}/g, // LaTeX 方程环境
                /[≈≠≤≥∫∑∏√∞∆∇]/g // 常见数学符号
            ];
            
            let containsMath = false;
            for (const pattern of mathFormulaPatterns) {
                if (pattern.test(text)) {
                    containsMath = true;
                    break;
                }
            }
            
            // 如果包含数学公式，添加专门的样式
            if (containsMath) {
                const originalText = p.textContent;
                
                // 清空当前内容并重建
                p.innerHTML = '';
                
                // 创建一个用于包装公式的元素
                const mathFormulaElement = document.createElement('span');
                mathFormulaElement.classList.add('math-formula');
                mathFormulaElement.textContent = originalText;
                
                p.appendChild(mathFormulaElement);
            }
            
            // 处理上标和下标 (简单处理)
            let html = p.innerHTML;
            
            // 检测并标记上标 (例如 x^2)
            html = html.replace(/([A-Za-z0-9])\^([A-Za-z0-9]+)/g, '$1<sup>$2</sup>');
            
            // 检测并标记下标 (例如 H_2O)
            html = html.replace(/([A-Za-z])\_([\d]+)/g, '$1<sub>$2</sub>');
            
            // 应用HTML
            if (html !== p.innerHTML) {
                p.innerHTML = html;
            }
        });
    }
    
    // 设置一个全局事件监听器，确保无论DOM结构如何变化，都能触发翻译功能
    document.addEventListener('translate-document', function() {
        console.log("触发翻译事件");
        if (!currentTaskId) {
            alert('请先上传PDF文件');
            return;
        }
        
        // 默认使用deepseek，API key从环境变量获取
        translateDocumentAndGeneratePdf('', 'deepseek', 'deepseek-chat');
    });
    
    // 翻译按钮点击事件
    const translateBtn = document.getElementById('translate-btn');
    const apiKeyInput = document.getElementById('api-key');
    const providerSelect = document.getElementById('provider-select');
    const modelInput = document.getElementById('model-input');
    
    if (translateBtn) {
        // 默认选择DeepSeek
        if (providerSelect) {
            providerSelect.value = 'deepseek';
            
            // 如果存在model输入框，设置默认值
            if (modelInput) {
                modelInput.placeholder = '模型名称 (默认: deepseek-chat)';
            }
        }
        
        // 隐藏API密钥输入框，使用环境变量
        if (apiKeyInput) {
            const apiKeyRow = apiKeyInput.closest('.settings-row');
            if (apiKeyRow) {
                apiKeyRow.innerHTML = `
                    <div class="settings-group api-key-input">
                        <span style="color: #555; font-size: 12px;">API密钥将从环境变量中获取</span>
                        <button id="translate-btn" class="btn btn-primary"><i class="fas fa-language"></i> 开始翻译</button>
                    </div>
                `;
                
                // 重新获取翻译按钮
                const newTranslateBtn = document.getElementById('translate-btn');
                if (newTranslateBtn) {
                    // 更新引用
                    translateBtn = newTranslateBtn;
                    
                    // 重新绑定事件监听器
                    translateBtn.addEventListener('click', function() {
                        console.log("翻译按钮被点击");
                        if (!currentTaskId) {
                            alert('请先上传PDF文件');
                            return;
                        }
                        
                        // 默认使用deepseek，API key从环境变量获取
                        translateDocumentAndGeneratePdf('', 'deepseek', 'deepseek-chat');
                    });
                }
            }
            return; // 已经处理过按钮事件，不需要再次绑定
        }
        
        // 只有在上面的代码块没有执行时才执行这部分
        translateBtn.addEventListener('click', function() {
            console.log("翻译按钮被点击");
            if (!currentTaskId) {
                alert('请先上传PDF文件');
                return;
            }
            
            // 默认使用deepseek，API key从环境变量获取
            translateDocumentAndGeneratePdf('', 'deepseek', 'deepseek-chat');
        });
    }
    
    // 翻译文档并展示对照结果
    function translateDocumentAndGeneratePdf(apiKey, provider, model) {
        if (!currentTaskId) {
            console.error("没有当前任务ID");
            showError("没有可翻译的文档，请先上传PDF文件");
            return;
        }
        
        console.log(`开始翻译文档: ${currentTaskId}, 提供商: ${provider}, 模型: ${model}`);
        
        // 确保translationInfoEl已正确初始化
        if (!translationInfoEl || translationInfoEl.length === 0) {
            console.log("翻译信息元素不存在，尝试重新获取");
            translationInfoEl = $('.content-column.translated .translation-info');
            
            // 如果仍然不存在，则创建一个
            if (translationInfoEl.length === 0) {
                console.log("创建翻译信息元素");
                $('.content-column.translated').append(
                    '<div class="translation-info"><p>准备就绪，点击"开始翻译"按钮开始翻译过程</p></div>'
                );
                translationInfoEl = $('.content-column.translated .translation-info');
            }
        }
        
        // 使用原生JavaScript更新翻译状态，避免jQuery相关问题
        const translationInfoElement = document.querySelector('.content-column.translated .translation-info');
        
        if (translationInfoElement) {
            translationInfoElement.innerHTML = `
                <div class="translation-progress">
                    <h3>正在检查翻译状态...</h3>
                    <p>请稍候...</p>
                    <div class="progress">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" style="width: 100%"></div>
                    </div>
                </div>
            `;
        }
        
        // 检查任务是否已翻译
        fetch(`${API_BASE_URL}/check_translation/${currentTaskId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`检查翻译状态HTTP错误: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("检查翻译状态结果:", data);
                
                if (data.success && data.translated) {
                    // 已翻译过，直接获取翻译结果
                    console.log("文档已翻译过，获取已有翻译结果");
                    
                    if (translationInfoElement) {
                        translationInfoElement.innerHTML = `
                            <div class="translation-progress">
                                <h3>文档已翻译过</h3>
                                <p>正在加载已翻译的内容...</p>
                                <div class="progress">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                        role="progressbar" style="width: 100%"></div>
                                </div>
                            </div>
                        `;
                    }
                    
                    // 重新请求翻译内容
                    proceedWithTranslation(apiKey, provider, model);
                } else {
                    // 未翻译过，开始翻译
                    console.log("文档未翻译过，开始翻译");
                    proceedWithTranslation(apiKey, provider, model);
                }
            })
            .catch(error => {
                console.error("检查翻译状态出错:", error);
                // 检查出错，仍然尝试翻译
                proceedWithTranslation(apiKey, provider, model);
            });
        
        // 执行翻译流程
        function proceedWithTranslation(apiKey, provider, model) {
            if (translationInfoElement) {
                translationInfoElement.innerHTML = `
                    <div class="translation-progress">
                        <h3>正在翻译文档...</h3>
                        <p>请耐心等待，这可能需要几分钟时间</p>
                        <div class="progress">
                            <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                 role="progressbar" style="width: 100%"></div>
                        </div>
                        <p class="mt-2"><small>翻译长文档可能需要较长时间，请不要关闭页面</small></p>
                    </div>
                `;
            }
            
            // 准备请求数据
            const requestData = {
                task_id: currentTaskId,
                provider: provider || 'deepseek', // 默认使用DeepSeek
                model: model || 'deepseek-chat',
                api_key: apiKey  // API密钥可选，如果未提供则使用环境变量
            };
            
            console.log("请求数据:", JSON.stringify(requestData, null, 2));
            console.log("请求URL:", `${API_BASE_URL}/translate_document`);
            
            // 发送翻译请求
            fetch(`${API_BASE_URL}/translate_document`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                console.log(`翻译请求状态: ${response.status} ${response.statusText}`);
                if (!response.ok) {
                    return response.text().then(text => {
                        // 尝试解析错误响应
                        try {
                            const errorData = JSON.parse(text);
                            throw new Error(errorData.message || `HTTP错误: ${response.status}`);
                        } catch (e) {
                            throw new Error(`HTTP错误: ${response.status} - ${text || '未知错误'}`);
                        }
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("翻译完成，响应数据:", data);
                // 输出详细的数据结构信息
                console.log("原始内容结构:", JSON.stringify(data.original, null, 2));
                console.log("翻译内容结构:", JSON.stringify(data.translation, null, 2));
                
                if (data.success) {
                    // 翻译成功
                    console.log("文档翻译成功");
                    
                    // 清空翻译状态信息
                    if (translationInfoElement) {
                        translationInfoElement.parentElement.removeChild(translationInfoElement);
                    }
                    
                    // 显示原文和译文对照
                    displayBilingualContent(data.original, data.translation, data.images);
                    
                    // 显示成功状态
                    showNotification("文档翻译完成");
                } else {
                    // 翻译失败但有响应
                    console.error("翻译失败:", data.message);
                    
                    // 使用原生JavaScript更新状态
                    if (translationInfoElement) {
                        translationInfoElement.innerHTML = `
                            <div class="alert alert-warning">
                                <h4>翻译处理失败</h4>
                                <p>${data.message || '未知错误'}</p>
                                <button id="retryTranslationBtn" class="btn btn-primary mt-2">重试翻译</button>
                            </div>
                        `;
                        
                        // 添加重试按钮功能
                        document.getElementById('retryTranslationBtn').addEventListener('click', function() {
                            console.log("重试翻译");
                            translateDocumentAndGeneratePdf(apiKey, provider, model);
                        });
                    }
                }
            })
            .catch(error => {
                console.error("翻译请求出错:", error);
                
                // 更新状态为错误
                if (translationInfoElement) {
                    translationInfoElement.innerHTML = `
                        <div class="alert alert-danger">
                            <h4>翻译请求失败</h4>
                            <p>${error.message}</p>
                            <button id="retryTranslationBtn" class="btn btn-primary mt-2">重试翻译</button>
                        </div>
                    `;
                    
                    // 添加重试按钮功能
                    document.getElementById('retryTranslationBtn').addEventListener('click', function() {
                        console.log("重试翻译");
                        translateDocumentAndGeneratePdf(apiKey, provider, model);
                    });
                }
                
                showError("翻译请求失败: " + error.message);
            });
        }
    }
}); 