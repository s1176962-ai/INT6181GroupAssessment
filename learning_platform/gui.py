"""One Tkinter interface for setup, quizzes, notebook and learning history."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .auth import AuthService
from .display import DisplaySettings, window_size
from .editor_ui import EditorPage
from .i18n import Translator
from .models import option_label
from .repositories import ProgressRepository, QuestionRepository
from .services import QuizEngine, image_path, select_questions
from .storage import DataError
from .theme import BACKGROUND, apply_theme
from .user_ui import UserPage

ROOT = Path(__file__).resolve().parent.parent


class Application:
    def __init__(self, root, project_root=ROOT, progress_path=None):
        self.root = root
        self.project_root = Path(project_root)
        self.bank = QuestionRepository(self.project_root / "data" / "questions")
        self.progress = ProgressRepository(
            progress_path or self.project_root / "data" / "progress.json"
        )
        self.guest_progress_path = self.progress.store.path
        self.auth = AuthService(self.guest_progress_path.parent)
        self.tr = Translator(self.guest_progress_path.parent)
        self.display_store = DisplaySettings(self.guest_progress_path.parent)
        self.display_warning = ""
        try:
            self.display = self.display_store.load()
        except DataError as exc:
            self.display = {"size": "auto", "compact": True}
            self.display_warning = str(exc)
        self.compact = self.display["compact"]
        self.signed_in = False
        self.users_page = None
        self.user = None
        self.editor = None
        self.engine = None
        self.images = []
        root.title(self.tr("多学科练习平台 | Quiz Platform"))
        self.apply_window_size()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.style = apply_theme(root, self.compact)
        header = ttk.Frame(root, style="Header.TFrame", padding=(20, 10))
        header.pack(fill="x")
        ttk.Label(header, text="QUIZ STUDIO", style="Header.TLabel").pack(side="left")
        self.account_action = ttk.Button(
            header, text=self.tr("登录"), command=self.logout, style="Header.TButton"
        )
        self.account_action.pack(side="right", padx=(16, 0))
        self.identity = ttk.Label(header, text="", style="HeaderSmall.TLabel")
        self.identity.pack(side="right")
        self.page_width = 1000
        # Every screen scrolls, including long questions, images and histories.
        outer = ttk.Frame(root, style="Page.TFrame")
        outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, highlightthickness=0, background=BACKGROUND)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, padding=16 if self.compact else 28)
        self.window = self.canvas.create_window((24, 24), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self.update_scroll_region)
        self.canvas.bind("<Configure>", self.layout_page)
        root.bind("<MouseWheel>", self.scroll_page)
        self.load_bank()
        self.login_page()

    def update_scroll_region(self, event=None):
        self.canvas.configure(
            scrollregion=(0, 0, self.canvas.winfo_width(), self.body.winfo_reqheight() + 48)
        )

    def layout_page(self, event=None):
        width = max(320, min(self.page_width, self.canvas.winfo_width() - 48))
        self.canvas.itemconfigure(self.window, width=width)
        self.canvas.coords(self.window, max(16, (self.canvas.winfo_width() - width) // 2), 24)

    def scroll_page(self, event):
        # Nested text editors and tables keep their own scroll position.
        if event.widget.winfo_toplevel() != self.root or isinstance(
            event.widget, (tk.Text, ttk.Treeview, ttk.Combobox)
        ):
            return
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def login_page(self, registering=False):
        """A local account owns progress; guest mode preserves the V1 data file."""
        self.engine = None
        self.editor = None
        self.users_page = None
        self.signed_in = False
        self.clear(self.tr("登录") if not registering else self.tr("创建本地账户"))
        self.page_width = 540
        self.layout_page()
        self.label(
            self.tr("每天一点练习，看见自己的进步。\n英语 · 数学 · 科学 | 本地保存 · 离线使用"),
            style="Muted.TLabel",
        )
        card = ttk.Frame(self.body, padding=(0, 16))
        card.pack(fill="x")
        self.login_name = tk.StringVar()
        self.login_password = tk.StringVar()
        self.login_confirm = tk.StringVar()
        fields = [
            (self.tr("用户名"), self.login_name, False),
            (self.tr("密码"), self.login_password, True),
        ]
        if registering:
            fields.append((self.tr("确认密码"), self.login_confirm, True))
        for title, variable, secret in fields:
            ttk.Label(card, text=title, style="Muted.TLabel").pack(anchor="w", pady=(12, 6))
            entry = ttk.Entry(card, textvariable=variable, show="•" if secret else "")
            entry.pack(fill="x")
            if not secret:
                entry.focus_set()
            entry.bind("<Return>", lambda event: self.authenticate(registering))
        if registering:
            ttk.Label(
                card, text=self.tr("用户名 3–32 位；密码 6–16 位。"), style="Muted.TLabel"
            ).pack(anchor="w", pady=(10, 0))
        self.login_error = ttk.Label(card, text="", foreground="#B13E36", wraplength=500)
        self.login_error.pack(anchor="w", pady=8)
        self.login_button = ttk.Button(
            card,
            text=self.tr("注册并进入") if registering else self.tr("登录"),
            style="Accent.TButton",
            command=lambda: self.authenticate(registering),
        )
        self.login_button.pack(fill="x", pady=(4, 8))
        ttk.Button(
            card,
            text=self.tr("已有账户，去登录") if registering else self.tr("没有账户？创建账户"),
            style="Quiet.TButton",
            command=lambda: self.login_page(not registering),
        ).pack(fill="x")
        ttk.Separator(self.body).pack(fill="x", pady=8)
        self.action_group(
            [
                (self.tr("访客进入（保留原有练习记录）"), self.enter_guest),
                (self.tr("设置 / 语言"), self.settings),
            ]
        )
        self.label(
            self.tr("账户保存在本机；只有管理员可以维护题库和管理用户。"), style="Muted.TLabel"
        )
        if self.tr.warning:
            self.label(self.tr.warning)

    def authenticate(self, registering=False):
        try:
            if registering:
                user = self.auth.register(
                    self.login_name.get(), self.login_password.get(), self.login_confirm.get()
                )
            else:
                user = self.auth.login(self.login_name.get(), self.login_password.get())
        except ValueError as exc:
            self.login_error.configure(text=self.tr(str(exc)))
            return
        self.login_password.set("")
        self.login_confirm.set("")
        self.user = user
        self.progress = ProgressRepository(self.auth.progress_path(user))
        self.home()

    def enter_guest(self):
        self.user = None
        self.progress = ProgressRepository(self.guest_progress_path)
        self.home()

    def logout(self):
        self.user = None
        self.progress = ProgressRepository(self.guest_progress_path)
        self.login_page()

    def manage_questions(self):
        if not self.check_admin():
            return
        self.editor = EditorPage(self)
        self.editor.show_list()

    def access_error(self, exc):
        messagebox.showinfo(self.tr("权限提示"), self.tr(str(exc)), parent=self.root)
        try:
            self.user = self.auth.require_session(self.user)
        except ValueError:
            self.logout()
        else:
            self.home()

    def check_admin(self):
        try:
            self.user = self.auth.require_admin(self.user)
            return True
        except ValueError as exc:
            self.access_error(exc)
            return False

    def check_session(self):
        if self.user is None:
            return True
        try:
            self.user = self.auth.require_session(self.user)
            return True
        except ValueError as exc:
            self.access_error(exc)
            return False

    def manage_users(self):
        if self.check_admin():
            self.users_page = UserPage(self)
            self.users_page.show_list()

    def settings(self):
        self.clear(self.tr("设置"))
        self.label(self.tr("界面语言"))
        self.language = tk.StringVar(value=self.tr.language)
        ttk.Radiobutton(
            self.body, text=self.tr("简体中文"), variable=self.language, value="zh"
        ).pack(anchor="w")
        ttk.Radiobutton(self.body, text="English", variable=self.language, value="en").pack(
            anchor="w"
        )
        self.label(self.tr("切换立即生效并记住选择；题库内容保留原文。"))
        self.button(self.tr("保存语言设置"), self.save_language, style="Accent.TButton")
        ttk.Separator(self.body).pack(fill="x", pady=10)
        self.label(self.tr("窗口与布局"), style="Subtitle.TLabel")
        self.label(
            self.tr("调整程序窗口大小，不改变电脑分辨率。自动模式适合笔记本。"),
            style="Muted.TLabel",
        )
        self.window_choices = [self.tr("自动适应屏幕"), "960x640", "1080x720", "1280x800"]
        self.window_choice = tk.StringVar(
            value=self.window_choices[0] if self.display["size"] == "auto" else self.display["size"]
        )
        ttk.Combobox(
            self.body, textvariable=self.window_choice, values=self.window_choices, state="readonly"
        ).pack(anchor="w", pady=4)
        self.compact_choice = tk.BooleanVar(value=self.compact)
        ttk.Checkbutton(
            self.body, text=self.tr("紧凑布局（减少间距与卡片高度）"), variable=self.compact_choice
        ).pack(anchor="w", pady=6)
        self.button(self.tr("应用窗口与布局"), self.save_display, style="Accent.TButton")
        if self.display_warning:
            self.label(self.display_warning)
        self.button(self.tr("返回"), self.home if self.signed_in else self.login_page)

    def apply_window_size(self):
        width, height = window_size(
            self.display["size"], self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        )
        self.root.minsize(min(720, width), min(480, height))
        self.root.geometry(f"{width}x{height}")

    def save_display(self):
        size = (
            "auto"
            if self.window_choice.get() == self.window_choices[0]
            else self.window_choice.get()
        )
        try:
            self.display_store.save(size, self.compact_choice.get())
        except ValueError as exc:
            messagebox.showerror(self.tr("保存失败"), str(exc), parent=self.root)
            return
        self.display = self.display_store.load()
        self.compact = self.display["compact"]
        self.root.state("normal")
        self.apply_window_size()
        apply_theme(self.root, self.compact)
        self.body.configure(padding=16 if self.compact else 28)
        self.settings()

    def save_language(self):
        try:
            self.tr.set_language(self.language.get())
        except ValueError as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.root)
            return
        self.root.title(self.tr("多学科练习平台 | Quiz Platform"))
        self.settings()

    def clear(self, title):
        for widget in self.body.winfo_children():
            widget.destroy()
        self.images = []
        self.page_width = 1000
        self.identity.configure(text=self.user["name"] if self.user else self.tr("访客"))
        self.account_action.configure(
            text=self.tr("退出登录 / 切换账户") if self.user else self.tr("登录")
        )
        self.canvas.yview_moveto(0)
        self.layout_page()
        self.label(title, style="Title.TLabel")

    def label(self, text, style="TLabel"):
        widget = ttk.Label(self.body, text=text, wraplength=800, justify="left", style=style)
        widget.pack(anchor="w", fill="x", pady=4 if self.compact else 7)
        widget.bind(
            "<Configure>", lambda event: widget.configure(wraplength=max(120, event.width - 8))
        )
        return widget

    def button(self, text, command, style="TButton"):
        widget = ttk.Button(self.body, text=text, command=command, style=style)
        widget.pack(anchor="w", pady=4 if self.compact else 7)
        return widget

    def action_group(self, actions):
        frame = ttk.Frame(self.body)
        frame.pack(fill="x", pady=(16, 4))
        buttons = [
            ttk.Button(frame, text=text, command=callback, style="Quiet.TButton")
            for text, callback in actions
        ]

        def reflow(event):
            row = column = used = 0
            for button in buttons:
                width = button.winfo_reqwidth() + 12
                if used and used + width > event.width:
                    row += 1
                    column = used = 0
                button.grid(row=row, column=column, sticky="w", padx=(0, 10), pady=4)
                used += width
                column += 1

        frame.bind("<Configure>", reflow)
        return frame

    def metrics(self, items):
        frame = ttk.Frame(self.body)
        frame.pack(fill="x", pady=(6, 10) if self.compact else (10, 18))
        for index, (title, value) in enumerate(items):
            frame.columnconfigure(index, weight=1, uniform="metrics")
            card = ttk.LabelFrame(frame, padding=8 if self.compact else 16)
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 8))
            ttk.Label(card, text=str(value), style="Metric.TLabel").pack(anchor="w")
            ttk.Label(card, text=title, style="Muted.TLabel", wraplength=150).pack(
                anchor="w", pady=(4, 0)
            )

    def dashboard_tiles(self, actions):
        frame = ttk.Frame(self.body)
        frame.pack(fill="x", pady=8)
        cards = []
        for number, (title, detail, callback) in enumerate(actions, 1):
            card = ttk.LabelFrame(frame, padding=10 if self.compact else 18)
            if not self.compact:
                ttk.Label(card, text=f"{number:02}", style="Muted.TLabel").pack(
                    anchor="w", pady=(0, 10)
                )
            ttk.Button(
                card,
                text=title,
                command=callback,
                style="Accent.TButton" if number == 1 else "TButton",
            ).pack(fill="x")
            description = ttk.Label(card, text=detail, style="Muted.TLabel", wraplength=300)
            if not self.compact:
                description.pack(anchor="w", fill="x", pady=(12, 0))
            description.bind(
                "<Configure>",
                lambda event, widget=description: widget.configure(
                    wraplength=max(150, event.width)
                ),
            )
            cards.append(card)

        def reflow(event):
            columns = 3 if self.compact and event.width >= 850 else (2 if event.width >= 600 else 1)
            for column in range(3):
                frame.columnconfigure(
                    column,
                    weight=1 if column < columns else 0,
                    uniform="cards" if column < columns else "",
                )
            for index, card in enumerate(cards):
                card.grid(
                    row=index // columns,
                    column=index % columns,
                    sticky="nsew",
                    padx=(0, 10 if index % columns < columns - 1 else 0),
                    pady=(0, 12),
                )

        frame.bind("<Configure>", reflow)

    def load_bank(self):
        self.questions = self.bank.all()
        self.by_id = {q.id: q for q in self.questions}

    def home(self):
        if not self.check_session():
            return
        self.signed_in = True
        self.users_page = None
        self.editor = None
        self.engine = None
        self.load_bank()
        self.clear(self.tr("你好，{0}。", self.user["name"] if self.user else self.tr("访客")))
        self.label(self.tr("选择一个方向，开始今天的学习。"), style="Muted.TLabel")
        try:
            progress = self.progress.load()
        except DataError as exc:
            self.label(self.tr(str(exc)))
            progress = {"wrong": {}, "history": []}
        self.metrics(
            [
                (self.tr("可练习题目"), len(self.questions)),
                (self.tr("已完成练习"), len(progress["history"])),
                (self.tr("待复习错题"), len(progress["wrong"])),
            ]
        )
        actions = [
            (self.tr("开始练习"), self.tr("选择学科与难度，专注完成一轮练习。"), self.configure),
            (
                self.tr("错题本与复习"),
                self.tr("回顾错题与解析，巩固还不熟悉的知识。"),
                self.notebook,
            ),
            (
                self.tr("学习统计与历史"),
                self.tr("查看每次成绩，记录自己的学习进步。"),
                self.history,
            ),
            (self.tr("设置 / 语言"), self.tr("选择适合自己的界面语言。"), self.settings),
        ]
        if self.user and self.user["role"] == "admin":
            actions.extend(
                [
                    (
                        self.tr("题库管理 / 上传图片"),
                        self.tr("整理题目、选项与图片，维护共享题库。"),
                        self.manage_questions,
                    ),
                    (
                        self.tr("用户管理"),
                        self.tr("管理账户权限，查看学习记录。"),
                        self.manage_users,
                    ),
                ]
            )
        self.dashboard_tiles(actions)
        self.action_group(
            [
                (self.tr("重新加载题库"), self.home),
                (self.tr("退出登录 / 切换账户"), self.logout),
                (self.tr("退出"), self.close),
            ]
        )
        if self.bank.warnings:
            self.label(
                self.tr("题库提示（其他有效题目仍可使用）：\n") + "\n".join(self.bank.warnings)
            )

    def configure(self):
        if not self.check_session():
            return
        self.clear(self.tr("配置练习"))
        if not self.questions:
            self.label(
                self.tr("题库为空，请添加或修复 data/questions 中的 JSON 文件，然后重新加载。")
            )
            self.button(self.tr("返回首页"), self.home)
            return
        subjects = sorted({q.subject for q in self.questions})
        self.subject = tk.StringVar(value=subjects[0])
        self.topic = tk.StringVar(value=self.tr("全部"))
        self.difficulty = tk.StringVar(value=self.tr("全部"))
        self.count = tk.StringVar(value="5")
        self.label(self.tr("学科"))
        subject_box = ttk.Combobox(
            self.body, textvariable=self.subject, values=subjects, state="readonly"
        )
        subject_box.pack(anchor="w")
        self.label(self.tr("主题"))
        self.topic_box = ttk.Combobox(self.body, textvariable=self.topic, state="readonly")
        self.topic_box.pack(anchor="w")
        self.label(self.tr("难度"))
        self.difficulty_box = ttk.Combobox(
            self.body, textvariable=self.difficulty, state="readonly"
        )
        self.difficulty_box.pack(anchor="w")
        self.label(self.tr("题目数量（不足时使用所有匹配题目；顺序随机）"))
        ttk.Entry(self.body, textvariable=self.count, width=12).pack(anchor="w")
        self.available = self.label("")
        subject_box.bind("<<ComboboxSelected>>", self.refresh_filters)
        self.topic_box.bind("<<ComboboxSelected>>", self.refresh_difficulties)
        self.difficulty_box.bind("<<ComboboxSelected>>", self.show_count)
        self.refresh_filters()
        self.button(self.tr("开始"), self.start_configured, style="Accent.TButton")
        self.button(self.tr("返回首页"), self.home)

    def refresh_filters(self, event=None):
        subset = [q for q in self.questions if q.subject == self.subject.get()]
        self.topic_box["values"] = [self.tr("全部")] + sorted({q.topic for q in subset})
        self.topic.set(self.tr("全部"))
        self.refresh_difficulties()

    def refresh_difficulties(self, event=None):
        subset = [
            q
            for q in self.questions
            if q.subject == self.subject.get()
            and (self.topic.get() == self.tr("全部") or q.topic == self.topic.get())
        ]
        self.difficulty_box["values"] = [self.tr("全部")] + sorted({q.difficulty for q in subset})
        self.difficulty.set(self.tr("全部"))
        self.show_count()

    def show_count(self, event=None):
        count = sum(
            q.subject == self.subject.get()
            and (self.topic.get() == self.tr("全部") or q.topic == self.topic.get())
            and (self.difficulty.get() == self.tr("全部") or q.difficulty == self.difficulty.get())
            for q in self.questions
        )
        self.available.configure(text=self.tr("当前匹配：{0} 道题", count))

    def start_configured(self):
        try:
            count = int(self.count.get())
            questions = select_questions(
                self.questions,
                self.subject.get(),
                None if self.topic.get() == self.tr("全部") else self.topic.get(),
                None if self.difficulty.get() == self.tr("全部") else self.difficulty.get(),
                count,
            )
            self.start_quiz(questions)
        except ValueError as exc:
            messagebox.showerror(
                self.tr("无法开始练习"),
                self.tr("请输入正整数题数并检查筛选条件。\n{0}", exc),
                parent=self.root,
            )

    def start_quiz(self, questions, review=False):
        if not self.check_session():
            return
        try:
            self.progress.load()
            self.engine = QuizEngine(questions, self.progress, review)
        except ValueError as exc:
            messagebox.showerror(self.tr("无法开始练习"), self.tr(str(exc)), parent=self.root)
            return
        self.show_question()

    def show_image(self, value):
        if not value:
            return
        try:
            path = image_path(self.project_root, value)
            photo = tk.PhotoImage(master=self.root, file=str(path))
            scale = max(1, (photo.width() + 479) // 480, (photo.height() + 219) // 220)
            if scale > 1:
                photo = photo.subsample(scale)
            self.images.append(photo)
            ttk.Label(self.body, image=photo).pack(anchor="w", pady=5)
        except (tk.TclError, OSError, ValueError) as exc:
            self.label(self.tr("图片无法显示：{0}\n{1}", value, exc))

    def question_content(self, q, selectable=False):
        self.label(f"{q.subject} / {q.topic} / {q.difficulty}  ·  {q.id}", style="Muted.TLabel")
        self.label(q.question, style="Subtitle.TLabel")
        self.show_image(q.question_image)
        self.option_buttons = []
        for index, option in enumerate(q.options):
            if selectable:
                widget = ttk.Radiobutton(
                    self.body,
                    text=f"{option_label(index)}: {option}",
                    variable=self.answer,
                    value=option,
                    style="Option.TRadiobutton",
                )
                widget.pack(fill="x", pady=5)
                self.option_buttons.append(widget)
            else:
                self.label(f"{option_label(index)}: {option}")
            if q.option_images:
                self.show_image(q.option_images[index])

    def show_question(self):
        engine = self.engine
        mode = self.tr("错题复习") if engine.review else self.tr("练习")
        self.clear(self.tr("{0} · 第 {1} / {2} 题", mode, engine.index + 1, len(engine.questions)))
        ttk.Progressbar(self.body, maximum=len(engine.questions), value=engine.index + 1).pack(
            fill="x", pady=(0, 22)
        )
        self.answer = tk.StringVar(value="")
        self.question_content(engine.current, selectable=True)
        self.submit_button = self.button(self.tr("提交答案"), self.submit, style="Accent.TButton")
        self.feedback = self.label("")
        self.next_button = self.button(
            self.tr("查看结果") if engine.index == len(engine.questions) - 1 else self.tr("下一题"),
            self.advance,
        )
        self.next_button.state(["disabled"])
        self.button(self.tr("结束练习并返回"), self.leave_quiz)

    def submit(self):
        if not self.check_session():
            return
        try:
            correct = self.engine.submit(self.answer.get())
        except ValueError as exc:
            messagebox.showerror(self.tr("提交失败"), self.tr(str(exc)), parent=self.root)
            return
        self.submit_button.state(["disabled"])
        for widget in self.option_buttons:
            widget.state(["disabled"])
        q = self.engine.current
        self.feedback.configure(
            style="Success.TLabel" if correct else "Warning.TLabel",
            text=self.tr(
                "{0}\n正确答案：{1}\n解析：{2}",
                self.tr("回答正确！") if correct else self.tr("回答错误，已记入错题本。"),
                q.answer,
                q.explanation,
            ),
        )
        self.next_button.state(["!disabled"])

    def advance(self):
        if self.engine.complete:
            self.results()
        else:
            self.engine.next_question()
            self.show_question()

    def results(self):
        result = self.engine.result()
        self.clear(self.tr("练习完成"))
        self.metrics(
            [
                (self.tr("得分"), f"{result['score']}/{result['max_score']}"),
                (self.tr("正确率"), f"{result['accuracy']:.0f}%"),
                (self.tr("题目数量"), result["total"]),
            ]
        )
        self.label(
            self.tr(
                "总题数：{0}\n正确：{1}\n错误：{2}\n正确率：{3}%\n总分：{4} / {5}",
                result["total"],
                result["correct"],
                result["incorrect"],
                f"{result['accuracy']:.2f}",
                result["score"],
                result["max_score"],
            )
        )
        self.label(self.tr("成绩已保存。每题 1 分，错题复习答对后从错题本移除。"))
        self.engine = None
        self.button(self.tr("返回首页"), self.home)
        self.button(self.tr("查看错题本"), self.notebook)
        self.button(self.tr("查看学习历史"), self.history)

    def leave_quiz(self):
        if self.can_leave():
            self.home()

    def can_leave(self):
        if self.users_page and not self.users_page.can_leave():
            return False
        if self.editor and not self.editor.can_leave():
            return False
        if self.engine and not self.engine.complete:
            return messagebox.askyesno(
                self.tr("结束练习？"),
                self.tr("已提交的错题记录会保留；未完成的练习不会计入成绩历史。"),
                parent=self.root,
            )
        return True

    def close(self):
        if self.can_leave():
            self.root.destroy()

    def notebook(self):
        if not self.check_session():
            return
        self.clear(self.tr("错题本"))
        self.button(self.tr("返回首页"), self.home)
        try:
            wrong = self.progress.load()["wrong"]
        except DataError as exc:
            self.label(self.tr(str(exc)))
            return
        if not wrong:
            self.label(self.tr("还没有错题。开始一次练习吧！"))
            return
        available = [self.by_id[key] for key in wrong if key in self.by_id]
        self.label(self.tr("复习规则：复习答对后移除；普通练习答对不会移除。重复答错累计次数。"))
        if available:
            self.button(
                self.tr("复习全部可用错题（{0} 道）", len(available)),
                lambda: self.start_quiz(available, True),
            )
        for key, record in wrong.items():
            ttk.Separator(self.body).pack(fill="x", pady=16)
            if key not in self.by_id:
                self.label(
                    self.tr("{0}：题目已删除或无效，暂不能复习；记录保留，恢复题目后可继续。", key)
                )
                continue
            q = self.by_id[key]
            self.question_content(q)
            self.label(
                self.tr(
                    "答错 {0} 次 · 上次选择：{1}\n正确答案：{2}\n解析：{3}",
                    record["count"],
                    record["last_answer"],
                    q.answer,
                    q.explanation,
                )
            )
            self.button(self.tr("复习这道题"), lambda question=q: self.start_quiz([question], True))

    def history(self):
        if not self.check_session():
            return
        self.clear(self.tr("学习统计与历史"))
        self.button(self.tr("返回首页"), self.home)
        try:
            history = self.progress.load()["history"]
        except DataError as exc:
            self.label(self.tr(str(exc)))
            return
        total = sum(record["total"] for record in history)
        correct = sum(record["correct"] for record in history)
        accuracy = correct / total * 100 if total else 0
        self.label(
            self.tr(
                "完成 {0} 次练习（含复习） · 已答 {1} 题 · 正确 {2} 题 · 综合正确率 {3}%",
                len(history),
                total,
                correct,
                f"{accuracy:.2f}",
            )
        )
        if not history:
            self.label(self.tr("暂无完成的练习记录。"))
        for record in reversed(history):
            ttk.Separator(self.body).pack(fill="x", pady=10)
            self.label(
                self.tr(
                    "{0} · {1} · {2}\n题数 {3} | 正确 {4} | 错误 {5} | 正确率 {6}% | 得分 {7}/{8}",
                    record["date"],
                    record["subject"],
                    record["mode"],
                    record["total"],
                    record["correct"],
                    record["incorrect"],
                    f"{record['accuracy']:.2f}",
                    record["score"],
                    record["max_score"],
                )
            )


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()
