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
; The optional engines' sizes (download in MB, disk in bytes), from the bundle's engines.json: CI passes them.
#ifndef xgboostDownload
  #define xgboostDownload "102"
  #define xgboostDisk "144000000"
#endif
#ifndef catboostDownload
  #define catboostDownload "113"
  #define catboostDisk "407000000"
#endif

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

; XGBoost and CatBoost aren't in the bundle (SPEC §6, Optional engines): ticked here, they're downloaded at the
; end of the install, by the same code the app uses (oakbox/engines.py), into %LOCALAPPDATA%\OAK box\engines. A
; download that fails doesn't fail the install: the app offers it again when a model needs it.
[Types]
Name: "custom"; Description: "OAK box"; Flags: iscustom

[Components]
Name: "main"; Description: "OAK box"; Types: custom; Flags: fixed
Name: "xgboost"; Description: "XGBoost model engine (downloads {#xgboostDownload} MB)"; ExtraDiskSpaceRequired: {#xgboostDisk}
Name: "catboost"; Description: "CatBoost model engine (downloads {#catboostDownload} MB)"; ExtraDiskSpaceRequired: {#catboostDisk}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; An update replaces the whole runtime, so a library dropped from a newer version doesn't linger.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\sample"

[Files]
Source: "{#Bundle}\*"; DestDir: "{app}"; Components: main; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "oakbox.ico"; DestDir: "{app}"; Components: main; Flags: ignoreversion

[Icons]
; pythonw.exe: no console window. -X utf8: text is UTF-8, not the code page (as Oakbox.cmd).
Name: "{group}\OAK box"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 -m oakbox"; WorkingDir: "{app}"; IconFilename: "{app}\oakbox.ico"
Name: "{autodesktop}\OAK box"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 -m oakbox"; WorkingDir: "{app}"; IconFilename: "{app}\oakbox.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\python.exe"; Parameters: "-X utf8 -m oakbox.engines install xgboost"; WorkingDir: "{app}"; StatusMsg: "Downloading XGBoost ({#xgboostDownload} MB)…"; Components: xgboost; Flags: runhidden waituntilterminated
Filename: "{app}\python\python.exe"; Parameters: "-X utf8 -m oakbox.engines install catboost"; WorkingDir: "{app}"; StatusMsg: "Downloading CatBoost ({#catboostDownload} MB)…"; Components: catboost; Flags: runhidden waituntilterminated
Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 -m oakbox"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,OAK box}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; What Python wrote beside the code (compiled caches), so the folder goes entirely; and the engines it downloaded.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{localappdata}\OAK box\engines"
Type: dirifempty; Name: "{localappdata}\OAK box"
