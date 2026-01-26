"""
Amazon 商品详情页爬虫
基于 DrissionPage 库实现
根据 ASIN 编码爬取商品详情信息：标题、五点描述、价格、属性、A+页图片
"""
import time
import os
import json
import re
from typing import List, Dict, Optional
from DrissionPage import ChromiumPage, ChromiumOptions, Chromium
import requests
from pathlib import Path


class AmazonDetailCrawler:
    """Amazon 商品详情页爬虫类"""
    
    def __init__(self, headless: bool = False, use_saved_login: bool = True, local_port: int = None):
        """
        初始化爬虫
        
        Args:
            headless: 是否无头模式运行
            use_saved_login: 是否使用保存的登录信息（用户数据目录）
            local_port: 接管本地浏览器的端口号（如 9333），如果指定则忽略其他参数
        """
        self.page = None
        self.browser = None
        self.headless = headless
        self.use_saved_login = use_saved_login
        self.local_port = local_port
        self.base_url = "https://www.amazon.com/dp/"
        self._init_browser()

    def _init_browser(self):
        """初始化浏览器配置，设置去指纹参数"""
        # 如果指定了本地端口，直接接管已打开的浏览器
        if self.local_port:
            print(f"正在接管本地浏览器（端口: {self.local_port}）...")
            print(f"提示: 请确保已用 --remote-debugging-port={self.local_port} 启动 Microsoft Edge")

            try:
                # 创建配置
                from DrissionPage import ChromiumOptions
                co = ChromiumOptions()

                # ========== 指定 Microsoft Edge 路径 ==========
                # Windows 10/11 标准 Edge 路径
                edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

                # 验证路径是否存在
                if os.path.exists(edge_path):
                    co.set_browser_path(edge_path)
                    print(f"✅ 指定 Edge 路径: {edge_path}")
                else:
                    # 尝试其他可能路径
                    alt_paths = [
                        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',  # ARM64版本
                        r'C:\Users\{}\AppData\Local\Microsoft\Edge\Application\msedge.exe'.format(os.getlogin()),
                        # 用户安装
                    ]

                    for path in alt_paths:
                        if os.path.exists(path):
                            co.set_browser_path(path)
                            print(f"✅ 找到 Edge 备用路径: {path}")
                            break
                    else:
                        print("⚠️ 未找到 Edge 路径，使用系统默认")

                # 设置接管端口
                co.set_local_port(self.local_port)

                # 非无头模式
                if not self.headless:
                    co.headless(False)

                # Edge 特定配置
                co.set_argument('--disable-features=EdgeTranslate')
                co.set_argument('--disable-component-update')

                # 创建页面对象（接管模式）
                self.page = ChromiumPage(co)
                print("✅ 已成功接管 Microsoft Edge 浏览器")
                return

            except Exception as e:
                print(f"❌ 接管失败: {e}")
                print("\n💡 Edge 浏览器启动步骤:")
                print("1. 关闭所有 Edge 窗口")
                print("2. 运行启动命令:")
                print('   msedge.exe --remote-debugging-port=9333 --remote-allow-origins=*')
                print("3. 或运行脚本: ..\\start_edge.bat")
                print("4. 保持 Edge 窗口打开，然后重试")
                raise

        # ========== 自动启动模式（当未指定local_port时） ==========
        print("自动启动 Microsoft Edge 浏览器...")

        # 配置浏览器选项
        co = ChromiumOptions()

        # ========== 设置 Microsoft Edge 为默认浏览器 ==========
        # Windows Edge 标准路径
        default_edge_paths = [
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',  # 32位标准版
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',  # 64位版
            r'C:\Users\{}\AppData\Local\Microsoft\Edge\Application\msedge.exe'.format(os.getlogin()),  # 用户安装
        ]

        edge_found = False
        for path in default_edge_paths:
            if os.path.exists(path):
                co.set_browser_path(path)
                print(f"✅ 使用 Microsoft Edge: {path}")
                edge_found = True
                break

        if not edge_found:
            print("⚠️ 未找到 Microsoft Edge，将使用系统默认浏览器")
            print("💡 请确保已安装 Microsoft Edge 浏览器")

        # Edge 优化配置
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--disable-gpu')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')

        # Edge 特定配置
        co.set_argument('--disable-features=EdgeTranslate,EdgeCollections')
        co.set_argument('--disable-component-update')
        co.set_argument('--lang=zh-CN')  # 设置中文语言

        # 设置 User-Agent (Edge)
        co.set_user_agent(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        )

        # 是否使用用户数据目录（保存登录信息）
        if self.use_saved_login:
            user_data_dir = os.path.join(os.path.dirname(__file__), 'edge_browser_data')
            co.set_user_data_path(user_data_dir)
            print(f"✅ 使用 Edge 用户数据目录: {user_data_dir}")

        # 无头模式
        if self.headless:
            co.headless()
        else:
            co.headless(False)
            co.set_argument('--start-maximized')  # 启动时最大化

        try:
            # 初始化页面
            self.page = ChromiumPage(addr_or_opts=co)

            # 执行 JavaScript 去除 webdriver 特征
            self.page.run_js('''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            ''')

            print(f"✅ Microsoft Edge 浏览器启动成功")
            print(f"🌐 浏览器版本: {self.page.browser.version if hasattr(self.page, 'browser') else '未知'}")

        except Exception as e:
            print(f"❌ Edge 浏览器启动失败: {e}")

            # 备用方案：使用简化配置
            print("🔄 尝试简化配置启动...")
            try:
                co_simple = ChromiumOptions()
                co_simple.headless(False)
                self.page = ChromiumPage(co_simple)
                print("✅ 简化配置启动成功")
            except Exception as e2:
                print(f"❌ 简化配置也失败: {e2}")
                raise
    
    def crawl_product(self, asin: str) -> Optional[Dict]:
        """
        爬取单个商品详情
        
        Args:
            asin: 商品 ASIN 编码
            
        Returns:
            商品详情数据字典
        """
        product_data = {
            'asin': asin,
            'url': f"{self.base_url}{asin}",
            'title': None,
            'bullet_points': [],
            'price': None,
            'product_details': {},  # 现在是嵌套字典: {"Table Name": {"key": "value"}}
            'aplus_images': []
        }
        
        try:
            print(f"\n正在爬取 ASIN: {asin}")
            url = f"{self.base_url}{asin}"
            self.page.get(url)
            time.sleep(3)  # 等待页面加载
            
            # 提取标题
            product_data['title'] = self._extract_title()
            
            # 提取五点描述
            product_data['bullet_points'] = self._extract_bullet_points()
            
            # 提取价格
            product_data['price'] = self._extract_price()
            
            # 提取商品详情
            product_data['product_details'] = self._extract_product_details()
            
            # 提取 A+ 页图片
            product_data['aplus_images'] = self._extract_aplus_images(asin)
            
            print(f"✅ 成功爬取 ASIN: {asin}")
            return product_data
            
        except Exception as e:
            print(f"❌ 爬取 ASIN {asin} 失败: {e}")
            import traceback
            traceback.print_exc()
            return product_data
    
    def _extract_title(self) -> Optional[str]:
        """提取商品标题"""
        try:
            title_element = self.page.ele('xpath://span[@id="productTitle"]', timeout=5)
            if title_element:
                title = title_element.text.strip()
                print(f"  标题: {title[:50]}...")
                return title
        except Exception as e:
            print(f"  ⚠️ 提取标题失败: {e}")
        return None
    
    def _extract_bullet_points(self) -> List[str]:
        """提取五点描述"""
        bullet_points = []
        try:
            bullets_container = self.page.ele('xpath://div[@id="feature-bullets"]', timeout=5)
            if bullets_container:
                # 查找所有 li 元素
                li_elements = bullets_container.eles('tag:li')
                for li in li_elements:
                    text = li.text.strip()
                    # 过滤掉空文本和"See more product details"等无关内容
                    if text and not text.startswith('See more') and len(text) > 10:
                        bullet_points.append(text)
                print(f"  五点描述: 共 {len(bullet_points)} 条")
        except Exception as e:
            print(f"  ⚠️ 提取五点描述失败: {e}")
        return bullet_points
    
    def _extract_price(self) -> Optional[str]:
        """提取价格（尝试多个XPath，选择第一个带货币符号的价格）"""
        price_xpaths = [
            '//div[@id="apex_desktop_newAccordionRow"]//div[@id="corePriceDisplay_desktop_feature_div"]//span[@aria-hidden="true"]',
            '//span[@class="a-price aok-align-center reinventPricePriceToPayMargin priceToPay"]//span[@aria-hidden="true"]',
            '//span[@class="a-price-whole"]',
            '//span[contains(@class, "a-price")]//span[@class="a-offscreen"]',
            '//span[contains(@class, "a-price")]//span[@aria-hidden="true"]'
        ]
        
        # 货币符号列表
        currency_symbols = ['$', '¥', '€', '£', '₹', '₽', '₩', '¢', 'R$', 'CA$', 'AU$', 'HK$', 'NZ$', 'S$']
        
        for xpath in price_xpaths:
            try:
                # 尝试获取所有匹配的元素
                price_elements = self.page.eles(f'xpath:{xpath}', timeout=2)
                if not price_elements:
                    continue
                
                # 遍历所有元素，找到第一个包含货币符号的价格
                for price_element in price_elements:
                    price_text = price_element.text.strip()
                    if not price_text:
                        continue
                    
                    # 检查是否包含货币符号
                    has_currency = any(symbol in price_text for symbol in currency_symbols)
                    
                    # 排除折扣百分比（如 -28%）和纯文本（如 List Price:）
                    is_discount = '%' in price_text and '-' in price_text
                    is_label = any(label in price_text.lower() for label in ['list price', 'was:', 'save', 'typical'])
                    
                    # 如果包含货币符号且不是折扣或标签，返回该价格
                    if has_currency and not is_discount and not is_label:
                        print(f"  价格: {price_text}")
                        return price_text
                
            except Exception as e:
                continue
        
        print("  ⚠️ 未找到价格信息")
        return None
    
    def _extract_product_details(self) -> Dict[str, Dict[str, str]]:
        """提取商品详情属性（按表格分组）"""
        details = {}
        total_items = 0
        
        try:
            # 方法1: 优先从左右两侧的详情表格提取（噪音更少）
            left_sections = self.page.ele('xpath://div[@id="productDetails_expanderTables_depthLeftSections"]', timeout=5)
            right_sections = self.page.ele('xpath://div[@id="productDetails_expanderTables_depthRightSections"]', timeout=5)
            
            all_sections = []
            if left_sections:
                all_sections.append(('Left', left_sections))
            if right_sections:
                all_sections.append(('Right', right_sections))
            
            if all_sections:
                print(f"  找到左右详情区域: {len(all_sections)} 个")
                
                for section_name, section_container in all_sections:
                    # 在每个容器中查找所有表格分组
                    expander_divs = section_container.eles('xpath:.//div[contains(@class, "a-expander-container")]')
                    
                    print(f"    [{section_name}] 找到 {len(expander_divs)} 个表格分组")
                    
                    for expander in expander_divs:
                        try:
                            # 提取标题
                            title_elem = expander.ele('xpath:.//span[@class="a-expander-prompt"]')
                            section_title = title_elem.text.strip() if title_elem else None
                            
                            if not section_title:
                                continue
                            
                            # 提取表格
                            table = expander.ele('xpath:.//table[contains(@class, "prodDetTable")]')
                            if not table:
                                continue
                            
                            section_data = {}
                            rows = table.eles('tag:tr')
                            
                            for row in rows:
                                try:
                                    th = row.ele('tag:th')
                                    td = row.ele('tag:td')
                                    
                                    if th and td:
                                        key = th.text.strip()
                                        value = td.text.strip()
                                        
                                        # 过滤掉噪音数据（如脚本、评论等）
                                        if key and value and len(key) < 100 and not key.startswith('var '):
                                            key = ' '.join(key.split())
                                            value = ' '.join(value.split())
                                            section_data[key] = value
                                            total_items += 1
                                except:
                                    continue
                            
                            if section_data:
                                final_title = section_title
                                counter = 2
                                while final_title in details:
                                    final_title = f"{section_title} {counter}"
                                    counter += 1
                                
                                details[final_title] = section_data
                                print(f"      ✅ [{final_title}]: {len(section_data)} 项")
                                
                        except Exception as e:
                            continue
            
            # 方法2: 如果没有数据，降级到从 prodDetails 下的可折叠表格提取
            if not details:
                print("  ⚠️ 未找到左右详情区域，尝试从 prodDetails 提取...")
                
                prod_details = self.page.ele('xpath://div[@id="prodDetails"]', timeout=3)
                if prod_details:
                    expander_sections = prod_details.eles('xpath:.//div[contains(@class, "a-expander-container")]')
                    
                    if expander_sections:
                        print(f"  找到 {len(expander_sections)} 个可折叠表格")
                        
                        for section in expander_sections:
                            try:
                                # 提取表格标题
                                title_elem = section.ele('xpath:.//span[@class="a-expander-prompt"]')
                                section_title = title_elem.text.strip() if title_elem else None
                                
                                if not section_title:
                                    section_title = "Unknown Section"
                                
                                # 提取表格数据
                                table = section.ele('xpath:.//table[contains(@class, "prodDetTable")]')
                                if not table:
                                    continue
                                
                                section_data = {}
                                rows = table.eles('tag:tr')
                                
                                for row in rows:
                                    try:
                                        th = row.ele('tag:th')
                                        td = row.ele('tag:td')
                                        
                                        if th and td:
                                            key = th.text.strip()
                                            value = td.text.strip()
                                            
                                            if key and value:
                                                key = ' '.join(key.split())
                                                value = ' '.join(value.split())
                                                section_data[key] = value
                                                total_items += 1
                                    except:
                                        continue
                                
                                if section_data:
                                    final_title = section_title
                                    counter = 2
                                    while final_title in details:
                                        final_title = f"{section_title} {counter}"
                                        counter += 1
                                    
                                    details[final_title] = section_data
                                    print(f"    ✅ [{final_title}]: {len(section_data)} 项")
                                    
                            except Exception as e:
                                print(f"    ⚠️ 处理表格分组失败: {e}")
                                continue
            
            print(f"  商品属性: 共 {len(details)} 个表格, {total_items} 项")
            
        except Exception as e:
            print(f"  ⚠️ 提取商品详情失败: {e}")
            import traceback
            traceback.print_exc()
        
        return details
    
    def _extract_aplus_images(self, asin: str) -> List[Dict[str, str]]:
        """
        提取 A+ 页面的图片
        
        Returns:
            图片信息列表，每项包含 url 和 local_path
        """
        images = []
        
        # 临时关闭图片下载功能以提高爬取速度
        print("  ⏭️  已跳过 A+ 图片下载（功能已关闭）")
        return images
        
        seen_urls = set()  # 用于去重
        
        try:
            # 查找所有包含 aplus 的容器
            aplus_containers = self.page.eles('xpath://div[contains(@class, "aplus")]')

            print(f"  找到 {len(aplus_containers)} 个 A+ 容器")

            for idx, container in enumerate(aplus_containers):
                # 在每个容器中查找图片
                imgs = container.eles('tag:img')
                for img in imgs:
                    img_url = img.attr('src') or img.attr('data-src')
                    if img_url and 'aplus-media' in img_url:
                        # 确保使用高质量图片链接
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url

                        # 去重：检查URL是否已存在
                        if img_url in seen_urls:
                            continue
                        seen_urls.add(img_url)

                        images.append({
                            'url': img_url,
                            'container_index': idx,
                            'local_path': None,  # 稍后下载时填充
                            'file_size': None  # 稍后下载时填充
                        })

            print(f"  A+ 图片（去重前）: {len(aplus_containers)} 个容器")
            print(f"  A+ 图片（去重后）: {len(images)} 张")

            # 下载图片
            if images:
                downloaded = self._download_aplus_images(images, asin)
                # 只保留成功下载的图片
                images = [img for img in images if img['local_path']]
                print(f"  A+ 图片（最终保存）: {len(images)} 张")

        except Exception as e:
            print(f"  ⚠️ 提取 A+ 图片失败: {e}")

        return images
    
    def _download_aplus_images(self, images: List[Dict], asin: str, min_size_kb: int = 100):
        """
        下载 A+ 图片到本地（过滤小于指定大小的图片）
        
        Args:
            images: 图片信息列表
            asin: 商品 ASIN
            min_size_kb: 最小文件大小（KB），默认100KB
        """
        # 创建图片保存目录
        img_dir = Path(__file__).parent / 'aplus_images' / asin
        img_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded_count = 0
        skipped_small = 0
        
        for idx, img_info in enumerate(images):
            try:
                url = img_info['url']
                
                # 先用HEAD请求获取文件大小，避免下载小图片
                try:
                    head_response = requests.head(url, timeout=5, allow_redirects=True)
                    content_length = head_response.headers.get('Content-Length')
                    
                    if content_length:
                        file_size_bytes = int(content_length)
                        file_size_kb = file_size_bytes / 1024
                        
                        # 过滤小于指定大小的图片
                        if file_size_kb < min_size_kb:
                            skipped_small += 1
                            print(f"    ⏭️  跳过小图片 {idx+1}/{len(images)}: {file_size_kb:.1f}KB < {min_size_kb}KB")
                            continue
                except:
                    # 如果HEAD请求失败，继续尝试下载
                    pass
                
                # 下载图片
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    content = response.content
                    file_size_bytes = len(content)
                    file_size_kb = file_size_bytes / 1024
                    
                    # 再次检查实际下载的文件大小
                    if file_size_kb < min_size_kb:
                        skipped_small += 1
                        print(f"    ⏭️  跳过小图片 {idx+1}/{len(images)}: {file_size_kb:.1f}KB < {min_size_kb}KB")
                        continue
                    
                    # 生成文件名
                    ext = '.jpg'
                    filename = f"aplus_{downloaded_count+1}_{int(file_size_kb)}kb{ext}"
                    filepath = img_dir / filename
                    
                    # 保存图片
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    img_info['local_path'] = str(filepath)
                    img_info['file_size'] = f"{file_size_kb:.1f}KB"
                    downloaded_count += 1
                    print(f"    ✅ 下载图片 {downloaded_count}: {filename} ({file_size_kb:.1f}KB)")
                else:
                    print(f"    ⚠️ 下载失败 {idx+1}/{len(images)}: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"    ⚠️ 下载图片 {idx+1} 失败: {e}")
        
        print(f"\n  📊 下载统计: 成功 {downloaded_count} 张, 跳过小图片 {skipped_small} 张")
        return downloaded_count
    
    def crawl_products_from_list(self, asins: List[str], output_file: str = 'amazon_products.json'):
        """
        批量爬取商品列表
        
        Args:
            asins: ASIN 列表
            output_file: 输出文件路径
        """
        all_products = []
        
        for idx, asin in enumerate(asins, 1):
            print(f"\n{'='*60}")
            print(f"进度: {idx}/{len(asins)}")
            print(f"{'='*60}")
            
            product_data = self.crawl_product(asin)
            if product_data:
                all_products.append(product_data)
            
            # 避免请求过快
            if idx < len(asins):
                time.sleep(2)
        
        # 保存结果
        self._save_results(all_products, output_file)
        
        return all_products
    
    def _save_results(self, products: List[Dict], output_file: str):
        """保存结果到 JSON 文件"""
        try:
            output_path = Path(__file__).parent / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"\n✅ 结果已保存到: {output_path}")
        except Exception as e:
            print(f"\n❌ 保存结果失败: {e}")
    
    def close(self):
        """关闭浏览器"""
        if self.page:
            try:
                self.page.close()
                print("标签页已关闭")
            except:
                print("无需关闭标签页（接管模式）")


# 使用示例
if __name__ == '__main__':
    print("="*60)
    print("Amazon 商品详情爬虫")
    print("="*60)
    
    # 测试 ASIN 列表
    test_asins = [
        'B0DQKSVC1B',  # 示例 ASIN
        # 可以添加更多 ASIN
    ]
    
    # 使用接管模式：连接到已打开的浏览器（端口 9333）
    print("\n【接管模式】连接到已打开的浏览器（端口 9333）...")
    print("提示: 请先运行启动Chrome调试模式.bat")
    print()
    
    crawler = AmazonDetailCrawler(local_port=9333)
    
    try:
        # 批量爬取
        products = crawler.crawl_products_from_list(
            asins=test_asins,
            output_file='amazon_products.json'
        )
        
        print("\n" + "="*60)
        print("爬取完成")
        print("="*60)
        print(f"成功爬取 {len(products)} 个商品")
        
    finally:
        crawler.close()
