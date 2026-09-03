[Setup]
AppName=Havano POS
AppVersion=1.0
AppId={{2A6A3644-F949-4786-B029-7C38B1C618F2}
DefaultDirName={autopf}\Havano POS
DefaultGroupName=Havano POS
OutputBaseFilename=HavanoPOS_Installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

; Branding
SetupIconFile=combined\havano-logo.ico
WizardImageFile=combined\wizard_large.bmp
WizardSmallImageFile=combined\wizard_small.bmp
WizardImageStretch=yes
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
; The main application executable created by PyInstaller
Source: "dist\HavanoPOS.exe"; DestDir: "{app}"; Flags: ignoreversion
; Include all assets (optional if PyInstaller bundled them inside, but if you have external folders like app_data, add them here)
; Source: "app_data\*"; DestDir: "{app}\app_data"; Flags: ignoreversion recursesubdirs createallsubdirs

; Include the SQL Server 2019 Express offline installer (Make sure you download it and place it next to this ISS file)
Source: "SQLEXPR_x64_ENU.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedToInstallSQLServer

[Icons]
Name: "{group}\Havano POS"; Filename: "{app}\HavanoPOS.exe"; IconFilename: "{app}\HavanoPOS.exe"
Name: "{commondesktop}\Havano POS"; Filename: "{app}\HavanoPOS.exe"; IconFilename: "{app}\HavanoPOS.exe"; Tasks: desktopicon

[Run]
; Run SQL Server 2019 Installer silently if needed
Filename: "{tmp}\SQLEXPR_x64_ENU.exe"; Parameters: "/QS /ACTION=Install /FEATURES=SQL /INSTANCENAME=SQLEXPRESS /SQLSVCACCOUNT=""NT AUTHORITY\Network Service"" /SQLSYSADMINACCOUNTS=""BUILTIN\ADMINISTRATORS"" /AGTSVCACCOUNT=""NT AUTHORITY\Network Service"" /IACCEPTSQLSERVERLICENSETERMS"; StatusMsg: "Installing SQL Server 2019 Express (This may take several minutes)..."; Check: NeedToInstallSQLServer; Flags: waituntilterminated

; Finally, run the App after installation
Filename: "{app}\HavanoPOS.exe"; Description: "{cm:LaunchProgram,Havano POS}"; Flags: nowait postinstall

[Code]
// Kill the app before setup
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  ShellExec('', 'taskkill.exe', '/f /im HavanoPOS.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Result := True;
end;

// This function checks the registry to see if SQL Server SQLEXPRESS is already installed
function NeedToInstallSQLServer(): Boolean;
var
  Installed: Boolean;
begin
  Installed := False;
  // Check the registry for the SQLEXPRESS instance
  if RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL') then
  begin
    if RegValueExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL', 'SQLEXPRESS') then
    begin
      Installed := True;
    end;
  end;
  
  // If Installed is True, we do NOT need to install SQL Server
  Result := not Installed;
end;
