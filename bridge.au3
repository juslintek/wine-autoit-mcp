#include <ScreenCapture.au3>
#include <Array.au3>

; Wine AutoIt Bridge - polls for commands from host, executes, returns results
; Communication via files in C:\AutoIt3\bridge\

Global $g_sBridgeDir = "C:\AutoIt3\bridge\"
Global $g_sCmdFile = $g_sBridgeDir & "command.json"
Global $g_sResultFile = $g_sBridgeDir & "result.json"
Global $g_sScreenDir = $g_sBridgeDir & "screenshots\"

DirCreate($g_sBridgeDir)
DirCreate($g_sScreenDir)

; Signal ready
FileWrite($g_sBridgeDir & "status.txt", "ready")

; Main loop - poll for commands
While 1
    If FileExists($g_sCmdFile) Then
        Local $sCmd = FileRead($g_sCmdFile)
        FileDelete($g_sCmdFile)
        If $sCmd <> "" Then
            Local $sResult = ExecuteCommand($sCmd)
            FileWrite($g_sResultFile, $sResult)
        EndIf
    EndIf
    Sleep(100)
WEnd

Func ExecuteCommand($sJson)
    ; Simple pipe-delimited parsing (action|param1|param2)
    Local $aParts = StringSplit($sJson, "|")
    If $aParts[0] < 1 Then Return '{"error":"empty command"}'

    Local $sAction = $aParts[1]

    Switch $sAction
        Case "screenshot"
            Local $sFile = $g_sScreenDir & "capture_" & @HOUR & @MIN & @SEC & ".png"
            _ScreenCapture_Capture($sFile)
            Return '{"ok":true,"file":"' & $sFile & '"}'

        Case "windows"
            Local $aList = WinList()
            Local $sResult = '{"windows":['
            Local $nCount = 0
            For $i = 1 To $aList[0][0]
                If $aList[$i][0] <> "" And BitAND(WinGetState($aList[$i][1]), 2) Then
                    If $nCount > 0 Then $sResult &= ","
                    $sResult &= '{"title":"' & StringReplace($aList[$i][0], '"', '\"') & '","hwnd":' & $aList[$i][1] & '}'
                    $nCount += 1
                EndIf
            Next
            $sResult &= ']}'
            Return $sResult

        Case "click"
            If $aParts[0] >= 2 Then
                Local $hWnd = HWnd($aParts[2])
                If $aParts[0] >= 3 Then
                    ControlClick($hWnd, "", $aParts[3])
                Else
                    WinActivate($hWnd)
                    MouseClick("left")
                EndIf
            EndIf
            Return '{"ok":true}'

        Case "gettext"
            If $aParts[0] >= 3 Then
                Local $sText = ControlGetText(HWnd($aParts[2]), "", $aParts[3])
                Return '{"text":"' & StringReplace($sText, '"', '\"') & '"}'
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
                Local $sTitle = WinGetTitle($hWnd)
                Local $aControls = _WinGetControls($hWnd)
                Local $sResult = '{"title":"' & StringReplace($sTitle, '"', '\"') & '","controls":['
                If IsArray($aControls) Then
                    For $i = 0 To UBound($aControls) - 1
                        If $i > 0 Then $sResult &= ","
                        Local $sCtrlText = ControlGetText($hWnd, "", $aControls[$i])
                        $sResult &= '{"id":"' & $aControls[$i] & '","text":"' & StringReplace(StringLeft($sCtrlText, 50), '"', '\"') & '"}'
                    Next
                EndIf
                $sResult &= ']}'
                Return $sResult
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

Func _WinGetControls($hWnd)
    Local $sControls = WinGetClassList($hWnd)
    Local $aClasses = StringSplit($sControls, @LF)
    Local $aResult[0]
    Local $aCount[]

    For $i = 1 To $aClasses[0]
        Local $sClass = StringStripWS($aClasses[$i], 3)
        If $sClass = "" Then ContinueLoop
        If Not IsDeclared("aCount") Or Not MapExists($aCount, $sClass) Then
            $aCount[$sClass] = 1
        Else
            $aCount[$sClass] += 1
        EndIf
        _ArrayAdd($aResult, "[CLASS:" & $sClass & "; INSTANCE:" & $aCount[$sClass] & "]")
    Next
    Return $aResult
EndFunc
