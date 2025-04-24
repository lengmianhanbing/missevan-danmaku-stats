import requests
import json
import time
from typing import Dict, List, Optional, Set
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

class MissEvanCrawler:
    def __init__(self):
        self.base_url = "https://www.missevan.com"
        self.api_url = "https://www.missevan.com/sound"
        self.drama_api_url = "https://www.missevan.com/dramaapi"
        self.search_api_url = "https://www.missevan.com/dramaapi/search"
        self.episode_api_url = "https://www.missevan.com/dramaapi/getepisode"
        self.danmaku_api_url = "https://www.missevan.com/dramaapi/getdanmaku"
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
            # 使用网页版评论API
            url = f"https://www.missevan.com/sound/getdm?soundid={sound_id}"
            response = self.session.get(url)
            response.raise_for_status()  # 检查HTTP错误
            
            # 解析XML格式的弹幕数据
            root = ET.fromstring(response.text)
            user_ids = set()
            
            # 遍历所有弹幕
            for d in root.findall('.//d'):
                try:
                    # 弹幕属性格式：p="时间,模式,字体大小,颜色,发送时间,弹幕池,用户ID,弹幕ID"
                    attrs = d.get('p').split(',')
                    if len(attrs) >= 7:
                        user_id = int(attrs[6])
                        user_ids.add(user_id)
                except (ValueError, IndexError) as e:
                    print(f"解析弹幕属性时出错: {str(e)}")
                    continue
            
            return user_ids
            
        except requests.exceptions.RequestException as e:
            print(f"获取sound {sound_id}的弹幕时出错: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text}")
            return set()
        except ET.ParseError as e:
            print(f"解析XML数据时出错: {str(e)}")
            return set()
        except Exception as e:
            print(f"处理弹幕数据时出错: {str(e)}")
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
                    episodes = drama_info.get("episodes", [])
                    
                    # 如果episodes是列表，直接使用
                    if isinstance(episodes, list):
                        # 只获取付费的分集（包括小剧场）
                        paid_episodes = [ep for ep in episodes 
                                      if isinstance(ep, dict) 
                                      and ep.get("need_pay") == 1]
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
                                      and ep.get("need_pay") == 1]
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
            # 使用猫耳 FM 的搜索 API
            url = f"{self.search_api_url}"
            params = {
                "s": keyword,
                "page": 1,
                "type": "drama",
                "order": "1"
            }
            
            print(f"Searching with URL: {url} and params: {params}")  # 调试日志
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            print(f"Response status: {response.status_code}")  # 调试日志
            
            data = response.json()
            if not data.get("success"):
                print(f"搜索失败: {data.get('info', '未知错误')}")
                return []
            
            results = data.get("info", {}).get("Datas", [])
            print(f"Found {len(results)} drama items")  # 调试日志
            
            # 格式化结果并过滤掉完全免费的广播剧
            formatted_results = []
            for item in results:
                try:
                    drama_id = item.get('id')
                    if not drama_id:
                        continue
                        
                    # 获取广播剧的分集信息
                    episodes = self.get_drama_sounds(drama_id)
                    if not episodes:  # 如果没有付费集，跳过这个广播剧
                        continue
                        
                    formatted_results.append({
                        'drama_id': drama_id,
                        'name': item.get('name'),
                        'author': item.get('author', '未知'),
                        'cover': item.get('cover')  # 直接使用原始图片URL
                    })
                except Exception as e:
                    print(f"解析广播剧项时出错: {str(e)}")
                    continue
            
            print(f"Found {len(formatted_results)} dramas with paid episodes")  # 调试日志
            return formatted_results
            
        except requests.exceptions.RequestException as e:
            print(f"搜索请求失败: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text}")
            return []
        except Exception as e:
            print(f"搜索广播剧时出错: {str(e)}")
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
    drama_info = crawler.get_sound_info(drama_id)
    drama_name = drama_info.get("name", "未知广播剧") if drama_info else "未知广播剧"

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