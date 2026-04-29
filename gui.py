"""
Stamp Detector — graphical interface (tkinter).

Wraps scanner.scan_folder in a friendly window: pick a folder, click Run,
watch progress. No terminal needed.

Run:
    python gui.py
    stamp_detector.exe       (when packaged as windowed exe)
"""

import io
import os
import queue
import sys
import threading
from pathlib import Path

# When running as windowed exe / pythonw, stdout/stderr are None.
# tqdm and print() inside scanner.py will crash without these.
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

from scanner import scan_folder


class StampDetectorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Поиск штампов в документах")
        root.geometry("780x600")
        root.minsize(700, 540)

        self.scan_thread: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.progress_queue: queue.Queue = queue.Queue()

        self._build_ui()
        self._poll_progress()

    # ─────────────────────── UI layout ───────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        # Form
        form = ttk.LabelFrame(self.root, text="Настройки", padding=10)
        form.pack(fill="x", **pad)

        # Input folder
        ttk.Label(form, text="Папка с документами:").grid(row=0, column=0, sticky="w", pady=4)
        self.input_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="Выбрать...", command=self._pick_input).grid(row=0, column=2)

        # Stamps folder
        ttk.Label(form, text="Папка со штампами:").grid(row=1, column=0, sticky="w", pady=4)
        self.stamps_var = tk.StringVar(value=str(BASE_DIR / "stamps"))
        ttk.Entry(form, textvariable=self.stamps_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="Выбрать...", command=self._pick_stamps).grid(row=1, column=2)

        # Output report
        ttk.Label(form, text="Сохранить отчёт в:").grid(row=2, column=0, sticky="w", pady=4)
        self.output_var = tk.StringVar(value=str(BASE_DIR / "stamp_report.xlsx"))
        ttk.Entry(form, textvariable=self.output_var).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="Выбрать...", command=self._pick_output).grid(row=2, column=2)

        form.columnconfigure(1, weight=1)

        # Advanced (collapsed-ish)
        adv = ttk.LabelFrame(self.root, text="Параметры (по умолчанию подходят)", padding=10)
        adv.pack(fill="x", **pad)

        ttk.Label(adv, text="Точность совпадения:").grid(row=0, column=0, sticky="w")
        self.threshold_var = tk.DoubleVar(value=0.80)
        ttk.Scale(adv, from_=0.5, to=0.95, variable=self.threshold_var,
                  orient="horizontal", length=200,
                  command=lambda v: self.threshold_label.config(text=f"{float(v):.2f}")
                  ).grid(row=0, column=1, sticky="w", padx=8)
        self.threshold_label = ttk.Label(adv, text="0.80", width=6)
        self.threshold_label.grid(row=0, column=2, sticky="w")

        ttk.Label(adv, text="Параллельных процессов:").grid(row=1, column=0, sticky="w", pady=4)
        self.workers_var = tk.IntVar(value=max(1, (os.cpu_count() or 2) - 1))
        ttk.Spinbox(adv, from_=1, to=(os.cpu_count() or 16), textvariable=self.workers_var, width=6
                    ).grid(row=1, column=1, sticky="w", padx=8)

        ttk.Label(adv, text="DPI для PDF:").grid(row=2, column=0, sticky="w", pady=4)
        self.dpi_var = tk.IntVar(value=100)
        ttk.Combobox(adv, textvariable=self.dpi_var, values=[72, 100, 120, 150],
                     state="readonly", width=6).grid(row=2, column=1, sticky="w", padx=8)

        # Buttons
        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        self.start_btn = ttk.Button(btns, text="Запустить поиск", command=self._on_start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="Остановить", command=self._on_cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.open_report_btn = ttk.Button(btns, text="Открыть отчёт", command=self._open_report, state="disabled")
        self.open_report_btn.pack(side="left", padx=8)

        # Progress
        prog_frame = ttk.LabelFrame(self.root, text="Прогресс", padding=10)
        prog_frame.pack(fill="both", expand=True, **pad)

        self.progress_bar = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress_bar.pack(fill="x", pady=4)

        self.status_var = tk.StringVar(value="Готов к запуску")
        ttk.Label(prog_frame, textvariable=self.status_var).pack(anchor="w", pady=2)

        ttk.Label(prog_frame, text="Найденные файлы со штампами:").pack(anchor="w", pady=(8, 2))
        list_frame = ttk.Frame(prog_frame)
        list_frame.pack(fill="both", expand=True)
        self.results_list = tk.Listbox(list_frame, height=8)
        self.results_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.results_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.results_list.config(yscrollcommand=scrollbar.set)

    # ─────────────────────── Event handlers ───────────────────────

    def _pick_input(self) -> None:
        path = filedialog.askdirectory(title="Выберите папку с документами для сканирования")
        if path:
            self.input_var.set(path)

    def _pick_stamps(self) -> None:
        path = filedialog.askdirectory(title="Выберите папку со штампами")
        if path:
            self.stamps_var.set(path)

    def _pick_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить отчёт",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
            initialfile="stamp_report.xlsx",
        )
        if path:
            self.output_var.set(path)

    def _on_start(self) -> None:
        input_folder = self.input_var.get().strip()
        stamps_dir = self.stamps_var.get().strip()
        output = self.output_var.get().strip()

        if not input_folder or not Path(input_folder).is_dir():
            messagebox.showerror("Ошибка", "Выберите корректную папку с документами.")
            return
        if not stamps_dir or not Path(stamps_dir).is_dir():
            messagebox.showerror("Ошибка", "Выберите корректную папку со штампами.")
            return
        if not any(Path(stamps_dir).glob("*.png")) and not any(Path(stamps_dir).glob("*.jpg")) \
                and not any(Path(stamps_dir).glob("*.jpeg")):
            messagebox.showerror(
                "Ошибка",
                f"В папке штампов нет файлов .png/.jpg.\n\n{stamps_dir}",
            )
            return
        if not output:
            messagebox.showerror("Ошибка", "Укажите путь для отчёта.")
            return

        # Lock UI
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.open_report_btn.config(state="disabled")
        self.results_list.delete(0, tk.END)
        self.progress_bar.config(value=0, maximum=100)
        self.status_var.set("Подготовка...")
        self.cancel_event.clear()

        self.scan_thread = threading.Thread(
            target=self._run_scan,
            args=(input_folder, stamps_dir, output,
                  float(self.threshold_var.get()),
                  int(self.workers_var.get()),
                  int(self.dpi_var.get())),
            daemon=True,
        )
        self.scan_thread.start()

    def _on_cancel(self) -> None:
        if self.scan_thread and self.scan_thread.is_alive():
            self.cancel_event.set()
            self.status_var.set("Останавливаем...")
            self.cancel_btn.config(state="disabled")

    def _open_report(self) -> None:
        path = Path(self.output_var.get())
        if not path.exists():
            messagebox.showinfo("Отчёт", "Файл отчёта пока не создан.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {exc}")

    # ─────────────────────── Background scan ───────────────────────

    def _run_scan(self, input_folder, stamps_dir, output, threshold, workers, dpi) -> None:
        def callback(processed, total, hits, last_file):
            self.progress_queue.put(("progress", processed, total, hits, last_file))

        try:
            scan_folder(
                root_folder=input_folder,
                stamps_dir=stamps_dir,
                output_path=output,
                threshold=threshold,
                workers=workers,
                pdf_dpi=dpi,
                resume=True,
                log_path=str(BASE_DIR / "scan.log"),
                progress_callback=callback,
                cancel_event=self.cancel_event,
            )
            self.progress_queue.put(("done", output))
        except Exception as exc:
            self.progress_queue.put(("error", str(exc)))

    def _poll_progress(self) -> None:
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, processed, total, hits, last_file = msg
                    if total > 0:
                        self.progress_bar.config(maximum=total, value=processed)
                        pct = (processed / total) * 100
                        self.status_var.set(
                            f"Обработано {processed:,} из {total:,} ({pct:.1f}%)  |  Найдено: {hits}"
                        )
                    if last_file and last_file not in ("Starting...", "Nothing to process"):
                        # Only add unique files (one row per file regardless of detection count)
                        pass
                elif kind == "hit":
                    _, file_name = msg
                    self.results_list.insert(tk.END, file_name)
                    self.results_list.see(tk.END)
                elif kind == "done":
                    _, output = msg
                    self.status_var.set(f"Готово. Отчёт: {output}")
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.open_report_btn.config(state="normal")
                    messagebox.showinfo("Готово", f"Сканирование завершено.\n\nОтчёт сохранён:\n{output}")
                elif kind == "error":
                    _, err = msg
                    self.status_var.set("Ошибка")
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    messagebox.showerror("Ошибка", err)
        except queue.Empty:
            pass
        finally:
            self.root.after(150, self._poll_progress)


def main() -> None:
    root = tk.Tk()
    try:
        # Modern theme on Windows
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    app = StampDetectorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
