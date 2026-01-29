import os
import sys
import yaml

# 仅用于“方案A”：手动登录/扫码一次，然后保存 Playwright storage_state
# 注意：不会也不应该自动绕过验证码；遇到验证码请在浏览器里手动完成。


def load_site_config(site_name: str, config_path: str):
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    site = cfg.get(site_name)
    if not site:
        raise SystemExit(f"找不到站点配置: {site_name}")
    return site


def _print_playwright_install_help(original_error: Exception | None = None):
    msg = (
        "Playwright 浏览器未安装或 Playwright CLI 被系统策略拦截。\n\n"
        "请在 PowerShell 中执行（推荐用 python -m 方式，避免 playwright.exe 被拦截）：\n\n"
        "  python -m playwright install\n\n"
        "如果你只需要 Chromium：\n\n"
        "  python -m playwright install chromium\n\n"
        "原始错误: " + (str(original_error) if original_error else "(无)")
    )
    print(msg)


def _normalize_amazon_login_url(url: str) -> str:
    url = (url or '').strip()
    if not url:
        return "https://www.amazon.com/"
    return url


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(here, 'sites_config.yaml')

    site_name = (sys.argv[1] if len(sys.argv) > 1 else 'amazon').strip().lower()
    site_cfg = load_site_config(site_name, config_path)

    auth = site_cfg.get('auth', {}) or {}
    if auth.get('provider') != 'playwright':
        raise SystemExit("当前仅支持 auth.provider=playwright")

    login_url = _normalize_amazon_login_url(auth.get('login_url') or site_cfg.get('base_url'))
    headed = bool(auth.get('headed', True))
    storage_state_path = auth.get('storage_state_path') or f"{site_name}_state.json"
    storage_state_path = os.path.join(here, storage_state_path) if not os.path.isabs(storage_state_path) else storage_state_path

    # 允许用户在运行时覆盖 URL（解决地区/跳转导致的无效地址问题）
    override = input(f"登录入口URL（直接回车使用默认: {login_url}）：").strip()
    if override:
        login_url = _normalize_amazon_login_url(override)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise SystemExit(
            "未安装 Playwright。请先安装依赖并安装浏览器：\n"
            "  pip install -r requirements.txt\n"
            "  python -m playwright install\n"
            f"原始错误: {e}"
        )

    print(f"将打开浏览器前往: {login_url}")
    print("提示：如果弹出验证码/扫码，请在浏览器里手动完成。")
    print("提示：如果看到 'Looking for Something? ... Web address ... not a functioning page'，说明落到了无效链接，请在本窗口输入一个新的 URL 重新打开。")

    def is_logged_in(page, context) -> bool:
        """非常保守的登录成功判定：
        1) cookies 里出现 amazon 常见会话 cookie（如 session-id / ubid-*），且
        2) 页面上出现 Account & Lists / Sign Out 等特征之一
        """
        try:
            cookies = context.cookies() or []
            names = set((c.get('name') or '').lower() for c in cookies)
            has_session = any(n in names for n in ['session-id', 'session-token']) or any(n.startswith('ubid-') for n in names)
        except Exception:
            has_session = False

        try:
            html = (page.content() or '').lower()
            # 这些词在不同语言站点可能变动，这里只作为辅助，不做强依赖
            has_dom = ('account & lists' in html) or ('sign out' in html) or ('/gp/flex/sign-out' in html)
        except Exception:
            has_dom = False

        # cookie 更可靠
        return bool(has_session or has_dom)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            context = browser.new_context()
            page = context.new_page()

            # 先去用户提供的入口
            page.goto(login_url, wait_until='domcontentloaded')

            # 再尝试打开首页（很多时候登录态会在首页自动激活/或触发重定向）
            try:
                page.goto('https://www.amazon.com/', wait_until='domcontentloaded', timeout=30000)
            except Exception:
                pass

            print("浏览器已打开。请在浏览器中完成登录/扫码/验证码后，再回到此窗口。")

            while True:
                # 提供一个小菜单，避免用户卡死
                cmd = input(
                    "输入指令：\n"
                    "  [Enter] 检查是否已登录（已登录则保存）\n"
                    "  r 重新打开一个 URL\n"
                    "  q 退出\n"
                    "> "
                ).strip().lower()

                if cmd == 'q':
                    print('已退出，不保存登录态。')
                    break

                if cmd == 'r':
                    new_url = input('请输入要重新打开的 URL：').strip()
                    if new_url:
                        try:
                            page.goto(_normalize_amazon_login_url(new_url), wait_until='domcontentloaded')
                        except Exception as e:
                            print(f"打开失败: {e}")
                    continue

                # 默认：检查登录态
                if is_logged_in(page, context):
                    context.storage_state(path=storage_state_path)
                    print(f"登录态已保存到: {storage_state_path}")
                    break

                print("当前似乎还未完成登录（或仍在验证页/无效页）。请继续在浏览器完成登录，或输入 r 重新打开可用链接。")

            browser.close()

    except Exception as e:
        # Playwright 常见问题：浏览器可执行文件缺失（需要安装 browser）
        if 'Executable doesn\'t exist' in str(e) or 'playwright install' in str(e):
            _print_playwright_install_help(e)
            raise SystemExit(1)
        raise


if __name__ == '__main__':
    main()
