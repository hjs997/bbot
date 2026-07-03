import os
import re
import sys
import time
import random
import requests
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def send_tg_photo(token: str, chat_id: str, photo_path: str, caption: str = ""):
    if not token or not chat_id: 
        return
    caption = caption[:1020]
    if os.path.exists(photo_path):
        try:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(photo_path, 'rb') as f:
                resp = requests.post(url, data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}, 
                                   files={'photo': f}, timeout=25)
            if resp.status_code == 200:
                log(f"📤 Telegram 截图已发送: {os.path.basename(photo_path)}")
                os.remove(photo_path)
                return
        except Exception as e:
            log(f"⚠️ 图片发送异常: {e}")
    send_tg_text(token, chat_id, caption)

def send_tg_text(token: str, chat_id: str, text: str):
    if not token or not chat_id: 
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"}, timeout=15)
    except Exception:
        pass

def parse_accounts(raw: str) -> list[tuple[str, str]]:
    accounts = []
    for line in re.split(r'[\n,]+', raw.strip()):
        line = line.strip()
        if '---' in line:
            parts = line.split('---', 1)
            if len(parts) == 2:
                accounts.append((parts[0].strip(), parts[1].strip()))
    return accounts

def _screenshot(page: ChromiumPage, path: str) -> str:
    try:
        page.get_screenshot(path=path)
        log(f"📸 截图已保存: {path}")
    except Exception:
        pass
    return path

# ─────────────────────────────────────────────
# Turnstile 破解器
# ─────────────────────────────────────────────
class TurnstileSolver:
    def __init__(self, page: ChromiumPage):
        self.page = page

    def solve(self, timeout: int = 15) -> bool:
        try:
            for _ in range(3):
                iframe = self.page.get_frame('css:iframe[src^="https://challenges.cloudflare.com"]', timeout=3)
                if iframe:
                    log("🛡️ 检测到 Cloudflare Turnstile 验证码，正在处理...")
                    try:
                        iframe.frame_ele.click.at(offset_x=random.randint(20, 30), offset_y=random.randint(20, 30))
                    except:
                        pass
                    time.sleep(4)
                    break
        except:
            pass
        return True

# ─────────────────────────────────────────────
# 主类
# ─────────────────────────────────────────────
class BotHostingRenewer:
    BASE_URL = "https://bot-hosting.net"
    LOGIN_URL = "https://bot-hosting.net/login"
    NEW_PANEL_URL = "https://bot-hosting.net/a"
    BILLING_URL = "https://bot-hosting.net/a/billings"

    def __init__(self, email: str, token: str, proxy: str = "", tg_token: str = "", tg_chat_id: str = ""):
        self.email = email
        self.discord_token = token
        self.proxy = proxy
        self.tg_token = tg_token
        self.tg_chat_id = tg_chat_id
        self.page: ChromiumPage | None = None
        self.safe_email = email.replace('@', '_').replace('.', '_')

    def _make_page(self) -> ChromiumPage:
        co = ChromiumOptions()
        if os.path.exists('/usr/bin/google-chrome'):
            co.set_browser_path('/usr/bin/google-chrome')
        for arg in ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--disable-popup-blocking', '--window-size=1280,1024']:
            co.set_argument(arg)
        co.headless(False)
        co.set_user_data_path(os.path.join(os.getcwd(), 'browser_profile', self.safe_email))
        if self.proxy:
            proxy_url = self.proxy if "://" in self.proxy else f"socks5://{self.proxy}"
            co.set_argument(f'--proxy-server={proxy_url}')
            log(f"🌐 代理已配置: {proxy_url}")
        return ChromiumPage(co)

    def _is_logged_in(self) -> bool:
        if not self.page: 
            return False
        try:
            url = self.page.url.lower()
            if "bot-hosting.net" in url and "discord.com" not in url:
                if "/a" in url:
                    if self.page.ele('xpath://a[contains(@href, "/a") and (contains(., "Overview") or contains(., "Billing"))]', timeout=2):
                        return True
                if "/login/welcome" in url:
                    return True
        except Exception:
            pass
        return False

    def login(self) -> bool:
        log(f"🔐 [{self.email}] 正在使用 Discord Token 免密登录...")
        self.page = self._make_page()
        page = self.page
        solver = TurnstileSolver(page)

        try:
            page.get(self.NEW_PANEL_URL)
            time.sleep(3)
            if self._is_logged_in():
                log(f"✨ [{self.email}] 会话未过期，已直接进入新版控制面板。")
                return True

            log("🌐 初始化 Discord 环境并注入 Token...")
            page.get("https://discord.com/404")
            time.sleep(2)

            inject_js = f"""
            function login(token) {{
                setInterval(() => {{
                    document.body.appendChild(document.createElement('iframe')).contentWindow.localStorage.token = `"${{token}}"`;
                }}, 50);
                setTimeout(() => location.reload(), 1500);
            }}
            login('{self.discord_token}');
            """
            page.run_js(inject_js)
            time.sleep(4)

            log("🚀 前往 bot-hosting 触发鉴权...")
            page.get(self.LOGIN_URL)
            time.sleep(5)
            solver.solve()

            discord_btn = (
                page.ele('xpath://*[contains(text(), "Continue with Discord")]', timeout=3) or
                page.ele('xpath://*[contains(text(), "Login with Discord")]') or
                page.ele('xpath://a[contains(@href, "discord.com/oauth2")]')
            )
            if discord_btn:
                log("🔄 检测到 'Continue with Discord' 按钮，执行点击...")
                try:
                    discord_btn.click()
                except:
                    page.run_js("arguments[0].click();", discord_btn)

            # 等待授权页
            for _ in range(15):
                if "oauth2/authorize" in page.url:
                    break
                time.sleep(1)

            if "oauth2/authorize" in page.url:
                log("🔓 已免密来到 Discord 授权界面，正在自动点击授权...")
                for attempt in range(3):
                    auth_btn = page.ele('xpath://button[contains(., "授权") or contains(., "Authorize")]', timeout=3)
                    if auth_btn:
                        try:
                            auth_btn.click(by_js=False)
                        except:
                            page.run_js("arguments[0].click();", auth_btn)
                    for _ in range(12):
                        time.sleep(1)
                        if self._is_logged_in():
                            log("🎉 登录并授权大成功！")
                            return True
                    log(f"⚠️ 第 {attempt+1} 次尝试失败...")

            if self._is_logged_in():
                log(f"🎉 [{self.email}] 登录成功！")
                return True

            log(f"❌ [{self.email}] 登录失败，当前 URL: {page.url}")
            pic = _screenshot(page, f"err_login_{self.safe_email}.png")
            send_tg_photo(self.tg_token, self.tg_chat_id, pic, f"❌ <b>{self.email}</b> 登录失败")
            return False

        except Exception as e:
            log(f"❌ 登录逻辑异常: {e}")
            return False

    def renew_service(self) -> dict:
        page = self.page
        result = {'success': False, 'message': '', 'due_date': 'N/A', 'btn_text': ''}

        log(f"🧭 正在直达账单页面: {self.BILLING_URL}")
        page.get(self.BILLING_URL)
        time.sleep(5)
        TurnstileSolver(page).solve()

        # 提取到期时间
        try:
            m = re.search(r'Expires\s+(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})', page.html, re.IGNORECASE)
            if m:
                result['due_date'] = m.group(1)
                log(f"📅 当前到期日: {result['due_date']}")
        except Exception as e:
            log(f"⚠️ 解析到期时间失败: {e}")

        # === 核心修复部分：适配新按钮 "Renew (+4d)" ===
        renew_ele = None
        btn_text = ""

        elements = page.eles('xpath://*[contains(translate(text(), "RENEW", "renew"), "renew")]')
        for el in elements:
            txt = el.text.strip()
            if not txt:
                continue
            if "manually to extend" in txt.lower():
                continue

            if ("renew in" in txt.lower() or 
                txt.lower().startswith("renew") or 
                "(+4d)" in txt):
                renew_ele = el
                btn_text = txt
                result['btn_text'] = txt
                log(f"✅ 找到续期按钮: {txt}")
                break

        if not renew_ele:
            result['message'] = '未找到续期按钮'
            log("❌ 未找到有效续期按钮")
            log("🔍 页面中所有含renew的元素:")
            for el in elements:
                log(f"   - {el.text.strip()}")
        elif "renew in" in btn_text.lower():
            log(f"⏳ 冷却中: {btn_text}")
            try:
                renew_ele.click()
            except:
                page.run_js("arguments[0].click();", renew_ele)
            result['message'] = f'冷却中 ({btn_text})，已执行点击'
        else:
            # 可立即续期
            log(f"⚡ 点击续期: {btn_text}")
            try:
                renew_ele.click()
            except:
                page.run_js("arguments[0].click();", renew_ele)

            time.sleep(4)

            # 确认弹窗
            confirm_btn = page.ele('xpath://button[contains(translate(text(),"CONFIRM","confirm"), "confirm") or contains(translate(text(),"YES","yes"), "yes")]', timeout=3)
            if confirm_btn:
                log("📦 点击确认...")
                try:
                    confirm_btn.click()
                except:
                    page.run_js("arguments[0].click();", confirm_btn)
                time.sleep(4)

            result['success'] = True
            result['message'] = f'已点击续期按钮 ({btn_text})'

            # 验证更新
            page.refresh()
            time.sleep(5)
            try:
                m_after = re.search(r'Expires\s+(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})', page.html, re.IGNORECASE)
                if m_after and m_after.group(1) != result['due_date']:
                    result['message'] += f" ✅ 到期日更新至 {m_after.group(1)}"
                    result['due_date'] = m_after.group(1)
            except:
                pass

        # 发送报告
        pic = _screenshot(page, f"renew_result_{self.safe_email}.png")
        status_icon = "✅" if result['success'] else "❌"
        caption = (
            f"{status_icon} <b>Bot-Hosting 续期报告</b>\n"
            f"👤 账号：{self.email}\n"
            f"📅 到期：{result['due_date']}\n"
            f"🔘 按钮：{result['btn_text'] or '未捕获'}\n"
            f"📝 状态：{result['message']}"
        )
        send_tg_photo(self.tg_token, self.tg_chat_id, pic, caption)
        return result

    def run(self):
        try:
            if not self.login():
                return
            self.renew_service()
        except Exception as e:
            log(f"❌ 脚本异常: {e}")
            if self.page:
                pic = _screenshot(self.page, f"err_crash_{self.safe_email}.png")
                send_tg_photo(self.tg_token, self.tg_chat_id, pic, f"❌ <b>{self.email}</b> 脚本崩溃\n{str(e)[:200]}")
        finally:
            if self.page:
                self.page.quit()


def main():
    accounts_raw = os.getenv('ACCOUNTS', '').strip()
    tg_token = os.getenv('TG_BOT_TOKEN', '').strip()
    tg_chat_id = os.getenv('TG_CHAT_ID', '').strip()
    proxy = os.getenv('PROXY', '').strip()

    if not accounts_raw:
        log("❌ ACCOUNTS 环境变量为空")
        sys.exit(1)

    accounts = parse_accounts(accounts_raw)
    for email, token in accounts:
        log(f"\n🚀 开始处理: {email}")
        renewer = BotHostingRenewer(email, token, proxy, tg_token, tg_chat_id)
        renewer.run()

    log("🏁 全部账号处理完毕")


if __name__ == '__main__':
    main()
