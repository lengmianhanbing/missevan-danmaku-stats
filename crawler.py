import requests
import json
import time
from typing import Dict, List, Optional, Set
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import concurrent.futures
import re

class MissEvanCrawler:
    def __init__(self):
        self.base_url = "https://www.missevan.com"
        self.api_url = "https://www.missevan.com/sound"
        self.drama_api_url = "https://www.missevan.com/dramaapi"
        self.search_api_url = "https://www.missevan.com/dramaapi/searchdrama"
        self.episode_api_url = "https://www.missevan.com/dramaapi/getepisode"
        self.danmaku_api_url = "https://danmaku.missevan.com/v2"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://www.missevan.com/mdrama",
            "Origin": "https://www.missevan.com"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.drama_cache = {}
        self.episode_cache = {}
        self.danmaku_cache = {}
        self.progress_callbacks = {}
        self.running_tasks = {}
        self.max_workers = 5  # 并发请求数量

    def get_sound_info(self, sound_id: int) -> Optional[Dict]:
        """获取声音详细信息"""
        url = f"{self.api_url}/getsound?soundid={sound_id}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data["success"] and "info" in data:
                return data["info"]
            return None
        except Exception as e:
            print(f"获取sound {sound_id}的信息时出错: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text}")
            return None

    def get_danmaku_ids(self, sound_id: int) -> Set[int]:
        """获取一个声音的所有弹幕用户ID"""
        try:
            url = f"{self.danmaku_api_url}/get/{sound_id}"
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success"):
                return set()
            
            # 提取所有弹幕的用户ID
            danmaku_ids = set()
            for danmaku in data.get("info", []):
                user_id = danmaku.get("user_id")
                if user_id:
                    danmaku_ids.add(user_id)
            
            return danmaku_ids
            
        except Exception as e:
            print(f"获取弹幕失败: {e}")
            return set()

    def get_drama_sounds(self, drama_id: int) -> List[Dict]:
        """获取广播剧的所有分集信息"""
        url = f"{self.drama_api_url}/getdrama?drama_id={drama_id}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data["success"] and "info" in data:
                drama_info = data["info"]
                if isinstance(drama_info, dict):
                    episodes = drama_info.get("soundlist", [])
                    
                    # 如果episodes是列表，直接使用
                    if isinstance(episodes, list):
                        # 只获取付费的分集（包括小剧场）
                        paid_episodes = [ep for ep in episodes 
                                      if isinstance(ep, dict) 
                                      and ep.get("price", 0) > 0]
                        return paid_episodes
                    # 如果episodes是字典，提取所有值
                    elif isinstance(episodes, dict):
                        episodes_list = []
                        for ep_id, ep_data in episodes.items():
                            if isinstance(ep_data, list) and len(ep_data) > 0:
                                episodes_list.extend(ep_data)
                            elif isinstance(ep_data, dict):
                                episodes_list.append(ep_data)
                        
                        # 只获取付费的分集（包括小剧场）
                        paid_episodes = [ep for ep in episodes_list 
                                      if isinstance(ep, dict) 
                                      and ep.get("price", 0) > 0]
                        return paid_episodes
            return []
        except Exception as e:
            print(f"获取广播剧 {drama_id} 信息时出错: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text}")
            return []

    def get_danmaku_count(self, sound_id: int) -> Optional[int]:
        """获取指定声音的弹幕数量"""
        url = f"{self.api_url}/getdm?soundid={sound_id}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data["success"] and "info" in data:
                return len(data["info"].get("comments", []))
            return None
        except Exception as e:
            print(f"获取sound {sound_id}的弹幕数量时出错: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text}")
            return None

    def get_cover_image_base64(self, image_url):
        """获取封面图片的base64编码"""
        try:
            response = self.session.get(image_url, headers=self.headers)
            if response.status_code == 200:
                import base64
                return f"data:image/jpeg;base64,{base64.b64encode(response.content).decode('utf-8')}"
            return None
        except Exception as e:
            print(f"获取封面图片失败: {e}")
            return None

    def search_drama(self, keyword):
        """搜索广播剧"""
        try:
            # 尝试将关键词转换为数字（ID）
            try:
                drama_id = int(keyword)
                # 如果是数字，直接获取广播剧信息
                drama_info = self.get_drama_sounds(drama_id)
                if not drama_info:
                    return []
                    
                # 获取广播剧名称
                drama_name = drama_info[0].get('name', '未知标题') if drama_info else '未知标题'
                
                return [{
                    'drama_id': drama_id,
                    'name': drama_name,
                    'author': '未知',
                    'cover': 'https://static.missevan.com/assets/images/avatar.png'
                }]
                
            except ValueError:
                # 如果不是数字，按名称搜索
                url = f"{self.search_api_url}?keyword={keyword}&page=1&limit=10"
                response = self.session.get(url)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("success"):
                    return []
                
                results = []
                for item in data.get("info", {}).get("dramalist", []):
                    # 检查是否有付费集
                    drama_id = item.get("drama_id")
                    if drama_id:
                        sounds = self.get_drama_sounds(drama_id)
                        if sounds:  # 如果有付费集，则添加到结果中
                            results.append({
                                'drama_id': drama_id,
                                'name': item.get("name", "未知标题"),
                                'author': item.get("author", "未知"),
                                'cover': item.get("cover", "https://static.missevan.com/assets/images/avatar.png")
                            })
                
                return results
                
        except Exception as e:
            print(f"搜索广播剧失败: {e}")
            return []

    def get_drama_by_name(self, name: str) -> Optional[Dict]:
        """通过名称获取广播剧信息"""
        try:
            results = self.search_drama(name)
            if not results:
                return None
                
            # 找到名称完全匹配的结果
            for drama in results:
                if drama['name'] == name:
                    return drama
                    
            # 如果没有完全匹配，返回第一个结果
            return results[0] if results else None
            
        except Exception as e:
            print(f"通过名称获取广播剧时出错: {str(e)}")
            return None

    def process_episode(self, episode):
        """处理单个分集"""
        try:
            sound_id = episode.get("sound_id")
            title = episode.get("name", "未知标题")
            
            if sound_id:
                # 获取弹幕用户ID
                danmaku_ids = self.get_danmaku_ids(sound_id)
                return {
                    'title': title,
                    'user_count': len(danmaku_ids),
                    'user_ids': danmaku_ids
                }
        except Exception as e:
            print(f"处理分集失败: {e}")
        return None

    def crawl_drama(self, drama_id, progress_queue=None):
        """爬取指定广播剧的所有付费分集弹幕"""
        try:
            # 获取所有分集信息
            episodes = self.get_drama_sounds(drama_id)
            if not episodes:
                if progress_queue:
                    progress_queue.put({
                        'status': 'error',
                        'message': "未找到付费分集信息"
                    })
                return set()
            
            # 使用线程池并发处理分集
            total_danmaku_users = set()
            total_episodes = len(episodes)
            processed_count = 0
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_episode = {
                    executor.submit(self.process_episode, episode): episode 
                    for episode in episodes
                }
                
                # 处理完成的任务
                for future in concurrent.futures.as_completed(future_to_episode):
                    episode = future_to_episode[future]
                    processed_count += 1
                    
                    try:
                        result = future.result()
                        if result:
                            total_danmaku_users.update(result['user_ids'])
                            
                            # 更新进度
                            if progress_queue:
                                progress_queue.put({
                                    'status': 'progress',
                                    'current': processed_count,
                                    'total': total_episodes,
                                    'message': f"正在处理: {result['title']}"
                                })
                                
                                progress_queue.put({
                                    'status': 'info',
                                    'message': f"分集 {result['title']} 弹幕用户数: {result['user_count']}"
                                })
                                
                                progress_queue.put({
                                    'status': 'info',
                                    'message': f"当前累计不重复用户数: {len(total_danmaku_users)}"
                                })
                    except Exception as e:
                        print(f"处理分集结果失败: {e}")
                        continue
            
            return total_danmaku_users
            
        except Exception as e:
            print(f"爬取广播剧失败: {e}")
            if progress_queue:
                progress_queue.put({
                    'status': 'error',
                    'message': f"爬取过程出错: {str(e)}"
                })
            return set()

def main():
    crawler = MissEvanCrawler()
    
    print("=== 猫耳FM弹幕爬虫 ===")
    print("提示：您可以从猫耳FM网站上找到广播剧ID，例如：")
    print("https://www.missevan.com/mdrama/drama/21089 中的 21089 就是广播剧ID")
    print()
    
    # 输入广播剧ID
    drama_id = input("请输入广播剧ID（按Ctrl+C可随时退出）: ")
    try:
        drama_id = int(drama_id)
    except ValueError:
        print("错误：请输入有效的数字ID")
        return

    # 获取广播剧信息
    url = f"{crawler.drama_api_url}/getdrama?drama_id={drama_id}"
    try:
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

    # 获取所有分集信息
    print(f"\n正在获取广播剧 {drama_name} 的分集信息...")
    episodes = crawler.get_drama_sounds(drama_id)
    
    if not episodes:
        print("未找到付费分集信息")
        return

    print(f"\n找到 {len(episodes)} 个正剧分集")
    print("\n开始获取每个分集的弹幕数量（去重后的用户数）...")

    # 获取每个分集的弹幕数量
    total_danmaku_users = set()  # 用于统计总体的不重复用户数
    total_episodes = len(episodes)
    
    for idx, episode in enumerate(episodes, 1):
        try:
            sound_id = episode.get("sound_id")
            title = episode.get("name", "未知标题")
            
            # 显示进度
            print(f"\n[{idx}/{total_episodes}] 正在处理: {title}")
            
            if sound_id:
                # 获取弹幕用户ID
                danmaku_ids = crawler.get_danmaku_ids(sound_id)
                total_danmaku_users.update(danmaku_ids)  # 添加到总用户集合中
                
                print(f"✓ 分集弹幕用户数: {len(danmaku_ids)}")
                print(f"当前累计不重复用户数: {len(total_danmaku_users)}")
                
                # 根据进度动态调整延时
                if idx < total_episodes:
                    delay = 0.5 if idx % 5 != 0 else 1.0  # 每5个请求增加一次延时
                    time.sleep(delay)
                    
        except Exception as e:
            print(f"处理分集时出错: {str(e)}")
            continue
    
    print(f"\n=== 统计完成 ===")
    print(f"广播剧：{drama_name}")
    print(f"总计不重复弹幕用户数: {len(total_danmaku_users)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已被用户中断")
    except Exception as e:
        print(f"\n程序出错: {str(e)}")