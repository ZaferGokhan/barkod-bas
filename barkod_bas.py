# -*- coding: utf-8 -*-
"""Excel sütununu veya yapıştırılan listeyi Nelko P21'e barkod olarak basar."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from openpyxl import load_workbook

from nelko import find_nelko_port, print_text_labels


def column_letter(index: int) -> str:
    number = index + 1
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    return str(value).strip()


def sheet_preview(path: Path, header: bool) -> tuple[list[str], int]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = []
        width = 0
        for index, row in enumerate(sheet.iter_rows(values_only=True)):
            if index >= 40 and width:
                break
            rows.append(row)
            width = max(width, len(row))
        if not rows or width == 0:
            return [], 0
        names = []
        for index in range(width):
            if header:
                raw = rows[0][index] if index < len(rows[0]) else None
                title = cell_text(raw) or f"Sütun {column_letter(index)}"
            else:
                title = f"Sütun {column_letter(index)}"
            names.append(title)
        return names, width
    finally:
        workbook.close()


def column_values(path: Path, column: int, header: bool) -> list[str]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        values = []
        for index, row in enumerate(workbook.active.iter_rows(values_only=True)):
            if header and index == 0:
                continue
            if column >= len(row):
                continue
            text = cell_text(row[column])
            if text:
                values.append(text)
        return values
    finally:
        workbook.close()


def run() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    root.title("Barkod Bas")
    root.configure(bg="#eef2f6")
    root.attributes("-topmost", True)
    import ctypes

    primary_w = ctypes.windll.user32.GetSystemMetrics(0)
    root.geometry(f"440x560+{max(12, primary_w - 900)}+16")
    root.minsize(400, 480)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", font=("Segoe UI", 10))
    style.configure("TButton", padding=(10, 6))

    events: queue.Queue = queue.Queue()
    stop = threading.Event()
    excel_path = {"path": None}
    printing = {"on": False}

    body = ttk.Frame(root, padding=12)
    body.pack(fill="both", expand=True)

    mode = tk.StringVar(value="excel")
    ttk.Label(body, text="Kaynak").pack(anchor="w")
    mode_row = ttk.Frame(body)
    mode_row.pack(fill="x", pady=(2, 8))
    ttk.Radiobutton(mode_row, text="Excel sütunu", value="excel", variable=mode).pack(side="left")
    ttk.Radiobutton(mode_row, text="Liste", value="list", variable=mode).pack(side="left", padx=12)

    excel_box = ttk.LabelFrame(body, text="Excel", padding=8)
    excel_box.pack(fill="x")
    file_var = tk.StringVar(value="Dosya seçilmedi")
    ttk.Label(excel_box, textvariable=file_var).pack(anchor="w")
    pick_row = ttk.Frame(excel_box)
    pick_row.pack(fill="x", pady=6)
    ttk.Label(pick_row, text="Sütun").pack(side="left")
    column_box = ttk.Combobox(pick_row, state="readonly", width=28)
    column_box.pack(side="left", padx=8)
    header_var = tk.BooleanVar(value=True)

    def reload_columns() -> None:
        path = excel_path["path"]
        if path is None:
            column_box["values"] = []
            return
        names, _width = sheet_preview(path, header_var.get())
        column_box["values"] = names
        if names:
            column_box.current(0)

    def choose_excel() -> None:
        selected = filedialog.askopenfilename(
            title="Excel dosyası",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not selected:
            return
        excel_path["path"] = Path(selected)
        file_var.set(Path(selected).name)
        reload_columns()

    ttk.Button(pick_row, text="Dosya", command=choose_excel).pack(side="left")
    ttk.Checkbutton(
        excel_box,
        text="İlk satır başlık",
        variable=header_var,
        command=reload_columns,
    ).pack(anchor="w")

    list_box = ttk.LabelFrame(body, text="Liste — her satır bir etiket", padding=8)
    list_box.pack(fill="both", expand=True, pady=(8, 0))
    text = tk.Text(list_box, height=8, font=("Consolas", 11), wrap="none")
    text.pack(fill="both", expand=True)

    status_var = tk.StringVar(value="Hazır. Excel sütunu veya liste verin.")
    ttk.Label(body, textvariable=status_var, wraplength=400).pack(anchor="w", pady=(8, 4))

    def collect() -> list[str]:
        if mode.get() == "list":
            return [line.strip() for line in text.get("1.0", "end").splitlines() if line.strip()]
        path = excel_path["path"]
        if path is None:
            raise RuntimeError("Önce bir Excel dosyası seçin.")
        if column_box.current() < 0:
            raise RuntimeError("Bir sütun seçin.")
        return column_values(path, column_box.current(), header_var.get())

    def worker(items: list[str]) -> None:
        try:
            port_name = find_nelko_port()
            if not port_name:
                events.put(("done", "P21 eşleşmemiş. Yazıcıyı açıp Bluetooth'tan eşleştirin."))
                return

            def progress(index: int, total: int, label: str) -> None:
                events.put(("progress", f"{index} / {total}   {label}"))

            note = print_text_labels(port_name, items, progress=progress, stop=stop)
            events.put(("done", note))
        except Exception as exc:
            events.put(("done", f"Basılamadı: {exc}"))

    def start_print() -> None:
        if printing["on"]:
            return
        try:
            items = collect()
        except Exception as exc:
            messagebox.showinfo("Barkod Bas", str(exc))
            return
        if not items:
            messagebox.showinfo("Barkod Bas", "Basılacak satır yok.")
            return
        if not messagebox.askyesno("Barkod Bas", f"{len(items)} etiket basılsın mı?"):
            return
        stop.clear()
        printing["on"] = True
        print_button.state(["disabled"])
        status_var.set(f"Bağlanıyor, {len(items)} etiket...")
        threading.Thread(target=worker, args=(items,), daemon=True).start()

    def stop_print() -> None:
        stop.set()
        status_var.set("Bu etiketten sonra duracak")

    buttons = ttk.Frame(body)
    buttons.pack(fill="x", pady=(4, 0))
    print_button = ttk.Button(buttons, text="Hepsini bas", command=start_print)
    print_button.pack(side="left")
    ttk.Button(buttons, text="Durdur", command=stop_print).pack(side="left", padx=8)

    def poll() -> None:
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == "progress":
                    status_var.set(payload)
                elif kind == "done":
                    printing["on"] = False
                    print_button.state(["!disabled"])
                    status_var.set(payload)
        except queue.Empty:
            pass
        root.after(150, poll)

    hint = ttk.Label(
        body,
        text="Etiketler tek tek basılır. Biri çıkmadan diğeri başlamaz. Çok uzun satır atlanır.",
        wraplength=400,
        foreground="#5c6b7a",
    )
    hint.pack(anchor="w", pady=(8, 0))
    poll()
    root.mainloop()


if __name__ == "__main__":
    run()
