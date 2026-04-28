!macro customInstallMode
  ${if} ${isUpdated}
    ${if} $hasPerMachineInstallation == "1"
      StrCpy $isForceMachineInstall "1"
    ${else}
      StrCpy $isForceCurrentInstall "1"
    ${endif}
  ${endif}
!macroend

!macro customInstall
  ${if} ${isUpdated}
  ${andIf} ${isForceRun}
    HideWindow
    ${StdUtils.ExecShellAsUser} $0 "$launchLink" "open" "--updated"
    !insertmacro quitSuccess
  ${endif}
!macroend

!macro preserveInstallDirectory RELATIVE_DIR
  IfFileExists "$INSTDIR\${RELATIVE_DIR}\*.*" +2 0
  IfFileExists "$INSTDIR\${RELATIVE_DIR}" 0 +7
    CreateDirectory "$PLUGINSDIR\aic-preserved"
    ClearErrors
    Rename "$INSTDIR\${RELATIVE_DIR}" "$PLUGINSDIR\aic-preserved\${RELATIVE_DIR}"
    IfErrors 0 +3
      DetailPrint "Unable to protect $INSTDIR\${RELATIVE_DIR}; aborting uninstall to avoid data loss."
      Abort "Unable to protect user data directory: $INSTDIR\${RELATIVE_DIR}"
!macroend

!macro restoreInstallDirectory RELATIVE_DIR
  IfFileExists "$PLUGINSDIR\aic-preserved\${RELATIVE_DIR}\*.*" +2 0
  IfFileExists "$PLUGINSDIR\aic-preserved\${RELATIVE_DIR}" 0 +9
    CreateDirectory "$INSTDIR"
    ClearErrors
    Rename "$PLUGINSDIR\aic-preserved\${RELATIVE_DIR}" "$INSTDIR\${RELATIVE_DIR}"
    IfErrors 0 +5
      DetailPrint "Unable to restore $INSTDIR\${RELATIVE_DIR}; leaving preserved copy in installer temp."
      CreateDirectory "$INSTDIR\${RELATIVE_DIR}"
      CopyFiles /SILENT "$PLUGINSDIR\aic-preserved\${RELATIVE_DIR}\*.*" "$INSTDIR\${RELATIVE_DIR}"
      RMDir /r "$PLUGINSDIR\aic-preserved\${RELATIVE_DIR}"
!macroend

!macro customRemoveFiles
  !insertmacro preserveInstallDirectory "Canvas Project"
  !insertmacro preserveInstallDirectory "output"
  !insertmacro preserveInstallDirectory "data"
  !insertmacro preserveInstallDirectory "AI CanvasPro Files"

  SetOutPath $TEMP
  RMDir /r "$INSTDIR"

  !insertmacro restoreInstallDirectory "Canvas Project"
  !insertmacro restoreInstallDirectory "output"
  !insertmacro restoreInstallDirectory "data"
  !insertmacro restoreInstallDirectory "AI CanvasPro Files"
!macroend
