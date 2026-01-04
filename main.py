importimport os
import time
import requests
import zipfile
import io
import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 1. 基础工具 ====================
def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

def download_silk():
    extract_dir = "silk_ext"
    if os.path.exists(extract_dir): return os.path.abspath(extract_dir)
    log(">>> [系统] 下载插件...")
    try:
        url = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3Dajhmfdgkijocedmfjonnpjfojldioehi%26uc"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, stream=True)
        if resp.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                zf.extractall(extract_dir)
            return os.path.abspath(extract_dir)
    except: pass
    return None

# ==================== 2. 过盾逻辑 ====================
def pass_full_page_shield(page):
    """处理全屏 Cloudflare"""
    log("--- [门神] 检查全屏验证...")
    for _ in range(5):
        title = page.title.lower()
        if "just a moment" in title or "attention" in title:
            log("--- [门神] 正在通过全屏盾...")
            iframe = page.ele('css:iframe[src*="cloudflare"]', timeout=2)
            if iframe: iframe.ele('tag:body').click(by_js=True)
            time.sleep(5)
        else:
            return True
    return False

def pass_modal_shield(modal):
    """处理弹窗内 Cloudflare"""
    log(">>> [弹窗] 检查内部验证码...")
    iframe = modal.wait.ele_displayed('css:iframe[src*="cloudflare"]', timeout=5)
    if not iframe:
        iframe = modal.wait.ele_displayed('css:iframe[title*="Widget"]', timeout=2)

    if iframe:
        log(">>> [弹窗] 👁️ 发现验证码，点击...")
        try:
            iframe.ele('tag:body').click(by_js=True)
            log(">>> [弹窗] 👆 已点击，强制等待 6 秒...")
            time.sleep(6)
            return True
        except: pass
    return False

def check_final_status(page):
    html = page.html.lower()
    if "can't renew" in html or "too early" in html:
        log("✅ [结果] 检测到红条: 还没到时间 (任务成功)")
        return True
    if "success" in html or "extended" in html:
        log("✅ [结果] 检测到绿条: 续期成功！")
        return True
    return False

# ==================== 3. 主程序 ====================
def job():
    ext_path = download_silk()
    
    # ⚠️ 配置浏览器参数 (防崩溃核心)
    co = ChromiumOptions()
    co.set_argument('--headless=new')       # 无头模式
    co.set_argument('--no-sandbox')         # Linux 必加
    co.set_argument('--disable-gpu')        # 禁用 GPU
    co.set_argument('--disable-dev-shm-usage') # 🚨 关键！防止内存不足崩溃
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    if ext_path: co.add_extension(ext_path)
    co.auto_port()

    # 启动浏览器
    page = ChromiumPage(co)
    page.set.timeouts(15)

    try:
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        if not all([email, password, target_url]): 
            log("❌ 配置缺失")
            exit(1)

        # Step 1: 登录
        log(">>> [1/3] 前往登录页...")
        page.get('https://dashboard.katabump.com/auth/login')
        pass_full_page_shield(page)

        if page.ele('css:input[name="email"]'):
            log(">>> 输入账号密码...")
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            page.ele('css:button[type="submit"]').click()
            page.wait.url_change('login', exclude=True, timeout=15)
        
        # Step 2: 找按钮
        log(">>> [2/3] 进入服务器页面...")
        page.get(target_url)
        pass_full_page_shield(page)
        
        renew_btn = None
        for _ in range(10):
            renew_btn = page.ele('css:button:contains("Renew")')
            if renew_btn and renew_btn.states.is_displayed: break
            time.sleep(1)

        if not renew_btn:
            log("⚠️ 未找到 Renew 按钮，检查是否未到期...")
            if check_final_status(page):
                log("🎉 脚本提前结束")
                return
            else:
                log("❌ 既没按钮也没提示，页面异常")
                log(f"   标题: {page.title}")
                exit(1)

        # Step 3: 续期
        log(">>> [3/3] 开始续期流程...")
        renew_btn.click(by_js=True)
        
        log(">>> 等待弹窗...")
        modal = page.wait.ele_displayed('css:.modal-content', timeout=10)
        
        if modal:
            pass_modal_shield(modal) # 先过盾
            
            confirm_btn = modal.ele('css:button.btn-primary')
            if confirm_btn:
                log(">>> [动作] 点击确认...")
                confirm_btn.click(by_js=True)
                time.sleep(5)
                if check_final_status(page):
                    log("🎉🎉🎉 完美结束")
                else:
                    log("❌ 未检测到成功文字")
                    exit(1)
            else:
                log("❌ 没找到确认按钮")
                exit(1)
        else:
            log("❌ 弹窗未出现")
            exit(1)

    except Exception as e:
        log(f"❌ 运行崩溃: {e}")
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
