let currentDramaId = null;
let isRunning = false;

function startCrawl() {
    const dramaId = document.getElementById('dramaId').value.trim();
    const startButton = document.getElementById('startButton');
    const progressArea = document.getElementById('progressArea');
    const resultArea = document.getElementById('resultArea');
    const log = document.getElementById('log');
    
    if (!dramaId) {
        alert('请输入广播剧ID');
        return;
    }
    
    if (isRunning) {
        return;
    }
    
    // 重置界面
    log.innerHTML = '';
    document.getElementById('progressBar').style.width = '0%';
    progressArea.classList.remove('d-none');
    resultArea.classList.add('d-none');
    startButton.disabled = true;
    isRunning = true;
    currentDramaId = dramaId;
    
    // 发送请求开始爬取
    fetch('/api/start_crawl', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ drama_id: dramaId })
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

function stopCrawl() {
    document.getElementById('startButton').disabled = false;
    isRunning = false;
    currentDramaId = null;
} 