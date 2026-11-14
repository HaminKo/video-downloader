; Inno Setup's recipe for dist\Video Downloader Setup.exe. installer/build.py
; runs it (ISCC.exe) once PyInstaller has built dist\Video Downloader\ and
; build.py has written host.json there; paths are from this folder.
;
; Setup installs that folder for this user only (no admin prompt), into
; %LOCALAPPDATA%\Programs\Video Downloader, with no choice of folder, adds a
; Start-menu entry (and, if ticked, a desktop shortcut) and points Chrome's
; helper key at the installed host.json. Uninstalling removes all of it and
; keeps the app's own folder in %APPDATA% (history, sign-in file).
; docs/decisions.md, "The app as .exe files".

; The app's names; tests/test_installer.py checks them against the Python
; ones (places.py, app.APP_ID, browser.KEY and browser.MANIFEST).
#define AppName "Video Downloader"
#define AppExe "Video Downloader.exe"
#define TaskbarId "VideoDownloader.App"
#define ChromeKey "Software\Google\Chrome\NativeMessagingHosts\video_downloader"
#define HostManifest "host.json"
; The build's date and time, so Settings > Apps shows which build is
; installed (also of two built on one day).
#define Version GetDateTimeString('yyyy/mm/dd hh:nn', '.', ':')

[Setup]
; Never change AppId: Windows knows the installed app by it, so a newer
; Setup installs over the old one.
AppId={{52EB16AF-7AAF-42C0-8CAB-4D7F7D143950}
AppName={#AppName}
AppVersion={#Version}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\build\icon.ico
OutputDir=..\dist
OutputBaseFilename={#AppName} Setup
Compression=lzma2
SolidCompression=yes
; Inno's default, said out loud: a window still open from the old install
; is offered to be closed before its files are replaced.
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Files an older install had and this one hasn't (an older yt-dlp's
; libraries, say) would stay next to the new ones: both folders are
; replaced as a whole.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\extension"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; The window sets the same taskbar ID (app.start()), so a pinned taskbar
; button and the open window are one button.
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#TaskbarId}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#TaskbarId}"; Tasks: desktopicon

[Registry]
; Chrome finds its helper through this key (HKEY_CURRENT_USER). Uninstalling
; deletes it, also when `python -m video_downloader.browser install` has
; pointed it at the project's helper since (run that again then).
Root: HKCU; Subkey: "{#ChromeKey}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
