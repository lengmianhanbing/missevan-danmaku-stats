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
            
        print(f"Searching for drama: {keyword}")  # 添加调试日志
        
        crawler = MissEvanCrawler()
        
        # 尝试将关键词转换为数字（ID）
        try:
            drama_id = int(keyword)
            # 如果是数字，直接获取广播剧信息
            drama_info = crawler.get_drama_sounds(drama_id)
            if not drama_info:
                return jsonify({'error': '未找到该广播剧'}), 404
                
            # 获取广播剧名称
            drama_name = drama_info[0].get('name', '未知标题') if drama_info else '未知标题'
            
            return jsonify({
                'results': [{
                    'drama_id': drama_id,
                    'name': drama_name,
                    'author': '未知',
                    'cover': 'https://static.missevan.com/assets/images/avatar.png'
                }]
            })
            
        except ValueError:
            # 如果不是数字，按名称搜索
            try:
                results = crawler.search_drama(keyword)
                print(f"Search results: {results}")  # 添加调试日志
                
                if not results:
                    # 尝试使用备用搜索方法
                    drama = crawler.get_drama_by_name(keyword)
                    if drama:
                        return jsonify({'results': [drama]})
                    return jsonify({'results': [], 'message': '未找到相关广播剧'})
                
                return jsonify({'results': results})
            except Exception as e:
                print(f"Search error: {str(e)}")  # 添加调试日志
                return jsonify({'error': f'搜索失败: {str(e)}'}), 500
        
    except Exception as e:
        print(f"Search error: {str(e)}")  # 添加调试日志
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port) 