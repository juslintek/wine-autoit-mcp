#include <ScreenCapture.au3>
#include <Array.au3>

; Wine AutoIt Bridge - 20ms polling
; NOTE: WinActivate crashes Wine when targeting cross-process windows.
; All input uses PostMessage WM_CHAR/WM_KEYDOWN directly — no activation needed.
; Run inside a named virtual desktop for screenshot to work:
;   wine explorer /desktop=gotas,1024x768 AutoIt3.exe bridge.au3

Global $g_sBridgeDir = "C:\AutoIt3\bridge\"
Global $g_sCmdFile = $g_sBridgeDir & "command.json"
Global $g_sResultFile = $g_sBridgeDir & "result.json"
Global $g_sScreenDir = $g_sBridgeDir & "screenshots\"

DirCreate($g_sBridgeDir)
DirCreate($g_sScreenDir)
FileWrite($g_sBridgeDir & "status.txt", "ready")

While 1
    If FileExists($g_sCmdFile) Then
        Local $sCmd = FileRead($g_sCmdFile)
        FileDelete($g_sCmdFile)
        If $sCmd <> "" Then
            FileWrite($g_sResultFile, ExecuteCommand($sCmd))
        EndIf
    EndIf
    Sleep(20)
WEnd

Func ExecuteCommand($sJson)
    Local $aParts = StringSplit($sJson, "|")
    If $aParts[0] < 1 Then Return '{"error":"empty command"}'
    Local $sAction = $aParts[1]

    Switch $sAction
        Case "screenshot"
            Local $sFile = $g_sScreenDir & "cap_" & @HOUR & @MIN & @SEC & @MSEC & ".png"
            _ScreenCapture_Capture($sFile)
            Return '{"ok":true,"file":"' & $sFile & '"}'

        Case "windows"
            Local $aList = WinList()
            Local $sResult = '{"windows":['
            Local $nCount = 0
            For $i = 1 To $aList[0][0]
                If $aList[$i][0] <> "" And BitAND(WinGetState($aList[$i][1]), 2) Then
                    If $nCount > 0 Then $sResult &= ","
                    $sResult &= '{"title":"' & StringReplace($aList[$i][0], '"', '\"') & '","hwnd":' & Dec(Hex($aList[$i][1])) & '}'
                    $nCount += 1
                EndIf
            Next
            Return $sResult & ']}'

        Case "wintitle"
            If $aParts[0] >= 2 Then
                Return '{"title":"' & StringReplace(WinGetTitle(HWnd($aParts[2])), '"', '\"') & '"}'
            EndIf
            Return '{"error":"need hwnd"}'

        Case "children"
            If $aParts[0] >= 2 Then
                Local $hParent = HWnd($aParts[2])
                Local $aResult[0]
                Local $hChild = _GetWindow($hParent, 5)
                While $hChild <> 0
                    _ArrayAdd($aResult, $hChild)
                    $hChild = _GetWindow($hChild, 2)
                WEnd
                Local $sResult = '{"children":['
                For $i = 0 To UBound($aResult) - 1
                    If $i > 0 Then $sResult &= ","
                    Local $sClass = _GetClassName($aResult[$i])
                    $sResult &= '{"hwnd":' & Dec(Hex($aResult[$i])) & ',"class":"' & $sClass & '","title":"' & StringReplace(WinGetTitle($aResult[$i]), '"', '\"') & '"}'
                Next
                Return $sResult & ']}'
            EndIf
            Return '{"error":"need hwnd"}'

        Case "login"
            ; Posts WM_CHAR directly to child textbox HWNDs — no WinActivate, no mouse
            If $aParts[0] >= 4 Then
                Local $hWnd = HWnd($aParts[2])
                Local $sUser = $aParts[3]
                Local $sPass = $aParts[4]
                Local $aChildren[0]
                Local $hChild = _GetWindow($hWnd, 5)
                While $hChild <> 0
                    _ArrayAdd($aChildren, $hChild)
                    $hChild = _GetWindow($hChild, 2)
                WEnd
                If UBound($aChildren) < 2 Then
                    Return '{"error":"expected 2+ child windows, got ' & UBound($aChildren) & '"}'
                EndIf
                _PostClear($aChildren[0])
                _PostChars($aChildren[0], $sUser)
                Sleep(50)
                _PostClear($aChildren[1])
                _PostChars($aChildren[1], $sPass)
                Sleep(50)
                DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0100, "wparam", 0x0D, "lparam", 0)
                DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0101, "wparam", 0x0D, "lparam", 0)
                Return '{"ok":true,"children":' & UBound($aChildren) & '}'
            EndIf
            Return '{"error":"need hwnd, userid, password"}'

        Case "postchar"
            If $aParts[0] >= 3 Then
                DllCall("user32.dll", "bool", "PostMessage", "handle", HWnd($aParts[2]), "uint", 0x0102, "wparam", Asc($aParts[3]), "lparam", 1)
                Return '{"ok":true}'
            EndIf
            Return '{"error":"need hwnd and char"}'

        Case "postkey"
            If $aParts[0] >= 3 Then
                Local $hWnd = HWnd($aParts[2])
                Local $nVK = Int($aParts[3])
                DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0100, "wparam", $nVK, "lparam", 0)
                DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0101, "wparam", $nVK, "lparam", 0)
                Return '{"ok":true}'
            EndIf
            Return '{"error":"need hwnd and vkcode"}'

        Case "winpos"
            If $aParts[0] >= 2 Then
                Local $aPos = WinGetPos(HWnd($aParts[2]))
                If IsArray($aPos) Then
                    Return '{"x":' & $aPos[0] & ',"y":' & $aPos[1] & ',"w":' & $aPos[2] & ',"h":' & $aPos[3] & '}'
                EndIf
                Return '{"error":"window not found"}'
            EndIf
            Return '{"error":"need hwnd"}'

        Case "click"
            If $aParts[0] >= 2 Then
                If $aParts[0] >= 3 Then
                    ControlClick(HWnd($aParts[2]), "", $aParts[3])
                Else
                    MouseClick("left")
                EndIf
            EndIf
            Return '{"ok":true}'

        Case "clickpos"
            If $aParts[0] >= 3 Then
                MouseClick("left", Int($aParts[2]), Int($aParts[3]))
                Return '{"ok":true}'
            EndIf
            Return '{"error":"need x y"}'

        Case "gettext"
            If $aParts[0] >= 3 Then
                Return '{"text":"' & StringReplace(ControlGetText(HWnd($aParts[2]), "", $aParts[3]), '"', '\"') & '"}'
            EndIf
            Return '{"error":"need hwnd and control"}'

        Case "settext"
            If $aParts[0] >= 4 Then
                ControlSetText(HWnd($aParts[2]), "", $aParts[3], $aParts[4])
                Return '{"ok":true}'
            EndIf
            Return '{"error":"need hwnd, control, text"}'

        Case "tree"
            If $aParts[0] >= 2 Then
                Local $hWnd = HWnd($aParts[2])
                Local $aControls = _WinGetControls($hWnd)
                Local $sResult = '{"title":"' & StringReplace(WinGetTitle($hWnd), '"', '\"') & '","controls":['
                If IsArray($aControls) Then
                    For $i = 0 To UBound($aControls) - 1
                        If $i > 0 Then $sResult &= ","
                        $sResult &= '{"id":"' & $aControls[$i] & '","text":"' & StringReplace(StringLeft(ControlGetText($hWnd, "", $aControls[$i]), 50), '"', '\"') & '"}'
                    Next
                EndIf
                Return $sResult & ']}'
            EndIf
            Return '{"error":"need hwnd"}'

        Case "key"
            If $aParts[0] >= 2 Then
                Send($aParts[2])
                Return '{"ok":true}'
            EndIf
            Return '{"error":"need key"}'

        Case "quit"
            FileWrite($g_sBridgeDir & "status.txt", "stopped")
            Exit

        Case Else
            Return '{"error":"unknown command: ' & $sAction & '"}'
    EndSwitch
EndFunc

Func _PostChars($hWnd, $sText)
    For $i = 1 To StringLen($sText)
        DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0102, "wparam", Asc(StringMid($sText, $i, 1)), "lparam", 1)
        Sleep(5)
    Next
EndFunc

Func _PostClear($hWnd)
    DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0100, "wparam", 0x23, "lparam", 0)
    DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0101, "wparam", 0x23, "lparam", 0)
    Sleep(20)
    For $i = 1 To 20
        DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0100, "wparam", 0x08, "lparam", 0)
        DllCall("user32.dll", "bool", "PostMessage", "handle", $hWnd, "uint", 0x0101, "wparam", 0x08, "lparam", 0)
        Sleep(5)
    Next
EndFunc

Func _GetWindow($hWnd, $nCmd)
    Local $aRet = DllCall("user32.dll", "handle", "GetWindow", "handle", $hWnd, "uint", $nCmd)
    If @error Or Not IsArray($aRet) Then Return 0
    Return $aRet[0]
EndFunc

Func _GetClassName($hWnd)
    Local $sClass = ""
    DllCall("user32.dll", "int", "GetClassNameW", "handle", $hWnd, "wstr", $sClass, "int", 256)
    Return $sClass
EndFunc

Func _WinGetControls($hWnd)
    Local $aClasses = StringSplit(WinGetClassList($hWnd), @LF)
    Local $aResult[0]
    Local $aCount[]
    For $i = 1 To $aClasses[0]
        Local $sClass = StringStripWS($aClasses[$i], 3)
        If $sClass = "" Then ContinueLoop
        If Not MapExists($aCount, $sClass) Then
            $aCount[$sClass] = 1
        Else
            $aCount[$sClass] += 1
        EndIf
        _ArrayAdd($aResult, "[CLASS:" & $sClass & "; INSTANCE:" & $aCount[$sClass] & "]")
    Next
    Return $aResult
EndFunc
