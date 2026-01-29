import requests
import json
import os
import time
import random
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re as re_mod
import urllib.parse
from urllib.parse import urlparse, urljoin
from abc import ABC, abstractmethod
import yaml
import sys

# 获取当前Python文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))


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

        # ===== runtime 可调参数（可在 sites_config.yaml -> runtime 覆盖） =====
        runtime_cfg = site_config.get('runtime', {}) or {}
        self.log_dedup_window = float(runtime_cfg.get('log_dedup_window', 10))
        self.status_log_dedup_window = float(runtime_cfg.get('status_log_dedup_window', 2))
        self.cookie_refresh_min_interval = float(runtime_cfg.get('cookie_refresh_min_interval', 5))
        self.cookie_refresh_backoff = float(runtime_cfg.get('cookie_refresh_backoff', 30))
        self.cookie_refresh_notice_dedup_window = float(runtime_cfg.get('cookie_refresh_notice_dedup_window', 10))

        # fetcher: requests | playwright | auto
        self.fetcher_mode = (runtime_cfg.get('fetcher', 'requests') or 'requests').strip().lower()

        # Playwright 抓取/捕获时是否无头（不弹窗）。默认 True。
        # 注意：auth.headed 更适合用于人工登录/保存 storage_state 的场景。
        self.playwright_headless = bool(runtime_cfg.get('playwright_headless', True))

        # ===== playwright: 捕获真实请求头（用于回灌到 requests） =====
        pch = (runtime_cfg.get('playwright_capture_headers', {}) or {})
        self.pch_enabled = bool(pch.get('enabled', False))
        trigger = (pch.get('trigger', {}) or {})
        self.pch_trigger_on_start = bool(trigger.get('on_start', True))
        self.pch_trigger_on_verification = bool(trigger.get('on_verification', True))
        self.pch_every_n_requests = int(trigger.get('every_n_requests', 0) or 0)

        match_cfg = (pch.get('match', {}) or {})
        self.pch_url_regex = match_cfg.get('url_regex')  # None 表示匹配任意
        self.pch_resource_types = match_cfg.get('resource_types') or ['document']
        # 兼容用户写成字符串
        if isinstance(self.pch_resource_types, str):
            self.pch_resource_types = [self.pch_resource_types]
        self.pch_first_match_only = bool(match_cfg.get('first_match_only', True))

        persist_cfg = (pch.get('persist', {}) or {})
        self.pch_persist_enabled = bool(persist_cfg.get('enabled', True))
        self.pch_persist_path = persist_cfg.get('path') or f'captured_headers_{self.site_name}.json'
        self.pch_ttl_seconds = int(persist_cfg.get('ttl_seconds', 3600) or 3600)

        policy_cfg = (pch.get('apply_policy', {}) or {})
        self.pch_override = bool(policy_cfg.get('override', True))
        self.pch_allowlist = policy_cfg.get('allowlist')
        self.pch_denylist = policy_cfg.get('denylist')
        # 命中验证页时，是否把 Playwright context cookies 回灌到 requests（默认关闭，避免引入不确定性）
        self.pch_apply_cookies = bool(policy_cfg.get('apply_cookies', False))

        # 默认策略：尽量只回灌“浏览器指纹头”，避免把敏感 cookie/authorization 固化到本地
        if not self.pch_allowlist:
            self.pch_allowlist = [
                'accept',
                'accept-encoding',
                'accept-language',
                'cache-control',
                'pragma',
                'sec-ch-ua',
                'sec-ch-ua-mobile',
                'sec-ch-ua-platform',
                'sec-fetch-dest',
                'sec-fetch-mode',
                'sec-fetch-site',
                'sec-fetch-user',
                'upgrade-insecure-requests',
                'user-agent',
                # 站点可能需要的补充
                'dnt',
            ]
        if not self.pch_denylist:
            self.pch_denylist = ['cookie', 'authorization', 'proxy-authorization']

        self._captured_headers: dict = {}
        self._captured_headers_meta: dict = {}
        self._request_count = 0
        self._playwright_capture_attempted = False

        # ===== auth（浏览器登录态复用 / Playwright storage_state） =====
        auth_cfg = site_config.get('auth', {}) or {}
        self.auth_enabled = bool(auth_cfg.get('enabled', False))
        self.auth_provider = (auth_cfg.get('provider', 'playwright') or 'playwright').strip().lower()
        self.auth_storage_state_path = auth_cfg.get('storage_state_path')
        self.auth_login_url = auth_cfg.get('login_url') or (self.base_url or '')
        self.auth_headed = bool(auth_cfg.get('headed', True))
        self.auth_auto_on_verification = bool(auth_cfg.get('auto_on_verification', True))

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
        self.proxies: dict | None = None

        # Cookies管理
        self.cookies: dict = {}
        self.cookies_file = os.path.join(current_dir, f'cookies_{self.site_name}.json')

        # 数据保存目录
        self.data_dir = os.path.join(current_dir, 'ecommerce_data', self.site_name)

        # 去重日志与刷新控制（确保在 init_cookies 之前设置）
        self._last_log = {'msg': None, 'time': 0.0}
        self._last_cookie_refresh_time = 0.0

        # 尝试加载已持久化的捕获请求头（如果 enabled）
        self._load_persisted_captured_headers()

        # 初始化
        self.init_cookies()
        self.create_directories()

        # 调试：是否保存“验证页/无效页/空结果页”的 HTML 到 logs。
        # 默认关闭，避免 logs 过多；需要排查时可在 sites_config.yaml 打开：runtime.debug_save_bad_pages: true
        self.debug_save_bad_pages = bool(runtime_cfg.get('debug_save_bad_pages', False))

    # ==================== Playwright 捕获请求头相关 ====================

    def _resolve_pch_path(self):
        path = self.pch_persist_path
        if not path:
            return None
        if not os.path.isabs(path):
            path = os.path.join(current_dir, path)
        return path

    def _load_persisted_captured_headers(self):
        """加载已落盘的捕获请求头（在 TTL 内才使用）。"""
        if not self.pch_enabled or not self.pch_persist_enabled:
            return
        path = self._resolve_pch_path()
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f) or {}
            headers = payload.get('headers') or {}
            meta = payload.get('meta') or {}
            ts = float(meta.get('captured_at', 0) or 0)
            if self.pch_ttl_seconds > 0 and ts > 0 and (time.time() - ts) > self.pch_ttl_seconds:
                return
            if isinstance(headers, dict) and headers:
                self.apply_captured_headers(headers, persist=False, log=True)
                self._captured_headers_meta = meta
        except Exception:
            # 静默失败，不影响主流程
            return

    def _filter_captured_headers(self, headers: dict) -> dict:
        if not headers:
            return {}
        allow = set(k.lower() for k in (self.pch_allowlist or []))
        deny = set(k.lower() for k in (self.pch_denylist or []))
        filtered = {}
        for k, v in headers.items():
            lk = str(k).lower()
            if lk in deny:
                continue
            if allow and lk not in allow:
                continue
            if v is None:
                continue
            filtered[lk] = str(v)
        return filtered

    def apply_captured_headers(self, captured: dict, persist: bool = True, log: bool = False):
        """把 Playwright 捕获的 headers 回灌到 requests 的默认 headers。"""
        if not captured or not isinstance(captured, dict):
            return

        filtered = self._filter_captured_headers(captured)
        if not filtered:
            return

        # 合并策略：override=True 时，以 captured 为准；否则只补缺
        if self.pch_override:
            for k, v in filtered.items():
                self.base_headers[k] = v
        else:
            for k, v in filtered.items():
                if k not in self.base_headers:
                    self.base_headers[k] = v

        # 同步到 session headers（requests 以后每次 get_headers 也会返回合并结果）
        self.session.headers.update(self.base_headers)

        self._captured_headers = dict(filtered)
        self._captured_headers_meta = {
            'captured_at': time.time(),
            'site': self.site_name,
            'base_url': self.base_url,
        }

        if log:
            keys = ', '.join(sorted(list(filtered.keys()))[:20])
            self._log(f"已应用 Playwright 捕获请求头（{len(filtered)}项），keys: {keys}", dedup_seconds=5)

        if persist and self.pch_enabled and self.pch_persist_enabled:
            path = self._resolve_pch_path()
            if path:
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump({'headers': filtered, 'meta': self._captured_headers_meta}, f, ensure_ascii=False, indent=2)
                except Exception:
                    # 静默失败
                    pass

    def _playwright_capture_headers(self, url: str) -> dict | None:
        """使用 Playwright 打开页面并监听网络请求，提取匹配请求的 headers。"""
        if not self.pch_enabled:
            return None
        if not self.auth_enabled:
            # 捕获也依赖登录态/浏览器环境（尤其是 Amazon），沿用已有开关
            self._log("Playwright 捕获请求头未启用：请在 sites_config.yaml 设置 auth.enabled: true", dedup_seconds=30)
            return None
        if self.auth_provider != 'playwright':
            return None

        storage_state = self._resolve_storage_state_path()
        if not storage_state or not os.path.exists(storage_state):
            self._log(
                f"未找到登录态文件: {storage_state}。请先运行 capture_state.py 保存登录态后再启用请求头捕获。",
                dedup_seconds=30,
            )
            return None

        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self._log("未安装 Playwright。请执行: pip install -r requirements.txt 以及 playwright install", dedup_seconds=30)
            return None

        import re as _re

        matched_headers = None
        url_pattern = None
        if self.pch_url_regex:
            try:
                url_pattern = _re.compile(self.pch_url_regex)
            except Exception:
                url_pattern = None

        resource_types = set([str(x).lower() for x in (self.pch_resource_types or [])])
        if not resource_types:
            resource_types = {'document'}

        def on_request(req):
            nonlocal matched_headers
            try:
                if matched_headers is not None and self.pch_first_match_only:
                    return

                if req.resource_type and str(req.resource_type).lower() not in resource_types:
                    return

                rurl = req.url or ''
                if url_pattern and not url_pattern.search(rurl):
                    return

                # 捕获 headers
                matched_headers = dict(req.headers or {})
            except Exception:
                return

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.playwright_headless)
                context = browser.new_context(storage_state=storage_state)
                page = context.new_page()
                page.on('request', on_request)

                page.goto(url, wait_until='domcontentloaded', timeout=60000)

                # 给一点时间让子请求/XHR 发出（尤其当 resource_types 包含 fetch/xhr 时）
                try:
                    page.wait_for_timeout(1500)
                except Exception:
                    pass

                context.close()
                browser.close()

            return matched_headers
        except Exception as e:
            self._log(f"Playwright 捕获请求头失败: {e}", dedup_seconds=30)
            return None

    def _maybe_capture_headers(self, trigger: str, url_for_capture: str):
        """按配置触发一次捕获（失败不影响主流程）。"""
        if not self.pch_enabled:
            return

        # 已有可用 headers 就不重复捕获
        if self._captured_headers:
            return

        # 避免每次请求都启动浏览器
        if trigger == 'on_start':
            if not self.pch_trigger_on_start:
                return
            if self._playwright_capture_attempted:
                return
        elif trigger == 'on_verification':
            if not self.pch_trigger_on_verification:
                return
        elif trigger == 'periodic':
            if self.pch_every_n_requests <= 0:
                return
            if self._request_count % self.pch_every_n_requests != 0:
                return

        self._playwright_capture_attempted = True
        self._log("尝试使用 Playwright 捕获真实请求头...", dedup_seconds=10)
        captured = self._playwright_capture_headers(url_for_capture)
        if captured:
            self.apply_captured_headers(captured, persist=True, log=True)
        else:
            self._log("未捕获到请求头（将继续使用默认 headers）", dedup_seconds=30)

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

    def _log(self, msg, dedup_seconds: float | int | None = None):
        """去重打印，避免短时间内重复输出相同信息"""
        now = time.time()
        # 允许调用方传 None/0 表示使用默认窗口
        window = self.log_dedup_window if not dedup_seconds else float(dedup_seconds)
        if msg == self._last_log.get('msg') and (now - self._last_log.get('time', 0)) < window:
            return
        print(msg)
        self._last_log['msg'] = msg
        self._last_log['time'] = now

    def init_cookies(self):
        """初始化cookies"""
        self._log(f"正在初始化 {self.site_name} 的cookies...", dedup_seconds=5)

        # 尝试从文件加载cookies
        if os.path.exists(self.cookies_file):
            try:
                with open(self.cookies_file, 'r') as f:
                    saved_cookies = json.load(f)
                    self.cookies = saved_cookies
                    self.session.cookies.update(self.cookies)
                    self._log(f"从文件加载了 {len(self.cookies)} 个cookies", dedup_seconds=5)
                    return
            except Exception as e:
                self._log(f"加载cookies文件失败: {e}", dedup_seconds=30)

        # 尝试获取初始cookies
        self.refresh_cookies()

    def refresh_cookies(self):
        """刷新cookies"""
        # 防止短时间内重复刷新或重复提示
        now = time.time()
        if now - self._last_cookie_refresh_time < self.cookie_refresh_min_interval:
            self._log(
                f"短时间内已刷新过 {self.site_name} 的cookies，已跳过重复刷新。",
                dedup_seconds=self.cookie_refresh_min_interval,
            )
            return

        self._log(f"刷新 {self.site_name} 的cookies...", dedup_seconds=self.cookie_refresh_min_interval)
        try:
            response = self.session.get(self.base_url, timeout=10)
            self.cookies = self.session.cookies.get_dict()

            if self.cookies:
                # 保存cookies到文件
                with open(self.cookies_file, 'w') as f:
                    json.dump(self.cookies, f)
                self._log(f"成功获取并保存 {len(self.cookies)} 个cookies", dedup_seconds=self.cookie_refresh_min_interval)
            else:
                self._log("未获取到cookies，使用默认配置", dedup_seconds=30)

            # 记录刷新时间
            self._last_cookie_refresh_time = time.time()

        except Exception as e:
            self._log(f"刷新cookies时出错: {e}", dedup_seconds=30)

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

        # 如果已捕获浏览器 UA，则优先使用；否则走随机 UA
        if 'user-agent' not in (self._captured_headers or {}):
            headers['user-agent'] = self.get_random_user_agent()

        if referer:
            headers['referer'] = referer

        # 添加网站特定的headers
        site_headers: dict = self.site_config.get('headers', {}) or {}
        headers.update(site_headers)

        return headers

    def make_request(self, url, max_retries=3):
        """发送请求"""
        self._request_count += 1

        # 触发一次性/周期性捕获（不会影响后续逻辑，失败会降级）
        # 用 url 本身更贴近实际；也可改成 self.base_url
        self._maybe_capture_headers('on_start', url)
        self._maybe_capture_headers('periodic', url)

        # 如果用户强制使用 Playwright，则直接走浏览器抓取
        if self.fetcher_mode == 'playwright':
            html = self._playwright_get_html(url)
            if html is None:
                return None
            return self._fake_response(url=url, html=html, status_code=200)

        for attempt in range(max_retries):
            try:
                headers = self.get_headers(referer=self.base_url)

                response = self.session.get(
                    url,
                    headers=headers,
                    cookies=(self.cookies or {}),
                    proxies=self.proxies,
                    timeout=30,
                    allow_redirects=True,
                    verify=True
                )

                self._log(
                    f"状态码: {response.status_code}, URL: {url[:80]}...",
                    dedup_seconds=self.status_log_dedup_window,
                )

                # 200 但页面是 Amazon 无效页：保存并按“坏页面”处理
                if response.status_code == 200 and self.is_not_functioning_page(response):
                    self._log("检测到 Amazon 无效页面(not a functioning page)。可能是登录入口/重定向参数失效或地区跳转导致。", dedup_seconds=30)
                    self._save_debug_html('not_functioning', url, response.text)

                    # auto 模式：优先用 Playwright 再试一次
                    if (
                        self.fetcher_mode == 'auto'
                        and self.auth_enabled
                        and self.auth_provider == 'playwright'
                        and self.auth_auto_on_verification
                    ):
                        self._log("无效页触发 auto 模式：尝试用 Playwright 重新获取页面...", dedup_seconds=30)
                        html, pw_cookies = self._playwright_get_html_and_cookies(url)
                        if html:
                            if self.pch_apply_cookies and pw_cookies:
                                try:
                                    self.cookies.update(pw_cookies)
                                    self.session.cookies.update(self.cookies)
                                    with open(self.cookies_file, 'w') as f:
                                        json.dump(self.cookies, f)
                                except Exception:
                                    pass
                            # 也保存一份 Playwright 抓到的页面用于对比
                            self._save_debug_html('playwright_after_not_functioning', url, html)
                            return self._fake_response(url=url, html=html, status_code=200)
                    else:
                        # 给出明确指引，避免用户以为是 cookies 问题
                        self._log(
                            "建议：在 sites_config.yaml 把 amazon.runtime.fetcher 设为 auto，并启用 amazon.auth.enabled=true，\n"
                            "再运行 capture_state.py 生成 amazon_state.json 后重试。",
                            dedup_seconds=60,
                        )

                if response.status_code == 200:
                    # 更新cookies
                    self.cookies.update(self.session.cookies.get_dict())

                    # 检查是否需要刷新cookies
                    if self.should_refresh_cookies(response):
                        # 保存验证页用于排查
                        self._save_debug_html('verification', url, response.text)
                        # 尝试捕获一次真实 headers（再继续原来的降级/刷新逻辑）
                        self._maybe_capture_headers('on_verification', url)

                        # auto 模式：检测到验证页优先切换到 Playwright（比 refresh_cookies 更有效）
                        if (
                            self.fetcher_mode == 'auto'
                            and self.auth_enabled
                            and self.auth_provider == 'playwright'
                            and self.auth_auto_on_verification
                        ):
                            self._log("检测到验证页面，优先使用 Playwright + 已保存登录态获取页面...", dedup_seconds=30)

                            html, pw_cookies = self._playwright_get_html_and_cookies(url)
                            if html:
                                if self.pch_apply_cookies and pw_cookies:
                                    try:
                                        self.cookies.update(pw_cookies)
                                        self.session.cookies.update(self.cookies)
                                        with open(self.cookies_file, 'w') as f:
                                            json.dump(self.cookies, f)
                                    except Exception:
                                        pass
                                self._save_debug_html('playwright_after_verification', url, html)
                                return self._fake_response(url=url, html=html, status_code=200)

                        # 非 auto / 或 Playwright 不可用时，才走原来的 refresh/backoff
                        if time.time() - self._last_cookie_refresh_time < self.cookie_refresh_backoff:
                            self._log(
                                "检测到可能需要刷新cookies（已在短时间内刷新过），已跳过重复提示与刷新。",
                                dedup_seconds=self.cookie_refresh_backoff,
                            )
                            time.sleep(random.uniform(5, 10))
                            continue

                        self._log(
                            "检测到可能需要刷新cookies...",
                            dedup_seconds=self.cookie_refresh_notice_dedup_window,
                        )
                        self.refresh_cookies()
                        time.sleep(random.uniform(5, 10))
                        continue

                    return response

                elif response.status_code in [403, 429]:
                    self._log(f"访问受限 ({response.status_code})，等待后重试...", dedup_seconds=30)
                    time.sleep(random.uniform(10, 20))
                    self.refresh_cookies()

                elif response.status_code == 503:
                    # Amazon 常见：503 + robot check/Service Unavailable
                    self._log(f"服务不可用 (503)，等待后重试...", dedup_seconds=30)

                    # auto 模式：503 也尝试切换 Playwright（通常比单纯 sleep 更有效）
                    if (
                        self.fetcher_mode == 'auto'
                        and self.auth_enabled
                        and self.auth_provider == 'playwright'
                        and self.auth_auto_on_verification
                    ):
                        self._save_debug_html('http_503', url, response.text)
                        self._log("503 触发 auto 模式：尝试用 Playwright 获取页面...", dedup_seconds=30)
                        html, pw_cookies = self._playwright_get_html_and_cookies(url)
                        if html:
                            if self.pch_apply_cookies and pw_cookies:
                                try:
                                    self.cookies.update(pw_cookies)
                                    self.session.cookies.update(self.cookies)
                                    with open(self.cookies_file, 'w') as f:
                                        json.dump(self.cookies, f)
                                except Exception:
                                    pass
                            self._save_debug_html('playwright_after_503', url, html)
                            return self._fake_response(url=url, html=html, status_code=200)

                    time.sleep(random.uniform(15, 25))

                else:
                    self._log(f"尝试 {attempt + 1}/{max_retries}: 状态码 {response.status_code}", dedup_seconds=5)
                    time.sleep(random.uniform(5, 8))

            except requests.exceptions.RequestException as e:
                self._log(f"尝试 {attempt + 1}/{max_retries}: 请求异常 - {e}", dedup_seconds=5)
                time.sleep(random.uniform(5, 8))

        self._log(f"请求失败: {url}", dedup_seconds=30)
        return None

    class _SimpleResponse:
        """一个最小 Response 兼容对象（只提供本项目用到的属性）"""

        def __init__(self, url: str, text: str, status_code: int = 200):
            self.url = url
            self.text = text
            self.status_code = status_code

    def _fake_response(self, url: str, html: str, status_code: int = 200):
        return self._SimpleResponse(url=url, text=html, status_code=status_code)

    def _resolve_storage_state_path(self):
        if not self.auth_storage_state_path:
            return None
        path = self.auth_storage_state_path
        if not os.path.isabs(path):
            path = os.path.join(current_dir, path)
        return path

    def _playwright_get_html(self, url: str) -> str | None:
        """使用 Playwright 获取页面 HTML（仅复用已保存登录态，不做验证码绕过）。"""
        if not self.auth_enabled:
            self._log("Playwright 抓取未启用：请在 sites_config.yaml 设置 auth.enabled: true", dedup_seconds=30)
            return None
        if self.auth_provider != 'playwright':
            self._log(f"当前 auth.provider={self.auth_provider}，不支持 Playwright 抓取", dedup_seconds=30)
            return None

        storage_state = self._resolve_storage_state_path()
        if not storage_state or not os.path.exists(storage_state):
            self._log(
                f"未找到登录态文件: {storage_state}。请先运行 capture_state.py 进行手动登录/扫码并保存登录态。",
                dedup_seconds=30,
            )
            return None

        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            self._log(
                "未安装 Playwright。请执行: pip install -r requirements.txt 以及 playwright install",
                dedup_seconds=30,
            )
            return None

        # 每次启用一个新的 context（更稳妥；也便于释放资源）。
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.playwright_headless)
                context = browser.new_context(storage_state=storage_state)
                page = context.new_page()
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                html = page.content()
                context.close()
                browser.close()
                return html
        except Exception as e:
            self._log(f"Playwright 获取页面失败: {e}", dedup_seconds=30)
            return None

    def _playwright_get_html_and_cookies(self, url: str) -> tuple[str | None, dict]:
        """用 Playwright 获取 HTML，并可选返回 cookies dict（name->value）。"""
        if not self.auth_enabled or self.auth_provider != 'playwright':
            return None, {}

        storage_state = self._resolve_storage_state_path()
        if not storage_state or not os.path.exists(storage_state):
            return None, {}

        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return None, {}

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.playwright_headless)
                context = browser.new_context(storage_state=storage_state)
                page = context.new_page()
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                html = page.content()

                cookies_dict: dict = {}
                try:
                    for c in (context.cookies() or []):
                        name = c.get('name')
                        value = c.get('value')
                        if name and value is not None:
                            cookies_dict[str(name)] = str(value)
                except Exception:
                    cookies_dict = {}

                context.close()
                browser.close()
                return html, cookies_dict
        except Exception:
            return None, {}

    def is_verification_page(self, response) -> bool:
        """更稳的验证页判断：
        - 关键词命中（captcha/signin）
        - 或者页面里出现 Amazon 常见的 robot check 表单特征
        """
        text = (getattr(response, 'text', '') or '')
        text_lower = text.lower()

        keywords = [
            'captcha',
            'robot check',
            'enter the characters',
            'ap/signin',
            'signin',
            'sign in',
        ]
        if any(k in text_lower for k in keywords):
            return True

        # Amazon robot check 页面常见结构（非常轻量，避免误判普通页面）
        if 'images-amazon.com/captcha' in text_lower:
            return True
        if 'validatecaptcha' in text_lower:
            return True

        url_lower = (getattr(response, 'url', '') or '').lower()
        if 'ap/signin' in url_lower or 'validatecaptcha' in url_lower:
            return True

        return False

    def should_refresh_cookies(self, response):
        """判断是否命中验证码/登录类页面（用于触发刷新 cookies 或切换 Playwright）。"""
        # 统一走更稳的判断
        return self.is_verification_page(response)

    def search_products(self, keyword, pages=1, get_details=False):
        """搜索商品并获取详情"""
        all_products = []

        for page in range(1, pages + 1):
            self._log(f"\n正在搜索第 {page} 页，关键词: {keyword}", dedup_seconds=2)

            search_url = self.build_search_url(keyword, page)
            self._log(f"搜索URL: {search_url}", dedup_seconds=2)

            products = []
            try:
                response = self.make_request(search_url)
                if response:
                    products = self.parse_search_results(response.text)

                    # 解析为空时，把页面落盘，便于检查到底返回了什么（验证页/无效页/结构变更）
                    if not products:
                        kind = self._classify_page(search_url, response.text)
                        self._log(f"解析结果为空，页面类型判断: {kind}", dedup_seconds=10)
                        self._save_debug_html(f"empty_{kind}", search_url, response.text)

                    if products:
                        self._log(f"第 {page} 页找到 {len(products)} 个商品", dedup_seconds=5)
                        if get_details:
                            products = self.enrich_products_with_details(products)
                        all_products.extend(products)
                    else:
                        self._log(f"第 {page} 页未找到商品", dedup_seconds=10)
            except Exception as e:
                self._log(f"搜索第 {page} 页时出错: {e}", dedup_seconds=30)
                import traceback
                traceback.print_exc()

            if products and len(products) < 3 and page > 1:
                self._log("商品数量较少，停止翻页", dedup_seconds=30)
                break

        return all_products

    def enrich_products_with_details(self, products):
        """为商品列表获取详细信息"""
        self._log("\n开始获取商品详情...", dedup_seconds=2)
        enriched_products = []

        for i, product in enumerate(products, 1):
            if 'url' in product:
                self._log(f"[{i}/{len(products)}] 获取详情: {product.get('title', 'N/A')[:50]}...", dedup_seconds=2)
                details = self.get_product_details(product['url'])
                if details:
                    product.update(details)
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
            self._log(f"获取商品详情时出错: {e}", dedup_seconds=30)
            return {}

    def download_image(self, image_url, product_id):
        """下载商品图片"""
        if not image_url or not product_id:
            return None
        try:
            headers = self.get_headers()
            response = requests.get(image_url, headers=headers, timeout=15)
            if response.status_code == 200:
                filename = f"{product_id}_{int(time.time())}.jpg"
                image_path = os.path.join(self.data_dir, 'images', filename)
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                self._log(f"✓ 图片下载成功: {filename}", dedup_seconds=30)
                return image_path
        except Exception as e:
            self._log(f"下载图片时出错: {e}", dedup_seconds=30)
        return None

    def save_to_csv(self, products, keyword):
        """保存数据到CSV文件"""
        if not products:
            self._log("没有数据可保存", dedup_seconds=30)
            return None

        fieldnames = set()
        for product in products:
            fieldnames.update(product.keys())
        fieldnames = list(fieldnames)

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
                    row[field] = str(value) if isinstance(value, (list, dict)) else value
                writer.writerow(row)

        self._log(f"\n数据已保存到: {filepath}", dedup_seconds=30)
        self._log(f"共保存 {len(products)} 条记录，包含 {len(fieldnames)} 个字段", dedup_seconds=30)
        return filepath

    def save_to_json(self, products, keyword):
        """保存数据到JSON文件"""
        if not products:
            self._log("没有数据可保存", dedup_seconds=30)
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
        filename = f"{self.site_name}_{safe_keyword}_{timestamp}.json"
        filepath = os.path.join(self.data_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(products, jsonfile, ensure_ascii=False, indent=2, default=str)

        self._log(f"数据已保存到: {filepath}", dedup_seconds=30)
        return filepath

    # =============== 公共辅助方法（解析通用） ===============
    def extract_text(self, element, selectors):
        for selector in selectors:
            elem = element.select_one(selector)
            if elem and elem.text.strip():
                return elem.text.strip()
        return None

    def extract_url(self, element):
        link_elem = element.select_one('h2 a, a.a-link-normal')
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            if href.startswith('/'):
                return urljoin(self.base_url, href)
            if 'http' in href:
                return href
        return None

    def extract_price(self, element):
        """提取价格。

        兼容 Amazon 搜索页常见结构：
        - .a-price .a-offscreen  (完整字符串，带货币符号，例如 "$12.99")
        - .a-price-whole + .a-price-fraction

        返回尽量保留原始显示（含货币符号）。
        """
        # 优先拿完整展示文本（通常含货币符号）
        price_elem = element.select_one('.a-price .a-offscreen, .s-item__price')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            return price_text or None

        # 退化：拼 whole + fraction
        whole = element.select_one('.a-price-whole')
        fraction = element.select_one('.a-price-fraction')
        if whole:
            whole_text = whole.get_text(strip=True)
            frac_text = fraction.get_text(strip=True) if fraction else ''
            # whole_text 里可能含有分组逗号/点，保持原样
            joined = f"{whole_text}.{frac_text}" if frac_text else whole_text
            return joined or None

        return None

    def extract_original_price(self, element):
        price_elem = element.select_one('.a-text-price .a-offscreen')
        if price_elem:
            return price_elem.get_text(strip=True) or None
        return None

    def extract_rating(self, element):
        rating_elem = element.select_one('.a-icon-alt, .s-item__reviews span')
        if rating_elem:
            rating_text = rating_elem.text.strip()
            match = re_mod.search(r'(\d+\.?\d*)', rating_text)
            if match:
                return match.group(1)
        return None

    def extract_reviews(self, element):
        """提取评论数。

        Amazon 搜索结果里常见：
        - span.a-size-base.s-underline-text
        - a[aria-label*="ratings"] / a[aria-label*="rating"]
        - 其它站点：.s-item__reviews-count
        """
        selectors = [
            'span.a-size-base.s-underline-text',
            'a[aria-label*="ratings" i]',
            'a[aria-label*="rating" i]',
            '.s-item__reviews-count',
        ]
        reviews_elem = None
        for sel in selectors:
            reviews_elem = element.select_one(sel)
            if reviews_elem and reviews_elem.get_text(strip=True):
                break

        if reviews_elem:
            text = reviews_elem.get_text(" ", strip=True)
            # 处理 "12,345" 或 "(1,234)" 或 "1,234 ratings"
            match = re_mod.search(r'(\d{1,3}(?:,\d{3})*|\d+)', text)
            if match:
                return match.group(1)
        return None

    def extract_purchase_hint(self, soup):
        """提取 Amazon 详情页“销量代理”字段。

        Amazon 近年来经常在标题下方/购买框附近显示：
        - "1K+ bought in past month"
        - "200+ purchased in past month"

        该字段不是所有商品都有，但对后续 API 调用做铺垫很有用。
        返回原始文本（尽量保持人类可读）。
        """
        if soup is None:
            return None

        text = soup.get_text("\n", strip=True)
        # 英文站点常见
        patterns = [
            r'([0-9,.]+\+?\s*(?:k\+?)?)\s*(?:bought|purchased)\s+in\s+past\s+month',
            r'([0-9,.]+\+?\s*(?:k\+?)?)\s*(?:bought|purchased)\s+in\s+the\s+past\s+month',
        ]
        lower = text.lower()
        for pat in patterns:
            m = re_mod.search(pat, lower, flags=re_mod.IGNORECASE)
            if m:
                # 返还原片段（更贴近页面）
                return m.group(0)
        return None

    def extract_image_url(self, element):
        img_elem = element.select_one('img.s-image, img')
        if img_elem:
            for attr in ['src', 'data-src', 'data-old-hires', 'data-image']:
                if img_elem.get(attr):
                    return img_elem[attr]
        return None

    def extract_badge(self, element, keywords):
        element_text = str(element).lower()
        for keyword in keywords:
            if keyword in element_text:
                return keyword.title()
        return None

    def _save_debug_html(self, prefix: str, url: str, html: str):
        """把 HTML 保存到 logs 目录，便于定位（仅在 debug_save_bad_pages=True 时生效）。"""
        if not getattr(self, 'debug_save_bad_pages', False):
            return
        try:
            logs_dir = os.path.join(self.data_dir, 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_prefix = ''.join(c for c in (prefix or 'page') if c.isalnum() or c in ('-', '_'))[:30]
            filename = f"{self.site_name}_{safe_prefix}_{ts}.html"
            path = os.path.join(logs_dir, filename)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(html or '')
            self._log(f"已保存调试页面: {path}", dedup_seconds=5)
        except Exception:
            return

    def is_not_functioning_page(self, response) -> bool:
        """检测 Amazon 'Looking for Something?/not a functioning page' 无效页面。"""
        text = (getattr(response, 'text', '') or '').lower()
        return (
            ('looking for something?' in text and 'not a functioning page' in text)
            or ("we're sorry" in text and 'not a functioning page' in text)
        )

    def _classify_page(self, url: str, html: str) -> str:
        """对返回页面做一个粗分类，用于日志输出。"""
        dummy = self._SimpleResponse(url=url, text=html or '', status_code=200)
        if self.is_not_functioning_page(dummy):
            return 'not_functioning'
        if self.is_verification_page(dummy):
            return 'verification'
        return 'normal_or_structure_changed'


# ==================== 具体网站实现 ====================

class AmazonCrawler(BaseEcommerceCrawler):
    """亚马逊爬虫"""

    def build_search_url(self, keyword, page=1):
        keyword_encoded = urllib.parse.quote(keyword)
        if page == 1:
            return f"{self.base_url}/s?k={keyword_encoded}"
        return f"{self.base_url}/s?k={keyword_encoded}&page={page}"

    def parse_search_results(self, html):
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        product_selectors = [
            'div[data-component-type="s-search-result"]',
            'div.s-result-item',
            'div[data-asin]',
            '.s-main-slot .s-result-item'
        ]

        for selector in product_selectors:
            elements = soup.select(selector)
            if not elements:
                continue
            for element in elements:
                try:
                    product_data = self.extract_product_basic_info(element)
                    if product_data and product_data.get('asin'):
                        products.append(product_data)
                except Exception:
                    continue
            if products:
                break

        return products

    def extract_product_basic_info(self, element):
        data = {}

        asin = element.get('data-asin', '')
        if not asin:
            link_elem = element.select_one('a.a-link-normal')
            if link_elem and link_elem.get('href'):
                match = re_mod.search(r'/dp/([A-Z0-9]{10})', link_elem['href'])
                if match:
                    asin = match.group(1)

        if not asin:
            return None

        data['asin'] = asin
        data['product_id'] = asin

        data['title'] = self.extract_text(element, ['h2 a span', '.a-text-normal', '.a-size-medium'])
        data['url'] = self.extract_url(element)
        data['price'] = self.extract_price(element)
        data['original_price'] = self.extract_original_price(element)
        data['rating'] = self.extract_rating(element)
        data['reviews'] = self.extract_reviews(element)
        data['image_url'] = self.extract_image_url(element)

        data['best_seller'] = self.extract_badge(element, ['best seller', 'bestseller'])
        data['amazon_choice'] = self.extract_badge(element, ["amazon's choice", 'amazon choice'])
        data['sponsored'] = self.extract_badge(element, ['sponsored'])
        data['prime_eligible'] = self.extract_badge(element, ['prime'])

        data['crawled_at'] = datetime.now().isoformat()
        data['source'] = 'amazon'

        return {k: v for k, v in data.items() if v is not None}

    def extract_product_details(self, soup):
        details = {}

        # 品牌
        details['brand'] = self.extract_text(soup, ['#bylineInfo', '#brand'])

        # 标题（兜底，有些页面详情里更准）
        details['title'] = self.extract_text(soup, ['#productTitle', '#title', 'h1 span#productTitle'])

        # 价格（详情页，尽量拿带货币符号的展示）
        details['price'] = self.extract_text(
            soup,
            [
                '#corePriceDisplay_desktop_feature_div .a-price .a-offscreen',
                '#corePriceDisplay_mobile_feature_div .a-price .a-offscreen',
                '#priceblock_ourprice',
                '#priceblock_dealprice',
                '#priceblock_saleprice',
                'span.a-price > span.a-offscreen',
            ],
        )

        # 评分 + 评论数（详情页）
        details['rating'] = None
        rating_text = self.extract_text(soup, ['#acrPopover', 'span.a-icon-alt'])
        if rating_text:
            m = re_mod.search(r'(\d+\.?\d*)', rating_text)
            if m:
                details['rating'] = m.group(1)

        details['reviews'] = None
        reviews_text = self.extract_text(
            soup,
            [
                '#acrCustomerReviewText',
                'a[data-hook="see-all-reviews-link-foot"], a[data-hook="see-all-reviews-link"]',
                'span[data-hook="total-review-count"]',
            ],
        )
        if reviews_text:
            m = re_mod.search(r'(\d{1,3}(?:,\d{3})*|\d+)', reviews_text)
            if m:
                details['reviews'] = m.group(1)

        # 描述：优先 feature bullets，其次 productDescription，其次 aplus
        bullets = []
        for li in soup.select('#feature-bullets ul li span.a-list-item'):
            txt = li.get_text(" ", strip=True)
            if txt:
                bullets.append(txt)
        if bullets:
            details['description'] = "\n".join(bullets[:30])
        else:
            desc_elem = soup.select_one('#productDescription')
            if desc_elem and desc_elem.get_text(strip=True):
                details['description'] = desc_elem.get_text(" ", strip=True)
            else:
                aplus = soup.select_one('#aplus')
                if aplus and aplus.get_text(strip=True):
                    details['description'] = aplus.get_text(" ", strip=True)[:3000]

        # 销量/购买提示（Amazon 不一定给出“真实销量”，这里提取可用的 proxy 字段）
        details['purchase_hint'] = self.extract_purchase_hint(soup)

        # Best Seller Rank（很多类目会给，通常可作为销量 proxy）
        rank_text_blob = None
        rank_elem = soup.select_one('#productDetails_detailBullets_sections1')
        if rank_elem and rank_elem.get_text(strip=True):
            rank_text_blob = rank_elem.get_text(" ", strip=True)
        else:
            bullet_rank = soup.select_one('#detailBulletsWrapper_feature_div')
            if bullet_rank and bullet_rank.get_text(strip=True):
                rank_text_blob = bullet_rank.get_text(" ", strip=True)

        if rank_text_blob:
            # #1,234 in ...
            m = re_mod.search(r'#(\d{1,3}(?:,\d{3})*)', rank_text_blob)
            if m:
                details['best_seller_rank'] = m.group(1)

        # 规格参数
        specs = {}
        spec_rows = soup.select('#productDetails_techSpec_section_1 tr')
        for row in spec_rows:
            th = row.select_one('th')
            td = row.select_one('td')
            if th and td:
                key = th.get_text(" ", strip=True).replace('\u200e', '')
                value = td.get_text(" ", strip=True).replace('\u200e', '')
                if key and value:
                    specs[key] = value

        if specs:
            details['specifications'] = specs

        return {k: v for k, v in details.items() if v is not None}


class EbayCrawler(BaseEcommerceCrawler):
    """eBay爬虫"""

    def build_search_url(self, keyword, page=1):
        keyword_encoded = urllib.parse.quote(keyword)
        return f"{self.base_url}/sch/i.html?_nkw={keyword_encoded}&_pgn={page}"

    def parse_search_results(self, html):
        products = []
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.s-item')

        for item in items:
            try:
                product_data = self.extract_product_basic_info(item)
                if product_data and product_data.get('item_id'):
                    products.append(product_data)
            except Exception:
                continue

        return products

    def extract_product_basic_info(self, element):
        data = {}

        item_id = element.get('data-view', '')
        if not item_id:
            return None

        data['item_id'] = item_id
        data['product_id'] = item_id

        data['title'] = self.extract_text(element, ['.s-item__title'])
        data['url'] = self.extract_url(element)
        data['price'] = self.extract_price(element)
        data['shipping_price'] = self.extract_shipping_price(element)
        data['rating'] = self.extract_rating(element)
        data['reviews'] = self.extract_reviews(element)
        data['image_url'] = self.extract_image_url(element)

        data['seller'] = self.extract_text(element, ['.s-item__seller-info-text'])
        data['condition'] = self.extract_text(element, ['.SECONDARY_INFO'])

        data['crawled_at'] = datetime.now().isoformat()
        data['source'] = 'ebay'

        return {k: v for k, v in data.items() if v is not None}

    def extract_product_details(self, soup):
        details = {}

        seller_elem = soup.select_one('.mbg-nw')
        if seller_elem:
            details['seller_name'] = seller_elem.text.strip()

        desc_elem = soup.select_one('#desc_div')
        if desc_elem:
            details['description'] = desc_elem.text.strip()[:1000]

        attrs = {}
        attr_rows = soup.select('.ux-layout-section__row')
        for row in attr_rows:
            label = row.select_one('.ux-labels-values__labels')
            value = row.select_one('.ux-labels-values__values')
            if label and value:
                attrs[label.text.strip()] = value.text.strip()

        if attrs:
            details['attributes'] = attrs

        return {k: v for k, v in details.items() if v is not None}

    def extract_shipping_price(self, element):
        shipping_elem = element.select_one('.s-item__shipping')
        if shipping_elem:
            shipping_text = shipping_elem.text.strip()
            match = re_mod.search(r'[\d.,]+', shipping_text)
            if match:
                return match.group(0)
        return None


class AlibabaCrawler(BaseEcommerceCrawler):
    """阿里巴巴爬虫"""

    def build_search_url(self, keyword, page=1):
        keyword_encoded = urllib.parse.quote(keyword)
        return f"{self.base_url}/trade/search?fsb=y&IndexArea=product_en&CatId=&SearchText={keyword_encoded}&page={page}"

    def parse_search_results(self, html):
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        items = soup.select('.organic-list .item-content')
        for item in items:
            try:
                product_data = self.extract_product_basic_info(item)
                if product_data:
                    products.append(product_data)
            except Exception:
                continue

        return products

    def extract_product_basic_info(self, element):
        data = {}

        data['title'] = self.extract_text(element, ['.title'])
        data['url'] = self.extract_url(element)
        data['price_range'] = self.extract_text(element, ['.price'])
        data['image_url'] = self.extract_image_url(element)

        data['supplier'] = self.extract_text(element, ['.company-name'])
        data['supplier_location'] = self.extract_text(element, ['.location'])
        data['min_order'] = self.extract_text(element, ['.moq'])

        data['crawled_at'] = datetime.now().isoformat()
        data['source'] = 'alibaba'

        return {k: v for k, v in data.items() if v is not None}

    def extract_product_details(self, soup):
        # 最小实现：避免抽象类无法实例化
        details = {}
        details['title'] = self.extract_text(soup, ['h1', '.product-title', '.title'])
        details['price_range'] = self.extract_text(soup, ['.price', '.price-range', '.product-price'])
        details['supplier'] = self.extract_text(soup, ['.company-name', '.store-name', '.supplier-name'])
        desc = self.extract_text(soup, ['.product-description', '#description', '.detail-description'])
        if desc:
            details['description'] = desc[:1000]
        details['image_url'] = self.extract_image_url(soup)
        return {k: v for k, v in details.items() if v is not None}


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

        downloaded = 0
        skipped = 0
        failed = 0

        for i, product in enumerate(products, 1):  # 按商品数下载（每个商品 1 张主图）
            image_url = product.get('image_url')
            product_id = product.get('product_id', product.get('asin', product.get('item_id', '')))

            if not image_url or not product_id:
                skipped += 1
                continue

            print(f"[{i}/{len(products)}] 下载图片...")
            path = crawler.download_image(image_url, product_id)
            if path:
                downloaded += 1
                product['image_path'] = path
            else:
                failed += 1

            time.sleep(random.uniform(1, 2))

        print(
            f"图片下载完成：成功 {downloaded}，跳过 {skipped}（无图/无ID），失败 {failed}。"
        )

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

    base_url = input("网站基础URL (例如 https://www.amazon.com): ").strip()
    if not base_url:
        print("基础URL不能为空!")
        return

    crawler_class = input("爬虫类名 (例如 AmazonCrawler): ").strip() or 'AmazonCrawler'

    # 保存一个简单的站点配置
    site_config = {
        'name': site_name,
        'base_url': base_url,
        'crawler_class': crawler_class,
        'headers': {
            'authority': urlparse(base_url).hostname if base_url else '',
            'method': 'GET',
            'scheme': urlparse(base_url).scheme if base_url else 'https'
        }
    }

    config_manager.add_site(site_name, site_config)


# 确保这个在文件的最末尾
if __name__ == "__main__":
    print("开始执行主程序...")
    main()
    # 仅在交互式终端中暂停，避免管道/自动化运行时 EOFError
    if hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        input("程序执行完毕，按Enter退出...")
