import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from chrome_vault.manager import (
    export_profile_to_vault,
    restore_profile_from_vault,
    wipe_profile_from_host,
    list_available_profiles,
    is_chrome_running,
)
from chrome_vault.paths import get_default_vault_file, get_chrome_user_data_dir
from chrome_vault.crypto import CryptoError


class ChromeVaultApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chrome Profile Portable Vault - כספת פרופיל כרום ניידת")
        self.geometry("640x560")
        self.minsize(580, 500)

        self.vault_file = get_default_vault_file()

        # Setup GUI layout
        self._setup_style()
        self._build_widgets()
        self._refresh_status()

    def _setup_style(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

    def _build_widgets(self):
        # Header Frame
        header_frame = ttk.Frame(self, padding=12)
        header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(
            header_frame,
            text="כספת פרופיל כרום ניידת (Portable Chrome Vault)",
            font=("Arial", 14, "bold"),
            anchor="center",
        )
        title_lbl.pack(pady=4)

        subtitle_lbl = ttk.Label(
            header_frame,
            text="שמירה, שחזור ומחיקה מאובטחת של פרופיל כרום עם קוד גישה",
            font=("Arial", 10),
            anchor="center",
        )
        subtitle_lbl.pack()

        # Status & Path Information Frame
        info_frame = ttk.LabelFrame(self, text=" פרטי אחסון וסטטוס (Status & Paths) ", padding=10)
        info_frame.pack(fill=tk.X, padx=12, pady=6)

        self.lbl_vault_status = ttk.Label(info_frame, text="", font=("Arial", 9, "bold"))
        self.lbl_vault_status.pack(anchor="w", pady=2)

        self.lbl_chrome_path = ttk.Label(
            info_frame,
            text=f"נתיב כרום במחשב: {get_chrome_user_data_dir()}",
            font=("Arial", 8),
            wraplength=580,
        )
        self.lbl_chrome_path.pack(anchor="w", pady=2)

        # Credentials & Profile Selection Frame
        cred_frame = ttk.LabelFrame(self, text=" הגדרות וקוד גישה (Passcode & Selection) ", padding=10)
        cred_frame.pack(fill=tk.X, padx=12, pady=6)

        # Profile selection row
        prof_row = ttk.Frame(cred_frame)
        prof_row.pack(fill=tk.X, pady=4)

        ttk.Label(prof_row, text="בחר פרופיל לשמירה:").pack(side=tk.LEFT, padx=4)
        self.profile_var = tk.StringVar(value="Default")
        self.profile_combo = ttk.Combobox(prof_row, textvariable=self.profile_var, width=28)
        self.profile_combo.pack(side=tk.LEFT, padx=4)
        btn_refresh = ttk.Button(prof_row, text="רענן רשימה", command=self._refresh_profiles)
        btn_refresh.pack(side=tk.LEFT, padx=4)

        # Passcode row
        pass_row = ttk.Frame(cred_frame)
        pass_row.pack(fill=tk.X, pady=4)

        ttk.Label(pass_row, text="קוד גישה / סיסמה:").pack(side=tk.LEFT, padx=4)
        self.entry_passcode = ttk.Entry(pass_row, show="*", width=30)
        self.entry_passcode.pack(side=tk.LEFT, padx=4)

        self.show_pass_var = tk.BooleanVar(value=False)
        chk_show = ttk.Checkbutton(
            pass_row,
            text="הצג קוד",
            variable=self.show_pass_var,
            command=self._toggle_show_passcode,
        )
        chk_show.pack(side=tk.LEFT, padx=4)

        # Actions Frame
        action_frame = ttk.LabelFrame(self, text=" פעולות (Actions) ", padding=10)
        action_frame.pack(fill=tk.X, padx=12, pady=6)

        btn_grid = ttk.Frame(action_frame)
        btn_grid.pack(fill=tk.X, pady=4)

        # 1. Export button
        self.btn_export = ttk.Button(
            btn_grid,
            text="1. שמור פרופיל ליישום (גיבוי מוצפן)",
            command=self._on_export_click,
        )
        self.btn_export.grid(row=0, column=0, padx=6, pady=4, sticky="ew")

        # 2. Restore button
        self.btn_restore = ttk.Button(
            btn_grid,
            text="2. שחזר פרופיל למחשב (טעינה)",
            command=self._on_restore_click,
        )
        self.btn_restore.grid(row=0, column=1, padx=6, pady=4, sticky="ew")

        # 3. Wipe button
        self.btn_wipe = ttk.Button(
            btn_grid,
            text="3. מחק פרופיל מהמחשב (ניקוי עקבות)",
            command=self._on_wipe_click,
        )
        self.btn_wipe.grid(row=1, column=0, columnspan=2, padx=6, pady=6, sticky="ew")

        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # Progress / Log Box Frame
        log_frame = ttk.LabelFrame(self, text=" יומן פעולות (Progress Log) ", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        self.log_text = tk.Text(log_frame, height=6, wrap="word", state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _toggle_show_passcode(self):
        self.entry_passcode.config(show="" if self.show_pass_var.get() else "*")

    def log(self, message: str):
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.after(0, _append)

    def _refresh_profiles(self):
        profiles = list_available_profiles()
        ids = [p["id"] for p in profiles]
        if not ids:
            ids = ["Default"]
        self.profile_combo["values"] = ids
        if self.profile_var.get() not in ids:
            self.profile_var.set(ids[0])
        self.log(f"נמצאו {len(profiles)} פרופילים של כרום במחשב.")

    def _refresh_status(self):
        self._refresh_profiles()
        if self.vault_file.exists():
            size_mb = self.vault_file.stat().st_size / (1024 * 1024)
            self.lbl_vault_status.config(
                text=f"קובץ כספת נייד קיים ביישום ({size_mb:.2f} MB)",
                foreground="green",
            )
        else:
            self.lbl_vault_status.config(
                text="עדיין אין קובץ כספת שמור ביישום.",
                foreground="gray",
            )

    def _run_in_thread(self, target_func):
        # Disable buttons during operation
        self.btn_export.config(state="disabled")
        self.btn_restore.config(state="disabled")
        self.btn_wipe.config(state="disabled")

        def wrapper():
            try:
                target_func()
            finally:
                self.after(0, lambda: self.btn_export.config(state="normal"))
                self.after(0, lambda: self.btn_restore.config(state="normal"))
                self.after(0, lambda: self.btn_wipe.config(state="normal"))
                self.after(0, self._refresh_status)

        t = threading.Thread(target=wrapper, daemon=True)
        t.start()

    def _on_export_click(self):
        passcode = self.entry_passcode.get().strip()
        if not passcode:
            messagebox.showwarning("שגיאה", "אנא הזן קוד גישה / סיסמה להצפנה!")
            return

        if is_chrome_running():
            proceed = messagebox.askyesno(
                "אזהרה",
                "כרום פתוח כרגע במחשב. מומלץ מאוד לסגור אותו כדי שהגיבוי יכלול את כל הנתונים העדכניים.\n\nהאם להמשיך בכל זאת?",
            )
            if not proceed:
                return

        profile_id = self.profile_var.get().strip() or "Default"

        def task():
            try:
                self.log(f"מתחיל גיבוי מוצפן של פרופיל '{profile_id}'...")
                export_profile_to_vault(
                    password=passcode,
                    vault_path=self.vault_file,
                    profile_id=profile_id,
                    progress_callback=self.log,
                )
                self.after(0, lambda: messagebox.showinfo(
                    "הצלחה",
                    f"פרופיל כרום נשמר בהצלחה ובאופן מוצפן בתוך היישום!\nקובץ: {self.vault_file.name}",
                ))
            except Exception as e:
                self.log(f"שגיאה: {e}")
                self.after(0, lambda: messagebox.showerror("שגיאה", f"ארעה שגיאה בגיבוי:\n{e}"))

        self._run_in_thread(task)

    def _on_restore_click(self):
        passcode = self.entry_passcode.get().strip()
        if not passcode:
            messagebox.showwarning("שגיאה", "אנא הזן את קוד הגישה לפענוח!")
            return

        if not self.vault_file.exists():
            messagebox.showwarning("קובץ חסר", "לא נמצא קובץ נתונים מוצפן ביישום לשחזור.")
            return

        if is_chrome_running():
            messagebox.showerror("שגיאה", "יש לסגור את דפדפן כרום לפני ביצוע שחזור הפרופיל למחשב!")
            return

        def task():
            try:
                self.log("מתחיל שחזור פרופיל למחשב...")
                restore_profile_from_vault(
                    password=passcode,
                    vault_path=self.vault_file,
                    progress_callback=self.log,
                )
                self.after(0, lambda: messagebox.showinfo(
                    "הצלחה",
                    "הפרופיל שוחזר בהצלחה למחשב!\nכעת ניתן לפתוח את כרום ולהשתמש בחשבון ללא צורך בהתחברות מחדש.",
                ))
            except CryptoError as e:
                self.log(f"שגיאת אימות: {e}")
                self.after(0, lambda: messagebox.showerror("שגיאת קוד גישה", str(e)))
            except Exception as e:
                self.log(f"שגיאה: {e}")
                self.after(0, lambda: messagebox.showerror("שגיאה", f"ארעה שגיאה בשחזור:\n{e}"))

        self._run_in_thread(task)

    def _on_wipe_click(self):
        if is_chrome_running():
            messagebox.showerror("שגיאה", "יש לסגור את דפדפן כרום לפני מחיקת הפרופיל מהמחשב!")
            return

        confirm = messagebox.askyesno(
            "אישור מחיקה",
            "האם אתה בטוח שברצונך למחוק את הפרופיל מהמחשב הנוכחי?\n(הנתונים בתוך היישום המוצפן יישארו ללא פגע)",
        )
        if not confirm:
            return

        profile_id = self.profile_var.get().strip() or "Default"

        def task():
            try:
                self.log("מוחק נתוני פרופיל מהמחשב המארח...")
                wipe_profile_from_host(
                    profile_id=profile_id,
                    progress_callback=self.log,
                )
                self.after(0, lambda: messagebox.showinfo(
                    "הניקוי הושלם",
                    "נתוני הפרופיל נמחקו מהמחשב בהצלחה. לא נותרו עקבות במחשב הציבורי.",
                ))
            except Exception as e:
                self.log(f"שגיאה: {e}")
                self.after(0, lambda: messagebox.showerror("שגיאה", f"ארעה שגיאה במחיקה:\n{e}"))

        self._run_in_thread(task)


def main():
    app = ChromeVaultApp()
    app.mainloop()


if __name__ == "__main__":
    main()
