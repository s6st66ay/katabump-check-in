import os
import time
import requests
import zipfile
import io
import datetime
import shutil
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 基础工具 ====================
def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

def download_cf_autoclicker():
    """
    【修正】下载 cf-autoclick 插件
    使用您提供的 master 分支链接
    """
    # 插件解压后的预期文件夹名
    expected_folder_name = "cf-autoclick-master"
    extract_root = "extensions"
    final_path = os.path.abspath(os.path.join(extract_root, expected_folder_name))
    
    # 如果已经下载并解压过，直接返回
    if os.path.exists(final_path):
        log(">>> [插件] cf-autoclick 已就绪")
        return final_path
        
    log(">>> [插件] 正在下载 cf-autoclick (Master分支)...")
    try:
        # 您提供的正确链接
        url = "https://codeload.github.com/tenacious6/cf-autoclick/zip/refs/heads/master"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, stream=True)
        
        if resp.status_code == 200:
            if not os.path.exists(extract_root): os.makedirs(extract_root)
            
            # 解压
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                zf.extractall(extract_root)
                
            log(f">>> [插件] 下载并解压完成: {final_path}")
            return final_path
        else:
            log(f"❌ [插件] 下载失败，状态码: {resp.status_code}")
            log(f"   链接: {url}")
    except Exception as e:
        log(f"❌ [插件] 安装异常: {e}")
    
    return None

# ==================== 核心逻辑 ====================

def pass_full_page_shield(page):
    """处理全屏盾 (等待插件)"""
    for _ in range(5):
        if "just a moment" in page.title.lower():
            log("--- [门神] 全屏盾出现，等待插件自动突破...")
            time.sleep(2)
        else:
            return True
    return False

def analyze_page_result(page):
    """解析结果"""
    log(">>> [系统] 检查页面提示...")
    
    danger = page.ele('css:.alert.alert-danger')
    if danger and danger.states.is_displayed:
        text = danger.text
        log(f"⬇️ 红色提示: {text}")
        if "can't renew" in text.lower():
            return "SUCCESS_TOO_EARLY"
        elif "captcha" in text.lower():
            return "FAIL_CAPTCHA"
        return "FAIL_OTHER"

    success = page.ele('css:.alert.alert-success')
    if success and success.states.is_displayed:
        log(f"⬇️ 绿色提示: {success.text}")
        log("🎉 [结果] 续期成功！")
        return "SUCCESS"

    return "UNKNOWN"

# ==================== 主程序 ====================
def job():
    # 1. 下载插件 (使用修正后的链接)
    ext_path = download_cf_autoclicker()
    
    co = ChromiumOptions()
    co.set_argument('--headless=new') 
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # 2. 挂载插件
    if ext_path: 
        co.add_extension(ext_path)
    else:
        log("⚠️ 警告: 插件下载失败，脚本将尝试裸奔 (成功率低)！")
        
    co.auto_port()
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
        log(">>> [Step 1] 登录...")
        page.get('https://dashboard.katabump.com/auth/login')
        pass_full_page_shield(page)

        if page.ele('css:input[name="email"]'):
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            page.ele('css:button#submit').click()
            page.wait.url_change('login', exclude=True, timeout=20)
        
        # Step 2: 续期循环
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            log(f"\n🚀 [Step 2] 尝试续期 (第 {attempt} 次)...")
            page.get(target_url)
            pass_full_page_shield(page)
            
            renew_btn = None
            for _ in range(5):
                renew_btn = page.ele('css:button[data-bs-target="#renew-modal"]')
                if renew_btn and renew_btn.states.is_displayed: break
                time.sleep(1)

            if renew_btn:
                log(">>> 点击 Renew 按钮...")
                renew_btn.click(by_js=True)
                
                log(">>> 等待弹窗...")
                modal = page.ele('css:.modal-content', timeout=10)
                
                if modal:
                    # ==========================================
                    # 插件时刻
                    # ==========================================
                    log(">>> [插件] 弹窗已出，等待插件自动过盾 (10s)...")
                    
                    # 确保 iframe 出现，给插件操作的机会
                    page.wait.ele_displayed('css:iframe[src*="cloudflare"], iframe[src*="turnstile"]', timeout=10)
                    
                    # 纯等待，让插件去点
                    time.sleep(10)
                    
                    confirm_btn = modal.ele('css:button[type="submit"].btn-primary')
                    if confirm_btn:
                        log(">>> 点击 Confirm...")
                        confirm_btn.click(by_js=True)
                        log(">>> 等待响应 (5s)...")
                        time.sleep(5)
                        
                        result = analyze_page_result(page)
                        
                        if result == "SUCCESS" or result == "SUCCESS_TOO_EARLY":
                            break 
                        
                        if result == "FAIL_CAPTCHA":
                            log("⚠️ 插件操作未完成，刷新重试...")
                            time.sleep(2)
                            continue
                    else:
                        log("❌ 找不到确认按钮")
                else:
                    log("❌ 弹窗未出")
            else:
                log("⚠️ 未找到按钮，检查是否已续期...")
                result = analyze_page_result(page)
                if result == "SUCCESS_TOO_EARLY":
                    break
            
            if attempt == max_retries:
                log("❌ 最大重试次数已达，任务终止。")
                exit(1)

    except Exception as e:
        log(f"❌ 异常: {e}")
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
