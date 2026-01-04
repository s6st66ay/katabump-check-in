import os
import time
import requests
import zipfile
import io
from DrissionPage import ChromiumPage, ChromiumOptions

def download_and_extract_silk_extension():
    """自动下载并解压 Silk 插件"""
    extension_id = "ajhmfdgkijocedmfjonnpjfojldioehi"
    crx_path = "silk.crx"
    extract_dir = "silk_ext"
    
    if os.path.exists(extract_dir) and os.listdir(extract_dir):
        print(f">>> [系统] 插件已就绪")
        return os.path.abspath(extract_dir)
        
    print(">>> [系统] 正在下载 Silk 隐私插件...")
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

def wait_for_cloudflare(page, timeout=10):
    """
    快速过盾检测
    Timeout 缩短为 10s，因为插件过盾通常很快
    """
    print(f"--- [盾] 检查全页 Cloudflare... ---")
    start = time.time()
    while time.time() - start < timeout:
        # 如果标题正常且没有 cf 的 iframe，直接放行
        if "just a moment" not in page.title.lower():
            if not page.ele('@src^https://challenges.cloudflare.com'):
                return True
        try:
            iframe = page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe: 
                iframe.ele('tag:body').click(by_js=True)
                time.sleep(1) # 点击后稍等
        except: pass
        time.sleep(1)
    return False

def solve_modal_captcha(modal):
    """
    【智能等待】弹窗内的验证码
    """
    print(">>> [验证] 寻找弹窗验证码...")
    
    # 使用 DrissionPage 内置的智能等待，最长等 8 秒
    # 一旦找到立刻返回，不用死循环
    iframe = modal.wait.ele_displayed('tag:iframe', timeout=8)
    
    if not iframe:
        # 再次尝试特指 src
        iframe = modal.wait.ele_displayed('@src^https://challenges.cloudflare.com', timeout=3)

    if iframe:
        print(">>> [验证] 发现验证码，点击...")
        try:
            iframe.ele('tag:body').click(by_js=True)
            # 点击后等待变绿，这里给 4 秒通常足够
            print(">>> [验证] 等待验证通过 (4s)...")
            time.sleep(4) 
            return True
        except Exception as e:
            print(f"⚠️ 验证码点击异常: {e}")
    else:
        print(">>> [验证] 无需验证码或插件已自动处理。")
    return False

def robust_click(ele):
    """点击逻辑"""
    try:
        ele.scroll.to_see()
        print(f">>> [动作] 点击: {ele.text}")
        ele.click(by_js=True)
        return True
    except:
        try:
            ele.click()
            return True
        except: return False

def check_result(page):
    """
    快速检测结果 (只看 5 秒)
    """
    print(">>> [检测] 分析结果...")
    start = time.time()
    while time.time() - start < 5:
        full_text = page.html.lower()
        
        # 1. 拦截
        if "captcha" in full_text or "验证码" in full_text:
            print("❌ 结果: 验证码拦截")
            return "FAIL"
        
        # 2. 成功/未到期
        if "can't renew" in full_text or "too early" in full_text:
            print("✅ 结果: 还没到时间 (操作正确)")
            return "SUCCESS"
        if "success" in full_text or "extended" in full_text:
            print("✅ 结果: 续期成功")
            return "SUCCESS"
        
        time.sleep(1)
    
    print("⚠️ 未捕捉到明确结果 (可能网络延迟)")
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
    
    # 页面加载策略：None (不等待资源加载，极速模式)
    co.set_load_mode('none')

    page = ChromiumPage(co)
    # 缩短超时时间，防止卡死
    page.set.timeouts(10)

    try:
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        if not all([email, password, target_url]): raise Exception("Secrets 缺失")

        # ==================== 1. 登录 ====================
        print(">>> [Step 1] 登录...")
        page.get('https://dashboard.katabump.com/auth/login')
        wait_for_cloudflare(page)
        
        if page.ele('css:input[name="email"]'):
            print(">>> 输入账号...")
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            page.ele('css:button[type="submit"]').click()
            
            # 【提速】等待 URL 变化，变了就走，不等 10 秒
            print(">>> 等待跳转...")
            page.wait.url_change('login', exclude=True, timeout=10)
            wait_for_cloudflare(page)

        # ==================== 2. 循环尝试 (3次) ====================
        # 减少为 3 次，避免浪费时间
        for attempt in range(1, 4):
            print(f"\n🚀 [Step 2] 尝试 ({attempt}/3)...")
            try:
                page.get(target_url)
                # 等待 Renew 按钮出现，最多等 5 秒
                renew_btn = page.wait.ele_displayed('css:button:contains("Renew")', timeout=5)
                
                if not renew_btn:
                    # 没按钮，可能已经续期了，检查一下文字
                    res = check_result(page)
                    if res == "SUCCESS": break
                    print("⚠️ 没按钮也没成功提示，重试...")
                    continue

                robust_click(renew_btn)
                
                # 等待弹窗出现
                modal = page.wait.ele_displayed('css:.modal-content', timeout=5)
                if modal:
                    # 处理验证码
                    solve_modal_captcha(modal)
                    
                    # 找确认按钮
                    confirm = modal.ele('css:button.btn-primary')
                    if confirm and confirm.states.is_enabled:
                        robust_click(confirm)
                        # 等待结果回显
                        time.sleep(3) 
                        if check_result(page) == "SUCCESS":
                            break
                    else:
                        print("⚠️ 按钮灰，检查结果...")
                        if check_result(page) == "SUCCESS": break
                else:
                    print("❌ 弹窗未出")
            
            except Exception as e:
                print(f"❌ 异常: {e}")
            
            # 失败后简短休息
            if attempt < 3: time.sleep(3)

        print("\n🏁 脚本运行结束")

    except Exception as e:
        print(f"❌ 崩溃: {e}")
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
