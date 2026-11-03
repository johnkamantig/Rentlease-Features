param([switch]$Release, [switch]$MappedPath)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path $PSScriptRoot -Parent
if (-not $MappedPath) {
  # A transient drive mapping shortens all Gradle/CMake paths without moving
  # files or changing Windows registry policy. Never replace an existing drive.
  $projectRoot = Split-Path (Split-Path $appRoot -Parent) -Parent
  $drive = @('R:','S:','T:','U:','V:') | Where-Object { -not (Test-Path "$_\") } | Select-Object -First 1
  if (-not $drive) { throw 'No free temporary build drive; free R:-V: or use a short project path.' }
  & subst.exe $drive $projectRoot
  if ($LASTEXITCODE) { throw 'Could not establish temporary workspace drive.' }
  try {
    $arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"$drive\notchip-lab\app\scripts\build-android.ps1",'-MappedPath')
    if ($Release) { $arguments += '-Release' }
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & powershell.exe @arguments 2>&1 | ForEach-Object { $_.ToString() }
    $mappedExit = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = 'Stop'
    $localProperties = Join-Path $appRoot 'android\local.properties'
    if (Test-Path -LiteralPath $localProperties) {
      $realSdk = Join-Path (Split-Path $appRoot -Parent) 'android-sdk'
      Set-Content -LiteralPath $localProperties -Value ('sdk.dir=' + $realSdk.Replace('\','/'))
    }
    & subst.exe $drive /D
  }
  if ($mappedExit) { throw 'Mapped native build failed; preserve its log.' }
  return
}
Set-Location -LiteralPath $appRoot
$env:NODE_ENV = if ($Release) { 'production' } else { 'development' }
if (Test-Path -LiteralPath '..\jdk17\bin\java.exe') {
  $env:JAVA_HOME = (Resolve-Path -LiteralPath '..\jdk17').Path
}
if (-not $env:JAVA_HOME -or -not (Test-Path -LiteralPath "$env:JAVA_HOME\bin\java.exe")) {
  throw 'Set JAVA_HOME to a Java 17 JDK before building.'
}
$sdkRoot = Join-Path (Split-Path $appRoot -Parent) 'android-sdk'
if (-not (Test-Path -LiteralPath "$sdkRoot\ndk\27.1.12297006\source.properties")) {
  throw 'Prepare the isolated Android SDK first (see DEVICE_TEST.md).'
}
$ninjaVersion = & "$sdkRoot\cmake\3.22.1\bin\ninja.exe" --version
if ($ninjaVersion.Trim() -ne '1.13.2') { throw 'Run prepare_ninja.py to prepare the lab SDK long-path build tool.' }
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:ANDROID_USER_HOME = Join-Path $sdkRoot '.android'
$env:GRADLE_USER_HOME = Join-Path $appRoot '.gradle'
node .\scripts\prepare-native.cjs
if ($LASTEXITCODE) { throw 'Module preparation failed' }
npx.cmd expo prebuild --platform android --no-install
if ($LASTEXITCODE) { throw 'Expo prebuild failed' }
Set-Content -LiteralPath 'android\local.properties' -Value ('sdk.dir=' + $sdkRoot.Replace('\','/'))
# Do not silently install missing tools into an external Android SDK.
$properties = Join-Path $appRoot 'android\gradle.properties'
$content = Get-Content -Raw -LiteralPath $properties
if ($content -notmatch 'android.builder.sdkDownload=false') {
  Add-Content -LiteralPath $properties -Value "`nandroid.builder.sdkDownload=false"
}
$task = if ($Release) { ':app:assembleRelease' } else { ':app:assembleDebug' }
# Windows PowerShell 5 treats native stderr warnings as error records. Let
# Gradle finish, then use its exit code rather than stopping at the first warning.
$savedPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  & .\android\gradlew.bat -p android $task '-PreactNativeArchitectures=arm64-v8a' '-Pkotlin.incremental=false' '--no-daemon' '--console=plain' 2>&1 | ForEach-Object { $_.ToString() }
  $buildExit = $LASTEXITCODE
} finally { $ErrorActionPreference = $savedPreference }
if ($buildExit) { throw 'Native build failed. Preserve log and fix the reported prerequisite; no APK is verified.' }
$variant = if ($Release) { 'release' } else { 'debug' }
$apk = Join-Path $appRoot "android\app\build\outputs\apk\$variant\app-$variant.apk"
if (-not (Test-Path -LiteralPath $apk)) { throw 'Build completed without the expected APK.' }
$artifacts = Join-Path (Split-Path $appRoot -Parent) 'artifacts'
New-Item -ItemType Directory -Path $artifacts -Force | Out-Null
$copy = Join-Path $artifacts ("rentlease-sweep-lab-$variant-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.apk')
if (Test-Path -LiteralPath $copy) { throw 'Artifact name collision; refusing overwrite.' }
Copy-Item -LiteralPath $apk -Destination $copy
Get-FileHash -LiteralPath $copy -Algorithm SHA256
