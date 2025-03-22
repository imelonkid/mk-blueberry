// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
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
    
    if (fileUpload && uploadArea) {
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
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
        
        // 点击上传
        fileUpload.addEventListener('change', function() {
            if (this.files.length) {
                handleFileUpload(this.files[0]);
            }
        });
        
        function handleFileUpload(file) {
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
        
        // 段落对应高亮
        const originalParagraphs = document.querySelectorAll('.content-column.original p');
        const translatedParagraphs = document.querySelectorAll('.content-column.translated p');
        
        if (originalParagraphs.length > 0 && translatedParagraphs.length > 0) {
            // 确保原文和译文段落数量相同
            const minParagraphs = Math.min(originalParagraphs.length, translatedParagraphs.length);
            
            for (let i = 0; i < minParagraphs; i++) {
                // 鼠标悬停在原文上，高亮原文和对应的译文
                originalParagraphs[i].addEventListener('mouseover', function() {
                    this.classList.add('highlight');
                    translatedParagraphs[i].classList.add('highlight');
                });
                
                originalParagraphs[i].addEventListener('mouseout', function() {
                    this.classList.remove('highlight');
                    translatedParagraphs[i].classList.remove('highlight');
                });
                
                // 鼠标悬停在译文上，高亮译文和对应的原文
                translatedParagraphs[i].addEventListener('mouseover', function() {
                    this.classList.add('highlight');
                    originalParagraphs[i].classList.add('highlight');
                });
                
                translatedParagraphs[i].addEventListener('mouseout', function() {
                    this.classList.remove('highlight');
                    originalParagraphs[i].classList.remove('highlight');
                });
            }
        }
        
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
                
                document.querySelectorAll('.paper-section p').forEach(p => {
                    p.style.fontSize = (15 * currentZoom / 100) + 'px';
                });
                
                document.querySelectorAll('.paper-section h2').forEach(h => {
                    h.style.fontSize = (20 * currentZoom / 100) + 'px';
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
}); 