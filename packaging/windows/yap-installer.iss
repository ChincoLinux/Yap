; Yap — Inno Setup installer script for Windows
; Issue: https://github.com/ChincoLinux/Yap/issues/162
;
; Requirements to build:
;   - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;   - python-3.12.x-embed-amd64.zip extracted to build\python-embed\
;   - llama-cli.exe (Windows build) in build\llama-cli\
;   - All source files in the repo root
;
; Usage:
;   ISCC.exe packaging\windows\yap-installer.iss
;
; Output: dist\windows\yap-<VERSION>-setup.exe
;
; La version NO se fija aqui: build-windows.ps1 la inyecta con
; /DMyAppVersion= (leida del fichero VERSION). Si se compila a mano sin
; ese argumento se usa 0.0.0, a proposito: un artefacto claramente
; invalido vale mas que uno que parece correcto. Ver #242.

#define MyAppName       "Yap"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher  "ChincoLinux"
#define MyAppURL        "https://github.com/ChincoLinux/Yap"
#define MyAppExeName    "yap-launcher.bat"
#define MyInstallDir    "{autopf}\Yap"

[Setup]
AppId={{E5F1A2B3-C4D5-6E7F-8A9B-0C1D2E3F4A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
SourceDir=..\..
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={#MyInstallDir}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Require admin for Program Files installation
PrivilegesRequired=admin
; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Output
OutputDir=..\..\dist\windows
OutputBaseFilename=yap-{#MyAppVersion}-setup
WizardStyle=modern
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; Uninstaller
UninstallDisplayName={#MyAppName} {#MyAppVersion}
; License
LicenseFile=LICENSE
; Readme shown after install
InfoAfterFile=USAGE.md

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath";   Description: "Agregar Yap al PATH del sistema"; GroupDescription: "Configuración del sistema"; Flags: checkedonce
Name: "autostart";   Description: "Iniciar Yap automáticamente al encender el equipo"; GroupDescription: "Configuración del sistema"; Flags: unchecked

[Dirs]
Name: "{app}"
Name: "{app}\models"
Name: "{app}\whitelist"
Name: "{app}\whitelist\pseint"
Name: "{app}\cursos"
Name: "{app}\python"
Name: "{app}\bin"
; User config dir created on first run by yap.py itself

[Files]
; Main agent
Source: "yap.py";                         DestDir: "{app}";                Flags: ignoreversion
Source: "VERSION";                        DestDir: "{app}";                Flags: ignoreversion
Source: "LICENSE";                        DestDir: "{app}";                Flags: ignoreversion
Source: "USAGE.md";                       DestDir: "{app}";                Flags: ignoreversion

; Whitelists and courses
Source: "whitelist\apps.conf";            DestDir: "{app}\whitelist";      Flags: ignoreversion
Source: "whitelist\web.conf";             DestDir: "{app}\whitelist";      Flags: ignoreversion
Source: "whitelist\pseint\ejercicios.conf"; DestDir: "{app}\whitelist\pseint"; Flags: ignoreversion
Source: "cursos\*.json";                  DestDir: "{app}\cursos";         Flags: ignoreversion

; Windows launcher scripts
Source: "packaging\windows\yap-launcher.bat"; DestDir: "{app}";           Flags: ignoreversion

; Python embedded (pre-downloaded by build-windows.ps1)
Source: "build\python-embed\*";           DestDir: "{app}\python";         Flags: ignoreversion recursesubdirs

; llama-cli for Windows (pre-compiled, from llama.cpp releases)
Source: "build\llama-cli\llama-cli.exe";  DestDir: "{app}\bin";            Flags: ignoreversion
Source: "build\llama-cli\*.dll";          DestDir: "{app}\bin";            Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Start Menu
Name: "{group}\Yap — Asistente IA";       Filename: "{app}\yap-launcher.bat"; Comment: "Asistente IA local educativo"
Name: "{group}\Desinstalar Yap";          Filename: "{uninstallexe}"

; Desktop (optional task)
Name: "{autodesktop}\Yap";                Filename: "{app}\yap-launcher.bat"; Tasks: desktopicon

[Registry]
; Add to PATH (optional task)
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
    ValueType: expandsz; ValueName: "Path"; \
    ValueData: "{olddata};{app}\bin;{app}\python"; \
    Check: NeedsAddPath(ExpandConstant('{app}\bin')); \
    Tasks: addtopath; Flags: preservestringtype uninsdeletekeyifempty

; Auto-start (optional task)
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "YapDesktop"; \
    ValueData: """{app}\yap-launcher.bat"" --minimized"; \
    Tasks: autostart; Flags: uninsdeletevalue

; App registration for uninstaller
Root: HKLM; Subkey: "SOFTWARE\ChincoLinux\Yap"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\ChincoLinux\Yap"; ValueType: string; ValueName: "Version";    ValueData: "{#MyAppVersion}"

[Run]
; Verify installation
Filename: "{app}\python\python.exe"; Parameters: "-c ""import sys; print('Python', sys.version)"""; \
    Description: "Verificar Python"; StatusMsg: "Verificando Python embebido..."; \
    Flags: runhidden waituntilterminated

; Open README after install (optional)
Filename: "{app}\USAGE.md"; Description: "Ver guía de uso"; \
    Flags: postinstall nowait unchecked shellexec

[UninstallDelete]
; Clean compiled Python bytecode
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\*.pyc"
; NOTE: user config (~\AppData\Local\yap\) is intentionally preserved
; Models in {app}\models are preserved (large files, user may reinstall)

[Code]
// Helper: check if path already contains the value
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

// Notify Windows of environment change after PATH modification
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    if WizardIsTaskSelected('addtopath') then begin
      // Broadcast WM_SETTINGCHANGE so running processes see the new PATH
      RegWriteStringValue(HKEY_LOCAL_MACHINE,
        'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
        'Path',
        ExpandConstant('{app}\bin') + ';' +
        ExpandConstant('{app}\python') + ';' +
        GetEnv('Path'));
    end;
  end;
end;
