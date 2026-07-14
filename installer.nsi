; JITM POS - Windows Installer Script
; Build with: makensis installer.nsi

!define PRODUCT_NAME "JITM POS"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "JITM"
!define PRODUCT_WEB_SITE "https://github.com/Muhammad2684/jitm-pos"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\JITM.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

SetCompressor lzma

RequestExecutionLevel admin

!include "MUI2.nsh"
!include "FileFunc.nsh"

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "static\icon.ico"
!define MUI_UNICON "static\icon.ico"

; Language Selection Dialog
!insertmacro MUI_LANGUAGE "English"

; Installer Pages
!insertmacro MUI_PAGE_WELCOME

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_INSTFILES

; Directory where the PyInstaller build output is
!define BUILD_DIR "dist\JITM"

Section "JITM POS" SEC01
    SetOutPath "$INSTDIR"
    SetOverwrite try

    ; Copy all built files
    File /r "${BUILD_DIR}\*.*"

    ; Create shortcuts
    CreateDirectory "$SMPROGRAMS\JITM POS"
    CreateShortCut "$SMPROGRAMS\JITM POS\JITM POS.lnk" "$INSTDIR\JITM.exe" "" "$INSTDIR\JITM.exe" 0
    CreateShortCut "$DESKTOP\JITM POS.lnk" "$INSTDIR\JITM.exe" "" "$INSTDIR\JITM.exe" 0

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninst.exe"

    ; Registry for Add/Remove Programs
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
SectionEnd

Section -AdditionalIcons
    WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${PRODUCT_WEB_SITE}"
    CreateShortCut "$SMPROGRAMS\JITM POS\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
    CreateShortCut "$SMPROGRAMS\JITM POS\Uninstall.lnk" "$INSTDIR\uninst.exe"
SectionEnd

Section Uninstall
    ; Remove files
    RMDir /r "$INSTDIR\*.*"

    ; Remove shortcuts
    RMDir /r "$SMPROGRAMS\JITM POS"
    Delete "$DESKTOP\JITM POS.lnk"

    ; Remove registry keys
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_DIR_REGKEY}"
SectionEnd

; Auto-close installer on success
!define MUI_FINISHPAGE_RUN "$INSTDIR\JITM.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch JITM POS"
