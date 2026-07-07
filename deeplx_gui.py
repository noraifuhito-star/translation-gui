import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import tkinter.font as tkfont
import requests
import json
import threading
import re
import os

LANGUAGES = [
    ("Auto Detect", "auto"),
    ("Bulgarian", "BG"), ("Czech", "CS"), ("Danish", "DA"),
    ("German", "DE"), ("Greek", "EL"), ("English", "EN"),
    ("Spanish", "ES"), ("Estonian", "ET"), ("Finnish", "FI"),
    ("French", "FR"), ("Hungarian", "HU"), ("Indonesian", "ID"),
    ("Italian", "IT"), ("Japanese", "JA"), ("Korean", "KO"),
    ("Lithuanian", "LT"), ("Latvian", "LV"), ("Norwegian", "NB"),
    ("Dutch", "NL"), ("Polish", "PL"), ("Portuguese", "PT"),
    ("Romanian", "RO"), ("Russian", "RU"), ("Slovak", "SK"),
    ("Slovenian", "SL"), ("Swedish", "SV"), ("Turkish", "TR"),
    ("Ukrainian", "UK"), ("Chinese (simplified)", "ZH"),
]


class FindReplaceDialog:
    def __init__(self, parent, text_widget):
        self.parent = parent
        self.text = text_widget
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Find / Replace")
        self.dialog.geometry("480x160")
        self.dialog.transient(parent)
        self.dialog.resizable(False, False)

        f = ttk.Frame(self.dialog, padding=10)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Find:").grid(row=0, column=0, sticky="e")
        self.find_var = tk.StringVar()
        self.find_entry = ttk.Entry(f, textvariable=self.find_var, width=40)
        self.find_entry.grid(row=0, column=1, padx=5, pady=2, columnspan=3)
        self.find_entry.focus_set()

        ttk.Label(f, text="Replace:").grid(row=1, column=0, sticky="e")
        self.replace_var = tk.StringVar()
        self.replace_entry = ttk.Entry(f, textvariable=self.replace_var, width=40)
        self.replace_entry.grid(row=1, column=1, padx=5, pady=2, columnspan=3)

        self.case_var = tk.BooleanVar()
        ttk.Checkbutton(f, text="Case", variable=self.case_var).grid(row=2, column=1, sticky="w")
        self.regex_var = tk.BooleanVar()
        ttk.Checkbutton(f, text="Regex", variable=self.regex_var).grid(row=2, column=2, sticky="w")

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=8)
        ttk.Button(btn_frame, text="Find Next", command=self.find_next, width=12).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Replace", command=self.replace, width=10).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Replace All", command=self.replace_all, width=12).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy, width=8).pack(side="left", padx=2)

        self.dialog.bind("<Return>", lambda e: self.find_next())
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

    def _get_content(self):
        return self.text.get("1.0", "end-1c")

    def _compile_pattern(self):
        pattern = self.find_var.get()
        if not pattern:
            return None
        flags = 0 if self.case_var.get() else re.I
        if not self.regex_var.get():
            pattern = re.escape(pattern)
        try:
            return re.compile(pattern, flags)
        except re.error:
            return None

    def find_next(self):
        pat = self._compile_pattern()
        if not pat:
            return
        content = self._get_content()
        cur = self.text.index("insert")
        start = self.text.index(f"{cur} + 1c")
        rest = self.text.get(start, "end-1c")
        offset = len(self.text.get("1.0", start)) - 1
        m = pat.search(rest)
        if m:
            abs_start = offset + m.start()
            abs_end = offset + m.end()
            idx_start = f"1.0 + {abs_start}c"
            idx_end = f"1.0 + {abs_end}c"
        else:
            m = pat.search(content)
            if not m:
                messagebox.showinfo("Find", "No match found", parent=self.dialog)
                return
            idx_start = f"1.0 + {m.start()}c"
            idx_end = f"1.0 + {m.end()}c"
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", idx_start, idx_end)
        self.text.see(idx_start)
        self.text.mark_set("insert", idx_end)

    def replace(self):
        pat = self._compile_pattern()
        if not pat:
            return
        if self.text.tag_ranges("sel"):
            start = self.text.index("sel.first")
            end = self.text.index("sel.last")
            sel = self.text.get(start, end)
            if pat.fullmatch(sel) if self.regex_var.get() else (sel == self.find_var.get()):
                repl = self.replace_var.get()
                if self.regex_var.get():
                    sel = pat.sub(repl, sel, count=1)
                else:
                    sel = repl
                self.text.delete(start, end)
                self.text.insert(start, sel)
                self.text.tag_add("sel", start, f"{start} + {len(sel)}c")
                self.text.see(start)
        self.find_next()

    def replace_all(self):
        pat = self._compile_pattern()
        if not pat:
            return
        content = self._get_content()
        repl = self.replace_var.get()
        if self.regex_var.get():
            new_content, count = pat.subn(repl, content)
        else:
            new_content, count = content.replace(self.find_var.get(), repl), content.count(self.find_var.get())
        if count == 0:
            messagebox.showinfo("Replace", "No matches found", parent=self.dialog)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", new_content)
        messagebox.showinfo("Replace", f"Replaced {count} occurrence(s)", parent=self.dialog)


class DeepLXGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DeepLX Translator")
        self.root.geometry("950x700")
        self.root.minsize(700, 500)

        self.server_url = tk.StringVar(value="http://127.0.0.1:1188")
        self.token = tk.StringVar(value="")
        self.source_lang = tk.StringVar(value="JA")
        self.target_lang = tk.StringVar(value="EN")
        self.status_var = tk.StringVar(value="Ready")
        self.word_wrap = tk.BooleanVar(value=True)
        self.dark_mode = tk.BooleanVar(value=True)
        self.file_path = None
        self.modified = False

        self._font = tkfont.Font(family="TkDefaultFont", size=10)
        self._auto_save_timer = None

        self._build_menu()
        self._build_ui()
        self._apply_theme()
        self._bind_shortcuts()
        self._check_server()
        self._update_status()

    def _build_menu(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        file_menu = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self._new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._save_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        edit_menu = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=lambda: self.input_text.edit_undo(), accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=lambda: self.input_text.edit_redo(), accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=lambda: self.root.focus_get().event_generate("<<Cut>>"), accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=lambda: self.root.focus_get().event_generate("<<Copy>>"), accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=lambda: self.root.focus_get().event_generate("<<Paste>>"), accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=lambda: self.input_text.tag_add("sel", "1.0", "end"), accelerator="Ctrl+A")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find / Replace...", command=self._find_dialog, accelerator="Ctrl+F")

        view_menu = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="View", menu=view_menu)
        view_menu.add_checkbutton(label="Dark Mode", variable=self.dark_mode, command=self._apply_theme)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Word Wrap", variable=self.word_wrap, command=self._toggle_wrap)
        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", command=lambda: self._zoom(1), accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=lambda: self._zoom(-1), accelerator="Ctrl+-")
        view_menu.add_command(label="Reset Zoom", command=self._zoom_reset, accelerator="Ctrl+0")

        tools_menu = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Word Count", command=self._word_count, accelerator="Ctrl+Shift+C")
        tools_menu.add_separator()
        tools_menu.add_command(label="Check Server", command=self._check_server)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        srv = ttk.LabelFrame(main, text="Server", padding=4)
        srv.pack(fill="x", pady=(0, 4))
        ttk.Label(srv, text="URL:").grid(row=0, column=0, sticky="e")
        ttk.Entry(srv, textvariable=self.server_url, width=28).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(srv, text="Token:").grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Entry(srv, textvariable=self.token, width=14, show="*").grid(row=0, column=3, sticky="w", padx=4)
        ttk.Button(srv, text="Check", command=self._check_server, width=6).grid(row=0, column=4, padx=4)

        lang = ttk.Frame(main)
        lang.pack(fill="x", pady=4)
        ttk.Label(lang, text="Source:").pack(side="left")
        self.src_menu = ttk.Combobox(lang, textvariable=self.source_lang,
                                     values=[f"{n} ({c})" for n, c in LANGUAGES], width=20, state="readonly")
        self.src_menu.pack(side="left", padx=4)
        self.src_menu.current(14)
        self._map_combo(self.src_menu, self.source_lang)

        ttk.Label(lang, text="Target:").pack(side="left", padx=(12, 0))
        self.tgt_menu = ttk.Combobox(lang, textvariable=self.target_lang,
                                     values=[f"{n} ({c})" for n, c in LANGUAGES if c != "auto"], width=20, state="readonly")
        self.tgt_menu.pack(side="left", padx=4)
        self.tgt_menu.current(5)
        self._map_combo(self.tgt_menu, self.target_lang)

        ttk.Button(lang, text="⇄", width=3, command=self._swap_langs).pack(side="left", padx=8)

        # paned window for input / buttons / output
        self.pane = ttk.PanedWindow(main, orient="vertical")
        self.pane.pack(fill="both", expand=True, pady=(4, 0))

        input_frame = ttk.Frame(self.pane)
        input_label = ttk.Frame(input_frame)
        input_label.pack(anchor="w", fill="x")
        ttk.Label(input_label, text="Input text:").pack(side="left")
        self.char_count_label = ttk.Label(input_label, text="0 chars", foreground="gray")
        self.char_count_label.pack(side="right")

        self.input_text = tk.Text(input_frame, height=6, wrap="word" if self.word_wrap.get() else "none",
                                  font=self._font, undo=True, padx=3, pady=3)
        v_scroll = ttk.Scrollbar(input_frame, orient="vertical", command=self.input_text.yview)
        self.input_text.configure(yscrollcommand=v_scroll.set)
        self.input_text.pack(fill="both", expand=True, side="left")
        v_scroll.pack(fill="y", side="right", before=self.input_text)
        self.input_text.bind("<<Modified>>", self._on_modified)
        self.input_text.bind("<KeyRelease>", self._on_key_release)
        self.input_menu = self._build_context_menu(self.input_text)
        self.pane.add(input_frame, weight=1)

        btn_frame = ttk.Frame(self.pane)
        ttk.Button(btn_frame, text="Clear Input", command=lambda: self.input_text.delete("1.0", "end")).pack(side="left")
        ttk.Button(btn_frame, text="Clear Output", command=self._clear_output).pack(side="left", padx=4)
        self.translate_btn = ttk.Button(btn_frame, text="Translate", command=self._translate, width=18)
        self.translate_btn.pack(side="right")
        self.pane.add(btn_frame, weight=0)

        output_frame = ttk.Frame(self.pane)
        out_label = ttk.Frame(output_frame)
        out_label.pack(anchor="w", fill="x")
        ttk.Label(out_label, text="Translation:").pack(side="left")
        self.out_char_count = ttk.Label(out_label, text="", foreground="gray")
        self.out_char_count.pack(side="right")

        self.output_text = tk.Text(output_frame, height=6, wrap="word", font=self._font,
                                   state="disabled", foreground="#333", padx=3, pady=3)
        y_scroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=y_scroll.set)
        self.output_text.pack(fill="both", expand=True, side="left")
        y_scroll.pack(fill="y", side="right", before=self.output_text)
        self.output_menu = self._build_context_menu(self.output_text)
        self.pane.add(output_frame, weight=1)

        sep = ttk.Separator(main, orient="horizontal")
        sep.pack(fill="x")
        self.status_label = ttk.Label(main, textvariable=self.status_var, anchor="w", foreground="gray")
        self.status_label.pack(fill="x", pady=(2, 0))

    def _bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self._new_file())
        self.root.bind("<Control-N>", lambda e: self._new_file())
        self.root.bind("<Control-o>", lambda e: self._open_file())
        self.root.bind("<Control-O>", lambda e: self._open_file())
        self.root.bind("<Control-s>", lambda e: self._save_file())
        self.root.bind("<Control-S>", lambda e: self._save_file())
        self.root.bind("<Control-Shift-S>", lambda e: self._save_as())
        self.root.bind("<Control-Shift-s>", lambda e: self._save_as())
        self.root.bind("<Control-f>", lambda e: self._find_dialog())
        self.root.bind("<Control-F>", lambda e: self._find_dialog())
        self.root.bind("<Control-h>", lambda e: self._find_dialog(replace=True))
        self.root.bind("<Control-H>", lambda e: self._find_dialog(replace=True))
        self.root.bind("<Control-plus>", lambda e: self._zoom(1))
        self.root.bind("<Control-KP_Add>", lambda e: self._zoom(1))
        self.root.bind("<Control-minus>", lambda e: self._zoom(-1))
        self.root.bind("<Control-KP_Subtract>", lambda e: self._zoom(-1))
        self.root.bind("<Control-0>", lambda e: self._zoom_reset())
        self.root.bind("<Control-Shift-c>", lambda e: self._word_count())
        self.root.bind("<Control-Shift-C>", lambda e: self._word_count())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        for w in (self.input_text, self.output_text):
            w.bind("<Control-a>", lambda e, w=w: (w.tag_remove("sel", "1.0", "end"), w.tag_add("sel", "1.0", "end")) or "break")
            w.bind("<Control-A>", lambda e, w=w: (w.tag_remove("sel", "1.0", "end"), w.tag_add("sel", "1.0", "end")) or "break")

    def _build_context_menu(self, text_widget):
        menu = tk.Menu(text_widget, tearoff=0, background="#333", foreground="#eee",
                       activebackground="#555", activeforeground="#fff",
                       disabledforeground="#888")
        is_readonly = str(text_widget.cget("state")) == "disabled"

        def _cut():
            text_widget.event_generate("<<Cut>>")
        def _copy():
            text_widget.event_generate("<<Copy>>")
        def _paste():
            text_widget.event_generate("<<Paste>>")
        def _delete():
            try:
                if text_widget.tag_ranges("sel"):
                    text_widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
        def _select_all():
            text_widget.tag_remove("sel", "1.0", "end")
            text_widget.tag_add("sel", "1.0", "end")
        def _undo():
            try:
                text_widget.edit_undo()
            except tk.TclError:
                pass
        def _redo():
            try:
                text_widget.edit_redo()
            except tk.TclError:
                pass

        if not is_readonly:
            menu.add_command(label="Undo", command=_undo, accelerator="Ctrl+Z")
            menu.add_command(label="Redo", command=_redo, accelerator="Ctrl+Y")
            menu.add_separator()
            menu.add_command(label="Cut", command=_cut, accelerator="Ctrl+X")
        else:
            menu.add_command(label="Cut", state="disabled")
        menu.add_command(label="Copy", command=_copy, accelerator="Ctrl+C")
        if not is_readonly:
            menu.add_command(label="Paste", command=_paste, accelerator="Ctrl+V")
            menu.add_command(label="Delete", command=_delete, accelerator="Del")
        else:
            menu.add_command(label="Paste", state="disabled")
            menu.add_command(label="Delete", state="disabled")
        menu.add_separator()
        menu.add_command(label="Select All", command=_select_all, accelerator="Ctrl+A")

        def _popup(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"
        text_widget.bind("<Button-3>", _popup)
        text_widget.bind("<Button-2>", _popup)  # older 2-button mice
        text_widget.bind("<Control-Button-3>", _popup)
        return menu

    @staticmethod
    def _lang_code(value):
        value = value.strip()
        if "(" in value and value.endswith(")"):
            value = value.split("(")[-1].rstrip(")")
        return value.upper()

    @staticmethod
    def _map_combo(combo, var):
        def on_select(event):
            var.set(combo.get())
        combo.bind("<<ComboboxSelected>>", on_select)

    def _swap_langs(self):
        src_code = self._lang_code(self.source_lang.get())
        if src_code == "AUTO":
            return
        src_disp = self.src_menu.get()
        tgt_disp = self.tgt_menu.get()
        self.source_lang.set(tgt_disp)
        self.target_lang.set(src_disp)

    # ---- notepad file ops ----
    def _new_file(self):
        if self.modified and not self._confirm_discard():
            return
        self.input_text.delete("1.0", "end")
        self.input_text.edit_reset()
        self.file_path = None
        self.modified = False
        self._update_title()

    def _open_file(self):
        if self.modified and not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open Text File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", content)
            self.input_text.edit_reset()
            self.file_path = path
            self.modified = False
            self._update_title()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")

    def _save_file(self):
        if self.file_path:
            self._do_save(self.file_path)
        else:
            self._save_as()

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Text File",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._do_save(path)
            self.file_path = path
            self._update_title()

    def _do_save(self, path):
        try:
            content = self.input_text.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.modified = False
            self._update_title()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    def _confirm_discard(self):
        return messagebox.askyesno("Unsaved Changes", "Save changes before closing?") or \
               messagebox.askyesno("Discard?", "Discard changes?")

    def _on_close(self):
        if self.modified:
            ret = messagebox.askyesnocancel("Unsaved Changes", "Save changes before closing?")
            if ret is None:
                return
            if ret:
                self._save_file()
        self.root.destroy()

    def _update_title(self):
        name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        mod = " *" if self.modified else ""
        self.root.title(f"DeepLX Translator — {name}{mod}")

    # ---- notepad edit ops ----
    def _find_dialog(self, replace=False):
        FindReplaceDialog(self.root, self.input_text)

    def _word_count(self):
        content = self.input_text.get("1.0", "end-1c")
        chars = len(content)
        words = len(re.findall(r'\S+', content))
        lines = int(self.input_text.index("end-1c").split(".")[0])
        messagebox.showinfo("Word Count", f"Characters: {chars}\nWords: {words}\nLines: {lines}")

    def _toggle_wrap(self):
        wrap = "word" if self.word_wrap.get() else "none"
        self.input_text.configure(wrap=wrap)

    def _apply_theme(self):
        dark = self.dark_mode.get()
        bg = "#1e1e1e" if dark else "#ffffff"
        fg = "#dcdcdc" if dark else "#000000"
        text_bg = "#252526" if dark else "#ffffff"
        text_fg = "#e6e6e6" if dark else "#000000"
        select_bg = "#264f78" if dark else "#0078d7"
        self.root.configure(bg=bg)
        self.root.option_add('*TCombobox*Listbox.background', text_bg)
        self.root.option_add('*TCombobox*Listbox.foreground', text_fg)
        self.root.option_add('*TCombobox*Listbox.selectBackground', select_bg)
        self.root.option_add('*TCombobox*Listbox.selectForeground', text_fg)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=bg, foreground=fg, fieldbackground=text_bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background="#333" if dark else "#f0f0f0", foreground=fg)
        style.configure("TEntry", fieldbackground=text_bg, foreground=text_fg)
        style.configure("TPanedwindow", background="#444" if dark else "#ccc")
        style.map("TCombobox",
                  fieldbackground=[("readonly", text_bg)],
                  foreground=[("readonly", text_fg)],
                  selectbackground=[("readonly", select_bg)])
        for widget in (self.input_text, self.output_text):
            widget.configure(bg=text_bg, fg=text_fg, insertbackground=text_fg, selectbackground=select_bg)
        self.char_count_label.configure(foreground="#aaa" if dark else "gray")
        self.out_char_count.configure(foreground="#aaa" if dark else "gray")
        self.status_label.configure(foreground="#aaa" if dark else "gray")
    def _zoom(self, delta):
        self.font_size = max(6, min(40, self._font.cget("size") + delta * 2))
        self._font.configure(size=self.font_size)

    def _zoom_reset(self):
        self._font.configure(size=10)

    def _clear_output(self):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")
        self.out_char_count.configure(text="")

    # ---- auto-save ----
    def _on_modified(self, event=None):
        if self.input_text.edit_modified():
            self.modified = True
            self._update_title()
            self.input_text.edit_modified(False)

    def _on_key_release(self, event=None):
        self._update_status()
        if self._auto_save_timer:
            self.root.after_cancel(self._auto_save_timer)
        self._auto_save_timer = self.root.after(2000, self._auto_save)

    def _auto_save(self):
        if self.modified and self.file_path:
            try:
                content = self.input_text.get("1.0", "end-1c")
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.modified = False
                self._update_title()
            except Exception:
                pass

    # ---- status bar ----
    def _update_status(self, msg=None):
        if msg:
            self.status_var.set(msg)
            return
        try:
            cursor = self.input_text.index("insert")
            line, col = cursor.split(".")
            content = self.input_text.get("1.0", "end-1c")
            chars = len(content)
            words = len(re.findall(r'\S+', content))
            self.status_var.set(f"Ln {line}, Col {col}  |  {words} words, {chars} chars")
            self.char_count_label.configure(text=f"{chars} chars")
        except Exception:
            pass

    # ---- server check ----
    def _check_server(self):
        self.status_var.set("Checking server…")
        def task():
            try:
                r = requests.get(self.server_url.get().rstrip("/"), timeout=3)
                if r.status_code == 200:
                    self.root.after(0, lambda: self._update_status("Server: OK"))
                else:
                    self.root.after(0, lambda: self._update_status(f"Server returned {r.status_code}"))
            except Exception as e:
                e_msg = str(e)
                self.root.after(0, lambda: self._update_status(f"Server unreachable: {e_msg}"))
        threading.Thread(target=task, daemon=True).start()

    # ---- translate ----
    def _translate(self):
        text = self.input_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("No input", "Please enter some text to translate.")
            return

        self.translate_btn.config(state="disabled", text="Translating…")
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")
        self.status_var.set("Translating…")

        threading.Thread(target=self._do_translate, args=(text,), daemon=True).start()

    @staticmethod
    def _safe_cut(rest, pos, min_pos):
        if pos >= len(rest):
            return len(rest)
        if pos > 0 and rest[pos - 1].isascii() and rest[pos - 1].isalnum() and pos < len(rest) and rest[pos].isascii() and rest[pos].isalnum():
            for i in range(pos, min_pos, -1):
                if not (rest[i - 1].isascii() and rest[i - 1].isalnum()):
                    return i
        return pos

    @staticmethod
    def _split_long_line(line, max_size=500):
        result, rest = [], line
        while len(rest) > max_size:
            chunk_end = max_size
            min_pos = max_size // 3
            window = rest[:max_size]
            matches = list(re.finditer(r'[。！？!?…]+[」』）\]\)]?', window))
            if matches and matches[-1].end() > min_pos:
                chunk_end = matches[-1].end()
            else:
                matches = list(re.finditer(r'(?<=[.!?…])\s+', window))
                if matches and matches[-1].end() > min_pos:
                    chunk_end = matches[-1].end()
                else:
                    matches = list(re.finditer(r'[、，,;:：]\s*', window))
                    if matches and matches[-1].end() > min_pos:
                        chunk_end = matches[-1].end()
            chunk_end = DeepLXGUI._safe_cut(rest, chunk_end, min_pos)
            result.append(rest[:chunk_end].rstrip())
            rest = rest[chunk_end:].lstrip()
        if rest:
            result.append(rest)
        return result

    @staticmethod
    def _chunk_text(text, max_size=500, min_size=100):
        paragraphs = re.split(r'\n[ \t]*\n', text.strip())
        chunks = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            lines = para.splitlines()
            cur = ""
            for line in lines:
                if len(line) > max_size:
                    oversized = DeepLXGUI._split_long_line(line, max_size)
                    if cur:
                        chunks.append(cur)
                        cur = ""
                    chunks.extend(oversized)
                    continue
                if not cur:
                    cur = line
                    continue
                candidate = cur + "\n" + line
                if len(candidate) <= max_size:
                    cur = candidate
                elif len(cur) < min_size:
                    cur = candidate
                else:
                    chunks.append(cur)
                    cur = line
            if cur:
                if chunks and len(cur) < min_size:
                    chunks[-1] += "\n" + cur
                else:
                    chunks.append(cur)
        if not chunks:
            chunks = [text]
        final = []
        for c in chunks:
            if len(c) > max_size:
                final.extend(DeepLXGUI._split_long_line(c, max_size))
            else:
                final.append(c)
        return final

    def _translate_chunk(self, url, headers, payload, timeout=30):
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        data = r.json()
        if data.get("code") != 200:
            msg = data.get("message", f"HTTP {r.status_code}")
            raise RuntimeError(msg)
        return data.get("data", "")

    def _do_translate(self, text):
        try:
            url = self.server_url.get().rstrip("/") + "/translate"
            headers = {"Content-Type": "application/json"}
            token_val = self.token.get().strip()
            if token_val:
                headers["Authorization"] = f"Bearer {token_val}"

            source_lang = self._lang_code(self.source_lang.get())
            target_lang = self._lang_code(self.target_lang.get())

            chunks = self._chunk_text(text)
            total = len(chunks)

            if total == 1:
                payload = {"text": text, "source_lang": source_lang, "target_lang": target_lang}
                result = self._translate_chunk(url, headers, payload)
                self.root.after(0, self._show_result, result)
                return

            results = []
            for i, chunk in enumerate(chunks, 1):
                self.root.after(0, lambda i=i: self.status_var.set(f"Translating chunk {i}/{total}…"))
                payload = {"text": chunk, "source_lang": source_lang, "target_lang": target_lang}
                result = self._translate_chunk(url, headers, payload)
                results.append(result)
            self.root.after(0, self._show_result, "\n".join(results))
        except requests.exceptions.Timeout:
            self.root.after(0, lambda: self._show_error("Request timed out"))
        except requests.ConnectionError:
            self.root.after(0, lambda: self._show_error("Cannot connect to server"))
        except json.JSONDecodeError:
            self.root.after(0, lambda: self._show_error("Invalid response from server"))
        except Exception as e:
            e_msg = str(e)
            self.root.after(0, lambda: self._show_error(e_msg))

    def _show_result(self, text):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")
        chars = len(text)
        self.out_char_count.configure(text=f"{chars} chars")
        self._update_status("Done")
        self.translate_btn.config(state="normal", text="Translate")

    def _show_error(self, msg):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", f"Error: {msg}")
        self.output_text.configure(state="disabled")
        self._update_status("Error")
        self.translate_btn.config(state="normal", text="Translate")


if __name__ == "__main__":
    root = tk.Tk()
    DeepLXGUI(root)
    root.mainloop()
