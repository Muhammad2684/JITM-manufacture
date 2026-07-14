; JITM POS - Windows Installer Script (Single-file build)
; Build with: makensis installer.nsi

!define PRODUCT_NAME "JITM POS"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "JITM"
!define PRODUCT_WEB_SITE "https://github.com/Muhammad2684/jitm-pos"
!define PRODUCT_EXE "JITM.exe"

SetCompressor lzma

RequestExecutionLevel admin

!include "MUI2.nsh"

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "static\icon.ico"
!define MUI_UNICON "static\icon.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch JITM POS"

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_INSTFILES

Section "JITM POS" SEC01
    SetOutPath "$INSTDIR"
    SetOverwrite try

    ; Copy the single executable
    File "dist\${PRODUCT_EXE}"

    ; Windows need Runtime DLLs for some systems — bundle VC redist check
    ; (PyInstaller handles this, but we add a check)
    
    ; Create shortcuts
    CreateDirectory "$SMPROGRAMS\JITM POS"
    CreateShortCut "$SMPROGRAMS\JITM POS\JITM POS.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0
    CreateShortCut "$DESKTOP\JITM POS.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninst.exe"

    ; Registry for Add/Remove Programs
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
SectionEnd

Section -AdditionalIcons
    WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${PRODUCT_WEB_SITE}"
    CreateShortCut "$SMPROGRAMS\JITM POS\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
    CreateShortCut "$SMPROGRAMS\JITM POS\Uninstall.lnk" "$INSTDIR\uninst.exe"
SectionEnd

Section Uninstall
    RMDir /r "$INSTDIR\*.*"
    RMDir /r "$SMPROGRAMS\JITM POS"
    Delete "$DESKTOP\JITM POS.lnk"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
