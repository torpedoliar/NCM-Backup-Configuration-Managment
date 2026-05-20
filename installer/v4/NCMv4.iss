#define MyAppName "NCM v4"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "NCM"
#define MyAppExeName "ncm-v4-desktop.exe"

[Setup]
AppId={{A6A1DB5B-2C6D-4D2E-A59D-68C3BCA34740}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NCM v4
DefaultGroupName=NCM v4
OutputDir=..\..\dist
OutputBaseFilename=NCM-v4-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
Source: "..\..\app_v4\*"; DestDir: "{app}\app_v4"; Flags: recursesubdirs ignoreversion
Source: "install_service.ps1"; DestDir: "{app}\installer"
Source: "uninstall_service.ps1"; DestDir: "{app}\installer"
Source: "generate_cert.ps1"; DestDir: "{app}\installer"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\installer\install_service.ps1"" -InstallDir ""{app}"""; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\installer\uninstall_service.ps1"""; Flags: runhidden waituntilterminated
