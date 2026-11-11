import sys

def main():
    if len(sys.argv) > 1:
        # Arguments provided: run CLI
        from chrome_vault.cli import main as cli_main
        sys.exit(cli_main())
    else:
        # No arguments: launch GUI
        try:
            from chrome_vault.gui import main as gui_main
            gui_main()
        except Exception as e:
            print(f"לא ניתן להפעיל ממשק גרפי (GUI): {e}")
            print("מפעיל ממשק שורת פקודה (CLI) במקום:")
            from chrome_vault.cli import main as cli_main
            sys.exit(cli_main())

if __name__ == "__main__":
    main()
