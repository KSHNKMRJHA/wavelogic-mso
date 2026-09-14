; =====================================================================
;  WaveLogic MSO - Inno Setup installer (Inno Setup 6.x)
;  Follows the generating-python-installer skill template:
;  LZMA2 ultra compression, full metadata, residue-free uninstall,
;  arch-matched VC++ redistributable.
;
;  Build:  iscc /DSourceDir="..." /DOutputDir="..." installer.iss
; =====================================================================

#ifndef MyAppName
#define MyAppName        "WaveLogic MSO"
#endif
#ifndef MyAppVersion
#define MyAppVersion     "1.0.1"
#endif
#ifndef MyAppPublisher
#define MyAppPublisher   "Kishan J."
#endif
#ifndef MyAppURL
#define MyAppURL         "https://github.com/KSHNKMRJHA/wavelogic-mso"
#endif
#ifndef MyAppExeName
#define MyAppExeName     "WaveLogicMSO.exe"
#endif
#ifndef MySourceDir
#define MySourceDir      "dist_runtime"
#endif
#ifndef MyOutputDir
#define MyOutputDir      "output"
#endif
#ifndef MyRedist
#define MyRedist         "vc_redist.x64.exe"
#endif
#ifndef MyIcon
#define MyIcon           "src\wavelogic_logo.ico"
#endif

[Setup]
; --- identity ---
AppId={{D2C20B44-54A4-45DC-B8AD-DE074F04442F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; --- install path & privileges ---
AppendDefaultDirName=yes
DefaultDirName={autopf}\WaveLogic MSO
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=no
PrivilegesRequired=admin

; --- output ---
OutputDir={#MyOutputDir}
OutputBaseFilename=WaveLogicMSO-Setup_v{#MyAppVersion}

; --- visual ---
WizardStyle=modern
SetupIconFile={#MyIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}

; --- compression (skill template) ---
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; --- architecture (64-bit Python build -> x64 install mode) ---
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#if FileExists(MyRedist)
Source: "{#MyRedist}"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
#if FileExists(MyRedist)
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; StatusMsg: "Installing VC++ runtime..."; Flags: waituntilterminated; Check: IsWin64
#endif
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent