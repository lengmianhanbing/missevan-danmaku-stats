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
    
    fetch(searchUrl, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    })
        .then(response => {
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || `HTTP error! status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Search results:', data);
            
            if (data.error) {
                searchResults.innerHTML = `<div class="list-group-item text-danger">${data.error}</div>`;
                return;
            }
            
            if (!data.results || data.results.length === 0) {
                searchResults.innerHTML = '<div class="list-group-item">未找到相关广播剧，请尝试其他关键词</div>';
                return;
            }
            
            // 显示搜索结果
            searchResults.innerHTML = data.results.map(drama => `
                <div class="list-group-item list-group-item-action" onclick="selectDrama(${drama.drama_id}, '${drama.name}')">
                    <div class="d-flex align-items-center">
                        <img src="${drama.cover}" class="me-3" style="width: 50px; height: 50px; object-fit: cover;" onerror="this.src='https://static.missevan.com/assets/images/avatar.png'">
                        <div>
                            <h6 class="mb-1">${drama.name}</h6>
                            <small class="text-muted">作者: ${drama.author || '未知'}</small>
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
    document.getElementById('searchInput').value = `${dramaName} (ID: ${dramaId})`;
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
    finalResult.textContent = message;
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