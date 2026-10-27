"""One Tkinter interface for setup, quizzes, notebook and learning history."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .auth import AuthService
from .editor_ui import EditorPage
from .i18n import Translator
from .models import option_label
from .repositories import ProgressRepository, QuestionRepository
from .services import QuizEngine, image_path, select_questions
from .storage import DataError
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
        self.signed_in = False
        self.users_page = None
        self.user = None
        self.editor = None
        self.engine = None
        self.images = []
        root.title(self.tr("多学科练习平台 | Quiz Platform"))
        root.geometry("940x760")
        root.minsize(680, 540)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.configure("TButton", padding=8)
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("TLabel", font=("Microsoft YaHei UI", 11))
        style.configure("TRadiobutton", font=("Microsoft YaHei UI", 11), padding=6)
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=12)
        # Every screen scrolls, including long questions, images and histories.
        outer = ttk.Frame(root)
        outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, padding=24)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width)
        )
        root.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta / 120), "units"))
        self.load_bank()
        self.login_page()

    def login_page(self, registering=False):
        """A local account owns progress; guest mode preserves the V1 data file."""
        self.engine = None
        self.editor = None
        self.users_page = None
        self.signed_in = False
        self.clear(self.tr("QUIZ STUDIO · 学习空间"))
        self.label(
            self.tr("每天一点练习，看见自己的进步。\n英语 · 数学 · 科学 | 本地保存 · 离线使用")
        )
        card = ttk.LabelFrame(
            self.body,
            text=self.tr("创建本地账户") if registering else self.tr("欢迎回来"),
            padding=24,
        )
        card.pack(fill="x", pady=24)
        self.login_name = tk.StringVar()
        self.login_password = tk.StringVar()
        self.login_confirm = tk.StringVar()
        for title, variable, secret in [
            (self.tr("用户名"), self.login_name, False),
            (self.tr("密码"), self.login_password, True),
        ]:
            ttk.Label(card, text=title).pack(anchor="w", pady=(10, 5))
            ttk.Entry(card, textvariable=variable, show="•" if secret else "", width=40).pack(
                anchor="w"
            )
        if registering:
            ttk.Label(card, text=self.tr("确认密码")).pack(anchor="w", pady=(10, 5))
            ttk.Entry(card, textvariable=self.login_confirm, show="•", width=40).pack(anchor="w")
            ttk.Label(card, text=self.tr("用户名 3–32 位；密码 6–16 位。"), padding=8).pack(
                anchor="w"
            )
        self.login_error = ttk.Label(card, text="", foreground="#b42318", wraplength=580)
        self.login_error.pack(anchor="w", pady=8)
        self.login_button = ttk.Button(
            card,
            text=self.tr("注册并进入") if registering else self.tr("登录"),
            style="Accent.TButton",
            command=lambda: self.authenticate(registering),
        )
        self.login_button.pack(anchor="w", pady=8)
        ttk.Button(
            card,
            text=self.tr("已有账户，去登录") if registering else self.tr("没有账户？创建账户"),
            command=lambda: self.login_page(not registering),
        ).pack(anchor="w", pady=5)
        self.button(self.tr("访客进入（保留原有练习记录）"), self.enter_guest)
        self.label(self.tr("账户保存在本机；只有管理员可以维护题库和管理用户。"))
        self.button(self.tr("设置 / 语言"), self.settings)
        if self.tr.warning:
            self.label(self.tr.warning)
        self.button(self.tr("退出"), self.close)

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
        self.button(self.tr("保存语言设置"), self.save_language)
        self.button(self.tr("返回"), self.home if self.signed_in else self.login_page)

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
        self.canvas.yview_moveto(0)
        ttk.Label(self.body, text=title, style="Title.TLabel").pack(anchor="w", pady=(0, 20))

    def label(self, text):
        widget = ttk.Label(self.body, text=text, wraplength=620, justify="left")
        widget.pack(anchor="w", pady=6)
        return widget

    def button(self, text, command):
        widget = ttk.Button(self.body, text=text, command=command)
        widget.pack(anchor="w", pady=6)
        return widget

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
        self.clear(self.tr("多学科练习平台"))
        self.label(self.tr("你好，{0}。", self.user["name"] if self.user else self.tr("访客")))
        self.label(
            self.tr(
                "离线学习 · 即时反馈 · 错题复习\n已加载 {0} 道题，{1} 个学科。",
                len(self.questions),
                len({q.subject for q in self.questions}),
            )
        )
        self.button(self.tr("开始练习"), self.configure)
        self.button(self.tr("错题本与复习"), self.notebook)
        self.button(self.tr("学习统计与历史"), self.history)
        if self.user and self.user["role"] == "admin":
            self.button(self.tr("题库管理 / 上传图片"), self.manage_questions)
            self.button(self.tr("用户管理"), self.manage_users)
        self.button(self.tr("设置 / 语言"), self.settings)
        self.button(self.tr("重新加载题库"), self.home)
        self.button(self.tr("退出登录 / 切换账户"), self.logout)
        self.button(self.tr("退出"), self.close)
        if self.bank.warnings:
            self.label(
                self.tr("题库提示（其他有效题目仍可使用）：\n") + "\n".join(self.bank.warnings)
            )
        try:
            self.progress.load()
        except DataError as exc:
            self.label(self.tr(str(exc)))

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
        self.button(self.tr("开始"), self.start_configured)
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
        self.label(f"{q.subject} / {q.topic} / {q.difficulty}  ·  {q.id}")
        self.label(q.question)
        self.show_image(q.question_image)
        self.option_buttons = []
        for index, option in enumerate(q.options):
            if selectable:
                widget = ttk.Radiobutton(
                    self.body,
                    text=f"{option_label(index)}: {option}",
                    variable=self.answer,
                    value=option,
                )
                widget.pack(anchor="w", pady=3)
                self.option_buttons.append(widget)
            else:
                self.label(f"{option_label(index)}: {option}")
            if q.option_images:
                self.show_image(q.option_images[index])

    def show_question(self):
        engine = self.engine
        mode = self.tr("错题复习") if engine.review else self.tr("练习")
        self.clear(self.tr("{0} · 第 {1} / {2} 题", mode, engine.index + 1, len(engine.questions)))
        self.answer = tk.StringVar(value="")
        self.question_content(engine.current, selectable=True)
        self.submit_button = self.button(self.tr("提交答案"), self.submit)
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
            text=self.tr(
                "{0}\n正确答案：{1}\n解析：{2}",
                self.tr("回答正确！") if correct else self.tr("回答错误，已记入错题本。"),
                q.answer,
                q.explanation,
            )
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
