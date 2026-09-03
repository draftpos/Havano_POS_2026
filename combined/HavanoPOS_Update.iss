[Setup]
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableReadyMemo=yes
; Use exactly the same AppId as the original setup so Inno Setup knows this is an update!
AppId={{2A6A3644-F949-4786-B029-7C38B1C618F2}}
AppName=Havano POS
AppVersion=2.0.8.37
DefaultDirName={pf}\Havano POS
DefaultGroupName=Havano POS
OutputBaseFilename=HavanoPOS_Update_Installer_v2.0.8.37
; Disable warning that the directory already exists (since it's an update)
DirExistsWarning=no
; Disable Inno Setup's built-in application closing prompt to make it completely silent
CloseApplications=no
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

; Branding
SetupIconFile=..\assets\havano_new_blue.ico

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
Name: "{app}"; Permissions: users-modify

[Files]
; The main application executable created by PyInstaller
Source: "..\dist\HavanoPOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Havano POS"; Filename: "{app}\HavanoPOS.exe"; IconFilename: "{app}\HavanoPOS.exe"
Name: "{commondesktop}\Havano POS"; Filename: "{app}\HavanoPOS.exe"; IconFilename: "{app}\HavanoPOS.exe"; Tasks: desktopicon

[Run]
; Run the App after installation
Filename: "{app}\HavanoPOS.exe"; Description: "{cm:LaunchProgram,Havano POS}"; Flags: nowait

[Code]
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  // Kill the application before starting setup to prevent "Access is denied" errors
  ShellExec('', 'taskkill.exe', '/f /im HavanoPOS.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Result := True;
end;
