#define AppName "GastroInsight AI"
#define AppVersion "2.0.0"

[Setup]
AppId={{8F3B2C1A-5D4E-4F6A-9B7C-1E2D3F4A5B6C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=GastroInsight AI
DefaultDirName={localappdata}\Programs\GastroInsight AI
DefaultGroupName=GastroInsight AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=GastroInsightAI-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\GastroInsightAI.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "redlocal"; Description: "Crear acceso «red del local» para que los celulares del personal se conecten por WiFi"; GroupDescription: "Red:"
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\GastroInsightAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GastroInsight AI (red del local)"; Filename: "{app}\GastroInsightAI.exe"; Parameters: "--red"; Tasks: redlocal
Name: "{autodesktop}\GastroInsight AI (red del local)"; Filename: "{app}\GastroInsightAI.exe"; Parameters: "--red"; Tasks: redlocal
Name: "{group}\GastroInsight AI"; Filename: "{app}\GastroInsightAI.exe"
Name: "{autodesktop}\GastroInsight AI"; Filename: "{app}\GastroInsightAI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GastroInsightAI.exe"; Description: "Abrir GastroInsight AI"; Flags: nowait postinstall skipifsilent
