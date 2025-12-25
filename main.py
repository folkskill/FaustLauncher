import tkinter as tk
from tkinter import ttk, font
import os
import random
import sys
import json
from PIL import Image, ImageTk, ImageFilter
from json import load
import pymysql
from subprocess import Popen
from functions.settings_page import init_settings_page
from functions.settings_manager import get_settings_manager

# 添加自定义汉化工具导入
try:
    sys.path.append('functions')
    from functions.custom_translation import open_custom_translation_tool
except ImportError as e:
    print(f"导入自定义汉化工具失败: {e}")
    open_custom_translation_tool = None

dowloading = False
root: tk.Tk = None # type: ignore
config_path = ""
settings_manager = get_settings_manager()

class TerminalRedirector:
    """重定向print输出到文本组件的类"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.buffer = ""  # 缓冲区用于处理部分消息
    
    def write(self, message):
        """重定向write方法"""
        if message:
            # 添加到缓冲区
            self.buffer += message
            
            # 如果缓冲区以换行符结尾，处理完整消息
            if self.buffer.endswith('\n'):
                # 移除结尾的换行符
                full_message = self.buffer.rstrip('\n')
                if full_message:  # 只处理非空消息
                    self._add_message_to_terminal(full_message)
                # 清空缓冲区
                self.buffer = ""
    
    def _add_message_to_terminal(self, message):
        """添加格式化消息到终端"""
        if '\r' in message:
            return
        self.text_widget.config(state=tk.NORMAL)
        
        # 添加时间戳
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 根据消息内容确定级别
        level = "info"
        if "错误" in message or "失败" in message or "❌" in message:
            level = "error"
        elif "成功" in message or "完成" in message or "✅" in message:
            level = "success"
        elif "警告" in message or "⚠️" in message:
            level = "warning"
        
        # 插入带时间戳和颜色的消息
        self.text_widget.insert(tk.END, f"[{timestamp}] ", "info")
        self.text_widget.insert(tk.END, message + "\n", level)
        
        # 自动滚动到底部
        self.text_widget.see(tk.END)
        
        # 禁用文本编辑
        self.text_widget.config(state=tk.DISABLED)
        
        # 立即更新显示
        self.text_widget.update_idletasks()
    
    def flush(self):
        """重定向flush方法"""
        # 处理缓冲区中剩余的消息
        if self.buffer:
            self._add_message_to_terminal(self.buffer)
            self.buffer = ""
    
    def start_redirect(self):
        """开始重定向"""
        sys.stdout = self
        sys.stderr = self
    
    def stop_redirect(self):
        """停止重定向"""
        # 刷新缓冲区
        self.flush()
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

class FaustLauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Faust Launcher")
        self.root.geometry("900x700")
        self.root.resizable(False, False)
        
        # 设置应用程序图标
        try:
            if os.path.exists("images/icon/icon.ico"):
                self.root.iconbitmap("images/icon/icon.ico")
        except:
            pass
        
        # 背景图片相关
        self.background_images = []
        self.current_bg_index = 0
        self.current_bg_image = None
        self.current_blurred_bg = None
        self.load_background_images()
        
        # 创建主容器框架 - 使用深蓝色背景
        self.container = tk.Frame(self.root, bg='#2c3e50')
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # 创建背景Canvas - 覆盖整个窗口
        self.bg_canvas = tk.Canvas(self.container, highlightthickness=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        # 创建内容容器 - 使用半透明深蓝色背景
        self.content_frame = tk.Frame(self.container, bg='#34495e')
        self.content_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER, width=800, height=600)
        
        # 创建分页控件 - 使用深蓝色背景
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建四个页面 - 使用深蓝色背景（添加工具页）
        self.home_frame = tk.Frame(self.notebook, bg='#34495e')
        self.features_frame = tk.Frame(self.notebook, bg='#34495e')
        self.tools_frame = tk.Frame(self.notebook, bg='#34495e')  # 新增工具页
        self.about_frame = tk.Frame(self.notebook, bg='#34495e')
        self.settings_frame = tk.Frame(self.notebook, bg='#34495e')
        
        # 添加页面到分页控件
        self.notebook.add(self.home_frame, text="🏘 主页")
        self.notebook.add(self.features_frame, text="✈ 快捷方式")
        self.notebook.add(self.tools_frame, text="🔨 工具页")
        self.notebook.add(self.settings_frame, text="⚙️ 设置")
        self.notebook.add(self.about_frame, text="💻 关于")
        
        # 绑定分页切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # 设置样式
        self.set_styles()

        # 初始化各页面
        self.init_home_page()
        self.init_features_page()
        self.init_tools_page()  # 新增工具页初始化
        self.init_settings_page()
        self.init_about_page()
        
        # 启动背景轮换
        self.start_background_rotation()
        
        # 设置终端重定向
        self.setup_terminal_redirect()

        # 检查设置
        self.root.after(100, self.check_settings)
    
    def init_settings_page(self):
        """初始化设置页面"""
        try:
            self.settings_page = init_settings_page(self.settings_frame)
        except Exception as e:
            print(f"初始化设置页面失败: {e}")
            # 创建错误提示
            error_label = tk.Label(self.settings_frame, 
                                 text="❌ 设置页面加载失败",
                                 font=('Microsoft YaHei UI', 16),
                                 bg='#34495e', fg='white')
            error_label.pack(expand=True)
            
            detail_label = tk.Label(self.settings_frame,
                                  text=str(e),
                                  font=('Microsoft YaHei UI', 10),
                                  bg='#34495e', fg='#bdc3c7')
            detail_label.pack()

    def init_tools_page(self):
        """初始化工具页内容"""
        from functions.handle_colorful import test_color_gradient_gui
        from functions.select_font import select_font_gui

        # 创建标题标签
        title_label = ttk.Label(self.tools_frame, text="🔧 工具页", style="Title.TLabel")
        title_label.pack(pady=30)
        
        # 创建工具区域 - 使用深蓝色背景
        tools_container = tk.Frame(self.tools_frame, bg='#34495e')
        tools_container.pack(fill=tk.BOTH, expand=True, padx=50, pady=20)
        
        # 创建工具列表
        tools = [
            {"name": "🔧 自定义汉化", "description": "编辑workshop目录下的JSON文件\n实现自定义的汉化修改。", "color": "#3498db", "command": self.open_custom_translation_tool},
            {"name": "🚜 文件夹超链接", "description": "为文件夹制作超链接，达到转移空间的目的？", "color": "#34db34", "command": self.folder_link},
            {"name": "💻 渐变文本处理器", "description": "根据用户输入的文本生成渐变的 Untity 富文本。", "color": "#FFBD30", "command": test_color_gradient_gui},
            {"name": "📝 字体修改", "description": "修改汉化包的字体，使用你自己喜欢的字体包代替。", "color": "#FA3E3E", "command": select_font_gui},
        ]
        
        # 使用网格布局创建工具卡片
        for i, tool in enumerate(tools):
            row = i // 2
            col = i % 2
            
            # 创建工具卡片
            card_frame = tk.Frame(tools_container, 
                                bg=tool['color'],
                                relief='raised',
                                borderwidth=2)
            card_frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            card_frame.grid_propagate(False)
            card_frame.configure(width=250, height=150)
            
            # 添加工具标题
            title_label = tk.Label(card_frame, 
                                 text=tool['name'],
                                 bg=tool['color'],
                                 fg='white',
                                 font=('Microsoft YaHei UI', 14, 'bold'))
            title_label.pack(pady=(20, 10))
            
            # 添加工具描述
            desc_label = tk.Label(card_frame, 
                                text=tool['description'],
                                bg=tool['color'],
                                fg='white',
                                font=('Microsoft YaHei UI', 10),
                                wraplength=220)
            desc_label.pack(pady=5)
            
            # 添加操作按钮
            action_button = tk.Button(card_frame, 
                                    text="🚀 打开",
                                    command=tool['command'],
                                    bg='white',
                                    fg=tool['color'],
                                    font=('Microsoft YaHei UI', 9, 'bold'),
                                    relief='flat',
                                    padx=15,
                                    pady=8,
                                    cursor='hand2')
            action_button.pack(pady=15)
            
            # 添加悬停效果
            action_button.bind("<Enter>", lambda e, b=action_button: b.configure(bg=self.darken_color(b.cget('bg'))))
            action_button.bind("<Leave>", lambda e, b=action_button: b.configure(bg='white'))
        
        # 配置网格权重
        for i in range(2):
            tools_container.columnconfigure(i, weight=1)
        for i in range(2):
            tools_container.rowconfigure(i, weight=1)

    def open_custom_translation_tool(self):
        """打开自定义汉化工具"""
        if open_custom_translation_tool:
            try:
                open_custom_translation_tool(self.root)
                print("🔧 自定义汉化工具已打开")
            except Exception as e:
                print(f"❌ 打开自定义汉化工具失败: {e}")
                import tkinter.messagebox as messagebox
                messagebox.showerror("错误", f"打开自定义汉化工具失败: {str(e)}")
        else:
            print("❌ 自定义汉化工具未正确导入")
            import tkinter.messagebox as messagebox
            messagebox.showerror("错误", "自定义汉化工具未正确导入，请检查functions目录")
    
    def show_coming_soon(self):
        """显示即将推出提示"""
        import tkinter.messagebox as messagebox
        messagebox.showinfo("提示", "更多实用工具即将推出！")

    def load_background_images(self):
        """加载背景图片"""
        background_dir = "images/background"
        if os.path.exists(background_dir):
            for file in os.listdir(background_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # 处理文件名中的空格
                    file_path = os.path.join(background_dir, file)
                    self.background_images.append(file_path)
        
        if not self.background_images:
            print("未找到背景图片，将使用默认背景")
        else:
            print(f"找到 {len(self.background_images)} 张背景图片")
    
    def set_background_image(self):
        """设置背景图片 - 居中显示，并添加模糊效果"""
        if self.background_images:
            try:
                # 随机选择一张图片
                bg_path = random.choice(self.background_images)
                # print(f"加载背景图片: {bg_path}")
                
                # 打开图片
                image = Image.open(bg_path)
                
                # 获取窗口大小
                width = self.root.winfo_width() or 900
                height = self.root.winfo_height() or 700
                
                # 确保图片大小合理
                if width < 100: width = 900
                if height < 100: height = 700
                
                # 计算缩放比例，保持图片比例
                img_width, img_height = image.size
                width_ratio = width / img_width
                height_ratio = height / img_height
                scale_ratio = max(width_ratio, height_ratio)  # 确保图片覆盖整个窗口
                
                # 计算缩放后的尺寸
                new_width = int(img_width * scale_ratio)
                new_height = int(img_height * scale_ratio)
                
                # 缩放图片
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # 应用高斯模糊效果
                blurred_image = image.filter(ImageFilter.GaussianBlur(radius=5))
                
                # 转换为PhotoImage
                bg_image = ImageTk.PhotoImage(blurred_image)
                
                # 保存图片引用
                self.current_bg_image = bg_image
                
                # 清除Canvas上的旧图片
                self.bg_canvas.delete("all")
                
                # 计算居中位置
                x_position = (width - new_width) // 2
                y_position = (height - new_height) // 2
                
                # 在Canvas上居中显示模糊背景图片
                self.bg_canvas.create_image(x_position, y_position, 
                                          anchor=tk.NW, 
                                          image=bg_image,
                                          tags="background")
            except Exception as e:
                print(f"加载背景图片失败: {e}")
                # 使用默认背景颜色
                self.bg_canvas.configure(bg='#2c3e50')
        else:
            # 使用默认背景颜色
            self.bg_canvas.configure(bg='#2c3e50')
    
    def start_background_rotation(self):
        """开始背景轮换"""
        # 延迟启动，确保窗口已显示
        self.root.after(100, self.rotate_background)
    
    def rotate_background(self):
        """轮换背景图片"""
        self.set_background_image()
        # 每30秒更换一次背景
        self.root.after(30000, self.rotate_background)
    
    def set_styles(self):
        """设置应用程序的样式"""
        style = ttk.Style()
        
        # 配置自定义主题
        style.theme_use('clam')
        
        style.configure('TNotebook', background='#34495e')
        style.configure('TNotebook.Tab', background='#2c3e50', foreground='#ecf0f1',
                       padding=[15, 5], font=('Microsoft YaHei UI', 10))
        style.map('TNotebook.Tab', background=[('selected', '#3498db')])
        
        # 配置标签样式 - 使用白色文字，在模糊背景上更清晰
        style.configure("Title.TLabel",
                       background='#34495e',
                       foreground='white',
                       font=('Microsoft YaHei UI', 18, 'bold'))
        style.configure("Subtitle.TLabel",
                       background='#34495e',
                       foreground='white',
                       font=('Microsoft YaHei UI', 12))
        
        # 配置标签框架样式 - 使用浅色背景
        style.configure("Custom.TLabelframe",
                       background='#f8f9fa',
                       foreground='#2c3e50',
                       bordercolor='#bdc3c7',
                       relief='raised',
                       borderwidth=2)
        style.configure("Custom.TLabelframe.Label",
                       background='#f8f9fa',
                       foreground='#2c3e50',
                       font=('Microsoft YaHei UI', 11, 'bold'))
        
        # 字体配置
        self.title_font = font.Font(family='Microsoft YaHei UI', size=18, weight='bold')
        self.subtitle_font = font.Font(family='Microsoft YaHei UI', size=12)
        self.normal_font = font.Font(family='Microsoft YaHei UI', size=10)
    
    def init_home_page(self):
        """初始化主页内容"""
        # 创建标题标签
        title_label = ttk.Label(self.home_frame, text="✨ Faust Launcher ✨", style="Title.TLabel")
        title_label.pack(pady=30)
        
        # 创建说明标签
        description = "欢迎使用 Faust Launcher - 您人生中绝无仅有的完美启动器！\n懒人化的一键操作，这就是浮士德大人的聪明才智口牙！"
        desc_label = ttk.Label(self.home_frame, text=description, style="Subtitle.TLabel", justify=tk.CENTER)
        desc_label.pack(pady=20)
        
        # 创建快速操作区域
        quick_actions_frame = ttk.LabelFrame(self.home_frame, text="🚀 快速操作", style="Custom.TLabelframe")
        quick_actions_frame.pack(fill=tk.X, padx=30, pady=20)
        
        # 创建按钮容器 - 使用浅色背景
        button_container = tk.Frame(quick_actions_frame, bg='#f8f9fa')
        button_container.pack(pady=15)
        
        # 创建几个美化按钮 - 使用tkinter支持的十六进制颜色
        buttons_data = [
            {"text": "🚀 启动游戏", "command": run_game, "color": "#2980b9"},
            {"text": "🎯 汉化更新", "command": self.update_translation, "color": "#27ae60"},
            {"text": "📚 使用帮助", "command": self.show_help, "color": "#9b59b6"}
        ]
        
        for i, btn_data in enumerate(buttons_data):
            button = tk.Button(button_container, 
                             text=btn_data["text"],
                             command=btn_data["command"],
                             bg=btn_data["color"],
                             fg='white',
                             font=('Microsoft YaHei UI', 10, 'bold'),
                             relief='flat',
                             padx=20,
                             pady=10,
                             cursor='hand2')
            button.pack(side=tk.LEFT, padx=10)
            # 添加悬停效果
            button.bind("<Enter>", lambda e, b=button: b.configure(bg=self.darken_color(b.cget('bg'))))
            button.bind("<Leave>", lambda e, b=button, c=btn_data["color"]: b.configure(bg=c))
        
        # 创建迷你终端区域 - 替换原来的系统状态面板
        terminal_frame = ttk.LabelFrame(self.home_frame, text="💻 迷你终端", style="Custom.TLabelframe")
        terminal_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # 创建终端工具栏
        terminal_toolbar = tk.Frame(terminal_frame, bg='#f8f9fa')
        terminal_toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        # 添加终端控制按钮
        clear_button = tk.Button(terminal_toolbar, 
                               text="🗑️ 清空终端",
                               command=self.clear_terminal,
                               bg='#e74c3c',
                               fg='white',
                               font=('Microsoft YaHei UI', 8, 'bold'),
                               relief='flat',
                               padx=8,
                               pady=3)
        clear_button.pack(side=tk.LEFT, padx=5)
        
        copy_button = tk.Button(terminal_toolbar,
                              text="📋 复制内容",
                              command=self.copy_terminal_content,
                              bg='#3498db',
                              fg='white',
                              font=('Microsoft YaHei UI', 8, 'bold'),
                              relief='flat',
                              padx=8,
                              pady=3)
        copy_button.pack(side=tk.LEFT, padx=5)
        
        # 创建终端显示区域
        terminal_container = tk.Frame(terminal_frame, bg='#1e1e1e')
        terminal_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建滚动条
        scrollbar = ttk.Scrollbar(terminal_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建终端文本组件
        self.terminal_text = tk.Text(terminal_container,
                                   bg='#1e1e1e',
                                   fg="#ffffff",
                                   font=('Consolas', 10),
                                   yscrollcommand=scrollbar.set,
                                   wrap=tk.WORD,
                                   relief='flat',
                                   borderwidth=0)
        self.terminal_text.pack(fill=tk.BOTH, expand=True)
        
        # 配置滚动条
        scrollbar.config(command=self.terminal_text.yview)
        
        # 设置文本组件为只读
        self.terminal_text.config(state=tk.DISABLED)
        
        # 设置终端重定向
        self.setup_terminal_redirect()
        
        # 添加欢迎信息
        self.add_terminal_message("🚀 Faust Launcher 已启动")
        self.add_terminal_message("💻 终端重定向已启用")
        self.add_terminal_message("=" * 50)
    
    def setup_terminal_redirect(self):
        """设置终端重定向"""
        """设置终端重定向"""
        # 启用文本组件编辑以添加内容
        self.terminal_text.config(state=tk.NORMAL)
        
        # 创建重定向器
        self.terminal_redirector = TerminalRedirector(self.terminal_text)
        self.terminal_redirector.start_redirect()
        
        # 禁用文本组件编辑
        self.terminal_text.config(state=tk.DISABLED)
        
        print("✅ 终端重定向已启用")
    
    def add_terminal_message(self, message):
        """添加消息到终端"""
        self.terminal_text.config(state=tk.NORMAL)
        self.terminal_text.insert(tk.END, message + "\n")
        self.terminal_text.see(tk.END)
        self.terminal_text.config(state=tk.DISABLED)
        self.terminal_text.update_idletasks()
    
    def clear_terminal(self):
        """清空终端内容"""
        self.terminal_text.config(state=tk.NORMAL)
        self.terminal_text.delete(1.0, tk.END)
        self.terminal_text.config(state=tk.DISABLED)
        print("🗑️ 终端内容已清空")
    
    def copy_terminal_content(self):
        """复制终端内容到剪贴板"""
        try:
            content = self.terminal_text.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            print("📋 终端内容已复制到剪贴板")
        except Exception as e:
            print(f"❌ 复制失败: {e}")
    
    def init_features_page(self):
        """初始化功能页内容"""
        # 创建标题标签
        title_label = ttk.Label(self.features_frame, text="🎯 快捷方式", style="Title.TLabel")
        title_label.pack(pady=30)
        
        # 创建功能区域 - 使用深蓝色背景
        features_container = tk.Frame(self.features_frame, bg='#34495e')
        features_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 创建功能列表 - 使用tkinter支持的十六进制颜色
        features = [
            {"name": "📁 游戏目录", "description": "边狱巴士的游戏目录。\n\n", "color": "#ff9c1b"},
            {"name": "🔄 零协会", "description": "一个伟大的社区。\n\n", "color": "#e74c3c"},
            {"name": "📒 气泡文本", "description": "由民间大佬制作的\n气泡mod的汉化版本。\n提取码：fib6", "color": "#3498db"},
            {"name": "📝 维基", "description": "边狱巴士的灰机wiki。\n\n", "color": "#2ecc71"},
            {"name": "📖 N网", "description": "下载边狱巴士mod。\n\n", "color": "#9b59b6"},
            {"name": "📦 mod管理", "description": "管理游戏mod。\n\n", "color": "#e67e22"}
        ]
        
        # 使用网格布局创建功能卡片
        for i, feature in enumerate(features):
            row = i // 3
            col = i % 3
            
            # 创建功能卡片 - 使用tkinter支持的十六进制颜色
            card_frame = tk.Frame(features_container, 
                                bg=feature['color'],
                                relief='raised',
                                borderwidth=2)
            card_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            card_frame.grid_propagate(False)
            card_frame.configure(width=200, height=120)
            
            # 添加功能标题
            title_label = tk.Label(card_frame, 
                                 text=feature['name'],
                                 bg=feature['color'],
                                 fg='white',
                                 font=('Microsoft YaHei UI', 12, 'bold'))
            title_label.pack(pady=(15, 5))
            
            # 添加功能描述
            desc_label = tk.Label(card_frame, 
                                text=feature['description'],
                                bg=feature['color'],
                                fg='white',
                                font=('Microsoft YaHei UI', 9),
                                wraplength=180)
            desc_label.pack(pady=5)
            
            # 添加操作按钮
            action_button = tk.Button(card_frame, 
                                    text="🚀 打开",
                                    command=lambda f=feature: self.open_feature(f),
                                    bg='white',
                                    fg=feature['color'],
                                    font=('Microsoft YaHei UI', 8, 'bold'),
                                    relief='flat',
                                    padx=10,
                                    pady=5,
                                    cursor='hand2')
            action_button.pack(pady=10)
        
        # 配置网格权重
        for i in range(3):
            features_container.columnconfigure(i, weight=1)
        for i in range(2):
            features_container.rowconfigure(i, weight=1)
    
    def init_about_page(self):
        """初始化关于页面内容"""
        # 创建标题标签
        title_label = ttk.Label(self.about_frame, text="ℹ️ 关于 Faust Launcher", style="Title.TLabel")
        title_label.pack(pady=30)
        
        # 创建内容区域 - 使用深蓝色背景
        content_frame = tk.Frame(self.about_frame, bg='#34495e')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=50, pady=20)
        
        # 添加应用程序信息
        about_info = [
            "🌟 版本: 0.3.9-release",
            "👥 开发: FolkSkill"
            "",
            "Faust Launcher 是一个专为懒人但丁设计的现代化一键启动器。"
            "",
            "✨ 特色功能:",
            "零协会汉化自动更新，气泡mod自动更新下载，mod管理，载入，无需多余配置，全部内置"
            "",
            "🎯 我们的目标:",
            "让每一个但丁都解放自己的双手，专心坐牢。",
            "",
            "© 2025 Faust Launcher. 保留所有权利。"
        ]
        
        for info in about_info:
            color = 'white' if not info.startswith('✨') and not info.startswith('🎯') else '#e74c3c'
            weight = 'normal' if not info.startswith('✨') and not info.startswith('🎯') else 'bold'
            
            info_label = tk.Label(content_frame, 
                                text=info,
                                bg='#34495e',
                                fg=color,
                                font=('Microsoft YaHei UI', 10, weight),
                                justify=tk.LEFT if info.startswith('   •') else tk.CENTER)
            info_label.pack(anchor=tk.CENTER if not info.startswith('   •') else tk.W, pady=2)
        
        # 创建底部按钮区域 - 使用深蓝色背景
        buttons_frame = tk.Frame(self.about_frame, bg='#34495e')
        buttons_frame.pack(pady=30)
        
        # 添加按钮
        buttons_data = [
            {"text": "🌐 bilibili", "command": self.open_website, "color": "#22c9e6"},
            {"text": "💌 意见反馈", "command": self.send_feedback, "color": "#9b59b6"}
        ]
        
        for btn_data in buttons_data:
            button = tk.Button(buttons_frame,
                             text=btn_data["text"],
                             command=btn_data["command"],
                             bg=btn_data["color"],
                             fg='white',
                             font=('Microsoft YaHei UI', 10, 'bold'),
                             relief='flat',
                             padx=15,
                             pady=8,
                             cursor='hand2')
            button.pack(side=tk.LEFT, padx=10)
            # 添加悬停效果
            button.bind("<Enter>", lambda e, b=button: b.configure(bg=self.darken_color(b.cget('bg'))))
            button.bind("<Leave>", lambda e, b=button, c=btn_data["color"]: b.configure(bg=c))
    
    def darken_color(self, color, factor=0.8):
        """加深颜色"""
        if color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = max(0, min(255, int(r * factor)))
            g = max(0, min(255, int(g * factor)))
            b = max(0, min(255, int(b * factor)))
            return f'#{r:02x}{g:02x}{b:02x}'
        return color
    
    def on_tab_changed(self, event):
        """处理标签页切换事件"""
        current_tab = self.notebook.select()
        tab_index = self.notebook.index(current_tab)
        tab_names = ["主页", "功能页", "工具页","设置", "关于"]  # 更新标签页名称列表
        # print(f"切换到标签页: {tab_names[tab_index]}")
    
    def update_translation(self):
        """更新汉化"""
        from threading import Thread
        Thread(target=handle_dowload).start()
    
    def show_help(self):
        """显示帮助信息"""
        Popen("README.txt", shell=True)
    
    def open_feature(self, feature):
        """打开指定功能"""
        import webbrowser
        global settings_manager

        if feature['name'] == "📁 游戏目录":
            # 打开settings.json的指定游戏路径
            path = settings_manager.get_setting("game_path")
            if path and os.path.exists(path):
                os.startfile(path)
        elif feature['name'] == "🔄 零协会":
            # 打开零协会的官方网站
            webbrowser.open("https://zeroasso.top")
        elif feature['name'] == "📒 气泡文本":
            # 打开气泡文本的网盘
            webbrowser.open("https://wwyi.lanzoub.com/b014wpn02j")
        elif feature['name'] == "📝 维基":
            # 打开边狱巴士的官方wiki
            webbrowser.open("https://limbuscompany.huijiwiki.com/wiki/%E9%A6%96%E9%A1%B5")
        elif feature['name'] == "📖 N网":
            # 打开N网
            webbrowser.open("https://www.nexusmods.com/limbuscompany/mods")
        elif feature['name'] == "📦 mod管理":
            # 打开mod管理器
            self.open_mod_manager()
    
    def open_website(self):
        """打开作者网站"""
        import webbrowser
        webbrowser.open("https://space.bilibili.com/599331034")
    
    def send_feedback(self):
        """发送反馈"""
        import webbrowser
        webbrowser.open("https://space.bilibili.com/599331034")
    
    def open_mod_manager(self):
        """打开mod管理器"""
        try:
            # 导入mod管理器模块
            sys.path.append('functions')
            from functions.mod_manager import open_mod_manager
            open_mod_manager(self.root)
        except Exception as e:
            print(f"打开mod管理器失败: {e}")
            import tkinter.messagebox as messagebox
            messagebox.showerror("错误", f"打开mod管理器失败: {str(e)}")

    def check_settings(self):
        global config_path, settings_manager

        if not settings_manager.get_setting("game_path"):
            print("错误: 未配置游戏路径")
            # 请求用户选择游戏文件 LimbusCompany.exe
            from tkinter.filedialog import askopenfilename
            file_path = askopenfilename(title="选择边狱巴士主程序", filetypes=[("边狱巴士主程序", "LimbusCompany.exe")])
            if file_path:
                settings_manager.set_setting("game_path", file_path.replace('LimbusCompany.exe', ''))
                settings_manager.save_settings()
                self.settings_page.refresh_all_displays()

            else:
                print("错误: 未选择游戏文件")
                os._exit(-1)

        config_path = settings_manager.get_setting("game_path")

        # 检查是否有命令行参数
        if len(sys.argv) > 1 or not os.path.exists("workshop/LLC_zh-CN"):
            from threading import Thread
            # 有命令行参数，进入命令行模式
            Thread(target=handle_dowload).start()

        self.root.after(1000, self.start_background_rotation)
        
    def folder_link(self):
        # 先要求用户分别选择两个路径，然后根据其生成文件夹超链接指令，然后以管理员身份执行
        import tkinter.messagebox as messagebox
        from tkinter.filedialog import askdirectory
        
        try:
            # 第一步：选择源文件夹（要创建链接的文件夹）
            messagebox.showinfo("选择源文件夹", "请选择要创建链接的源文件夹")
            source_path = askdirectory(title="选择源文件夹")
            if not source_path:
                messagebox.showwarning("取消", "操作已取消")
                return
            
            # 第二步：选择目标文件夹（链接要放置的位置）
            messagebox.showinfo("选择目标位置", "请选择链接要放置的目标文件夹")
            target_path = askdirectory(title="选择目标文件夹")
            if not target_path:
                messagebox.showwarning("取消", "操作已取消")
                return
            
            # 获取目标文件夹的名称（从源路径中提取）
            source_name = os.path.basename(source_path)
            link_path = os.path.join(target_path, source_name)
            
            # 检查目标位置是否已存在同名文件夹
            if os.path.exists(link_path):
                response = messagebox.askyesno("确认覆盖", 
                    f"目标位置已存在同名文件夹 '{source_name}'，是否覆盖？")
                if not response:
                    messagebox.showinfo("取消", "操作已取消")
                    return
            
            # 第三步：生成mklink命令
            # 使用 /J 参数创建目录联接（类似于符号链接）
            mklink_command = f'mklink /J "{link_path}" "{source_path}"'
            
            # 第四步：以管理员身份执行命令
            # 创建批处理文件来执行命令
            batch_content = f'''@echo off
echo 正在创建文件夹链接...
{mklink_command}
if %errorlevel% equ 0 (
    echo 文件夹链接创建成功！
    echo 源文件夹: {source_path}
    echo 链接位置: {link_path}
    pause
) else (
    echo 创建文件夹链接失败，请检查权限或路径是否正确
)
'''
            
            # 保存批处理文件
            batch_file = "create_link.bat"
            with open(batch_file, 'w', encoding='gbk') as f:
                f.write(batch_content)
            
            Popen(f'powershell Start-Process "{batch_file}" -Verb runAs', shell=True)

        except Exception as e:
            messagebox.showerror("错误", f"创建文件夹链接时出错: {str(e)}")

def handle_dowload():
    """命令行模式：执行下载翻译、下载气泡、载入mod并启动游戏"""
    
    global dowloading, root, config_path

    if dowloading:
        return
    dowloading = True

    print("汉化下载中...")
    
    # 导入并执行各个功能模块
    try:
        # 检测 workshop 下是否有 LLC_zh-CN 文件夹
        workshop_path = 'workshop/LLC_zh-CN'
        dowload_path = 'workshop'
        # 1. 下载翻译
        print("开始下载翻译...")
        sys.path.append('functions')
        from functions.zeroasso_dow import main as download_translation
        download_translation(dowload_path) # type: ignore
        print("翻译下载完成")
        
        # 2. 下载气泡
        print("开始下载气泡...")
        from functions.bubble_dow import main as download_bubble
        download_bubble(dowload_path) # type: ignore
        print("气泡下载完成")
        # 把 'workshop\LimbusCompany_Data\Lang\LLC_zh-CN' 复制到游戏目录下的 'workshop' 文件夹 并删除 LimbusCompany_Data 文件夹
        import shutil

        if os.path.exists(dowload_path + '/LimbusCompany_Data/Lang/LLC_zh-CN'): # type: ignore
            shutil.copytree(dowload_path + '/LimbusCompany_Data/Lang/LLC_zh-CN', workshop_path, dirs_exist_ok=True) # type: ignore
            print("文件夹复制完成")
        else:
            print("错误: 未找到 workshop 下的 LLC_zh-CN 文件夹")

        # 删除 LimbusCompany_Data 文件夹
        print("开始删除 LimbusCompany_Data 文件夹...")
        shutil.rmtree(os.path.join(dowload_path, 'LimbusCompany_Data'), ignore_errors=True) # type: ignore
        print("LimbusCompany_Data 文件夹删除完成")

        if not os.path.exists('Font/Context/ChineseFont.ttf'):
            shutil.copytree('Font', 'workshop/LLC_zh-CN', dirs_exist_ok=True) # type: ignore
            print("字体文件复制完成")

        print("汉化下载及处理全部完成！")

        if len(sys.argv) > 1:
            # 关闭窗口
            # root.withdraw()
            pass
        else:
            dowloading = False
            return
        
        run_game()
        
    except Exception as e:
        print(f"执行过程中出错: {e}")
        return
    
    print("启动器模式执行完成，程序退出")
    
    # 关闭窗口
    os._exit(0)

def run_game():
    global config_path, settings_manager
    # 复制 workshop 下的 LLC_zh-CN 文件夹到游戏目录下的 LimbusCompany_Data/Lang 文件夹 下
    import shutil
    print(f"开始复制 workshop 下的 LLC_zh-CN 文件夹到游戏目录下的 {config_path}")
    try:
        shutil.copytree('workshop/LLC_zh-CN', os.path.join(config_path, 'LimbusCompany_Data/Lang/LLC_zh-CN'), dirs_exist_ok=True) # type: ignore
        print("汉化复制完成")
    except Exception as e:
        print(f"效用汉化复制文件夹时出错: {e}")
        return

    # 根据 workshop/changes.json 更新 LimbusCompany_Data/Lang/LLC_zh-CN 里的数据
    print("开始应用自定义汉化修改...")
    try:
        # 检查changes.json文件是否存在
        changes_file = "workshop/changes.json"
        if os.path.exists(changes_file):
            # 加载changes.json
            with open(changes_file, 'r', encoding='utf-8') as f:
                changes_data = json.load(f)
            
            if changes_data:
                print(f"找到 {len(changes_data)} 个文件的修改记录")
                
                # 遍历changes.json中的每个文件修改记录
                for relative_path, file_changes in changes_data.items():
                    # 构建完整的文件路径
                    workshop_file_path = os.path.join("workshop", relative_path)
                    game_file_path = os.path.join(config_path, "LimbusCompany_Data", "Lang", relative_path) # type: ignore
                    
                    # 检查游戏目录中的文件是否存在
                    if os.path.exists(game_file_path):
                        print(f"应用修改到: {relative_path}")
                        
                        # 读取游戏目录中的原始文件
                        with open(game_file_path, 'r', encoding='utf-8') as f:
                            original_data = json.load(f)
                        
                        # 应用修改
                        modified_data = apply_changes_to_data(original_data, file_changes)
                        
                        # 保存修改后的文件
                        with open(game_file_path, 'w', encoding='utf-8') as f:
                            json.dump(modified_data, f, ensure_ascii=False, indent=4)
                        
                        print(f"文件 {relative_path} 修改已应用")
                    else:
                        print(f"警告: 游戏目录中未找到文件 {relative_path}")
            else:
                print("没有自定义汉化修改需要应用")
        else:
            print("没有找到changes.json文件，跳过自定义汉化修改")
    except Exception as e:
        print(f"应用自定义汉化修改时出错: {e}")
    
    # 气泡渐变色处理
    from functions.handle_colorful import main as handle_colorful
    handle_colorful()
    print("气泡渐变色处理完成")

    # 复制字体文件夹到汉化目录下
    print("开始复制字体文件夹到汉化目录下...")
    try:
        shutil.copytree('Font', 'workshop/LLC_zh-CN', dirs_exist_ok=True) # type: ignore
        print("字体文件夹复制完成")
    except Exception as e:
        print(f"复制字体文件夹时出错: {e}")

    from functions.zeroasso_dow import create_config_file
    create_config_file(settings_manager.get_setting('game_path'))

    if settings_manager.get_setting('enable_show_user_name'):
        set_user_name()

    # 载入mod并启动游戏
    print("开始载入mod并启动游戏...")
    from functions.load_mod import main as load_mod_and_launch
    load_mod_and_launch(config_path + '/LimbusCompany.exe') # type: ignore

    os._exit(0)

def set_user_name():
    """设置用户名称到 UserInfo_Friends.json 中"""
    global settings_manager, config_path
    user_name = settings_manager.get_setting('user_name')
    from json import dump, load
    datalist = load(open(f'{config_path}/LimbusCompany_Data/Lang/LLC_zh-CN/UserInfo_Friends.json','r',encoding='utf-8'))
    for data in datalist['dataList']:
        if data['id'] == 'Uid_Copy':
            data['content'] = f'{user_name}'
    dump(datalist, indent=4, fp=open(f'{config_path}/LimbusCompany_Data/Lang/LLC_zh-CN/UserInfo_Friends.json','w',encoding='utf-8'))

# 应用changes.json修改的辅助函数
def apply_changes_to_data(original_data, changes):
    """递归应用修改到数据 - 适配新的修改记录结构（包含id）"""

    print(f"应用用户自定义json修改: {type(original_data)}")

    if isinstance(original_data, dict) and isinstance(changes, dict):
        result = {}
        for key, value in original_data.items():
            if key in changes:
                # 如果changes中有对应的键，应用修改
                if isinstance(value, (dict, list)) and isinstance(changes[key], (dict, list)):
                    result[key] = apply_changes_to_data(value, changes[key])
                else:
                    result[key] = changes[key]
            else:
                result[key] = value
        return result
    elif isinstance(original_data, list) and isinstance(changes, list):
        result = []
        
        # 检查是否是包含id的字典列表的特殊修改记录
        if (len(original_data) > 0 and isinstance(original_data[0], dict) and 
            'id' in original_data[0] and len(changes) > 0 and 
            isinstance(changes[0], dict) and 'id' in changes[0]):
            
            # 对于包含id的字典列表，根据id进行匹配修改
            original_dict = {item['id']: item for item in original_data if 'id' in item}
            
            for change_item in changes:
                if isinstance(change_item, dict) and 'id' in change_item:
                    change_id = change_item['id']
                    
                    if change_id in original_dict:
                        # 找到对应的原始项
                        original_item = original_dict[change_id]
                        
                        if 'action' in change_item:
                            # 处理特殊操作
                            if change_item['action'] == 'deleted':
                                # 删除项，不添加到结果中
                                continue
                            elif change_item['action'] == 'added':
                                # 新增项，直接添加到结果中
                                result.append(change_item.get('changes', change_item))
                                continue
                        
                        # 应用修改
                        if 'changes' in change_item:
                            # 有具体的修改内容
                            modified_item = apply_changes_to_data(original_item, change_item['changes'])
                            result.append(modified_item)
                        else:
                            # 没有具体修改内容，使用原始项
                            result.append(original_item)
                    else:
                        # 新增项（id不在原始数据中）
                        if 'action' in change_item and change_item['action'] == 'added':
                            result.append(change_item.get('changes', change_item))
                        else:
                            # 未知情况，保留原始项
                            result.append(original_dict.get(change_id, change_item))
            
            # 添加未被修改的原始项
            for original_item in original_data:
                if isinstance(original_item, dict) and 'id' in original_item:
                    original_id = original_item['id']
                    if original_id not in [item['id'] for item in changes if isinstance(item, dict) and 'id' in item]:
                        result.append(original_item)
                else:
                    # 对于不包含id的项，直接添加
                    result.append(original_item)
            
            return result
        else:
            # 对于普通的列表，使用原来的逻辑
            for i, item in enumerate(original_data):
                if i < len(changes):
                    if isinstance(item, (dict, list)) and isinstance(changes[i], (dict, list)):
                        result.append(apply_changes_to_data(item, changes[i]))
                    else:
                        result.append(changes[i])
                else:
                    result.append(item)
            return result
    else:
        return original_data

def main():
    """主函数"""
    global root
    
    # 无命令行参数，正常启动GUI模式
    # 创建主窗口
    root = tk.Tk()
    
    # 创建应用程序实例
    app = FaustLauncherApp(root)
    
    # 启动主循环
    root.mainloop()

if __name__ == "__main__":
    main()