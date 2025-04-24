from flask import Flask, render_template, request, jsonify
from crawler import MissEvanCrawler
from flask_cors import CORS
import threading
import queue
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 用于存储爬取进度的全局变量
crawl_progress = {}

def crawl_drama(drama_id, progress_queue):
    """执行爬虫操作并更新进度"""
    try:
        crawler = MissEvanCrawler()
        
        # 更新状态：开始获取分集信息
        progress_queue.put({
            'status': 'info',
            'message': f'正在获取广播剧 {drama_id} 的分集信息...'
        })
        
        episodes = crawler.get_drama_sounds(drama_id)
        
        if not episodes:
            progress_queue.put({
                'status': 'error',
                'message': '未找到付费分集信息'
            })
            return
        
        progress_queue.put({
            'status': 'info',
            'message': f'找到 {len(episodes)} 个分集'
        })
        
        total_danmaku_users = set()
        total_episodes = len(episodes)
        
        for idx, episode in enumerate(episodes, 1):
            try:
                sound_id = episode.get("sound_id")
                title = episode.get("name", "未知标题")
                
                progress_queue.put({
                    'status': 'progress',
                    'current': idx,
                    'total': total_episodes,
                    'message': f'正在处理: {title}'
                })
                
                if sound_id:
                    danmaku_ids = crawler.get_danmaku_ids(sound_id)
                    total_danmaku_users.update(danmaku_ids)
                    
                    progress_queue.put({
                        'status': 'info',
                        'message': f'✓ 本集弹幕用户数: {len(danmaku_ids)}'
                    })
                    progress_queue.put({
                        'status': 'info',
                        'message': f'当前累计不重复用户数: {len(total_danmaku_users)}'
                    })
                    
            except Exception as e:
                progress_queue.put({
                    'status': 'error',
                    'message': f'处理分集时出错: {str(e)}'
                })
                continue
        
        # 更新最终结果
        progress_queue.put({
            'status': 'complete',
            'message': f'统计完成！总计不重复弹幕用户数: {len(total_danmaku_users)}'
        })
        
    except Exception as e:
        progress_queue.put({
            'status': 'error',
            'message': f'爬取过程出错: {str(e)}'
        })

@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')

@app.route('/api/start_crawl', methods=['POST'])
def start_crawl():
    """开始爬取数据"""
    try:
        data = request.get_json()
        drama_id = int(data.get('drama_id', 0))
        
        if drama_id <= 0:
            return jsonify({'error': '请输入有效的广播剧ID'}), 400
        
        # 创建新的进度队列
        progress_queue = queue.Queue()
        crawl_progress[drama_id] = progress_queue
        
        # 在新线程中执行爬虫
        thread = threading.Thread(target=crawl_drama, args=(drama_id, progress_queue))
        thread.daemon = True
        thread.start()
        
        return jsonify({'message': '开始获取数据', 'drama_id': drama_id})
        
    except ValueError:
        return jsonify({'error': '请输入有效的数字ID'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_progress/<int:drama_id>')
def get_progress(drama_id):
    """获取爬取进度"""
    try:
        if drama_id not in crawl_progress:
            return jsonify({'error': '未找到该任务'}), 404
            
        progress_queue = crawl_progress[drama_id]
        messages = []
        
        # 获取所有可用的进度消息
        while True:
            try:
                message = progress_queue.get_nowait()
                messages.append(message)
            except queue.Empty:
                break
        
        return jsonify({'messages': messages})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['GET'])
def search_drama():
    """搜索广播剧"""
    try:
        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return jsonify({'error': '请输入搜索关键词'}), 400
            
        crawler = MissEvanCrawler()
        results = crawler.search_drama(keyword)
        
        # 格式化搜索结果
        formatted_results = []
        for drama in results:
            formatted_results.append({
                'id': drama.get('drama_id'),
                'name': drama.get('name'),
                'author': drama.get('author'),
                'cover': drama.get('cover')
            })
        
        return jsonify({'results': formatted_results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port) 