import re
import time
import json
import csv
import random
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote
import os
from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime


class ChineseEcommerceDetailCrawler:
    """国内电商平台商品详情爬虫（直接爬取商品页）"""

    def __init__(self, headless: bool = False, use_saved_login: bool = True):
        """
        初始化爬虫
        """
        self.page = None
        self.headless = headless
        self.use_saved_login = use_saved_login
        self.current_site = 'unknown'

        # 各站点商品详情页配置
        self.site_detail_configs = {
            'taobao': {
                'name': '淘宝',
                'search_url': 'https://s.taobao.com/search?q={keyword}',
                'item_url_patterns': [
                    r'https://item\.taobao\.com/item\.htm\?id=\d+',
                    r'//item\.taobao\.com/item\.htm\?id=\d+'
                ],
                # 商品详情页选择器
                'detail_selectors': {
                    'title': ['h1[class*="Title"]', 'div.tb-detail-hd h1', '#J_Title'],
                    'price': ['.tb-rmb-num', '.tm-price', '#J_StrPrice'],
                    'original_price': ['.tm-originalPrice', '.tb-rmb-line'],
                    'sales': ['.tm-count', '#J_SellCounter'],
                    'shop_name': ['.tb-shop-name', '.shop-name'],
                    'shop_link': ['.tb-shop-name a', '.shop-name a'],
                    'description': ['#description', '.tb-detail-content'],
                    'specs': ['.tb-key .tb-prop'],
                    'images': ['.tb-booth img', '#J_UlThumb img'],
                    'rating': ['.tb-rate-counter'],
                    'comments_count': ['.tm-ind-panel .tm-count'],
                    'stock': ['.tb-amount'],
                    'sku': ['.tb-sku'],
                    'coupon': ['.tb-coupon'],
                    'promotion': ['.tb-promotion']
                }
            },
            'jd': {
                'name': '京东',
                'search_url': 'https://search.jd.com/Search?keyword={keyword}&enc=utf-8',
                'item_url_patterns': [
                    r'https://item\.jd\.com/\d+\.html',
                    r'//item\.jd\.com/\d+\.html'
                ],
                'detail_selectors': {
                    'title': ['.sku-name', 'div[class*="name"]'],
                    'price': ['.p-price .price', '.J-p-{}'],  # {} 会被商品ID替换
                    'original_price': ['.p-price del'],
                    'sales': ['.p-sales', '#sales', '.count'],
                    'shop_name': ['.J-hover-wrap .name', '.shop-name'],
                    'shop_link': ['.J-hover-wrap a', '.shop-name a'],
                    'description': ['.detail-content', '#product-detail'],
                    'specs': ['.p-parameter-list', '#parameter2'],
                    'images': ['.spec-items img', '#spec-list img'],
                    'rating': ['.percent-con'],
                    'comments_count': ['.comment-count'],
                    'stock': ['.store-prompt', '.stock'],
                    'sku': ['.itemInfo-wrap'],
                    'coupon': ['.coupon'],
                    'promotion': ['.prom-goods']
                }
            },
            'tmall': {
                'name': '天猫',
                'search_url': 'https://list.tmall.com/search_product.htm?q={keyword}',
                'item_url_patterns': [
                    r'https://detail\.tmall\.com/item\.htm\?id=\d+',
                    r'//detail\.tmall\.com/item\.htm\?id=\d+'
                ],
                'detail_selectors': {
                    'title': ['.tb-detail-hd h1', '.tb-main-title'],
                    'price': ['.tm-price', '.tm-price-panel'],
                    'original_price': ['.tm-originalPrice'],
                    'sales': ['.tm-count'],
                    'shop_name': ['.tb-shop-name', '.slogo-shopname'],
                    'shop_link': ['.tb-shop-name a'],
                    'description': ['.tb-detail-content', '#J_DivItemDesc'],
                    'specs': ['.tb-key'],
                    'images': ['.tb-booth img'],
                    'rating': ['.tb-rate-counter'],
                    'comments_count': ['.tm-review'],
                    'stock': ['.tb-amount'],
                    'sku': ['.tb-sku'],
                    'coupon': ['.tb-coupon'],
                    'promotion': ['.tb-promotion']
                }
            },
            '1688': {
                'name': '1688',
                'search_url': 'https://s.1688.com/selloffer/offer_search.html?keywords={keyword}',
                'item_url_patterns': [
                    r'https://detail\.1688\.com/offer/\d+\.html',
                    r'//detail\.1688\.com/offer/\d+\.html'
                ],
                'detail_selectors': {
                    'title': ['.offer-title', '.title'],
                    'price': ['.price', '.offer-price'],
                    'original_price': ['.original-price'],
                    'sales': ['.trade-num', '.sale-num'],
                    'shop_name': ['.company-name'],
                    'shop_link': ['.company-name a'],
                    'description': ['.offer-desc', '.content'],
                    'specs': ['.offer-attr'],
                    'images': ['.image-view img'],
                    'rating': ['.score'],
                    'comments_count': ['.comment-num'],
                    'stock': ['.stock', '.amount'],
                    'sku': ['.offer-sku'],
                    'coupon': ['.coupon-info'],
                    'promotion': ['.promotion-info']
                }
            }
        }

        self._init_browser()

    def _init_browser(self):
        """初始化浏览器（使用您原来的代码）"""
        print("🚀 启动浏览器...")
        co = ChromiumOptions()

        # 设置浏览器路径（可以根据需要调整）
        edge_paths = [
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        ]

        for path in edge_paths:
            if os.path.exists(path):
                co.set_browser_path(path)
                break

        # 浏览器配置
        co.set_argument('--disable-blink-features=AutomationControlled')
        # 防止 Chromium 恢复上次会话（避免自动打开上次的标签页，例如淘宝）
        co.set_argument('--disable-restore-session-state')
        co.set_argument('--no-first-run')
        co.set_argument('--disable-gpu')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--lang=zh-CN')
        co.set_argument('--disable-notifications')

        # 用户代理
        co.set_user_agent(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0'
        )

        # 如果需要保存登录，则创建并使用持久化用户数据目录
        if self.use_saved_login:
            user_data_dir = os.path.join(os.path.dirname(__file__), 'domestic_browser_data')
            # 确保目录存在并可写
            self._ensure_user_data_dir(user_data_dir)
            co.set_user_data_path(user_data_dir)
            # 有些 Chromium 启动需要显式传入 user-data-dir 参数
            try:
                co.set_argument(f'--user-data-dir={user_data_dir}')
                # 使用默认配置文件夹名 Default，可根据需要更改
                co.set_argument('--profile-directory=Default')
            except Exception:
                pass
            print(f"✅ 使用持久化用户数据目录: {user_data_dir}")

            # 如果启用保存登录，则强制使用可见模式以便手动交互式登录
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
            self.page = ChromiumPage(addr_or_opts=co)
            # 清空任何由 profile 恢复的启动页（例如有时 profile 会恢复上次打开的淘宝），
            # 立即跳转到空白页，避免在后续导航前短暂显示这些页面。
            try:
                self.page.get('about:blank')
                time.sleep(0.3)
            except Exception:
                pass

            # 隐藏自动化特征
            try:
                self.page.run_js('''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = { runtime: {} };
                ''')
            except Exception:
                pass

            print("✅ 浏览器启动成功")

            # 如果启用了保存登录，则简单检查当前profile是否需要登录/验证；如需要则提示手动完成
            if self.use_saved_login:
                try:
                    # 不在启动时打开任何站点或强制检测登录状态（此检测在不同机器/profile下易误判）。
                    # 浏览器已启动并加载了指定 profile；只有在用户选择站点时才会导航到对应页面。
                    print("ℹ️ 使用持久化 profile（浏览器已启动——选择站点后程序将导航到目标页面；首次登录请手动在打开的浏览器中完成一次以保存会话）。")
                except Exception as e:
                    print(f"⚠️ 登录检测过程出错: {e}")

        except Exception as e:
            print(f"❌ 浏览器启动失败: {e}")
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

    def _is_verification_or_login_present(self) -> bool:
        """简单检测页面上是否存在登录/验证相关的痕迹。

        返回 True 表示可能需要人工干预（登录/滑块/验证码等）。
        检测策略：检查 URL，页面文本，常见选择器。
        """
        try:
            # 检查 URL 中的明显关键词
            url = (self.page.url or '').lower()
            if any(k in url for k in ('login', 'signin', 'passport', 'auth', 'verify')):
                return True

            # 检查页面文本中常见提示
            text = (self.page.text or '')[:8000]
            login_keywords = ['登录', '请登录', '登录后', '输入密码', '请输入密码', '验证码', '滑块', '请完成安全验证', '请验证']
            for kw in login_keywords:
                if kw in text:
                    return True

            # 检查常见的输入或验证码元素
            try:
                if self.page.ele('input[type="password"]', timeout=1):
                    return True
            except:
                pass

            try:
                # captcha-like elements
                if self.page.ele('iframe[src*="captcha"]', timeout=1):
                    return True
            except:
                pass

        except Exception:
            return False

        return False

    def wait_for_manual_login(self, prompt: str = None, timeout: int = 600):
        """提示用户在浏览器中手动完成登录或验证，然后按 Enter 继续。

        参数:
            prompt: 自定义提示信息 (可选)
            timeout: 自动检测超时时间（秒），超时后函数返回。

        说明: 以最简单可靠的方式实现人工登录：在可见浏览器中操作后，按 Enter
        或等待自动检测到登录已解除验证页面状态。
        """
        if prompt is None:
            prompt = (
                "检测到可能需要登录/验证。请在打开的浏览器窗口中完成登录或验证码验证，"
                "完成后回到此控制台按 Enter 继续（或等待自动检测）。"
            )

        print('\n' + '=' * 60)
        print(prompt)
        print(f"正在每 3 秒检测一次页面状态，最长等待 {timeout} 秒...\n")

        start = time.time()
        try:
            # 轮询检测，用户可以在任意时刻按 Enter 跳出
            while True:
                # 如果验证/登录痕迹消失，则自动返回
                if not self._is_verification_or_login_present():
                    print("检测到登录/验证已完成，继续爬取...")
                    return

                # 检查超时
                if time.time() - start > timeout:
                    print(f"等待超时 ({timeout}s)，请确认登录/验证是否完成，然后按 Enter 继续或手动终止程序。")
                    try:
                        input('按 Enter 继续...')
                    except Exception:
                        pass
                    return

                # 非阻塞短等待，同时允许用户按 Ctrl+C 退出
                try:
                    # 在等待期间给用户一个机会按 Enter 来立刻继续
                    # 由于普通 input 会阻塞，这里只做短睡眠以避免阻塞主线程
                    time.sleep(3)
                except KeyboardInterrupt:
                    print('用户中断，停止等待')
                    return

        except Exception as e:
            print(f"手动登录等待出错: {e}")
            return

    def get_product_details_from_url(self, product_url: str) -> Dict:
        """
        从商品URL直接爬取商品详情

        Args:
            product_url: 商品详情页URL

        Returns:
            商品详情字典
        """
        print(f"\n🔍 开始爬取商品详情页: {product_url}")

        try:
            # 1. 打开商品页面
            # 先导航到空白页以避免显示被 profile 恢复的旧页面（例如淘宝），然后再打开目标页面
            try:
                self.page.get('about:blank')
                time.sleep(0.2)
            except Exception:
                pass
            self.page.get(product_url)
            time.sleep(5)  # 等待页面加载

            # 如果页面上出现登录/验证提示，暂停并让用户手动完成
            if self._is_verification_or_login_present():
                self.wait_for_manual_login()

            # 2. 滚动页面加载所有内容
            self._scroll_page_gradually()

            # 3. 检测站点并爬取详情
            site = self._detect_site_from_url(product_url)
            if site:
                self.current_site = site
                return self._extract_product_details(site, product_url)
            else:
                # 尝试自动识别站点
                return self._extract_product_details_auto(product_url)

        except Exception as e:
            print(f"❌ 爬取商品详情失败: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def search_and_get_details(self, site: str, keyword: str, max_items: int = 5) -> List[Dict]:
        """
        搜索关键词并爬取前N个商品的详情

        Args:
            site: 站点名称
            keyword: 搜索关键词
            max_items: 最大爬取商品数量

        Returns:
            商品详情列表
        """
        if site not in self.site_detail_configs:
            print(f"❌ 不支持该站点: {site}")
            return []

        self.current_site = site
        site_config = self.site_detail_configs[site]

        print(f"\n🔍 在 {site_config['name']} 搜索 '{keyword}'")

        try:
            # 1. 执行搜索
            search_url = site_config['search_url'].format(keyword=quote(keyword))
            # 先清空当前页面（避免显示 profile 恢复的页面），然后再导航到目标搜索页
            try:
                self.page.get('about:blank')
                time.sleep(0.2)
            except Exception:
                pass
            self.page.get(search_url)
            time.sleep(6)

            # 如果需要登录/验证，暂停并让用户手动完成
            if self._is_verification_or_login_present():
                self.wait_for_manual_login()

            # 滚动加载更多商品
            self._scroll_page_gradually()

            # 2. 提取商品链接
            product_urls = self._extract_product_urls_from_search(site)
            print(f"✅ 找到 {len(product_urls)} 个商品链接")

            if not product_urls:
                print("⚠️ 未找到商品链接")
                return []

            # 3. 限制爬取数量
            product_urls = product_urls[:max_items]

            # 4. 逐个爬取商品详情
            all_details = []
            for i, url in enumerate(product_urls, 1):
                print(f"\n📦 正在爬取第 {i}/{len(product_urls)} 个商品...")

                # 完整的URL
                if not url.startswith('http'):
                    if url.startswith('//'):
                        url = 'https:' + url
                    else:
                        url = urljoin(self.page.url, url)

                # 爬取详情
                details = self.get_product_details_from_url(url)
                if details:
                    all_details.append(details)
                    print(f"✅ 成功爬取: {details.get('title', '未知')[:50]}...")

                # 随机延迟，避免被封
                if i < len(product_urls):
                    delay = random.uniform(3, 8)
                    print(f"⏳ 等待 {delay:.1f} 秒后爬取下一个商品...")
                    time.sleep(delay)

            print(f"\n🎉 完成！成功爬取 {len(all_details)} 个商品的详情")
            return all_details

        except Exception as e:
            print(f"❌ 搜索爬取失败: {e}")
            return []

    def _extract_product_urls_from_search(self, site: str) -> List[str]:
        """
        从搜索结果页提取商品链接
        """
        urls = []

        # 获取页面所有链接
        try:
            # 优先针对京东做专门处理：多策略尝试提取商品链接（li[data-sku]、常用商品链接选择器、以及通用的 JS 扫描）
            if site == 'jd':
                try:
                    # 方法1：li[data-sku]
                    sku_elements = self.page.eles('css:li[data-sku]') or self.page.eles('xpath://li[@data-sku]')
                    if sku_elements:
                        for el in sku_elements:
                            try:
                                sku = el.attr('data-sku')
                                if sku:
                                    urls.append(f'https://item.jd.com/{sku}.html')
                            except:
                                continue
                        urls = list(dict.fromkeys(urls))
                        if urls:
                            return urls

                    # 方法2：常见的商品链接选择器（比如 .p-name a / .p-img a）
                    try:
                        name_links = self.page.eles('css:.p-name a') or self.page.eles('css:.p-img a') or self.page.eles('css:.p-name a.J_ClickStat')
                        if name_links:
                            for a in name_links:
                                try:
                                    href = a.attr('href') or ''
                                    if href:
                                        if href.startswith('//'):
                                            href = 'https:' + href
                                        elif href.startswith('/'):
                                            href = urljoin(self.page.url, href)
                                        if 'item.jd.com' in href or re.search(r'/\d+\.html', href):
                                            urls.append(href)
                                except:
                                    continue
                            urls = list(dict.fromkeys(urls))
                            if urls:
                                return urls
                    except Exception:
                        pass

                    # 方法3：运行 JS 扫描页面上所有链接，收集带 item.jd.com 或 匹配 item id 的链接
                    try:
                        js_collect = '''
                        (function(){
                            var hrefs = Array.from(document.querySelectorAll('a')).map(a=>a.href || a.getAttribute('href')||'');
                            hrefs = hrefs.filter(function(h){ if(!h) return false; return h.indexOf('item.jd.com')!==-1 || /\\/\\d+\\.html/.test(h); });
                            // 规范化协议-相对链接
                            hrefs = hrefs.map(function(h){ if(h.indexOf('http')!==0 && h.indexOf('//')===0) return 'https:'+h; return h; });
                            return Array.from(new Set(hrefs));
                        })();
                        '''
                        try:
                            collected = self.page.run_js(js_collect) or []
                        except Exception:
                            collected = []
                        if collected:
                            for h in collected:
                                try:
                                    if h and isinstance(h, str):
                                        urls.append(h)
                                except:
                                    continue
                            urls = list(dict.fromkeys(urls))
                            if urls:
                                return urls
                    except Exception:
                        pass

                except Exception:
                    # 若专门处理失败，则退回到通用方法
                    pass

            all_links = self.page.eles('tag:a')

            # 根据站点模式匹配
            patterns = self.site_detail_configs[site]['item_url_patterns']

            for link in all_links:
                try:
                    href = link.attr('href') or ''
                    if not href:
                        continue

                    # 规范化 href：处理 // 开头和相对链接
                    if href.startswith('//'):
                        href_norm = 'https:' + href
                    elif href.startswith('/'):
                        try:
                            href_norm = urljoin(self.page.url, href)
                        except:
                            href_norm = href
                    else:
                        href_norm = href

                    # 检查是否匹配商品URL模式或简单包含关键域名
                    matched = False
                    for pattern in patterns:
                        try:
                            if re.search(pattern, href_norm, re.IGNORECASE):
                                urls.append(href_norm)
                                matched = True
                                break
                        except:
                            continue

                    # 额外增强判断：对于京东，如果 href 中包含 'item.jd.com' 也算
                    if (not matched) and site == 'jd' and 'item.jd.com' in href_norm:
                        urls.append(href_norm)

                except Exception:
                    continue

            # 去重
            urls = list(dict.fromkeys(urls))

        except Exception as e:
            print(f"提取商品链接失败: {e}")

        return urls

    def _extract_product_details(self, site: str, product_url: str) -> Dict:
        """
        提取商品详细信息
        """
        details = {
            'platform': self.site_detail_configs[site]['name'],
            'url': product_url,
            'title': '',
            'price': '',
            'original_price': '',
            'sales': '',
            'shop_name': '',
            'shop_url': '',
            'description': '',
            'specifications': {},
            'images': [],
            'rating': '',
            'comments_count': '',
            'stock': '',
            'sku_info': '',
            'coupons': [],
            'promotions': [],
            'crawl_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 根据站点配置提取信息
        selectors = self.site_detail_configs[site]['detail_selectors']

        # 1. 提取标题
        details['title'] = self._extract_with_selectors(selectors.get('title', []))

        # 2. 提取价格（特别处理京东）
        if site == 'jd':
            # 提取商品ID用于京东价格选择器
            item_id = self._extract_jd_item_id(product_url)
            if item_id:
                # 京东价格是动态的，可能需要特殊处理
                price_selector = f'.J-p-{item_id}'
                details['price'] = self._extract_price_jd_special(price_selector)

        if not details['price']:
            details['price'] = self._extract_with_selectors(selectors.get('price', []))

        # 3. 提取原价
        details['original_price'] = self._extract_with_selectors(selectors.get('original_price', []))

        # 4. 提取销量
        details['sales'] = self._extract_with_selectors(selectors.get('sales', []))

        # 5. 提取店铺信息
        details['shop_name'] = self._extract_with_selectors(selectors.get('shop_name', []))
        details['shop_url'] = self._extract_link_with_selectors(selectors.get('shop_link', []))

        # 6. 提取描述（可能需要点击查看详情）
        details['description'] = self._extract_description(site)

        # 7. 提取规格参数
        details['specifications'] = self._extract_specifications(selectors.get('specs', []))

        # 8. 提取图片
        details['images'] = self._extract_images(selectors.get('images', []))

        # 9. 提取其他信息
        details['rating'] = self._extract_with_selectors(selectors.get('rating', []))
        details['comments_count'] = self._extract_with_selectors(selectors.get('comments_count', []))
        details['stock'] = self._extract_with_selectors(selectors.get('stock', []))
        details['sku_info'] = self._extract_with_selectors(selectors.get('sku', []))

        # 10. 清理和格式化数据
        details = self._clean_details(details)
        # 补充 style/color/discount 方便后续 API 使用
        details = self._enrich_details(details)

        return details

    def _extract_with_selectors(self, selectors: List[str]) -> str:
        """使用多个选择器尝试提取文本"""
        for selector in selectors:
            try:
                element = self.page.ele(selector, timeout=2)
                if element:
                    text = element.text.strip()
                    if text:
                        return text
            except:
                continue
        return ''

    def _extract_link_with_selectors(self, selectors: List[str]) -> str:
        """使用多个选择器尝试提取链接"""
        for selector in selectors:
            try:
                element = self.page.ele(selector, timeout=2)
                if element:
                    href = element.attr('href')
                    if href:
                        if href.startswith('//'):
                            return 'https:' + href
                        elif not href.startswith('http'):
                            return urljoin(self.page.url, href)
                        else:
                            return href
            except:
                continue
        return ''

    def _extract_price_jd_special(self, selector: str) -> str:
        """特殊处理京东价格（京东价格经常是动态加载的）"""
        try:
            # 方法1：直接选择器
            element = self.page.ele(selector, timeout=3)
            if element:
                return element.text.strip()

            # 方法2：查找价格相关的元素
            price_elements = self.page.eles('.price, [class*="price"], [class*="Price"]')
            for elem in price_elements:
                text = elem.text.strip()
                if text and any(char in text for char in ['¥', '￥', '.']):
                    # 提取数字价格
                    match = re.search(r'[\d.,]+', text)
                    if match:
                        return match.group()

            # 方法3：在页面文本中搜索价格
            page_text = self.page.text
            price_patterns = [
                r'¥\s*([\d\.,]+)',
                r'￥\s*([\d\.,]+)',
                r'京东价[:：]\s*([\d\.,]+)'
            ]

            for pattern in price_patterns:
                match = re.search(pattern, page_text)
                if match:
                    return match.group(1)

        except Exception as e:
            print(f"提取京东价格失败: {e}")

        return ''

    def _extract_description(self, site: str) -> str:
        """提取商品描述（可能需要交互）"""
        description = ''

        try:
            # 尝试点击"查看详情"等按钮
            detail_buttons = [
                '查看详情', '商品详情', '图文详情',
                '查看图文详情', '产品详情', '详情介绍'
            ]

            for button_text in detail_buttons:
                try:
                    button = self.page.ele(f'text:{button_text}', timeout=2)
                    if button:
                        button.click()
                        time.sleep(3)
                        break
                except:
                    continue

            # 尝试提取描述内容
            if site == 'jd':
                # 京东描述在iframe中
                try:
                    iframe = self.page.ele('#product-detail iframe', timeout=3)
                    if iframe:
                        # 切换到iframe
                        self.page.switch_to_frame(iframe)
                        desc_element = self.page.ele('body', timeout=3)
                        if desc_element:
                            description = desc_element.text[:2000]  # 限制长度
                        self.page.switch_to_frame()
                except:
                    pass

            # 通用描述提取
            desc_selectors = [
                '.detail-content', '.product-detail', '.desc-content',
                '#description', '.tb-detail-content'
            ]

            for selector in desc_selectors:
                try:
                    element = self.page.ele(selector, timeout=2)
                    if element:
                        description = element.text[:2000]
                        break
                except:
                    continue

        except Exception as e:
            print(f"提取描述失败: {e}")

        return description

    def _extract_specifications(self, selectors: List[str]) -> Dict:
        """提取规格参数"""
        specs = {}

        for selector in selectors:
            try:
                spec_elements = self.page.eles(selector)
                for element in spec_elements:
                    text = element.text.strip()
                    if text and '：' in text:
                        # 解析键值对
                        lines = text.split('\n')
                        for line in lines:
                            if '：' in line:
                                key, value = line.split('：', 1)
                                specs[key.strip()] = value.strip()
                    elif ':' in text:
                        # 英文冒号分隔
                        lines = text.split('\n')
                        for line in lines:
                            if ':' in line:
                                key, value = line.split(':', 1)
                                specs[key.strip()] = value.strip()
            except:
                continue

        return specs

    def _extract_images(self, selectors: List[str]) -> List[str]:
        """提取商品图片"""
        images = []

        for selector in selectors:
            try:
                img_elements = self.page.eles(selector)
                for img in img_elements:
                    src = img.attr('src') or img.attr('data-src') or img.attr('data-original')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif not src.startswith('http'):
                            src = urljoin(self.page.url, src)
                        images.append(src)
            except:
                continue

        return images

    def _scroll_page_gradually(self):
        """逐步滚动页面"""
        print("滚动页面加载内容...")

        # 多次滚动
        for i in range(5):
            try:
                scroll_distance = 500 + i * 200
                self.page.scroll.down(scroll_distance)
                time.sleep(1.5 + i * 0.3)
            except:
                pass

    def _detect_site_from_url(self, url: str) -> Optional[str]:
        """从URL检测站点"""
        for site, config in self.site_detail_configs.items():
            for pattern in config['item_url_patterns']:
                if re.search(pattern, url, re.IGNORECASE):
                    return site
        return None

    def _extract_jd_item_id(self, url: str) -> Optional[str]:
        """从京东URL提取商品ID"""
        match = re.search(r'item\.jd\.com/(\d+)\.html', url)
        if match:
            return match.group(1)
        return None

    def _extract_product_details_auto(self, product_url: str) -> Dict:
        """自动提取商品详情（当无法识别站点时使用）"""
        print("⚠️ 无法识别站点，使用通用提取方法")

        details = {
            'platform': '未知',
            'url': product_url,
            'title': '',
            'price': '',
            'description': '',
            'crawl_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            # 通用选择器尝试提取
            # 1. 标题
            title_selectors = ['h1', '.title', '.product-title', '.goods-title', '[class*="title"]']
            details['title'] = self._extract_with_selectors(title_selectors)

            # 2. 价格
            price_selectors = [
                '.price', '.product-price', '.goods-price',
                '[class*="price"]', '[class*="Price"]'
            ]
            details['price'] = self._extract_with_selectors(price_selectors)

            # 3. 描述
            desc_selectors = ['.description', '.product-desc', '.goods-desc', '[class*="desc"]']
            details['description'] = self._extract_with_selectors(desc_selectors)

            # 4. 图片
            img_selectors = ['.main-img img', '.product-img img', '.goods-img img']
            details['images'] = self._extract_images(img_selectors)

        except Exception as e:
            print(f"通用提取失败: {e}")

        return details

    def _clean_details(self, details: Dict) -> Dict:
        """清理和格式化详情数据"""
        # 清理价格
        for price_field in ['price', 'original_price']:
            if details.get(price_field):
                # 提取数字
                match = re.search(r'[\d.,]+', details[price_field])
                if match:
                    details[price_field] = match.group().replace(',', '')

        # 清理销量
        if details.get('sales'):
            # 提取数字
            match = re.search(r'[\d.]+' , details['sales'])
            if match:
                details['sales'] = match.group()

        # 清理标题和描述
        if details.get('title'):
            details['title'] = details['title'].strip()
            if len(details['title']) > 200:
                details['title'] = details['title'][:197] + '...'

        if details.get('description'):
            details['description'] = details['description'].strip()
            if len(details['description']) > 3000:
                details['description'] = details['description'][:2997] + '...'

        return details

    def _to_float_price(self, price_str: str) -> Optional[float]:
        """把价格字符串转换为 float，失败返回 None。"""
        try:
            if not price_str:
                return None
            m = re.search(r'[\d.,]+', str(price_str))
            if not m:
                return None
            num = m.group().replace(',', '')
            return float(num)
        except Exception:
            return None

    def _enrich_details(self, details: Dict) -> Dict:
        """从规格参数和价格推断出 style/color/discount 等便于后续 API 使用的字段。"""
        try:
            specs = details.get('specifications') or {}

            def find_in_specs(keys):
                for key in keys:
                    for k, v in specs.items():
                        if key in k or key in str(v):
                            return v
                return ''

            # 风格/样式
            style = find_in_specs(['风格', '样式', '款式', 'style']) or ''
            # 颜色
            color = find_in_specs(['颜色', '色系', '颜色分类', 'color']) or ''

            # 折扣：优先使用已有的促销/优惠信息，否则通过原价和当前价计算
            discount = ''
            # 查看 coupons/promotions 字段
            coupons = details.get('coupons') or []
            promotions = details.get('promotions') or []
            if coupons:
                discount = ';'.join([str(c) for c in coupons])
            elif promotions:
                discount = ';'.join([str(p) for p in promotions])
            else:
                # 计算基于原价和价格的降幅
                p = self._to_float_price(details.get('price', ''))
                op = self._to_float_price(details.get('original_price', ''))
                if p and op and op > 0 and p < op:
                    percent_off = round((1 - (p / op)) * 100, 1)
                    discount = f"{percent_off}%"

            # 将新字段写回 details
            details['style'] = style
            details['color'] = color
            details['discount'] = discount

            return details
        except Exception:
            return details

    def save_details(self, products: List[Dict], filename: str = None):
        """保存商品详情"""
        if not products:
            print("⚠️ 没有商品数据可保存")
            return

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"product_details_{timestamp}.json"

        try:
            # 保存为JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)

            print(f"✅ 商品详情已保存到: {filename}")

            # 同时保存为CSV
            csv_filename = filename.replace('.json', '.csv')
            self._save_details_to_csv(products, csv_filename)

        except Exception as e:
            print(f"❌ 保存失败: {e}")

    def _save_details_to_csv(self, products: List[Dict], filename: str):
        """保存商品详情为CSV"""
        try:
            if not products:
                return

            # 准备CSV数据
            csv_data = []
            for product in products:
                # 规格参数转换为字符串
                specs_str = '; '.join([f'{k}: {v}' for k, v in product.get('specifications', {}).items()])
                images_str = '; '.join(product.get('images', [])[:3])  # 只保存前3张图片

                csv_row = {
                    '平台': product.get('platform', ''),
                    '商品标题': product.get('title', ''),
                    '价格': product.get('price', ''),
                    '原价': product.get('original_price', ''),
                    '销量': product.get('sales', ''),
                    '店铺名称': product.get('shop_name', ''),
                    '店铺链接': product.get('shop_url', ''),
                    '描述': product.get('description', '')[:500],  # 限制长度
                    '规格参数': specs_str,
                    '评分': product.get('rating', ''),
                    '评论数': product.get('comments_count', ''),
                    '库存': product.get('stock', ''),
                    '图片': images_str,
                    '商品链接': product.get('url', ''),
                    '爬取时间': product.get('crawl_time', ''),
                    '风格/样式': product.get('style', ''),
                    '颜色': product.get('color', ''),
                    '折扣': product.get('discount', '')
                }
                csv_data.append(csv_row)

            # 写入CSV
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                fieldnames = list(csv_data[0].keys()) if csv_data else []
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)

            print(f"✅ CSV文件已保存: {filename}")

        except Exception as e:
            print(f"⚠️ 保存CSV失败: {e}")

    def close(self):
        """关闭浏览器"""
        if self.page:
            try:
                self.page.quit()
                print("✅ 浏览器已关闭")
            except:
                pass

    def _is_logged_in_site(self, site: str) -> bool:
        """基于站点特定的页面元素判断是否已登录，返回 True 表示已登录。"""
        try:
            # 给页面一些时间渲染动态内容
            time.sleep(2)

            page_text = (self.page.text or '')[:5000]

            # 尝试通过 document.cookie 判断（更可靠），需要浏览器页面已加载
            cookies_str = ''
            try:
                cookies_str = self.page.run_js("return document.cookie") or ''
            except Exception:
                cookies_str = ''

            if site == 'taobao':
                # Cookie-based check for Taobao
                if cookies_str and any(k in cookies_str for k in ['cookie2', 'cna', 't', 'unb', 'thw']):
                    return True
                # 未登录页面通常包含提示 '亲，请登录' 或 '请登录'
                if '亲，请登录' in page_text or '请登录' in page_text:
                    return False

                # 已登录时会有 '我的淘宝'、用户名或用户头像（'我的淘宝' 是较稳健的信号）
                if '我的淘宝' in page_text or '我的购物车' in page_text:
                    return True

                # 尝试通过元素识别：优先查找用户菜单或用户名
                try:
                    user_ele = self.page.ele('css:.site-nav-user, css:#J_MyTaobao, text:我的淘宝', timeout=2)
                    if user_ele:
                        # 若元素存在且有文本，且不是登录提示，则视为已登录
                        txt = (user_ele.text or '').strip()
                        if txt and '登录' not in txt:
                            return True
                        # 元素存在但没有文本（可能是头像），也可认为已登录
                        if not txt:
                            return True
                except Exception:
                    pass

                return False

            elif site == 'jd':
                # Cookie-based check for JD (pt_key/pt_pin 或 unick/pin 表示登录)
                if cookies_str and any(k in cookies_str for k in ['pt_key', 'pt_pin', 'unick', 'pin']):
                    return True
                # 京东未登录顶部通常显示 '请登录'，已登录会显示用户名或'您好'
                if '请登录' in page_text or '登录' in page_text and '我的京东' not in page_text:
                    # ambiguous: check element text
                    pass

                try:
                    tt = self.page.ele('css:#ttbar-login', timeout=2)
                    if tt and tt.text:
                        txt = tt.text.strip()
                        # 如果包含'请登录'或'登录'则表示未登录
                        if '请登录' in txt or '登录' in txt:
                            return False
                        # 否则包含用户名或问候语，视为已登录
                        return True
                except Exception:
                    pass

                # 检查常见用户名元素
                try:
                    nick = self.page.ele('css:.nickname', timeout=2)
                    if nick and (nick.text or '').strip():
                        return True
                except Exception:
                    pass

                # 最后基于页面文本的启发式判断
                if '您好' in page_text or '我的订单' in page_text or '我的京东' in page_text:
                    return True

                return False

            else:
                return False

        except Exception:
            return False


def main():
    """主函数"""
    print("=" * 60)
    print("国内电商平台商品详情爬虫")
    print("=" * 60)
    print("支持：直接爬取商品详情页或搜索后爬取")
    print("=" * 60)

    try:
        # 创建爬虫
        crawler = ChineseEcommerceDetailCrawler(
            headless=False,  # 显示浏览器窗口
            use_saved_login=True
        )

        print("\n请选择爬取方式：")
        print("1. 直接输入商品URL爬取")
        print("2. 搜索关键词后爬取商品详情")
        print("3. 批量爬取多个商品")

        choice = input("请输入选择 (1-3): ").strip()

        if choice == '1':
            # 方式1：直接输入URL
            product_url = input("\n请输入商品详情页URL: ").strip()
            if product_url:
                details = crawler.get_product_details_from_url(product_url)
                if details:
                    print(f"\n✅ 商品详情爬取成功！")
                    print(f"标题: {details.get('title')}")
                    print(f"价格: {details.get('price')}")
                    print(f"销量: {details.get('sales')}")
                    print(f"店铺: {details.get('shop_name')}")
                    crawler.save_details([details])

        elif choice == '2':
            # 方式2：搜索后爬取
            print("\n请选择平台：")
            print("1. 京东")
            print("2. 淘宝")
            print("3. 天猫")
            print("4. 1688")

            site_choice = input("请输入选择 (1-4): ").strip()
            site_map = {'1': 'jd', '2': 'taobao', '3': 'tmall', '4': '1688'}
            site = site_map.get(site_choice, 'jd')

            keyword = input(f"\n请输入在 {crawler.site_detail_configs[site]['name']} 搜索的关键词: ").strip()
            if not keyword:
                keyword = "手机"  # 默认关键词

            max_items = input("请输入最多爬取商品数量 (默认5): ").strip()
            max_items = int(max_items) if max_items.isdigit() else 5

            # 执行搜索并爬取详情
            details_list = crawler.search_and_get_details(site, keyword, max_items)

            # 打印结果
            if details_list:
                print(f"\n✅ 成功爬取 {len(details_list)} 个商品的详情")
                for details in details_list:
                    print(f"标题: {details.get('title')}, 价格: {details.get('price')}, 店铺: {details.get('shop_name')}")
                # 自动保存为 JSON 和 CSV
                try:
                    crawler.save_details(details_list)
                except Exception as e:
                    print(f"⚠️ 保存结果时出错: {e}")
            else:
                print("⚠️ 未找到符合条件的商品")

        elif choice == '3':
            # 方式3：批量爬取
            file_path = input("\n请输入包含商品链接的文本文件路径: ").strip()
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f.readlines() if line.strip()]

                all_details = []
                for i, url in enumerate(urls, 1):
                    print(f"\n📦 正在爬取第 {i}/{len(urls)} 个商品...")
                    details = crawler.get_product_details_from_url(url)
                    if details:
                        all_details.append(details)
                        print(f"✅ 成功爬取: {details.get('title', '未知')[:50]}...")

                    # 随机延迟，避免被封
                    if i < len(urls):
                        delay = random.uniform(3, 8)
                        print(f"⏳ 等待 {delay:.1f} 秒后爬取下一个商品...")
                        time.sleep(delay)

                print(f"\n🎉 完成！成功爬取 {len(all_details)} 个商品的详情")
                # 保存结果
                crawler.save_details(all_details)
            else:
                print("❌ 文件不存在")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

    finally:
        # 确保关闭浏览器（仅当 crawler 已成功创建时）
        try:
            if 'crawler' in locals() and locals().get('crawler'):
                locals().get('crawler').close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
