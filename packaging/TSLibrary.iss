#define AppName "TSLibrary"
#ifndef AppVersion
  #error Pass /DAppVersion via scripts/build_windows.ps1
#endif

[Setup]
AppId={{3382D8A4-B091-476C-A1ED-C82D49754F0B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=TSLibrary
DefaultDirName={localappdata}\Programs\TSLibrary
DefaultGroupName=TSLibrary
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Global\TSLibrary.Desktop.80d069e4
UninstallDisplayIcon={app}\TSLibrary.exe
SetupIconFile=TSLibrary.ico
OutputDir=..\dist
OutputBaseFilename=TSLibrary-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\TSLibrary\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TSLibrary"; Filename: "{app}\TSLibrary.exe"
Name: "{autodesktop}\TSLibrary"; Filename: "{app}\TSLibrary.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TSLibrary.exe"; Description: "Open TSLibrary"; Flags: nowait postinstall skipifsilent
