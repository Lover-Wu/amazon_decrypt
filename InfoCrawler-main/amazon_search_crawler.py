import re
import time
import json
import csv
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
import os
from DrissionPage import ChromiumPage, ChromiumOptions


class EnhancedAmazonSearchCrawler:
    """Amazon 搜索结果爬虫类（增强版）"""

    def __init__(self, headless: bool = False, use_saved_login: bool = True,
                 local_port: int = None, browser_type: str = 'edge'):
        """
        初始化爬虫
        """
        self.page = None
        self.headless = headless
        self.use_saved_login = use_saved_login
        self.local_port = local_port
        self.browser_type = browser_type.lower()
        self.base_url = "https://www.amazon.com"
        # search_config holds per-site selectors and home URL; can be changed at runtime
        self.search_config = {
            'home_url': self.base_url,
            'search_box_selector': '#twotabsearchtextbox',
            'search_btn_selector': '#nav-search-submit-button',
            'result_selectors': [
                'xpath://div[@role="listitem"][@data-asin]',
                'xpath://div[@data-component-type="s-search-result"]',
                'css:div.s-result-item[data-asin]'
            ]
        }
        self._init_browser()

    def _init_browser(self):
        """初始化浏览器配置"""
        if self.local_port:
            print(f"正在接管浏览器（端口: {self.local_port}）...")
            try:
                co = ChromiumOptions()
                co.set_local_port(self.local_port)

                if self.browser_type == 'edge':
                    edge_paths = [
                        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                    ]
                    for path in edge_paths:
                        if os.path.exists(path):
                            co.set_browser_path(path)
                            print(f"✅ 指定 Edge 路径: {path}")
                            break

                if not self.headless:
                    co.headless(False)

                self.page = ChromiumPage(co)
                print("✅ 已接管浏览器")
                return

            except Exception as e:
                print(f"❌ 接管失败: {e}")
                print("🔄 将自动启动新浏览器...")

        print(f"🚀 自动启动 {'Microsoft Edge' if self.browser_type == 'edge' else 'Chrome'} 浏览器...")
        co = ChromiumOptions()

        if self.browser_type == 'edge':
            edge_paths = [
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            ]
            edge_found = False
            for path in edge_paths:
                if os.path.exists(path):
                    co.set_browser_path(path)
                    print(f"✅ 使用 Microsoft Edge: {path}")
                    edge_found = True
                    break
            if not edge_found:
                print("⚠️ 未找到 Edge，使用系统默认浏览器")
        else:
            chrome_paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            ]
            chrome_found = False
            for path in chrome_paths:
                if os.path.exists(path):
                    co.set_browser_path(path)
                    print(f"✅ 使用 Google Chrome: {path}")
                    chrome_found = True
                    break
            if not chrome_found:
                print("⚠️ 未找到 Chrome，使用系统默认浏览器")

        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--disable-gpu')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')

        if self.browser_type == 'edge':
            co.set_argument('--disable-features=EdgeTranslate')
            co.set_argument('--disable-component-update')
            co.set_argument('--lang=zh-CN')
            co.set_user_agent(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
            )

        if self.use_saved_login:
            if self.browser_type == 'edge':
                user_data_dir = os.path.join(os.path.dirname(__file__), 'edge_browser_data')
            else:
                user_data_dir = os.path.join(os.path.dirname(__file__), 'browser_data')
            co.set_user_data_path(user_data_dir)
            print(f"✅ 使用用户数据目录: {user_data_dir}")

        if self.headless:
            co.headless()
        else:
            co.headless(False)
            co.set_argument('--start-maximized')

        self.page = ChromiumPage(addr_or_opts=co)
        self.page.run_js('''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        ''')
        print(f"✅ 浏览器启动成功")

    def check_captcha(self) -> bool:
        """
        检查是否出现验证码
        """
        captcha_indicators = [
            'captcha',
            'robot check',
            'enter the characters',
            'type the characters',
            'solve this puzzle'
        ]

        page_text = self.page.html.lower()
        for indicator in captcha_indicators:
            if indicator in page_text:
                print("⚠️ 检测到验证码！程序暂停，请人工处理...")
                print("处理完成后按 Enter 继续...")
                input()
                return True
        return False

    def search_products(self, keyword: str, max_pages: int = 5, detailed_extraction: bool = True) -> List[Dict]:
        """
        搜索商品并爬取结果（优化：减少不必要的 sleep，使用显式等待）
        此函数已被包装为调用 _search_products_impl；保留为空以兼容旧调用。
        """
        return self._search_products_impl(keyword, max_pages=max_pages, detailed_extraction=detailed_extraction)

    def _search_products_impl(self, keyword: str, max_pages: int = 5, detailed_extraction: bool = True) -> List[Dict]:
        """
        统一的搜索实现（原 search_products 的优化版本），现在被 wrapper 调用。
        """
        all_products = []
        try:
            print(f"正在打开 {self.search_config.get('home_url', self.base_url)} ...")
            self.page.get(self.search_config.get('home_url', self.base_url))
            # 短等待页面加载必要节点
            try:
                # 尝试使用配置的按钮选择器短等待
                self.page.ele(self.search_config.get('search_btn_selector', ''), timeout=4)
            except:
                pass

            # 一次性检查验证码
            if self.check_captcha():
                time.sleep(1)

            self._perform_search(keyword)

            for page_num in range(1, max_pages + 1):
                print(f"\n{'=' * 60}")
                print(f"正在爬取第 {page_num} 页...")
                print(f"{'=' * 60}")

                # 提取商品
                products = self._extract_products_enhanced(detailed_mode=detailed_extraction)
                all_products.extend(products)
                print(f"第 {page_num} 页提取到 {len(products)} 个商品")

                if page_num < max_pages:
                    if not self._go_next_page():
                        print("没有下一页了，停止爬取")
                        break
                    # 页面跳转后进行小等待并检测是否出现产品列表
                    for _ in range(8):  # 最多约4s
                        # 使用配置的 result_selectors
                        found = False
                        for sel in self.search_config.get('result_selectors', []):
                            try:
                                if sel.startswith('xpath:'):
                                    if self.page.eles(sel):
                                        found = True
                                        break
                                else:
                                    if self.page.eles(sel):
                                        found = True
                                        break
                            except:
                                continue
                        if found:
                            break
                        time.sleep(0.5)

            print(f"\n✅ 爬取完成！共获取 {len(all_products)} 个商品数据")
            return all_products

        except Exception as e:
            print(f"❌ 爬取过程出错: {e}")
            return all_products

    def _perform_search(self, keyword: str):
        """
        执行搜索操作（使用 self.search_config 中的选择器，使得可支持不同网站）
        """
        try:
            search_box_selector = self.search_config.get('search_box_selector')
            search_btn_selector = self.search_config.get('search_btn_selector')

            print(f"搜索关键词: {keyword}")

            search_box = None
            if search_box_selector:
                try:
                    search_box = self.page.ele(search_box_selector, timeout=5)
                except Exception:
                    search_box = None

            # 如果没有找到搜索框，尝试在页面直接通过 JS 设置搜索参数或 raise
            if search_box:
                try:
                    search_box.clear()
                    search_box.input(keyword)
                except Exception:
                    try:
                        # 作为回退，直接输入回车
                        search_box.input('\n')
                    except:
                        pass

            # 尝试点击或回车提交（优先使用配置的按钮选择器）
            if search_btn_selector:
                try:
                    search_btn = self.page.ele(search_btn_selector, timeout=2)
                except Exception:
                    search_btn = None
            else:
                search_btn = None

            if search_btn:
                try:
                    search_btn.click()
                except Exception:
                    # 回退到输入回车
                    try:
                        if search_box:
                            search_box.input('\n')
                    except:
                        pass
            else:
                # 如果没有按钮，则尝试按回车提交（若找到了输入框）
                if search_box:
                    try:
                        search_box.input('\n')
                    except:
                        pass

            # 等待搜索结果主要容器出现（短超时）
            selectors = self.search_config.get('result_selectors', [])
            found = False
            for _ in range(10):  # 最多等待约 5s
                for sel in selectors:
                    try:
                        eles = self.page.eles(sel)
                    except Exception:
                        eles = []
                    if eles:
                        found = True
                        break
                if found:
                    break
                time.sleep(0.5)

            if not found:
                print("⚠️ 搜索提交后未在短时间内检测到结果，可能加载较慢或选择器不匹配")

            print("搜索请求已提交")

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            raise

    def _search_products_impl(self, keyword: str, max_pages: int = 5, detailed_extraction: bool = True) -> List[Dict]:
        """
        统一的搜索实现（原 search_products 的优化版本），现在被 wrapper 调用。
        """
        all_products = []
        try:
            print(f"正在打开 {self.search_config.get('home_url', self.base_url)} ...")
            self.page.get(self.search_config.get('home_url', self.base_url))
            # 短等待页面加载必要节点
            try:
                # 尝试使用配置的按钮选择器短等待
                self.page.ele(self.search_config.get('search_btn_selector', ''), timeout=4)
            except:
                pass

            # 一次性检查验证码
            if self.check_captcha():
                time.sleep(1)

            self._perform_search(keyword)

            for page_num in range(1, max_pages + 1):
                print(f"\n{'=' * 60}")
                print(f"正在爬取第 {page_num} 页...")
                print(f"{'=' * 60}")

                # 提取商品
                products = self._extract_products_enhanced(detailed_mode=detailed_extraction)
                all_products.extend(products)
                print(f"第 {page_num} 页提取到 {len(products)} 个商品")

                if page_num < max_pages:
                    if not self._go_next_page():
                        print("没有下一页了，停止爬取")
                        break
                    # 页面跳转后进行小等待并检测是否出现产品列表
                    for _ in range(8):  # 最多约4s
                        # 使用配置的 result_selectors
                        found = False
                        for sel in self.search_config.get('result_selectors', []):
                            try:
                                if sel.startswith('xpath:'):
                                    if self.page.eles(sel):
                                        found = True
                                        break
                                else:
                                    if self.page.eles(sel):
                                        found = True
                                        break
                            except:
                                continue
                        if found:
                            break
                        time.sleep(0.5)

            print(f"\n✅ 爬取完成！共获取 {len(all_products)} 个商品数据")
            return all_products

        except Exception as e:
            print(f"❌ 爬取过程出错: {e}")
            return all_products

    def _perform_search(self, keyword: str):
        """
        执行搜索操作（使用 self.search_config 中的选择器，使得可支持不同网站）
        """
        try:
            search_box_selector = self.search_config.get('search_box_selector')
            search_btn_selector = self.search_config.get('search_btn_selector')

            print(f"搜索关键词: {keyword}")

            search_box = None
            if search_box_selector:
                try:
                    search_box = self.page.ele(search_box_selector, timeout=5)
                except Exception:
                    search_box = None

            # 如果没有找到搜索框，尝试在页面直接通过 JS 设置搜索参数或 raise
            if search_box:
                try:
                    search_box.clear()
                    search_box.input(keyword)
                except Exception:
                    try:
                        # 作为回退，直接输入回车
                        search_box.input('\n')
                    except:
                        pass

            # 尝试点击或回车提交（优先使用配置的按钮选择器）
            if search_btn_selector:
                try:
                    search_btn = self.page.ele(search_btn_selector, timeout=2)
                except Exception:
                    search_btn = None
            else:
                search_btn = None

            if search_btn:
                try:
                    search_btn.click()
                except Exception:
                    # 回退到输入回车
                    try:
                        if search_box:
                            search_box.input('\n')
                    except:
                        pass
            else:
                # 如果没有按钮，则尝试按回车提交（若找到了输入框）
                if search_box:
                    try:
                        search_box.input('\n')
                    except:
                        pass

            # 等待搜索结果主要容器出现（短超时）
            selectors = self.search_config.get('result_selectors', [])
            found = False
            for _ in range(10):  # 最多等待约 5s
                for sel in selectors:
                    try:
                        eles = self.page.eles(sel)
                    except Exception:
                        eles = []
                    if eles:
                        found = True
                        break
                if found:
                    break
                time.sleep(0.5)

            if not found:
                print("⚠️ 搜索提交后未在短时间内检测到结果，可能加载较慢或选择器不匹配")

            print("搜索请求已提交")

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            raise

    def search_products(self, keyword: str, max_pages: int = 5, detailed_extraction: bool = True) -> List[Dict]:
        """
        搜索商品并爬取结果（优化：减少不必要的 sleep，使用显式等待）
        此函数已被包装为调用 _search_products_impl；保留为空以兼容旧调用。
        """
        return self._search_products_impl(keyword, max_pages=max_pages, detailed_extraction=detailed_extraction)

    def _search_products_impl(self, keyword: str, max_pages: int = 5, detailed_extraction: bool = True) -> List[Dict]:
        """
        统一的搜索实现（原 search_products 的优化版本），现在被 wrapper 调用。
        """
        all_products = []
        try:
            print(f"正在打开 {self.search_config.get('home_url', self.base_url)} ...")
            self.page.get(self.search_config.get('home_url', self.base_url))
            # 短等待页面加载必要节点
            try:
                # 尝试使用配置的按钮选择器短等待
                self.page.ele(self.search_config.get('search_btn_selector', ''), timeout=4)
            except:
                pass

            # 一次性检查验证码
            if self.check_captcha():
                time.sleep(1)

            self._perform_search(keyword)

            for page_num in range(1, max_pages + 1):
                print(f"\n{'=' * 60}")
                print(f"正在爬取第 {page_num} 页...")
                print(f"{'=' * 60}")

                # 提取商品
                products = self._extract_products_enhanced(detailed_mode=detailed_extraction)
                all_products.extend(products)
                print(f"第 {page_num} 页提取到 {len(products)} 个商品")

                if page_num < max_pages:
                    if not self._go_next_page():
                        print("没有下一页了，停止爬取")
                        break
                    # 页面跳转后进行小等待并检测是否出现产品列表
                    for _ in range(8):  # 最多约4s
                        # 使用配置的 result_selectors
                        found = False
                        for sel in self.search_config.get('result_selectors', []):
                            try:
                                if sel.startswith('xpath:'):
                                    if self.page.eles(sel):
                                        found = True
                                        break
                                else:
                                    if self.page.eles(sel):
                                        found = True
                                        break
                            except:
                                continue
                        if found:
                            break
                        time.sleep(0.5)

            print(f"\n✅ 爬取完成！共获取 {len(all_products)} 个商品数据")
            return all_products

        except Exception as e:
            print(f"❌ 爬取过程出错: {e}")
            return all_products

    def _perform_search(self, keyword: str):
        """
        执行搜索操作（使用 self.search_config 中的选择器，使得可支持不同网站）
        """
        try:
            search_box_selector = self.search_config.get('search_box_selector')
            search_btn_selector = self.search_config.get('search_btn_selector')

            print(f"搜索关键词: {keyword}")

            search_box = None
            if search_box_selector:
                try:
                    search_box = self.page.ele(search_box_selector, timeout=5)
                except Exception:
                    search_box = None

            # 如果没有找到搜索框，尝试在页面直接通过 JS 设置搜索参数或 raise
            if search_box:
                try:
                    search_box.clear()
                    search_box.input(keyword)
                except Exception:
                    try:
                        # 作为回退，直接输入回车
                        search_box.input('\n')
                    except:
                        pass

            # 尝试点击或回车提交（优先使用配置的按钮选择器）
            if search_btn_selector:
                try:
                    search_btn = self.page.ele(search_btn_selector, timeout=2)
                except Exception:
                    search_btn = None
            else:
                search_btn = None

            if search_btn:
                try:
                    search_btn.click()
                except Exception:
                    # 回退到输入回车
                    try:
                        if search_box:
                            search_box.input('\n')
                    except:
                        pass
            else:
                # 如果没有按钮，则尝试按回车提交（若找到了输入框）
                if search_box:
                    try:
                        search_box.input('\n')
                    except:
                        pass

            # 等待搜索结果主要容器出现（短超时）
            selectors = self.search_config.get('result_selectors', [])
            found = False
            for _ in range(10):  # 最多等待约 5s
                for sel in selectors:
                    try:
                        eles = self.page.eles(sel)
                    except Exception:
                        eles = []
                    if eles:
                        found = True
                        break
                if found:
                    break
                time.sleep(0.5)

            if not found:
                print("⚠️ 搜索提交后未在短时间内检测到结果，可能加载较慢或选择器不匹配")

            print("搜索请求已提交")

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            raise

    def _extract_products_enhanced(self, detailed_mode: bool = True) -> List[Dict]:
        """
        增强版商品提取（优化：使用短轮询等待、尽早返回，减少固定 sleep）
        """
        products = []
        try:
            # 小辅助：在短时间内轮询多个选择器，返回找到的元素列表
            def wait_for_any_selector(selectors, total_timeout=4.0, poll_interval=0.4):
                elapsed = 0.0
                while elapsed < total_timeout:
                    for selector_type, selector in selectors:
                        if selector_type == 'xpath':
                            elems = self.page.eles(f'xpath:{selector}')
                        else:
                            elems = self.page.eles(selector)
                        if elems:
                            return elems
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                return []

            selectors_to_try = [
                ('xpath', '//div[@role="listitem"][@data-asin]'),
                ('xpath', '//div[@data-component-type="s-search-result"]'),
                ('css', 'div.s-result-item[data-asin]'),
                ('xpath', '//div[contains(@class, "s-result-item")][@data-asin]'),
            ]

            # 优先短轮询等待（默认 total_timeout = 4s）
            product_elements = wait_for_any_selector(selectors_to_try, total_timeout=4.0, poll_interval=0.4)

            if not product_elements:
                # 退回到更宽松的短等待（总 8s）
                product_elements = wait_for_any_selector(selectors_to_try, total_timeout=8.0, poll_interval=0.6)

            if not product_elements:
                print("⚠️ 未找到商品元素（已短时重试）")
                return products

            print(f"✅ 找到 {len(product_elements)} 个商品元素（采用短轮询）")

            for idx, element in enumerate(product_elements, 1):
                if detailed_mode:
                    product_data = self._extract_product_info_detailed(element, idx)
                else:
                    product_data = self._extract_product_info_basic(element, idx)

                if product_data:
                    products.append(product_data)
                    # 精简输出，避免大量 I/O 影响性能
                    asin = product_data.get('asin', 'N/A')
                    price_info = product_data.get('price_details') or {}
                    print(f"  ✅ 商品 {idx}: ASIN={asin} 价格={price_info.get('current_price', 'N/A')}")
                else:
                    print(f"  ⚠️ 商品 {idx} 数据提取失败")

            return products

        except Exception as e:
            print(f"❌ 提取商品列表失败: {e}")
            return products

    def _extract_title_description_enhanced(self, element) -> Tuple[Optional[str], Optional[str]]:
        """
        增强版标题和描述提取
        """
        title = None
        description = None

        try:
            # 策略1: 查找带aria-label的h2标签
            h2_elements = element.eles('xpath:.//h2[@aria-label]')
            for h2 in h2_elements:
                aria_label = h2.attr('aria-label')
                if aria_label and len(aria_label.strip()) > 10:
                    if not aria_label.isupper():
                        description = aria_label.strip()
                        title = aria_label.strip()
                        break

            # 策略2: 如果没有aria-label，查找h2内的span文本
            if not title:
                h2_elements = element.eles('xpath:.//h2//span')
                for h2 in h2_elements:
                    text = h2.text
                    if text and len(text.strip()) > 15:
                        title = text.strip()
                        if not description:
                            description = text.strip()
                        break

            # 策略3: 查找包含商品描述的div
            if not description:
                desc_selectors = [
                    'xpath:.//div[contains(@class, "s-title-instructions-style")]',
                    'xpath:.//div[contains(@class, "a-section")]//span[contains(@class, "a-text-normal")]',
                    'xpath:.//span[contains(@class, "a-size-base-plus")]'
                ]
                for selector in desc_selectors:
                    desc_elements = element.eles(selector)
                    for desc in desc_elements:
                        text = desc.text
                        if text and len(text.strip()) > 20:
                            description = text.strip()
                            if not title:
                                title = text.strip()
                            break
                    if description:
                        break

            # 清理和标准化
            if title:
                title = self._clean_text(title)
            if description:
                description = self._clean_text(description)
                if title and description == title:
                    description = None

            return title, description

        except Exception as e:
            print(f"⚠️ 提取标题描述时出错: {e}")
            return title, description

    # python
    def _extract_product_info_basic(self, element, index) -> Optional[Dict]:
        """
        基本商品信息提取：返回最小但常用字段，用于快速模式。
        """
        try:
            prod = {'index': index}
            # ASIN
            asin = element.attr('data-asin') or None
            prod['asin'] = asin

            # 链接
            link_ele = element.ele('xpath:.//h2//a') or element.ele(
                'xpath:.//a[@class="a-link-normal a-text-normal"]') or element.ele(
                'xpath:.//a[contains(@href,"/dp/") or contains(@href,"/gp/")]')
            detail_url = None
            if link_ele:
                href = link_ele.attr('href') or ''
                if href:
                    detail_url = urljoin(self.base_url, href)
            prod['detail_url'] = detail_url

            # 标题与描述
            title, description = self._extract_title_description_enhanced(element)
            prod['title'] = title or ""
            prod['description'] = description or ""

            # 图片
            prod['image'] = self._extract_image_url(element)

            # 价格（结构化）
            price_details = self._extract_price_enhanced(element) or {}
            prod['price_details'] = price_details
            # 兼容顶层 current_price 字段（若后续代码依赖）
            if price_details.get('current_price'):
                prod['current_price'] = price_details.get('current_price')

            # 评分与评论数
            try:
                rating_ele = element.ele('xpath:.//span[@class="a-icon-alt"]')
                rating_text = rating_ele.text if rating_ele else ""
                rating_match = re.search(r'([0-9]+(\.[0-9]+)?)', rating_text or "")
                prod['rating'] = float(rating_match.group(1)) if rating_match else None
            except:
                prod['rating'] = None

            try:
                review_ele = element.ele(
                    'xpath:.//span[@class="a-size-base" or contains(@class,"a-size-small")][normalize-space()]')
                if review_ele and review_ele.text:
                    rc = re.sub(r'[^\d]', '', review_ele.text)
                    prod['review_count'] = int(rc) if rc else None
                else:
                    prod['review_count'] = None
            except:
                prod['review_count'] = None

            # 品牌、Prime、Sponsored
            prod['brand'] = self._extract_brand_enhanced(element)
            prod['is_prime'] = bool(element.eles('xpath:.//i[contains(@aria-label,"Prime")]') or element.eles(
                'xpath:.//span[contains(@aria-label,"Prime")]'))
            prod['has_sponsored'] = bool(element.eles('xpath:.//span[contains(text(),"Sponsored")]') or element.eles(
                'xpath:.//span[contains(text(),"推广")]') or ('sponsored' in (element.text or "").lower()))

            return prod

        except Exception as e:
            print(f"⚠️ 提取基本商品信息时出错: {e}")
            return None

    def _extract_product_info_detailed(self, element, index) -> Optional[Dict]:
        """
        详细商品信息提取：在基本信息上补充特性、变体、库存等（调用已有方法）。
        """
        try:
            prod = self._extract_product_info_basic(element, index) or {'index': index}
            # 特性/卖点
            try:
                prod['features'] = self._extract_product_features(element)
            except:
                prod['features'] = []

            # 变体
            try:
                prod['variants'] = self._extract_variants_info(element)
            except:
                prod['variants'] = []

            # 运输信息与库存
            try:
                prod['shipping'] = self._extract_shipping_info(element)
            except:
                prod['shipping'] = None

            try:
                prod['stock_status'] = self._extract_stock_status(element)
            except:
                prod['stock_status'] = None

            return prod

        except Exception as e:
            print(f"⚠️ 提取详细商品信息时出错: {e}")
            return None

    def _extract_price_enhanced(self, element) -> Dict:
        """
        更完整的价格提取器：
        - 一次读取 element.html / element.text
        - 识别常见 Amazon 价格展示（a-offscreen, a-price, strike-through, price ranges, "from"/"starting at", Subscribe&Save）
        - 返回兼容旧字段并新增数值化字段：current_price_value, original_price_value, price_min, price_max, currency
        - 尽量保持速度：优先 a-offscreen、一次性正则匹配
        """
        price_data = {
            'current_price': None,
            'original_price': None,
            'discount': None,
            'discount_percentage': None,
            'savings': None,
            'shipping': None,
            'price_unit': 'USD',
            'price_type': None,
            # 下面是新增的数值化字段，便于排序/计算
            'current_price_value': None,
            'original_price_value': None,
            'price_min': None,
            'price_max': None,
            'currency': None,
        }

        try:
            # 预编译正则（捕获货币符号与数字部分）
            price_token_re = re.compile(r'([\$€£¥])\s*(\d{1,3}(?:[,\d]*)(?:\.\d{1,2})?)')
            range_re = re.compile(r'([\$€£¥]\s*\d[\d,\.\s]*?)\s*[-~–]\s*([\$€£¥]\s*\d[\d,\.\s]*?)')
            from_re = re.compile(r'(^|\b)(from|starting at|starts at)\b', re.I)
            pct_re = re.compile(r'(\d{1,3})\s*%')
            save_re = re.compile(r'(?:Save|Save up to)\s*[:\-]?\s*[\$€£¥]?\s*(\d{1,3}(?:[,\d]*)(?:\.\d{1,2})?)', re.I)
            shipping_re = re.compile(r'(FREE\s+Shipping|Free Shipping|Shipping[:\s]|Delivery[:\s])', re.I)

            # 读取文本/HTML
            full_text = (element.text or "").strip()
            try:
                full_html = element.html or ""
            except Exception:
                full_html = ""
            combined = full_html + "\n" + full_text

            # helper: 规范化价格字符串并转换为 float
            def parse_price_token(token: str):
                if not token:
                    return None, None
                m = price_token_re.search(token)
                if not m:
                    return None, None
                symbol = m.group(1)
                num = m.group(2).replace(',', '').replace(' ', '')
                try:
                    val = float(num)
                except Exception:
                    val = None
                return symbol, val

            # 1) 优先取 a-offscreen（Amazon 通常把语义化价格放在这里）
            try:
                off_nodes = element.eles('xpath:.//span[@class="a-offscreen"]')
            except Exception:
                off_nodes = []

            if off_nodes:
                off_texts = [(n.text or '').strip() for n in off_nodes if (n.text or '').strip()]
                if off_texts:
                    # 第一条通常是现价
                    cur_raw = off_texts[0].replace('\u00a0', ' ')
                    price_data['current_price'] = cur_raw
                    sym, val = parse_price_token(cur_raw)
                    if sym and val is not None:
                        price_data['currency'] = sym
                        price_data['current_price_value'] = val
                        price_data['price_unit'] = 'USD' if sym == '$' else ('EUR' if sym == '€' else ('GBP' if sym == '£' else 'JPY'))
                    # 如果有第二条，可能为原价
                    if len(off_texts) >= 2:
                        orig_raw = off_texts[1].replace('\u00a0', ' ')
                        price_data['original_price'] = orig_raw
                        sym2, val2 = parse_price_token(orig_raw)
                        if sym2 and val2 is not None:
                            price_data['original_price_value'] = val2

            # 2) 若没有 a-offscreen 的结果，使用范围或全文匹配（一次性）
            if not price_data['current_price']:
                # 价格范围
                rm = range_re.search(combined)
                if rm:
                    low_raw = rm.group(1).replace('\u00a0', ' ')
                    high_raw = rm.group(2).replace('\u00a0', ' ')
                    price_data['current_price'] = f"{low_raw} - {high_raw}"
                    price_data['price_type'] = 'range'
                    s1, v1 = parse_price_token(low_raw)
                    s2, v2 = parse_price_token(high_raw)
                    if v1 is not None:
                        price_data['price_min'] = v1
                    if v2 is not None:
                        price_data['price_max'] = v2
                    # set currency if available
                    if s1:
                        price_data['currency'] = s1
                else:
                    # 抽取页面中所有价格 token，第一项为现价，第二项为原价（常见）
                    all_tokens = price_token_re.findall(combined)
                    if all_tokens:
                        # price_token_re.findall returns list of tuples (sym, num)
                        # reconstruct strings
                        tokens = [f"{t[0]}{t[1]}" for t in all_tokens]
                        cur_raw = tokens[0].replace('\u00a0', ' ')
                        price_data['current_price'] = cur_raw
                        s, v = parse_price_token(cur_raw)
                        if s and v is not None:
                            price_data['currency'] = s
                            price_data['current_price_value'] = v
                            price_data['price_unit'] = 'USD' if s == '$' else ('EUR' if s == '€' else ('GBP' if s == '£' else 'JPY'))
                        if len(tokens) >= 2:
                            orig_raw = tokens[1].replace('\u00a0', ' ')
                            price_data['original_price'] = orig_raw
                            s2, v2 = parse_price_token(orig_raw)
                            if v2 is not None:
                                price_data['original_price_value'] = v2

            # 3) 识别 "from" / "starting at" 文本（如果价格是起价）
            if price_data['current_price'] and from_re.search(combined):
                price_data['price_type'] = 'from'

            # 4) 计算折扣与节省（若提供原价和现价）
            if price_data.get('current_price_value') is None and price_data.get('current_price'):
                # attempt to get numeric if current_price is a single token
                sym, v = parse_price_token(price_data['current_price'])
                if v is not None:
                    price_data['current_price_value'] = v
                    if sym:
                        price_data['currency'] = sym

            if price_data.get('original_price_value') is None and price_data.get('original_price'):
                sym, v = parse_price_token(price_data['original_price'])
                if v is not None:
                    price_data['original_price_value'] = v

            if price_data.get('current_price_value') is not None and price_data.get('original_price_value') is not None:
                try:
                    cur = price_data['current_price_value']
                    orig = price_data['original_price_value']
                    if orig > 0 and orig >= cur:
                        diff = orig - cur
                        pct = (diff / orig) * 100
                        price_data['discount'] = f"${diff:.2f}"
                        price_data['discount_percentage'] = f"{pct:.1f}%"
                        price_data['savings'] = f"Save ${diff:.2f} ({pct:.1f}%)"
                except Exception:
                    pass

            # 5) 若折扣字段缺失，尝试从文本中补充
            if not price_data.get('discount_percentage'):
                pm = pct_re.search(combined)
                if pm:
                    price_data['discount_percentage'] = f"{pm.group(1)}%"
            if not price_data.get('savings'):
                sm = save_re.search(combined)
                if sm:
                    val = sm.group(1).replace(',', '')
                    price_data['savings'] = f"Save ${val}"

            # 6) 抽取运输信息
            shipm = shipping_re.search(combined)
            if shipm:
                price_data['shipping'] = shipm.group(1).strip()

            # 7) 补齐 price_min/price_max 若尚未设置
            if price_data.get('current_price_value') is not None and price_data.get('price_min') is None:
                price_data['price_min'] = price_data['current_price_value']
            if price_data.get('current_price_value') is not None and price_data.get('price_max') is None:
                price_data['price_max'] = price_data['current_price_value']

            # 8) 规范 currency 字段为符号/代码
            if price_data.get('currency'):
                sym = price_data['currency']
                code = 'USD' if sym == '$' else ('EUR' if sym == '€' else ('GBP' if sym == '£' else 'JPY'))
                price_data['price_unit'] = code
                price_data['currency'] = sym

            return price_data

        except Exception as e:
            print(f"⚠️ 提取价格信息时出错: {e}")
            return price_data

    def _extract_brand_enhanced(self, element) -> Optional[str]:
        """
        增强版品牌提取
        """
        try:
            brand_selectors = [
                'xpath:.//span[@class="a-size-base-plus a-color-base"]',
                'xpath:.//h2[contains(@class, "a-size-mini")]//span',
                'xpath:.//span[contains(@class, "a-text-bold")]',
                'xpath:.//a[contains(@href, "/s?k=")]//span',
            ]

            for selector in brand_selectors:
                brand_elements = element.eles(selector)
                if brand_elements:
                    for brand_ele in brand_elements:
                        brand_text = brand_ele.text or ""
                        if brand_text and len(brand_text.strip()) > 1:
                            lower_text = brand_text.lower()
                            if len(brand_text) > 15 or lower_text in ['sponsored', 'advertisement']:
                                continue
                            return brand_text.strip()

            # 如果上述方法没找到，尝试从标题中提取可能品牌
            title_elements = element.eles('xpath:.//h2')
            if title_elements:
                for title_ele in title_elements:
                    title_text = title_ele.text or ""
                    words = title_text.split()
                    if len(words) >= 2:
                        if words[0].istitle() and len(words[0]) <= 20:
                            return words[0]

            return None

        except Exception as e:
            print(f"⚠️ 提取品牌信息时出错: {e}")
            return None
    def _extract_image_url(self, element) -> Optional[str]:
        """
        提取图片URL
        """
        try:
            img_selectors = [
                'xpath:.//img[@class="s-image"]',
                'xpath:.//img[contains(@data-image-latency, "s-product-image")]',
            ]

            for selector in img_selectors:
                img_elements = element.eles(selector)
                if img_elements:
                    for img_ele in img_elements:
                        src = img_ele.attr('src') or img_ele.attr('data-src')
                        if src and src.startswith('http'):
                            return src
            return None

        except Exception as e:
            print(f"⚠️ 提取图片URL时出错: {e}")
            return None

    def _extract_product_features(self, element) -> List[str]:
        """
        提取商品特性/卖点
        """
        try:
            features = []
            feature_selectors = [
                'xpath:.//div[contains(@class, "a-color-secondary")]//span',
                'xpath:.//ul[@class="a-unordered-list"]//span',
            ]

            for selector in feature_selectors:
                feature_elements = element.eles(selector)
                for feature_ele in feature_elements:
                    feature_text = feature_ele.text or ""
                    if feature_text and len(feature_text.strip()) > 5:
                        cleaned = self._clean_text(feature_text)
                        features.append(cleaned)

            return features[:5]

        except Exception as e:
            print(f"⚠️ 提取商品特性时出错: {e}")
            return []

    def _extract_shipping_info(self, element) -> Optional[str]:
        """
        提取运输信息
        """
        try:
            shipping_selectors = [
                'xpath:.//span[contains(text(), "FREE Shipping")]',
                'xpath:.//span[contains(text(), "Delivery")]',
                'xpath:.//span[contains(@aria-label, "FREE Shipping")]',
            ]

            for selector in shipping_selectors:
                shipping_elements = element.eles(selector)
                if shipping_elements:
                    shipping_text = shipping_elements[0].text or ""
                    if shipping_text:
                        return shipping_text.strip()
            return None

        except Exception as e:
            print(f"⚠️ 提取运输信息时出错: {e}")
            return None

    def _extract_stock_status(self, element) -> Optional[str]:
        """
        提取库存状态
        """
        try:
            stock_selectors = [
                'xpath:.//span[contains(text(), "In Stock")]',
                'xpath:.//span[contains(text(), "Only") and contains(text(), "left")]',
                'xpath:.//span[contains(text(), "Out of Stock")]',
            ]

            for selector in stock_selectors:
                stock_elements = element.eles(selector)
                if stock_elements:
                    stock_text = stock_elements[0].text or ""
                    if stock_text:
                        return stock_text.strip()
            return None

        except Exception as e:
            print(f"⚠️ 提取库存状态时出错: {e}")
            return None

    def _extract_variants_info(self, element) -> List[Dict]:
        """
        提取变体信息
        """
        try:
            variants = []
            variant_selectors = [
                'xpath:.//div[contains(@class, "a-row a-size-base")]//span',
                'xpath:.//ul[contains(@class, "a-unordered-list")]//li',
            ]

            for selector in variant_selectors:
                variant_elements = element.eles(selector)
                for variant_ele in variant_elements:
                    variant_text = variant_ele.text or ""
                    if variant_text and ('Color:' in variant_text or 'Size:' in variant_text):
                        variants.append({'text': variant_text.strip()})

            return variants[:3]

        except Exception as e:
            print(f"⚠️ 提取变体信息时出错: {e}")
            return []


    def _clean_text(self, text: str) -> str:
        """
        清理文本
        """
        if not text:
            return ""

        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

        return text

    def _go_next_page(self) -> bool:
        """
        翻到下一页
        """
        try:
            next_page_selector = 'a.s-pagination-next'

            next_btn = self.page.ele(next_page_selector, timeout=5)

            if next_btn and 's-pagination-disabled' not in (next_btn.attr('class') or ''):
                next_btn.click()
                print("✅ 已翻页")
                return True
            else:
                print("⚠️ 下一页按钮不可用")
                return False

        except Exception as e:
            print(f"❌ 翻页失败: {e}")
            return False

    def close(self):
        """关闭浏览器"""
        if self.page:
            self.page.quit()
            print("浏览器已关闭")

    def save_results(self, products: List[Dict], filename: str = None):
        """
        保存爬取结果到JSON和CSV文件，包含用于后续API的数据表格字段：
        - index, asin, title, description, detail_url
        - price (原始字符串), price_value (current numeric), currency, price_min, price_max
        - original_price, original_price_value, discount_percentage, savings, shipping
        这样CSV可直接作为轻量数据表对外提供或导入数据库。
        """
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"amazon_search_results_{timestamp}.json"

        # 构建完整产品表（包含数值字段，便于后续 API 使用）
        table_products = []
        for idx, p in enumerate(products, 1):
            price_details = p.get('price_details') or {}
            # 尝试优先获取标准化字段
            price_str = price_details.get('current_price') or p.get('current_price') or ""
            price_value = price_details.get('current_price_value')
            currency_sym = price_details.get('currency') or price_details.get('price_unit') or None
            price_min = price_details.get('price_min')
            price_max = price_details.get('price_max')
            original_price = price_details.get('original_price')
            original_price_value = price_details.get('original_price_value')
            discount_pct = price_details.get('discount_percentage')
            savings = price_details.get('savings')
            shipping = price_details.get('shipping') or p.get('shipping')

            table_products.append({
                'index': idx,
                'asin': p.get('asin') or "",
                'title': p.get('title') or "",
                'description': p.get('description') or "",
                'detail_url': p.get('detail_url') or "",
                'price': price_str or "",
                'price_value': price_value if price_value is not None else "",
                'currency': currency_sym or "",
                'price_min': price_min if price_min is not None else "",
                'price_max': price_max if price_max is not None else "",
                'original_price': original_price or "",
                'original_price_value': original_price_value if original_price_value is not None else "",
                'discount_percentage': discount_pct or "",
                'savings': savings or "",
                'shipping': shipping or "",
            })

        data_to_save = {
            'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_products': len(table_products),
            'products': table_products
        }

        # 保存 JSON（完整表）
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            print(f"✅ 完整结果已保存到: {filename}")
        except Exception as e:
            print(f"⚠️ 保存JSON时出错: {e}")

        # 保存 CSV（包含所有对外需要的列，便于直接当作数据表提供给 API 或导入 DB）
        csv_filename = filename.replace('.json', '.csv')
        self._save_to_csv(table_products, csv_filename)

    def _save_to_csv(self, products: List[Dict], filename: str):
        """
        将完整的产品表保存为 CSV，列包括：
        index, asin, title, description, detail_url, price, price_value, currency,
        price_min, price_max, original_price, original_price_value, discount_percentage, savings, shipping
        """
        try:
            fieldnames = [
                'index', 'asin', 'title', 'description', 'detail_url',
                'price', 'price_value', 'currency', 'price_min', 'price_max',
                'original_price', 'original_price_value', 'discount_percentage', 'savings', 'shipping'
            ]
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for product in products:
                    # 仅写入所需列，保证字段顺序与表头一致
                    row = {k: product.get(k, '') for k in fieldnames}
                    writer.writerow(row)

            print(f"✅ CSV数据表已保存: {filename}")

        except Exception as e:
            print(f"⚠️ 保存CSV文件时出错: {e}")

def main():
    """主函数 - 运行爬虫的示例"""
    import sys

    print("🔍 Amazon 搜索爬虫 - 增强版")
    print("=" * 50)

    # # 1.1配置选项
    # config = {
    #     'headless': True,  # 改为 True（无头模式）
    #     'use_saved_login': False,  # 改为 False（不使用保存的登录）
    #     'browser_type': 'edge',  #
    #     'max_pages': 1,  # 只爬1页
    #     'detailed_extraction': False,  # 快速模式
    # }

    # 1.2配置选项
    config = {
        'headless': False,  # 是否无头模式运行
        'use_saved_login': True,  # 是否使用保存的登录信息
        'browser_type': 'edge',  # 浏览器类型：edge 或 chrome
        'max_pages': 2,  # 最大爬取页数
        'detailed_extraction': True,  # 是否启用详细提取
    }
    # 创建爬虫实例
    print("正在初始化浏览器...")
    crawler = EnhancedAmazonSearchCrawler(
        headless=config['headless'],
        use_saved_login=config['use_saved_login'],
        browser_type=config['browser_type']
    )

    try:
        # 搜索关键词
        keywords = [
            "wireless headphones",
            "laptop bag",
            "coffee maker",
            "yoga mat",
            "smart watch"
        ]

        print("\n请选择搜索关键词:")
        for i, keyword in enumerate(keywords, 1):
            print(f"  {i}. {keyword}")
        print(f"  6. 自定义关键词")

        choice = input("\n请输入选择 (1-6): ").strip()

        if choice == '6':
            keyword = input("请输入自定义搜索关键词: ").strip()
        elif choice.isdigit() and 1 <= int(choice) <= 5:
            keyword = keywords[int(choice) - 1]
        else:
            print("⚠️ 无效选择，使用默认关键词")
            keyword = keywords[0]

        print(f"\n🔍 开始搜索: {keyword}")
        print("=" * 60)

        # 开始爬取
        start_time = time.time()

        products = crawler.search_products(
            keyword=keyword,
            max_pages=config['max_pages'],
            detailed_extraction=config['detailed_extraction']
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        # 打印详细统计
        print("\n" + "=" * 60)
        print("📊 爬取结果统计")
        print("=" * 60)

        # 统计信息
        total_products = len(products)
        products_with_price = sum(1 for p in products if p.get('price_details', {}).get('current_price'))
        products_with_rating = sum(1 for p in products if p.get('rating'))
        prime_products = sum(1 for p in products if p.get('is_prime'))
        sponsored_products = sum(1 for p in products if p.get('has_sponsored'))

        print(f"总商品数: {total_products}")
        print(f"有价格的商品: {products_with_price}")
        print(f"有评分的商品: {products_with_rating}")
        print(f"Prime商品: {prime_products}")
        print(f"推广商品: {sponsored_products}")
        print(f"爬取时间: {elapsed_time:.2f} 秒")

        # 价格分布分析
        prices = []
        for p in products:
            price_data = p.get('price_details', {})
            if price_data.get('current_price'):
                try:
                    price_str = price_data['current_price']
                    # 提取数字部分（处理价格范围）
                    if '-' in price_str:
                        # 取最低价
                        price_match = re.search(r'[\$€£¥]\s*(\d+\.?\d*)', price_str)
                        if price_match:
                            prices.append(float(price_match.group(1)))
                    else:
                        price_num = re.search(r'(\d+\.?\d*)', price_str)
                        if price_num:
                            prices.append(float(price_num.group(1)))
                except Exception as e:
                    continue

        if prices:
            avg_price = sum(prices) / len(prices)
            max_price = max(prices)
            min_price = min(prices)
            print(f"\n💰 价格分析:")
            print(f"  平均价格: ${avg_price:.2f}")
            print(f"  最高价格: ${max_price:.2f}")
            print(f"  最低价格: ${min_price:.2f}")
            print(f"  价格范围: ${min_price:.2f} - ${max_price:.2f}")

        # 显示前5个商品的详细信息
        if products:
            print(f"\n📋 前5个商品详情:")
            print("-" * 60)

            for idx, product in enumerate(products[:5], 1):
                print(f"\n商品 #{product.get('index', idx)}:")
                print(f"  ASIN: {product.get('asin', 'N/A')}")

                # 标题和描述
                if product.get('title'):
                    title = product['title']
                    if len(title) > 60:
                        title = title[:57] + "..."
                    print(f"  标题: {title}")

                if product.get('description') and product['description'] != product.get('title'):
                    desc = product['description']
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    print(f"  描述: {desc}")

                # 价格信息4

                price_data = product.get('price_details', {})
                if price_data:
                    print(f"  价格信息:")
                    if price_data.get('current_price'):
                        print(f"    现价: {price_data['current_price']}")
                    if price_data.get('original_price'):
                        print(f"    原价: {price_data['original_price']}")
                    if price_data.get('discount_percentage'):
                        print(f"    折扣: {price_data['discount_percentage']}")
                    if price_data.get('shipping'):
                        print(f"    运费: {price_data['shipping']}")

                # 评分信息
                if product.get('rating'):
                    rating_str = f"评分: {product['rating']}/5"
                    if product.get('review_count'):
                        rating_str += f" ({product['review_count']}条评论)"
                    print(f"  {rating_str}")

                # 品牌
                if product.get('brand'):
                    print(f"  品牌: {product['brand']}")

                # Prime状态
                if product.get('is_prime'):
                    print(f"  ✅ Prime商品")

                if product.get('has_sponsored'):
                    print(f"  ⚠️ 推广商品")

                if product.get('detail_url'):
                    print(f"  链接: {product['detail_url'][:80]}...")

        # 保存结果
        if products:
            crawler.save_results(products)

            # 显示价格最便宜的前5个商品
            products_with_price = [p for p in products if p.get('price_details', {}).get('current_price')]
            if products_with_price:
                # 按价格排序
                def get_price(product):
                    try:
                        price_str = product['price_details']['current_price']
                        # 处理价格范围
                        if '-' in price_str:
                            price_match = re.search(r'[\$€£¥]\s*(\d+\.?\d*)', price_str)
                            return float(price_match.group(1)) if price_match else float('inf')
                        else:
                            price_num = re.search(r'(\d+\.?\d*)', price_str)
                            return float(price_num.group(1)) if price_num else float('inf')
                    except:
                        return float('inf')

                sorted_products = sorted(products_with_price, key=get_price)

                print(f"\n💸 最便宜的5个商品:")
                print("-" * 60)
                for idx, product in enumerate(sorted_products[:5], 1):
                    price = product['price_details']['current_price']
                    title = product.get('title', 'N/A')
                    if len(title) > 50:
                        title = title[:47] + "..."
                    print(f"{idx}. {price} - {title}")

        print(f"\n✅ 爬取完成！共获取 {len(products)} 个商品数据")

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭浏览器
        crawler.close()
        print("\n🎯 程序执行完毕")


# 运行主函数
if __name__ == '__main__':
    main()