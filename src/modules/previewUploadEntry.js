import appStore from '../core/stores/appStore.js';
import { uploadFile } from './project.js';
import { isPreviewModeEnabled } from './previewMode.js';
import {
  applyUploadedPreviewAudioResult,
  applyUploadedPreviewImageResult,
  applyUploadedPreviewVideoResult
} from './previewUploadResult.js';

const PREVIEW_UPLOAD_TYPES = {
  image: {
    accept: 'image/*',
    mimePrefix: 'image/',
    label: '图片',
    successMessage: '已将上传图片写入当前节点',
    applyResult: applyUploadedPreviewImageResult,
    nodeTypes: new Set(['source-image', 'image', 'ai-image'])
  },
  video: {
    accept: 'video/*',
    mimePrefix: 'video/',
    label: '视频',
    successMessage: '已将上传视频写入当前节点',
    applyResult: applyUploadedPreviewVideoResult,
    nodeTypes: new Set(['source-video', 'video', 'ai-video'])
  },
  audio: {
    accept: 'audio/*',
    mimePrefix: 'audio/',
    label: '音频',
    successMessage: '已将上传音频写入当前节点',
    applyResult: applyUploadedPreviewAudioResult,
    nodeTypes: new Set(['ai-audio'])
  }
};

function getState(storeApi) {
  return storeApi?.getState?.() || {};
}

function getToast(showToast) {
  return typeof showToast === 'function' ? showToast : globalThis.window?.showToast;
}

function setButtonBusy(button, busy) {
  if (!button) return;
  if (busy) {
    if (!button.dataset.previewUploadLabel) {
      button.dataset.previewUploadLabel = button.textContent || '上传';
    }
    button.disabled = true;
    button.textContent = '上传中';
    return;
  }
  button.disabled = false;
  button.textContent = button.dataset.previewUploadLabel || '上传';
}

export function resolvePreviewUploadTarget(state = {}) {
  const selectedNodeIds = Array.isArray(state.selectedNodeIds)
    ? state.selectedNodeIds.filter(Boolean)
    : [];
  if (selectedNodeIds.length !== 1) {
    return { ok: false, message: '请选择一个要写入结果的节点' };
  }
  const nodeId = selectedNodeIds[0];
  const node = state.nodes?.[nodeId];
  if (!node) {
    return { ok: false, message: '找不到当前选中的节点' };
  }
  const nodeType = String(node.type || '').trim();
  for (const [kind, config] of Object.entries(PREVIEW_UPLOAD_TYPES)) {
    if (!config.nodeTypes.has(nodeType)) continue;
    return {
      ok: true,
      kind,
      nodeId,
      node,
      accept: config.accept,
      mimePrefix: config.mimePrefix,
      label: config.label,
      successMessage: config.successMessage,
      applyResult: config.applyResult
    };
  }
  return { ok: false, message: '当前节点不支持预览上传' };
}

export async function handlePreviewUploadFile({
  file,
  button = null,
  storeApi = appStore,
  uploadFileImpl = uploadFile,
  showToast = null,
  getProjectId = () => globalThis.window?.currentProjectId || 'default_v2_project',
  applyResults = {}
} = {}) {
  const toast = getToast(showToast);
  const target = resolvePreviewUploadTarget(getState(storeApi));
  if (!target.ok) {
    toast?.(target.message, 'warn');
    return false;
  }
  if (!file) return false;
  if (!String(file.type || '').startsWith(target.mimePrefix)) {
    toast?.(`请上传${target.label}文件`, 'error');
    return false;
  }
  setButtonBusy(button, true);
  try {
    const uploadRes = await uploadFileImpl(file, getProjectId());
    const applyFn = applyResults[target.kind] || target.applyResult;
    applyFn({ nodeId: target.nodeId, uploadRes, fileName: file.name });
    toast?.(target.successMessage, 'success');
    return true;
  } catch (err) {
    toast?.(err?.message || '上传失败，请重试', 'error');
    return false;
  } finally {
    setButtonBusy(button, false);
  }
}

export async function handlePreviewUploadFiles({
  files,
  button = null,
  storeApi = appStore,
  uploadFileImpl = uploadFile,
  showToast = null,
  getProjectId = () => globalThis.window?.currentProjectId || 'default_v2_project',
  applyResults = {}
} = {}) {
  const toast = getToast(showToast);
  const target = resolvePreviewUploadTarget(getState(storeApi));
  if (!target.ok) {
    toast?.(target.message, 'warn');
    return { succeeded: 0, failed: 0, total: 0 };
  }
  const fileArray = Array.from(files);
  if (!fileArray.length) return { succeeded: 0, failed: 0, total: 0 };

  const validFiles = fileArray.filter(
    f => String(f.type || '').startsWith(target.mimePrefix)
  );
  if (!validFiles.length) {
    toast?.(`请上传${target.label}文件`, 'error');
    return { succeeded: 0, failed: fileArray.length, total: fileArray.length };
  }

  setButtonBusy(button, true);
  let succeeded = 0;
  let failed = 0;
  try {
    for (const file of validFiles) {
      try {
        const uploadRes = await uploadFileImpl(file, getProjectId());
        const applyFn = applyResults[target.kind] || target.applyResult;
        applyFn({ nodeId: target.nodeId, uploadRes, fileName: file.name });
        succeeded++;
      } catch {
        failed++;
      }
    }
  } finally {
    setButtonBusy(button, false);
  }

  if (succeeded > 0) {
    toast?.(target.successMessage, 'success');
  }
  if (failed > 0) {
    toast?.(`${failed}个文件上传失败`, 'error');
  }
  return { succeeded, failed, total: fileArray.length };
}

export function bindPreviewUploadEntry({
  button,
  input,
  storeApi = appStore,
  uploadFileImpl = uploadFile,
  showToast = null,
  getProjectId,
  applyResults
} = {}) {
  if (!button || !input) return null;
  const toast = getToast(showToast);

  const onClickButton = () => {
    if (!isPreviewModeEnabled()) return;
    const target = resolvePreviewUploadTarget(getState(storeApi));
    if (!target.ok) {
      toast?.(target.message, 'warn');
      return;
    }

    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.multiple = true;
    fileInput.accept = target.accept;
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    const cleanup = () => {
      if (fileInput.parentNode) fileInput.parentNode.removeChild(fileInput);
    };

    fileInput.addEventListener('change', async () => {
      const files = fileInput.files;
      if (!files || !files.length) {
        cleanup();
        return;
      }
      try {
        await handlePreviewUploadFiles({
          files,
          button,
          storeApi,
          uploadFileImpl,
          showToast,
          getProjectId,
          applyResults
        });
      } finally {
        cleanup();
      }
    });

    fileInput.addEventListener('cancel', cleanup);
    fileInput.click();
  };

  button.addEventListener('click', onClickButton);
  return () => {
    button.removeEventListener?.('click', onClickButton);
  };
}
