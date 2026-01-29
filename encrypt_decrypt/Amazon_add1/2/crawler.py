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
from urllib.parse import urljoin, urlparse
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
        self.site_display_name = site_config.get('display_name', self.site_name)

        # 使用真实请求头（可以在配置中覆盖）
        self.base_headers = {
            'authority': urlparse(self.base_url).netloc,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'device-memory': '8',
            'dpr': '1',
            'downlink': '10',
            'ect': '4g',
            'pragma': 'no-cache',
            'rtt': '50',
            'sec-ch-device-memory': '8',
            'sec-ch-dpr': '1',
            'sec-ch-ua': '"Chromium";v="120", "Not A(Brand";v="99", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # 更新配置中的headers
        config_headers = site_config.get('headers', {})
        self.base_headers.update(config_headers)

        # 使用Session保持会话
        self.session = requests.Session()
        self.session.headers.update(self.base_headers)

        # Cookies管理
        self.cookies = {}
        self.cookies_file = os.path.join(current_dir, f'cookies_{self.site_name}.json')

        # 数据保存目录
        self.data_dir = os.path.join(current_dir, 'ecommerce_data', self.site_name)

        # 请求计数器
        self.request_count = 0

        # 初始化
        self.init_cookies()
        self.create_directories()

        print(f"{self.site_display_name} 爬虫初始化完成")

    # ==================== 抽象方法（子类必须实现） ====================

    @abstractmethod
    def build_search_url(self, keyword, page=1):
        """构建搜索URL - 子类必须实现"""
        pass

    @abstractmethod
    def parse_search_results(self, html, max_results):
        """解析搜索结果页面 - 子类必须实现"""
        pass

    @abstractmethod
    def extract_product_info(self, product_element):
        """从商品元素提取基本信息 - 子类必须实现"""
        pass

    @abstractmethod
    def extract_product_details(self, html):
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
        print(f"正在初始化 {self.site_display_name} 的cookies...")

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

        # 获取初始cookies
        self.refresh_cookies()

    def refresh_cookies(self):
        """刷新cookies"""
        print(f"刷新 {self.site_display_name} 的cookies...")
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
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
        ]
        return random.choice(user_agents)

    def get_headers(self, referer=None):
        """获取请求头"""
        headers = self.base_headers.copy()
        headers['user-agent'] = self.get_random_user_agent()

        if referer:
            headers['referer'] = referer

        return headers

    def make_request(self, url, max_retries=3):
        """发送请求"""
        for attempt in range(max_retries):
            try:
                # 随机延迟
                delay = random.uniform(2, 5)
                if attempt > 0:
                    delay = random.uniform(5, 10)

                print(f"等待 {delay:.1f} 秒...")
                time.sleep(delay)

                # 更新请求头
                headers = self.get_headers(referer=self.base_url)

                response = self.session.get(
                    url,
                    headers=headers,
                    cookies=self.cookies,
                    timeout=30,
                    allow_redirects=True,
                    verify=True
                )

                self.request_count += 1
                print(f"状态码: {response.status_code}, 请求#{self.request_count}")

                if response.status_code == 200:
                    # 更新cookies
                    self.cookies.update(self.session.cookies.get_dict())

                    # 检查是否是验证页面
                    if self.is_captcha_page(response.text):
                        print("检测到验证页面，等待后重试...")
                        time.sleep(random.uniform(10, 15))
                        self.refresh_cookies()
                        continue

                    return response

                elif response.status_code in [403, 429]:
                    print(f"访问受限 ({response.status_code})，等待后重试...")
                    time.sleep(random.uniform(20, 30))
                    self.refresh_cookies()

                elif response.status_code == 503:
                    print(f"服务不可用 (503)，等待后重试...")
                    time.sleep(random.uniform(15, 25))

                else:
                    print(f"尝试 {attempt + 1}/{max_retries}: 状态码 {response.status_code}")
                    time.sleep(random.uniform(5, 8))

            except requests.exceptions.Timeout:
                print(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
                time.sleep(random.uniform(5, 10))
            except requests.exceptions.RequestException as e:
                print(f"请求异常: {e}")
                time.sleep(random.uniform(5, 10))

        print(f"请求失败: {url}")
        return None

    def is_captcha_page(self, html):
        """检查是否是验证码页面"""
        text = html.lower()
        captcha_indicators = [
            'captcha',
            'enter the characters you see',
            'robot check',
            'security check'
        ]

        for indicator in captcha_indicators:
            if indicator in text:
                return True

        # 如果页面内容很短，也可能是验证页面
        if len(html) < 5000:
            return True

        return False

    def search_products(self, keyword, max_results=20, pages=1):
        """搜索商品"""
        all_products = []

        for page in range(1, pages + 1):
            print(f"\n正在搜索第 {page} 页: {keyword}")

            # 构建搜索URL
            search_url = self.build_search_url(keyword, page)
            print(f"搜索URL: {search_url[:100]}...")

            # 发送请求
            response = self.make_request(search_url)

            if response:
                # 解析页面
                products = self.parse_search_results(response.text, max_results)

                if products:
                    all_products.extend(products)
                    print(f"第 {page} 页找到 {len(products)} 个商品")
                else:
                    print(f"第 {page} 页未找到商品")

                # 随机延迟
                time.sleep(random.uniform(2, 4))
            else:
                print(f"第 {page} 页请求失败")

            # 如果已经达到最大结果数，停止翻页
            if len(all_products) >= max_results:
                print(f"已达到最大结果数 {max_results}")
                break

        # 限制结果数量
        if len(all_products) > max_results:
            all_products = all_products[:max_results]

        return all_products

    def get_product_details(self, product_url):
        """获取商品详情"""
        if not product_url:
            return {}

        try:
            response = self.make_request(product_url)
            if response:
                return self.extract_product_details(response.text)
            else:
                return {}
        except Exception as e:
            print(f"获取商品详情时出错: {e}")
            return {}

    def save_to_csv(self, products, keyword):
        """保存数据到CSV文件"""
        if not products:
            print("没有数据可保存")
            return None

        # 确定字段（合并所有商品的字段）
        fieldnames = set()
        for product in products:
            fieldnames.update(product.keys())

        # 排序字段
        fieldnames = sorted(fieldnames)

        # 创建文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()[:50]
        filename = f"{self.site_name}_{safe_keyword}_{timestamp}.csv"
        filepath = os.path.join(self.data_dir, filename)

        # 保存到CSV
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for product in products:
                row = {}
                for field in fieldnames:
                    value = product.get(field, '')
                    # 处理特殊类型
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
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()[:50]
        filename = f"{self.site_name}_{safe_keyword}_{timestamp}.json"
        filepath = os.path.join(self.data_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(products, jsonfile, ensure_ascii=False, indent=2, default=str)

        print(f"数据已保存到: {filepath}")
        return filepath


# ==================== 具体网站爬虫实现 ====================

class AmazonCrawler(BaseEcommerceCrawler):
    """亚马逊爬虫"""

    def build_search_url(self, keyword, page=1):
        """构建亚马逊搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)

        if page == 1:
            return f"{self.base_url}/s?k={keyword_encoded}"
        else:
            return f"{self.base_url}/s?k={keyword_encoded}&page={page}"

    def parse_search_results(self, html, max_results):
        """解析亚马逊搜索结果"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # 查找商品元素
        items = soup.find_all('div', {'data-component-type': 's-search-result'})

        # 备用选择器
        if not items or len(items) < 5:
            items = soup.find_all('div', class_='s-result-item')

        if not items or len(items) < 5:
            items = soup.select('[data-asin]')

        count = 0
        for item in items:
            if count >= max_results:
                break

            try:
                product = self.extract_product_info(item)
                if product:
                    products.append(product)
                    count += 1
            except Exception as e:
                print(f"解析商品出错: {e}")
                continue

        return products

    def extract_product_info(self, element):
        """提取亚马逊商品信息"""
        product = {}

        # 提取ASIN
        asin = element.get('data-asin', '')
        if not asin:
            # 尝试从链接中提取
            link_elem = element.select_one('a[href*="/dp/"]')
            if link_elem:
                match = re.search(r'/dp/([A-Z0-9]{10})', link_elem.get('href', ''))
                if match:
                    asin = match.group(1)

        if not asin:
            return None

        product['asin'] = asin
        product['product_id'] = asin
        product['source'] = 'amazon'

        # 提取标题
        title_selectors = [
            'h2 a span',
            '.a-text-normal',
            '.a-size-medium',
            'h2'
        ]

        for selector in title_selectors:
            elem = element.select_one(selector)
            if elem and elem.text.strip():
                product['title'] = elem.text.strip()[:200]
                break

        if 'title' not in product:
            return None

        # 提取价格
        product['price'] = self.extract_price(element)

        # 提取评分
        rating_elem = element.select_one('.a-icon-alt')
        if rating_elem:
            rating_text = rating_elem.text.strip()
            match = re.search(r'(\d+\.?\d*)', rating_text)
            if match:
                product['rating'] = match.group(1)

        # 提取评价数量
        review_selectors = [
            '.a-size-base.s-underline-text',
            '.a-size-base',
            '[aria-label*="stars"]'
        ]

        for selector in review_selectors:
            elem = element.select_one(selector)
            if elem:
                reviews_text = elem.text.strip()
                match = re.search(r'(\d+,?\d*)', reviews_text)
                if match:
                    product['reviews'] = match.group(1)
                    break

        # 提取图片
        img_elem = element.select_one('img.s-image')
        if img_elem:
            for attr in ['src', 'data-src', 'data-old-hires']:
                if img_elem.get(attr):
                    product['image_url'] = img_elem[attr]
                    break

        # 提取链接
        link_selectors = [
            'h2 a',
            'a.a-link-normal',
            '.a-link-normal.s-no-outline'
        ]

        for selector in link_selectors:
            elem = element.select_one(selector)
            if elem and elem.get('href'):
                href = elem['href']
                if href.startswith('/'):
                    product['url'] = f"{self.base_url}{href}"
                elif 'amazon.' in href:
                    product['url'] = href
                else:
                    product['url'] = f"{self.base_url}{href}"
                break

        # 提取徽章信息
        if 'Best Seller' in str(element) or 'bestseller' in str(element).lower():
            product['badge'] = 'Best Seller'

        if "Amazon's Choice" in str(element) or 'amazon choice' in str(element).lower():
            product['badge'] = "Amazon's Choice"

        # 添加时间戳
        product['crawled_at'] = datetime.now().isoformat()

        return product

    def extract_price(self, element):
        """提取亚马逊价格"""
        # 方法1：查找隐藏的价格文本
        hidden_price = element.select_one('.a-offscreen')
        if hidden_price:
            price_text = hidden_price.text.strip()
            if price_text and re.search(r'[\$\€\£\¥]', price_text):
                return price_text

        # 方法2：查找价格容器
        price_container = element.select_one('.a-price')
        if price_container:
            # 获取符号
            symbol_elem = price_container.select_one('.a-price-symbol')
            symbol = symbol_elem.text.strip() if symbol_elem else '$'

            # 获取整数部分
            whole_elem = price_container.select_one('.a-price-whole')
            whole = whole_elem.text.strip() if whole_elem else ''

            # 获取小数部分
            fraction_elem = price_container.select_one('.a-price-fraction')
            fraction = fraction_elem.text.strip() if fraction_elem else ''

            # 组合价格
            if whole:
                price = whole
                if fraction:
                    price += f".{fraction}"
                return f"{symbol}{price}"

        # 方法3：在元素文本中搜索价格
        element_text = str(element)
        usd_pattern = r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?'
        match = re.search(usd_pattern, element_text)
        if match:
            return match.group(0).replace(' ', '')

        return None

    def extract_product_details(self, html):
        """提取亚马逊商品详情"""
        details = {}
        soup = BeautifulSoup(html, 'html.parser')

        # 提取品牌
        brand_elem = soup.select_one('#bylineInfo')
        if brand_elem:
            details['brand'] = brand_elem.text.strip().replace('Brand:', '').strip()

        # 提取描述
        desc_elem = soup.select_one('#productDescription')
        if desc_elem:
            details['description'] = desc_elem.text.strip()[:500]

        # 提取销售排名
        rank_elem = soup.select_one('#productDetails_detailBullets_sections1')
        if rank_elem:
            rank_text = rank_elem.text
            match = re.search(r'#(\d+,?\d*,?\d*)', rank_text)
            if match:
                details['sales_rank'] = match.group(1)

        return details


class EbayCrawler(BaseEcommerceCrawler):
    """eBay爬虫"""

    def build_search_url(self, keyword, page=1):
        """构建eBay搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)
        return f"{self.base_url}/sch/i.html?_nkw={keyword_encoded}&_pgn={page}"

    def parse_search_results(self, html, max_results):
        """解析eBay搜索结果"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # 查找商品元素
        items = soup.select('.s-item')

        count = 0
        for item in items:
            if count >= max_results:
                break

            try:
                product = self.extract_product_info(item)
                if product:
                    products.append(product)
                    count += 1
            except Exception as e:
                print(f"解析商品出错: {e}")
                continue

        return products

    def extract_product_info(self, element):
        """提取eBay商品信息"""
        product = {}

        # 提取商品ID
        item_id = element.get('data-view', '')
        if not item_id:
            # 尝试从链接中提取
            link_elem = element.select_one('.s-item__link')
            if link_elem:
                match = re.search(r'/itm/(\d+)', link_elem.get('href', ''))
                if match:
                    item_id = match.group(1)

        if not item_id:
            return None

        product['item_id'] = item_id
        product['product_id'] = item_id
        product['source'] = 'ebay'

        # 提取标题
        title_elem = element.select_one('.s-item__title')
        if title_elem:
            product['title'] = title_elem.text.strip()[:200]

        if 'title' not in product:
            return None

        # 提取价格
        price_elem = element.select_one('.s-item__price')
        if price_elem:
            product['price'] = price_elem.text.strip()

        # 提取运费
        shipping_elem = element.select_one('.s-item__shipping')
        if shipping_elem:
            product['shipping'] = shipping_elem.text.strip()

        # 提取卖家
        seller_elem = element.select_one('.s-item__seller-info')
        if seller_elem:
            product['seller'] = seller_elem.text.strip()

        # 提取评分
        rating_elem = element.select_one('.s-item__etrs-text')
        if rating_elem:
            product['seller_rating'] = rating_elem.text.strip()

        # 提取图片
        img_elem = element.select_one('.s-item__image-img')
        if img_elem:
            product['image_url'] = img_elem.get('src', '')

        # 提取链接
        link_elem = element.select_one('.s-item__link')
        if link_elem and link_elem.get('href'):
            product['url'] = link_elem['href']

        # 提取商品状态
        condition_elem = element.select_one('.SECONDARY_INFO')
        if condition_elem:
            product['condition'] = condition_elem.text.strip()

        # 添加时间戳
        product['crawled_at'] = datetime.now().isoformat()

        return product

    def extract_product_details(self, html):
        """提取eBay商品详情"""
        details = {}
        soup = BeautifulSoup(html, 'html.parser')

        # 提取卖家信息
        seller_elem = soup.select_one('.mbg-nw')
        if seller_elem:
            details['seller_name'] = seller_elem.text.strip()

        # 提取描述
        desc_elem = soup.select_one('#desc_div')
        if desc_elem:
            details['description'] = desc_elem.text.strip()[:500]

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


class AlibabaCrawler(BaseEcommerceCrawler):
    """阿里巴巴爬虫"""

    def build_search_url(self, keyword, page=1):
        """构建阿里巴巴搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)
        return f"{self.base_url}/trade/search?SearchText={keyword_encoded}&page={page}"

    def parse_search_results(self, html, max_results):
        """解析阿里巴巴搜索结果"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # 查找商品元素（根据阿里巴巴的页面结构）
        items = soup.select('.organic-list .item-content, .J-offer-wrapper, .list-item')

        count = 0
        for item in items:
            if count >= max_results:
                break

            try:
                product = self.extract_product_info(item)
                if product:
                    products.append(product)
                    count += 1
            except Exception as e:
                print(f"解析商品出错: {e}")
                continue

        return products

    def extract_product_info(self, element):
        """提取阿里巴巴商品信息"""
        product = {}

        # 提取商品ID（阿里巴巴通常没有固定的ID格式）
        product_id = str(hash(str(element)))
        product['product_id'] = product_id
        product['source'] = 'alibaba'

        # 提取标题
        title_elem = element.select_one('.title, .elements-title-normal')
        if title_elem:
            product['title'] = title_elem.text.strip()[:200]

        if 'title' not in product:
            return None

        # 提取价格范围
        price_elem = element.select_one('.price, .elements-offer-price-normal')
        if price_elem:
            product['price'] = price_elem.text.strip()

        # 提取最小起订量
        moq_elem = element.select_one('.moq, .min-order')
        if moq_elem:
            product['min_order'] = moq_elem.text.strip()

        # 提取供应商
        supplier_elem = element.select_one('.company-name, .supplier')
        if supplier_elem:
            product['supplier'] = supplier_elem.text.strip()

        # 提取图片
        img_elem = element.select_one('img')
        if img_elem:
            product['image_url'] = img_elem.get('src', '')

        # 提取链接
        link_elem = element.select_one('a')
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            if href.startswith('/'):
                product['url'] = f"{self.base_url}{href}"
            else:
                product['url'] = href

        # 添加时间戳
        product['crawled_at'] = datetime.now().isoformat()

        return product

    def extract_product_details(self, html):
        """提取阿里巴巴商品详情"""
        details = {}
        soup = BeautifulSoup(html, 'html.parser')

        # 提取公司信息
        company_elem = soup.select_one('.company-name')
        if company_elem:
            details['company'] = company_elem.text.strip()

        # 提取交易方式
        trade_elem = soup.select_one('.trade-assurance')
        if trade_elem:
            details['trade_assurance'] = trade_elem.text.strip()

        return details


class JDCrawler(BaseEcommerceCrawler):
    """京东爬虫"""

    def build_search_url(self, keyword, page=1):
        """构建京东搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)
        return f"{self.base_url}/search?keyword={keyword_encoded}&page={page}"

    def parse_search_results(self, html, max_results):
        """解析京东搜索结果"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # 查找商品元素（京东的商品容器）
        items = soup.select('.gl-item, .goods-item')

        count = 0
        for item in items:
            if count >= max_results:
                break

            try:
                product = self.extract_product_info(item)
                if product:
                    products.append(product)
                    count += 1
            except Exception as e:
                print(f"解析商品出错: {e}")
                continue

        return products

    def extract_product_info(self, element):
        """提取京东商品信息"""
        product = {}

        # 提取SKU
        sku = element.get('data-sku', '')
        if not sku:
            # 尝试从链接中提取
            link_elem = element.select_one('a[href*="item.jd.com"]')
            if link_elem:
                match = re.search(r'/(\d+)\.html', link_elem.get('href', ''))
                if match:
                    sku = match.group(1)

        if not sku:
            return None

        product['sku'] = sku
        product['product_id'] = sku
        product['source'] = 'jd'

        # 提取标题
        title_elem = element.select_one('.p-name em, .sku-name')
        if title_elem:
            product['title'] = title_elem.text.strip()[:200]

        if 'title' not in product:
            return None

        # 提取价格
        price_elem = element.select_one('.p-price, .J_price')
        if price_elem:
            product['price'] = price_elem.text.strip()

        # 提取评价数量
        review_elem = element.select_one('.p-commit')
        if review_elem:
            product['reviews'] = review_elem.text.strip()

        # 提取图片
        img_elem = element.select_one('.p-img img')
        if img_elem:
            product['image_url'] = img_elem.get('src', '')

        # 提取链接
        link_elem = element.select_one('a[href*="item.jd.com"]')
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            if href.startswith('//'):
                product['url'] = f"https:{href}"
            elif href.startswith('/'):
                product['url'] = f"{self.base_url}{href}"
            else:
                product['url'] = href

        # 提取店铺
        shop_elem = element.select_one('.p-shop')
        if shop_elem:
            product['shop'] = shop_elem.text.strip()

        # 添加时间戳
        product['crawled_at'] = datetime.now().isoformat()

        return product

    def extract_product_details(self, html):
        """提取京东商品详情"""
        details = {}
        soup = BeautifulSoup(html, 'html.parser')

        # 提取品牌
        brand_elem = soup.select_one('#parameter-brand')
        if brand_elem:
            details['brand'] = brand_elem.text.strip()

        # 提取规格参数
        params = {}
        param_rows = soup.select('.parameter2 li')
        for row in param_rows:
            parts = row.text.split('：')
            if len(parts) == 2:
                params[parts[0].strip()] = parts[1].strip()

        if params:
            details['parameters'] = params

        return details


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
                'display_name': '亚马逊',
                'base_url': 'https://www.amazon.com',
                'crawler_class': 'AmazonCrawler',
                'headers': {
                    'authority': 'www.amazon.com',
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'accept-language': 'en-US,en;q=0.5',
                }
            },
            'ebay': {
                'name': 'ebay',
                'display_name': 'eBay',
                'base_url': 'https://www.ebay.com',
                'crawler_class': 'EbayCrawler',
                'headers': {
                    'authority': 'www.ebay.com',
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'accept-language': 'en-US,en;q=0.5',
                }
            },
            'alibaba': {
                'name': 'alibaba',
                'display_name': '阿里巴巴',
                'base_url': 'https://www.alibaba.com',
                'crawler_class': 'AlibabaCrawler',
                'headers': {
                    'authority': 'www.alibaba.com',
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'accept-language': 'en-US,en;q=0.5',
                }
            },
            'jd': {
                'name': 'jd',
                'display_name': '京东',
                'base_url': 'https://www.jd.com',
                'crawler_class': 'JDCrawler',
                'headers': {
                    'authority': 'www.jd.com',
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'accept-language': 'zh-CN,zh;q=0.9',
                }
            }
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
                    # 合并默认配置和加载的配置
                    if loaded_config:
                        for site in default_config:
                            if site in loaded_config:
                                default_config[site].update(loaded_config[site])
                    return default_config
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
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            print(f"配置文件已保存: {self.config_file}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def get_site_config(self, site_name):
        """获取网站配置"""
        return self.sites_config.get(site_name)

    def list_sites(self):
        """列出所有支持的网站"""
        return list(self.sites_config.keys())

    def get_site_display_name(self, site_name):
        """获取网站显示名称"""
        config = self.get_site_config(site_name)
        return config.get('display_name', site_name) if config else site_name


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
            'AlibabaCrawler': AlibabaCrawler,
            'JDCrawler': JDCrawler
        }

        crawler_class = crawler_classes.get(crawler_class_name)
        if not crawler_class:
            raise ValueError(f"找不到爬虫类: {crawler_class_name}")

        return crawler_class(site_config)


# ==================== 主程序 ====================

def main():
    """主函数"""
    print("=" * 60)
    print("通用电商爬虫框架 v1.0")
    print("支持：亚马逊、eBay、阿里巴巴、京东等")
    print("=" * 60)

    # 初始化配置管理器
    config_manager = ConfigManager()

    # 显示可用网站
    print("\n可用网站列表:")
    sites = config_manager.list_sites()

    for i, site in enumerate(sites, 1):
        display_name = config_manager.get_site_display_name(site)
        config = config_manager.get_site_config(site)
        base_url = config.get('base_url', 'N/A') if config else 'N/A'
        print(f"{i}. {display_name} ({site}) - {base_url}")

    # 选择网站
    try:
        choice = input(f"\n请选择网站 (1-{len(sites)}): ").strip()
        site_index = int(choice) - 1

        if 0 <= site_index < len(sites):
            site_name = sites[site_index]
        else:
            print("选择无效，使用默认网站: 亚马逊")
            site_name = 'amazon'
    except:
        print("输入无效，使用默认网站: 亚马逊")
        site_name = 'amazon'

    # 创建爬虫
    try:
        crawler = CrawlerFactory.create_crawler(site_name, config_manager)
        print(f"\n已创建 {config_manager.get_site_display_name(site_name)} 爬虫")
    except Exception as e:
        print(f"创建爬虫失败: {e}")
        return

    # 用户输入搜索参数
    print("\n" + "=" * 60)
    keyword = input("请输入搜索关键词: ").strip()
    if not keyword:
        print("关键词不能为空!")
        return

    try:
        max_results = int(input(f"请输入最大商品数量 (1-100，默认20): ").strip() or "20")
        max_results = max(1, min(max_results, 100))
    except:
        max_results = 20

    try:
        pages = int(input(f"请输入搜索页数 (1-10，默认1): ").strip() or "1")
        pages = max(1, min(pages, 10))
    except:
        pages = 1

    get_details = input("是否获取商品详细信息? (y/n，默认n): ").strip().lower() == 'y'
    download_images = input("是否下载商品图片? (y/n，默认n): ").strip().lower() == 'y'

    print(f"\n开始爬取 {config_manager.get_site_display_name(site_name)} 商品")
    print(f"关键词: {keyword}")
    print(f"最大商品数: {max_results}")
    print(f"搜索页数: {pages}")
    print(f"获取详情: {'是' if get_details else '否'}")
    print(f"下载图片: {'是' if download_images else '否'}")
    print("=" * 60)

    # 搜索商品
    products = crawler.search_products(keyword, max_results=max_results, pages=pages)

    if not products:
        print("\n没有找到商品!")
        print("\n可能的原因:")
        print("1. 网站反爬虫机制触发")
        print("2. 网络连接问题")
        print("3. 关键词无结果")
        print("4. 需要更新页面解析规则")
        return

    print(f"\n搜索完成，共找到 {len(products)} 个商品")

    # 获取商品详情
    if get_details and products:
        print("\n开始获取商品详情...")
        for i, product in enumerate(products, 1):
            if 'url' in product:
                print(f"[{i}/{len(products)}] 获取详情: {product.get('title', 'N/A')[:50]}...")
                details = crawler.get_product_details(product['url'])
                if details:
                    product.update(details)
                time.sleep(random.uniform(1, 3))

    # 下载图片
    if download_images and products:
        print("\n开始下载商品图片...")
        for i, product in enumerate(products[:10], 1):  # 最多下载10张
            image_url = product.get('image_url')
            product_id = product.get('product_id', product.get('asin', product.get('item_id', '')))

            if image_url and product_id:
                print(f"[{i}/{min(10, len(products))}] 下载图片...")
                try:
                    headers = crawler.get_headers()
                    response = requests.get(image_url, headers=headers, timeout=10)

                    if response.status_code == 200:
                        # 生成文件名
                        ext = os.path.splitext(image_url)[1]
                        if not ext or len(ext) > 5:
                            ext = '.jpg'

                        filename = f"{product_id}_{int(time.time())}{ext}"
                        image_path = os.path.join(crawler.data_dir, 'images', filename)

                        with open(image_path, 'wb') as f:
                            f.write(response.content)

                        product['local_image_path'] = image_path
                        print(f"  ✓ 图片下载成功")
                    else:
                        print(f"  ✗ 图片下载失败: HTTP {response.status_code}")
                except Exception as e:
                    print(f"  ✗ 下载图片时出错: {e}")

                time.sleep(random.uniform(1, 2))

    # 保存数据
    print("\n正在保存数据...")
    csv_file = crawler.save_to_csv(products, keyword)
    json_file = crawler.save_to_json(products, keyword)

    # 显示统计信息
    print("\n" + "=" * 60)
    print("爬取统计:")
    print(f"网站: {config_manager.get_site_display_name(site_name)}")
    print(f"关键词: {keyword}")
    print(f"搜索页数: {pages}")
    print(f"商品总数: {len(products)}")
    print(f"请求次数: {crawler.request_count}")

    if products:
        # 详细统计
        price_count = sum(1 for p in products if p.get('price'))
        rating_count = sum(1 for p in products if p.get('rating'))
        image_count = sum(1 for p in products if p.get('image_url'))

        print(f"\n详细统计:")
        print(f"有价格的商品: {price_count}")
        print(f"有评分的商品: {rating_count}")
        print(f"有图片的商品: {image_count}")

        # 价格范围
        prices = []
        for product in products:
            price = product.get('price', '')
            if price:
                # 提取数字部分
                match = re.search(r'[\d,]+\.?\d*', price)
                if match:
                    price_num = float(match.group().replace(',', ''))
                    prices.append(price_num)

        if prices:
            print(f"价格范围: ${min(prices):.2f} - ${max(prices):.2f}")
            print(f"平均价格: ${sum(prices) / len(prices):.2f}")

        # 显示示例商品
        print(f"\n前3个商品示例:")
        for i, product in enumerate(products[:3], 1):
            print(f"\n{i}. {product.get('title', 'N/A')[:80]}...")
            print(f"   价格: {product.get('price', 'N/A')}")

            if product.get('rating'):
                print(f"   评分: {product.get('rating')}")

            if product.get('reviews'):
                print(f"   评价: {product.get('reviews')}")

            if product.get('url'):
                print(f"   链接: {product.get('url')[:80]}...")

    print("\n" + "=" * 60)


def add_new_site():
    """添加新网站"""
    print("\n添加新网站")
    print("=" * 60)

    config_manager = ConfigManager()

    site_name = input("网站标识 (英文小写，如: taobao): ").strip().lower()
    if not site_name:
        print("网站标识不能为空!")
        return

    if site_name in config_manager.sites_config:
        print(f"网站 {site_name} 已存在!")
        return

    display_name = input("网站显示名称 (如: 淘宝): ").strip()
    base_url = input("网站基础URL (如: https://www.taobao.com): ").strip()

    if not base_url.startswith('http'):
        print("URL必须以http或https开头!")
        return

    print("\n选择爬虫类型:")
    print("1. 亚马逊类型 (适合商品卡片式布局)")
    print("2. eBay类型 (适合拍卖/一口价混合)")
    print("3. 阿里巴巴类型 (适合B2B批发网站)")
    print("4. 京东类型 (适合国内电商)")

    crawler_type = input("请选择 (1-4，默认1): ").strip() or "1"

    crawler_map = {
        '1': 'AmazonCrawler',
        '2': 'EbayCrawler',
        '3': 'AlibabaCrawler',
        '4': 'JDCrawler'
    }

    crawler_class = crawler_map.get(crawler_type, 'AmazonCrawler')

    # 创建配置
    new_config = {
        'name': site_name,
        'display_name': display_name or site_name,
        'base_url': base_url,
        'crawler_class': crawler_class,
        'headers': {
            'authority': urlparse(base_url).netloc,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.5',
        }
    }

    # 添加到配置
    config_manager.sites_config[site_name] = new_config
    config_manager.save_config(config_manager.sites_config)

    print(f"\n✓ 已成功添加网站: {display_name}")
    print(f"下次运行程序时即可选择该网站")


# ==================== 程序入口 ====================

if __name__ == "__main__":
    try:
        # 显示主菜单
        print("电商爬虫框架")
        print("=" * 60)
        print("1. 开始爬取商品")
        print("2. 添加新网站")
        print("3. 查看支持的网站")

        choice = input("\n请选择操作 (1-3，默认1): ").strip() or "1"

        if choice == "1":
            main()
        elif choice == "2":
            add_new_site()
        elif choice == "3":
            config_manager = ConfigManager()
            sites = config_manager.list_sites()

            print("\n支持的网站列表:")
            print("=" * 60)
            for site in sites:
                config = config_manager.get_site_config(site)
                display_name = config.get('display_name', site) if config else site
                base_url = config.get('base_url', 'N/A') if config else 'N/A'
                print(f"• {display_name} ({site})")
                print(f"  网址: {base_url}")
                print(f"  爬虫类: {config.get('crawler_class', 'N/A') if config else 'N/A'}")
                print()

            input("\n按Enter键返回主菜单...")
            # 重新运行主程序
            exec(open(__file__).read())
        else:
            print("无效选择，运行默认爬虫")
            main()

    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n程序出错: {e}")
        import traceback

        traceback.print_exc()

    input("\n按Enter键退出...")