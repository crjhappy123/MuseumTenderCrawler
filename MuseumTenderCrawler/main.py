# -*- coding: utf-8 -*-
import re
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests

# 设置目标网站URL列表
TARGET_URLS = [
    ("Nanjing", "https://njggzy.nanjing.gov.cn/njweb/search/fullsearch.html?wd=%E5%8D%9A%E7%89%A9%E9%A6%86"),
    ("Jiangsu", "http://jsggzy.jszwfw.gov.cn/search/fullsearch.html?wd=%E5%8D%9A%E7%89%A9%E9%A6%86")
]

# 设置输出文件路径（仅用于调试）
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"tender_info_{datetime.now().strftime('%Y%m%d')}.txt")

# 创建输出目录
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 设置请求头，模拟浏览器访问
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# 博物馆相关关键词，用于筛选招标信息
MUSEUM_KEYWORDS = ["博物馆", "展览馆", "文物", "文化遗产"]

def fetch_page(url):
    """使用Selenium获取网页内容，处理动态加载的内容"""
    try:
        # 设置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 无头模式，不显示浏览器界面
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # 指定ChromeDriver路径，如果不在PATH中，请手动设置路径
        from selenium.webdriver.chrome.service import Service
        driver_path = "C:/Users/Rudy/Desktop/Drivers/chromedriver.exe"  # 请替换为您的ChromeDriver路径，如果不同请修改此路径
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 如果ChromeDriver在PATH中，使用此行（请注释掉上面三行）
        # driver = webdriver.Chrome(options=chrome_options)
        # 注意：如果您尚未安装ChromeDriver，请访问 https://chromedriver.chromium.org/home 下载适合您Chrome版本的驱动程序，并将其放置在上述路径中或添加到系统PATH。
        
        # 访问页面
        driver.get(url)
        
        # 等待页面加载完成，等待搜索结果出现
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "search-row"))
        )
        
        # 获取页面内容
        html_content = driver.page_source
        
        # 关闭浏览器
        driver.quit()
        
        return html_content
    except Exception as e:
        print(f"请求过程中发生错误：{e}")
        print("请确保ChromeDriver已安装并添加到系统PATH中，或在脚本中指定ChromeDriver路径。")
        print("下载ChromeDriver：https://chromedriver.chromium.org/home")
        return None

def parse_tenders(html_content, source):
    """解析网页中的招标信息，根据不同来源调整解析逻辑"""
    soup = BeautifulSoup(html_content, 'html.parser')
    tenders = []
    
    if source == "Nanjing":
        # 根据南京市公共资源交易网的HTML结构调整选择器
        tender_items = soup.find_all('li', class_='search-row')
        
        for item in tender_items:
            title_tag = item.find('h2', class_='title').find('a') if item.find('h2', class_='title') else None
            if title_tag:
                title = title_tag.get_text(strip=True)
                link = title_tag.get('onclick', '').split("'")[5] if 'onclick' in title_tag.attrs else ''
                if not link and 'href' in title_tag.attrs:
                    link = title_tag['href']
                
                # 检查标题是否包含博物馆相关关键词
                if any(keyword in title for keyword in MUSEUM_KEYWORDS):
                    tenders.append({
                        'title': title,
                        'link': link,
                        'date': item.find('span', class_='content-date').get_text(strip=True) if item.find('span', class_='content-date') else '未知日期',
                        'source': source
                    })
    elif source == "Jiangsu":
        # 根据江苏公共资源交易网的HTML结构调整选择器
        tender_items = soup.find_all('li', class_='search-row')
        
        for item in tender_items:
            title_tag = item.find('h2', class_='title').find('a') if item.find('h2', class_='title') else None
            if title_tag:
                title = title_tag.get_text(strip=True)
                link = title_tag.get('onclick', '').split("'")[1] if 'onclick' in title_tag.attrs and len(title_tag.get('onclick', '').split("'")) > 1 else ''
                if not link and 'href' in title_tag.attrs:
                    link = title_tag['href']
                
                # 检查标题是否包含博物馆相关关键词
                if any(keyword in title for keyword in MUSEUM_KEYWORDS):
                    date_tag = item.find('span', class_='content-date')
                    tenders.append({
                        'title': title,
                        'link': link,
                        'date': date_tag.get_text(strip=True) if date_tag else '未知日期',
                        'source': source
                    })
    
    return tenders

def format_for_wechat(tenders):
    """格式化招标信息为适合企业微信推送的文本"""
    if not tenders:
        return "未找到博物馆相关的招标信息。"
    
    message = "博物馆相关招标信息更新：\n\n"
    for i, tender in enumerate(tenders, 1):
        message += f"{i}. {tender['title']}\n"
        message += f"   来源: {tender['source']}\n"
        message += f"   日期: {tender['date']}\n"
        message += f"   链接: {tender['link']}\n\n"
    
    return message

def send_wechat_message(content):
    """发送消息到企业微信群"""
    webhook_url = os.environ.get("WECHAT_WEBHOOK_URL")
    if not webhook_url:
        print("缺少 WECHAT_WEBHOOK_URL 配置")
        return
    data = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    try:
        resp = requests.post(webhook_url, json=data)
        resp.raise_for_status()
        print("企业微信消息发送成功")
    except Exception as e:
        print("发送失败：", e)

def main():
    """主函数"""
    print("开始爬取博物馆相关招标信息...")
    all_tenders = []
    
    for source, url in TARGET_URLS:
        print(f"爬取 {source} 网站: {url}")
        html_content = fetch_page(url)
        if html_content:
            # 保存并打印部分HTML内容以便调试
            debug_file = f"debug_html_{source.lower()}.html"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(html_content[:20000])  # 保存前20000个字符以便查看更多内容
            print(f"已保存部分HTML内容到 {debug_file} 以便调试。")
            tenders = parse_tenders(html_content, source)
            if tenders:
                all_tenders.extend(tenders)
                print(f"从 {source} 找到 {len(tenders)} 条博物馆相关招标信息。")
            else:
                print(f"未在 {source} 找到博物馆相关的招标信息。")
        else:
            print(f"无法获取 {source} 网页内容，请检查网络或URL。")
    
    # 格式化输出为企业微信推送格式
    wechat_message = format_for_wechat(all_tenders)
    print("\n企业微信推送格式预览：")
    print(wechat_message)
    
    # 同时保存到文件以便调试
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(wechat_message)
    print(f"已保存输出到 {OUTPUT_FILE} 以便查看完整内容。")
    
    # 发送到企业微信
    send_wechat_message(wechat_message)
    print("爬取完成！")

if __name__ == "__main__":
    main()
