"""Shared desktop design tokens; no business logic or third-party dependencies."""

import tkinter.font as tkfont
from tkinter import ttk

BACKGROUND = "#F1F5F8"
SURFACE = "#FFFFFF"
INK = "#18313D"
MUTED = "#607784"
PRIMARY = "#137C72"
BORDER = "#D9E4E8"


def apply_theme(root, compact=False):
    """Use an explicit ttk theme so colors are consistent on Windows and Tk."""
    available = tkfont.families(root)
    family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in available else "TkDefaultFont"
    font = (family, 10)
    root.configure(background=BACKGROUND)
    # A global *Font override would also override title and metric ttk styles.
    tkfont.nametofont("TkDefaultFont", root=root).configure(family=family, size=10)
    root.option_add("*Text.font", font)
    root.option_add("*Listbox.font", font)
    root.option_add("*Text.background", SURFACE)
    root.option_add("*Text.foreground", INK)
    root.option_add("*Text.insertBackground", PRIMARY)
    root.option_add("*Text.selectBackground", "#D0EAE4")
    root.option_add("*Text.relief", "flat")
    root.option_add("*Text.highlightThickness", 1)
    root.option_add("*Text.highlightBackground", BORDER)
    root.option_add("*Text.highlightColor", PRIMARY)
    root.option_add("*Text.padX", 12)
    root.option_add("*Text.padY", 10)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=font, background=SURFACE, foreground=INK)
    style.configure("TFrame", background=SURFACE)
    style.configure("Page.TFrame", background=BACKGROUND)
    style.configure("Header.TFrame", background=INK)
    style.configure("Header.TLabel", background=INK, foreground="white", font=(family, 14, "bold"))
    style.configure("HeaderSmall.TLabel", background=INK, foreground="#B6DAD4", font=(family, 9))
    style.configure("TLabel", background=SURFACE, foreground=INK)
    style.configure("Title.TLabel", font=(family, 23, "bold"), foreground=INK)
    style.configure("Subtitle.TLabel", font=(family, 14, "bold"))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Metric.TLabel", foreground=PRIMARY, font=(family, 24, "bold"))
    style.configure(
        "TLabelframe", background=SURFACE, bordercolor=BORDER, relief="solid", borderwidth=1
    )
    style.configure(
        "TLabelframe.Label", background=SURFACE, foreground=MUTED, font=(family, 10, "bold")
    )
    style.configure(
        "TButton",
        padding=(16, 10),
        background=SURFACE,
        foreground=INK,
        bordercolor=BORDER,
        borderwidth=1,
        focusthickness=2,
        focuscolor=PRIMARY,
    )
    style.map(
        "TButton",
        background=[("disabled", "#F1F4F5"), ("active", "#E9F3F1")],
        foreground=[("disabled", "#92A2AA")],
        bordercolor=[("focus", PRIMARY)],
    )
    style.configure(
        "Accent.TButton",
        background=PRIMARY,
        foreground="white",
        bordercolor=PRIMARY,
        font=(family, 10, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", "#BDCFCD"), ("active", "#096258")],
        foreground=[("disabled", "#F3F7F6"), ("!disabled", "white")],
    )
    style.configure("Quiet.TButton", borderwidth=0, foreground=MUTED, padding=(12, 8))
    style.configure(
        "Header.TButton",
        background=INK,
        foreground="white",
        bordercolor="#607784",
        padding=(14, 6),
    )
    style.map(
        "Header.TButton",
        background=[("active", PRIMARY)],
        foreground=[("!disabled", "white")],
    )
    style.configure("Danger.TButton", foreground="#B13E36")
    style.configure(
        "TEntry",
        padding=9,
        fieldbackground=SURFACE,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        insertcolor=INK,
    )
    style.map("TEntry", bordercolor=[("focus", PRIMARY)])
    style.configure(
        "TCombobox", padding=8, fieldbackground=SURFACE, bordercolor=BORDER, arrowcolor=PRIMARY
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE)],
        foreground=[("readonly", INK)],
        bordercolor=[("focus", PRIMARY)],
    )
    style.configure("TRadiobutton", padding=8, background=SURFACE)
    style.configure(
        "Option.TRadiobutton",
        padding=(16, 14),
        relief="solid",
        borderwidth=1,
        bordercolor=BORDER,
        font=(family, 11),
    )
    style.map(
        "Option.TRadiobutton",
        background=[("selected", "#E5F3EE"), ("active", "#F3F8F7")],
        foreground=[("disabled", MUTED)],
        bordercolor=[("selected", PRIMARY), ("focus", PRIMARY)],
    )
    style.configure("Success.TLabel", background="#E5F3EE", foreground="#126449", padding=16)
    style.configure("Warning.TLabel", background="#FFF2E7", foreground="#924512", padding=16)
    style.configure(
        "Treeview",
        rowheight=36,
        background=SURFACE,
        fieldbackground=SURFACE,
        foreground=INK,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background="#EAF0F3",
        foreground=MUTED,
        font=(family, 10, "bold"),
        padding=(12, 10),
        relief="flat",
    )
    style.map("Treeview", background=[("selected", "#CCE8E1")], foreground=[("selected", INK)])
    style.configure("TSeparator", background=BORDER)
    style.configure(
        "TScrollbar", background="#D5DFE4", troughcolor=BACKGROUND, borderwidth=0, arrowsize=12
    )
    style.configure(
        "Horizontal.TProgressbar",
        background=PRIMARY,
        troughcolor="#E5EDEF",
        borderwidth=0,
        thickness=6,
    )
    if compact:
        style.configure("Title.TLabel", font=(family, 19, "bold"))
        style.configure("Metric.TLabel", font=(family, 19, "bold"))
        style.configure("TButton", padding=(12, 6))
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=5)
        style.configure("Option.TRadiobutton", padding=(12, 8))
        style.configure("Treeview", rowheight=28)
    return style
