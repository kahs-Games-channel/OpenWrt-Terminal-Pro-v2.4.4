import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import paramiko
import threading
import sys
import time
import json
import os
import re
import stat
import socket
from datetime import datetime

# =========================================================
# ЦВЕТОВАЯ СХЕМА
# =========================================================

class Colors:
    BG_DARK = "#0a0a0f"
    BG_PANEL = "#12121a"
    BG_CARD = "#1a1a25"
    BG_INPUT = "#1e1e2e"
    BG_HOVER = "#252535"
    BG_HEADER = "#16162a"
    
    ACCENT_BLUE = "#4fc3f7"
    ACCENT_CYAN = "#00e5ff"
    ACCENT_GREEN = "#69f0ae"
    ACCENT_RED = "#ff5252"
    ACCENT_ORANGE = "#ffab40"
    ACCENT_PURPLE = "#b388ff"
    ACCENT_YELLOW = "#ffd740"
    
    TEXT_PRIMARY = "#e0e0e0"
    TEXT_SECONDARY = "#a0a0b0"
    TEXT_DIM = "#606078"
    
    BORDER = "#2a2a3a"
    
    TERMINAL_BG = "#0a0a12"
    TERMINAL_FG = "#b0ffb0"
    
    STATUS_CONNECTED = "#69f0ae"
    STATUS_DISCONNECTED = "#ff5252"

FOLDER_MARKER = "[D] "
FILE_MARKER = "[F] "
PARENT_MARKER = "[..]"

class RouterTerminal:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Xiaomi AX3000T — Terminal Pro (В РАЗРАБОТКЕ)")
        self.root.geometry("1280x820")
        self.root.configure(bg=Colors.BG_DARK)
        self.root.minsize(1000, 600)
        
        # Центрируем окно на экране с учетом нескольких мониторов
        self.center_window()
        
        # Убираем стандартную панель Windows и кнопки управления
        self.root.overrideredirect(True)
        
        try:
            self.root.iconbitmap("OpenWrt_Terminal_Pro.ico")
        except:
            pass
        
        # Флаг для перемещения окна
        self._drag_start = None
        
        self.client = None
        self.channel = None
        self.sftp = None
        self.connected = False
        self.connecting = False
        self._closing = False
        self.sftp_available = False
        
        self.command_history = []
        self.history_index = -1
        self.macros = self.load_macros()
        self.local_path = os.path.expanduser("~")
        self.remote_path = "/root"
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\-_]|\[[0-?]*[ -/]*[@-~])')
        self.stop_reading = threading.Event()
        
        self.setup_styles()
        self.create_widgets()
        self.bind_shortcuts()
        self.refresh_local()
        self.cmd_entry.focus()
    
    def center_window(self):
        """Центрирует окно на экране с учетом нескольких мониторов"""
        # Получаем размеры окна
        window_width = 1280
        window_height = 820
        
        # Получаем информацию о экране
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Рассчитываем позицию для центрирования
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Устанавливаем позицию окна
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
    def strip_ansi(self, text):
        return self.ansi_escape.sub('', text)
    
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("TNotebook", background=Colors.BG_DARK, borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", 
                       background=Colors.BG_PANEL, 
                       foreground=Colors.TEXT_SECONDARY,
                       padding=[20, 10],
                       font=("Segoe UI", 10),
                       borderwidth=0)
        style.map("TNotebook.Tab",
                 background=[("selected", Colors.BG_CARD)],
                 foreground=[("selected", Colors.ACCENT_CYAN)],
                 expand=[("selected", [1, 1, 1, 0])])
        
        style.configure("TProgressbar",
                       background=Colors.ACCENT_BLUE,
                       troughcolor=Colors.BG_INPUT,
                       borderwidth=0,
                       lightcolor=Colors.ACCENT_BLUE,
                       darkcolor=Colors.ACCENT_BLUE)
    
    def create_widgets(self):
        self.main_container = tk.Frame(self.root, bg=Colors.BG_DARK)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        self.create_header()
        
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        self.terminal_tab = tk.Frame(self.notebook, bg=Colors.BG_DARK)
        self.notebook.add(self.terminal_tab, text="  Терминал  ")
        self.create_terminal_tab()
        
        self.files_tab = tk.Frame(self.notebook, bg=Colors.BG_DARK)
        self.notebook.add(self.files_tab, text="  Файлы  ")
        self.create_files_tab()
        
        self.create_status_bar()
    
    def create_header(self):
        header = tk.Frame(self.main_container, bg=Colors.BG_HEADER, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Левая часть — теперь шире за счёт переноса текста
        left_header = tk.Frame(header, bg=Colors.BG_HEADER)
        left_header.pack(side=tk.LEFT, padx=15, pady=8, fill=tk.X, expand=True)
        
        logo = tk.Canvas(left_header, width=36, height=36, bg=Colors.BG_HEADER, highlightthickness=0)
        logo.pack(side=tk.LEFT, padx=(0, 12))
        logo.create_rectangle(6, 10, 30, 28, fill=Colors.ACCENT_CYAN, outline="", stipple="gray25")
        logo.create_line(12, 6, 12, 12, fill=Colors.ACCENT_CYAN, width=2)
        logo.create_line(18, 6, 18, 12, fill=Colors.ACCENT_CYAN, width=2)
        logo.create_line(24, 6, 24, 12, fill=Colors.ACCENT_CYAN, width=2)
        
        title_frame = tk.Frame(left_header, bg=Colors.BG_HEADER)
        title_frame.pack(side=tk.LEFT)
        
        # Название роутера
        tk.Label(title_frame, text="Xiaomi AX3000T",
                font=("Segoe UI", 14, "bold"),
                bg=Colors.BG_HEADER,
                fg=Colors.TEXT_PRIMARY).pack(anchor="w")
        # Версия — в две строки для надёжности
        tk.Label(title_frame, text="OpenWrt Terminal Pro v2.4.4 by kahsGames",
                font=("Segoe UI", 9),
                bg=Colors.BG_HEADER,
                fg=Colors.ACCENT_CYAN,
                wraplength=250).pack(anchor="w")
        
        # Правая часть с кнопками управления окном
        window_controls = tk.Frame(header, bg=Colors.BG_HEADER)
        window_controls.pack(side=tk.RIGHT, padx=12, pady=8)
        
        # Кнопка свернуть
        self.minimize_btn = tk.Button(window_controls, text="─", width=3, height=1,
                                    bg=Colors.BG_HEADER, fg=Colors.TEXT_DIM,
                                    font=("Segoe UI", 12, "bold"),
                                    relief=tk.FLAT, borderwidth=0,
                                    cursor="hand2",
                                    activebackground=Colors.BG_HOVER,
                                    activeforeground=Colors.TEXT_PRIMARY,
                                    command=self.minimize_window)
        self.minimize_btn.pack(side=tk.LEFT, padx=1)
        
        # Кнопка развернуть
        self.maximize_btn = tk.Button(window_controls, text="□", width=3, height=1,
                                    bg=Colors.BG_HEADER, fg=Colors.TEXT_DIM,
                                    font=("Segoe UI", 10, "bold"),
                                    relief=tk.FLAT, borderwidth=0,
                                    cursor="hand2",
                                    activebackground=Colors.BG_HOVER,
                                    activeforeground=Colors.TEXT_PRIMARY,
                                    command=self.toggle_maximize)
        self.maximize_btn.pack(side=tk.LEFT, padx=1)
        
        # Кнопка закрыть
        self.close_btn = tk.Button(window_controls, text="×", width=3, height=1,
                                 bg=Colors.BG_HEADER, fg=Colors.TEXT_DIM,
                                 font=("Segoe UI", 14, "bold"),
                                 relief=tk.FLAT, borderwidth=0,
                                 cursor="hand2",
                                 activebackground=Colors.ACCENT_RED,
                                 activeforeground=Colors.BG_DARK,
                                 command=self.on_close)
        self.close_btn.pack(side=tk.LEFT, padx=1)
        
        # Фрейм для кнопок приложения
        app_btns_frame = tk.Frame(header, bg=Colors.BG_HEADER)
        app_btns_frame.pack(side=tk.RIGHT, padx=(0, 12), pady=10)
        
        self.connect_btn = self.create_button(app_btns_frame, "Подключиться",
                                             Colors.ACCENT_BLUE, self.show_connect_dialog)
        self.connect_btn.pack(side=tk.LEFT, padx=2)
        
        self.disconnect_btn = self.create_button(app_btns_frame, "Отключиться",
                                                Colors.ACCENT_RED, self.disconnect, state="disabled")
        self.disconnect_btn.pack(side=tk.LEFT, padx=2)
        
        self.install_sftp_btn = self.create_button(app_btns_frame, "SFTP",
                                                  Colors.ACCENT_ORANGE, self.install_sftp_on_router, state="disabled")
        self.install_sftp_btn.pack(side=tk.LEFT, padx=2)
        
        # Добавляем возможность перемещения окна
        header.bind("<Button-1>", self.start_drag)
        header.bind("<B1-Motion>", self.drag_window)
        header.bind("<ButtonRelease-1>", self.stop_drag)
        
        # Логотип для перемещения
        logo.bind("<Button-1>", lambda e: self.start_drag(e))
        logo.bind("<B1-Motion>", self.drag_window)
        logo.bind("<ButtonRelease-1>", self.stop_drag)
        
        title_frame.bind("<Button-1>", lambda e: self.start_drag(e))
        title_frame.bind("<B1-Motion>", self.drag_window)
        title_frame.bind("<ButtonRelease-1>", self.stop_drag)
    
    def create_button(self, parent, text, color, command, state="normal", small=False):
        btn = tk.Button(parent, text=text, command=command,
                       bg=color, fg=Colors.BG_DARK,
                       font=("Segoe UI", 9, "bold") if small else ("Segoe UI", 10, "bold"),
                       relief=tk.FLAT,
                       padx=10 if small else 14, pady=4 if small else 6,
                       cursor="hand2",
                       state=state,
                       activebackground=color, activeforeground=Colors.BG_DARK,
                       disabledforeground=Colors.TEXT_DIM,
                       borderwidth=0)
        
        def on_enter(e):
            if btn['state'] == 'normal':
                btn.configure(bg=self.lighten_color(color))
        def on_leave(e):
            if btn['state'] == 'normal':
                btn.configure(bg=color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn
    
    def lighten_color(self, color):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        r = min(255, r + 40)
        g = min(255, g + 40)
        b = min(255, b + 40)
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def create_terminal_tab(self):
        tab_container = tk.Frame(self.terminal_tab, bg=Colors.BG_DARK)
        tab_container.pack(fill=tk.BOTH, expand=True)
        
        self.create_side_panel(tab_container)
        
        terminal_panel = tk.Frame(tab_container, bg=Colors.BG_DARK)
        terminal_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 8), pady=8)
        
        terminal_card = tk.Frame(terminal_panel, bg=Colors.BG_CARD, bd=1, relief=tk.FLAT)
        terminal_card.pack(fill=tk.BOTH, expand=True)
        
        term_header = tk.Frame(terminal_card, bg=Colors.BG_PANEL, height=35)
        term_header.pack(fill=tk.X)
        term_header.pack_propagate(False)
        
        tk.Label(term_header, text="  Terminal", 
                font=("Segoe UI", 9), bg=Colors.BG_PANEL, fg=Colors.TEXT_SECONDARY).pack(side=tk.LEFT, pady=5)
        
        term_btns = tk.Frame(term_header, bg=Colors.BG_PANEL)
        term_btns.pack(side=tk.RIGHT, padx=5)
        
        self.create_button(term_btns, "Очистить", Colors.BG_HOVER, self.clear_terminal, small=True).pack(side=tk.LEFT, padx=2)
        self.create_button(term_btns, "Сохранить", Colors.BG_HOVER, self.save_log, small=True).pack(side=tk.LEFT, padx=2)
        
        self.terminal = scrolledtext.ScrolledText(
            terminal_card,
            bg=Colors.TERMINAL_BG,
            fg=Colors.TERMINAL_FG,
            font=("Cascadia Code", 10),
            insertbackground=Colors.ACCENT_CYAN,
            relief=tk.FLAT,
            borderwidth=0,
            selectbackground=Colors.ACCENT_BLUE,
            selectforeground=Colors.BG_DARK
        )
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 3))
        
        self.terminal.tag_configure("green", foreground=Colors.ACCENT_GREEN)
        self.terminal.tag_configure("red", foreground=Colors.ACCENT_RED)
        self.terminal.tag_configure("yellow", foreground=Colors.ACCENT_YELLOW)
        self.terminal.tag_configure("cyan", foreground=Colors.ACCENT_CYAN)
        self.terminal.tag_configure("purple", foreground=Colors.ACCENT_PURPLE)
        self.terminal.tag_configure("white", foreground=Colors.TEXT_PRIMARY)
        self.terminal.tag_configure("bold", font=("Cascadia Code", 10, "bold"))
        self.terminal.tag_configure("dim", foreground=Colors.TEXT_DIM)
        
        self.terminal_menu = tk.Menu(self.terminal, tearoff=0, 
                                     bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                                     activebackground=Colors.ACCENT_BLUE,
                                     activeforeground=Colors.BG_DARK)
        self.terminal_menu.add_command(label="Копировать", command=self.copy_selection)
        self.terminal_menu.add_command(label="Вставить", command=self.paste_to_terminal)
        self.terminal_menu.add_separator()
        self.terminal_menu.add_command(label="Очистить", command=self.clear_terminal)
        self.terminal.bind("<Button-3>", self.show_context_menu)
        
        input_frame = tk.Frame(terminal_card, bg=Colors.BG_INPUT, height=45)
        input_frame.pack(fill=tk.X, padx=3, pady=(0, 3))
        input_frame.pack_propagate(False)
        
        prompt_frame = tk.Frame(input_frame, bg="#1a1a2e", width=150)
        prompt_frame.pack(side=tk.LEFT, fill=tk.Y)
        prompt_frame.pack_propagate(False)
        
        self.prompt_label = tk.Label(prompt_frame, text="root@AX3000T:~#",
                                    bg="#1a1a2e", fg=Colors.ACCENT_GREEN,
                                    font=("Cascadia Code", 10, "bold"))
        self.prompt_label.pack(padx=12, pady=10)
        
        tk.Frame(input_frame, bg=Colors.BORDER, width=2).pack(side=tk.LEFT, fill=tk.Y)
        
        self.cmd_entry = tk.Entry(input_frame, bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                                insertbackground=Colors.ACCENT_CYAN, 
                                font=("Cascadia Code", 10),
                                relief=tk.FLAT, borderwidth=0)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        self.cmd_entry.bind("<Return>", self.send_command)
        self.cmd_entry.bind("<Up>", self.history_up)
        self.cmd_entry.bind("<Down>", self.history_down)
        self.cmd_entry.bind("<Tab>", self.autocomplete)
        self.cmd_entry.bind("<Escape>", lambda e: self.cmd_entry.delete(0, tk.END))
        
        ctrl_frame = tk.Frame(input_frame, bg=Colors.BG_INPUT)
        ctrl_frame.pack(side=tk.RIGHT, padx=8)
        
        self.create_button(ctrl_frame, "Enter", Colors.ACCENT_GREEN, self.send_enter, small=True).pack(side=tk.LEFT, padx=2)
        self.create_button(ctrl_frame, "Ctrl+C", Colors.ACCENT_RED, self.send_ctrl_c, small=True).pack(side=tk.LEFT, padx=2)
        
        self.print_colored("\n", "dim")
        self.print_colored("  " + "=" * 60 + "\n", "cyan")
        self.print_colored("    Xiaomi AX3000T — OpenWrt Terminal Pro v2.4.4 by kahsGames\n", "cyan")
        self.print_colored("  " + "=" * 60 + "\n", "cyan")
        self.print_colored("\n", "dim")
        self.print_colored("  ВНИМАНИЕ: Программа находится в разработке\n", "red")
        self.print_colored("  Некоторые функции могут работать некорректно\n\n", "yellow")
        self.print_colored("  Нажмите 'Подключиться' для соединения с роутером\n", "yellow")
        self.print_colored("  Если ошибка 'EOF' — нажмите 'SFTP'\n\n", "yellow")
        self.print_colored("  GitHub: https://github.com/kahs-Games-channel\n", "cyan")
        self.print_colored("  Поддержка: issues на GitHub\n\n", "cyan")
    
    def create_side_panel(self, parent):
        side_panel = tk.Frame(parent, bg=Colors.BG_PANEL, width=220)
        side_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0), pady=8)
        side_panel.pack_propagate(False)
        
        panel_header = tk.Frame(side_panel, bg=Colors.BG_PANEL, height=50)
        panel_header.pack(fill=tk.X)
        panel_header.pack_propagate(False)
        
        tk.Label(panel_header, text="Быстрые команды", 
                font=("Segoe UI", 11, "bold"), 
                bg=Colors.BG_PANEL, 
                fg=Colors.ACCENT_CYAN).pack(pady=15)
        
        cmd_canvas = tk.Canvas(side_panel, bg=Colors.BG_PANEL, highlightthickness=0)
        cmd_scrollbar = tk.Scrollbar(side_panel, orient="vertical", command=cmd_canvas.yview)
        cmd_frame = tk.Frame(cmd_canvas, bg=Colors.BG_PANEL)
        
        cmd_frame.bind("<Configure>", lambda e: cmd_canvas.configure(scrollregion=cmd_canvas.bbox("all")))
        cmd_canvas.create_window((0, 0), window=cmd_frame, anchor="nw")
        cmd_canvas.configure(yscrollcommand=cmd_scrollbar.set)
        
        commands = [
            ("Статус системы", "uptime && free -m && df -h", Colors.ACCENT_BLUE),
            ("Интерфейсы", "ifconfig || ip addr", Colors.ACCENT_CYAN),
            ("WiFi", "iwinfo", Colors.ACCENT_PURPLE),
            ("Фаервол", "iptables -L -n 2>/dev/null || nft list ruleset", Colors.ACCENT_RED),
            ("Процессы", "ps | head -20", Colors.ACCENT_GREEN),
            ("Память", "free -m", Colors.ACCENT_YELLOW),
            ("Network config", "cat /etc/config/network", Colors.ACCENT_BLUE),
            ("Wireless config", "cat /etc/config/wireless", Colors.ACCENT_CYAN),
            ("Network restart", "/etc/init.d/network restart", Colors.ACCENT_RED),
            ("Пакеты", "opkg list-installed | head -20", Colors.ACCENT_GREEN),
            ("Уст. SFTP", "opkg update && opkg install openssh-sftp-server && /etc/init.d/dropbear restart", Colors.ACCENT_ORANGE),
            ("Zapret restart", "/etc/init.d/zapret restart 2>/dev/null", Colors.ACCENT_PURPLE),
        ]
        
        for text, cmd, color in commands:
            self.create_side_button(cmd_frame, text, cmd, color).pack(fill=tk.X, padx=8, pady=2)
        
        cmd_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        cmd_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def on_mousewheel(event):
            cmd_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        cmd_canvas.bind("<Enter>", lambda e: cmd_canvas.bind_all("<MouseWheel>", on_mousewheel))
        cmd_canvas.bind("<Leave>", lambda e: cmd_canvas.unbind_all("<MouseWheel>"))
        
        tk.Frame(side_panel, bg=Colors.BORDER, height=2).pack(fill=tk.X, padx=10, pady=8)
        
        macro_header = tk.Frame(side_panel, bg=Colors.BG_PANEL, height=35)
        macro_header.pack(fill=tk.X)
        macro_header.pack_propagate(False)
        
        tk.Label(macro_header, text="Макросы", 
                font=("Segoe UI", 10, "bold"), 
                bg=Colors.BG_PANEL, 
                fg=Colors.ACCENT_ORANGE).pack(side=tk.LEFT, padx=15)
        
        macro_btns = tk.Frame(macro_header, bg=Colors.BG_PANEL)
        macro_btns.pack(side=tk.RIGHT, padx=8)
        
        self.create_button(macro_btns, "+", Colors.BG_HOVER, self.add_macro, small=True).pack(side=tk.LEFT, padx=2)
        self.create_button(macro_btns, "...", Colors.BG_HOVER, self.import_macros, small=True).pack(side=tk.LEFT, padx=2)
        
        self.macros_frame = tk.Frame(side_panel, bg=Colors.BG_PANEL)
        self.macros_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_macros_list()
    
    def create_side_button(self, parent, text, command, color):
        btn_frame = tk.Frame(parent, bg=Colors.BG_CARD, bd=1, relief=tk.FLAT)
        
        indicator = tk.Frame(btn_frame, bg=color, width=4)
        indicator.pack(side=tk.LEFT, fill=tk.Y)
        
        btn = tk.Button(btn_frame, text=text, 
                       command=lambda c=command: self.insert_command(c),
                       bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                       font=("Segoe UI", 8),
                       relief=tk.FLAT, anchor="w", padx=10, pady=6,
                       cursor="hand2",
                       activebackground=Colors.BG_HOVER,
                       activeforeground=Colors.TEXT_PRIMARY,
                       wraplength=170)
        btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def on_enter(e):
            btn_frame.configure(bg=Colors.BG_HOVER)
            btn.configure(bg=Colors.BG_HOVER)
        def on_leave(e):
            btn_frame.configure(bg=Colors.BG_CARD)
            btn.configure(bg=Colors.BG_CARD)
        
        btn_frame.bind("<Enter>", on_enter)
        btn_frame.bind("<Leave>", on_leave)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
        return btn_frame
    
    def create_files_tab(self):
        tab_container = tk.Frame(self.files_tab, bg=Colors.BG_DARK)
        tab_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # ЛЕВАЯ ПАНЕЛЬ
        left_panel = self.create_file_panel(tab_container, "Локальный компьютер", Colors.ACCENT_BLUE)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        
        self.local_path_var = tk.StringVar(value=self.local_path)
        self.create_file_nav(left_panel, self.local_path_var, self.browse_local,
                           lambda: self.navigate_local(".."), self.refresh_local,
                           lambda path: self.navigate_local(path))
        
        left_list_frame = tk.Frame(left_panel, bg=Colors.BG_CARD)
        left_list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 5))
        
        self.local_listbox = self.create_file_listbox(left_list_frame)
        self.local_listbox.bind("<Double-Button-1>", self._on_local_item_click)
        self.local_listbox.bind("<Return>", self._on_local_item_click)
        
        left_btns = tk.Frame(left_panel, bg=Colors.BG_PANEL)
        left_btns.pack(fill=tk.X, padx=8, pady=(0, 8))
        
        self.create_button(left_btns, "Загрузить ->", Colors.ACCENT_BLUE,
                         self.upload_selected).pack(side=tk.RIGHT, padx=2)
        self.create_button(left_btns, "Удалить", Colors.ACCENT_RED,
                         self.delete_local_files).pack(side=tk.LEFT, padx=2)
        self.create_button(left_btns, "Открыть", Colors.ACCENT_CYAN,
                         self.open_local_item, small=True).pack(side=tk.LEFT, padx=2)
        
        # ЦЕНТРАЛЬНАЯ ПАНЕЛЬ
        center_panel = tk.Frame(tab_container, bg=Colors.BG_DARK, width=60)
        center_panel.pack(side=tk.LEFT, fill=tk.Y)
        center_panel.pack_propagate(False)
        
        tk.Frame(center_panel, bg=Colors.BG_DARK, height=100).pack()
        
        tk.Button(center_panel, text=">", command=self.upload_selected,
                bg=Colors.ACCENT_BLUE, fg=Colors.BG_DARK,
                font=("Segoe UI", 16, "bold"),
                relief=tk.FLAT, width=2, height=2,
                cursor="hand2", borderwidth=0,
                activebackground=Colors.ACCENT_CYAN).pack(pady=5)
        
        tk.Button(center_panel, text="<", command=self.download_selected,
                bg=Colors.ACCENT_GREEN, fg=Colors.BG_DARK,
                font=("Segoe UI", 16, "bold"),
                relief=tk.FLAT, width=2, height=2,
                cursor="hand2", borderwidth=0,
                activebackground="#8cff8c").pack(pady=5)
        
        self.transfer_info = tk.Label(center_panel, text="Выберите\nфайлы",
                                     bg=Colors.BG_DARK, fg=Colors.TEXT_DIM,
                                     font=("Segoe UI", 8), justify=tk.CENTER)
        self.transfer_info.pack(pady=15)
        
        # ПРАВАЯ ПАНЕЛЬ
        right_panel = self.create_file_panel(tab_container, "Xiaomi AX3000T", Colors.ACCENT_ORANGE)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))
        
        self.remote_path_var = tk.StringVar(value=self.remote_path)
        self.create_file_nav(right_panel, self.remote_path_var, None,
                           lambda: self.navigate_remote(".."), self.refresh_remote,
                           lambda path: self.navigate_remote(path),
                           home_cmd=lambda: self.navigate_remote("/root"))
        
        right_list_frame = tk.Frame(right_panel, bg=Colors.BG_CARD)
        right_list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 5))
        
        self.remote_listbox = self.create_file_listbox(right_list_frame)
        self.remote_listbox.bind("<Double-Button-1>", self._on_remote_item_click)
        self.remote_listbox.bind("<Return>", self._on_remote_item_click)
        
        self.remote_status = tk.Label(right_panel, text="",
                                     bg=Colors.BG_PANEL, fg=Colors.TEXT_DIM,
                                     font=("Segoe UI", 8))
        self.remote_status.pack(pady=2)
        
        right_btns = tk.Frame(right_panel, bg=Colors.BG_PANEL)
        right_btns.pack(fill=tk.X, padx=8, pady=(0, 8))
        
        self.create_button(right_btns, "<- Скачать", Colors.ACCENT_GREEN,
                         self.download_selected).pack(side=tk.LEFT, padx=2)
        self.create_button(right_btns, "Папка", Colors.BG_HOVER,
                         self.create_remote_dir).pack(side=tk.LEFT, padx=2)
        self.create_button(right_btns, "Удалить", Colors.ACCENT_RED,
                         self.delete_remote_files).pack(side=tk.RIGHT, padx=2)
        self.create_button(right_btns, "Открыть", Colors.ACCENT_CYAN,
                         self.open_remote_item, small=True).pack(side=tk.RIGHT, padx=2)
        
        progress_frame = tk.Frame(tab_container, bg=Colors.BG_DARK)
        progress_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X)
        
        self.progress_label = tk.Label(progress_frame, text="Готов",
                                      bg=Colors.BG_DARK, fg=Colors.TEXT_DIM,
                                      font=("Segoe UI", 9))
        self.progress_label.pack(pady=3)
    
    def create_file_panel(self, parent, title, accent_color):
        panel = tk.Frame(parent, bg=Colors.BG_PANEL)
        
        header = tk.Frame(panel, bg=Colors.BG_CARD, height=45)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Frame(header, bg=accent_color, width=4).pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(header, text=f"  {title}",
                font=("Segoe UI", 10, "bold"),
                bg=Colors.BG_CARD, fg=accent_color,
                wraplength=300).pack(side=tk.LEFT, pady=10)
        
        return panel
    
    def create_file_nav(self, panel, path_var, browse_cmd, up_cmd, refresh_cmd, enter_cmd, home_cmd=None):
        nav = tk.Frame(panel, bg=Colors.BG_PANEL, height=40)
        nav.pack(fill=tk.X, padx=8, pady=(5, 0))
        nav.pack_propagate(False)
        
        if browse_cmd:
            tk.Button(nav, text="...", command=browse_cmd,
                    bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                    font=("Segoe UI", 9), relief=tk.FLAT, width=3,
                    cursor="hand2", borderwidth=0,
                    activebackground=Colors.BG_HOVER).pack(side=tk.LEFT, padx=1, pady=3)
        
        tk.Button(nav, text="^", command=up_cmd,
                bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                font=("Segoe UI", 9), relief=tk.FLAT, width=3,
                cursor="hand2", borderwidth=0,
                activebackground=Colors.BG_HOVER).pack(side=tk.LEFT, padx=1, pady=3)
        
        entry = tk.Entry(nav, textvariable=path_var,
                       bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                       font=("Consolas", 9), relief=tk.FLAT,
                       borderwidth=0, insertbackground=Colors.ACCENT_CYAN)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=3)
        entry.bind("<Return>", lambda e: enter_cmd(entry.get()))
        
        tk.Button(nav, text="Обновить", command=refresh_cmd,
                bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                font=("Segoe UI", 8), relief=tk.FLAT, width=7,
                cursor="hand2", borderwidth=0,
                activebackground=Colors.BG_HOVER).pack(side=tk.LEFT, padx=1, pady=3)
        
        if home_cmd:
            tk.Button(nav, text="Домой", command=home_cmd,
                    bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                    font=("Segoe UI", 8), relief=tk.FLAT, width=6,
                    cursor="hand2", borderwidth=0,
                    activebackground=Colors.BG_HOVER).pack(side=tk.LEFT, padx=1, pady=3)
    
    def create_file_listbox(self, parent):
        listbox = tk.Listbox(parent, bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                            font=("Consolas", 9), selectbackground=Colors.ACCENT_BLUE,
                            selectforeground=Colors.BG_DARK, selectmode=tk.EXTENDED,
                            relief=tk.FLAT, borderwidth=0, activestyle="none",
                            highlightthickness=0)
        
        scrollbar = tk.Scrollbar(parent, command=listbox.yview, bg=Colors.BG_PANEL,
                                troughcolor=Colors.BG_INPUT, borderwidth=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        return listbox
    
    def create_status_bar(self):
        status_frame = tk.Frame(self.main_container, bg=Colors.BG_HEADER, height=40)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        indicator_frame = tk.Frame(status_frame, bg=Colors.BG_HEADER, width=200)
        indicator_frame.pack(side=tk.LEFT, fill=tk.Y)
        indicator_frame.pack_propagate(False)
        
        self.status_canvas = tk.Canvas(indicator_frame, width=24, height=24,
                                       bg=Colors.BG_HEADER, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(15, 5), pady=8)
        self.status_dot = self.status_canvas.create_oval(4, 4, 20, 20,
                                                         fill=Colors.STATUS_DISCONNECTED,
                                                         outline="")
        
        self.status_label = tk.Label(indicator_frame, text="Отключено",
                                    bg=Colors.BG_HEADER, fg=Colors.STATUS_DISCONNECTED,
                                    font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side=tk.LEFT)
        
        tk.Frame(status_frame, bg=Colors.BORDER, width=2).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.sftp_status_label = tk.Label(status_frame, text="",
                                         bg=Colors.BG_HEADER, fg=Colors.TEXT_DIM,
                                         font=("Segoe UI", 9))
        self.sftp_status_label.pack(side=tk.LEFT, padx=10)
        
        self.conn_info = tk.Label(status_frame, text="",
                                 bg=Colors.BG_HEADER, fg=Colors.TEXT_DIM,
                                 font=("Segoe UI", 9))
        self.conn_info.pack(side=tk.RIGHT, padx=15)
    
    # =========================================================
    # ИСПРАВЛЕННЫЕ МЕТОДЫ ОТКРЫТИЯ ПАПОК    # =========================================================
    
    def _on_local_item_click(self, event=None):
        self._open_selected_item(self.local_listbox, is_remote=False)
    
    def _on_remote_item_click(self, event=None):
        self._open_selected_item(self.remote_listbox, is_remote=True)
    
    def _open_selected_item(self, listbox, is_remote=False):
        sel = listbox.curselection()
        if not sel:
            return
        
        item_text = listbox.get(sel[0])
        
        if item_text == PARENT_MARKER:
            if is_remote:
                self.navigate_remote("..")
            else:
                self.navigate_local("..")
            return
        
        if item_text.startswith(FOLDER_MARKER):
            dir_name = item_text[4:].strip()
            if is_remote:
                new_path = os.path.join(self.remote_path, dir_name).replace("\\", "/")
                self.navigate_remote(new_path)
            else:
                new_path = os.path.join(self.local_path, dir_name)
                self.navigate_local(new_path)
            return
    
    def open_local_item(self):
        self._open_selected_item(self.local_listbox, is_remote=False)
    
    def open_remote_item(self):
        self._open_selected_item(self.remote_listbox, is_remote=True)
    
    # =========================================================
    # ФАЙЛОВЫЕ ОПЕРАЦИИ
    # =========================================================
    
    def refresh_local(self):
        if self._closing: return
        self.local_listbox.delete(0, tk.END)
        self.local_listbox.insert(tk.END, PARENT_MARKER)
        
        try:
            if not os.path.exists(self.local_path):
                self.local_path = os.path.expanduser("~")
            
            items = os.listdir(self.local_path)
            dirs, files = [], []
            
            for item in items:
                full_path = os.path.join(self.local_path, item)
                try:
                    if os.path.isdir(full_path):
                        dirs.append(f"{FOLDER_MARKER}{item}")
                    else:
                        size = os.path.getsize(full_path)
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size/1024:.1f} KB"
                        else:
                            size_str = f"{size/(1024*1024):.1f} MB"
                        files.append(f"{FILE_MARKER}{item}  {size_str}")
                except:
                    continue
            
            for d in sorted(dirs):
                self.local_listbox.insert(tk.END, d)
            for f in sorted(files):
                self.local_listbox.insert(tk.END, f)
            
            self.local_path_var.set(self.local_path)
        except Exception as e:
            self.local_listbox.insert(tk.END, f"Ошибка: {e}")
    
    def refresh_remote(self):
        if self._closing: return
        self.remote_listbox.delete(0, tk.END)
        
        if not self.sftp_available or not self.sftp:
            self.remote_listbox.insert(tk.END, "SFTP не доступен")
            self.remote_listbox.insert(tk.END, "Нажмите 'SFTP' для установки")
            self.remote_status.config(text="SFTP недоступен", fg=Colors.ACCENT_RED)
            return
        
        self.remote_listbox.insert(tk.END, PARENT_MARKER)
        
        try:
            items = self.sftp.listdir_attr(self.remote_path)
            dirs, files = [], []
            
            for item in items:
                if stat.S_ISDIR(item.st_mode):
                    dirs.append(f"{FOLDER_MARKER}{item.filename}")
                else:
                    size = item.st_size
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size/1024:.1f} KB"
                    else:
                        size_str = f"{size/(1024*1024):.1f} MB"
                    files.append(f"{FILE_MARKER}{item.filename}  {size_str}")
            
            for d in sorted(dirs):
                self.remote_listbox.insert(tk.END, d)
            for f in sorted(files):
                self.remote_listbox.insert(tk.END, f)
            
            self.remote_path_var.set(self.remote_path)
            self.remote_status.config(text="SFTP доступен", fg=Colors.ACCENT_GREEN)
        except Exception as e:
            self.remote_listbox.insert(tk.END, f"Ошибка: {e}")
            self.remote_status.config(text="Ошибка SFTP", fg=Colors.ACCENT_YELLOW)
    
    def browse_local(self):
        path = filedialog.askdirectory(title="Выберите папку", initialdir=self.local_path)
        if path and os.path.exists(path):
            self.local_path = os.path.normpath(path)
            self.refresh_local()
    
    def navigate_local(self, path):
        if not path:
            return
        
        path = path.strip()
        
        if path == "..":
            new_path = os.path.dirname(self.local_path)
        elif os.path.isabs(path):
            new_path = path
        else:
            new_path = os.path.join(self.local_path, path)
        
        new_path = os.path.normpath(new_path)
        
        if os.path.exists(new_path) and os.path.isdir(new_path):
            self.local_path = new_path
            self.refresh_local()
        else:
            self.print_colored(f"Папка не существует: {new_path}\n", "red")
    
    def navigate_remote(self, path):
        if not self.sftp_available or self._closing or not path:
            return
        
        path = path.strip()
        
        if path == "..":
            new_path = os.path.dirname(self.remote_path)
        elif path.startswith("/"):
            new_path = path
        else:
            new_path = os.path.join(self.remote_path, path).replace("\\", "/")
        
        new_path = os.path.normpath(new_path).replace("\\", "/")
        while "//" in new_path:
            new_path = new_path.replace("//", "/")
        
        try:
            self.sftp.stat(new_path)
            self.remote_path = new_path
            self.refresh_remote()
        except:
            self.print_colored(f"Папка не существует: {new_path}\n", "red")
    
    def get_selected_local_files(self):
        files = []
        for i in self.local_listbox.curselection():
            text = self.local_listbox.get(i)
            if text.startswith(FOLDER_MARKER) or text == PARENT_MARKER:
                continue
            if text.startswith(FILE_MARKER):
                name = text[len(FILE_MARKER):].strip()
                if "  " in name:
                    name = name[:name.rindex("  ")].strip()
                if name:
                    files.append(name)
        return files
    
    def get_selected_remote_files(self):
        files = []
        for i in self.remote_listbox.curselection():
            text = self.remote_listbox.get(i)
            if text.startswith(FOLDER_MARKER) or text == PARENT_MARKER:
                continue
            if text.startswith(FILE_MARKER):
                name = text[len(FILE_MARKER):].strip()
                if "  " in name:
                    name = name[:name.rindex("  ")].strip()
                if name:
                    files.append(name)
        return files
    
    def upload_selected(self):
        if not self.sftp_available:
            messagebox.showinfo("SFTP не доступен", "Нажмите 'SFTP' для установки SFTP сервера")
            return
        files = self.get_selected_local_files()
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для загрузки")
            return
        self.transfer_info.config(text=f"Вверх {len(files)}")
        threading.Thread(target=self._transfer_files, args=(files, True), daemon=True).start()
    
    def download_selected(self):
        if not self.sftp_available:
            messagebox.showinfo("SFTP не доступен", "Нажмите 'SFTP' для установки SFTP сервера")
            return
        files = self.get_selected_remote_files()
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для скачивания")
            return
        self.transfer_info.config(text=f"Вниз {len(files)}")
        threading.Thread(target=self._transfer_files, args=(files, False), daemon=True).start()
    
    def _transfer_files(self, files, upload=True):
        total = len(files)
        self.progress_bar["maximum"] = total
        self.progress_bar["value"] = 0
        
        for i, filename in enumerate(files):
            if self._closing: return
            direction = "Загрузка" if upload else "Скачивание"
            self.progress_label.config(text=f"{direction} {filename} ({i+1}/{total})")
            
            try:
                if upload:
                    local = os.path.join(self.local_path, filename)
                    remote = os.path.join(self.remote_path, filename).replace("\\", "/")
                    self.sftp.put(local, remote)
                else:
                    remote = os.path.join(self.remote_path, filename).replace("\\", "/")
                    local = os.path.join(self.local_path, filename)
                    self.sftp.get(remote, local)
                self.print_colored(f"OK {filename}\n", "green")
            except Exception as e:
                self.print_colored(f"Ошибка {filename}: {e}\n", "red")
            
            self.progress_bar["value"] = i + 1
        
        self.progress_label.config(text="Готово")
        self.transfer_info.config(text="Выберите\nфайлы")
        self.root.after(0, self.refresh_remote if upload else self.refresh_local)
    
    def delete_local_files(self):
        files = self.get_selected_local_files()
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для удаления")
            return
        if messagebox.askyesno("Подтверждение", f"Удалить {len(files)} файл(ов) с компьютера?"):
            for f in files:
                try:
                    os.remove(os.path.join(self.local_path, f))
                    self.print_colored(f"Удален локальный: {f}\n", "yellow")
                except Exception as e:
                    self.print_colored(f"Ошибка {f}: {e}\n", "red")
            self.refresh_local()
    
    def delete_remote_files(self):
        if not self.sftp_available: return
        files = self.get_selected_remote_files()
        if not files:
            messagebox.showinfo("Информация", "Выберите файлы для удаления")
            return
        if messagebox.askyesno("Подтверждение", f"Удалить {len(files)} файл(ов) с роутера?"):
            for f in files:
                try:
                    self.sftp.remove(os.path.join(self.remote_path, f).replace("\\", "/"))
                    self.print_colored(f"Удален с роутера: {f}\n", "yellow")
                except Exception as e:
                    self.print_colored(f"Ошибка {f}: {e}\n", "red")
            self.refresh_remote()
    
    def create_remote_dir(self):
        if not self.sftp_available:
            messagebox.showinfo("SFTP не доступен", "Нажмите 'SFTP' для установки SFTP сервера")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Создать папку на роутере")
        dialog.geometry("380x160")
        dialog.configure(bg=Colors.BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 160) // 2
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="Создать новую папку", bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN,
                font=("Segoe UI", 12, "bold")).pack(pady=15)
        
        tk.Label(dialog, text=f"В: {self.remote_path}", bg=Colors.BG_CARD, fg=Colors.TEXT_DIM,
                font=("Segoe UI", 9)).pack()
        
        entry = tk.Entry(dialog, bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                        font=("Segoe UI", 11), relief=tk.FLAT, borderwidth=0,
                        insertbackground=Colors.ACCENT_CYAN)
        entry.pack(padx=20, pady=10, fill=tk.X)
        entry.focus()
        
        def create():
            name = entry.get().strip()
            if name:
                try:
                    self.sftp.mkdir(os.path.join(self.remote_path, name).replace("\\", "/"))
                    self.print_colored(f"Создана папка: {name}\n", "green")
                    self.refresh_remote()
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))
        
        btn_frame = tk.Frame(dialog, bg=Colors.BG_CARD)
        btn_frame.pack(pady=10)
        
        self.create_button(btn_frame, "Создать", Colors.ACCENT_GREEN, create).pack(side=tk.LEFT, padx=5)
        self.create_button(btn_frame, "Отмена", Colors.BG_HOVER, dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        entry.bind("<Return>", lambda e: create())
    
    # =========================================================
    # ПОДКЛЮЧЕНИЕ И ТЕРМИНАЛ
    # =========================================================
    
    def bind_shortcuts(self):
        self.root.bind("<Control-l>", lambda e: self.clear_terminal())
        self.root.bind("<Control-c>", lambda e: self.copy_selection())
        self.root.bind("<Control-v>", lambda e: self.paste_to_terminal())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def start_drag(self, event):
        """Начало перемещения окна"""
        self._drag_start = (event.x_root, event.y_root)
    
    def drag_window(self, event):
        """Перемещение окна"""
        if self._drag_start:
            x = self.root.winfo_x() + (event.x_root - self._drag_start[0])
            y = self.root.winfo_y() + (event.y_root - self._drag_start[1])
            self.root.geometry(f"+{x}+{y}")
            self._drag_start = (event.x_root, event.y_root)
    
    def stop_drag(self, event):
        """Остановка перемещения окна"""
        self._drag_start = None
    
    def minimize_window(self):
        """Свернуть окно"""
        self.root.withdraw()
        # Восстанавливаем окно по клику на иконке в трее
        self.root.after(100, lambda: self.root.deiconify())
    
    def toggle_maximize(self):
        """Переключить развернутое состояние окна"""
        if self.root.state() == "zoomed":
            self.root.state("normal")
        else:
            self.root.state("zoomed")
    
    def update_status(self, connected, message=""):
        if self._closing: return
        try:
            self.connected = connected
            if connected:
                self.status_label.config(text="Подключено", fg=Colors.STATUS_CONNECTED)
                self.status_canvas.itemconfig(self.status_dot, fill=Colors.STATUS_CONNECTED)
                self.connect_btn.config(state="disabled")
                self.disconnect_btn.config(state="normal")
                self.install_sftp_btn.config(state="normal")
                if self.sftp_available:
                    self.sftp_status_label.config(text="SFTP доступен", fg=Colors.ACCENT_GREEN)
                else:
                    self.sftp_status_label.config(text="SFTP не доступен", fg=Colors.ACCENT_RED)
                self.root.after(100, self.safe_refresh_remote)
            else:
                self.status_label.config(text="Отключено", fg=Colors.STATUS_DISCONNECTED)
                self.status_canvas.itemconfig(self.status_dot, fill=Colors.STATUS_DISCONNECTED)
                self.connect_btn.config(state="normal")
                self.disconnect_btn.config(state="disabled")
                self.install_sftp_btn.config(state="disabled")
                self.sftp_status_label.config(text="")
            if message: self.conn_info.config(text=message)
        except: pass
        self.connecting = False
    
    def safe_refresh_remote(self):
        if not self._closing:
            try: self.refresh_remote()
            except: pass
    
    def safe_print(self, text, color=None):
        if self._closing: return
        try:
            if color:
                self.terminal.insert(tk.END, text, color)
            else:
                self.terminal.insert(tk.END, self.strip_ansi(text))
            self.terminal.see(tk.END)
            self.root.update_idletasks()
        except: pass
    
    def print(self, text):
        self.safe_print(text)
    
    def print_colored(self, text, color="white"):
        self.safe_print(text, color)
    
    def insert_command(self, cmd):
        if self._closing: return
        try:
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, cmd)
            self.cmd_entry.focus()
        except: pass
    
    def show_context_menu(self, event):
        try: self.terminal_menu.post(event.x_root, event.y_root)
        except: pass
    
    def copy_selection(self, event=None):
        try:
            self.terminal.clipboard_clear()
            self.terminal.clipboard_append(self.terminal.get("sel.first", "sel.last"))
        except: pass
    
    def paste_to_terminal(self, event=None):
        if self._closing: return
        try: self.cmd_entry.insert(tk.INSERT, self.root.clipboard_get())
        except: pass
    
    def send_enter(self, event=None):
        if self._closing or not self.channel: return
        try: self.channel.send("\n"); self.safe_print("\n[ENTER]\n")
        except: pass
    
    def send_ctrl_c(self, event=None):
        if self._closing or not self.channel: return
        try: self.channel.send("\x03"); self.safe_print("\n[Ctrl+C]\n")
        except: pass
    
    def show_connect_dialog(self):
        if self.connecting or self._closing: return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Подключение к роутеру")
        dialog.geometry("440x380")
        dialog.configure(bg=Colors.BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 440) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 380) // 2
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="ПОДКЛЮЧЕНИЕ К AX3000T", bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN,
                font=("Segoe UI", 12, "bold")).pack(pady=15)
        
        fields = [
            ("IP адрес:", "192.168.1.1"),
            ("Порт SSH:", "22"),
            ("Логин:", "root"),
            ("Пароль:", ""),
        ]
        
        entries = {}
        for label_text, default in fields:
            frame = tk.Frame(dialog, bg=Colors.BG_CARD)
            frame.pack(pady=6, padx=40, fill=tk.X)
            
            tk.Label(frame, text=label_text, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                    width=14, anchor="w", font=("Segoe UI", 10)).pack(side=tk.LEFT)
            
            entry = tk.Entry(frame, bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY,
                           font=("Segoe UI", 10), relief=tk.FLAT, borderwidth=0,
                           show="*" if "Пароль" in label_text else "",
                           insertbackground=Colors.ACCENT_CYAN)
            entry.insert(0, default)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
            entries[label_text] = entry
        
        self.dialog_status = tk.Label(dialog, text="", bg=Colors.BG_CARD, fg=Colors.TEXT_DIM,
                                      font=("Segoe UI", 9))
        self.dialog_status.pack(pady=5)
        
        btn_frame = tk.Frame(dialog, bg=Colors.BG_CARD)
        btn_frame.pack(pady=15)
        
        def do_connect():
            if self._closing: return
            params = {}
            for k, v in entries.items():
                key = k.split(" ")[0].rstrip(":")
                params[key] = v.get().strip()
            
            if not params.get('IP'):
                self.dialog_status.config(text="Введите IP адрес!", fg=Colors.ACCENT_RED)
                return
            
            self.dialog_status.config(text="Подключение...", fg=Colors.ACCENT_YELLOW)
            self.connecting = True
            dialog.destroy()
            
            self.print_colored(f"\nПодключение к {params['IP']}...\n", "yellow")
            threading.Thread(target=self.ssh_connect, args=(params,), daemon=True).start()
        
        self.create_button(btn_frame, "Подключиться", Colors.ACCENT_BLUE, do_connect).pack(side=tk.LEFT, padx=5)
        self.create_button(btn_frame, "Отмена", Colors.BG_HOVER, dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        entries[fields[0][0]].focus()
        dialog.bind("<Return>", lambda e: do_connect())
    
    def ssh_connect(self, params):
        try:
            self.print_colored("Установка соединения...\n", "dim")
            
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=params.get('IP', '192.168.1.1'),
                port=int(params.get('Порт', params.get('SSH', 22))),
                username=params.get('Логин', 'root'),
                password=params.get('Пароль', ''),
                timeout=15,
                allow_agent=False,
                look_for_keys=False,
                compress=False,
                disabled_algorithms={'pubkeys': []}
            )
            
            try:
                self.sftp = self.client.open_sftp()
                self.sftp_available = True
                self.print_colored("SFTP доступен\n", "green")
            except:
                self.sftp = None
                self.sftp_available = False
                self.print_colored("SFTP не доступен\n", "yellow")
            
            self.channel = self.client.invoke_shell(width=120, height=40, term='xterm')
            self.channel.settimeout(0.0)
            
            self.root.after(0, self.update_status, True, f"Xiaomi AX3000T - {params.get('IP', '')}")
            self.print_colored("\nПодключение установлено!\n", "green")
            self.print_colored("=" * 50 + "\n\n", "dim")
            
            self.stop_reading.clear()
            threading.Thread(target=self.read_output, daemon=True).start()
            
        except Exception as e:
            self.root.after(0, self.update_status, False)
            self.print_colored(f"\nОшибка подключения: {e}\n", "red")
            self._cleanup_connection()
    
    def install_sftp_on_router(self):
        if not self.channel or self.channel.closed:
            messagebox.showinfo("Установка SFTP",
                "Подключитесь к роутеру, затем нажмите эту кнопку.\n\n"
                "Или выполните вручную:\n"
                "opkg update\n"
                "opkg install openssh-sftp-server\n"
                "/etc/init.d/dropbear restart")
            return
        
        self.print_colored("\nУстановка SFTP...\n", "yellow")
        
        commands = [
            "opkg update",
            "opkg install openssh-sftp-server",
            "/etc/init.d/dropbear restart 2>/dev/null || /etc/init.d/sshd restart 2>/dev/null"
        ]
        
        def install():
            for cmd in commands:
                self.print_colored(f"> {cmd}\n", "white")
                try:
                    self.channel.send(cmd + "\n")
                    time.sleep(3)
                except:
                    break
            self.print_colored("\nГотово! Переподключитесь\n", "green")
        
        threading.Thread(target=install, daemon=True).start()
    
    def _cleanup_connection(self):
        for obj in ['sftp', 'channel', 'client']:
            try:
                if getattr(self, obj):
                    getattr(self, obj).close()
            except: pass
        self.sftp = None
        self.channel = None
        self.client = None
        self.sftp_available = False
    
    def disconnect(self):
        self.stop_reading.set()
        
        for attr_name in ['sftp', 'channel', 'client']:
            try:
                if getattr(self, attr_name):
                    getattr(self, attr_name).close()
            except: pass
            setattr(self, attr_name, None)
        
        self.sftp_available = False
        
        if not self._closing:
            self.update_status(False)
            self.print_colored("\nОтключено от роутера\n", "yellow")
    
    def read_output(self):
        while not self.stop_reading.is_set():
            try:
                if self.channel and not self.channel.closed and self.channel.recv_ready():
                    data = self.strip_ansi(self.channel.recv(4096).decode('utf-8', errors='ignore'))
                    if data.strip():
                        self.root.after(0, self.safe_print, data)
                time.sleep(0.03)
            except:
                break
        
        if not self.stop_reading.is_set() and not self._closing:
            self.root.after(0, self.update_status, False)
            self._cleanup_connection()
    
    def send_command(self, event=None):
        if self._closing or not self.channel or self.channel.closed:
            self.print_colored("Нет подключения!\n", "red")
            return
        
        cmd = self.cmd_entry.get().strip()
        if cmd:
            if not self.command_history or self.command_history[-1] != cmd:
                self.command_history.append(cmd)
            self.history_index = len(self.command_history)
            
            try:
                self.channel.send(cmd + "\n")
            except:
                self.print_colored("Ошибка отправки\n", "red")
            
            self.cmd_entry.delete(0, tk.END)
    
    def history_up(self, event):
        if self._closing: return
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.command_history[self.history_index])
    
    def history_down(self, event):
        if self._closing: return
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.command_history[self.history_index])
        else:
            self.history_index = len(self.command_history)
            self.cmd_entry.delete(0, tk.END)
    
    def autocomplete(self, event):
        cmds = ['ifconfig', 'iptables', 'reboot', 'uptime', 'ps', 'cat', 'ls', 'opkg', 'uci',
                'wifi', 'logread', 'free', 'top', 'df', 'ping', 'netstat', 'passwd', 'clear',
                'iwinfo', 'wget', 'curl', 'ssh', 'killall', 'service', 'dmesg', 'mount']
        current = self.cmd_entry.get().strip()
        if current:
            matches = [c for c in cmds if c.startswith(current)]
            if matches:
                self.cmd_entry.delete(0, tk.END)
                self.cmd_entry.insert(0, matches[0] if len(matches) == 1 else os.path.commonprefix(matches))
    
    def clear_terminal(self):
        if not self._closing:
            try: self.terminal.delete(1.0, tk.END)
            except: pass
    
    def save_log(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.terminal.get(1.0, tk.END))
            self.print_colored(f"Лог сохранен\n", "green")
    
    def load_macros(self):
        try:
            with open("macros_ax3000t.json", "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "WiFi статус": "wifi status",
                "Установить SFTP": "opkg update && opkg install openssh-sftp-server && /etc/init.d/dropbear restart",
                "Перезапуск Zapret": "/etc/init.d/zapret restart",
                "Проверка сети": "ping -c 4 google.com",
            }
    
    def save_macros(self):
        with open("macros_ax3000t.json", "w", encoding='utf-8') as f:
            json.dump(self.macros, f, indent=2, ensure_ascii=False)
    
    def update_macros_list(self):
        for widget in self.macros_frame.winfo_children():
            widget.destroy()
        
        canvas = tk.Canvas(self.macros_frame, bg=Colors.BG_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.macros_frame, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=Colors.BG_PANEL)
        
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        for name, cmd in self.macros.items():
            mf = tk.Frame(sf, bg=Colors.BG_CARD)
            mf.pack(fill=tk.X, pady=2, padx=2)
            
            tk.Button(mf, text=name, command=lambda c=cmd: self.insert_command(c),
                    bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY,
                    font=("Segoe UI", 8), relief=tk.FLAT,
                    anchor="w", padx=8, pady=5, cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            tk.Button(mf, text="X", command=lambda n=name: self.delete_macro(n),
                    bg=Colors.BG_CARD, fg=Colors.ACCENT_RED,
                    font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
                    width=3, cursor="hand2").pack(side=tk.RIGHT, padx=2)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
    
    def add_macro(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить макрос")
        dialog.geometry("450x220")
        dialog.configure(bg=Colors.BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Название:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY).pack(pady=(15,5))
        ne = tk.Entry(dialog, bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY)
        ne.pack(padx=20, fill=tk.X)
        
        tk.Label(dialog, text="Команда:", bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY).pack(pady=(10,5))
        ce = tk.Entry(dialog, bg=Colors.BG_INPUT, fg=Colors.TEXT_PRIMARY)
        ce.pack(padx=20, fill=tk.X)
        
        def save():
            n, c = ne.get().strip(), ce.get().strip()
            if n and c:
                self.macros[n] = c
                self.save_macros()
                self.update_macros_list()
                dialog.destroy()
        
        self.create_button(dialog, "Сохранить", Colors.ACCENT_GREEN, save).pack(pady=15)
        ne.focus()
        dialog.bind("<Return>", lambda e: save())
    
    def delete_macro(self, name):
        if messagebox.askyesno("Удаление", f"Удалить '{name}'?"):
            if name in self.macros:
                del self.macros[name]
                self.save_macros()
                self.update_macros_list()
    
    def import_macros(self):
        fn = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if fn:
            with open(fn, 'r', encoding='utf-8') as f:
                self.macros.update(json.load(f))
            self.save_macros()
            self.update_macros_list()
    
    def on_close(self):
        self._closing = True
        self.stop_reading.set()
        self.disconnect()
        try: self.root.destroy()
        except: pass


if __name__ == "__main__":
    try:
        import paramiko
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
        import paramiko
    
    app = RouterTerminal()
    app.root.mainloop()