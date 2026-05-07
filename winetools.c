/*
 * winetools.exe — Wine window automation tool (replaces AutoIt bridge)
 * Compile: i686-w64-mingw32-gcc -O2 -o winetools.exe winetools.c -luser32
 *
 * Commands:
 *   winetools windows              — list all visible windows as JSON
 *   winetools children <hwnd>      — list child HWNDs
 *   winetools title <hwnd>         — get window title
 *   winetools pos <hwnd>           — get window position {x,y,w,h}
 *   winetools type <hwnd> <text>   — SetForegroundWindow + SendInput text
 *   winetools key <hwnd> <vk>      — send virtual key (decimal)
 *   winetools tab <hwnd>           — send Tab
 *   winetools enter <hwnd>         — send Enter
 *   winetools clear <hwnd>         — End + 20x Backspace
 *   winetools seq <hwnd> <actions> — multiple actions in one invocation
 *     Actions: t=tab, e=enter, c=clear, k<vk>=key, s<text>=type
 *     Example: winetools seq 12345 c s1 t s1 e
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static void send_vk(WORD vk) {
    INPUT inp[2] = {0};
    inp[0].type = INPUT_KEYBOARD;
    inp[0].ki.wVk = vk;
    inp[0].ki.wScan = MapVirtualKey(vk, MAPVK_VK_TO_VSC);
    inp[1] = inp[0];
    inp[1].ki.dwFlags = KEYEVENTF_KEYUP;
    SendInput(2, inp, sizeof(INPUT));
    Sleep(30);
}

static void send_char(WCHAR ch) {
    INPUT inp[2] = {0};
    inp[0].type = INPUT_KEYBOARD;
    inp[0].ki.wScan = ch;
    inp[0].ki.dwFlags = KEYEVENTF_UNICODE;
    inp[1] = inp[0];
    inp[1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
    SendInput(2, inp, sizeof(INPUT));
    Sleep(15);
}

static void focus_window(HWND hwnd) {
    SetForegroundWindow(hwnd);
    Sleep(100);
}

static BOOL CALLBACK enum_windows_cb(HWND hwnd, LPARAM lParam) {
    if (!IsWindowVisible(hwnd)) return TRUE;
    char title[256];
    GetWindowTextA(hwnd, title, sizeof(title));
    if (title[0] == '\0') return TRUE;
    int *count = (int*)lParam;
    if (*count > 0) printf(",");
    printf("{\"title\":\"");
    for (char *p = title; *p; p++) {
        if (*p == '"') printf("\\\"");
        else if (*p == '\\') printf("\\\\");
        else putchar(*p);
    }
    printf("\",\"hwnd\":%lu}", (unsigned long)(ULONG_PTR)hwnd);
    (*count)++;
    return TRUE;
}

static BOOL CALLBACK enum_children_cb(HWND hwnd, LPARAM lParam) {
    int *count = (int*)lParam;
    if (*count > 0) printf(",");
    char cls[128] = {0};
    GetClassNameA(hwnd, cls, sizeof(cls));
    printf("{\"hwnd\":%lu,\"class\":\"%s\"}", (unsigned long)(ULONG_PTR)hwnd, cls);
    (*count)++;
    return TRUE;
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "usage: winetools <command> [args...]\n");
        return 1;
    }
    const char *cmd = argv[1];

    if (strcmp(cmd, "windows") == 0) {
        int count = 0;
        printf("{\"windows\":[");
        EnumWindows(enum_windows_cb, (LPARAM)&count);
        printf("]}\n");
    } else if (strcmp(cmd, "children") == 0 && argc >= 3) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        int count = 0;
        printf("{\"children\":[");
        EnumChildWindows(hwnd, enum_children_cb, (LPARAM)&count);
        printf("]}\n");
    } else if (strcmp(cmd, "title") == 0 && argc >= 3) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        char title[512];
        GetWindowTextA(hwnd, title, sizeof(title));
        printf("{\"title\":\"%s\"}\n", title);
    } else if (strcmp(cmd, "pos") == 0 && argc >= 3) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        RECT r;
        GetWindowRect(hwnd, &r);
        printf("{\"x\":%ld,\"y\":%ld,\"w\":%ld,\"h\":%ld}\n", r.left, r.top, r.right-r.left, r.bottom-r.top);
    } else if (strcmp(cmd, "type") == 0 && argc >= 4) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        focus_window(hwnd);
        int len = MultiByteToWideChar(CP_UTF8, 0, argv[3], -1, NULL, 0);
        WCHAR *wstr = (WCHAR*)malloc(len * sizeof(WCHAR));
        MultiByteToWideChar(CP_UTF8, 0, argv[3], -1, wstr, len);
        for (int i = 0; wstr[i]; i++) send_char(wstr[i]);
        free(wstr);
        printf("{\"ok\":true}\n");
    } else if (strcmp(cmd, "key") == 0 && argc >= 4) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        focus_window(hwnd);
        send_vk((WORD)atoi(argv[3]));
        printf("{\"ok\":true}\n");
    } else if (strcmp(cmd, "tab") == 0 && argc >= 3) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        focus_window(hwnd);
        send_vk(VK_TAB);
        printf("{\"ok\":true}\n");
    } else if (strcmp(cmd, "enter") == 0 && argc >= 3) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        focus_window(hwnd);
        send_vk(VK_RETURN);
        printf("{\"ok\":true}\n");
    } else if (strcmp(cmd, "clear") == 0 && argc >= 3) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        focus_window(hwnd);
        send_vk(VK_END);
        for (int i = 0; i < 20; i++) send_vk(VK_BACK);
        printf("{\"ok\":true}\n");
    } else if (strcmp(cmd, "seq") == 0 && argc >= 3) {
        HWND hwnd = (HWND)(ULONG_PTR)atol(argv[2]);
        focus_window(hwnd);
        Sleep(300);
        for (int i = 3; i < argc; i++) {
            char *a = argv[i];
            if (a[0] == 't') { send_vk(VK_TAB); }
            else if (a[0] == 'e') { send_vk(VK_RETURN); }
            else if (a[0] == 'c') { send_vk(VK_END); for(int j=0;j<20;j++) send_vk(VK_BACK); }
            else if (a[0] == 'k' && a[1]) { send_vk((WORD)atoi(a+1)); }
            else if (a[0] == 's' && a[1]) {
                char *text = a + 1;
                int len = MultiByteToWideChar(CP_UTF8, 0, text, -1, NULL, 0);
                WCHAR *wstr = (WCHAR*)malloc(len * sizeof(WCHAR));
                MultiByteToWideChar(CP_UTF8, 0, text, -1, wstr, len);
                for (int j = 0; wstr[j]; j++) send_char(wstr[j]);
                free(wstr);
            }
            Sleep(200);
        }
        printf("{\"ok\":true}\n");
    } else {
        fprintf(stderr, "unknown command: %s\n", cmd);
        return 1;
    }
    return 0;
}
