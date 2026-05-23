import { graphStore, uiStore } from '../core/stores/index.js';
import { generateId } from '../core/math.js';
import { commit } from '../modules/history.js';
import { getNodeDefaultSize, buildSourceMediaNodePayload } from '../services/fileService.js';
import { showSnapshotPicker } from './snapshotPicker.js';

let _lastWorldX = 0;
let _lastWorldY = 0;

function getActiveCanvasName() {
    const el = document.getElementById('projectNameText');
    if (el && el.textContent && el.textContent.trim()) {
        return el.textContent.trim();
    }
    if (window.currentProjectId) {
        return String(window.currentProjectId);
    }
    return 'default';
}

function addSnapshotImageNodes(selectedImages, worldX, worldY) {
    if (!selectedImages || selectedImages.length === 0) return;

    const size = getNodeDefaultSize('source-image');
    const offsetX = 20;
    const offsetY = 20;

    selectedImages.forEach((img, idx) => {
        const nodeId = generateId('source-image');
        const nodeX = worldX - size.width / 2 + idx * offsetX;
        const nodeY = worldY - size.height / 2 + idx * offsetY;

        const baseName = img.filename.replace(/\.[^.]+$/, '');
        const imageUrl = '/' + img.virtualPath;

        const nodeData = buildSourceMediaNodePayload({
            id: nodeId,
            type: 'source-image',
            x: nodeX,
            y: nodeY,
            src: imageUrl,
            localPath: img.virtualPath,
            fileName: img.virtualPath,
            name: baseName || '图片',
        });

        graphStore.addNode(nodeData);
        graphStore.setSelectedNodes([nodeId]);
    });

    commit();
}

function createSnapshotMenuItem() {
    const btn = document.createElement('button');
    btn.className = 'v2-menu-row';
    btn.dataset.snapshotAction = 'true';

    const ico = document.createElement('div');
    ico.className = 'v2-menu-ico';
    ico.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>`;

    const lblWrap = document.createElement('div');
    lblWrap.className = 'v2-menu-lbl-wrap';

    const lbl = document.createElement('span');
    lbl.className = 'v2-menu-lbl';
    lbl.textContent = '项目快照';

    lblWrap.appendChild(lbl);
    btn.appendChild(ico);
    btn.appendChild(lblWrap);

    btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const overlay = document.getElementById('v2PickerOverlay');
        if (overlay) overlay.remove();

        const canvasName = getActiveCanvasName();

        showSnapshotPicker({
            canvasName,
            worldX: _lastWorldX,
            worldY: _lastWorldY,
            onConfirm: addSnapshotImageNodes,
            onCancel: () => {},
        });
    });

    return btn;
}

function createSnapshotSeparator() {
    const sep = document.createElement('div');
    sep.className = 'v2-menu-sep';
    sep.dataset.snapshotAction = 'true';
    return sep;
}

function injectSnapshotMenuItem(pickerOverlay) {
    const menuPanel = pickerOverlay.querySelector('.v2-node-add-menu');
    if (!menuPanel) return;
    if (menuPanel.querySelector('[data-snapshot-action]')) return;

    const snapshotItem = createSnapshotMenuItem();
    const separator = createSnapshotSeparator();

    menuPanel.insertBefore(separator, menuPanel.firstChild);
    menuPanel.insertBefore(snapshotItem, menuPanel.firstChild);
}

function captureWorldCoordinates() {
    try {
        const state = graphStore?.getStateRaw?.() || graphStore?.getState?.();
        if (state && state.viewport) {
            const vp = state.viewport;
            const cx = window.innerWidth / 2;
            const cy = window.innerHeight / 2;
            _lastWorldX = (cx - vp.x) / vp.scale;
            _lastWorldY = (cy - vp.y) / vp.scale;
        }
    } catch (e) {
        // fallback: use center of viewport
    }
}

let _observer = null;

function startObserving() {
    if (_observer) return;

    _observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType !== Node.ELEMENT_NODE) continue;
                if (node.id === 'v2PickerOverlay') {
                    captureWorldCoordinates();
                    setTimeout(() => injectSnapshotMenuItem(node), 0);
                    return;
                }
                const overlay = node.querySelector?.('#v2PickerOverlay');
                if (overlay) {
                    captureWorldCoordinates();
                    setTimeout(() => injectSnapshotMenuItem(overlay), 0);
                    return;
                }
            }
        }
    });

    _observer.observe(document.body, { childList: true, subtree: true });
}

function interceptDblClick() {
    const wrap = document.getElementById('v2-wrap');
    if (!wrap) return;

    wrap.addEventListener('dblclick', (e) => {
        try {
            const state = graphStore?.getStateRaw?.() || graphStore?.getState?.();
            if (state && state.viewport) {
                const vp = state.viewport;
                _lastWorldX = (e.clientX - vp.x) / vp.scale;
                _lastWorldY = (e.clientY - vp.y) / vp.scale;
            }
        } catch (err) {
            // fallback
        }
    }, true);
}

export function initSnapshotIntegration() {
    startObserving();
    interceptDblClick();
}
