"""
Example: test GotasSQL login flow.

Run: python3 test_login.py
Or with pytest: pytest test_login.py -v
"""
import sys
sys.path.insert(0, ".")
from wine_test import WineApp


def test_login():
    with WineApp("dist/gotassql.exe") as app:
        # Wait for login dialog
        app.wait_for_window("Gotas SQL", timeout=20)
        app.screenshot("screenshots/01_login.png")

        # Login: tab to password, type 1, enter
        app.seq("t s1 e")

        # Wait for main window (title changes to include "Admin")
        app.wait_for_window("Admin", timeout=10)
        app.screenshot("screenshots/02_main.png")

        # Verify
        app.assert_window_title("Admin")
        print("✓ Login successful")


if __name__ == "__main__":
    test_login()
