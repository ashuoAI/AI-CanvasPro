const { contextBridge, ipcRenderer, webUtils } = require("electron");

contextBridge.exposeInMainWorld("aiCanvasDesktop", {
  isElectron: true,
  getAppVersion: () => ipcRenderer.invoke("app:getVersion"),
  checkForUpdates: () => ipcRenderer.invoke("appUpdater:checkForUpdates"),
  getUpdateState: () => ipcRenderer.invoke("appUpdater:getState"),
  downloadUpdate: () => ipcRenderer.invoke("appUpdater:downloadUpdate"),
  installDownloadedUpdate: () => ipcRenderer.invoke("appUpdater:quitAndInstall"),
  onUpdaterEvent: (callback) => {
    if (typeof callback !== "function") return () => {};
    const listener = (_event, payload) => {
      callback(payload);
    };
    ipcRenderer.on("appUpdater:event", listener);
    return () => {
      ipcRenderer.removeListener("appUpdater:event", listener);
    };
  },
});

contextBridge.exposeInMainWorld("electronAPI", {
  getPathForFile: (file) => webUtils.getPathForFile(file),
  project: {
    open: (payload) => ipcRenderer.invoke("project:open", payload),
    save: (payload) => ipcRenderer.invoke("project:save", payload),
    listRecent: () => ipcRenderer.invoke("project:listRecent"),
    removeRecent: (payload) => ipcRenderer.invoke("project:removeRecent", payload),
    consumeExternalOpenRequests: () =>
      ipcRenderer.invoke("project:consumeExternalOpenRequests"),
    onExternalOpen: (callback) => {
      if (typeof callback !== "function") return () => {};
      const listener = () => {
        ipcRenderer
          .invoke("project:consumeExternalOpenRequests")
          .then((requests) => {
            callback(Array.isArray(requests) ? requests : []);
          })
          .catch((error) => {
            callback([
              {
                success: false,
                error: String(error?.message || error),
              },
            ]);
          });
      };
      ipcRenderer.on("project:externalOpenAvailable", listener);
      return () => {
        ipcRenderer.removeListener("project:externalOpenAvailable", listener);
      };
    },
  },
  importAsset: (payload) => ipcRenderer.invoke("asset:import", payload),
  mediaTask: {
    enqueue: (payload) => ipcRenderer.invoke("mediaTask:enqueue", payload),
    cancel: (payload) => ipcRenderer.invoke("mediaTask:cancel", payload),
    onUpdate: (callback) => {
      if (typeof callback !== "function") return () => {};
      const listener = (_event, payload) => {
        callback(payload);
      };
      ipcRenderer.on("mediaTask:update", listener);
      return () => {
        ipcRenderer.removeListener("mediaTask:update", listener);
      };
    },
  },
  getLocalPreviewUrl: (payload) => ipcRenderer.invoke("file:getLocalPreviewUrl", payload),
  importLocalFile: (payload) => ipcRenderer.invoke("file:importLocalFile", payload),
  showItemInFolder: (payload) => ipcRenderer.invoke("shell:showItemInFolder", payload),
  openKnownFolder: (payload) => ipcRenderer.invoke("shell:openKnownFolder", payload),
  shell: {
    openExternal: (url) => ipcRenderer.invoke("shell:openExternal", { url }),
  },
  diagnostics: {
    logEvent: (payload) => ipcRenderer.invoke("diagnostics:logEvent", payload),
    createPackage: () => ipcRenderer.invoke("diagnostics:createPackage"),
    openLogsFolder: () => ipcRenderer.invoke("diagnostics:openLogsFolder"),
  },
  onAssetUpdated: (callback) => {
    if (typeof callback !== "function") return () => {};
    const listener = (_event, payload) => {
      callback(payload);
    };
    ipcRenderer.on("asset:updated", listener);
    return () => {
      ipcRenderer.removeListener("asset:updated", listener);
    };
  },
  logDragImport: (label, payload) =>
    ipcRenderer.send("diagnostics:dragImportLog", { label, payload }),
});
