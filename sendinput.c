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

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "usage: sendinput <hwnd> <text|--vk N|--clear|--tab|--enter>\n");
        return 1;
    }
    HWND hwnd = (HWND)(ULONG_PTR)atol(argv[1]);
    SetForegroundWindow(hwnd);
    Sleep(100);

    if (strcmp(argv[2], "--vk") == 0 && argc >= 4) {
        send_vk((WORD)atoi(argv[3]));
    } else if (strcmp(argv[2], "--clear") == 0) {
        send_vk(VK_END);
        for (int i = 0; i < 20; i++) send_vk(VK_BACK);
    } else if (strcmp(argv[2], "--tab") == 0) {
        send_vk(VK_TAB);
    } else if (strcmp(argv[2], "--enter") == 0) {
        send_vk(VK_RETURN);
    } else {
        int len = MultiByteToWideChar(CP_UTF8, 0, argv[2], -1, NULL, 0);
        WCHAR *wstr = (WCHAR*)malloc(len * sizeof(WCHAR));
        MultiByteToWideChar(CP_UTF8, 0, argv[2], -1, wstr, len);
        for (int i = 0; wstr[i]; i++) send_char(wstr[i]);
        free(wstr);
    }
    return 0;
}
