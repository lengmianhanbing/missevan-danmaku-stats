let currentDramaId = null;
let isRunning = false;

function searchDrama() {
    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');
    const keyword = searchInput.value.trim();
    
    if (!keyword) {
        alert('请输入搜索关键词');
        return;
    }
    
    // 显示加载状态
    searchResults.innerHTML = '<div class="list-group-item">搜索中...</div>';
    searchResults.classList.remove('d-none');
    
    // 发送搜索请求
    const searchUrl = `/api/search?keyword=${encodeURIComponent(keyword)}`;
    console.log('Searching:', searchUrl);
    
    fetch(searchUrl)
        .then(response => {
            console.log('Response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Search results:', data);
            
            if (!data.results || data.results.length === 0) {
                searchResults.innerHTML = '<div class="list-group-item">未找到相关广播剧</div>';
                return;
            }
            
            // 显示搜索结果
            searchResults.innerHTML = data.results.map(drama => `
                <div class="list-group-item list-group-item-action" onclick="selectDrama(${drama.drama_id}, '${drama.name}')">
                    <div class="d-flex align-items-center">
                        <div class="me-3" style="width: 60px; height: 80px; background-color: #f8f9fa; display: flex; align-items: center; justify-content: center; border-radius: 4px;">
                            <img src="${drama.cover || 'https://static.missevan.com/assets/images/avatar.png'}" 
                                 class="rounded" 
                                 style="max-width: 100%; max-height: 100%; object-fit: contain;"
                                 onerror="this.src='https://static.missevan.com/assets/images/avatar.png'">
                        </div>
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${drama.name}</h6>
                            <small class="text-muted">作者: ${drama.author || '未知'}</small>
                            <br>
                            <small class="text-muted">ID: ${drama.drama_id}</small>
                        </div>
                    </div>
                </div>
            `).join('');
            
            // 如果只有一个结果，自动选择
            if (data.results.length === 1) {
                const drama = data.results[0];
                selectDrama(drama.drama_id, drama.name);
            }
        })
        .catch(error => {
            console.error('Search error:', error);
            searchResults.innerHTML = `<div class="list-group-item text-danger">搜索失败: ${error.message}</div>`;
        });
}

function selectDrama(dramaId, dramaName) {
    currentDramaId = dramaId;
    document.getElementById('searchInput').value = '';  // 清空搜索框
    document.getElementById('searchResults').classList.add('d-none');
    startCrawl();
}

function startCrawl() {
    if (!currentDramaId) {
        alert('请先选择或输入广播剧ID');
        return;
    }
    
    if (isRunning) {
        return;
    }
    
    const startButton = document.getElementById('searchButton');
    const progressArea = document.getElementById('progressArea');
    const resultArea = document.getElementById('resultArea');
    const log = document.getElementById('log');
    
    // 重置界面
    log.innerHTML = '';
    document.getElementById('progressBar').style.width = '0%';
    progressArea.classList.remove('d-none');
    resultArea.classList.add('d-none');
    startButton.disabled = true;
    isRunning = true;
    
    // 发送请求开始爬取
    fetch('/api/start_crawl', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ drama_id: currentDramaId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            addLog('error', data.error);
            stopCrawl();
        } else {
            // 开始轮询进度
            pollProgress();
        }
    })
    .catch(error => {
        addLog('error', '请求失败: ' + error);
        stopCrawl();
    });
}

function pollProgress() {
    if (!isRunning || !currentDramaId) {
        return;
    }
    
    fetch(`/api/get_progress/${currentDramaId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                addLog('error', data.error);
                stopCrawl();
                return;
            }
            
            // 处理所有新消息
            data.messages.forEach(message => {
                switch (message.status) {
                    case 'progress':
                        updateProgress(message);
                        break;
                    case 'error':
                        addLog('error', message.message);
                        break;
                    case 'no_paid_episodes':
                        addLog('error', message.message);
                        showNoPaidEpisodesError();
                        stopCrawl();
                        return;
                    case 'complete':
                        addLog('success', message.message);
                        showFinalResult(message.message);
                        stopCrawl();
                        return;
                    default:
                        addLog('info', message.message);
                }
            });
            
            // 继续轮询
            if (isRunning) {
                setTimeout(pollProgress, 500);
            }
        })
        .catch(error => {
            addLog('error', '获取进度失败: ' + error);
            stopCrawl();
        });
}

function updateProgress(data) {
    const progress = (data.current / data.total) * 100;
    document.getElementById('progressBar').style.width = `${progress}%`;
    document.getElementById('status').textContent = `进度：${data.current}/${data.total} - ${data.message}`;
}

function addLog(type, message) {
    const log = document.getElementById('log');
    const entry = document.createElement('div');
    entry.className = type;
    entry.textContent = message;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function showFinalResult(message) {
    const resultArea = document.getElementById('resultArea');
    const finalResult = document.getElementById('finalResult');
    resultArea.classList.remove('d-none');
    
    // 从消息中提取广播剧名称和用户数
    const dramaNameMatch = message.match(/广播剧：(.+)/);
    const userCountMatch = message.match(/总计不重复弹幕用户数: (\d+)/);
    
    if (dramaNameMatch && userCountMatch) {
        const dramaName = dramaNameMatch[1];
        const userCount = userCountMatch[1];
        finalResult.innerHTML = `
            <div class="mb-2"><strong>广播剧：</strong>${dramaName}</div>
            <div><strong>总计不重复弹幕用户数：</strong>${userCount}</div>
        `;
    } else {
        finalResult.textContent = message;
    }
    
    resultArea.scrollIntoView({ behavior: 'smooth' });
}

function showNoPaidEpisodesError() {
    const resultArea = document.getElementById('resultArea');
    const finalResult = document.getElementById('finalResult');
    resultArea.classList.remove('d-none');
    finalResult.textContent = '无付费集，请重新选择广播剧';
    finalResult.classList.add('text-danger');
    resultArea.scrollIntoView({ behavior: 'smooth' });
    
    // 重置搜索框
    document.getElementById('searchInput').value = '';
    document.getElementById('searchResults').classList.add('d-none');
}

function stopCrawl() {
    document.getElementById('searchButton').disabled = false;
    isRunning = false;
    currentDramaId = null;
}

// 添加回车键搜索功能
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    
    // 监听回车键
    searchInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault(); // 阻止默认的回车行为
            searchDrama();
        }
    });
}); 