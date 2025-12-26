import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import json
import os
import time
import shutil

# === 配置区域 ===
JSON_FILE = 'showcase.json'
IMG_DIR = 'gallery_images'
MAX_WIDTH = 1280  # 压缩后的最大宽度
QUALITY = 85  # JPG 质量
WINDOW_TITLE = "NovelAI 图库管理器"

# 确保目录存在
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)


class GalleryManager:
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1000x600")

        # 数据内存缓存
        self.data = []
        self.load_data()

        # 当前选中的图片路径（用于新增或修改）
        self.temp_image_path = None
        self.current_editing_id = None  # 如果不为None，说明正在编辑模式

        self.setup_ui()
        self.refresh_list()

    def load_data(self):
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except:
                self.data = []
        else:
            self.data = []

    def save_data(self):
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def setup_ui(self):
        # === 布局 ===
        # 左边是列表，右边是编辑器
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = tk.Frame(paned, width=400)
        right_frame = tk.Frame(paned)
        paned.add(left_frame)
        paned.add(right_frame)

        # === 左侧列表 ===
        # 表头
        columns = ("title", "category")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings")
        self.tree.heading("title", text="标题")
        self.tree.heading("category", text="分类")
        self.tree.column("title", width=200)
        self.tree.column("category", width=80)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定点击事件
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # === 右侧编辑器 ===
        # 标题输入
        tk.Label(right_frame, text="标题:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.entry_title = tk.Entry(right_frame)
        self.entry_title.pack(fill=tk.X, pady=(0, 10))

        # 分类选择
        tk.Label(right_frame, text="分类:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.var_category = tk.StringVar(value="run")
        cat_frame = tk.Frame(right_frame)
        cat_frame.pack(anchor="w", pady=(0, 10))
        tk.Radiobutton(cat_frame, text="精选成品 (Run)", variable=self.var_category, value="run").pack(side=tk.LEFT,
                                                                                                       padx=10)
        tk.Radiobutton(cat_frame, text="画师组合 (Combo)", variable=self.var_category, value="combo").pack(side=tk.LEFT)

        # 图片操作区
        tk.Label(right_frame, text="图片:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        img_btn_frame = tk.Frame(right_frame)
        img_btn_frame.pack(anchor="w", fill=tk.X)

        tk.Button(img_btn_frame, text="📁 选择图片...", command=self.choose_image).pack(side=tk.LEFT)
        self.lbl_img_status = tk.Label(img_btn_frame, text="未选择", fg="#666")
        self.lbl_img_status.pack(side=tk.LEFT, padx=10)

        # 图片缩略图预览
        self.lbl_preview = tk.Label(right_frame, bg="#eee", text="预览区域", height=8)
        self.lbl_preview.pack(fill=tk.X, pady=10)

        # Prompt 输入
        tk.Label(right_frame, text="提示词 / Prompt:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.txt_prompt = tk.Text(right_frame, height=10)
        self.txt_prompt.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 按钮区
        btn_frame = tk.Frame(right_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        self.btn_save = tk.Button(btn_frame, text="💾 保存新增", bg="#2ecc71", fg="white", font=("Arial", 10, "bold"),
                                  command=self.save_item)
        self.btn_save.pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="🗑️ 删除选中", bg="#e74c3c", fg="white", command=self.delete_item).pack(side=tk.RIGHT,
                                                                                                          padx=5)
        tk.Button(btn_frame, text="🧹 清空/新建", command=self.clear_form).pack(side=tk.RIGHT, padx=5)

    def refresh_list(self):
        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 重新填充
        for item in self.data:
            display_cat = "精选图" if item['category'] == 'run' else "画师串"
            self.tree.insert("", "end", iid=str(item['id']), values=(item['title'], display_cat))

    def choose_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.temp_image_path = path
            self.lbl_img_status.config(text=os.path.basename(path))
            self.show_preview(path)

    def show_preview(self, path):
        # 显示缩略图逻辑
        try:
            img = Image.open(path)
            # 缩放到高度 150 以内显示
            aspect = img.width / img.height
            new_h = 150
            new_w = int(new_h * aspect)
            img = img.resize((new_w, new_h))
            self.photo = ImageTk.PhotoImage(img)  # 必须保持引用
            self.lbl_preview.config(image=self.photo, text="", height=0)  # height=0 让它自适应图片
        except Exception as e:
            self.lbl_preview.config(text=f"无法预览: {e}", image="")

    def on_select(self, event):
        # 当点击列表某一项时，填充右侧
        selected = self.tree.selection()
        if not selected: return

        item_id = int(selected[0])
        # 查找数据
        record = next((x for x in self.data if x['id'] == item_id), None)
        if record:
            self.current_editing_id = item_id

            # 填充表单
            self.entry_title.delete(0, tk.END)
            self.entry_title.insert(0, record['title'])

            self.var_category.set(record['category'])

            self.txt_prompt.delete("1.0", tk.END)
            self.txt_prompt.insert("1.0", record['prompt'])

            # 图片处理
            self.temp_image_path = None  # 重置临时路径
            self.lbl_img_status.config(text="保持原图 (如需修改请点击选择)")
            self.show_preview(record['image'])  # 这里传入的是相对路径 gallery_images/xxx.jpg

            # 按钮变更为“保存修改”
            self.btn_save.config(text="💾 保存修改", bg="#3498db")

    def clear_form(self):
        self.current_editing_id = None
        self.entry_title.delete(0, tk.END)
        self.txt_prompt.delete("1.0", tk.END)
        self.var_category.set("run")
        self.temp_image_path = None
        self.lbl_img_status.config(text="未选择")
        self.lbl_preview.config(image="", text="预览区域", height=8)
        self.btn_save.config(text="💾 保存新增", bg="#2ecc71")
        self.tree.selection_remove(self.tree.selection())

    def process_image(self, source_path):
        """压缩并保存图片，返回相对路径"""
        try:
            with Image.open(source_path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # 调整大小
                if img.width > MAX_WIDTH:
                    new_h = int(img.height * (MAX_WIDTH / img.width))
                    img = img.resize((MAX_WIDTH, new_h), Image.Resampling.LANCZOS)

                timestamp = int(time.time() * 1000)
                filename = f"img_{timestamp}.jpg"
                target_path = os.path.join(IMG_DIR, filename)

                img.save(target_path, "JPEG", quality=QUALITY, optimize=True)
                return f"{IMG_DIR}/{filename}"
        except Exception as e:
            messagebox.showerror("错误", f"图片处理失败: {e}")
            return None

    def save_item(self):
        title = self.entry_title.get().strip()
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        category = self.var_category.get()

        if not title:
            messagebox.showwarning("提示", "标题不能为空")
            return

        # === 模式 A: 修改现有条目 ===
        if self.current_editing_id is not None:
            # 找到原始数据
            record = next((x for x in self.data if x['id'] == self.current_editing_id), None)
            if record:
                record['title'] = title
                record['prompt'] = prompt
                record['category'] = category

                # 如果用户选了新图，处理新图，删旧图
                if self.temp_image_path:
                    new_img_path = self.process_image(self.temp_image_path)
                    if new_img_path:
                        # 尝试删除旧图
                        if os.path.exists(record['image']):
                            try:
                                os.remove(record['image'])
                            except:
                                pass
                        record['image'] = new_img_path

                self.save_data()
                self.refresh_list()
                messagebox.showinfo("成功", "修改已保存")
                self.clear_form()  # 保存后清空，方便下一次

        # === 模式 B: 新增条目 ===
        else:
            if not self.temp_image_path:
                messagebox.showwarning("提示", "请选择一张图片")
                return

            img_rel_path = self.process_image(self.temp_image_path)
            if img_rel_path:
                new_id = int(time.time() * 1000)
                new_entry = {
                    "id": new_id,
                    "title": title,
                    "category": category,
                    "image": img_rel_path,
                    "prompt": prompt
                }
                # 新增到最前
                self.data.insert(0, new_entry)
                self.save_data()
                self.refresh_list()
                self.clear_form()
                messagebox.showinfo("成功", "添加成功")

    def delete_item(self):
        selected = self.tree.selection()
        if not selected: return

        if not messagebox.askyesno("确认", "确定要删除这条记录吗？\n(关联的图片文件也会被删除)"):
            return

        item_id = int(selected[0])
        record = next((x for x in self.data if x['id'] == item_id), None)

        if record:
            # 删除本地文件
            if os.path.exists(record['image']):
                try:
                    os.remove(record['image'])
                except:
                    pass

            # 删除数据
            self.data = [x for x in self.data if x['id'] != item_id]
            self.save_data()
            self.refresh_list()
            self.clear_form()


if __name__ == "__main__":
    root = tk.Tk()
    app = GalleryManager(root)
    root.mainloop()