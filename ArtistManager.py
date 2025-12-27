import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
import json
import os
import requests
import threading
import time
import re

# ================= 代理设置 =================
PROXY_PORT = '7897'

os.environ["http_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"
os.environ["https_proxy"] = f"http://127.0.0.1:{PROXY_PORT}"

# ================= 配置区域 =================
CONFIG_FILE = 'config.json'
ARTIST_FILE = 'artists.txt'
DATA_FILE = 'artist_data.json'
IMAGE_DIR = 'images'
# 使用特定 UA 防止被判定为脚本攻击
DEFAULT_HEADERS = {'User-Agent': 'NovelAI_Artist_Manager/HighRes_v7'}

API_STATUS_CODES = {
    200: "请求成功",
    204: "请求成功 (无内容)",
    400: "参数错误 (Bad Request)",
    401: "认证失败 (检查账号/API Key)",
    403: "拒绝访问 (权限不足/被禁止)",
    404: "未找到 (Not Found)",
    410: "分页限制 (Gone)",
    420: "无效记录",
    422: "资源锁定或验证失败",
    423: "资源已存在",
    424: "参数无效",
    429: "请求过于频繁 (被限流，请稍后)",
    500: "服务器内部错误",
    502: "网关错误 (服务器负载过高)",
    503: "服务不可用 (Downbooru)",
}

class ArtistManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NovelAI 画师图鉴管理器 (高清修复版)")
        self.root.geometry("1050x750")

        self.artists = []
        self.config = self.load_config()
        self.is_running = False
        self.current_preview_image = None

        self.setup_ui()
        self.load_artists_from_file()

    # ================= 界面布局 =================
    def setup_ui(self):
        # 1. 顶部 API 设置
        top_frame = tk.LabelFrame(self.root, text="API 设置", padx=10, pady=5)
        top_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(top_frame, text="User:").pack(side="left")
        self.entry_user = tk.Entry(top_frame, width=15)
        self.entry_user.pack(side="left", padx=5)
        self.entry_user.insert(0, self.config.get('username', ''))

        tk.Label(top_frame, text="API Key:").pack(side="left")
        self.entry_key = tk.Entry(top_frame, width=35, show="*")
        self.entry_key.pack(side="left", padx=5)
        self.entry_key.insert(0, self.config.get('api_key', ''))

        tk.Button(top_frame, text="保存配置", command=self.save_config).pack(side="left", padx=10)

        # 2. 主体左右分栏
        main_pane = tk.PanedWindow(self.root, orient="horizontal", sashwidth=5)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # === 左侧：列表 ===
        left_frame = tk.Frame(main_pane)
        main_pane.add(left_frame, width=320)

        search_frame = tk.Frame(left_frame)
        search_frame.pack(fill="x", pady=2)
        tk.Label(search_frame, text="🔍").pack(side="left")
        self.entry_search = tk.Entry(search_frame)
        self.entry_search.pack(side="left", fill="x", expand=True)
        self.entry_search.bind("<KeyRelease>", self.filter_list)

        self.listbox = tk.Listbox(left_frame, selectmode=tk.SINGLE, font=("Consolas", 10), activestyle='dotbox')
        scroll = tk.Scrollbar(left_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        # === 右侧：预览与操作 ===
        right_frame = tk.Frame(main_pane)
        main_pane.add(right_frame)

        # 预览区
        preview_frame = tk.LabelFrame(right_frame, text="预览区", height=320)
        preview_frame.pack(fill="x", padx=5, pady=5)
        preview_frame.pack_propagate(False)
        self.lbl_preview = tk.Label(preview_frame, text="点击左侧列表查看预览", bg="#f0f0f0")
        self.lbl_preview.pack(fill="both", expand=True, padx=5, pady=5)

        # 按钮区
        btn_frame = tk.Frame(right_frame)
        btn_frame.pack(fill="x", padx=5, pady=5)
        tk.Button(btn_frame, text="🖼️ 替换选中画师图片", command=self.replace_image_for_selected).pack(fill="x", pady=2)

        manage_frame = tk.LabelFrame(right_frame, text="库管理")
        manage_frame.pack(fill="x", padx=5, pady=5)
        manage_frame.columnconfigure(0, weight=1);
        manage_frame.columnconfigure(1, weight=1)

        tk.Button(manage_frame, text="➕ 批量导入", command=self.open_batch_add_window).grid(row=0, column=0,
                                                                                            sticky="ew", padx=2, pady=2)
        tk.Button(manage_frame, text="✨ 手动新增", command=self.open_manual_add_window, bg="#e3f2fd").grid(row=0,
                                                                                                           column=1,
                                                                                                           sticky="ew",
                                                                                                           padx=2,
                                                                                                           pady=2)
        tk.Button(manage_frame, text="✏️ 重命名", command=self.edit_artist).grid(row=1, column=0, sticky="ew", padx=2,
                                                                                 pady=2)
        tk.Button(manage_frame, text="🗑️ 彻底删除", command=self.delete_artist, fg="red").grid(row=1, column=1,
                                                                                               sticky="ew", padx=2,
                                                                                               pady=2)

        # 日志区
        log_frame = tk.LabelFrame(right_frame, text="系统日志")
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)
        log_scroll = tk.Scrollbar(log_frame)
        log_scroll.pack(side="right", fill="y")
        self.log_text = tk.Text(log_frame, height=10, state='disabled', font=("Consolas", 9), bg="#f9f9f9",
                                yscrollcommand=log_scroll.set)
        self.log_text.pack(fill="both", expand=True)
        log_scroll.config(command=self.log_text.yview)

        # 底部运行
        bottom_frame = tk.Frame(self.root, pady=5)
        bottom_frame.pack(fill="x", padx=10)
        self.progress = ttk.Progressbar(bottom_frame, orient="horizontal", mode='determinate')
        self.progress.pack(fill="x", pady=2)
        self.btn_run = tk.Button(bottom_frame, text="🚀 启动自动更新 (下载高清样图)", command=self.run_process_thread,
                                 bg="#4caf50", fg="white", font=("Arial", 11, "bold"))
        self.btn_run.pack(fill="x")

    # ================= 核心数据管理逻辑 =================

    def manage_json_record(self, delete_name=None, add_name=None, add_path=None):
        """原子化管理 JSON 数据：删旧 + 增新 + 排序"""
        data = []
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                data = []

        if delete_name:
            data = [item for item in data if item['name'] != delete_name]

        if add_name:
            data = [item for item in data if item['name'] != add_name]
            data.append({"name": add_name, "image": add_path})

        data.sort(key=lambda x: x['name'])

        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def process_and_save_image(self, source_path, artist_name):
        try:
            if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)
            safe_name = self.get_safe_filename(artist_name)
            target_path = os.path.join(IMAGE_DIR, f"{safe_name}.jpg")

            img = Image.open(source_path)
            img = img.convert('RGB')
            # 质量设为 95 保证清晰度
            img.save(target_path, 'JPEG', quality=95)

            self.log(f"图片处理完成: {target_path}")
            return target_path
        except Exception as e:
            messagebox.showerror("图片错误", f"无法处理图片: {str(e)}")
            return None

    # ================= 交互功能 =================

    def edit_artist(self):
        sel = self.listbox.curselection()
        if not sel: return
        old_name = self.listbox.get(sel[0])
        new_name = simpledialog.askstring("重命名", "新画师名:", initialvalue=old_name)
        if not new_name: return
        clean_new = self.clean_name(new_name)
        if not clean_new or clean_new == old_name: return

        if clean_new in self.artists:
            messagebox.showwarning("错误", "名字已存在")
            return

        self.artists[self.artists.index(old_name)] = clean_new
        self.save_artists_to_file()

        old_safe = self.get_safe_filename(old_name)
        new_safe = self.get_safe_filename(clean_new)
        old_path = os.path.join(IMAGE_DIR, f"{old_safe}.jpg")
        new_path = os.path.join(IMAGE_DIR, f"{new_safe}.jpg")

        has_img = False
        if os.path.exists(old_path):
            try:
                self.lbl_preview.config(image='');
                self.current_preview_image = None
                os.rename(old_path, new_path)
                has_img = True
                self.log(f"文件重命名: {old_path} -> {new_path}")
            except Exception as e:
                self.log(f"重命名文件失败: {e}")

        if has_img:
            self.manage_json_record(delete_name=old_name, add_name=clean_new, add_path=new_path)
        else:
            self.manage_json_record(delete_name=old_name)

        self.refresh_list()
        try:
            idx = self.artists.index(clean_new)
            self.listbox.selection_set(idx);
            self.on_list_select(None)
        except:
            pass

    def delete_artist(self):
        sel = self.listbox.curselection()
        if not sel: return
        name = self.listbox.get(sel[0])
        if messagebox.askyesno("删除", f"确定删除 {name}？"):
            if name in self.artists:
                self.artists.remove(name);
                self.save_artists_to_file()
            path = os.path.join(IMAGE_DIR, f"{self.get_safe_filename(name)}.jpg")
            if os.path.exists(path):
                self.lbl_preview.config(image='');
                self.current_preview_image = None
                try:
                    os.remove(path)
                except:
                    pass
            self.manage_json_record(delete_name=name)
            self.refresh_list()
            self.lbl_preview.config(image='', text='已删除')

    def replace_image_for_selected(self):
        sel = self.listbox.curselection()
        if not sel: return
        name = self.listbox.get(sel[0])
        f = filedialog.askopenfilename()
        if f:
            np = self.process_and_save_image(f, name)
            if np:
                self.manage_json_record(add_name=name, add_path=np)
                self.show_preview(np)

    # ================= 自动更新逻辑 (含高清修复) =================
    def run_process_thread(self):
        if self.is_running: return
        user, key = self.entry_user.get().strip(), self.entry_key.get().strip()
        if not user or not key: return messagebox.showerror("错误", "请先配置 API 信息")

        self.is_running = True
        self.btn_run.config(state='disabled')
        t = threading.Thread(target=self.dl_worker, args=(user, key))
        t.daemon = True
        t.start()

    def dl_worker(self, user, key):
        self.log("=== 🚀 开始自动更新 ===")
        if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)

        stats = {'total': len(self.artists), 'skip': 0, 'new': 0, 'fail': []}

        # 读取现有数据
        res_map = {}
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    res_map = {item['name']: item['image'] for item in json.load(f)}
            except:
                pass

        self.progress['maximum'] = stats['total']

        for i, art in enumerate(self.artists):
            self.progress['value'] = i + 1
            safe_name = self.get_safe_filename(art)
            path = os.path.join(IMAGE_DIR, f"{safe_name}.jpg")

            # 检查本地
            if os.path.exists(path):
                stats['skip'] += 1
                res_map[art] = path
                self.log(f"[{i + 1}] {art}: ✅ 已存在")
                continue

            # 下载
            self.log(f"[{i + 1}] {art}: ⏳ 搜索中...")

            # 第一尝试：全年龄
            url, error_msg = self._fetch(art, 'rating:general', user, key)

            # 如果没找到且没有严重错误，尝试无分级限制（可能是R18画师）
            if not url and (error_msg and "为空" in error_msg):
                self.log(f"    -> ⚠️ 全年龄未找到，尝试全部分级...")
                time.sleep(1)  # 稍微暂停防止429
                url, error_msg = self._fetch(art, '', user, key)

            if url:
                self.log(f"    -> 捕捉到链接，下载中...")
                if self._dl(url, path):
                    stats['new'] += 1
                    res_map[art] = path
                    self.log(f"    -> 🎉 成功")
                else:
                    stats['fail'].append(art)
                    self.log(f"    -> ❌ 下载流断开或写入失败")
            else:
                stats['fail'].append(art)
                # 打印具体的 API 错误信息
                self.log(f"    -> ❌ 获取失败: {error_msg}")

            # 增加延时，防止 429 User Throttled
            time.sleep(2)

            # 保存结果
        final_list = [{"name": k, "image": v} for k, v in res_map.items() if k in self.artists]
        final_list.sort(key=lambda x: x['name'])
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, indent=2)

        self.is_running = False
        self.btn_run.config(state='normal')

        # 报告
        sep = "=" * 30
        self.log(f"\n{sep}\n统计报告\n{sep}")
        self.log(f"总数: {stats['total']} | 跳过: {stats['skip']} | 新增: {stats['new']} | 失败: {len(stats['fail'])}")
        if stats['fail']:
            self.log("失败列表 (请检查日志中的具体错误原因):")
            for f in stats['fail']: self.log(f"artist:{f}")
        messagebox.showinfo("完成", "更新结束")

    # ================= 关键修改：API 获取逻辑 =================
    def _fetch(self, t, ex, u, k):
        try:
            # 构造 Tag，处理 ex 为空的情况
            search_tag = f'{t} {ex} order:score'.strip()

            params = {
                'tags': search_tag,
                'limit': 1,
                # 某些老旧图片可能没有 large_file_url，增加 source 方便调试
                'only': 'large_file_url,file_url,preview_file_url,id'
            }

            # 优化 UA，包含用户名有助于防止被封禁（如果用户填了的话）
            headers = DEFAULT_HEADERS.copy()
            if u:
                headers['User-Agent'] = f'NovelAI_Artist_Manager/2.0 ({u})'

            # 发起请求
            r = requests.get('https://danbooru.donmai.us/posts.json',
                             params=params,
                             auth=(u, k),
                             headers=headers,
                             timeout=15)

            # 状态码判断
            if r.status_code == 200:
                data = r.json()
                if not data:
                    return None, "搜索结果为空 (Tag可能不匹配)"

                post = data[0]
                url = post.get('large_file_url') or post.get('file_url') or post.get('preview_file_url')

                if not url:
                    return None, f"找到记录但无图片链接 (ID: {post.get('id')})"

                return url, None

            else:
                # 返回具体的 HTTP 错误码和文档描述
                error_desc = API_STATUS_CODES.get(r.status_code, "未知错误")
                return None, f"API {r.status_code}: {error_desc}"

        except requests.exceptions.ConnectionError:
            return None, "网络连接失败 (DNS/代理问题)"
        except requests.exceptions.Timeout:
            return None, "请求超时"
        except json.JSONDecodeError:
            return None, "API 返回了非 JSON 数据 (可能是 Cloudflare 拦截)"
        except Exception as e:
            return None, f"脚本异常: {str(e)}"

    def _dl(self, u, p):
        try:
            # 1. 发起请求，增加 headers 伪装
            headers = DEFAULT_HEADERS.copy()
            # 如果配置里有 user，带上 user 更好
            user = self.entry_user.get().strip()
            if user: headers['User-Agent'] = f'NovelAI_Artist_Manager/2.0 ({user})'

            with requests.get(u, stream=True, timeout=20, headers=headers, verify=False) as r:
                r.raise_for_status()

                # 2. 检查 Content-Type (防止把 html 网页当图片下)
                ct = r.headers.get('Content-Type', '').lower()
                if 'image' not in ct and 'octet-stream' not in ct:
                    self.log(f"    -> ⚠️ 警告: 服务器返回的不是图片，而是 {ct}")
                    return False

                # 3. 写入文件
                with open(p, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)

            # 4. 【关键步骤】下载完成后，校验图片完整性
            # 如果是网页或坏文件，这里会报错，从而触发 except 删除坏文件
            try:
                with Image.open(p) as img:
                    img.verify()  # 校验文件结构是否损坏
            except Exception as e:
                self.log(f"    -> ⚠️ 图片文件损坏或无效，已删除 ({e})")
                if os.path.exists(p):
                    os.remove(p)  # 删掉坏文件，防止看着闹心
                return False

            return True

        except Exception as e:
            # 如果发生网络错误，也要确保没有留下半截的坏文件
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass
            # 打印一点简单的错误提示（可选）
            # print(f"下载异常: {e}")
            return False

    # ================= 基础工具 =================
    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def get_safe_filename(self, name):
        return re.sub(r'[\\/*?:"<>|]', "_", name)

    def clean_name(self, name):
        return name.lower().strip().replace('artist:', '').replace(',', '').strip()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        return {}

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f: json.dump(
            {'username': self.entry_user.get(), 'api_key': self.entry_key.get()}, f)
        messagebox.showinfo("OK", "配置已保存")

    def load_artists_from_file(self):
        if not os.path.exists(ARTIST_FILE): open(ARTIST_FILE, 'w').close()
        with open(ARTIST_FILE, 'r', encoding='utf-8') as f: l = f.readlines()
        self.artists = sorted(list(set([self.clean_name(x) for x in l if self.clean_name(x)])))
        self.refresh_list()

    def save_artists_to_file(self):
        with open(ARTIST_FILE, 'w', encoding='utf-8') as f:
            for a in sorted(self.artists): f.write(a + "\n")

    def refresh_list(self, f=""):
        self.listbox.delete(0, tk.END)
        for a in self.artists:
            if f.lower() in a: self.listbox.insert(tk.END, a)
        self.root.title(f"NovelAI 画师管理器 (HighRes) - {len(self.artists)} 人")

    def filter_list(self, e):
        self.refresh_list(self.entry_search.get())

    def on_list_select(self, e):
        s = self.listbox.curselection()
        if not s: return
        p = os.path.join(IMAGE_DIR, f"{self.get_safe_filename(self.listbox.get(s[0]))}.jpg")
        self.show_preview(p)

    def show_preview(self, p):
        if os.path.exists(p):
            try:
                img = Image.open(p)
                w, h = img.size
                r = min(320 / w, 300 / h)
                self.current_preview_image = ImageTk.PhotoImage(
                    img.resize((int(w * r), int(h * r)), Image.Resampling.LANCZOS))
                self.lbl_preview.config(image=self.current_preview_image, text="")
            except:
                self.lbl_preview.config(image='', text="图片错误")
        else:
            self.lbl_preview.config(image='', text="无图片")

    def open_batch_add_window(self):
        win = tk.Toplevel(self.root);
        win.title("批量");
        win.geometry("500x400")
        t = tk.Text(win);
        t.pack(fill="both", expand=True)

        def run():
            raw = t.get("1.0", tk.END);
            tkns = re.split(r'[,\n，;；]+', raw);
            c = 0
            for k in tkns:
                n = self.clean_name(k)
                if n and n not in self.artists: self.artists.append(n); c += 1
            if c: self.save_artists_to_file(); self.refresh_list(); messagebox.showinfo("OK",
                                                                                        f"导入 {c}"); win.destroy()

        tk.Button(win, text="导入", command=run).pack(fill="x")

    def open_manual_add_window(self):
        win = tk.Toplevel(self.root);
        win.title("新增");
        win.geometry("400x250")
        tk.Label(win, text="名:").pack();
        en = tk.Entry(win);
        en.pack()
        tk.Label(win, text="图:").pack();
        ep = tk.Entry(win);
        ep.pack()

        def sel():
            f = filedialog.askopenfilename();
            if f: ep.delete(0, tk.END); ep.insert(0, f)

        tk.Button(win, text="浏览", command=sel).pack()

        def ok():
            n, p = self.clean_name(en.get()), ep.get()
            if n and p:
                if n not in self.artists: self.artists.append(n); self.save_artists_to_file(); self.refresh_list()
                np = self.process_and_save_image(p, n)
                if np: self.manage_json_record(add_name=n, add_path=np); win.destroy(); messagebox.showinfo("OK",
                                                                                                            "成功")

        tk.Button(win, text="保存", command=ok).pack(fill="x")


if __name__ == "__main__":
    root = tk.Tk()
    app = ArtistManagerApp(root)
    root.mainloop()