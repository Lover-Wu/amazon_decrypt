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

        # 使用你提供的真实请求头
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

        # 初始化cookie（从你提供的复制）
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
        directories = ['amazon_data', 'amazon_data/products', 'amazon_data/images']
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

    def search_products(self, keyword, pages=1):
        """搜索商品"""
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
        keyword_encoded = requests.utils.quote(keyword)

        # 亚马逊搜索URL格式
        if page == 1:
            return f"{self.base_url}/s?k={keyword_encoded}&ref=nb_sb_noss_2"
        else:
            return f"{self.base_url}/s?k={keyword_encoded}&page={page}&ref=sr_pg_{page}"

    def make_request(self, url, max_retries=3):
        """发送请求"""
        for attempt in range(max_retries):
            try:
                headers = self.get_headers(referer=self.base_url)

                response = requests.get(
                    url,
                    headers=headers,
                    cookies=self.cookies,
                    proxies=self.proxies,
                    timeout=20,
                    allow_redirects=True,
                    verify=True
                )

                print(f"状态码: {response.status_code}, URL: {url[:80]}...")

                if response.status_code == 200:
                    # 检查是否是验证页面
                    if "api-services-support@amazon.com" in response.text or "enter the characters you see below" in response.text:
                        print("遇到验证码页面!")
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
                else:
                    print(f"尝试 {attempt + 1}/{max_retries}: 状态码 {response.status_code}")
                    time.sleep(random.uniform(3, 6))

            except requests.exceptions.RequestException as e:
                print(f"尝试 {attempt + 1}/{max_retries}: 请求异常 - {e}")
                time.sleep(random.uniform(3, 6))

        print(f"请求失败: {url}")
        return None

    def parse_search_results(self, html):
        """解析搜索结果页面 - 使用更灵活的方法"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # 方法1: 查找所有包含data-asin属性的元素
        elements_with_asin = soup.find_all(attrs={"data-asin": True})

        for element in elements_with_asin:
            try:
                # 确保是商品元素（排除其他元素）
                if self.is_product_element(element):
                    product_data = self.extract_product_data(element)
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
        # 检查是否包含商品相关的内容
        text = str(element)
        product_indicators = [
            'data-asin=',
            'data-index=',
            'data-component-type="s-search-result"',
            's-result-item',
            'sponsored',
            'amazon'
        ]

        # 至少包含两个商品指示器
        indicators_found = sum(1 for indicator in product_indicators if indicator in text)
        return indicators_found >= 2

    def extract_product_data(self, product_element):
        """从商品元素提取数据"""
        data = {}

        # 提取ASIN
        asin = product_element.get('data-asin', '')
        if not asin:
            return None

        data['asin'] = asin

        # 尝试多种方法提取标题
        title = self.extract_title(product_element)
        if title:
            data['title'] = title

        # 提取链接
        url = self.extract_url(product_element)
        if url:
            data['url'] = url

        # 提取价格
        price = self.extract_price(product_element)
        if price:
            data['price'] = price

        # 提取评分
        rating = self.extract_rating(product_element)
        if rating:
            data['rating'] = rating

        # 提取评价数量
        reviews = self.extract_reviews(product_element)
        if reviews:
            data['reviews'] = reviews

        # 提取图片
        image_url = self.extract_image_url(product_element)
        if image_url:
            data['image_url'] = image_url

        # 提取是否为赞助商品
        if 'sponsored' in str(product_element).lower():
            data['sponsored'] = 'Yes'

        # 添加爬取时间
        data['crawled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return data

    def extract_title(self, element):
        """提取商品标题"""
        # 多种可能的选择器
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
                return elem.text.strip()[:200]  # 限制标题长度

        return None

    def extract_url(self, element):
        """提取商品链接"""
        # 多种可能的选择器
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
        """提取商品价格"""
        # 查找价格元素
        price_text = ''

        # 方法1: 直接查找价格
        price_elem = element.select_one('.a-price .a-offscreen')
        if price_elem:
            price_text = price_elem.text.strip()

        # 方法2: 查找包含货币符号的文本
        if not price_text:
            price_patterns = [r'\$\d+\.\d{2}', r'SGD\s*\d+\.\d{2}', r'USD\s*\d+\.\d{2}']
            text = str(element)
            for pattern in price_patterns:
                match = re.search(pattern, text)
                if match:
                    price_text = match.group()
                    break

        return price_text if price_text else None

    def extract_rating(self, element):
        """提取商品评分"""
        rating_elem = element.select_one('.a-icon-alt')
        if rating_elem:
            rating_text = rating_elem.text.strip()
            # 提取数字评分，如 "4.5 out of 5 stars"
            match = re.search(r'(\d+\.?\d*)', rating_text)
            if match:
                return match.group(1)

        return None

    def extract_reviews(self, element):
        """提取评价数量"""
        # 多种可能的选择器
        selectors = [
            '.a-size-base.s-underline-text',
            '.a-size-base',
            'span.a-size-base'
        ]

        for selector in selectors:
            elem = element.select_one(selector)
            if elem:
                text = elem.text.strip()
                # 查找包含数字的评价数量
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

    def alternative_parse_method(self, soup):
        """备用解析方法"""
        products = []

        # 尝试查找所有商品卡片
        cards = soup.select('[data-component-type="s-search-result"]')

        for card in cards:
            try:
                data = {}

                # 提取ASIN
                asin = card.get('data-asin', '')
                if not asin:
                    continue

                data['asin'] = asin

                # 提取其他信息
                title_elem = card.select_one('h2 a span')
                if title_elem:
                    data['title'] = title_elem.text.strip()[:200]

                link_elem = card.select_one('h2 a')
                if link_elem and link_elem.get('href'):
                    href = link_elem['href']
                    if href.startswith('/'):
                        data['url'] = f"{self.base_url}{href}"

                price_elem = card.select_one('.a-price .a-offscreen')
                if price_elem:
                    data['price'] = price_elem.text.strip()

                rating_elem = card.select_one('.a-icon-alt')
                if rating_elem:
                    rating_text = rating_elem.text.strip()
                    match = re.search(r'(\d+\.?\d*)', rating_text)
                    if match:
                        data['rating'] = match.group(1)

                # 添加爬取时间
                data['crawled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                products.append(data)

            except Exception as e:
                continue

        return products

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

        # 确定CSV字段
        fieldnames = ['asin', 'title', 'price', 'rating', 'reviews', 'url', 'image_url', 'crawled_at']

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for product in products:
                # 确保只写入定义的字段
                row = {field: product.get(field, '') for field in fieldnames}
                writer.writerow(row)

        print(f"\n数据已保存到: {filepath}")
        print(f"共保存 {len(products)} 条记录")
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
            json.dump(products, jsonfile, ensure_ascii=False, indent=2)

        print(f"数据已保存到: {filepath}")
        return filepath


def main():
    """主函数"""
    print("=" * 60)
    print("亚马逊商品爬虫 v2.0")
    print("=" * 60)

    # 选择国家站点
    print("\n支持的亚马逊站点:")
    print("1. 新加坡 (sg)")
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
        pages = max(1, min(pages, 5))  # 限制1-5页
    except:
        pages = 1
        print("输入无效，使用默认值1页")

    print(f"\n开始爬取亚马逊{country_code.upper()}站点商品: {keyword}")
    print(f"爬取页数: {pages}")
    print("=" * 60)

    # 搜索商品
    products = crawler.search_products(keyword, pages=pages)

    if not products:
        print("\n没有找到商品!")
        print("可能的原因:")
        print("1. 页面结构已变化")
        print("2. 需要更新cookies")
        print("3. IP被限制")
        print("4. 搜索关键词无结果")
        return

    print(f"\n搜索完成，共找到 {len(products)} 个商品")

    # 询问是否下载图片
    download_images = input("\n是否下载商品图片? (y/n, 默认n): ").strip().lower() == 'y'

    if download_images:
        print("\n开始下载商品图片...")
        for i, product in enumerate(products, 1):
            if 'image_url' in product and 'asin' in product:
                print(f"[{i}/{len(products)}] 下载图片...")
                image_path = crawler.download_image(product['image_url'], product['asin'])
                if image_path:
                    product['local_image_path'] = image_path
                time.sleep(random.uniform(1, 2))  # 图片下载延迟

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
    print(f"有价格的商品: {sum(1 for p in products if 'price' in p and p['price'])}")
    print(f"有评分的商品: {sum(1 for p in products if 'rating' in p and p['rating'])}")
    print(f"有图片的商品: {sum(1 for p in products if 'image_url' in p and p['image_url'])}")
    print(f"赞助商品: {sum(1 for p in products if p.get('sponsored') == 'Yes')}")

    if csv_file:
        print(f"\nCSV文件: {os.path.basename(csv_file)}")
    if json_file:
        print(f"JSON文件: {os.path.basename(json_file)}")

    print("=" * 60)

    # 显示前几个商品作为示例
    if products:
        print("\n前5个商品示例:")
        for i, product in enumerate(products[:5], 1):
            print(f"\n{i}. ASIN: {product.get('asin', 'N/A')}")
            print(f"   标题: {product.get('title', 'N/A')[:60]}...")
            print(f"   价格: {product.get('price', 'N/A')}")
            print(f"   评分: {product.get('rating', 'N/A')}")
            if 'url' in product:
                print(f"   链接: {product['url'][:60]}...")


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