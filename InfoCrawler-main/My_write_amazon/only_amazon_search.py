import re
import time
import json
import csv
from typing import List, Dict, Optional
from urllib.parse import urljoin
import os
from DrissionPage import ChromiumPage, ChromiumOptions


class AmazonCrawler:
    """亚马逊商品搜索爬虫（精简版）"""

    def __init__(self, headless: bool = False, use_saved_login: bool = True,
                 browser_type: str = 'edge'):
        """
        初始化爬虫

        Args:
            headless: 是否无头模式
            use_saved_login: 是否使用已保存的登录状态
            browser_type: 浏览器类型 ('edge' 或 'chrome')
        """
        self.page = None
        self.headless = headless
        self.use_saved_login = use_saved_login
        self.browser_type = browser_type.lower()
        self.base_url = "https://www.amazon.com"

        # 亚马逊专用选择器配置
        self.search_config = {
            'home_url': self.base_url,
            'search_box_selector': '#twotabsearchtextbox',
            'search_btn_selector': '#nav-search-submit-button',
            'result_selectors': [
                'xpath://div[@data-component-type="s-search-result"]',
                'xpath://div[@role="listitem"][@data-asin]',
                'css:div.s-result-item[data-asin]'
            ]
        }

        self._init_browser()

    def _init_browser(self):
        """初始化浏览器配置"""
        print(f"🚀 启动 {'Microsoft Edge' if self.browser_type == 'edge' else 'Google Chrome'} 浏览器...")
        co = ChromiumOptions()

        # 设置浏览器路径
        if self.browser_type == 'edge':
            edge_paths = [
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                os.path.expanduser(r'~\AppData\Local\Microsoft\Edge\Application\msedge.exe'),
            ]

            for path in edge_paths:
                if os.path.exists(path):
                    co.set_browser_path(path)
                    print(f"✅ 使用 Microsoft Edge: {path}")
                    break
            else:
                print("⚠️ 未找到 Edge 浏览器，将尝试系统默认浏览器")
        else:
            chrome_paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                os.path.expanduser(r'~\AppData\Local\Google\Chrome\Application\chrome.exe'),
            ]

            for path in chrome_paths:
                if os.path.exists(path):
                    co.set_browser_path(path)
                    print(f"✅ 使用 Google Chrome: {path}")
                    break
            else:
                print("⚠️ 未找到 Chrome 浏览器，将尝试系统默认浏览器")

        # 浏览器选项
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--disable-gpu')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')

        if self.browser_type == 'edge':
            co.set_argument('--lang=zh-CN')
            co.set_user_agent(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
            )
        else:
            co.set_user_agent(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

        # 用户数据目录
        if self.use_saved_login:
            user_data_dir = os.path.join(os.path.dirname(__file__), 'amazon_browser_data')
            # 确保目录存在并可写
            self._ensure_user_data_dir(user_data_dir)
            co.set_user_data_path(user_data_dir)
            print(f"✅ 使用用户数据目录: {user_data_dir}")

            # 保存登录时需要可见模式以便手动登录并保存会话
            if self.headless:
                print("⚠️ use_saved_login 已启用，强制关闭 headless 模式以保留登录信息（需要手动登录）")
                self.headless = False

        # 是否无头模式
        if self.headless:
            co.headless()
        else:
            co.headless(False)
            co.set_argument('--start-maximized')

        # 创建页面
        try:
            self.page = ChromiumPage(addr_or_opts=co)

            # 隐藏自动化特征（容错）
            try:
                self.page.run_js('''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                ''')
            except Exception:
                pass

            print("✅ 浏览器启动成功")

            # 如果启用保存登录，启动后检查是否已登录 Amazon，否则提示手动登录
            if self.use_saved_login:
                time.sleep(1)
                try:
                    self._ensure_logged_in_or_prompt()
                except Exception as e:
                    print(f"⚠️ 登录检测过程出错: {e}")

        except Exception as e:
            print(f"❌ 启动浏览器失败: {e}")
            raise

    def search_products(self, keyword: str, max_pages: int = 3) -> List[Dict]:
        """
        搜索亚马逊商品

        Args:
            keyword: 搜索关键词
            max_pages: 最大爬取页数

        Returns:
            商品信息列表
        """
        all_products = []

        try:
            # 打开亚马逊首页
            print(f"正在打开 {self.base_url} ...")
            self.page.get(self.base_url)
            time.sleep(2)

            # 执行搜索
            self._perform_search(keyword)

            # 逐页爬取
            for page_num in range(1, max_pages + 1):
                print(f"\n{'=' * 50}")
                print(f"正在爬取第 {page_num} 页...")
                print(f"{'=' * 50}")

                # 等待商品加载
                self._wait_for_products()

                # 提取商品信息
                products = self._extract_products()
                all_products.extend(products)
                print(f"✅ 第 {page_num} 页提取到 {len(products)} 个商品")

                # 如果不是最后一页，尝试翻页
                if page_num < max_pages:
                    if not self._go_next_page():
                        print("⚠️ 没有下一页了，停止爬取")
                        break

            print(f"\n🎉 爬取完成！共获取 {len(all_products)} 个商品数据")
            return all_products

        except Exception as e:
            print(f"❌ 爬取过程出错: {e}")
            return all_products

    def _perform_search(self, keyword: str):
        """执行搜索"""
        try:
            print(f"搜索关键词: {keyword}")

            # 查找搜索框
            search_box = self.page.ele(self.search_config['search_box_selector'], timeout=10)
            if not search_box:
                raise Exception("找不到搜索框")

            # 清空并输入关键词
            search_box.clear()
            search_box.input(keyword)
            time.sleep(1)

            # 查找搜索按钮并点击
            search_btn = self.page.ele(self.search_config['search_btn_selector'], timeout=5)
            if search_btn:
                search_btn.click()
            else:
                # 如果没有找到按钮，按回车键
                search_box.input('\n')

            print("✅ 搜索请求已提交")
            time.sleep(3)

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            raise

    def _wait_for_products(self, timeout: int = 10):
        """等待商品加载"""
        print("等待商品加载...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            for selector in self.search_config['result_selectors']:
                try:
                    elements = self.page.eles(selector)
                    if elements and len(elements) > 0:
                        print(f"✅ 找到 {len(elements)} 个商品")
                        return
                except:
                    continue
            time.sleep(1)

        print("⚠️ 超时未找到商品")

    def _extract_products(self) -> List[Dict]:
        """提取商品信息"""
        products = []

        try:
            # 查找所有商品元素
            for selector in self.search_config['result_selectors']:
                elements = self.page.eles(selector)
                if elements:
                    product_elements = elements
                    break
            else:
                print("⚠️ 未找到商品元素")
                return products

            print(f"开始提取 {len(product_elements)} 个商品信息...")

            for idx, element in enumerate(product_elements, 1):
                try:
                    product_data = self._extract_single_product(element, idx)
                    if product_data:
                        products.append(product_data)

                        # 显示进度
                        if idx % 10 == 0:
                            print(f"  已处理 {idx}/{len(product_elements)} 个商品")

                except Exception as e:
                    print(f"⚠️ 提取商品 {idx} 时出错: {e}")
                    continue

            return products

        except Exception as e:
            print(f"❌ 提取商品列表失败: {e}")
            return products

    def _extract_single_product(self, element, index: int) -> Optional[Dict]:
        """提取单个商品信息"""
        try:
            product = {'index': index}

            # 1. ASIN (Amazon商品ID)
            asin = element.attr('data-asin')
            if not asin:
                # 尝试从链接中提取ASIN
                link_elem = element.ele('xpath:.//a[contains(@href, "/dp/")]')
                if link_elem:
                    href = link_elem.attr('href') or ''
                    # 从URL中提取ASIN
                    match = re.search(r'/dp/([A-Z0-9]{10})', href)
                    if match:
                        asin = match.group(1)

            product['asin'] = asin or ''

            # 2. 商品标题
            title_elem = element.ele('xpath:.//h2//span')
            if title_elem:
                product['title'] = self._clean_text(title_elem.text or '')
            else:
                product['title'] = ''

            # 3. 价格信息
            price_data = self._extract_price(element)
            product.update(price_data)

            # 4. 商品链接
            link = self._extract_link(element)
            product['url'] = link

            # 5. 商品简介/描述
            description = self._extract_description(element)
            product['description'] = description

            # 6. 评分和评论数（可选）
            rating_info = self._extract_rating(element)
            product.update(rating_info)

            # 清理空值
            product = {k: v for k, v in product.items() if v not in [None, '', []]}

            return product

        except Exception as e:
            print(f"提取商品信息失败: {e}")
            return None

    def _extract_price(self, element) -> Dict:
        """提取价格信息"""
        price_info = {
            'price': '',
            'original_price': '',
            'discount_price': '',
            'currency': 'USD'
        }

        try:
            # 查找所有价格元素
            price_elements = element.eles('xpath:.//span[@class="a-price"]//span[@class="a-offscreen"]')

            if price_elements:
                # 第一个价格通常是当前价格
                if len(price_elements) >= 1:
                    price_text = price_elements[0].text or ''
                    price_info['price'] = self._clean_price(price_text)

                # 第二个价格可能是原价（折扣情况）
                if len(price_elements) >= 2:
                    original_text = price_elements[1].text or ''
                    price_info['original_price'] = self._clean_price(original_text)

                    # 如果有原价，当前价格就是折扣价
                    if price_info['original_price']:
                        price_info['discount_price'] = price_info['price']

            # 如果没有找到，尝试其他选择器
            if not price_info['price']:
                whole_price = element.ele('xpath:.//span[@class="a-price-whole"]')
                if whole_price:
                    price_info['price'] = whole_price.text or ''

            return price_info

        except Exception as e:
            print(f"提取价格失败: {e}")
            return price_info

    def _extract_link(self, element) -> str:
        """提取商品链接"""
        try:
            link_elem = element.ele('xpath:.//a[contains(@href, "/dp/") or contains(@href, "/gp/")]')
            if link_elem:
                href = link_elem.attr('href') or ''
                if href:
                    # 确保是完整URL
                    if href.startswith('/'):
                        return urljoin(self.base_url, href)
                    elif href.startswith('http'):
                        return href
                    else:
                        return urljoin(self.base_url, '/' + href.lstrip('/'))
            return ''
        except:
            return ''

    def _extract_description(self, element) -> str:
        """提取商品简介"""
        try:
            # 尝试多个描述选择器
            selectors = [
                'xpath:.//span[contains(@class, "a-color-secondary")]',
                'xpath:.//div[contains(@class, "a-section")]//span',
                'xpath:.//div[contains(@class, "a-row")]//span'
            ]

            for selector in selectors:
                desc_elem = element.ele(selector)
                if desc_elem:
                    text = desc_elem.text or ''
                    if text and len(text.strip()) > 10:
                        return self._clean_text(text)[:200]  # 限制长度

            return ''
        except:
            return ''

    def _extract_rating(self, element) -> Dict:
        """提取评分信息"""
        rating_info = {
            'rating': '',
            'review_count': ''
        }

        try:
            # 提取评分
            rating_elem = element.ele('xpath:.//span[@class="a-icon-alt"]')
            if rating_elem:
                rating_text = rating_elem.text or ''
                # 提取数字评分，如 "4.5 out of 5 stars"
                match = re.search(r'([\d.]+) out of 5', rating_text)
                if match:
                    rating_info['rating'] = match.group(1)

            # 提取评论数
            review_elem = element.ele('xpath:.//span[contains(@class, "a-size-base")]')
            if review_elem:
                review_text = review_elem.text or ''
                # 提取数字
                numbers = re.findall(r'\d+', review_text.replace(',', ''))
                if numbers:
                    rating_info['review_count'] = numbers[0]

            return rating_info
        except:
            return rating_info

    def _clean_price(self, price_text: str) -> str:
        """清理价格文本"""
        if not price_text:
            return ''

        # 移除货币符号和空格
        cleaned = re.sub(r'[^\d.,]', '', price_text)
        return cleaned.strip()

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""

        # 移除多余空格和换行
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # 移除控制字符
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        return text

    def _go_next_page(self) -> bool:
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
            filename = f"amazon_products_{timestamp}.json"

        # 准备保存的数据
        data_to_save = {
            'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_products': len(products),
            'products': products
        }

        # 保存为JSON
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            print(f"✅ 结果已保存到: {filename}")

            # 同时保存为CSV便于查看
            csv_filename = filename.replace('.json', '.csv')
            self._save_to_csv(products, csv_filename)

        except Exception as e:
            print(f"❌ 保存文件时出错: {e}")

    def _save_to_csv(self, products: List[Dict], filename: str):
        """保存为CSV文件"""
        try:
            # 定义CSV列
            fieldnames = [
                'index', 'asin', 'title', 'price', 'original_price',
                'discount_price', 'rating', 'review_count', 'url'
            ]

            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for product in products:
                    # 只写入需要的列
                    row = {
                        'index': product.get('index', ''),
                        'asin': product.get('asin', ''),
                        'title': product.get('title', '')[:100],  # 限制标题长度
                        'price': product.get('price', ''),
                        'original_price': product.get('original_price', ''),
                        'discount_price': product.get('discount_price', ''),
                        'rating': product.get('rating', ''),
                        'review_count': product.get('review_count', ''),
                        'url': product.get('url', '')
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
                print("✅ 浏览器已关闭")
            except:
                pass

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

                # 简单判断：如果文本中没有 'sign'，则视为已登录
                if acct_elem and text and 'sign' not in text:
                    print(f"✅ 已检测到登录：{acct_elem.text.strip()}")
                    return

                if not prompted:
                    print("⚠️ 未检测到已登录账户。请在打开的浏览器中手动登录 Amazon。")
                    print("登录完成后，程序会自动检测或按 Enter 跳过等待。")
                    prompted = True

                # 每隔几秒检查一次
                for _ in range(6):
                    time.sleep(2)
                    try:
                        acct_elem = self.page.ele('#nav-link-accountList-nav-line-1') or self.page.ele('#nav-link-accountList')
                        if acct_elem and acct_elem.text and 'sign' not in acct_elem.text.strip().lower():
                            print(f"✅ 已检测到登录：{acct_elem.text.strip()}")
                            return
                    except Exception:
                        pass

                try:
                    input("如果已完成登录，请按 Enter 继续（或等待自动检测）...")
                except Exception:
                    # 在某些场景 input 可能不可用，继续检测直到超时
                    pass

            print("⚠️ 登录检测超时，继续运行（后续可能会遇到验证或需要登录）。")
        except Exception as e:
            print(f"⚠️ 登录检测过程中出现错误: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("亚马逊商品搜索爬虫")
    print("=" * 60)

    try:
        # 用户选择浏览器
        print("\n请选择浏览器:")
        print("1. Microsoft Edge (默认)")
        print("2. Google Chrome")

        browser_choice = input("请输入数字 (1或2): ").strip()
        browser_type = 'chrome' if browser_choice == '2' else 'edge'

        # 创建爬虫实例
        crawler = AmazonCrawler(
            headless=False,  # 显示浏览器窗口
            use_saved_login=True,  # 使用保存的登录状态
            browser_type=browser_type
        )

        # 输入搜索关键词
        print("\n请输入要搜索的商品关键词:")
        keyword = input("关键词: ").strip()

        if not keyword:
            keyword = "laptop"  # 默认关键词
            print(f"使用默认关键词: {keyword}")

        # 输入爬取页数
        print("\n请输入要爬取的页数 (建议1-3页):")
        try:
            max_pages = int(input("页数: ").strip() or "1")
        except:
            max_pages = 1
            print(f"使用默认页数: {max_pages}")

        # 开始爬取
        print(f"\n开始爬取亚马逊 '{keyword}' ...")
        print("请等待浏览器加载...")

        products = crawler.search_products(keyword, max_pages=max_pages)

        # 保存结果
        if products:
            crawler.save_results(products)

            # 显示摘要信息
            print(f"\n📊 爬取摘要:")
            print(f"   关键词: {keyword}")
            print(f"   商品数量: {len(products)}")
            print(f"   文件格式: JSON和CSV")

            # 显示前几个商品
            print(f"\n📦 前5个商品:")
            for i, product in enumerate(products[:5], 1):
                title = product.get('title', '无标题')[:50]
                price = product.get('price', '无价格')
                rating = product.get('rating', '无评分')
                print(f"   {i}. {title}")
                print(f"      价格: ${price} | 评分: {rating}/5")
        else:
            print("⚠️ 未找到任何商品")

    except KeyboardInterrupt:
        print("\n⏹️ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保关闭浏览器
        try:
            if 'crawler' in locals() and locals().get('crawler'):
                locals().get('crawler').close()
        except:
            pass

    print("\n" + "=" * 60)
    print("程序执行完毕")
    print("=" * 60)
    input("按 Enter 键退出...")


if __name__ == '__main__':
    main()