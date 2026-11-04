; The OAK box installer for Windows (Inno Setup 6). It installs the portable bundle
; (packaging/build_bundle.sh windows, unpacked to dist\oakbox-win64) for this user only:
; no admin rights, into %LOCALAPPDATA%\Programs\OAK box, with a Start menu entry and an
; uninstaller. Projects (Documents\OAK box) are the user's, never touched by it.
;
;   iscc /DAppVersion=0.1.0 packaging\oakbox.iss      ->  dist\OAKbox-0.1.0-setup.exe
;
; Unsigned for now (SPEC §6, D14): Windows SmartScreen asks "Run anyway" the first time.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#define Bundle "..\dist\oakbox-win64"

[Setup]
; Never change AppId: it's how a new version finds the old one to replace.
AppId={{835628E2-A484-4CFA-8F36-5E3528B30863}
AppName=OAK box
AppVersion={#AppVersion}
AppVerName=OAK box {#AppVersion}
AppPublisher=OpenAVMKit
AppPublisherURL=https://www.openavmkit.com/
AppSupportURL=https://github.com/larsiusprime/oakbox/issues
; Per user, no admin: {autopf} is %LOCALAPPDATA%\Programs when not elevated. Its paths stay
; well under Windows' 260 characters (the bundle's longest is 141 from its root).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\OAK box
DefaultGroupName=OAK box
DisableProgramGroupPage=yes
UninstallDisplayName=OAK box
UninstallDisplayIcon={app}\oakbox.ico
SetupIconFile=oakbox.ico
OutputDir=..\dist
OutputBaseFilename=OAKbox-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
; Windows asks to close a running OAK box before replacing its files.
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; An update replaces the whole runtime, so a library dropped from a newer version doesn't linger.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\sample"

[Files]
Source: "{#Bundle}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "oakbox.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; pythonw.exe: no console window. -X utf8: text is UTF-8, not the code page (as Oakbox.cmd).
Name: "{group}\OAK box"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 -m oakbox"; WorkingDir: "{app}"; IconFilename: "{app}\oakbox.ico"
Name: "{autodesktop}\OAK box"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 -m oakbox"; WorkingDir: "{app}"; IconFilename: "{app}\oakbox.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 -m oakbox"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,OAK box}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; What Python wrote beside the code (compiled caches), so the folder goes entirely.
Type: filesandordirs; Name: "{app}\python"
