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
Name: "cargardemo"; Description: "Cargar datos de demostración (cuentas, mesas, carta y ventas de ejemplo)"; GroupDescription: "Primer uso:"; Flags: unchecked
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

[Code]
var
  AdminPage: TInputQueryWizardPage;

function DatosExisten(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\GastroInsightAI\gastroinsight.sqlite3'));
end;

procedure InitializeWizard();
begin
  AdminPage := CreateInputQueryPage(wpSelectTasks,
    'Cuenta de administrador', 'Crea la cuenta con la que entrarás por primera vez',
    'Esta cuenta administra la plataforma: locales, personal, cámaras y privacidad. Guarda bien la contraseña.');
  AdminPage.Add('Usuario (sin espacios):', False);
  AdminPage.Add('Nombre:', False);
  AdminPage.Add('Correo (opcional):', False);
  AdminPage.Add('Contraseña (mínimo 10 caracteres, que no se parezca al usuario):', True);
  AdminPage.Add('Repite la contraseña:', True);
  AdminPage.Values[0] := 'admin';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = AdminPage.ID) and DatosExisten();
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = AdminPage.ID then
  begin
    if (Trim(AdminPage.Values[0]) = '') or (Pos(' ', Trim(AdminPage.Values[0])) > 0) then
    begin
      MsgBox('Escribe un usuario sin espacios.', mbError, MB_OK);
      Result := False;
    end
    else if Length(AdminPage.Values[3]) < 10 then
    begin
      MsgBox('La contraseña debe tener al menos 10 caracteres.', mbError, MB_OK);
      Result := False;
    end
    else if AdminPage.Values[3] <> AdminPage.Values[4] then
    begin
      MsgBox('Las contraseñas no coinciden.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Archivo: String;
  Lineas: TArrayOfString;
  Codigo: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent()) and (not DatosExisten()) then
  begin
    Archivo := ExpandConstant('{tmp}\admin_inicial.txt');
    SetArrayLength(Lineas, 5);
    Lineas[0] := Trim(AdminPage.Values[0]);
    Lineas[1] := Trim(AdminPage.Values[1]);
    Lineas[2] := Trim(AdminPage.Values[2]);
    Lineas[3] := AdminPage.Values[3];
    if WizardIsTaskSelected('cargardemo') then Lineas[4] := '1' else Lineas[4] := '0';
    SaveStringsToUTF8File(Archivo, Lineas, False);
    WizardForm.StatusLabel.Caption := 'Creando la cuenta de administrador (puede tardar un minuto)...';
    if (not Exec(ExpandConstant('{app}\GastroInsightAI.exe'), 'manage crear_admin_inicial --archivo "' + Archivo + '"',
                 '', SW_HIDE, ewWaitUntilTerminated, Codigo)) or (Codigo <> 0) then
      MsgBox('No se pudo crear la cuenta de administrador. Usa una contraseña más segura y vuelve a instalar,' + #13#10 +
             'o revisa %LOCALAPPDATA%\GastroInsightAI\logs\aplicacion.log', mbError, MB_OK);
    DeleteFile(Archivo);
  end;
end;
