"""VideoSorter by Jair Lima — move vídeos de Pictures para Videos preservando metadados."""

import os
import sys
import shutil
import logging
import argparse
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

SRC      = Path.home() / "Pictures"
DST      = Path.home() / "Videos"
LOG_FILE = Path(__file__).parent / "logs" / "videosorter.log"

VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv",
    ".m4v", ".mts", ".m2ts", ".3gp", ".flv", ".webm", ".ts",
}

# ---------------------------------------------------------------------------
# Logging com rotação (5 arquivos × 1 MB)
# ---------------------------------------------------------------------------

def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=1 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler(
        stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    )
    sh.setFormatter(fmt)
    root.addHandler(sh)


# ---------------------------------------------------------------------------
# Notificação nativa do Windows (sem dependências externas)
# ---------------------------------------------------------------------------

def notify(title: str, message: str):
    """Exibe balão de notificação na bandeja do sistema via PowerShell."""
    safe_title = title.replace('"', "'")
    safe_msg   = message.replace('"', "'")
    ps = (
        'Add-Type -AssemblyName System.Windows.Forms; '
        '$n = New-Object System.Windows.Forms.NotifyIcon; '
        '$n.Icon = [System.Drawing.SystemIcons]::Information; '
        '$n.Visible = $true; '
        f'$n.ShowBalloonTip(7000, "{safe_title}", "{safe_msg}", '
        '[System.Windows.Forms.ToolTipIcon]::Info); '
        'Start-Sleep -Seconds 8; '
        '$n.Dispose()'
    )
    subprocess.Popen(
        ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Lógica de movimentação
# ---------------------------------------------------------------------------

def scan_videos() -> list[Path]:
    found = []
    for root, _, files in os.walk(SRC):
        for fname in files:
            if Path(fname).suffix.lower() in VIDEO_EXTS:
                found.append(Path(root) / fname)
    return found


def resolve_conflict(dest_path: Path) -> Path:
    if not dest_path.exists():
        return dest_path
    stem, suffix, parent = dest_path.stem, dest_path.suffix, dest_path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def move_video(src_path: Path) -> tuple[bool, str]:
    try:
        rel       = src_path.relative_to(SRC)
        dest_path = resolve_conflict(DST / rel)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest_path))
        msg = f"Movido: {rel}  ->  {dest_path.relative_to(DST)}"
        logging.info(msg)
        return True, msg
    except Exception as exc:
        msg = f"ERRO ao mover {src_path.name}: {exc}"
        logging.error(msg)
        return False, msg


def run_sort(
    msg_callback=None,
    progress_callback=None,
) -> tuple[int, int]:
    """
    Executa movimentação completa.
    msg_callback(str)        — chamado para cada linha de log
    progress_callback(i, n)  — chamado com (atual, total) a cada arquivo
    """
    videos = scan_videos()
    total  = len(videos)

    if progress_callback:
        progress_callback(0, total)

    if not videos:
        msg = "Nenhum video encontrado em Pictures."
        logging.info(msg)
        if msg_callback:
            msg_callback(msg)
        return 0, 0

    ok_count = err_count = 0
    for i, v in enumerate(videos, 1):
        success, msg = move_video(v)
        if success:
            ok_count += 1
        else:
            err_count += 1
        if msg_callback:
            msg_callback(msg)
        if progress_callback:
            progress_callback(i, total)

    summary = f"Concluido: {ok_count} movido(s), {err_count} erro(s)."
    logging.info(summary)
    if msg_callback:
        msg_callback(summary)
    return ok_count, err_count


# ---------------------------------------------------------------------------
# Agendamento via Task Scheduler
# ---------------------------------------------------------------------------

def schedule_weekly(script_path: Path) -> tuple[bool, str]:
    """Registra tarefa semanal (toda terca as 00:00) no Task Scheduler."""
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = sys.executable

    cmd = [
        "schtasks", "/create",
        "/tn", "VideoSorter",
        "/tr", f'"{pythonw}" "{script_path}" --silent',
        "/sc", "WEEKLY",
        "/d",  "TUE",
        "/st", "00:00",
        "/f",
        "/rl", "HIGHEST",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, "Tarefa 'VideoSorter' criada: toda terca-feira as 00:00."
    return False, f"Falha ao criar tarefa: {result.stderr.strip()}"


# ---------------------------------------------------------------------------
# Interface gráfica
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VideoSorter by Jair Lima")
        self.resizable(False, False)
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 4}

        # Cabeçalho
        tk.Label(
            self, text="VideoSorter by Jair Lima", font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 2), sticky="w")

        tk.Label(self, text=f"Origem : {SRC}", font=("Segoe UI", 9)).grid(
            row=1, column=0, columnspan=3, padx=12, sticky="w"
        )
        tk.Label(self, text=f"Destino: {DST}", font=("Segoe UI", 9)).grid(
            row=2, column=0, columnspan=3, padx=12, sticky="w"
        )

        # Botões
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=8, padx=12, sticky="w")

        self.btn_scan = tk.Button(
            btn_frame, text="Verificar agora", width=18, command=self._on_scan
        )
        self.btn_scan.pack(side="left", padx=(0, 6))

        self.btn_run = tk.Button(
            btn_frame, text="Executar agora", width=18, command=self._on_run
        )
        self.btn_run.pack(side="left", padx=(0, 6))

        self.btn_sched = tk.Button(
            btn_frame, text="Agendar semanalmente", width=22, command=self._on_schedule,
        )
        self.btn_sched.pack(side="left")

        # Barra de progresso
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self, variable=self.progress_var, maximum=100, length=560, mode="determinate"
        )
        self.progress_bar.grid(row=4, column=0, columnspan=3, padx=12, pady=(0, 2), sticky="ew")

        self.progress_label = tk.StringVar(value="")
        tk.Label(self, textvariable=self.progress_label, font=("Segoe UI", 8), fg="#555").grid(
            row=5, column=0, columnspan=3, padx=12, sticky="w"
        )

        # Log
        tk.Label(self, text="Log:", font=("Segoe UI", 9, "bold")).grid(
            row=6, column=0, padx=12, pady=(6, 0), sticky="w"
        )
        self.log_box = tk.Text(
            self, width=72, height=12, state="disabled",
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
            relief="flat", bd=0,
        )
        self.log_box.grid(row=7, column=0, columnspan=2, padx=12, pady=(0, 4))

        sb = ttk.Scrollbar(self, command=self.log_box.yview)
        sb.grid(row=7, column=2, sticky="ns", padx=(0, 8), pady=(0, 4))
        self.log_box.config(yscrollcommand=sb.set)

        # Status inferior
        self.status_var = tk.StringVar(value="Pronto.")
        tk.Label(self, textvariable=self.status_var, font=("Segoe UI", 8), fg="gray").grid(
            row=8, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="w"
        )

    # -- helpers --

    def _log(self, msg: str):
        self.log_box.config(state="normal")
        self.log_box.insert("end", f"{datetime.now():%H:%M:%S}  {msg}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def _set_progress(self, current: int, total: int):
        if total == 0:
            self.progress_var.set(0)
            self.progress_label.set("")
            return
        pct = (current / total) * 100
        self.progress_var.set(pct)
        self.progress_label.set(f"{current} / {total} arquivos  ({pct:.0f}%)")

    def _set_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_scan.config(state=state)
        self.btn_run.config(state=state)
        self.btn_sched.config(state=state)

    def _refresh_status(self):
        if LOG_FILE.exists():
            mtime = datetime.fromtimestamp(LOG_FILE.stat().st_mtime)
            self.status_var.set(f"Ultima execucao registrada: {mtime:%Y-%m-%d %H:%M}")
        else:
            self.status_var.set("Nenhuma execucao registrada ainda.")

    # -- eventos --

    def _on_scan(self):
        self._set_buttons(False)
        self._log("Escaneando Pictures...")
        self._set_progress(0, 0)

        def task():
            videos = scan_videos()
            if videos:
                self._log(f"{len(videos)} video(s) encontrado(s):")
                for v in videos:
                    self._log(f"  {v.relative_to(SRC)}")
            else:
                self._log("Nenhum video encontrado.")
            self._set_buttons(True)

        threading.Thread(target=task, daemon=True).start()

    def _on_run(self):
        if not messagebox.askyesno(
            "Confirmar", "Mover todos os videos de Pictures para Videos agora?"
        ):
            return
        self._set_buttons(False)
        self._set_progress(0, 0)
        self._log("Iniciando movimentacao...")

        def task():
            def on_progress(i, n):
                self._set_progress(i, n)

            ok, err = run_sort(msg_callback=self._log, progress_callback=on_progress)
            self._refresh_status()
            self._set_buttons(True)
            if ok > 0:
                notify("VideoSorter", f"{ok} video(s) movido(s) com sucesso.")

        threading.Thread(target=task, daemon=True).start()

    def _on_schedule(self):
        ok, msg = schedule_weekly(Path(__file__).resolve())
        self._log(msg)
        if ok:
            messagebox.showinfo("Agendamento", msg)
        else:
            messagebox.showerror("Erro", msg)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent", action="store_true", help="Executa sem GUI (Task Scheduler)")
    args = parser.parse_args()

    setup_logging()

    if args.silent:
        logging.info("=== Execucao automatica (Task Scheduler) ===")
        ok, err = run_sort()
        if ok > 0 or err > 0:
            notify("VideoSorter", f"{ok} video(s) movido(s), {err} erro(s).")
    else:
        app = App()
        app.mainloop()


if __name__ == "__main__":
    main()
