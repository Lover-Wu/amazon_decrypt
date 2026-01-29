import requests
import json
import os
import time
import random
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import sys
import re
import urllib.parse
from urllib.parse import urlparse, urljoin
from abc import ABC, abstractmethod
import yaml

# 获取当前Python文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"当前文件目录: {current_dir}")


class BaseEcommerceCrawler(ABC):
    """电商爬虫基类"""

    def __init__(self, site_config):
        """
        初始化爬虫
        site_config: 网站配置字典
        """
        self.site_config = site_config
        self.base_url = site_config.get('base_url', '')
        self.site_name = site_config.get('name', 'unknown')

        # 使用真实请求头
        self.base_headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Chromium";v="120", "Not(A:Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

        # 使用Session保持会话
        self.session = requests.Session()
        self.session.headers.update(self.base_headers)

        # 代理设置
        self.proxies = None

        # Cookies管理
        self.cookies = {}
        self.cookies_file = os.path.join(current_dir, f'cookies_{self.site_name}.json')

        # 数据保存目录
        self.data_dir = os.path.join(current_dir, 'ecommerce_data', self.site_name)

        # 初始化
        self.init_cookies()
        self.create_directories()

    # ==================== 抽象方法（子类必须实现） ====================

    @abstractmethod
    def build_search_url(self, keyword, page=1):
        """构建搜索URL - 子类必须实现"""
        pass

    @abstractmethod
    def parse_search_results(self, html):
        """解析搜索结果页面 - 子类必须实现"""
        pass

    @abstractmethod
    def extract_product_basic_info(self, product_element):
        """从商品元素提取基本信息 - 子类必须实现"""
        pass

    @abstractmethod
    def extract_product_details(self, soup):
        """提取商品详情信息 - 子类必须实现"""
        pass

    # ==================== 通用方法 ====================

    def create_directories(self):
        """创建保存数据的目录"""
        directories = [
            self.data_dir,
            os.path.join(self.data_dir, 'products'),
            os.path.join(self.data_dir, 'images'),
            os.path.join(self.data_dir, 'details'),
            os.path.join(self.data_dir, 'logs')
        ]

        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"创建目录: {directory}")

    def init_cookies(self):
        """初始化cookies"""
        print(f"正在初始化 {self.site_name} 的cookies...")

        # 尝试从文件加载cookies
        if os.path.exists(self.cookies_file):
            try:
                with open(self.cookies_file, 'r') as f:
                    saved_cookies = json.load(f)
                    self.cookies = saved_cookies
                    self.session.cookies.update(self.cookies)
                    print(f"从文件加载了 {len(self.cookies)} 个cookies")
                    return
            except Exception as e:
                print(f"加载cookies文件失败: {e}")

        # 尝试获取初始cookies
        self.refresh_cookies()

    def refresh_cookies(self):
        """刷新cookies"""
        print(f"刷新 {self.site_name} 的cookies...")
        try:
            response = self.session.get(self.base_url, timeout=10)
            self.cookies = self.session.cookies.get_dict()

            if self.cookies:
                # 保存cookies到文件
                with open(self.cookies_file, 'w') as f:
                    json.dump(self.cookies, f)
                print(f"成功获取并保存 {len(self.cookies)} 个cookies")
            else:
                print("未获取到cookies，使用默认配置")

        except Exception as e:
            print(f"刷新cookies时出错: {e}")

    def get_random_user_agent(self):
        """获取随机User-Agent"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        ]
        return random.choice(user_agents)

    def get_headers(self, referer=None):
        """获取请求头"""
        headers = self.base_headers.copy()
        headers['user-agent'] = self.get_random_user_agent()

        if referer:
            headers['referer'] = referer

        # 添加网站特定的headers
        site_headers = self.site_config.get('headers', {})
        headers.update(site_headers)

        return headers

    def make_request(self, url, max_retries=3):
        """发送请求"""
        for attempt in range(max_retries):
            try:
                headers = self.get_headers(referer=self.base_url)

                response = self.session.get(
                    url,
                    headers=headers,
                    cookies=self.cookies,
                    proxies=self.proxies,
                    timeout=30,
                    allow_redirects=True,
                    verify=True
                )

                print(f"状态码: {response.status_code}, URL: {url[:80]}...")

                if response.status_code == 200:
                    # 更新cookies
                    self.cookies.update(self.session.cookies.get_dict())

                    # 检查是否需要刷新cookies
                    if self.should_refresh_cookies(response):
                        print("检测到可能需要刷新cookies...")
                        self.refresh_cookies()
                        time.sleep(random.uniform(5, 10))
                        continue

                    return response

                elif response.status_code in [403, 429]:
                    print(f"访问受限 ({response.status_code})，等待后重试...")
                    time.sleep(random.uniform(10, 20))
                    self.refresh_cookies()

                elif response.status_code == 503:
                    print(f"服务不可用 (503)，等待后重试...")
                    time.sleep(random.uniform(15, 25))

                else:
                    print(f"尝试 {attempt + 1}/{max_retries}: 状态码 {response.status_code}")
                    time.sleep(random.uniform(5, 8))

            except requests.exceptions.RequestException as e:
                print(f"尝试 {attempt + 1}/{max_retries}: 请求异常 - {e}")
                time.sleep(random.uniform(5, 8))

        print(f"请求失败: {url}")
        return None

    def should_refresh_cookies(self, response):
        """判断是否需要刷新cookies"""
        text_lower = response.text.lower()

        # 检查常见的验证页面关键词
        verification_keywords = [
            'captcha',
            'verification',
            'security check',
            'enter characters',
            'robot check',
            '人机验证',
            '验证码'
        ]

        for keyword in verification_keywords:
            if keyword in text_lower:
                return True

        # 检查是否被重定向到非商品页面
        if 'product' not in response.url and 'item' not in response.url:
            if 'search' not in response.url and 'home' in response.url:
                return True

        return False

    def search_products(self, keyword, pages=1, get_details=False):
        """搜索商品并获取详情"""
        all_products = []

        for page in range(1, pages + 1):
            print(f"\n正在搜索第 {page} 页，关键词: {keyword}")

            # 构建搜索URL
            search_url = self.build_search_url(keyword, page)
            print(f"搜索URL: {search_url}")

            try:
                response = self.make_request(search_url)
                if response:
                    products = self.parse_search_results(response.text)

                    if products:
                        print(f"第 {page} 页找到 {len(products)} 个商品")

                        # 如果需要获取详情
                        if get_details:
                            products = self.enrich_products_with_details(products)

                        all_products.extend(products)

                        # 显示一些商品信息
                        for i, product in enumerate(products[:3], 1):
                            title = product.get('title', 'N/A')[:50]
                            price = product.get('price', 'N/A')
                            print(f"  {i}. {title} - {price}")
                    else:
                        print(f"第 {page} 页未找到商品")

                    # 随机延迟
                    delay = random.uniform(2, 6)
                    time.sleep(delay)

                    # 每2页刷新一次cookies
                    if page % 2 == 0:
                        self.refresh_cookies()

                else:
                    print(f"第 {page} 页请求失败")

            except Exception as e:
                print(f"搜索第 {page} 页时出错: {e}")
                import traceback
                traceback.print_exc()

            # 如果商品数量很少，可能没有更多页面了
            if products and len(products) < 3 and page > 1:
                print("商品数量较少，停止翻页")
                break

        return all_products

    def enrich_products_with_details(self, products):
        """为商品列表获取详细信息"""
        print(f"\n开始获取商品详情...")
        enriched_products = []

        for i, product in enumerate(products, 1):
            if 'url' in product:
                print(f"[{i}/{len(products)}] 获取详情: {product.get('title', 'N/A')[:50]}...")

                details = self.get_product_details(product['url'])
                if details:
                    product.update(details)

                # 避免请求过快
                time.sleep(random.uniform(1, 3))

            enriched_products.append(product)

        return enriched_products

    def get_product_details(self, product_url):
        """获取商品详情页面信息"""
        if not product_url:
            return {}

        try:
            response = self.make_request(product_url)
            if not response:
                return {}

            soup = BeautifulSoup(response.text, 'html.parser')
            return self.extract_product_details(soup)

        except Exception as e:
            print(f"获取商品详情时出错: {e}")
            return {}

    def download_image(self, image_url, product_id):
        """下载商品图片"""
        if not image_url or not product_id:
            return None

        try:
            headers = self.get_headers()
            response = requests.get(image_url, headers=headers, timeout=15)

            if response.status_code == 200:
                # 生成文件名
                filename = f"{product_id}_{int(time.time())}.jpg"
                image_path = os.path.join(self.data_dir, 'images', filename)

                with open(image_path, 'wb') as f:
                    f.write(response.content)

                print(f"✓ 图片下载成功: {filename}")
                return image_path

        except Exception as e:
            print(f"下载图片时出错: {e}")

        return None

    def save_to_csv(self, products, keyword):
        """保存数据到CSV文件"""
        if not products:
            print("没有数据可保存")
            return None

        # 确定字段
        fieldnames = set()
        for product in products:
            fieldnames.update(product.keys())

        fieldnames = list(fieldnames)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
        filename = f"{self.site_name}_{safe_keyword}_{timestamp}.csv"
        filepath = os.path.join(self.data_dir, filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for product in products:
                row = {}
                for field in fieldnames:
                    value = product.get(field, '')
                    if isinstance(value, (list, dict)):
                        row[field] = str(value)
                    else:
                        row[field] = value
                writer.writerow(row)

        print(f"\n数据已保存到: {filepath}")
        print(f"共保存 {len(products)} 条记录，包含 {len(fieldnames)} 个字段")
        return filepath

    def save_to_json(self, products, keyword):
        """保存数据到JSON文件"""
        if not products:
            print("没有数据可保存")
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
        filename = f"{self.site_name}_{safe_keyword}_{timestamp}.json"
        filepath = os.path.join(self.data_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(products, jsonfile, ensure_ascii=False, indent=2, default=str)

        print(f"数据已保存到: {filepath}")
        return filepath


# ==================== 具体网站实现 ====================

class AmazonCrawler(BaseEcommerceCrawler):
    """亚马逊爬虫"""

    def build_search_url(self, keyword, page=1):
        """构建亚马逊搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)

        if page == 1:
            return f"{self.base_url}/s?k={keyword_encoded}"
        else:
            return f"{self.base_url}/s?k={keyword_encoded}&page={page}"

    def parse_search_results(self, html):
        """解析亚马逊搜索结果"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # 尝试多种选择器
        product_selectors = [
            'div[data-component-type="s-search-result"]',
            'div.s-result-item',
            'div[data-asin]',
            '.s-main-slot .s-result-item'
        ]

        for selector in product_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    try:
                        product_data = self.extract_product_basic_info(element)
                        if product_data and product_data.get('asin'):
                            products.append(product_data)
                    except Exception as e:
                        continue

                if products:
                    break

        return products

    def extract_product_basic_info(self, element):
        """提取亚马逊商品基本信息"""
        data = {}

        # 提取ASIN
        asin = element.get('data-asin', '')
        if not asin:
            # 尝试从链接中提取
            link_elem = element.select_one('a.a-link-normal')
            if link_elem and link_elem.get('href'):
                match = re.search(r'/dp/([A-Z0-9]{10})', link_elem['href'])
                if match:
                    asin = match.group(1)

        if not asin:
            return None

        data['asin'] = asin
        data['product_id'] = asin

        # 提取基本信息
        data['title'] = self.extract_text(element, ['h2 a span', '.a-text-normal', '.a-size-medium'])
        data['url'] = self.extract_url(element)
        data['price'] = self.extract_price(element)
        data['original_price'] = self.extract_original_price(element)
        data['rating'] = self.extract_rating(element)
        data['reviews'] = self.extract_reviews(element)
        data['image_url'] = self.extract_image_url(element)

        # 提取徽章信息
        data['best_seller'] = self.extract_badge(element, ['best seller', 'bestseller'])
        data['amazon_choice'] = self.extract_badge(element, ["amazon's choice", 'amazon choice'])
        data['sponsored'] = self.extract_badge(element, ['sponsored'])

        # 提取Prime信息
        data['prime_eligible'] = self.extract_badge(element, ['prime'])

        # 爬取时间
        data['crawled_at'] = datetime.now().isoformat()
        data['source'] = 'amazon'

        # 移除空值
        data = {k: v for k, v in data.items() if v is not None}

        return data

    def extract_product_details(self, soup):
        """提取亚马逊商品详情"""
        details = {}

        # 提取品牌
        details['brand'] = self.extract_text(soup, ['#bylineInfo', '#brand'])

        # 提取描述
        desc_elem = soup.select_one('#productDescription')
        if desc_elem:
            details['description'] = desc_elem.text.strip()

        # 提取销售排名
        rank_elem = soup.select_one('#productDetails_detailBullets_sections1')
        if rank_elem:
            rank_text = rank_elem.text
            match = re.search(r'#(\d+,?\d*,?\d*)', rank_text)
            if match:
                details['sales_rank'] = match.group(1)

        # 提取技术规格
        specs = {}
        spec_rows = soup.select('#productDetails_techSpec_section_1 tr')
        for row in spec_rows:
            th = row.select_one('th')
            td = row.select_one('td')
            if th and td:
                key = th.text.strip().replace('\u200e', '')
                value = td.text.strip().replace('\u200e', '')
                specs[key] = value

        if specs:
            details['specifications'] = specs

        return details

    # 辅助方法
    def extract_text(self, element, selectors):
        """使用多个选择器提取文本"""
        for selector in selectors:
            elem = element.select_one(selector)
            if elem and elem.text.strip():
                return elem.text.strip()
        return None

    def extract_url(self, element):
        """提取商品链接"""
        link_elem = element.select_one('h2 a, a.a-link-normal')
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            if href.startswith('/'):
                return urljoin(self.base_url, href)
            elif 'http' in href:
                return href
        return None

    def extract_price(self, element):
        """提取价格"""
        price_elem = element.select_one('.a-price .a-offscreen, .a-price-whole')
        if price_elem:
            price_text = price_elem.text.strip()
            # 清理价格文本
            price_text = re.sub(r'[^\d.,]', '', price_text)
            return price_text
        return None

    def extract_original_price(self, element):
        """提取原价"""
        price_elem = element.select_one('.a-text-price .a-offscreen')
        if price_elem:
            price_text = price_elem.text.strip()
            price_text = re.sub(r'[^\d.,]', '', price_text)
            return price_text
        return None

    def extract_rating(self, element):
        """提取评分"""
        rating_elem = element.select_one('.a-icon-alt')
        if rating_elem:
            rating_text = rating_elem.text.strip()
            match = re.search(r'(\d+\.?\d*)', rating_text)
            if match:
                return match.group(1)
        return None

    def extract_reviews(self, element):
        """提取评价数量"""
        reviews_elem = element.select_one('.a-size-base.s-underline-text, span[aria-label*="stars"]')
        if reviews_elem:
            text = reviews_elem.text.strip()
            match = re.search(r'(\d+,?\d*)', text)
            if match:
                return match.group(1)
        return None

    def extract_image_url(self, element):
        """提取图片URL"""
        img_elem = element.select_one('img.s-image')
        if img_elem:
            for attr in ['src', 'data-src', 'data-old-hires']:
                if img_elem.get(attr):
                    return img_elem[attr]
        return None

    def extract_badge(self, element, keywords):
        """提取徽章信息"""
        element_text = str(element).lower()
        for keyword in keywords:
            if keyword in element_text:
                return keyword.title()
        return None


class EbayCrawler(BaseEcommerceCrawler):
    """eBay爬虫"""

    def build_search_url(self, keyword, page=1):
        """构建eBay搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)
        return f"{self.base_url}/sch/i.html?_nkw={keyword_encoded}&_pgn={page}"

    def parse_search_results(self, html):
        """解析eBay搜索结果"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # eBay商品选择器
        items = soup.select('.s-item')

        for item in items:
            try:
                product_data = self.extract_product_basic_info(item)
                if product_data and product_data.get('item_id'):
                    products.append(product_data)
            except Exception as e:
                continue

        return products

    def extract_product_basic_info(self, element):
        """提取eBay商品基本信息"""
        data = {}

        # 提取商品ID
        item_id = element.get('data-view', '')
        if not item_id:
            return None

        data['item_id'] = item_id
        data['product_id'] = item_id

        # 提取基本信息
        data['title'] = self.extract_text(element, ['.s-item__title'])
        data['url'] = self.extract_url(element)
        data['price'] = self.extract_price(element)
        data['shipping_price'] = self.extract_shipping_price(element)
        data['rating'] = self.extract_rating(element)
        data['reviews'] = self.extract_reviews(element)
        data['image_url'] = self.extract_image_url(element)

        # 提取卖家信息
        data['seller'] = self.extract_text(element, ['.s-item__seller-info-text'])

        # 提取商品状态
        data['condition'] = self.extract_text(element, ['.SECONDARY_INFO'])

        data['crawled_at'] = datetime.now().isoformat()
        data['source'] = 'ebay'

        return {k: v for k, v in data.items() if v is not None}

    def extract_product_details(self, soup):
        """提取eBay商品详情"""
        details = {}

        # 提取卖家信息
        seller_elem = soup.select_one('.mbg-nw')
        if seller_elem:
            details['seller_name'] = seller_elem.text.strip()

        # 提取描述
        desc_elem = soup.select_one('#desc_div')
        if desc_elem:
            details['description'] = desc_elem.text.strip()[:1000]

        # 提取商品属性
        attrs = {}
        attr_rows = soup.select('.ux-layout-section__row')
        for row in attr_rows:
            label = row.select_one('.ux-labels-values__labels')
            value = row.select_one('.ux-labels-values__values')
            if label and value:
                attrs[label.text.strip()] = value.text.strip()

        if attrs:
            details['attributes'] = attrs

        return details

    # eBay特定的提取方法
    def extract_shipping_price(self, element):
        """提取运费"""
        shipping_elem = element.select_one('.s-item__shipping')
        if shipping_elem:
            shipping_text = shipping_elem.text.strip()
            match = re.search(r'[\d.,]+', shipping_text)
            if match:
                return match.group(0)
        return None


class AlibabaCrawler(BaseEcommerceCrawler):
    """阿里巴巴爬虫"""

    def build_search_url(self, keyword, page=1):
        """构建阿里巴巴搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)
        return f"{self.base_url}/trade/search?fsb=y&IndexArea=product_en&CatId=&SearchText={keyword_encoded}&page={page}"

    def parse_search_results(self, html):
        """解析阿里巴巴搜索结果"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        items = soup.select('.organic-list .item-content')

        for item in items:
            try:
                product_data = self.extract_product_basic_info(item)
                if product_data:
                    products.append(product_data)
            except Exception as e:
                continue

        return products

    def extract_product_basic_info(self, element):
        """提取阿里巴巴商品基本信息"""
        data = {}

        # 提取基本信息
        data['title'] = self.extract_text(element, ['.title'])
        data['url'] = self.extract_url(element)
        data['price_range'] = self.extract_text(element, ['.price'])
        data['image_url'] = self.extract_image_url(element)

        # 提取供应商信息
        data['supplier'] = self.extract_text(element, ['.company-name'])
        data['supplier_location'] = self.extract_text(element, ['.location'])

        # 提取交易信息
        data['min_order'] = self.extract_text(element, ['.moq'])

        data['crawled_at'] = datetime.now().isoformat()
        data['source'] = 'alibaba'

        return {k: v for k, v in data.items() if v is not None}


# ==================== 配置管理器 ====================

class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file="sites_config.yaml"):
        self.config_file = os.path.join(current_dir, config_file)
        self.sites_config = self.load_config()

    def load_config(self):
        """加载配置文件"""
        default_config = {
            'amazon': {
                'name': 'amazon',
                'base_url': 'https://www.amazon.com',
                'crawler_class': 'AmazonCrawler',
                'headers': {
                    'authority': 'www.amazon.com',
                    'method': 'GET',
                    'scheme': 'https'
                }
            },
            'ebay': {
                'name': 'ebay',
                'base_url': 'https://www.ebay.com',
                'crawler_class': 'EbayCrawler',
                'headers': {
                    'authority': 'www.ebay.com',
                    'method': 'GET',
                    'scheme': 'https'
                }
            },
            'alibaba': {
                'name': 'alibaba',
                'base_url': 'https://www.alibaba.com',
                'crawler_class': 'AlibabaCrawler',
                'headers': {
                    'authority': 'www.alibaba.com',
                    'method': 'GET',
                    'scheme': 'https'
                }
            }
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            else:
                # 创建默认配置文件
                self.save_config(default_config)
                return default_config
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return default_config

    def save_config(self, config):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            print(f"配置文件已保存: {self.config_file}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def add_site(self, site_name, site_config):
        """添加新网站配置"""
        if site_name not in self.sites_config:
            self.sites_config[site_name] = site_config
            self.save_config(self.sites_config)
            print(f"已添加网站: {site_name}")
        else:
            print(f"网站 {site_name} 已存在")

    def get_site_config(self, site_name):
        """获取网站配置"""
        return self.sites_config.get(site_name)


# ==================== 爬虫工厂 ====================

class CrawlerFactory:
    """爬虫工厂"""

    @staticmethod
    def create_crawler(site_name, config_manager=None):
        """创建爬虫实例"""
        if not config_manager:
            config_manager = ConfigManager()

        site_config = config_manager.get_site_config(site_name)
        if not site_config:
            raise ValueError(f"找不到网站配置: {site_name}")

        crawler_class_name = site_config.get('crawler_class', 'AmazonCrawler')

        # 根据类名创建实例
        crawler_classes = {
            'AmazonCrawler': AmazonCrawler,
            'EbayCrawler': EbayCrawler,
            'AlibabaCrawler': AlibabaCrawler
        }

        crawler_class = crawler_classes.get(crawler_class_name)
        if not crawler_class:
            raise ValueError(f"找不到爬虫类: {crawler_class_name}")

        return crawler_class(site_config)


# ==================== 主程序 ====================

def main():
    """主函数"""
    print("=" * 60)
    print("通用电商网站爬虫框架 v2.0")
    print("=" * 60)

    # 初始化配置管理器
    config_manager = ConfigManager()

    # 显示可用网站
    print("\n可用网站列表:")
    sites = list(config_manager.sites_config.keys())
    for i, site in enumerate(sites, 1):
        print(f"{i}. {site.capitalize()} - {config_manager.sites_config[site]['base_url']}")

    print(f"{len(sites) + 1}. 添加新网站")

    # 选择网站
    try:
        choice = input(f"\n请选择网站 (1-{len(sites) + 1}): ").strip()

        if choice == str(len(sites) + 1):
            # 添加新网站
            add_new_site(config_manager)
            return

        site_index = int(choice) - 1
        if 0 <= site_index < len(sites):
            site_name = sites[site_index]
        else:
            print("选择无效，使用默认网站: Amazon")
            site_name = 'amazon'
    except:
        site_name = 'amazon'

    # 创建爬虫
    try:
        crawler = CrawlerFactory.create_crawler(site_name, config_manager)
        print(f"\n已创建 {site_name.capitalize()} 爬虫")
    except Exception as e:
        print(f"创建爬虫失败: {e}")
        return

    # 用户输入
    keyword = input("\n请输入要搜索的商品关键词: ").strip()
    if not keyword:
        print("关键词不能为空!")
        return

    try:
        pages = int(input("请输入要爬取的页数 (1-10): ").strip() or "1")
        pages = max(1, min(pages, 10))
    except:
        pages = 1

    get_details = input("\n是否获取商品详细信息? (y/n): ").strip().lower() == 'y'
    download_images = input("是否下载商品图片? (y/n): ").strip().lower() == 'y'

    print(f"\n开始爬取 {site_name.capitalize()} 商品: {keyword}")
    print(f"爬取页数: {pages}")
    print("=" * 60)

    # 搜索商品
    products = crawler.search_products(keyword, pages=pages, get_details=get_details)

    if not products:
        print("\n没有找到商品!")
        return

    print(f"\n搜索完成，共找到 {len(products)} 个商品")

    # 下载图片
    if download_images and products:
        print("\n开始下载商品图片...")
        for i, product in enumerate(products[:5], 1):  # 最多下载5张图片
            image_url = product.get('image_url')
            product_id = product.get('product_id', product.get('asin', product.get('item_id', '')))

            if image_url and product_id:
                print(f"[{i}/{min(5, len(products))}] 下载图片...")
                crawler.download_image(image_url, product_id)
                time.sleep(random.uniform(1, 2))

    # 保存数据
    print("\n正在保存数据...")
    csv_file = crawler.save_to_csv(products, keyword)
    json_file = crawler.save_to_json(products, keyword)

    # 显示统计信息
    print("\n" + "=" * 60)
    print("爬取统计:")
    print(f"网站: {site_name.capitalize()}")
    print(f"关键词: {keyword}")
    print(f"爬取页数: {pages}")
    print(f"商品总数: {len(products)}")

    if products:
        # 显示示例
        print("\n前3个商品示例:")
        for i, product in enumerate(products[:3], 1):
            print(f"\n{i}. 标题: {product.get('title', 'N/A')[:80]}...")
            print(f"   价格: {product.get('price', product.get('price_range', 'N/A'))}")

            if 'rating' in product:
                print(f"   评分: {product.get('rating', 'N/A')}")

            if 'url' in product:
                print(f"   链接: {product.get('url')[:80]}...")

    print("=" * 60)


def add_new_site(config_manager):
    """添加新网站"""
    print("\n添加新网站配置")
    print("-" * 40)

    site_name = input("网站名称 (英文小写，如: jd): ").strip().lower()
    if not site_name:
        print("网站名称不能为空!")
        return

    base_url = input("https://www.amazon.sg/ref=nav_logo")
# 确保这个在文件的最末尾
if __name__ == "__main__":
    print("开始执行主程序...")
    main()
    input("程序执行完毕，按Enter退出...")