from crawler import MissEvanCrawler
import json
from bs4 import BeautifulSoup

def test_search():
    crawler = MissEvanCrawler()
    
    # 测试搜索"燎原"
    keyword = "燎原"
    print(f"\n测试搜索关键词: {keyword}")
    
    try:
        # 直接使用 requests 测试搜索
        import requests
        url = "https://www.missevan.com/dramaapi/search"
        params = {
            "s": keyword,
            "page": 1,
            "type": "drama",
            "order": "1"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://www.missevan.com/mdrama",
            "Origin": "https://www.missevan.com"
        }
        
        print("\n发送请求:")
        print(f"URL: {url}")
        print(f"参数: {json.dumps(params, ensure_ascii=False)}")
        print(f"头部: {json.dumps(headers, ensure_ascii=False)}")
        
        response = requests.get(url, params=params, headers=headers)
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应内容: {response.text[:1000]}")
        
        # 解析 JSON 响应
        data = response.json()
        if data.get("success"):
            results = data.get("info", {}).get("Datas", [])
            print(f"\n找到 {len(results)} 个结果:")
            
            for idx, item in enumerate(results, 1):
                try:
                    print(f"\n{idx}. 广播剧信息:")
                    print(f"   ID: {item.get('id')}")
                    print(f"   名称: {item.get('name')}")
                    print(f"   作者: {item.get('author', '未知')}")
                    print(f"   封面: {item.get('cover')}")
                except Exception as e:
                    print(f"解析第 {idx} 个结果时出错: {str(e)}")
                    continue
        else:
            print(f"\n搜索失败: {data.get('info', '未知错误')}")
            
    except Exception as e:
        print(f"\n测试过程中出错: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    test_search() 