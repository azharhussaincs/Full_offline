; ===========================================================================
;  PeopleFinder — Windows installer  (Inno Setup 6.3+)
;
;  Build:   ISCC.exe  packaging\installer.iss
;  (ISCC.exe ships with Inno Setup — https://jrsoftware.org/isdl.php)
;
;  Inputs (produced by packaging\build_windows.bat):
;    * packaging\dist\PeopleFinder\     — the frozen app + bundled Elasticsearch
;                                          distribution (incl. its own jdk/)
;    * runtime\es-data\                  — the ~22 GB Elasticsearch DATA dir that
;                                          contains the tc_index index
;
;  Output:  packaging\Output\PeopleFinder-Setup.exe   — the single installer.
;
;  Layout after install:
;    {app}\PeopleFinder.exe                     the application
;    {app}\elasticsearch\...                    the bundled Elasticsearch (read-only)
;    {localappdata}\PeopleFinder\es-data\...     the tc_index data (writable; ~22 GB)
;    {localappdata}\PeopleFinder\es-logs, es-tmp, es-config   created at first run
;
;  The application starts Elasticsearch in the background (hidden), pointed at
;  the es-data directory, and stops it on exit.  The end user does nothing.
;
;  NOTE: the ~22 GB payload makes a large installer and a slow build with
;  Compression=lzma2/max + SolidCompression.  While iterating, change
;  Compression to lzma2/fast (or none).  To split onto fixed-size media,
;  uncomment DiskSpanning / DiskSliceSize.
; ===========================================================================

#define MyAppName      "PeopleFinder"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "PeopleFinder"
#define MyAppExeName   "PeopleFinder.exe"

[Setup]
; Stable, unique product GUID — keep constant across versions so upgrades replace.
AppId={{C9B4E1A2-3D7F-4A56-9E0B-7F1C2D3E4A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Large app — let the user choose the install drive/folder.
DisableDirPage=no
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
OutputDir=Output
OutputBaseFilename=PeopleFinder-Setup
SetupIconFile=app.ico
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
; --- Optional: split the (large) installer into fixed-size volumes ---
; DiskSpanning=yes
; DiskSliceSize=4096000000
; SlicesPerDisk=1

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; The frozen application + the bundled Elasticsearch distribution (incl. jdk/).
Source: "dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

; The ~22 GB Elasticsearch data directory (the tc_index index).  It is installed
; into a per-user, WRITABLE location so the app can run without admin rights and
; so there is no slow first-run copy.  The end user never opens this folder.
Source: "..\runtime\es-data\*"; DestDir: "{localappdata}\{#MyAppName}\es-data"; \
    Flags: recursesubdirs createallsubdirs ignoreversion uninsneveruninstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Make sure the app (and the Elasticsearch / java.exe it spawned) is stopped
; before files are removed.  /T kills the whole process tree; ignore errors.
Filename: "{cmd}"; Parameters: "/c taskkill /F /T /IM {#MyAppExeName}"; Flags: runhidden

[UninstallDelete]
; Remove everything the app created under %LOCALAPPDATA% — including the ~22 GB
; es-data directory (it was flagged uninsneveruninstall above so Inno's own
; file list doesn't touch it; this wipes the whole folder explicitly).
Type: filesandordirs; Name: "{localappdata}\{#MyAppName}"

[Code]
// Best-effort: stop a running instance before (over)installing, so files aren't locked.
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
    Exec(ExpandConstant('{cmd}'), '/c taskkill /F /T /IM {#MyAppExeName}', '',
         SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
