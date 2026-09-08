#define MyAppName "POLARIS-AI"
#define MyAppVersion "1.0.0-rc1"
#define MyAppPublisher "POLARIS-AI Research"
#define MyAppExeName "POLARIS-AI.exe"

[Setup]
AppId={{B8C6F0A0-8E47-4B48-9E44-4B7D3C1A0A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\POLARIS-AI
DefaultGroupName={#MyAppName}
OutputDir=..\..\release\windows\installer
OutputBaseFilename=POLARIS-AI-Setup-{#MyAppVersion}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\..\release\windows\dist\POLARIS-AI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\POLARIS-AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\POLARIS-AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch POLARIS-AI"; Flags: nowait postinstall skipifsilent
