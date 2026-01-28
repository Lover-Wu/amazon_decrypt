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

# 获取当前Python文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"当前文件目录: {current_dir}")


class AmazonCrawler:
    def __init__(self, country_code="sg"):
        """
        初始化亚马逊爬虫
        country_code: 国家代码，如'sg'（新加坡）、'com'（美国）、'co.uk'（英国）等
        """
        self.country_code = country_code
        self.base_url = f"https://www.amazon.{country_code}"

        # 使用真实请求头
        self.base_headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache',
            'device-memory': '8',
            'dpr': '1',
            'downlink': '10',
            'ect': '4g',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'rtt': '100',
            'sec-ch-device-memory': '8',
            'sec-ch-dpr': '1',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            'sec-ch-ua-full-version-list': '"Not(A:Brand";v="8.0.0.0", "Chromium";v="144.0.7559.97", "Microsoft Edge";v="144.0.3719.92"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"19.0.0"',
            'sec-ch-viewport-width': '988',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
            'viewport-width': '988',
        }

        # 代理IP（如果需要）
        self.proxies = None

        # 创建保存目录
        self.create_directories()

        # 初始化cookie
        self.cookies = {
            'aws-waf-token': 'e23de046-9eb0-4fa2-89de-02ade4294943:BgoAtyYLeKsEAAAA:nclDK0eeYilSMr32ha/O8blFETQsvGXnfhOggmaVeMb3tQYWsVlpZWZrNwptyb0Fqp7dppmuW85xL5ebRmkUpiAHoCPMW23I6NNX+V6SiglPgbpzGwV4Ml1qi2da4MT3vfh5QeAjt5K58QmbsHm0DSV67qOLJhQaGY/M+6c5K2Jj/pyGcu1WgGGS8vOv7JOr',
            'session-id': '356-3871843-8277767',
            'i18n-prefs': 'SGD',
            'lc-acbsg': 'en_SG',
            'ubid-acbsg': '358-4136526-4938309',
            'id_pkel': 'n1',
            'id_pk': 'eyJuIjoiMSIsImFmIjoiMSJ9',
            'sso-state-acbsg': 'Xdsso|ZQE5bHD-GdRE215S3iMjq9Wa55l-LsS5mb_M2bQSZsuoD8cI30_iiKaYA-ds8GJAIAfvMa3166pPJk2GD5r8dhzY6Thjb-Y-uWeE71yq4qAlAnjG',
            'at-acbsg': 'Atza|gQCpRreZAQEBAcwnRfhfKH3wsu7r7yGS9J5BgQbUqxQuEg_vsI3qKTrqqBLqfRA-ksnefkS64BaBF6vVdsqYMC1KrvCGzLcjWOinWKXyn63nhXCsGVDbB3GJERyLqhZbseggBWKrL6uQ5c3MBcWkYtQuElsVXc8gqlYG4OQeGCjA-BlRTIpF6oa01sr_fUuh1ccR-sWhh20tFZCz-q8gQh0qBNYDxVp1kVCGaLnRLcQVnCnegtu5YZ5hazQIwxGtsVoUKbASQS1qutf3CVTPr4tAQsKGkDmfHjySenkOydPeZIiQajQtX5So5fj9SW8DBydZjy1iNuK7H1h4jHEeaEHI0fb2CMQo4PTHFpfHzznF9A',
            'sess-at-acbsg': 'GyTqNvRRda5hlHGaNLirDClVTqG51w6FiBKWY+QfYeA=',
            'sst-acbsg': 'Sst1|PQLCRluQqjHZ47z0GV6TrWEnCaCyOLyawiw6f6mK0WPzo8lvjJXWfelazMtnZ8cxMplX1Uug80L6m6nrEANgxFeprXC-ZTtFzwfRayQVqTV5SaR8QGcPayhHzQ5zZ4Hx3cZk4D2wQE6MWKmfqRa_ykNWx5UO2pKcZl73EDPfTFi5sorxcDAqACdZ1m_CnApHVePxRGRPVqDQKSQmiGvtkDFFw-Zsasdci7-lhoDPU8sWjQ2xIwaQLjE4qh_KqCdHP08zr1qMb-VE8bfDBWXs2XiLyh_MwyTE91ol0iNU9hPWsRI',
            'session-token': 'JsetI2T0XZUDbPXVqESV9wYsZvqZLSN7P2ckBoFGgPKtK9Tr7lqz/2C292uPmdaokMyCOqzCrGbaMZl/N5dNtCrwTVImFk7jWk/9xv/5ZZiX1ZCLlqjNg9go0Dk3A8OuN6WfB3M8xH45vYdTLrDnuzLnYmQVEzo//Uny61aVql3KOTUNxUxRoNyi9dhsQNsYzNqvJVa7gDr+1P2vpGBDqrLgt2SJcQNFIQRLirlt/x4+qaYPxATzJiZGu5zyYZh2sB3MvPDKhioAJHPmTZmOaXlAjQyAgG05j+dEQnDbsgMZn5Z59qD1N03JHj0ds+T5dRk5zArmqqyyFoYZcchuNLc78jShtlK8iKYOXBIrlaBSwrz/AJBoXQ==',
            'session-id-time': '2082787201l',
            'x-acbsg': 'nSrgiVXDSdYdLbT7jHocPJMXKaky@vw7Kv6HFDibg2KUXta6SdJ6iXQPgqIZ8WOk',
            'csm-hit': 'tb:T09P488AZ5JSSC263YAT+s-W6R9818BMPN1K836DWPR|1769564680747&t:1769564680747&adb:adblk_no',
            'rxc': 'ADFy9CdY1VHb3Fmr53E'
        }

    def create_directories(self):
        """创建保存数据的目录"""
        directories = ['amazon_data', 'amazon_data/products', 'amazon_data/images', 'amazon_data/details']
        for directory in directories:
            dir_path = os.path.join(current_dir, directory)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"创建目录: {dir_path}")

    def get_headers(self, referer=None):
        """获取请求头"""
        headers = self.base_headers.copy()
        if referer:
            headers['referer'] = referer
        return headers

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
                        # 如果需要获取详情
                        if get_details:
                            products = self.enrich_products_with_details(products)

                        all_products.extend(products)
                        print(f"第 {page} 页找到 {len(products)} 个商品")
                    else:
                        print(f"第 {page} 页未找到商品，可能页面结构已变化")

                    # 随机延迟，避免被封
                    time.sleep(random.uniform(3, 7))
                else:
                    print(f"第 {page} 页请求失败")
            except Exception as e:
                print(f"搜索第 {page} 页时出错: {e}")

            # 如果一页少于5个商品，可能没有更多页面了
            if len(products) < 5 and page > 1:
                print("商品数量较少，停止翻页")
                break

        return all_products

    def build_search_url(self, keyword, page=1):
        """构建搜索URL"""
        keyword_encoded = urllib.parse.quote(keyword)

        # 亚马逊搜索URL格式
        if page == 1:
            return f"{self.base_url}/s?k={keyword_encoded}&ref=nb_sb_noss_2"
        else:
            return f"{self.base_url}/s?k={keyword_encoded}&page={page}&qid={int(time.time())}&ref=sr_pg_{page}"

    def make_request(self, url, max_retries=3, is_detail_page=False):
        """发送请求"""
        for attempt in range(max_retries):
            try:
                headers = self.get_headers(referer=self.base_url)

                response = requests.get(
                    url,
                    headers=headers,
                    cookies=self.cookies,
                    proxies=self.proxies,
                    timeout=25,
                    allow_redirects=True,
                    verify=True
                )

                print(f"状态码: {response.status_code}, URL: {url[:80]}...")

                if response.status_code == 200:
                    # 检查是否是验证页面
                    if "api-services-support@amazon.com" in response.text or "enter the characters you see below" in response.text:
                        print("遇到验证码页面!")
                        return None

                    # 检查页面是否被重定向到首页（通常是封禁）
                    if "amazon." in url and "amazon." not in response.url:
                        print("可能被重定向到验证页面")
                        return None

                    return response
                elif response.status_code == 503:
                    print(f"尝试 {attempt + 1}/{max_retries}: 亚马逊服务不可用 (503)，等待后重试...")
                    time.sleep(random.uniform(10, 15))
                elif response.status_code == 404:
                    print("页面不存在 (404)")
                    return None
                elif response.status_code == 403:
                    print("访问被拒绝 (403)，可能需要更新cookies")
                    return None
                elif response.status_code == 429:
                    print(f"请求过于频繁 (429)，等待更长时间...")
                    time.sleep(random.uniform(30, 60))
                else:
                    print(f"尝试 {attempt + 1}/{max_retries}: 状态码 {response.status_code}")
                    time.sleep(random.uniform(5, 8))

            except requests.exceptions.RequestException as e:
                print(f"尝试 {attempt + 1}/{max_retries}: 请求异常 - {e}")
                time.sleep(random.uniform(5, 8))

        print(f"请求失败: {url}")
        return None

    def parse_search_results(self, html):
        """解析搜索结果页面"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # 方法1: 查找所有包含data-asin属性的元素
        elements_with_asin = soup.find_all(attrs={"data-asin": True})

        for element in elements_with_asin:
            try:
                # 确保是商品元素
                if self.is_product_element(element):
                    product_data = self.extract_product_basic_info(element)
                    if product_data and product_data.get('asin'):
                        products.append(product_data)
            except Exception as e:
                continue

        # 方法2: 如果方法1没找到，尝试其他选择器
        if len(products) < 5:
            print("尝试备用解析方法...")
            products = self.alternative_parse_method(soup)

        return products

    def is_product_element(self, element):
        """判断是否是商品元素"""
        text = str(element)
        product_indicators = [
            'data-asin=',
            'data-index=',
            'data-component-type="s-search-result"',
            's-result-item',
            'sponsored',
            'amazon'
        ]

        indicators_found = sum(1 for indicator in product_indicators if indicator in text)
        return indicators_found >= 2

    def extract_product_basic_info(self, product_element):
        """从商品元素提取基本信息"""
        data = {}

        # 提取ASIN
        asin = product_element.get('data-asin', '')
        if not asin:
            return None

        data['asin'] = asin

        # 提取基本信息
        data['title'] = self.extract_title(product_element)
        data['url'] = self.extract_url(product_element)
        data['price'] = self.extract_price(product_element)
        data['original_price'] = self.extract_original_price(product_element)
        data['discount'] = self.extract_discount(product_element)
        data['rating'] = self.extract_rating(product_element)
        data['reviews'] = self.extract_reviews(product_element)
        data['image_url'] = self.extract_image_url(product_element)

        # 提取销售信息
        data['best_seller'] = self.extract_best_seller_info(product_element)
        data['amazon_choice'] = self.extract_amazon_choice_info(product_element)
        data['sponsored'] = self.extract_sponsored_info(product_element)

        # 提取发货信息
        data['shipping_info'] = self.extract_shipping_info(product_element)
        data['prime_eligible'] = self.extract_prime_info(product_element)

        # 添加爬取时间
        data['crawled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 移除空值
        data = {k: v for k, v in data.items() if v is not None}

        return data

    def extract_title(self, element):
        """提取商品标题"""
        selectors = [
            'h2 a span',
            '.a-text-normal',
            '.a-size-medium',
            'span.a-text-normal',
            'h2'
        ]

        for selector in selectors:
            elem = element.select_one(selector)
            if elem and elem.text.strip():
                return elem.text.strip()[:200]

        return None

    def extract_url(self, element):
        """提取商品链接"""
        selectors = [
            'h2 a',
            '.a-link-normal',
            'a.a-link-normal'
        ]

        for selector in selectors:
            elem = element.select_one(selector)
            if elem and elem.get('href'):
                href = elem['href']
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                elif 'amazon.' in href:
                    return href

        return None

    def extract_price(self, element):
        """提取商品当前价格"""
        price_selectors = [
            '.a-price .a-offscreen',
            '.a-price-whole',
            '.a-color-price',
            '.s-price'
        ]

        for selector in price_selectors:
            elem = element.select_one(selector)
            if elem:
                price_text = elem.text.strip()
                # 清理价格文本
                price_text = re.sub(r'[^\d.,]', '', price_text)
                if price_text:
                    return price_text

        return None

    def extract_original_price(self, element):
        """提取原价（如果有折扣）"""
        elem = element.select_one('.a-text-price .a-offscreen')
        if elem:
            price_text = elem.text.strip()
            price_text = re.sub(r'[^\d.,]', '', price_text)
            if price_text:
                return price_text
        return None

    def extract_discount(self, element):
        """提取折扣信息"""
        discount_elem = element.select_one('.a-text-price + span')
        if discount_elem:
            discount_text = discount_elem.text.strip()
            # 提取折扣百分比
            match = re.search(r'(\d+)%', discount_text)
            if match:
                return f"{match.group(1)}%"
        return None

    def extract_rating(self, element):
        """提取商品评分"""
        rating_elem = element.select_one('.a-icon-alt')
        if rating_elem:
            rating_text = rating_elem.text.strip()
            match = re.search(r'(\d+\.?\d*)', rating_text)
            if match:
                return match.group(1)
        return None

    def extract_reviews(self, element):
        """提取评价数量"""
        selectors = [
            '.a-size-base.s-underline-text',
            '.a-size-base',
            'span.a-size-base'
        ]

        for selector in selectors:
            elem = element.select_one(selector)
            if elem:
                text = elem.text.strip()
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

    def extract_best_seller_info(self, element):
        """提取Best Seller信息"""
        # 查找Best Seller徽章
        best_seller_selectors = [
            '.a-badge-text',
            '.s-best-seller-badge',
            '.a-icon-best-seller'
        ]

        for selector in best_seller_selectors:
            elem = element.select_one(selector)
            if elem and 'best seller' in elem.text.lower():
                return elem.text.strip()

        # 检查文字中是否包含best seller
        text = str(element).lower()
        if 'best seller' in text or 'bestseller' in text:
            return 'Best Seller'

        return None

    def extract_amazon_choice_info(self, element):
        """提取Amazon's Choice信息"""
        choice_selectors = [
            '.ac-badge-rect',
            '.a-badge-label',
            '.ac-sparkle-badge'
        ]

        for selector in choice_selectors:
            elem = element.select_one(selector)
            if elem and 'choice' in elem.text.lower():
                return elem.text.strip()

        text = str(element).lower()
        if "amazon's choice" in text or 'amazon choice' in text:
            return "Amazon's Choice"

        return None

    def extract_sponsored_info(self, element):
        """提取赞助信息"""
        sponsored_selectors = [
            '.s-sponsored-label-info-icon',
            '.s-label-popover-default',
            '.a-color-secondary'
        ]

        for selector in sponsored_selectors:
            elem = element.select_one(selector)
            if elem and 'sponsored' in elem.text.lower():
                return 'Sponsored'

        text = str(element).lower()
        if 'sponsored' in text:
            return 'Sponsored'

        return None

    def extract_shipping_info(self, element):
        """提取发货信息"""
        shipping_selectors = [
            '.a-color-base.a-text-bold',
            '.s-align-children-center',
            '.a-row.a-size-base.a-color-secondary'
        ]

        for selector in shipping_selectors:
            elem = element.select_one(selector)
            if elem:
                text = elem.text.strip()
                if 'free' in text.lower() or 'delivery' in text.lower() or 'shipping' in text.lower():
                    return text

        return None

    def extract_prime_info(self, element):
        """提取Prime资格信息"""
        prime_selectors = [
            '.s-prime',
            '.a-icon-prime',
            '.prime-badge'
        ]

        for selector in prime_selectors:
            elem = element.select_one(selector)
            if elem:
                return 'Prime Eligible'

        text = str(element).lower()
        if 'prime' in text:
            return 'Prime Eligible'

        return None

    def alternative_parse_method(self, soup):
        """备用解析方法"""
        products = []

        # 尝试查找所有商品卡片
        cards = soup.select('[data-component-type="s-search-result"]')

        for card in cards:
            try:
                data = self.extract_product_basic_info(card)
                if data:
                    products.append(data)
            except Exception as e:
                continue

        return products

    def enrich_products_with_details(self, products):
        """为商品列表获取详细信息"""
        print(f"\n开始获取商品详情...")
        enriched_products = []

        for i, product in enumerate(products, 1):
            if 'url' in product and 'asin' in product:
                print(f"[{i}/{len(products)}] 获取详情: {product.get('title', 'N/A')[:50]}...")

                # 获取商品详情
                details = self.get_product_details(product['url'])
                if details:
                    product.update(details)
                    print(f"   获取到 {len(details)} 条详细信息")

                # 避免请求过快
                time.sleep(random.uniform(2, 5))

            enriched_products.append(product)

        return enriched_products

    def get_product_details(self, product_url):
        """获取商品详情页面信息"""
        if not product_url:
            return {}

        try:
            response = self.make_request(product_url, is_detail_page=True)
            if not response:
                return {}

            soup = BeautifulSoup(response.text, 'html.parser')
            details = {}

            # 1. 提取品牌
            details['brand'] = self.extract_brand(soup)

            # 2. 提取描述
            details['description'] = self.extract_description(soup)

            # 3. 提取技术规格
            details['technical_specs'] = self.extract_technical_specs(soup)

            # 4. 提取销售排名（销量指标）
            details['sales_rank'] = self.extract_sales_rank(soup)

            # 5. 提取库存状态
            details['availability'] = self.extract_availability(soup)

            # 6. 提取卖家信息
            details['seller_info'] = self.extract_seller_info(soup)

            # 7. 提取商品类别
            details['category'] = self.extract_category(soup)

            # 8. 提取商品尺寸/重量
            details['dimensions'] = self.extract_dimensions(soup)

            # 9. 提取商品颜色选项
            details['color_options'] = self.extract_color_options(soup)

            # 10. 提取保修信息
            details['warranty'] = self.extract_warranty(soup)

            # 11. 提取商品特点
            details['features'] = self.extract_features(soup)

            # 12. 提取问答数量
            details['qa_count'] = self.extract_qa_count(soup)

            # 13. 提取商品上架时间
            details['first_available'] = self.extract_first_available(soup)

            # 14. 提取更多图片
            details['additional_images'] = self.extract_additional_images(soup)

            # 移除空值
            details = {k: v for k, v in details.items() if v is not None}

            return details

        except Exception as e:
            print(f"解析商品详情时出错: {e}")
            return {}

    def extract_brand(self, soup):
        """提取品牌"""
        # 多种可能的品牌选择器
        brand_selectors = [
            '#bylineInfo',
            '#brand',
            '.a-section.a-spacing-none',
            'a#bylineInfo'
        ]

        for selector in brand_selectors:
            elem = soup.select_one(selector)
            if elem:
                brand_text = elem.text.strip()
                # 清理品牌文本
                brand_text = brand_text.replace('Brand:', '').replace('Visit the', '').strip()
                if brand_text:
                    return brand_text

        return None

    def extract_description(self, soup):
        """提取商品描述"""
        # 描述选择器
        desc_selectors = [
            '#productDescription',
            '#feature-bullets',
            '.a-section.a-spacing-medium'
        ]

        descriptions = []
        for selector in desc_selectors:
            elems = soup.select(selector)
            for elem in elems:
                text = elem.text.strip()
                if text and len(text) > 50:  # 确保是有效描述
                    descriptions.append(text)

        if descriptions:
            return "\n\n".join(descriptions[:3])  # 最多返回3个描述

        return None

    def extract_technical_specs(self, soup):
        """提取技术规格"""
        tech_specs = {}

        # 方法1: 从表格中提取
        spec_tables = soup.select('#productDetails_techSpec_section_1 tr, #technicalSpecifications_section_1 tr')
        for row in spec_tables:
            th = row.select_one('th')
            td = row.select_one('td')
            if th and td:
                key = th.text.strip().replace('\u200e', '').replace(':', '')
                value = td.text.strip().replace('\u200e', '')
                if key and value:
                    tech_specs[key] = value

        # 方法2: 从产品信息部分提取
        if not tech_specs:
            info_sections = soup.select('.a-section.a-spacing-medium.a-spacing-top-small')
            for section in info_sections:
                text = section.text.strip()
                lines = text.split('\n')
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            if key and value:
                                tech_specs[key] = value

        return tech_specs if tech_specs else None

    def extract_sales_rank(self, soup):
        """提取销售排名（销量指标）"""
        # 查找销售排名
        rank_selectors = [
            '#productDetails_detailBullets_sections1 tr',
            '.zg_hrsr_item',
            '#SalesRank'
        ]

        for selector in rank_selectors:
            elem = soup.select_one(selector)
            if elem:
                rank_text = elem.text.strip()
                # 提取排名数字
                match = re.search(r'#(\d+,?\d*)', rank_text)
                if match:
                    return match.group(1)
                elif rank_text:
                    return rank_text

        return None

    def extract_availability(self, soup):
        """提取库存状态"""
        availability_selectors = [
            '#availability',
            '#outOfStock',
            '.a-color-success',
            '.a-color-error'
        ]

        for selector in availability_selectors:
            elem = soup.select_one(selector)
            if elem:
                availability_text = elem.text.strip()
                if availability_text:
                    return availability_text

        return None

    def extract_seller_info(self, soup):
        """提取卖家信息"""
        seller_info = {}

        # 卖家名称
        seller_elem = soup.select_one('#sellerProfileTriggerId')
        if seller_elem:
            seller_info['name'] = seller_elem.text.strip()

        # 是否亚马逊自营
        sold_by_elem = soup.select_one('.tabular-buybox-text a')
        if sold_by_elem:
            seller_text = sold_by_elem.text.strip()
            seller_info['sold_by'] = seller_text
            if 'amazon' in seller_text.lower():
                seller_info['fulfilled_by_amazon'] = 'Yes'

        # 卖家评分
        rating_elem = soup.select_one('.a-icon.a-icon-star-small')
        if rating_elem:
            seller_info['seller_rating'] = rating_elem.text.strip()

        return seller_info if seller_info else None

    def extract_category(self, soup):
        """提取商品类别"""
        category_selectors = [
            '.a-list-item',
            '#wayfinding-breadcrumbs_feature_div',
            '.a-color-tertiary'
        ]

        categories = []
        for selector in category_selectors:
            elems = soup.select(selector)
            for elem in elems:
                text = elem.text.strip()
                if text and '›' in text:
                    # 清理类别文本
                    cats = [cat.strip() for cat in text.split('›')]
                    categories.extend(cats)

        if categories:
            return ' > '.join(categories[:5])  # 最多5级类别

        return None

    def extract_dimensions(self, soup):
        """提取商品尺寸和重量"""
        dimensions = {}

        # 在技术规格中查找尺寸和重量
        spec_text = str(soup)
        dimension_patterns = {
            'dimensions': r'[Dd]imensions?[:\s]*([^<>\n]+)',
            'weight': r'[Ww]eight[:\s]*([^<>\n]+)',
            'size': r'[Ss]ize[:\s]*([^<>\n]+)',
            'package_dimensions': r'[Pp]ackage [Dd]imensions[:\s]*([^<>\n]+)',
            'item_weight': r'[Ii]tem [Ww]eight[:\s]*([^<>\n]+)'
        }

        for key, pattern in dimension_patterns.items():
            match = re.search(pattern, spec_text)
            if match:
                dimensions[key] = match.group(1).strip()

        return dimensions if dimensions else None

    def extract_color_options(self, soup):
        """提取颜色选项"""
        color_selectors = [
            '#variation_color_name',
            '#color_name_0',
            '.a-button-text'
        ]

        colors = []
        for selector in color_selectors:
            elems = soup.select(selector)
            for elem in elems:
                text = elem.text.strip()
                if text and text not in colors:
                    colors.append(text)

        if colors:
            return ', '.join(colors[:10])  # 最多10种颜色

        return None

    def extract_warranty(self, soup):
        """提取保修信息"""
        warranty_selectors = [
            '.a-section.warranty-information',
            '#warrantyInformation',
            '.a-spacing-small'
        ]

        for selector in warranty_selectors:
            elem = soup.select_one(selector)
            if elem:
                warranty_text = elem.text.strip()
                if 'warranty' in warranty_text.lower() or 'guarantee' in warranty_text.lower():
                    return warranty_text

        return None

    def extract_features(self, soup):
        """提取商品特点"""
        features = []

        # 从要点列表中提取
        bullet_points = soup.select('#feature-bullets li')
        for point in bullet_points:
            text = point.text.strip()
            if text and len(text) > 5:
                features.append(text)

        if features:
            return features[:10]  # 最多10个特点

        return None

    def extract_qa_count(self, soup):
        """提取问答数量"""
        qa_elem = soup.select_one('#askATFLink')
        if qa_elem:
            text = qa_elem.text.strip()
            # 提取数字
            match = re.search(r'(\d+,?\d*)', text)
            if match:
                return match.group(1)

        return None

    def extract_first_available(self, soup):
        """提取首次上架时间"""
        date_selectors = [
            '#productDetails_detailBullets_sections1 tr',
            '.a-size-base.a-color-secondary'
        ]

        for selector in date_selectors:
            elems = soup.select(selector)
            for elem in elems:
                text = elem.text.strip()
                if 'first available' in text.lower() or 'date first listed' in text.lower():
                    # 提取日期
                    date_pattern = r'(\d{1,2} [A-Za-z]+ \d{4}|\d{4}-\d{2}-\d{2})'
                    match = re.search(date_pattern, text)
                    if match:
                        return match.group(1)

        return None

    def extract_additional_images(self, soup):
        """提取更多图片"""
        images = []
        img_elements = soup.select('#altImages img, #imageBlock img')

        for img in img_elements:
            for attr in ['src', 'data-old-hires', 'data-a-dynamic-image']:
                if img.get(attr):
                    img_url = img[attr]
                    # 转换为高清图片链接
                    if isinstance(img_url, str) and 'http' in img_url:
                        if '_SS' in img_url:
                            hd_url = img_url.replace('_SS', '_SL1500')
                            images.append(hd_url)
                        elif '._S' in img_url:
                            hd_url = img_url.split('._')[0] + '._SL1500_.jpg'
                            images.append(hd_url)
                        else:
                            images.append(img_url)
                    break

        # 去重
        unique_images = []
        for img in images:
            if img not in unique_images:
                unique_images.append(img)

        return unique_images[:5] if unique_images else None  # 最多5张图片

    def download_image(self, image_url, product_asin):
        """下载商品图片"""
        if not image_url or not product_asin:
            return None

        try:
            headers = self.get_headers()
            response = requests.get(image_url, headers=headers, timeout=15)

            if response.status_code == 200:
                # 生成文件名
                filename = f"{product_asin}_{int(time.time())}.jpg"
                image_path = os.path.join(current_dir, 'amazon_data', 'images', filename)

                with open(image_path, 'wb') as f:
                    f.write(response.content)

                print(f"✓ 图片下载成功: {filename}")
                return image_path
            else:
                print(f"图片下载失败: HTTP {response.status_code}")
                return None

        except Exception as e:
            print(f"下载图片时出错: {e}")
            return None

    def save_to_csv(self, products, keyword):
        """保存数据到CSV文件"""
        if not products:
            print("没有数据可保存")
            return None

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
        filename = f"amazon_{self.country_code}_{safe_keyword}_{timestamp}.csv"
        filepath = os.path.join(current_dir, 'amazon_data', filename)

        # 确定CSV字段（包括所有可能的信息）
        base_fields = [
            'asin', 'title', 'price', 'original_price', 'discount',
            'rating', 'reviews', 'best_seller', 'amazon_choice', 'sponsored',
            'shipping_info', 'prime_eligible', 'url', 'image_url'
        ]

        detail_fields = [
            'brand', 'description', 'sales_rank', 'availability',
            'category', 'color_options', 'warranty', 'qa_count',
            'first_available', 'crawled_at'
        ]

        # 收集所有可能的字段
        all_fields = base_fields + detail_fields

        # 添加技术规格和卖家信息作为单独字段（如果存在）
        for product in products:
            if 'technical_specs' in product and isinstance(product['technical_specs'], dict):
                for key in product['technical_specs'].keys():
                    field_name = f"spec_{key}"
                    if field_name not in all_fields:
                        all_fields.append(field_name)

            if 'seller_info' in product and isinstance(product['seller_info'], dict):
                for key in product['seller_info'].keys():
                    field_name = f"seller_{key}"
                    if field_name not in all_fields:
                        all_fields.append(field_name)

            if 'dimensions' in product and isinstance(product['dimensions'], dict):
                for key in product['dimensions'].keys():
                    field_name = f"dim_{key}"
                    if field_name not in all_fields:
                        all_fields.append(field_name)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=all_fields)
            writer.writeheader()

            for product in products:
                row = {}

                # 添加基础字段
                for field in all_fields:
                    if field in product:
                        value = product[field]
                        # 处理特殊类型
                        if isinstance(value, (list, dict)):
                            row[field] = str(value)
                        else:
                            row[field] = value
                    else:
                        row[field] = ''

                writer.writerow(row)

        print(f"\n数据已保存到: {filepath}")
        print(f"共保存 {len(products)} 条记录，包含 {len(all_fields)} 个字段")
        return filepath

    def save_to_json(self, products, keyword):
        """保存数据到JSON文件"""
        if not products:
            print("没有数据可保存")
            return None

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
        filename = f"amazon_{self.country_code}_{safe_keyword}_{timestamp}.json"
        filepath = os.path.join(current_dir, 'amazon_data', filename)

        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(products, jsonfile, ensure_ascii=False, indent=2, default=str)

        print(f"数据已保存到: {filepath}")
        return filepath


def main():
    """主函数"""
    print("=" * 60)
    print("亚马逊商品爬虫 v3.0 - 增强版")
    print("=" * 60)

    # 选择国家站点
    print("\n支持的亚马逊站点:")
    print("1. 新加坡 (sg) - 默认")
    print("2. 美国 (com)")
    print("3. 英国 (co.uk)")
    print("4. 日本 (co.jp)")
    print("5. 德国 (de)")

    country_choice = input("\n请选择站点 (1-5，默认1): ").strip()

    country_map = {
        '1': 'sg',
        '2': 'com',
        '3': 'co.uk',
        '4': 'co.jp',
        '5': 'de'
    }

    country_code = country_map.get(country_choice, 'sg')
    print(f"使用站点: amazon.{country_code}")

    # 创建爬虫实例
    crawler = AmazonCrawler(country_code=country_code)

    # 用户输入搜索关键词
    keyword = input("\n请输入要搜索的商品关键词: ").strip()
    if not keyword:
        print("关键词不能为空!")
        return

    # 用户输入爬取页数
    try:
        pages = int(input("请输入要爬取的页数 (1-5，建议1-2): ").strip() or "1")
        pages = max(1, min(pages, 5))
    except:
        pages = 1
        print("输入无效，使用默认值1页")

    # 询问是否获取详情
    get_details = input("\n是否获取商品详细信息? (y/n，建议y): ").strip().lower() == 'y'

    # 询问是否下载图片
    download_images = input("是否下载商品图片? (y/n，默认n): ").strip().lower() == 'y'

    print(f"\n开始爬取亚马逊{country_code.upper()}站点商品: {keyword}")
    print(f"爬取页数: {pages}")
    print(f"获取详情: {'是' if get_details else '否'}")
    print(f"下载图片: {'是' if download_images else '否'}")
    print("=" * 60)

    # 搜索商品
    products = crawler.search_products(keyword, pages=pages, get_details=get_details)

    if not products:
        print("\n没有找到商品!")
        print("可能的原因:")
        print("1. 页面结构已变化")
        print("2. 需要更新cookies")
        print("3. IP被限制")
        print("4. 搜索关键词无结果")
        return

    print(f"\n搜索完成，共找到 {len(products)} 个商品")

    # 下载图片
    if download_images and products:
        print("\n开始下载商品图片...")
        for i, product in enumerate(products, 1):
            if 'image_url' in product and 'asin' in product:
                print(f"[{i}/{len(products)}] 下载图片...")
                image_path = crawler.download_image(product['image_url'], product['asin'])
                if image_path:
                    product['local_image_path'] = image_path
                time.sleep(random.uniform(1, 2))

    # 保存数据
    print("\n正在保存数据...")
    csv_file = crawler.save_to_csv(products, keyword)
    json_file = crawler.save_to_json(products, keyword)

    # 显示统计信息
    print("\n" + "=" * 60)
    print("爬取统计:")
    print(f"站点: amazon.{country_code}")
    print(f"关键词: {keyword}")
    print(f"爬取页数: {pages}")
    print(f"商品总数: {len(products)}")

    # 详细统计
    if products:
        stats = {
            '有价格': sum(1 for p in products if 'price' in p and p['price']),
            '有评分': sum(1 for p in products if 'rating' in p and p['rating']),
            '有评价': sum(1 for p in products if 'reviews' in p and p['reviews']),
            'Best Seller': sum(1 for p in products if 'best_seller' in p and p['best_seller']),
            "Amazon's Choice": sum(1 for p in products if 'amazon_choice' in p and p['amazon_choice']),
            '赞助商品': sum(1 for p in products if 'sponsored' in p and p['sponsored']),
            'Prime商品': sum(1 for p in products if 'prime_eligible' in p and p['prime_eligible']),
            '有品牌': sum(1 for p in products if 'brand' in p and p['brand']),
            '有销售排名': sum(1 for p in products if 'sales_rank' in p and p['sales_rank']),
        }

        for stat_name, stat_value in stats.items():
            print(f"{stat_name}: {stat_value}")

    if csv_file:
        print(f"\nCSV文件: {os.path.basename(csv_file)}")
    if json_file:
        print(f"JSON文件: {os.path.basename(json_file)}")

    print("=" * 60)

    # 显示示例商品信息
    if products:
        print("\n示例商品详细信息:")
        for i, product in enumerate(products[:3], 1):
            print(f"\n{i}. ASIN: {product.get('asin', 'N/A')}")
            print(f"   标题: {product.get('title', 'N/A')[:70]}...")
            print(f"   价格: {product.get('price', 'N/A')}", end="")
            if product.get('original_price'):
                print(f" (原价: {product.get('original_price')})", end="")
            if product.get('discount'):
                print(f" (折扣: {product.get('discount')})", end="")
            print()
            print(f"   评分: {product.get('rating', 'N/A')} ({product.get('reviews', '0')} 评价)")

            if product.get('brand'):
                print(f"   品牌: {product.get('brand')}")

            if product.get('sales_rank'):
                print(f"   销售排名: #{product.get('sales_rank')}")

            if product.get('best_seller') or product.get('amazon_choice'):
                badges = []
                if product.get('best_seller'):
                    badges.append(product.get('best_seller'))
                if product.get('amazon_choice'):
                    badges.append(product.get('amazon_choice'))
                print(f"   徽章: {', '.join(badges)}")

            if product.get('description'):
                desc_preview = product.get('description')[:100] + "..." if len(
                    product.get('description')) > 100 else product.get('description')
                print(f"   描述预览: {desc_preview}")


if __name__ == "__main__":
    # 安装所需库: pip install requests beautifulsoup4

    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断程序")
    except Exception as e:
        print(f"\n程序运行出错: {e}")
        import traceback

        traceback.print_exc()

    input("\n按Enter键退出...")