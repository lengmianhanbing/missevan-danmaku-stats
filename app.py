from flask import Flask, render_template, request, jsonify
from crawler import MissEvanCrawler
from flask_cors import CORS
import threading
import queue
import os
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 创建全局爬虫实例
crawler = MissEvanCrawler()

# 用于存储爬取进度的全局变量
crawl_progress = {}

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
        
        # 获取广播剧名称
        try:
            url = f"{crawler.drama_api_url}/getdrama?drama_id={drama_id}"
            response = crawler.session.get(url)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                drama_info = data.get("info", {})
                drama_name = drama_info.get("name", "未知广播剧")
            else:
                drama_name = "未知广播剧"
        except Exception as e:
            print(f"获取广播剧信息失败: {e}")
            drama_name = "未知广播剧"
        
        def crawl_task():
            try:
                # 获取所有分集信息
                episodes = crawler.get_drama_sounds(drama_id)
                if not episodes:
                    progress_queue.put({
                        'status': 'error',
                        'message': "未找到付费分集信息"
                    })
                    return
                
                # 获取每个分集的弹幕数量
                total_danmaku_users = set()  # 用于统计总体的不重复用户数
                total_episodes = len(episodes)
                
                for idx, episode in enumerate(episodes, 1):
                    try:
                        sound_id = episode.get("sound_id")
                        title = episode.get("name", "未知标题")
                        
                        # 更新进度
                        progress = (idx / total_episodes) * 100
                        progress_queue.put({
                            'status': 'progress',
                            'current': idx,
                            'total': total_episodes,
                            'message': f"正在处理: {title}"
                        })
                        
                        if sound_id:
                            # 获取弹幕用户ID
                            danmaku_ids = crawler.get_danmaku_ids(sound_id)
                            total_danmaku_users.update(danmaku_ids)  # 添加到总用户集合中
                            
                            # 添加进度消息
                            progress_queue.put({
                                'status': 'info',
                                'message': f"分集 {title} 弹幕用户数: {len(danmaku_ids)}"
                            })
                            progress_queue.put({
                                'status': 'info',
                                'message': f"当前累计不重复用户数: {len(total_danmaku_users)}"
                            })
                            
                            # 根据进度动态调整延时
                            if idx < total_episodes:
                                delay = 0.5 if idx % 5 != 0 else 1.0  # 每5个请求增加一次延时
                                time.sleep(delay)
                                
                    except Exception as e:
                        progress_queue.put({
                            'status': 'error',
                            'message': f"处理分集时出错: {str(e)}"
                        })
                        continue
                
                # 添加最终结果
                progress_queue.put({
                    'status': 'complete',
                    'message': f"广播剧：{drama_name}\n总计不重复弹幕用户数: {len(total_danmaku_users)}"
                })
                
            except Exception as e:
                progress_queue.put({
                    'status': 'error',
                    'message': f"爬取过程出错: {str(e)}"
                })
        
        # 启动爬虫任务
        thread = threading.Thread(target=crawl_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({'message': '开始爬取', 'drama_id': drama_id})
        
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
        print(f"Request headers: {dict(request.headers)}")  # 添加调试日志
        
        # 尝试将关键词转换为数字（ID）
        try:
            drama_id = int(keyword)
            print(f"Converting keyword to ID: {drama_id}")  # 添加调试日志
            
            # 如果是数字，直接获取广播剧信息
            drama_info = crawler.get_drama_sounds(drama_id)
            if not drama_info:
                print(f"No drama found with ID: {drama_id}")  # 添加调试日志
                return jsonify({'error': '未找到该广播剧'}), 404
                
            # 获取广播剧名称
            drama_name = drama_info[0].get('name', '未知标题') if drama_info else '未知标题'
            print(f"Found drama: {drama_name}")  # 添加调试日志
            
            return jsonify({
                'results': [{
                    'drama_id': drama_id,
                    'name': drama_name,
                    'author': '未知',
                    'cover': 'https://static.missevan.com/assets/images/avatar.png'
                }]
            })
            
        except ValueError:
            print(f"Keyword is not a number, searching by name: {keyword}")  # 添加调试日志
            
            # 如果不是数字，按名称搜索
            try:
                results = crawler.search_drama(keyword)
                print(f"Search results: {results}")  # 添加调试日志
                
                if not results:
                    print(f"No results found for keyword: {keyword}")  # 添加调试日志
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