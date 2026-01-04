import os
import time
import requests
import zipfile
import io
import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 实时日志工具 ====================
def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

# ==================== 核心逻辑 ====================

def download_and_extract_silk_extension():
    extension_id = "ajhmfdgkijocedmfjonnpjfojldioehi"
    crx_path = "silk.crx"
    extract_dir = "silk_ext"
    
    if os.path.exists(extract_dir) and os.listdir(extract_dir):
        log(f">>> [系统] 插件已就绪")
        return os.path.abspath(extract_dir)
        
    log(">>> [系统] 正在下载 Silk 隐私插件...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    download_url = f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3D{extension_id}%26uc"
    
    try:
        resp = requests.get(download_url, headers=headers, stream=True)
        if resp.status_code == 200:
            content = resp.content
            zip_start = content.find(b'PK\x03\x04')
            if zip_start == -1: return None
            with zipfile.ZipFile(io.BytesIO(content[zip_start:])) as zf:
                if not os.path.exists(extract_dir): os.makedirs(extract_dir)
                zf.extractall(extract_dir)
            return os.path.abspath(extract_dir)
        return None
    except: return None

def wait_for_cloudflare(page, timeout=15):
    """
    【增强版】过盾检测
    不仅看标题，还看页面里有没有盾的 iframe
    """
    log(f"--- [盾] 正在扫描全页验证码 (限时 {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        # 1. 检查标题是否包含 Cloudflare 特征
        is_blocked_title = "just a moment" in page.title.lower()
        
        # 2. 检查页面内是否有验证码 iframe
        iframe = page.ele('@src^https://challenges.cloudflare.com')
        
        if not is_blocked_title and not iframe:
            return True # 通行
            
        if iframe:
            log("--- [盾] 发现验证码，尝试点击...")
            try:
                iframe.ele('tag:body').click(by_js=True)
                time.sleep(2) # 点完等一下
            except: pass
            
        time.sleep(1)
    
    return False

def solve_modal_captcha(modal):
    log(">>> [验证] 正在扫描弹窗验证码...")
    
    # 智能等待 iframe
    iframe = modal.wait.ele_displayed('tag:iframe', timeout=8)
    
    if not iframe:
        iframe = modal.wait.ele_displayed('@src^https://challenges.cloudflare.com', timeout=3)

    if iframe:
        log(">>> [验证] 发现验证码，点击中...")
        try:
            iframe.ele('tag:body').click(by_js=True)
            for i in range(4, 0, -1):
                log(f">>> [验证] 等待验证通过... {i}s")
                time.sleep(1)
            return True
        except Exception as e:
            log(f"⚠️ 验证码点击异常: {e}")
    else:
        log(">>> [验证] 无需验证码或插件已自动处理。")
    return False

def robust_click(ele):
    try:
        ele.scroll.to_see()
        log(f">>> [动作] 点击按钮: {ele.text}")
        ele.click(by_js=True)
        return True
    except:
        try:
            ele.click()
            return True
        except: return False

def check_result(page):
    log(">>> [检测] 正在分析页面文字结果...")
    start = time.time()
    while time.time() - start < 5:
        full_text = page.html.lower()
        
        if "captcha" in full_text or "验证码" in full_text:
            log("❌ 结果: 验证码拦截 (页面包含 Captcha 字样)")
            return "FAIL"
        
        if "can't renew" in full_text or "too early" in full_text:
            log("✅ 结果: 还没到时间 (操作正确)")
            return "SUCCESS"
        if "success" in full_text or "extended" in full_text:
            log("✅ 结果: 续期成功")
            return "SUCCESS"
        
        time.sleep(1)
    
    log("⚠️ 未捕捉到明确结果")
    return "UNKNOWN"

def job():
    ext_path = download_and_extract_silk_extension()
    co = ChromiumOptions()
    co.set_argument('--headless=new')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    if ext_path: co.add_extension(ext_path)
    co.auto_port()
    co.set_load_mode('none')

    page = ChromiumPage(co)
    page.set.timeouts(15)

    try:
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        
        if not all([email, password, target_url]): 
            log("❌ Secrets 配置缺失")
            exit(1)

        # ==================== 1. 登录 ====================
        log(">>> [Step 1] 开始登录流程...")
        page.get('https://dashboard.katabump.com/auth/login')
        wait_for_cloudflare(page)
        
        if page.ele('css:input[name="email"]'):
            log(">>> 输入账号密码...")
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            page.ele('css:button[type="submit"]').click()
            
            log(">>> 等待页面跳转...")
            start_wait = time.time()
            while time.time() - start_wait < 10:
                if "login" not in page.url:
                    log(">>> 跳转成功！")
                    break
                time.sleep(1)
            wait_for_cloudflare(page)

        # ==================== 2. 循环尝试 ====================
        for attempt in range(1, 4):
            log(f"\n🚀 [Step 2] 第 {attempt}/3 次续期尝试...")
            try:
                page.get(target_url)
                
                # 【关键修复】进入页面后，立刻检查是否有全屏盾
                # 之前这里漏掉了，导致直接去抓按钮抓不到
                wait_for_cloudflare(page, timeout=15)
                
                # 寻找按钮
                renew_btn = None
                for _ in range(5):
                    renew_btn = page.ele('css:button:contains("Renew")')
                    if renew_btn and renew_btn.states.is_displayed:
                        break
                    time.sleep(1)
                
                if not renew_btn:
                    log("⚠️ 未找到 Renew 按钮，检查是否被拦截或已续期...")
                    # 此时如果没有按钮，check_result 可能会发现 captcha
                    res = check_result(page)
                    if res == "SUCCESS": 
                        break
                    elif res == "FAIL":
                        log("⚠️ 检测到拦截，刷新页面重试...")
                        continue # 触发下一次重试
                    
                    # 既没按钮，也没检测到 captcha 关键字，可能是网络卡了，重试
                    continue

                robust_click(renew_btn)
                
                log(">>> 等待弹窗弹出...")
                modal = page.wait.ele_displayed('css:.modal-content', timeout=5)
                
                if modal:
                    solve_modal_captcha(modal)
                    
                    confirm = modal.ele('css:button.btn-primary')
                    if confirm:
                        robust_click(confirm)
                        log(">>> 指令已发送，等待服务器响应...")
                        time.sleep(3) 
                        if check_result(page) == "SUCCESS":
                            break
                    else:
                        log("⚠️ 确认按钮不可用")
                        if check_result(page) == "SUCCESS": break
                else:
                    log("❌ 弹窗未出现")
            
            except Exception as e:
                log(f"❌ 异常: {e}")
            
            if attempt < 3: 
                log("⏳ 休息 3 秒后重试...")
                time.sleep(3)

        log("\n🏁 脚本运行结束")

    except Exception as e:
        log(f"❌ 崩溃: {e}")
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
