# -*- coding: utf-8 -*-
"""
童年游戏厅 · 游戏库编辑器 (Windows)
=====================================
编辑 RetroArch 风格的游戏目录（/sdcard/ChildhoodArcade/）。

功能：
  · 预览        选中即显示封面与完整资料
  · 新增        选 ROM 自动归类平台、自动算 SHA256、自动生成条目
  · 删除        从清单移除，可选连带删除 ROM / 封面
  · 编辑        标题、别名、类型、人数、版本、封面、BIOS 等
  · 批量编辑    多选批量赋值 + 正则查找替换（带预览）
  · 匹配规则    清单条目与磁盘文件对应：精确/忽略大小写/去扩展名/模糊/正则/按哈希
  · BIOS 管理   扫描平台目录里已有的 BIOS，可勾选为新游戏的默认 BIOS

运行：  python 游戏库编辑器.py
需要：  Python 3.8+（只用标准库 tkinter，无需第三方库）
"""
import os, re, sys, io, json, hashlib, shutil, subprocess, tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:                                    # 可选：用于预览 JPEG/BMP 等 Tk 不认识的封面
    from PIL import Image
    HAVE_PIL = True
except Exception:                       # 没装 Pillow 也能用（只是不能预览非 PNG/GIF）
    HAVE_PIL = False

# ---------------------------------------------------------------- 设计令牌
BG        = '#EFEAE0'      # 窗口底色（米黄纸感）
SURFACE   = '#FFFDF8'      # 卡片
SURFACE2  = '#F7F2E8'      # 次级卡片 / 悬停
BORDER    = '#E0D8C8'      # 描边
TEXT      = '#2E2620'      # 主文字
MUTED     = '#8A7C68'      # 次要文字
ACCENT    = '#8E1835'      # 主题红（复古机台）
ACCENT_HV = '#A81C3E'
ACCENT_LT = '#F6E3E6'
GOLD      = '#E8B42C'
GOLD_LT   = '#FBF1D6'
SEL       = '#F2E3C8'

FONT      = ('Microsoft YaHei UI', 10)
FONT_B    = ('Microsoft YaHei UI', 10, 'bold')
FONT_T    = ('Microsoft YaHei UI', 15, 'bold')
FONT_S    = ('Microsoft YaHei UI', 9)

PLATFORMS = ['nes', 'arcade', 'gba', 'md', 'sfc']
PLATFORM_LABEL = {
    'nes': '红白机  NES / FC', 'arcade': '街机  Arcade', 'gba': '掌机  GBA',
    'md': 'MD  Mega Drive', 'sfc': 'SFC  Super Nintendo',
}
EXT_PLATFORM = {'.nes': 'nes', '.zip': 'arcade', '.gba': 'gba', '.md': 'md', '.sfc': 'sfc'}

# 常见街机 BIOS（作为新增时的默认候选）
KNOWN_BIOS = {
    'arcade': ['neogeo.zip', 'pgm.zip', 'decocass.zip', 'tps-x.zip', 'darius.zip',
                'taito-cg.zip', 'egs.zip', 'igs036u.bin'],
    'nes': [], 'gba': [], 'md': [], 'sfc': [],
}

FIELDS = ['id', 'title', 'system', 'path', 'art', 'hash', 'bytes',
          'bios', 'biosHash', 'engineId', 'coreHash', 'nativeEngineId',
          'mapper', 'genre', 'players', 'aliases', 'version', 'group', 'versionCount']


def image_kind(path):
    """看图片文件的真实格式（很多封面是 JPEG 却叫 .png，扩展名会骗人）。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(16)
    except Exception:
        return '读取失败'
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'PNG'
    if head[:3] == b'\xff\xd8\xff':
        return 'JPEG'
    if head[:6] in (b'GIF87a', b'GIF89a'):
        return 'GIF'
    if head[:2] == b'BM':
        return 'BMP'
    if head[:4] == b'RIFF':
        return 'WEBP'
    if head[:5] == b'<?xml' or head[:4] == b'<svg ':
        return 'SVG'
    return '未知格式'


# ---------------------------------------------------------------- 工具函数
def sha256(path):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                b = f.read(262144)
                if not b:
                    break
                h.update(b)
    except OSError:
        return ''
    return h.hexdigest()


def slugify(name):
    s = os.path.splitext(os.path.basename(name))[0].lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'game'


def human(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ''
    if n >= 1048576:
        return '%.1f MB' % (n / 1048576)
    if n >= 1024:
        return '%.1f KB' % (n / 1024)
    return '%d B' % n


class Rounded(tk.Canvas):
    """圆角卡片容器。"""
    def __init__(self, master, bg=BG, radius=12, border=BORDER, **kw):
        super().__init__(master, highlightthickness=0, bd=0, bg=bg, **kw)
        self._bg, self._radius, self._border = bg, radius, border
        self.body = tk.Frame(self, bg=bg)
        self.bind('<Configure>', lambda e: self._paint())

    def _paint(self):
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        r = min(self._radius, w // 2, h // 2)
        c = self
        c.delete('all')
        if r < 2:
            c.create_rectangle(0, 0, w, h, fill=self._bg, outline=self._border)
        else:
            for x, y, s, e in ((0, 0, 90, 90), (w - 2 * r, 0, 0, 90),
                                (0, h - 2 * r, 270, 90), (w - 2 * r, h - 2 * r, 180, 90)):
                c.create_arc(x, y, x + 2 * r, y + 2 * r, start=s, extent=e,
                             style='pieslice', fill=self._bg, outline=self._bg)
            c.create_rectangle(r, 0, w - r, h, fill=self._bg, outline=self._bg)
            c.create_rectangle(0, r, w, h - r, fill=self._bg, outline=self._bg)
            for x, y, s, e in ((0, 0, 90, 90), (w - 2 * r, 0, 0, 90),
                                (0, h - 2 * r, 270, 90), (w - 2 * r, h - 2 * r, 180, 90)):
                c.create_arc(x, y, x + 2 * r, y + 2 * r, start=s, extent=e,
                             style='pieslice', fill=self._bg, outline=self._border)
            c.create_line(r, 0, w - r, 0, fill=self._border)
            c.create_line(r, h, w - r, h, fill=self._border)
            c.create_line(0, r, 0, h - r, fill=self._border)
            c.create_line(w, r, w, h - r, fill=self._border)
        self.body.place(x=0, y=0, relwidth=1, relheight=1)


class FlatButton(tk.Canvas):
    """Win11 风格扁平按钮（可圆角 / 强调色 / 悬停）。"""
    def __init__(self, master, text, command=None, accent=False, width=None, **kw):
        self._bg = ACCENT if accent else SURFACE
        self._fg = '#FFFFFF' if accent else TEXT
        self._hover = ACCENT_HV if accent else SURFACE2
        self._border = None if accent else BORDER
        self._text = text
        self._cmd = command
        self._fixed_width = width
        super().__init__(master, height=34, highlightthickness=0, bd=0,
                         bg=self._bg, cursor='hand2')
        self.bind('<Configure>', lambda e: self._paint())
        self.bind('<Enter>', lambda e: self._set(self._hover))
        self.bind('<Leave>', lambda e: self._set(self._bg))
        self.bind('<Button-1>', lambda e: self._cmd and self._cmd())

    def _set(self, c):
        self._bg = c
        self.configure(bg=c)
        self._paint()

    def _paint(self):
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        self.delete('all')
        r = 7
        if self._border:
            for x, y, s, e in ((0, 0, 90, 90), (w - 2 * r, 0, 0, 90),
                                (0, h - 2 * r, 270, 90), (w - 2 * r, h - 2 * r, 180, 90)):
                self.create_arc(x, y, x + 2 * r, y + 2 * r, start=s, extent=e,
                               style='pieslice', fill=self._bg, outline=self._border)
            self.create_rectangle(r, 0, w - r, h, fill=self._bg, outline=self._bg)
            self.create_rectangle(0, r, w, h - r, fill=self._bg, outline=self._bg)
        else:
            for x, y, s, e in ((0, 0, 90, 90), (w - 2 * r, 0, 0, 90),
                                (0, h - 2 * r, 270, 90), (w - 2 * r, h - 2 * r, 180, 90)):
                self.create_arc(x, y, x + 2 * r, y + 2 * r, start=s, extent=e,
                               style='pieslice', fill=self._bg, outline=self._bg)
            self.create_rectangle(r, 0, w - r, h, fill=self._bg, outline=self._bg)
            self.create_rectangle(0, r, w, h - r, fill=self._bg, outline=self._bg)
        self.create_text(w / 2, h / 2, text=self._text, fill=self._fg, font=FONT)


class App(tk.Tk):
    def __init__(self, start_dir=None):
        super().__init__()
        self.title('童年游戏厅 · 游戏库编辑器')
        self.geometry('1400x860')
        self.minsize(1150, 700)
        self.configure(bg=BG)
        self._start_dir = start_dir

        self.root_dir = None
        self.lib = {}
        self.dirty = False
        self._photo = None

        self._style()
        self._ui()
        self.select_platform(PLATFORMS[0])
        if self._start_dir and os.path.isdir(self._start_dir):
            self.root_dir = self._start_dir
            self.path_lbl.configure(text=self._start_dir)
            self.load_library()
            self.refresh_table()
            self.status('已载入：' + self._start_dir)
        else:
            self.status('就绪 — 点「打开游戏目录」选择 /sdcard/ChildhoodArcade/')

    # -------------------------------------------------- 主题
    def _style(self):
        st = ttk.Style(self)
        try:
            st.theme_use('clam')
        except tk.TclError:
            pass
        st.configure('Treeview', background=SURFACE, fieldbackground=SURFACE,
                     foreground=TEXT, font=FONT, rowheight=34,
                     borderwidth=0, relief='flat')
        st.map('Treeview', background=[('selected', SEL)],
               foreground=[('selected', TEXT)])
        st.configure('TNotebook', background=BG, borderwidth=0)
        st.configure('TCombobox', fieldbackground=SURFACE, background=SURFACE,
                     foreground=TEXT, bordercolor=BORDER, arrowsize=13,
                     selectbackground=SEL, selectforeground=TEXT, padding=4)
        st.map('TCombobox', fieldbackground=[('readonly', SURFACE)],
               bordercolor=[('focus', ACCENT)])
        st.configure('TCheckbutton', background=SURFACE, foreground=TEXT,
                     focuscolor=SURFACE)
        st.configure('TLabel', background=SURFACE, foreground=TEXT, font=FONT)
        st.configure('TEntry', fieldbackground=SURFACE, background=SURFACE,
                     foreground=TEXT, bordercolor=BORDER, insertcolor=TEXT)

    # -------------------------------------------------- 界面
    def _ui(self):
        # 顶部命令栏
        bar = tk.Frame(self, bg=BG, height=62)
        bar.pack(fill='x', side='top')
        tk.Label(bar, text='🎮  童年游戏厅 · 游戏库编辑器', bg=BG, fg=TEXT,
                 font=FONT_T).pack(side='left', padx=(18, 8), pady=14)
        tk.Label(bar, text='RetroArch 风格游戏目录管理', bg=BG, fg=MUTED,
                 font=FONT_S).pack(side='left', pady=(20, 0))
        for text, cmd, acc in [('打开游戏目录', self.cmd_open_dir, True),
                               ('保存全部', self.cmd_save, False),
                               ('新增游戏', self.cmd_add, False),
                               ('批量编辑', self.cmd_batch, False),
                               ('匹配规则', self.cmd_match, False),
                               ('BIOS 管理', self.cmd_bios, False),
                               ('封面体检', self.cmd_check_art, False)]:
            FlatButton(bar, text, cmd, accent=acc).pack(side='right', padx=5, pady=14)
            bar.bind('<Configure>', lambda e: None)

        main = tk.Frame(self, bg=BG)
        main.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # 侧栏
        side = Rounded(main, bg=SURFACE, radius=12)
        side.grid(row=0, column=0, sticky='nsw', padx=(0, 12))
        sb = side.body
        sb.configure(bg=SURFACE)
        tk.Label(sb, text='平台', bg=SURFACE, fg=MUTED, font=FONT_S).pack(anchor='w', padx=16, pady=(16, 6))
        self.platform_btns = {}
        for p in PLATFORMS:
            b = FlatButton(sb, PLATFORM_LABEL[p], lambda pp=p: self.select_platform(pp), width=200)
            b.pack(fill='x', padx=10, pady=2)
            self.platform_btns[p] = b
        tk.Label(sb, text='目录', bg=SURFACE, fg=MUTED, font=FONT_S).pack(anchor='w', padx=16, pady=(18, 4))
        self.path_lbl = tk.Label(sb, text='未打开', bg=SURFACE, fg=MUTED, font=FONT_S,
                                 wraplength=190, justify='left')
        self.path_lbl.pack(anchor='w', padx=16)
        tk.Label(sb, text='匹配状态', bg=SURFACE, fg=MUTED, font=FONT_S).pack(anchor='w', padx=16, pady=(18, 4))
        self.match_lbl = tk.Label(sb, text='—', bg=SURFACE, fg=TEXT, font=FONT_S,
                                  wraplength=190, justify='left')
        self.match_lbl.pack(anchor='w', padx=16)

        # 右侧
        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        top = Rounded(right, bg=SURFACE, radius=12)
        top.grid(row=0, column=0, sticky='nsew')
        tf = top.body
        tf.configure(bg=SURFACE)
        cols = ('title', 'platform', 'file', 'size', 'hash', 'art')
        self.tree = ttk.Treeview(tf, columns=cols, show='headings', selectmode='extended')
        heads = {'title': '标题', 'platform': '平台', 'file': 'ROM 文件',
                 'size': '大小', 'hash': 'SHA-256', 'art': '封面'}
        widths = {'title': 260, 'platform': 90, 'file': 210, 'size': 90, 'hash': 150, 'art': 200}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor='w')
        sb2 = ttk.Scrollbar(tf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb2.set)
        self.tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
        sb2.pack(side='right', fill='y', pady=10, padx=(0, 8))
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.on_select())
        self.count_lbl = tk.Label(tf, text='', bg=SURFACE, fg=MUTED, font=FONT_S)
        self.count_lbl.pack(anchor='w', padx=14, pady=(0, 8))

        # 详情
        det = Rounded(right, bg=SURFACE, radius=12)
        det.grid(row=1, column=0, sticky='ew', pady=(12, 0))
        df = det.body
        df.configure(bg=SURFACE)
        df.columnconfigure(1, weight=1)

        self.img_lbl = tk.Label(df, text='封面预览', bg=SURFACE2, fg=MUTED,
                                font=FONT_S, width=16, height=9, relief='flat',
                                bd=0)
        self.img_lbl.grid(row=0, column=0, rowspan=2, padx=(14, 16), pady=14)

        form = tk.Frame(df, bg=SURFACE)
        form.grid(row=0, column=1, sticky='w')
        self.fields = {}
        labels = [('title', '标题'), ('aliases', '别名'), ('genre', '类型'),
                  ('players', '人数'), ('version', '版本'), ('system', '机种'),
                  ('id', 'ID'), ('path', 'ROM 路径'), ('art', '封面路径'),
                  ('hash', 'SHA-256'), ('bytes', '字节数'), ('bios', 'BIOS')]
        for i, (k, lab) in enumerate(labels):
            r, c = divmod(i, 2)
            tk.Label(form, text=lab, bg=SURFACE, fg=MUTED, font=FONT_S).grid(
                row=r, column=c * 2, sticky='w', padx=(0, 6), pady=3)
            e = ttk.Entry(form, width=32, font=FONT)
            e.grid(row=r, column=c * 2 + 1, sticky='ew', padx=(0, 18), pady=3)
            self.fields[k] = e

        btns = tk.Frame(df, bg=SURFACE)
        btns.grid(row=1, column=1, sticky='w', pady=(8, 14))
        for text, cmd, acc in [('应用到选中项', self.cmd_apply_fields, True),
                               ('打开 ROM 目录', self.cmd_open_rom_dir, False),
                               ('用默认封面', self.cmd_default_art, False),
                               ('删除选中', self.cmd_delete, False)]:
            FlatButton(btns, text, cmd, accent=acc).pack(side='left', padx=(0, 6))

        # 状态栏
        self.status_lbl = tk.Label(self, text='', bg=BG, fg=MUTED, font=FONT_S,
                                   anchor='w', padx=18, pady=6)
        self.status_lbl.pack(fill='x', side='bottom')

    # -------------------------------------------------- 状态
    def status(self, msg):
        self.status_lbl.configure(text=msg)

    def select_platform(self, p):
        self.current = p
        for k, b in self.platform_btns.items():
            b._set(ACCENT if k == p else SURFACE)
            b._fg = '#FFFFFF' if k == p else TEXT
            b._paint()
        self.refresh_table()

    # -------------------------------------------------- 数据
    def load_library(self):
        self.lib = {}
        for p in PLATFORMS:
            f = os.path.join(self.root_dir, p, 'games.json')
            if os.path.isfile(f):
                try:
                    with open(f, 'r', encoding='utf-8') as fh:
                        self.lib[p] = json.load(fh)
                except Exception as ex:
                    messagebox.showerror('读取失败', '%s\n%s' % (f, ex))
                    self.lib[p] = []
            else:
                self.lib[p] = []
        self.dirty = False

    def save_library(self):
        for p, games in self.lib.items():
            d = os.path.join(self.root_dir, p)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'games.json'), 'w', encoding='utf-8') as fh:
                json.dump(games, fh, ensure_ascii=False, indent=2)
        self.dirty = False

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        p = self.current
        for g in self.lib.get(p, []):
            self.tree.insert('', 'end', iid=g.get('id', ''), values=(
                g.get('title', ''), p, g.get('path', ''),
                human(g.get('bytes')), (g.get('hash') or '')[:12], g.get('art', '')))
        self.count_lbl.configure(text='%s · %d 个游戏' % (PLATFORM_LABEL[p], len(self.lib.get(p, []))))

    def selected(self):
        by = {g.get('id'): g for g in self.lib.get(self.current, [])}
        return [by[i] for i in self.tree.selection() if i in by]

    def abs_path(self, g, rel):
        rel = rel or ''
        if os.path.isabs(rel):
            return rel
        return os.path.join(self.root_dir, g.get('_plat') or self.current,
                            rel.replace('/', os.sep))

    def bios_of(self, plat):
        """该平台可用的 BIOS：清单里引用过的 + 目录里没被当 ROM 用过的 zip。"""
        games = self.lib.get(plat, [])
        used_as_rom = {os.path.basename(g.get('path') or '') for g in games}
        found = []
        for g in games:
            b = g.get('bios')
            if b and b not in found:
                found.append(b)
        romdir = os.path.join(self.root_dir, plat, 'roms')
        if os.path.isdir(romdir):
            for f in sorted(os.listdir(romdir)):
                if f in used_as_rom or f in found:
                    continue
                if f.lower().endswith(('.zip', '.bin')):
                    found.append(f)
        for b in KNOWN_BIOS.get(plat, []):
            if b not in found and os.path.isfile(os.path.join(romdir, b)):
                found.append(b)
        return found

    def default_bios(self, plat, filename):
        """按游戏名猜一个默认 BIOS。"""
        if plat != 'arcade':
            return ''
        base = os.path.splitext(os.path.basename(filename or ''))[0].lower()
        pgm_hint = ('kov', 'orlegend', 'ddp', 'ddonpach', 'kov3')
        neo_hint = ('kof', 'mslug', 'samsho', 'aof', 'fatfury', 'garou', 'lastblad',
                    'lastbld', 'svc', 'wh', 'sengoku', 'kof', 'kabukikl', 'doubledr',
                    'wakuwak', 'ragnagrd', 'galaxyfg', 'killbld', 'rotd', 'breakers')
        avail = self.bios_of(plat)
        want = None
        if base.startswith(pgm_hint):
            want = 'pgm.zip'
        elif base.startswith(neo_hint):
            want = 'neogeo.zip'
        if want and want in avail:
            return want
        for b in avail:
            if b.lower() in ('neogeo.zip', 'pgm.zip'):
                return b
        return avail[0] if avail else ''

    # -------------------------------------------------- 操作
    def cmd_open_dir(self):
        d = filedialog.askdirectory(
            title='选择游戏根目录（内含 nes/ arcade/ gba/ md/ sfc/ 子目录）')
        if not d:
            return
        self.root_dir = d
        self.path_lbl.configure(text=d)
        self.load_library()
        self.refresh_table()
        self.status('已载入 %d 个平台' % len(self.lib))

    def cmd_save(self):
        if not self.root_dir:
            return messagebox.showinfo('提示', '请先打开游戏目录')
        self.save_library()
        self.status('已保存 games.json（各平台，格式化）')

    def cmd_preview(self):
        g = self.selected()
        if g:
            self.show_preview(g[0])

    def show_preview(self, g):
        art = self.abs_path(g, g.get('art'))
        if not art or not os.path.isfile(art):
            self.img_lbl.configure(image='', text='(无封面)', bg=SURFACE2)
            return
        ph = self.load_photo(art)
        if ph is None:
            kind = image_kind(art)
            hint = '(无法预览)' if HAVE_PIL else '(缺少 Pillow 无法预览)'
            self.img_lbl.configure(image='', text='%s\n%s' % (hint, kind), bg=SURFACE2)
            return
        self._photo = ph
        self.img_lbl.configure(image=ph, text='', bg=SURFACE2, width=160, height=120)

    def load_photo(self, path):
        """读封面。Tk 只认 PNG/GIF/PPM，其它格式用 Pillow 现场转成 PNG 再交给 Tk。"""
        try:
            ph = tk.PhotoImage(file=path)
            return ph.subsample(max(1, int(ph.width() / 160)))
        except Exception:
            pass
        if not HAVE_PIL:
            return None
        try:
            im = Image.open(path)
            im.load()
            if im.mode not in ('RGB', 'RGBA'):
                im = im.convert('RGBA' if 'A' in im.mode else 'RGB')
            buf = io.BytesIO()
            im.save(buf, format='PNG')
            ph = tk.PhotoImage(data=buf.getvalue())
            return ph.subsample(max(1, int(ph.width() / 160)))
        except Exception:
            return None

    def on_select(self):
        g = self.selected()
        if not g:
            return
        g = g[0]
        g['_plat'] = self.current
        for k, e in self.fields.items():
            e.delete(0, tk.END)
            v = g.get(k, '')
            e.insert(0, '' if v is None else str(v))
        self.show_preview(g)

    def cmd_check_art(self):
        """体检封面：找出真实格式不是 PNG 的文件，可一键就地转成真 PNG。"""
        if not self.root_dir:
            return messagebox.showinfo('提示', '请先打开游戏目录')
        bad = []
        total = 0
        for plat in self.lib:
            cdir = os.path.join(self.root_dir, plat, 'covers')
            if not os.path.isdir(cdir):
                continue
            for name in sorted(os.listdir(cdir)):
                f = os.path.join(cdir, name)
                if not os.path.isfile(f):
                    continue
                total += 1
                k = image_kind(f)
                if k != 'PNG':
                    bad.append((f, k))
        if not bad:
            messagebox.showinfo('封面体检', '共 %d 张封面，全部是标准 PNG，没问题。' % total)
            return
        lines = ['共 %d 张封面，其中 %d 张格式异常：' % (total, len(bad))]
        for f, k in bad[:12]:
            lines.append('  %-30s %s' % (os.path.basename(f), k))
        if len(bad) > 12:
            lines.append('  …… 还有 %d 张' % (len(bad) - 12))
        if HAVE_PIL:
            lines.append('')
            lines.append('是否把这 %d 张就地转换成标准 PNG？（转换后备份到 covers_backup/）' % len(bad))
            if not messagebox.askyesno('封面体检', '\n'.join(lines)):
                return
            bd = os.path.join(self.root_dir, 'covers_backup')
            os.makedirs(bd, exist_ok=True)
            ok = 0
            for f, k in bad:
                try:
                    shutil.copy2(f, os.path.join(bd, os.path.basename(f)))
                    im = Image.open(f)
                    im.load()
                    if im.mode not in ('RGB', 'RGBA'):
                        im = im.convert('RGBA' if 'A' in im.mode else 'RGB')
                    im.save(f, format='PNG')
                    ok += 1
                except Exception as e:
                    print('convert failed', f, e)
            messagebox.showinfo('封面体检', '已转换 %d 张为标准 PNG（原文件已备份到 covers_backup/）' % ok)
        else:
            messagebox.showwarning('封面体检', '\n'.join(lines) + '\n\n（未内置 Pillow，无法自动转换）')

    def cmd_apply_fields(self):
        g = self.selected()
        if not g:
            return
        g = g[0]
        for k, e in self.fields.items():
            v = e.get().strip()
            if k == 'bytes':
                try:
                    v = int(v)
                except ValueError:
                    v = 0
            g[k] = v
        self.dirty = True
        self.refresh_table()
        self.status('已修改条目（记得点「保存全部」）')

    def cmd_open_rom_dir(self):
        g = self.selected()
        if not g:
            return
        p = self.abs_path(g[0], g[0].get('path'))
        if p and os.path.isfile(p):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(p)])
        else:
            messagebox.showinfo('提示', 'ROM 文件不存在:\n' + str(p))

    def cmd_default_art(self):
        g = self.selected()
        if not g:
            return
        g = g[0]
        base = os.path.splitext(os.path.basename(g.get('path') or g.get('id') or ''))[0]
        g['art'] = 'covers/%s.png' % base
        self.fields['art'].delete(0, tk.END)
        self.fields['art'].insert(0, g['art'])
        self.dirty = True

    # -------------------------------------------------- 新增（含 BIOS 选择）
    def cmd_add(self):
        if not self.root_dir:
            return messagebox.showinfo('提示', '请先打开游戏目录')
        files = filedialog.askopenfilenames(
            title='选择要添加的 ROM（可多选）',
            filetypes=[('ROM 文件', '*.nes *.zip *.gba *.md *.sfc'), ('全部文件', '*.*')])
        if not files:
            return
        added, skipped = 0, 0
        for f in files:
            plat = EXT_PLATFORM.get(os.path.splitext(f)[1].lower(), 'nes')
            dlg = AddDialog(self, plat, os.path.basename(f))
            if not dlg.accepted:
                skipped += 1
                continue
            g = self.build_entry(plat, f, dlg.values())
            if g:
                self.lib.setdefault(plat, []).append(g)
                added += 1
        self.dirty = True
        self.refresh_table()
        self.status('新增 %d 个游戏，跳过 %d 个（记得点「保存全部」）' % (added, skipped))

    def build_entry(self, plat, src, vals):
        name = os.path.basename(src)
        base = slugify(name)
        existing = {g.get('id') for g in self.lib.get(plat, [])}
        gid = base
        n = 1
        while gid in existing:
            n += 1
            gid = '%s-%d' % (base, n)
        dest_dir = os.path.join(self.root_dir, plat, 'roms')
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, name)
        try:
            if os.path.abspath(src) != os.path.abspath(dest):
                shutil.copy2(src, dest)
        except Exception as ex:
            messagebox.showerror('复制失败', '%s\n%s' % (name, ex))
            return None
        g = {'id': gid, 'title': vals.get('title') or os.path.splitext(name)[0],
             'path': 'roms/' + name,
             'art': 'covers/%s.png' % os.path.splitext(name)[0],
             'hash': sha256(dest), 'bytes': os.path.getsize(dest)}
        bios = vals.get('bios')
        if bios:
            bp = os.path.join(self.root_dir, plat, 'roms', bios)
            g['bios'] = bios
            if os.path.isfile(bp):
                g['biosHash'] = sha256(bp)
        if plat == 'arcade':
            sysname = vals.get('system') or 'neogeo'
            g['system'] = sysname
            if sysname == 'mame':
                g['nativeEngineId'] = 'mame-native-000000000000'
            else:
                g['engineId'] = 'fbneo-ejs4012-mvp-v1'
                g['coreHash'] = '31345c479c90c97252035c4ed212b5ca58695ad4829e03bfa7f292339a71ab4e'
                g['nativeEngineId'] = 'fbneo-native-5a15ab447444'
        else:
            g['system'] = plat
        for k in ('genre', 'players', 'aliases', 'version'):
            if vals.get(k):
                g[k] = vals[k]
        return g

    # -------------------------------------------------- 删除
    def cmd_delete(self):
        gs = self.selected()
        if not gs:
            return
        if not messagebox.askyesno('确认删除', '从清单中删除选中的 %d 个游戏？' % len(gs)):
            return
        del_files = messagebox.askyesno(
            '同时删除文件？', '是否同时删除对应的 ROM / 封面文件？\n选「否」只删清单条目')
        for g in gs:
            if del_files:
                for rel in (g.get('path'), g.get('art')):
                    if not rel:
                        continue
                    p = self.abs_path(g, rel)
                    try:
                        if os.path.isfile(p):
                            os.remove(p)
                    except OSError:
                        pass
            self.lib[self.current].remove(g)
        self.dirty = True
        self.refresh_table()
        self.status('已删除 %d 个游戏（记得点「保存全部」）' % len(gs))

    # -------------------------------------------------- 批量编辑
    def cmd_batch(self):
        gs = self.selected()
        if not gs:
            return messagebox.showinfo('提示', '请先在表格里多选要修改的游戏')
        if BatchDialog(self, gs).applied:
            self.dirty = True
            self.refresh_table()
            self.status('批量修改完成（记得点「保存全部」）')

    # -------------------------------------------------- 匹配规则
    def cmd_match(self):
        if not self.root_dir:
            return messagebox.showinfo('提示', '请先打开游戏目录')
        MatchDialog(self).run()

    # -------------------------------------------------- BIOS 管理
    def cmd_bios(self):
        if not self.root_dir:
            return messagebox.showinfo('提示', '请先打开游戏目录')
        BiosDialog(self).run()


# ---------------------------------------------------------------- 新增对话框
class AddDialog(tk.Toplevel):
    """新增游戏：可指定 BIOS（默认按机种自动选，也可下拉换）。"""
    def __init__(self, master, plat, filename):
        super().__init__(master)
        self.master = master
        self.plat = plat
        self.filename = filename
        self.accepted = False
        self.values = {}
        self.title('新增游戏 — %s' % PLATFORM_LABEL[plat])
        self.configure(bg=BG)
        self.geometry('560x430')
        self.transient(master)
        self.grab_set()

        card = Rounded(self, bg=SURFACE, radius=12)
        card.pack(fill='both', expand=True, padx=14, pady=14)
        f = card.body
        f.configure(bg=SURFACE)

        tk.Label(f, text='新增到：%s' % PLATFORM_LABEL[plat], bg=SURFACE, fg=TEXT,
                 font=FONT_B).grid(row=0, column=0, columnspan=2, sticky='w', padx=18, pady=(16, 4))
        tk.Label(f, text='文件：%s' % filename, bg=SURFACE, fg=MUTED,
                 font=FONT_S).grid(row=1, column=0, columnspan=2, sticky='w', padx=18)

        form = tk.Frame(f, bg=SURFACE)
        form.grid(row=2, column=0, columnspan=2, sticky='w', padx=18, pady=10)
        rows = [('title', '标题'), ('aliases', '别名'), ('genre', '类型'),
                ('players', '人数'), ('version', '版本')]
        self.inputs = {}
        for i, (k, lab) in enumerate(rows):
            r, c = divmod(i, 2)
            tk.Label(form, text=lab, bg=SURFACE, fg=MUTED, font=FONT_S).grid(
                row=r, column=c * 2, sticky='w', padx=(0, 6), pady=3)
            e = ttk.Entry(form, width=26, font=FONT)
            e.grid(row=r, column=c * 2 + 1, sticky='w', padx=(0, 14), pady=3)
            self.inputs[k] = e
        self.inputs['title'].insert(0, os.path.splitext(filename)[0])

        # BIOS 选择
        tk.Label(f, text='BIOS（街机游戏必选，决定能否正常初始化）', bg=SURFACE, fg=MUTED,
                 font=FONT_S).grid(row=3, column=0, columnspan=2, sticky='w', padx=18, pady=(6, 2))
        bios = master.bios_of(plat)
        self.bios_combo = ttk.Combobox(f, values=(bios if bios else ['（无）']),
                                       state='readonly', font=FONT, width=52)
        self.bios_combo.grid(row=4, column=0, columnspan=2, sticky='ew', padx=18)
        # 默认：按机种挑一个最合适的
        default = master.default_bios(plat, filename)
        if default:
            self.bios_combo.set(default)
        elif bios:
            self.bios_combo.set(bios[0])
        tk.Label(f, text='可用 BIOS：%s' % ('、'.join(bios) if bios else '该平台目录里没有找到 BIOS'),
                 bg=SURFACE, fg=MUTED, font=FONT_S, wraplength=500,
                 justify='left').grid(row=5, column=0, columnspan=2, sticky='w', padx=18, pady=(4, 0))

        if plat == 'arcade':
            tk.Label(f, text='机种', bg=SURFACE, fg=MUTED, font=FONT_S).grid(
                row=6, column=0, sticky='w', padx=18, pady=(10, 0))
            self.sys_combo = ttk.Combobox(f, values=['neogeo', 'cps1', 'cps2', 'konami',
                                                    'pgm', 'sega', 'irem'],
                                         state='readonly', font=FONT, width=18)
            self.sys_combo.set('neogeo')
            self.sys_combo.grid(row=6, column=1, sticky='w', padx=6)

        b = tk.Frame(f, bg=SURFACE)
        b.grid(row=7, column=0, columnspan=2, sticky='ew', padx=18, pady=16)
        FlatButton(b, '取消', self.destroy, width=110).pack(side='right')
        FlatButton(b, '添加', self.ok, accent=True, width=110).pack(side='right', padx=8)

    def ok(self):
        self.values = {k: e.get().strip() for k, e in self.inputs.items()}
        b = self.bios_combo.get().strip()
        self.values['bios'] = '' if b in ('', '（无）') else b
        if hasattr(self, 'sys_combo'):
            self.values['system'] = self.sys_combo.get()
        self.accepted = True
        self.destroy()


# ---------------------------------------------------------------- 批量编辑
class BatchDialog(tk.Toplevel):
    def __init__(self, master, games):
        super().__init__(master)
        self.master = master
        self.games = games
        self.applied = False
        self.title('批量编辑 — %d 个游戏' % len(games))
        self.configure(bg=BG)
        self.geometry('640x470')
        self.transient(master)

        card = Rounded(self, bg=SURFACE, radius=12)
        card.pack(fill='both', expand=True, padx=14, pady=14)
        f = card.body
        f.configure(bg=SURFACE)

        tk.Label(f, text='批量赋值', bg=SURFACE, fg=TEXT, font=FONT_B).pack(
            anchor='w', padx=18, pady=(16, 4))
        g1 = tk.Frame(f, bg=SURFACE)
        g1.pack(fill='x', padx=18)
        tk.Label(g1, text='字段', bg=SURFACE, fg=MUTED, font=FONT_S).pack(side='left')
        self.field = ttk.Combobox(g1, values=['title', 'aliases', 'genre', 'players',
                                              'version', 'system', 'bios', 'art'],
                                  state='readonly', width=16, font=FONT)
        self.field.set('genre')
        self.field.pack(side='left', padx=6)
        tk.Label(g1, text='新值', bg=SURFACE, fg=MUTED, font=FONT_S).pack(side='left', padx=(12, 0))
        self.value = ttk.Entry(g1, width=26, font=FONT)
        self.value.pack(side='left', padx=6)
        tk.Label(g1, text='(留空=不改)', bg=SURFACE, fg=MUTED, font=FONT_S).pack(side='left')

        tk.Label(f, text='正则查找替换', bg=SURFACE, fg=TEXT, font=FONT_B).pack(
            anchor='w', padx=18, pady=(14, 4))
        g2 = tk.Frame(f, bg=SURFACE)
        g2.pack(fill='x', padx=18)
        tk.Label(g2, text='字段', bg=SURFACE, fg=MUTED, font=FONT_S).grid(row=0, column=0, sticky='w')
        self.rfield = ttk.Combobox(g2, values=['title', 'aliases', 'genre', 'version'],
                                   state='readonly', width=16, font=FONT)
        self.rfield.set('title')
        self.rfield.grid(row=0, column=1, sticky='w', padx=6)
        tk.Label(g2, text='查找', bg=SURFACE, fg=MUTED, font=FONT_S).grid(row=0, column=2, sticky='w')
        self.find = ttk.Entry(g2, width=22, font=FONT)
        self.find.grid(row=0, column=3, sticky='w', padx=6)
        tk.Label(g2, text='替换为', bg=SURFACE, fg=MUTED, font=FONT_S).grid(row=1, column=0, sticky='w', pady=4)
        self.repl = ttk.Entry(g2, width=22, font=FONT)
        self.repl.grid(row=1, column=3, sticky='w', padx=6)
        self.use_re = tk.BooleanVar(value=True)
        ttk.Checkbutton(g2, text='使用正则', variable=self.use_re, font=FONT_S).grid(
            row=1, column=1, sticky='w')

        self.preview = tk.Text(f, height=11, font=('Consolas', 9), bg=SURFACE2, fg=TEXT,
                               relief='flat', bd=0, wrap='none')
        self.preview.pack(fill='both', expand=True, padx=18, pady=10)

        b = tk.Frame(f, bg=SURFACE)
        b.pack(fill='x', padx=18, pady=(0, 16))
        FlatButton(b, '预览', self.do_preview, width=100).pack(side='left')
        FlatButton(b, '应用', self.do_apply, accent=True, width=100).pack(side='left', padx=8)
        FlatButton(b, '关闭', self.destroy, width=100).pack(side='right')

    def do_preview(self):
        self.preview.delete('1.0', tk.END)
        f = self.find.get()
        if not f:
            self.preview.insert(tk.END, '（先填「查找」）')
            return
        try:
            pat = re.compile(f) if self.use_re.get() else re.compile(re.escape(f), re.IGNORECASE)
        except re.error as ex:
            self.preview.insert(tk.END, '正则错误: %s' % ex)
            return
        rf = self.rfield.get()
        for g in self.games:
            old = str(g.get(rf, '') or '')
            new = pat.sub(self.repl.get(), old)
            if new != old:
                self.preview.insert(tk.END, '%s\n    %s\n  → %s\n\n' % (g.get('id'), old, new))
        self.preview.insert(tk.END, '（预览结束）')

    def do_apply(self):
        fld = self.field.get()
        val = self.value.get()
        if val:
            for g in self.games:
                g[fld] = val
        f = self.find.get()
        if f:
            try:
                pat = re.compile(f) if self.use_re.get() else re.compile(re.escape(f), re.IGNORECASE)
            except re.error as ex:
                return messagebox.showerror('正则错误', str(ex))
            rf = self.rfield.get()
            for g in self.games:
                g[rf] = pat.sub(self.repl.get(), str(g.get(rf, '') or ''))
        self.applied = True
        self.destroy()


# ---------------------------------------------------------------- 匹配规则
class MatchDialog(tk.Toplevel):
    RULES = [('精确匹配', 'exact'), ('忽略大小写', 'nocase'), ('去扩展名匹配', 'stem'),
             ('模糊包含', 'fuzzy'), ('正则匹配', 'regex'), ('按 SHA-256 校验', 'hash')]

    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title('匹配规则')
        self.configure(bg=BG)
        self.geometry('1160x680')
        self.transient(master)
        self.rows = []

        card = Rounded(self, bg=SURFACE, radius=12)
        card.pack(fill='both', expand=True, padx=14, pady=14)
        f = card.body
        f.configure(bg=SURFACE)

        top = tk.Frame(f, bg=SURFACE)
        top.pack(fill='x', padx=18, pady=(16, 8))
        tk.Label(top, text='规则', bg=SURFACE, fg=MUTED, font=FONT_S).pack(side='left')
        self.rule = ttk.Combobox(top, values=[r[0] for r in self.RULES], state='readonly',
                                 width=16, font=FONT)
        self.rule.set(self.RULES[0][0])
        self.rule.pack(side='left', padx=6)
        tk.Label(top, text='自定义正则', bg=SURFACE, fg=MUTED, font=FONT_S).pack(side='left', padx=(12, 0))
        self.custom = ttk.Entry(top, width=24, font=FONT)
        self.custom.pack(side='left', padx=6)
        for text, cmd, acc in [('扫描匹配', self.do_scan, True),
                               ('应用路径修正', self.do_apply, False),
                               ('补全缺失条目', self.do_add_missing, False)]:
            FlatButton(top, text, cmd, accent=acc).pack(side='left', padx=6)

        cols = ('id', 'title', 'plat', 'status', 'cur', 'found')
        self.tree = ttk.Treeview(f, columns=cols, show='headings')
        heads = {'id': 'ID', 'title': '标题', 'plat': '平台', 'status': '状态',
                 'cur': '清单里的文件', 'found': '实际找到的文件'}
        widths = {'id': 150, 'title': 220, 'plat': 80, 'status': 90, 'cur': 220, 'found': 260}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor='w')
        sb = ttk.Scrollbar(f, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill='both', expand=True, padx=(18, 0), pady=(0, 8))
        sb.pack(fill='y', padx=(0, 18), pady=(0, 8))
        self.status = tk.Label(f, text='', bg=SURFACE, fg=MUTED, font=FONT_S)
        self.status.pack(anchor='w', padx=18, pady=(0, 14))

    def rule_key(self):
        for label, key in self.RULES:
            if self.rule.get() == label:
                return key
        return 'exact'

    def do_scan(self):
        self.tree.delete(*self.tree.get_children())
        key = self.rule_key()
        root = self.master.root_dir
        total = ok = miss = 0
        for plat in PLATFORMS:
            games = self.master.lib.get(plat, [])
            romdir = os.path.join(root, plat, 'roms')
            files = {}
            if os.path.isdir(romdir):
                for f in os.listdir(romdir):
                    files[f.lower()] = f
            for g in games:
                total += 1
                cur = g.get('path') or ''
                curname = os.path.basename(cur)
                found = None
                if key == 'hash':
                    want = g.get('hash')
                    if want and os.path.isdir(romdir):
                        for f in os.listdir(romdir):
                            if sha256(os.path.join(romdir, f)) == want:
                                found = f
                                break
                elif key in ('exact', 'nocase'):
                    found = files.get(curname.lower())
                elif key == 'stem':
                    stem = os.path.splitext(curname)[0].lower()
                    for lk, orig in files.items():
                        if os.path.splitext(lk)[0] == stem:
                            found = orig
                            break
                elif key == 'fuzzy':
                    stem = os.path.splitext(curname)[0].lower()
                    for lk, orig in files.items():
                        if stem and (stem in os.path.splitext(lk)[0].lower()
                                     or os.path.splitext(lk)[0].lower() in stem):
                            found = orig
                            break
                elif key == 'regex':
                    pat = self.custom.get()
                    if pat:
                        try:
                            rx = re.compile(pat, re.IGNORECASE)
                            for lk, orig in files.items():
                                if rx.search(curname) or rx.search(os.path.splitext(curname)[0]):
                                    found = orig
                                    break
                        except re.error:
                            pass
                if found:
                    ok += 1
                    status, rel = '已匹配', 'roms/' + found
                else:
                    miss += 1
                    status, rel = '缺失', cur
                self.tree.insert('', 'end', iid='%s|%s' % (plat, g.get('id')),
                                 values=(g.get('id'), g.get('title'), plat, status, curname, found or ''))
                self.rows.append((plat, g, found))
        self.status.configure(text='共 %d 条：匹配 %d，缺失 %d' % (total, ok, miss))

    def do_apply(self):
        n = 0
        for plat, g, found in self.rows:
            if found:
                newp = 'roms/' + found
                if g.get('path') != newp:
                    g['path'] = newp
                    n += 1
        if n:
            self.master.dirty = True
            self.master.refresh_table()
        self.status.configure(text='已修正 %d 条路径（记得点「保存全部」）' % n)

    def do_add_missing(self):
        root = self.master.root_dir
        added = 0
        for plat, g, found in self.rows:
            if found:
                continue
            romdir = os.path.join(root, plat, 'roms')
            if not os.path.isdir(romdir):
                continue
            used = {x.get('id') for x in self.master.lib.get(plat, [])}
            for f in os.listdir(romdir):
                gid = slugify(f)
                if gid in used:
                    continue
                p = os.path.join(romdir, f)
                ng = {'id': gid, 'title': os.path.splitext(f)[0],
                      'path': 'roms/' + f, 'art': 'covers/%s.png' % os.path.splitext(f)[0],
                      'hash': sha256(p), 'bytes': os.path.getsize(p)}
                if plat == 'arcade':
                    ng['system'] = 'neogeo'
                    ng['bios'] = 'neogeo.zip'
                    ng['nativeEngineId'] = 'fbneo-native-5a15ab447444'
                else:
                    ng['system'] = plat
                self.master.lib.setdefault(plat, []).append(ng)
                added += 1
                break
        if added:
            self.master.dirty = True
            self.master.refresh_table()
        self.status.configure(text='新增 %d 条（记得点「保存全部」）' % added)


# ---------------------------------------------------------------- BIOS 管理
class BiosDialog(tk.Toplevel):
    """列出各平台目录里已有的 BIOS，可查看校验值、复制、删除。"""
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title('BIOS 管理')
        self.configure(bg=BG)
        self.geometry('900x620')
        self.transient(master)

        card = Rounded(self, bg=SURFACE, radius=12)
        card.pack(fill='both', expand=True, padx=14, pady=14)
        f = card.body
        f.configure(bg=SURFACE)

        tk.Label(f, text='平台目录里可用的 BIOS', bg=SURFACE, fg=TEXT, font=FONT_B).pack(
            anchor='w', padx=18, pady=(16, 4))
        tk.Label(f, text='BIOS 放在 <平台>/roms/ 目录，街机内核启动时会自动读取同目录的 BIOS。',
                 bg=SURFACE, fg=MUTED, font=FONT_S).pack(anchor='w', padx=18)

        cols = ('plat', 'name', 'size', 'hash', 'used')
        self.tree = ttk.Treeview(f, columns=cols, show='headings')
        for c, h, w in (('plat', '平台', 110), ('name', 'BIOS 文件', 200),
                        ('size', '大小', 100), ('hash', 'SHA-256', 260), ('used', '被引用', 80)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor='w')
        sb = ttk.Scrollbar(f, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill='both', expand=True, padx=(18, 0), pady=10)
        sb.pack(fill='y', padx=(0, 18), pady=10)

        b = tk.Frame(f, bg=SURFACE)
        b.pack(fill='x', padx=18, pady=(0, 16))
        FlatButton(b, '刷新', self.refresh, width=100).pack(side='left')
        FlatButton(b, '复制 SHA-256', self.copy_hash, width=140).pack(side='left', padx=8)
        FlatButton(b, '用系统默认', self.use_default, width=140).pack(side='left', padx=8)
        FlatButton(b, '关闭', self.destroy, width=100).pack(side='right')
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        root = self.master.root_dir
        for plat in PLATFORMS:
            romdir = os.path.join(root, plat, 'roms')
            if not os.path.isdir(romdir):
                continue
            used = {g.get('bios') for g in self.master.lib.get(plat, []) if g.get('bios')}
            bios = [b for b in self.master.bios_of(plat)
                    if os.path.isfile(os.path.join(romdir, b))]
            for b in bios:
                p = os.path.join(romdir, b)
                self.tree.insert('', 'end', iid=plat + '|' + b, values=(
                    plat, b, human(os.path.getsize(p)), sha256(p)[:24],
                    ('%d 个游戏' % len([g for g in self.master.lib.get(plat, [])
                                         if g.get('bios') == b])) if b in used else '未引用'))

    def copy_hash(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        plat, name = iid.split('|', 1)
        p = os.path.join(self.master.root_dir, plat, 'roms', name)
        h = sha256(p)
        self.clipboard_clear()
        self.clipboard_append(h)
        self.status_hint('SHA-256 已复制：' + h)

    def status_hint(self, msg):
        pass

    def use_default(self):
        sel = self.tree.selection()
        if not sel:
            return
        plat, name = sel[0].split('|', 1)
        n = 0
        for g in self.master.lib.get(plat, []):
            if g.get('system') in (None, 'nes', 'gba', 'md', 'sfc'):
                continue
            if g.get('bios') != name:
                g['bios'] = name
                p = os.path.join(self.master.root_dir, plat, 'roms', name)
                if os.path.isfile(p):
                    g['biosHash'] = sha256(p)
                n += 1
        if n:
            self.master.dirty = True
            self.master.refresh_table()
        messagebox.showinfo('BIOS 管理', '已把 %d 个街机游戏的 BIOS 设为 %s' % (n, name))


def selftest(root_dir):
    """无头自检：检查某个目录里所有封面能不能被预览（命令 --selftest <目录>）。"""
    import tkinter as _tk
    r = _tk.Tk()
    r.withdraw()
    total = 0
    ok = 0
    bad = []
    for plat in ['nes', 'arcade', 'gba', 'md', 'sfc']:
        cdir = os.path.join(root_dir, plat, 'covers')
        if not os.path.isdir(cdir):
            continue
        for name in sorted(os.listdir(cdir)):
            f = os.path.join(cdir, name)
            if not os.path.isfile(f):
                continue
            total += 1
            try:
                ph = _tk.PhotoImage(file=f)
                ok += 1
            except Exception:
                try:
                    im = Image.open(f)
                    im.load()
                    buf = io.BytesIO()
                    im.save(buf, format='PNG')
                    _tk.PhotoImage(data=buf.getvalue())
                    ok += 1
                except Exception as e:
                    bad.append('%s/%s (%s): %s' % (plat, name, image_kind(f), e))
    r.destroy()
    print('Pillow bundled : %s' % HAVE_PIL)
    print('covers scanned : %d' % total)
    print('preview ok     : %d' % ok)
    print('preview failed : %d' % len(bad))
    for b in bad[:40]:
        print('   ' + b)
    return 0 if not bad else 1


if __name__ == '__main__':
    _argv = sys.argv[1:]
    if _argv and _argv[0] == '--selftest':
        sys.exit(selftest(_argv[1] if len(_argv) > 1 else '.'))
    _arg = _argv[0] if _argv else None
    App(_arg).mainloop()
