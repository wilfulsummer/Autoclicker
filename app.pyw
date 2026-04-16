import importlib.util
import sys
import tkinter as tk
import webbrowser

from runtime_paths import APP_DIR, IS_FROZEN


REQUIREMENTS_FILE = APP_DIR / "requirements.txt"

PACKAGE_LINKS = {
    "python": "https://www.python.org/downloads/",
    "pynput": "https://pypi.org/project/pynput/",
}

MODULE_NAME_MAP = {
    "pynput": "pynput",
}


def _required_packages() -> list[str]:
    if not REQUIREMENTS_FILE.exists():
        return []
    packages: list[str] = []
    for raw_line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        package = line.split("==", 1)[0].split(">=", 1)[0].split("[", 1)[0].strip()
        if package:
            packages.append(package)
    return packages


def _missing_packages() -> list[str]:
    missing: list[str] = []
    for package in _required_packages():
        module_name = MODULE_NAME_MAP.get(package, package.replace("-", "_"))
        if importlib.util.find_spec(module_name) is None:
            missing.append(package)
    return missing


def _show_missing_dependencies_window(packages: list[str]) -> None:
    root = tk.Tk()
    root.title("Missing Dependencies")
    root.geometry("540x320")
    root.minsize(500, 280)
    root.configure(background="#111111")

    shell = tk.Frame(root, background="#171717", highlightbackground="#2B2B2B", highlightcolor="#2B2B2B", highlightthickness=1)
    shell.pack(fill="both", expand=True, padx=16, pady=16)

    title = tk.Label(
        shell,
        text="AutoClicker needs a few dependencies before it can start.",
        anchor="w",
        justify="left",
        background="#171717",
        foreground="#F3F4F6",
        font=("Segoe UI Semibold", 12),
    )
    title.pack(fill="x", padx=16, pady=(16, 8))

    body = tk.Label(
        shell,
        text=(
            "Missing packages:\n- "
            + "\n- ".join(packages)
            + "\n\nInstall Python packages with:\n"
            + f'"{sys.executable}" -m pip install -r "{REQUIREMENTS_FILE}"'
        ),
        anchor="nw",
        justify="left",
        background="#171717",
        foreground="#D1D5DB",
        font=("Segoe UI", 10),
    )
    body.pack(fill="x", padx=16, pady=(0, 12))

    links_frame = tk.Frame(shell, background="#171717")
    links_frame.pack(fill="x", padx=16, pady=(0, 12))

    links_label = tk.Label(
        links_frame,
        text="Install links:",
        anchor="w",
        background="#171717",
        foreground="#9CA3AF",
        font=("Segoe UI Semibold", 10),
    )
    links_label.pack(fill="x", pady=(0, 6))

    def open_link(url: str) -> None:
        webbrowser.open(url)

    shown = set()
    for package in packages:
        url = PACKAGE_LINKS.get(package)
        if not url or url in shown:
            continue
        shown.add(url)
        btn = tk.Button(
            links_frame,
            text=f"Open {package} install page",
            command=lambda current=url: open_link(current),
            relief="flat",
            bd=0,
            cursor="hand2",
            background="#242424",
            activebackground="#2F2F2F",
            foreground="#F3F4F6",
            activeforeground="#F3F4F6",
            padx=10,
            pady=6,
        )
        btn.pack(anchor="w", pady=(0, 6))

    close_button = tk.Button(
        shell,
        text="Close",
        command=root.destroy,
        relief="flat",
        bd=0,
        cursor="hand2",
        background="#2FA247",
        activebackground="#27903D",
        foreground="#F8FAFC",
        activeforeground="#F8FAFC",
        padx=12,
        pady=7,
    )
    close_button.pack(anchor="e", padx=16, pady=(8, 16))

    root.mainloop()


def main() -> None:
    if IS_FROZEN:
        from app import main as app_main
        app_main()
        return

    missing = _missing_packages()
    if missing:
        _show_missing_dependencies_window(missing)
        return

    try:
        from app import main as app_main
    except ModuleNotFoundError as exc:
        package = exc.name or "unknown package"
        _show_missing_dependencies_window([package])
        return

    app_main()


if __name__ == "__main__":
    main()
