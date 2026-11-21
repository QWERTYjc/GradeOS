Unicode True
!include "LogicLib.nsh"
Name "GradeOS"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\GradeOS"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "icons/GradeOS.ico"
UninstallIcon "icons/GradeOS.ico"
VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "GradeOS"
VIAddVersionKey "FileDescription" "GradeOS 教师工作台安装程序"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "GradeOS contributors"
AutoCloseWindow true
ShowInstDetails nevershow
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

!macro CheckClosed
  ${If} ${FileExists} "$INSTDIR\app\GradeOS.exe"
    ClearErrors
    FileOpen $0 "$INSTDIR\app\GradeOS.exe" a
    ${If} ${Errors}
      MessageBox MB_OK|MB_ICONEXCLAMATION "请先退出正在运行的 GradeOS。" /SD IDOK
      SetErrorLevel 1
      Abort
    ${EndIf}
    FileClose $0
  ${EndIf}
!macroend

Function .onInit
  ${IfNot} ${FileExists} "$INSTDIR\app\GradeOS.exe"
  ${AndIf} ${FileExists} "$INSTDIR\previous\GradeOS.exe"
    Rename "$INSTDIR\previous" "$INSTDIR\app"
  ${EndIf}
  !insertmacro CheckClosed
  RMDir /r "$INSTDIR\installing"
FunctionEnd

Function un.onInit
  !insertmacro CheckClosed
FunctionEnd

Section "GradeOS"
  SetShellVarContext current
  SetOutPath "$INSTDIR\installing"
  File /r "${APP}/*"
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\previous"
  ${If} ${FileExists} "$INSTDIR\app\GradeOS.exe"
    ClearErrors
    Rename "$INSTDIR\app" "$INSTDIR\previous"
    ${If} ${Errors}
      RMDir /r "$INSTDIR\installing"
      MessageBox MB_OK|MB_ICONEXCLAMATION "请关闭 GradeOS 后重新安装。" /SD IDOK
      Abort
    ${EndIf}
  ${EndIf}
  ClearErrors
  Rename "$INSTDIR\installing" "$INSTDIR\app"
  ${If} ${Errors}
    Rename "$INSTDIR\previous" "$INSTDIR\app"
    Abort
  ${EndIf}
  RMDir /r "$INSTDIR\previous"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortcut "$SMPROGRAMS\GradeOS.lnk" "$INSTDIR\app\GradeOS.exe"
  CreateShortcut "$DESKTOP\GradeOS.lnk" "$INSTDIR\app\GradeOS.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GradeOS" "DisplayName" "GradeOS"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GradeOS" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GradeOS" "DisplayIcon" "$INSTDIR\app\GradeOS.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GradeOS" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  IfSilent +2
  Exec '"$INSTDIR\app\GradeOS.exe"'
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$SMPROGRAMS\GradeOS.lnk"
  Delete "$DESKTOP\GradeOS.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GradeOS"
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\previous"
  RMDir /r "$INSTDIR\installing"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
