# -*- coding: utf-8 -*-

import json
import io
import os
import uuid
import Tkinter as tk
import tkMessageBox
import tkFileDialog
import tkFont

try:
    import ttk
except ImportError:
    ttk = None


# --- Constants -----------------------------------------------------------------

APP_TITLE = "Kanbanchik"
DEFAULT_FILE = "board.json"
CARD_BG = "#FFFFF0"
CARD_HOVER_BG = "#FFFACD"
CARD_BORDER = "#D4D0C8"
INSERTION_COLOR = "#FF6600"
DRAG_GHOST_BG = "#FFFFE0"
FONT_FAMILY = "TkDefaultFont"

COLUMN_DEFS = [
    {"id": "todo",  "title": u"Надо",   "header_bg": "#F0C060", "col_bg": "#FFF3CD"},
    {"id": "doing", "title": u"Делаю",  "header_bg": "#60B0D0", "col_bg": "#D0ECF5"},
    {"id": "done",  "title": u"Готово", "header_bg": "#60D060", "col_bg": "#D0F5D0"},
]


# --- CardDialog: modal add / edit window -------------------------------------

class CardDialog(tk.Toplevel):
    """Modal dialog for creating or editing a card.  Returns (title, desc) or None."""

    def __init__(self, parent, title_text=u"", desc_text=u""):
        tk.Toplevel.__init__(self, parent)
        self.transient(parent)
        self.grab_set()

        self.result = None
        is_new = not title_text
        self.title(u"Новая карточка" if is_new else u"Редактировать карточку")

        # Title entry
        tk.Label(self, text=u"Название:").grid(
            row=0, column=0, padx=5, pady=(5, 2), sticky=tk.W)
        self.title_var = tk.StringVar(value=title_text)
        entry = tk.Entry(self, textvariable=self.title_var, width=40)
        entry.grid(row=0, column=1, padx=5, pady=(5, 2), sticky=tk.EW)

        # Description text area
        tk.Label(self, text=u"Описание:").grid(
            row=1, column=0, padx=5, pady=2, sticky=tk.NW)
        self.desc_text = tk.Text(self, width=40, height=5, wrap=tk.WORD)
        self.desc_text.grid(row=1, column=1, padx=5, pady=2, sticky=tk.EW)
        if desc_text:
            self.desc_text.insert("1.0", desc_text)

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=5)
        tk.Button(btn_frame, text=u"OK", width=10,
                  command=self._on_ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text=u"Отмена", width=10,
                  command=self._on_cancel).pack(side=tk.LEFT, padx=5)

        self.columnconfigure(1, weight=1)
        self.resizable(False, False)

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry("+{}+{}".format(x, y))

        entry.focus_set()
        entry.selection_range(0, tk.END)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window()

    def _on_ok(self):
        title = self.title_var.get().strip()
        if not title:
            tkMessageBox.showwarning(u"Ошибка",
                                     u"Название не может быть пустым.",
                                     parent=self)
            return
        desc = self.desc_text.get("1.0", "end-1c").strip()
        self.result = (title, desc)
        self.destroy()

    def _on_cancel(self):
        self.destroy()


# --- Card widget --------------------------------------------------------------

class Card(tk.Frame):
    """Single kanban card — title, optional description, drag & context bindings."""

    def __init__(self, parent, card_data, board):
        self._data = card_data
        self._board = board
        self.column = None
        self._hover = False

        tk.Frame.__init__(self, parent, bg=CARD_BG, bd=1, relief=tk.RAISED,
                          padx=4, pady=3)
        self.columnconfigure(0, weight=1)

        # Title label
        self._lbl_title = tk.Label(
            self, text=card_data["title"], bg=CARD_BG,
            font=(FONT_FAMILY, 10, "bold"),
            anchor=tk.W, wraplength=170, justify=tk.LEFT)
        self._lbl_title.grid(row=0, column=0, sticky=tk.EW)

        # Description label (optional)
        desc = card_data.get("description", u"")
        if desc:
            self._lbl_desc = tk.Label(
                self, text=desc, bg=CARD_BG,
                font=(FONT_FAMILY, 8), anchor=tk.W,
                wraplength=170, justify=tk.LEFT, fg="#555555")
            self._lbl_desc.grid(row=1, column=0, sticky=tk.EW, pady=(2, 0))
        else:
            self._lbl_desc = None

        # Event bindings – forward all events through bound children
        self._bind_events()
        self._update_bg(CARD_BG)

    # -- helpers ---------------------------------------------------------------

    def _bind_events(self):
        for w in (self, self._lbl_title):
            w.bind("<Button-1>", self._on_press)
            w.bind("<Double-Button-1>", self._on_double_click)
            w.bind("<Button-3>", self._on_context)
        if self._lbl_desc:
            self._lbl_desc.bind("<Button-1>", self._on_press)
            self._lbl_desc.bind("<Double-Button-1>", self._on_double_click)
            self._lbl_desc.bind("<Button-3>", self._on_context)

    def _update_bg(self, color):
        self.configure(bg=color)
        self._lbl_title.configure(bg=color)
        if self._lbl_desc:
            self._lbl_desc.configure(bg=color)

    @property
    def card_data(self):
        return self._data

    # -- event handlers --------------------------------------------------------

    def _on_press(self, event):
        self._board.start_drag(self)

    def _on_double_click(self, event):
        self._board.edit_card(self)

    def _on_context(self, event):
        self._board.show_context_menu(self, event)

    def on_hover(self, active):
        """Called by the board to toggle hover appearance."""
        if active and self._board.is_dragging:
            return
        self._hover = active
        self._update_bg(CARD_HOVER_BG if active else CARD_BG)

    def set_hover_during_drag(self):
        """Force hover bg while this card is the drag source visual."""
        self._update_bg(CARD_HOVER_BG)


# --- Column widget -----------------------------------------------------------

class Column(tk.Frame):
    """A single board column: coloured header, scrollable card area."""

    def __init__(self, parent, col_def, board):
        tk.Frame.__init__(self, parent, bd=1, relief=tk.SUNKEN)
        self._col_def = col_def
        self._board = board
        self._cards = []
        self._highlighted = False

        # Header
        hdr = tk.Frame(self, bg=col_def["header_bg"], height=36)
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)

        tk.Label(hdr, text=col_def["title"], bg=col_def["header_bg"],
                 font=(FONT_FAMILY, 12, "bold")).pack(
                     side=tk.LEFT, padx=8, pady=4)

        btn_add = tk.Button(hdr, text=u"+",
                            font=(FONT_FAMILY, 10, "bold"),
                            width=2, bd=1,
                            command=lambda: board.add_card_ui(col_def["id"]))
        btn_add.pack(side=tk.RIGHT, padx=4, pady=2)

        # Canvas + scrollbar
        self._canvas = tk.Canvas(self, bg=col_def["col_bg"],
                                 bd=0, highlightthickness=0)
        sb = tk.Scrollbar(self, orient=tk.VERTICAL,
                          command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame (hosts cards)
        self._inner = tk.Frame(self._canvas, bg=col_def["col_bg"])
        self._inner_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor=tk.NW)
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Insertion-point marker
        self._ins = tk.Frame(self._inner, bg=INSERTION_COLOR, height=3)

        # Motion events for drag-drop target detection
        self._canvas.bind("<B1-Motion>", board.on_drag_motion)
        self._inner.bind("<B1-Motion>", board.on_drag_motion)

    # -- properties ------------------------------------------------------------

    @property
    def col_def(self):
        return self._col_def

    @property
    def cards(self):
        return self._cards

    @property
    def inner(self):
        return self._inner

    # -- canvas scroll logic ---------------------------------------------------

    def _on_inner_configure(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._inner_id, width=event.width)

    # -- card management -------------------------------------------------------

    def add_card_widget(self, card, index=None):
        if index is None:
            index = len(self._cards)
        card.configure(bg=CARD_BG)
        if index < len(self._cards):
            before = self._cards[index]
            card.pack(in_=self._inner, fill=tk.X, padx=3, pady=2, before=before)
        else:
            card.pack(in_=self._inner, fill=tk.X, padx=3, pady=2)
        self._cards.insert(index, card)
        card.column = self

    def remove_card_widget(self, card):
        if card in self._cards:
            self._cards.remove(card)
            card.pack_forget()

    # -- insertion-index calculation (for drag-drop) ---------------------------

    def get_insert_index(self, y):
        if not self._cards:
            return 0
        for i, c in enumerate(self._cards):
            cy = c.winfo_y()
            ch = c.winfo_height()
            if y < cy + ch // 2:
                return i
        return len(self._cards)

    # -- visual feedback -------------------------------------------------------

    def show_insertion(self, index):
        self._ins.place_forget()
        if index < len(self._cards):
            y = self._cards[index].winfo_y()
            if y > 0:
                y -= 1
            self._ins.place(x=2, y=y, relwidth=1, width=-4)
        else:
            if self._cards:
                y = self._cards[-1].winfo_y() + self._cards[-1].winfo_height()
            else:
                y = 0
            self._ins.place(x=2, y=y, relwidth=1, width=-4)
        self._ins.lift()

    def hide_insertion(self):
        self._ins.place_forget()

    def set_highlight(self, on):
        if on != self._highlighted:
            self._highlighted = on
            if on:
                self.configure(bd=2, relief=tk.FLAT, bg="#4488FF")
            else:
                self.configure(bd=1, relief=tk.SUNKEN, bg="SystemButtonFace")


# --- Board widget ------------------------------------------------------------

class Board(tk.Frame):
    """Three-column board.  Owns drag-drop logic and delegates to App."""

    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent)
        self._app = app
        self._columns = {}
        self._dragging = False
        self._drag_data = None
        self._drag_src_col = None
        self._ghost = None

        for cd in COLUMN_DEFS:
            col = Column(self, cd, self)
            col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
            self._columns[cd["id"]] = col

    # -- properties ------------------------------------------------------------

    @property
    def is_dragging(self):
        return self._dragging

    def get_column(self, col_id):
        return self._columns.get(col_id)

    # -- rebuild from data -----------------------------------------------------

    def rebuild_from_data(self, cards_data):
        col_ids = [cd["id"] for cd in COLUMN_DEFS]
        by_col = {cid: [] for cid in col_ids}
        for cd in cards_data:
            by_col.setdefault(cd.get("column", "todo"), []).append(cd)

        for cid in col_ids:
            col = self._columns[cid]
            for w in list(col.cards):
                col.remove_card_widget(w)
                w.destroy()
            sorted_cards = sorted(by_col.get(cid, []),
                                  key=lambda c: c.get("order", 0))
            for cd in sorted_cards:
                card = Card(col.inner, cd, self)
                col.add_card_widget(card)

    def add_card_to_column(self, col_id, card_data, index=None):
        col = self._columns[col_id]
        card = Card(col.inner, card_data, self)
        col.add_card_widget(card, index)
        return card

    # -- drag-and-drop ---------------------------------------------------------

    def start_drag(self, card):
        if self._dragging:
            return
        self._dragging = True
        self._drag_data = card.card_data
        self._drag_src_col = card.column

        # Remove the card widget
        self._drag_src_col.remove_card_widget(card)
        card.destroy()

        # Ghost label
        self._ghost = tk.Label(
            self.master, text=self._drag_data["title"],
            bg=DRAG_GHOST_BG, font=(FONT_FAMILY, 10, "bold"),
            bd=2, relief=tk.RAISED)
        self._place_ghost()

        self.master.bind("<B1-Motion>", self.on_drag_motion)
        self.master.bind("<ButtonRelease-1>", self.on_drag_release)
        self.master.focus_set()

    def _place_ghost(self):
        if not self._ghost:
            return
        rx = self.master.winfo_rootx()
        ry = self.master.winfo_rooty()
        mx = self.master.winfo_pointerx() - rx
        my = self.master.winfo_pointery() - ry
        self._ghost.place(x=mx, y=my, anchor=tk.CENTER)

    def on_drag_motion(self, event):
        if not self._dragging:
            return
        self._place_ghost()

        for col in self._columns.values():
            col.set_highlight(False)
            col.hide_insertion()

        target = self._find_column(event.x_root, event.y_root)
        if target:
            target.set_highlight(True)
            inner_y = event.y_root - target.inner.winfo_rooty()
            inner_y += float(target._canvas.canvasy(0))
            idx = target.get_insert_index(inner_y)
            target.show_insertion(idx)

    def on_drag_release(self, event):
        if not self._dragging:
            return

        self.master.unbind("<B1-Motion>")
        self.master.unbind("<ButtonRelease-1>")

        if self._ghost:
            self._ghost.destroy()
            self._ghost = None

        target = self._find_column(event.x_root, event.y_root)
        if target:
            inner_y = event.y_root - target.inner.winfo_rooty()
            inner_y += float(target._canvas.canvasy(0))
            idx = target.get_insert_index(inner_y)
            card = Card(target.inner, self._drag_data, self)
            target.add_card_widget(card, idx)
            self._drag_data["column"] = target.col_def["id"]
            self._app._update_orders()
            self._app.update_counts()
            self._app.set_action(u"Карточка перемещена")
        else:
            card = Card(self._drag_src_col.inner, self._drag_data, self)
            self._drag_src_col.add_card_widget(card)

        for col in self._columns.values():
            col.set_highlight(False)
            col.hide_insertion()

        self._dragging = False
        self._drag_data = None
        self._drag_src_col = None

    def cancel_drag(self):
        if not self._dragging:
            return
        self.master.unbind("<B1-Motion>")
        self.master.unbind("<ButtonRelease-1>")

        if self._ghost:
            self._ghost.destroy()
            self._ghost = None

        if self._drag_data and self._drag_src_col:
            card = Card(self._drag_src_col.inner, self._drag_data, self)
            self._drag_src_col.add_card_widget(card)

        for col in self._columns.values():
            col.set_highlight(False)
            col.hide_insertion()

        self._dragging = False
        self._drag_data = None
        self._drag_src_col = None

    def _find_column(self, x_root, y_root):
        for col in self._columns.values():
            fx = col.winfo_rootx()
            fy = col.winfo_rooty()
            fw = col.winfo_width()
            fh = col.winfo_height()
            if fx <= x_root <= fx + fw and fy <= y_root <= fy + fh:
                return col
        return None

    # -- card editing / context menu -------------------------------------------

    def edit_card(self, card):
        data = card.card_data
        dlg = CardDialog(self.master, data["title"],
                         data.get("description", u""))
        if dlg.result:
            title, desc = dlg.result
            data["title"] = title
            data["description"] = desc
            card._lbl_title.configure(text=title)

            if card._lbl_desc:
                if desc:
                    card._lbl_desc.configure(text=desc)
                else:
                    card._lbl_desc.destroy()
                    card._lbl_desc = None
            elif desc:
                lbl = tk.Label(card, text=desc, bg=CARD_BG,
                               font=(FONT_FAMILY, 8), anchor=tk.W,
                               wraplength=170, justify=tk.LEFT, fg="#555555")
                lbl.grid(row=1, column=0, sticky=tk.EW, pady=(2, 0))
                lbl.bind("<Button-1>", card._on_press)
                lbl.bind("<Double-Button-1>", card._on_double_click)
                lbl.bind("<Button-3>", card._on_context)
                card._lbl_desc = lbl

            self._app.set_action(u"Карточка отредактирована")
            self._app.update_counts()

    def show_context_menu(self, card, event):
        menu = tk.Menu(self.master, tearoff=False)
        menu.add_command(label=u"Редактировать",
                         command=lambda: self.edit_card(card))
        menu.add_command(label=u"Удалить",
                         command=lambda: self._app.delete_card(card))
        menu.post(event.x_root, event.y_root)

    def add_card_ui(self, col_id):
        self._app.add_card(col_id)


# --- Main application --------------------------------------------------------

class App(object):
    """Application controller: data model, menus, toolbar, status bar."""

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.minsize(800, 500)

        self._cards_data = []
        self._current_file = None

        self._build_menubar()
        self._build_toolbar()
        self._board = Board(root, self)
        self._board.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._build_statusbar()

        # Global hotkeys
        self.root.bind("<Control-n>", lambda e: self.new_board())
        self.root.bind("<Control-N>", lambda e: self.new_board())
        self.root.bind("<Control-o>", lambda e: self.open_board())
        self.root.bind("<Control-O>", lambda e: self.open_board())
        self.root.bind("<Control-s>", lambda e: self.save_board())
        self.root.bind("<Control-S>", lambda e: self.save_board())
        self.root.bind("<Escape>", lambda e: self._board.cancel_drag())

        self._auto_load()
        self.update_counts()

    # -- UI construction -------------------------------------------------------

    def _build_menubar(self):
        mb = tk.Menu(self.root)
        fm = tk.Menu(mb, tearoff=False)
        fm.add_command(label=u"Новая доска", command=self.new_board,
                       accelerator="Ctrl+N")
        fm.add_command(label=u"Открыть...", command=self.open_board,
                       accelerator="Ctrl+O")
        fm.add_command(label=u"Сохранить", command=self.save_board,
                       accelerator="Ctrl+S")
        fm.add_separator()
        fm.add_command(label=u"Выход", command=self.root.quit)
        mb.add_cascade(label=u"Файл", menu=fm)

        hm = tk.Menu(mb, tearoff=False)
        hm.add_command(label=u"О программе",
                       command=self._show_about)
        mb.add_cascade(label=u"Справка", menu=hm)

        self.root.config(menu=mb)

    def _build_toolbar(self):
        tb = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        tb.pack(fill=tk.X, side=tk.TOP)
        for txt, cmd in [(u"Новая", self.new_board),
                         (u"Открыть", self.open_board),
                         (u"Сохранить", self.save_board)]:
            tk.Button(tb, text=txt, command=cmd, bd=1).pack(
                side=tk.LEFT, padx=2, pady=2)

    def _build_statusbar(self):
        sb = tk.Frame(self.root, bd=1, relief=tk.SUNKEN)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        self._lbl_counts = tk.Label(sb, text=u"", anchor=tk.W, padx=4)
        self._lbl_counts.pack(side=tk.LEFT)
        self._lbl_action = tk.Label(sb, text=u"", anchor=tk.E,
                                    padx=4, fg="#666666")
        self._lbl_action.pack(side=tk.RIGHT)

    def _show_about(self):
        tkMessageBox.showinfo(
            u"О программе",
            u"Kanbanchik v1.0\n"
            u"Канбан-доска на Python 2.7 + Tkinter\n\n"
            u"Три колонки: Надо / Делаю / Готово\n"
            u"Перетаскивание, редактирование, сохранение в JSON",
            parent=self.root)

    # -- data-model helpers ----------------------------------------------------

    def update_counts(self):
        counts = {}
        for cd in self._cards_data:
            col = cd.get("column", "todo")
            counts[col] = counts.get(col, 0) + 1
        parts = []
        for cd in COLUMN_DEFS:
            parts.append(u"{}: {}".format(
                cd["title"], counts.get(cd["id"], 0)))
        self._lbl_counts.configure(text=u"  |  ".join(parts))

    def set_action(self, msg):
        self._lbl_action.configure(text=msg)

    def _update_orders(self):
        for cd in COLUMN_DEFS:
            col = self._board.get_column(cd["id"])
            for i, w in enumerate(col.cards):
                w.card_data["order"] = i

    # -- card operations -------------------------------------------------------

    def add_card(self, col_id):
        dlg = CardDialog(self.root)
        if dlg.result:
            title, desc = dlg.result
            data = {
                "id": uuid.uuid4().hex,
                "title": title,
                "description": desc,
                "column": col_id,
                "order": len(self._board.get_column(col_id).cards),
            }
            self._cards_data.append(data)
            self._board.add_card_to_column(col_id, data)
            self.set_action(u"Добавлена карточка")
            self.update_counts()

    def delete_card(self, card):
        data = card.card_data
        ok = tkMessageBox.askyesno(
            u"Подтверждение",
            u"Удалить карточку \u00ab{}\u00bb?".format(data["title"]),
            parent=self.root)
        if ok:
            card.column.remove_card_widget(card)
            card.destroy()
            self._cards_data = [c for c in self._cards_data
                                if c["id"] != data["id"]]
            self.set_action(u"Карточка удалена")
            self.update_counts()

    # -- persistence -----------------------------------------------------------

    def _serialize(self):
        self._update_orders()
        return {"version": 1, "cards": self._cards_data}

    def _deserialize(self, data):
        if not isinstance(data, dict) or "cards" not in data:
            raise ValueError(u"Неверный формат файла")
        self._cards_data = data["cards"]
        self._board.rebuild_from_data(self._cards_data)

    def new_board(self):
        if self._cards_data:
            ok = tkMessageBox.askyesno(
                u"Подтверждение",
                u"Создать новую доску?\n"
                u"Несохранённые изменения будут потеряны.",
                parent=self.root)
            if not ok:
                return
        self._cards_data = []
        for cd in COLUMN_DEFS:
            col = self._board.get_column(cd["id"])
            for w in list(col.cards):
                col.remove_card_widget(w)
                w.destroy()
        self._current_file = None
        self.set_action(u"Новая доска")
        self.update_counts()

    def save_board(self):
        if self._board.is_dragging:
            return
        if self._current_file:
            self._do_save(self._current_file)
        else:
            self.save_board_as()

    def save_board_as(self):
        fn = tkFileDialog.asksaveasfilename(
            parent=self.root, title=u"Сохранить доску",
            defaultextension=".json",
            filetypes=[(u"JSON файлы", "*.json"),
                       (u"Все файлы", "*.*")])
        if fn:
            self._current_file = fn
            self._do_save(fn)

    def _do_save(self, fn):
        try:
            data = self._serialize()
            with io.open(fn, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
            self.set_action(u"Сохранено: {}".format(os.path.basename(fn)))
        except Exception as e:
            tkMessageBox.showerror(u"Ошибка сохранения",
                                   unicode(e), parent=self.root)

    def open_board(self):
        if self._board.is_dragging:
            return
        fn = tkFileDialog.askopenfilename(
            parent=self.root, title=u"Открыть доску",
            defaultextension=".json",
            filetypes=[(u"JSON файлы", "*.json"),
                       (u"Все файлы", "*.*")])
        if fn:
            self._do_load(fn)

    def _do_load(self, fn):
        try:
            with io.open(fn, "r", encoding="utf-8") as f:
                data = json.loads(f.read())
            self._deserialize(data)
            self._current_file = fn
            self.set_action(u"Загружено: {}".format(os.path.basename(fn)))
            self.update_counts()
        except Exception as e:
            tkMessageBox.showerror(u"Ошибка загрузки",
                                   unicode(e), parent=self.root)

    def _auto_load(self):
        if os.path.exists(DEFAULT_FILE):
            try:
                self._do_load(DEFAULT_FILE)
                self._current_file = DEFAULT_FILE
            except Exception:
                self._current_file = None


# --- Entry point -------------------------------------------------------------

def main():
    import sys
    reload(sys)
    sys.setdefaultencoding("utf-8")

    root = tk.Tk()
    root.geometry("900x600")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()