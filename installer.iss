; JITM POS - Windows Installer Script (Inno Setup)
; -------------------------------------------------------------------------
; Build with: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Requires Inno Setup 6+: https://jrsoftware.org/isdl.php
;
; Replaces the old installer.nsi. Fixes:
;   - Unstyled/black buttons with no text (NSIS + no manifest issue)
;   - No visible install-location page
;   - Data being wiped on uninstall/reinstall
;   - Clunky update flow (now: just run the new installer, it upgrades in place)
; -------------------------------------------------------------------------

#define MyAppName "JITM POS"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "JITM"
#define MyAppExeName "JITM.exe"
#define MyAppURL "https://github.com/Muhammad2684/jitm-pos"

[Setup]
; Keep this GUID identical for every future release - it is how Setup
; recognizes "this is the same app, just a newer version" and enables
; in-place upgrades instead of side-by-side installs.
AppId={{52BFE99D-EC72-48CB-9B94-F620A040F569}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}

; Installing to LocalAppData means no admin/UAC prompt is needed, which
; sidesteps the elevation-related rendering glitches (black/blank buttons)
; some users hit with the old NSIS installer.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; This page is what shows the user exactly where the app will be
; installed, with an option to change it.
DisableDirPage=no
DisableReadyPage=no

UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=JITM-POS-Setup-{#MyAppVersion}
SetupIconFile=static\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

; Prevents the app from being launched during install/uninstall while
; files are being replaced.
AppMutex=JITMPOSSingleInstanceMutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; -------------------------------------------------------------------------
; Data persistence:
; app.py / database.py store the SQLite database and settings under
; {localappdata}\JITM POS (NOT inside {app}). Because that folder lives
; outside the install directory, Inno Setup's uninstaller never touches
; it, so data automatically survives an uninstall + reinstall or an
; update without any special-casing here.
; -------------------------------------------------------------------------

[Code]
function InitializeSetup(): Boolean;
begin
  // Close the app if it's already running so its .exe can be overwritten
  // cleanly during an update - avoids "file in use" failures.
  Exec('taskkill.exe', '/F /IM {#MyAppExeName} /T', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  Exec('taskkill.exe', '/F /IM {#MyAppExeName} /T', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Response: Integer;
begin
  // Program files are always removed. Business data (sales, products,
  // settings) is kept by default - it lives in AppData, not {app} - and
  // is only deleted if the user explicitly opts in here.
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\JITM POS');
    if DirExists(DataDir) then
    begin
      Response := MsgBox(
        'Also delete your saved JITM POS data (sales, products, customers, settings)?' + #13#10 + #13#10 +
        'Choose "No" to keep your data so it is still there if you reinstall JITM POS later.' + #13#10 +
        'This cannot be undone.',
        mbConfirmation, MB_YESNO);
      if Response = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
