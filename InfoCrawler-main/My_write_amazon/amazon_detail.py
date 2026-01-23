"""
Amazon 商品搜索详情一体化爬虫
基于 DrissionPage 库实现
直接通过关键词搜索并爬取商品详情信息
"""
import time
import os
import json
import csv
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions


class AmazonSearchDetailCrawler:
    """Amazon 商品搜索详情一体化爬虫类"""

    def __init__(self, headless: bool = False, use_saved_login: bool = True):
        """
        初始化爬虫

        Args:
            headless: 是否无头模式运行
            use_saved_login: 是否使用保存的登录信息
        """
        self.page = None
        self.headless = headless
        self.use_saved_login = use_saved_login
        self.base_url = "https://www.amazon.com"
        self._init_browser()

    def _init_browser(self):
        """初始化Edge浏览器配置"""
        print("🚀 启动 Microsoft Edge 浏览器...")
        co = ChromiumOptions()

        # Edge浏览器路径
        edge_paths = [
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            os.path.expanduser(r'~\AppData\Local\Microsoft\Edge\Application\msedge.exe'),
        ]

        # 自动查找Edge路径
        edge_found = False
        for path in edge_paths:
            if os.path.exists(path):
                co.set_browser_path(path)
                edge_found = True
                print(f"✅ 找到 Microsoft Edge: {path}")
                break

        if not edge_found:
            print("⚠️ 警告：未找到 Microsoft Edge 浏览器！")
            print("请确保您的Windows系统已安装 Microsoft Edge。")
            input("\n按 Enter 键退出...")
            exit()

        # Edge浏览器配置
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--disable-gpu')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--lang=en-US')

        # Edge用户代理
        co.set_user_agent(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        )

        # 是否使用用户数据目录
        if self.use_saved_login:
            # 使用与该文件同目录下的 edge_browser_data 目录保存 profile
            user_data_dir = os.path.join(os.path.dirname(__file__), 'edge_browser_data')
            # 确保目录存在（会创建目录）
            self._ensure_user_data_dir(user_data_dir)
            co.set_user_data_path(user_data_dir)
            print(f"✅ 使用用户数据目录: {user_data_dir}")

            # 为了手动登录并保留会话，必须以可见模式运行（headless 下无法交互式登录或浏览器可能使用临时profile）
            if self.headless:
                print("⚠️ use_saved_login 已启用，强制关闭 headless 模式以保留登录信息（需要手动登录）")
                self.headless = False

        # 是否无头模式
        if self.headless:
            co.headless()
        else:
            co.headless(False)
            co.set_argument('--start-maximized')

        try:
            # 创建页面
            self.page = ChromiumPage(addr_or_opts=co)

            # 隐藏自动化特征
            try:
                self.page.run_js('''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                ''')
            except Exception:
                pass

            print("✅ Edge浏览器启动成功")

            # 如果启用了保存登录，则检测是否已登录；若未登录，提示手动登录并等待
            if self.use_saved_login:
                # small delay to allow profile to initialize
                time.sleep(1)
                try:
                    self._ensure_logged_in_or_prompt()
                except Exception as e:
                    print(f"⚠️ 登录检查过程出错: {e}")

        except Exception as e:
            print(f"❌ Edge浏览器启动失败: {e}")
            exit()

    def _ensure_user_data_dir(self, path: str):
        """确保用户数据目录存在并可写"""
        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            # 在目录中创建一个占位文件，确保目录是可写的
            test_file = os.path.join(path, '.profile_write_test')
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write('ok')
            try:
                os.remove(test_file)
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ 无法创建用户数据目录 {path}: {e}")

    def _ensure_logged_in_or_prompt(self, timeout: int = 180):
        """
        检查当前 profile 是否已登录 Amazon。\
        若未登录则保持浏览器可见，提示用户手动登录，等待用户完成或自动检测到已登录后继续。
        """
        try:
            print("🔐 检查是否已登录 Amazon...")
            # 打开首页以读取账号信息
            self.page.get(self.base_url)
            time.sleep(2)

            start = time.time()
            prompted = False
            while time.time() - start < timeout:
                # 尝试获取顶部账号元素文本
                acct_elem = None
                try:
                    acct_elem = self.page.ele('#nav-link-accountList-nav-line-1') or self.page.ele('#nav-link-accountList')
                except Exception:
                    acct_elem = None

                text = ''
                try:
                    if acct_elem and acct_elem.text:
                        text = acct_elem.text.strip().lower()
                except Exception:
                    text = ''

                # 如果文本中不包含 sign in 则认为可能已登录（简单判断）
                if acct_elem and text and 'sign' not in text:
                    print(f"✅ 已检测到登录：{acct_elem.text.strip()}")
                    return

                # 未登录
                if not prompted:
                    print("⚠️ 未检测到已登录账户。请在打开的浏览器中手动登录 Amazon。")
                    print("登录完成后，程序会自动检测或按 Enter 跳过等待。")
                    prompted = True

                # 每隔一段时间检查一次
                for _ in range(6):
                    time.sleep(2)
                    try:
                        acct_elem = self.page.ele('#nav-link-accountList-nav-line-1') or self.page.ele('#nav-link-accountList')
                        if acct_elem and acct_elem.text and 'sign' not in acct_elem.text.strip().lower():
                            print(f"✅ 已检测到登录：{acct_elem.text.strip()}")
                            return
                    except Exception:
                        pass

                # 提示用户可立即完成并按 Enter 继续（避免无限等待）
                try:
                    input("如果已完成登录，请按 Enter 继续（或等待自动检测）...")
                except Exception:
                    # 在某些场景 input 可能不可用，继续检测直到超时
                    pass

            print("⚠️ 登录检测超时，继续运行（后续可能会遇到验证或需要登录）。")
        except Exception as e:
            print(f"⚠️ 登录检测过程中出现错误: {e}")

    def search_and_crawl(self, keyword: str, max_products: int = 10, max_pages: int = 1) -> List[Dict]:
        """
        搜索关键词并爬取商品详情

        Args:
            keyword: 搜索关键词
            max_products: 最大爬取商品数量
            max_pages: 最大爬取页数

        Returns:
            商品详情列表
        """
        all_products = []

        try:
            print(f"\n🔍 开始搜索: {keyword}")
            print(f"计划爬取: 最多 {max_products} 个商品，{max_pages} 页")

            # 1. 打开亚马逊并搜索
            self._open_amazon_and_search(keyword)

            # 2. 逐页爬取
            for page_num in range(1, max_pages + 1):
                print(f"\n{'='*60}")
                print(f"正在处理第 {page_num} 页")
                print(f"{'='*60}")

                # 等待搜索结果加载
                self._wait_for_search_results()

                # 获取当前页面的商品链接
                product_links = self._get_product_links_from_page(max_products - len(all_products))

                if not product_links:
                    print("⚠️ 本页没有找到商品")
                    break

                print(f"本页找到 {len(product_links)} 个商品，开始爬取详情...")

                # 3. 爬取每个商品的详情
                for idx, (title, url) in enumerate(product_links, 1):
                    print(f"\n[{idx}/{len(product_links)}] 爬取商品: {title[:50]}...")

                    product_data = self._crawl_product_detail(url, len(all_products) + idx)
                    if product_data:
                        all_products.append(product_data)

                    # 如果已经达到最大数量，停止爬取
                    if len(all_products) >= max_products:
                        print(f"已达到最大爬取数量 {max_products}")
                        break

                    # 避免请求过快
                    if idx < len(product_links):
                        time.sleep(2)

                # 如果已经达到最大数量，停止翻页
                if len(all_products) >= max_products:
                    break

                # 尝试翻到下一页（如果不是最后一页）
                if page_num < max_pages:
                    if not self._go_to_next_page():
                        print("没有下一页了，停止爬取")
                        break
                    time.sleep(2)  # 等待下一页加载

            print(f"\n🎉 爬取完成！共获取 {len(all_products)} 个商品详情")
            return all_products

        except Exception as e:
            print(f"❌ 爬取过程出错: {e}")
            import traceback
            traceback.print_exc()
            return all_products

    def _open_amazon_and_search(self, keyword: str):
        """打开亚马逊并执行搜索"""
        try:
            # 打开亚马逊首页
            print(f"正在打开 {self.base_url} ...")
            self.page.get(self.base_url)
            time.sleep(3)

            # 执行搜索
            print(f"搜索关键词: {keyword}")

            # 查找搜索框
            search_box = self.page.ele('#twotabsearchtextbox', timeout=10)
            if not search_box:
                raise Exception("找不到搜索框")

            # 清空并输入关键词
            search_box.clear()
            search_box.input(keyword)
            time.sleep(1)

            # 查找搜索按钮并点击
            search_btn = self.page.ele('#nav-search-submit-button', timeout=5)
            if search_btn:
                search_btn.click()
            else:
                # 如果没有找到按钮，按回车键
                search_box.input('\n')

            print("✅ 搜索请求已提交")
            time.sleep(3)  # 等待搜索结果加载

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            raise

    def _wait_for_search_results(self, timeout: int = 10):
        """等待搜索结果加载"""
        print("等待搜索结果加载...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            # 尝试多种搜索结果选择器
            result_selectors = [
                'xpath://div[@data-component-type="s-search-result"]',
                'xpath://div[@role="listitem"][@data-asin]',
                'css:div.s-result-item[data-asin]',
                'xpath://div[contains(@class, "s-result-item")]'
            ]

            for selector in result_selectors:
                elements = self.page.eles(selector)
                if elements and len(elements) > 0:
                    print(f"✅ 找到 {len(elements)} 个搜索结果")
                    return

            time.sleep(1)

        print("⚠️ 超时未找到搜索结果")

    def _get_product_links_from_page(self, max_links: int) -> List[tuple]:
        """从当前页面获取商品链接和标题"""
        product_links = []

        try:
            # 查找所有商品元素
            result_selectors = [
                'xpath://div[@data-component-type="s-search-result"]',
                'xpath://div[@role="listitem"][@data-asin]',
                'css:div.s-result-item[data-asin]'
            ]

            product_elements = None
            for selector in result_selectors:
                elements = self.page.eles(selector)
                if elements:
                    product_elements = elements
                    break

            if not product_elements:
                return product_links

            # 提取商品链接和标题
            for element in product_elements:
                if len(product_links) >= max_links:
                    break

                try:
                    # 提取商品标题
                    title_elem = element.ele('xpath:.//h2//span')
                    if title_elem:
                        title = title_elem.text.strip()
                        if not title:
                            continue
                    else:
                        continue

                    # 提取商品链接
                    link_elem = element.ele('xpath:.//a[contains(@href, "/dp/")]')
                    if not link_elem:
                        link_elem = element.ele('xpath:.//a[contains(@href, "/gp/")]')

                    if link_elem:
                        href = link_elem.attr('href') or ''
                        if href:
                            # 确保是完整URL
                            if href.startswith('/'):
                                url = urljoin(self.base_url, href)
                            elif href.startswith('http'):
                                url = href
                            else:
                                url = urljoin(self.base_url, '/' + href.lstrip('/'))

                            # 添加到列表
                            product_links.append((title, url))

                except Exception as e:
                    print(f"提取商品链接失败: {e}")
                    continue

            return product_links

        except Exception as e:
            print(f"获取商品链接失败: {e}")
            return product_links

    def _crawl_product_detail(self, url: str, index: int) -> Optional[Dict]:
        """爬取单个商品详情"""
        product_data = {
            'index': index,
            'url': url,
            'title': None,
            'bullet_points': [],
            'price': None,
            'product_details': {},
            'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            print(f"  正在访问商品页面...")
            self.page.get(url)
            time.sleep(3)  # 等待页面加载

            # 检查是否404或找不到页面
            page_text = self.page.html.lower()
            if 'page not found' in page_text or 'we couldn\'t find that page' in page_text:
                print(f"  ⚠️ 页面不存在或已被移除")
                return product_data

            # 提取标题
            product_data['title'] = self._extract_title()

            # 提取五点描述
            product_data['bullet_points'] = self._extract_bullet_points()

            # 提取价格
            product_data['price'] = self._extract_price()

            # 提取商品属性
            product_data['product_details'] = self._extract_product_details()

            print(f"  ✅ 商品详情爬取成功")
            return product_data

        except Exception as e:
            print(f"  ❌ 爬取商品详情失败: {e}")
            return product_data

    def _extract_title(self) -> Optional[str]:
        """提取商品标题"""
        try:
            # 尝试多个标题选择器
            title_selectors = [
                'xpath://span[@id="productTitle"]',
                'xpath://h1[@id="title"]//span',
                'xpath://h1[contains(@class, "product-title")]',
            ]

            for selector in title_selectors:
                title_element = self.page.ele(selector, timeout=3)
                if title_element and title_element.text:
                    title = title_element.text.strip()
                    print(f"    标题: {title[:60]}...")
                    return title
        except:
            pass

        print("    ⚠️ 提取标题失败")
        return None

    def _extract_bullet_points(self) -> List[str]:
        """提取五点描述"""
        bullet_points = []
        try:
            # 尝试多个五点描述选择器
            bullet_selectors = [
                'xpath://div[@id="feature-bullets"]',
                'xpath://div[@id="detailBullets_feature_div"]',
                'xpath://ul[contains(@class, "a-unordered-list") and contains(@class, "a-vertical")]',
            ]

            for selector in bullet_selectors:
                bullets_container = self.page.ele(selector, timeout=3)
                if bullets_container:
                    # 查找所有 li 元素
                    li_elements = bullets_container.eles('tag:li')
                    for li in li_elements:
                        text = li.text.strip()
                        # 过滤掉空文本和无关内容
                        if text and len(text) > 5 and 'see more' not in text.lower():
                            bullet_points.append(text)
                    break

            print(f"    五点描述: 共 {len(bullet_points)} 条")
        except Exception as e:
            print(f"    ⚠️ 提取五点描述失败: {e}")
        return bullet_points

    def _extract_price(self) -> Optional[str]:
        """提取价格信息"""
        try:
            # 价格选择器
            price_selectors = [
                'xpath://span[@class="a-price"]//span[@class="a-offscreen"]',
                'xpath://span[contains(@class, "a-price-whole")]',
                'xpath://span[contains(@class, "a-price")]//span[@aria-hidden="true"]'
            ]

            # 货币符号
            currency_symbols = ['$', '¥', '€', '£']

            for selector in price_selectors:
                price_elements = self.page.eles(selector)
                if price_elements:
                    for price_element in price_elements:
                        price_text = price_element.text.strip()
                        if price_text and any(symbol in price_text for symbol in currency_symbols):
                            print(f"    价格: {price_text}")
                            return price_text

            print("    ⚠️ 未找到价格信息")
            return None

        except Exception as e:
            print(f"    ⚠️ 提取价格失败: {e}")
            return None

    def _extract_product_details(self) -> Dict[str, str]:
        """提取商品属性表"""
        details = {}

        try:
            # 查找详情表
            detail_selectors = [
                'xpath://table[@id="productDetails_techSpec_section_1"]',
                'xpath://table[@id="productDetails_detailBullets_sections1"]',
                'xpath://table[contains(@class, "prodDetTable")]',
            ]

            for selector in detail_selectors:
                table = self.page.ele(selector, timeout=3)
                if table:
                    rows = table.eles('tag:tr')
                    for row in rows:
                        try:
                            th = row.ele('tag:th')
                            td = row.ele('tag:td')

                            if th and td:
                                key = th.text.strip().rstrip(':')
                                value = td.text.strip()

                                if key and value:
                                    details[key] = value
                        except:
                            continue
                    break

            print(f"    商品属性: 共 {len(details)} 项")

        except Exception as e:
            print(f"    ⚠️ 提取商品详情失败: {e}")

        return details

    def _go_to_next_page(self) -> bool:
        """翻到下一页"""
        try:
            # 查找下一页按钮
            next_btn = self.page.ele('css:a.s-pagination-next', timeout=5)

            if next_btn and 's-pagination-disabled' not in (next_btn.attr('class') or ''):
                next_btn.click()
                print("✅ 已翻页，等待新页面加载...")
                time.sleep(3)  # 等待新页面加载
                return True
            else:
                print("⚠️ 下一页按钮不可用或已禁用")
                return False

        except Exception as e:
            print(f"❌ 翻页失败: {e}")
            return False

    def save_results(self, products: List[Dict], filename: str = None):
        """
        保存爬取结果

        Args:
            products: 商品列表
            filename: 保存文件名（可选）
        """
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"amazon_search_details_{timestamp}.json"

        try:
            # 准备保存的数据
            data_to_save = {
                'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_products': len(products),
                'products': products
            }

            # 确保目录存在
            output_path = Path(__file__).parent / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存为JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            print(f"✅ JSON结果已保存到: {output_path}")

            # 同时保存为CSV便于查看
            csv_filename = str(output_path).replace('.json', '.csv')
            self._save_to_csv(products, csv_filename)

        except Exception as e:
            print(f"❌ 保存文件时出错: {e}")

    def _save_to_csv(self, products: List[Dict], filename: str):
        """保存为CSV文件"""
        try:
            # 定义CSV列
            fieldnames = [
                'index', 'title', 'price', 'url',
                'bullet_points', 'product_details'
            ]

            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for product in products:
                    # 处理bullet_points列表
                    bullet_points_str = ''
                    if 'bullet_points' in product and isinstance(product['bullet_points'], list):
                        bullet_points_str = ' | '.join(product['bullet_points'])

                    # 处理product_details字典
                    details_str = ''
                    if 'product_details' in product and isinstance(product['product_details'], dict):
                        details_str = ' | '.join(f'{k}: {v}' for k, v in product['product_details'].items())

                    # 只写入需要的列
                    row = {
                        'index': product.get('index', ''),
                        'title': product.get('title', '')[:200],  # 限制标题长度
                        'price': product.get('price', ''),
                        'url': product.get('url', ''),
                        'bullet_points': bullet_points_str[:500],  # 限制长度
                        'product_details': details_str[:500]  # 限制长度
                    }
                    writer.writerow(row)

            print(f"✅ CSV文件已保存: {filename}")

        except Exception as e:
            print(f"❌ 保存CSV时出错: {e}")

    def close(self):
        """关闭浏览器"""
        if self.page:
            try:
                self.page.quit()
                print("✅ Edge浏览器已关闭")
            except:
                pass


def main():
    """主函数"""
    print("=" * 60)
    print("Amazon 商品搜索详情一体化爬虫")
    print("=" * 60)
    print("说明：输入关键词直接搜索并爬取商品详情")
    print("=" * 60)

    try:
        # 创建爬虫实例
        print("\n正在初始化爬虫...")
        crawler = AmazonSearchDetailCrawler(
            headless=False,  # 显示浏览器窗口
            use_saved_login=True
        )

        # 输入搜索关键词
        print("\n请输入搜索关键词:")
        keyword = input("关键词: ").strip()

        if not keyword:
            keyword = "laptop"  # 默认关键词
            print(f"使用默认关键词: {keyword}")

        # 输入最大商品数量
        print("\n请输入最大爬取商品数量 (建议10-20):")
        try:
            max_products = int(input("数量: ").strip() or "10")
            if max_products < 1:
                max_products = 10
        except:
            max_products = 10
            print(f"使用默认数量: {max_products}")

        # 输入最大页数
        print("\n请输入最大爬取页数 (建议1-2):")
        try:
            max_pages = int(input("页数: ").strip() or "1")
            if max_pages < 1:
                max_pages = 1
        except:
            max_pages = 1
            print(f"使用默认页数: {max_pages}")

        # 开始爬取
        print(f"\n开始搜索并爬取: '{keyword}' ...")
        print("请等待，不要操作浏览器窗口...")

        products = crawler.search_and_crawl(
            keyword=keyword,
            max_products=max_products,
            max_pages=max_pages
        )

        # 保存结果
        if products:
            # 自动生成文件名
            safe_keyword = re.sub(r'[^\w\s-]', '', keyword)[:20]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"amazon_{safe_keyword}_{timestamp}.json"

            crawler.save_results(products, filename)

            # 显示摘要信息
            print(f"\n📊 爬取摘要:")
            print(f"   关键词: {keyword}")
            print(f"   商品数量: {len(products)}")
            print(f"   输出文件: {filename}")
            print(f"   同时生成: {filename.replace('.json', '.csv')}")

            # 显示前几个商品的信息
            if products:
                print(f"\n📦 前3个商品信息:")
                for i, product in enumerate(products[:3], 1):
                    title = product.get('title', '无标题')[:50]
                    price = product.get('price', 'N/A')
                    bullets_count = len(product.get('bullet_points', []))
                    details_count = len(product.get('product_details', {}))
                    print(f"   {i}. {title}")
                    print(f"      价格: {price} | 五点描述: {bullets_count}条 | 属性: {details_count}项")
        else:
            print("⚠️ 未找到任何商品")

    except KeyboardInterrupt:
        print("\n⏹️ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保关闭浏览器（仅在 crawler 已成功创建时调用）
        try:
            if 'crawler' in locals() and locals().get('crawler'):
                locals().get('crawler').close()
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("程序执行完毕")
    print("=" * 60)
    input("按 Enter 键退出...")


if __name__ == '__main__':
    main()