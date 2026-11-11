import argparse
import sys
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

def print_progress(msg: str) -> None:
    print(f"[*] {msg}")

def main() -> int:
    parser = argparse.ArgumentParser(
        description="כספת פרופיל כרום ניידת (Chrome Profile Portable Vault) - גיבוי ושחזור מוצפן"
    )
    subparsers = parser.add_subparsers(dest="command", help="פקודות זמינות")

    # Command: export
    p_export = subparsers.add_parser("export", help="שמירת פרופיל מהמחשב אל תוך קובץ היישום המוצפן")
    p_export.add_argument("-p", "--password", required=True, help="קוד גישה / סיסמה להצפנה")
    p_export.add_argument("--profile", default="Default", help="שם הפרופיל (ברירת מחדל: Default)")
    p_export.add_argument("--vault", default=None, help="נתיב קובץ הכספת (ברירת מחדל: בתיקיית היישום)")
    p_export.add_argument("--force", action="store_true", help="המשך גם אם כרום פתוח")

    # Command: restore
    p_restore = subparsers.add_parser("restore", help="שחזור פרופיל מקובץ היישום המוצפן אל המחשב")
    p_restore.add_argument("-p", "--password", required=True, help="קוד גישה / סיסמה לפענוח")
    p_restore.add_argument("--vault", default=None, help="נתיב קובץ הכספת (ברירת מחדל: בתיקיית היישום)")
    p_restore.add_argument("--force", action="store_true", help="המשך גם אם כרום פתוח")

    # Command: wipe
    p_wipe = subparsers.add_parser("wipe", help="מחיקת נתוני הפרופיל מהמחשב המארח (ניקוי עקבות במחשב ציבורי)")
    p_wipe.add_argument("--profile", default="Default", help="שם הפרופיל למחיקה")
    p_wipe.add_argument("--all", action="store_true", help="מחיקת כל תיקיית כרום מהמחשב")

    # Command: list
    subparsers.add_parser("list", help="הצגת הפרופילים הקיימים במחשב הנוכחי")

    # Command: info
    subparsers.add_parser("info", help="הצגת סטטוס ונתיבים של היישום")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    vault_file = Path(args.vault) if hasattr(args, "vault") and args.vault else get_default_vault_file()

    if args.command == "info":
        print(f"נתיב נתוני כרום במחשב: {get_chrome_user_data_dir()}")
        print(f"קובץ הכספת הנייד: {vault_file}")
        print(f"האם קיים קובץ כספת: {'כן' if vault_file.exists() else 'לא'}")
        print(f"האם כרום פועל כרגע: {'כן' if is_chrome_running() else 'לא'}")
        return 0

    if args.command == "list":
        profiles = list_available_profiles()
        if not profiles:
            print("לא נמצאו פרופילים של גוגל כרום במחשב זה.")
        else:
            print("פרופילים שנמצאו:")
            for p in profiles:
                print(f" - [{p['id']}] {p['name']}")
        return 0

    if args.command == "export":
        if is_chrome_running() and not args.force:
            print("אזהרה: גוגל כרום פועל כעת! מומלץ לסגור אותו לפני הגיבוי כדי לוודא שכל הקבצים נשמרים.")
            print("להמשך בכל זאת השתמש בדגל --force")
            return 1
        try:
            target = export_profile_to_vault(
                password=args.password,
                vault_path=vault_file,
                profile_id=args.profile,
                progress_callback=print_progress
            )
            print(f"\n[V] הפרופיל נשמר בהצלחה אל תוך קובץ היישום המוצפן: {target}")
            return 0
        except Exception as e:
            print(f"\n[X] שגיאה בגיבוי הפרופיל: {e}")
            return 1

    if args.command == "restore":
        if is_chrome_running() and not args.force:
            print("אזהרה: גוגל כרום פועל כעת! חובה לסגור את כרום לפני שחזור הפרופיל.")
            print("להמשך בכל זאת השתמש בדגל --force")
            return 1
        try:
            restore_profile_from_vault(
                password=args.password,
                vault_path=vault_file,
                progress_callback=print_progress
            )
            print("\n[V] הפרופיל שוחזר בהצלחה למחשב! כעת תוכל לפתוח את כרום ולהשתמש בו.")
            return 0
        except CryptoError as e:
            print(f"\n[X] שגיאת הצפנה: {e}")
            return 1
        except Exception as e:
            print(f"\n[X] שגיאה בשחזור הפרופיל: {e}")
            return 1

    if args.command == "wipe":
        if is_chrome_running():
            print("אזהרה: כרום פועל. יש לסגור את כרום לפני ניקוי הנתונים מהמחשב.")
            return 1
        try:
            wipe_profile_from_host(
                profile_id=args.profile,
                wipe_all=args.all,
                progress_callback=print_progress
            )
            print("\n[V] הניקוי מהמחשב הושלם בהצלחה. לא נותרו עקבות של הפרופיל במחשב המארח.")
            return 0
        except Exception as e:
            print(f"\n[X] שגיאה במחיקת הנתונים: {e}")
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
