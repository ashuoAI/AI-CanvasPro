const SNAPSHOT_STYLES_ID = 'snapshot-picker-styles';

function injectStyles() {
    if (document.getElementById(SNAPSHOT_STYLES_ID)) return;
    const style = document.createElement('style');
    style.id = SNAPSHOT_STYLES_ID;
    style.textContent = `
.snapshot-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    background: rgba(0,0,0,0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.snapshot-dialog {
    background: var(--bg-primary, #1e1e2e);
    border: 1px solid var(--border-color, #3a3a5c);
    border-radius: 12px;
    width: 720px;
    max-width: 90vw;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    color: var(--text-primary, #e0e0e0);
}
.snapshot-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color, #3a3a5c);
}
.snapshot-title {
    font-size: 16px;
    font-weight: 600;
}
.snapshot-mode-toggle {
    display: flex;
    gap: 4px;
    background: var(--bg-secondary, #2a2a3e);
    border-radius: 6px;
    padding: 2px;
}
.snapshot-mode-btn {
    padding: 4px 12px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text-secondary, #999);
    cursor: pointer;
    font-size: 12px;
    transition: all 0.15s;
}
.snapshot-mode-btn.active {
    background: var(--accent, #6c5ce7);
    color: #fff;
}
.snapshot-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    min-height: 200px;
}
.snapshot-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 10px;
}
.snapshot-item {
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    border: 2px solid transparent;
    cursor: pointer;
    transition: border-color 0.15s, transform 0.1s;
    background: var(--bg-secondary, #2a2a3e);
    aspect-ratio: 1;
}
.snapshot-item:hover {
    border-color: var(--accent-light, #8b7cf7);
    transform: scale(1.03);
}
.snapshot-item.selected {
    border-color: var(--accent, #6c5ce7);
    box-shadow: 0 0 0 2px var(--accent, #6c5ce7);
}
.snapshot-item.selected::after {
    content: '';
    position: absolute;
    top: 6px;
    right: 6px;
    width: 22px;
    height: 22px;
    background: var(--accent, #6c5ce7);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}
.snapshot-item.selected::before {
    content: '✓';
    position: absolute;
    top: 6px;
    right: 6px;
    width: 22px;
    height: 22px;
    z-index: 1;
    color: #fff;
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
}
.snapshot-thumb {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    background: var(--bg-tertiary, #333);
}
.snapshot-filename {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 3px 6px;
    font-size: 10px;
    color: #fff;
    background: linear-gradient(transparent, rgba(0,0,0,0.7));
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.snapshot-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    color: var(--text-secondary, #999);
    gap: 8px;
}
.snapshot-empty-icon {
    font-size: 40px;
    opacity: 0.5;
}
.snapshot-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    color: var(--text-secondary, #999);
    gap: 8px;
}
.snapshot-spinner {
    width: 24px;
    height: 24px;
    border: 3px solid var(--border-color, #3a3a5c);
    border-top-color: var(--accent, #6c5ce7);
    border-radius: 50%;
    animation: snapshot-spin 0.6s linear infinite;
}
@keyframes snapshot-spin {
    to { transform: rotate(360deg); }
}
.snapshot-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-top: 1px solid var(--border-color, #3a3a5c);
}
.snapshot-count {
    font-size: 13px;
    color: var(--text-secondary, #999);
}
.snapshot-actions {
    display: flex;
    gap: 8px;
}
.snapshot-btn {
    padding: 8px 20px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s;
}
.snapshot-btn-cancel {
    background: var(--bg-secondary, #2a2a3e);
    color: var(--text-secondary, #ccc);
    border: 1px solid var(--border-color, #3a3a5c);
}
.snapshot-btn-cancel:hover {
    background: var(--bg-tertiary, #3a3a4e);
}
.snapshot-btn-confirm {
    background: var(--accent, #6c5ce7);
    color: #fff;
}
.snapshot-btn-confirm:hover {
    background: var(--accent-hover, #7d6ff0);
}
.snapshot-btn-confirm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
`;
    document.head.appendChild(style);
}

async function fetchSnapshots(canvasName) {
    const url = `/api/v2/canvas-paths/snapshots/${encodeURIComponent(canvasName)}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
}

export function showSnapshotPicker({ canvasName, worldX, worldY, onConfirm, onCancel }) {
    injectStyles();

    const overlay = document.createElement('div');
    overlay.className = 'snapshot-overlay';

    const dialog = document.createElement('div');
    dialog.className = 'snapshot-dialog';

    const header = document.createElement('div');
    header.className = 'snapshot-header';

    const title = document.createElement('div');
    title.className = 'snapshot-title';
    title.textContent = '项目快照';

    const modeToggle = document.createElement('div');
    modeToggle.className = 'snapshot-mode-toggle';

    const singleBtn = document.createElement('button');
    singleBtn.className = 'snapshot-mode-btn active';
    singleBtn.textContent = '单选';

    const multiBtn = document.createElement('button');
    multiBtn.className = 'snapshot-mode-btn';
    multiBtn.textContent = '多选';

    modeToggle.appendChild(singleBtn);
    modeToggle.appendChild(multiBtn);
    header.appendChild(title);
    header.appendChild(modeToggle);

    const body = document.createElement('div');
    body.className = 'snapshot-body';

    const footer = document.createElement('div');
    footer.className = 'snapshot-footer';

    const countEl = document.createElement('div');
    countEl.className = 'snapshot-count';
    countEl.textContent = '加载中...';

    const actions = document.createElement('div');
    actions.className = 'snapshot-actions';

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'snapshot-btn snapshot-btn-cancel';
    cancelBtn.textContent = '取消';

    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'snapshot-btn snapshot-btn-confirm';
    confirmBtn.textContent = '确定';
    confirmBtn.disabled = true;

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    footer.appendChild(countEl);
    footer.appendChild(actions);

    dialog.appendChild(header);
    dialog.appendChild(body);
    footer.appendChild(countEl);
    footer.appendChild(actions);
    dialog.appendChild(footer);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    let multiMode = false;
    let selectedSet = new Set();
    let images = [];

    singleBtn.addEventListener('click', () => {
        multiMode = false;
        singleBtn.classList.add('active');
        multiBtn.classList.remove('active');
        if (selectedSet.size > 1) {
            const first = selectedSet.values().next().value;
            selectedSet.clear();
            selectedSet.add(first);
            updateSelectionUI();
        }
    });

    multiBtn.addEventListener('click', () => {
        multiMode = true;
        multiBtn.classList.add('active');
        singleBtn.classList.remove('active');
    });

    function updateSelectionUI() {
        const items = body.querySelectorAll('.snapshot-item');
        items.forEach(item => {
            const idx = parseInt(item.dataset.index, 10);
            if (selectedSet.has(idx)) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
        confirmBtn.disabled = selectedSet.size === 0;
        countEl.textContent = selectedSet.size > 0
            ? `已选择 ${selectedSet.size} 张图片`
            : (images.length > 0 ? `共 ${images.length} 张图片` : '无图片');
    }

    function handleItemClick(index) {
        if (multiMode) {
            if (selectedSet.has(index)) {
                selectedSet.delete(index);
            } else {
                selectedSet.add(index);
            }
        } else {
            if (selectedSet.has(index) && selectedSet.size === 1) {
                selectedSet.clear();
            } else {
                selectedSet.clear();
                selectedSet.add(index);
            }
        }
        updateSelectionUI();
    }

    function renderImages(imgs) {
        images = imgs;
        body.innerHTML = '';
        if (imgs.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'snapshot-empty';
            empty.innerHTML = '<div class="snapshot-empty-icon">📷</div><div>该画布暂无快照图片</div>';
            body.appendChild(empty);
            countEl.textContent = '无图片';
            return;
        }
        const grid = document.createElement('div');
        grid.className = 'snapshot-grid';
        imgs.forEach((img, idx) => {
            const item = document.createElement('div');
            item.className = 'snapshot-item';
            item.dataset.index = String(idx);

            const thumb = document.createElement('img');
            thumb.className = 'snapshot-thumb';
            thumb.loading = 'lazy';
            thumb.alt = img.filename;
            thumb.src = '/' + img.virtualPath;

            thumb.addEventListener('error', () => {
                thumb.style.display = 'none';
                item.style.background = 'var(--bg-tertiary, #333)';
                const fallback = document.createElement('div');
                fallback.style.cssText = 'display:flex;align-items:center;justify-content:center;width:100%;height:100%;font-size:24px;opacity:0.3;';
                fallback.textContent = '🖼';
                item.insertBefore(fallback, item.firstChild);
            });

            const nameEl = document.createElement('div');
            nameEl.className = 'snapshot-filename';
            nameEl.textContent = img.filename;

            item.appendChild(thumb);
            item.appendChild(nameEl);
            item.addEventListener('click', () => handleItemClick(idx));
            grid.appendChild(item);
        });
        body.appendChild(grid);
        countEl.textContent = `共 ${imgs.length} 张图片`;
    }

    function close() {
        overlay.remove();
    }

    cancelBtn.addEventListener('click', () => {
        close();
        onCancel?.();
    });

    confirmBtn.addEventListener('click', () => {
        const selected = Array.from(selectedSet).map(idx => images[idx]);
        close();
        onConfirm?.(selected, worldX, worldY);
    });

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            close();
            onCancel?.();
        }
    });

    document.addEventListener('keydown', function escHandler(e) {
        if (e.key === 'Escape') {
            close();
            onCancel?.();
            document.removeEventListener('keydown', escHandler);
        }
    });

    body.innerHTML = '<div class="snapshot-loading"><div class="snapshot-spinner"></div><span>加载快照中...</span></div>';

    fetchSnapshots(canvasName).then(data => {
        if (data.success) {
            renderImages(data.images);
        } else {
            body.innerHTML = `<div class="snapshot-empty"><div class="snapshot-empty-icon">⚠️</div><div>加载失败</div></div>`;
            countEl.textContent = '加载失败';
        }
    }).catch(err => {
        console.error('[SnapshotPicker] fetch error:', err);
        body.innerHTML = `<div class="snapshot-empty"><div class="snapshot-empty-icon">⚠️</div><div>网络错误: ${err.message}</div></div>`;
        countEl.textContent = '加载失败';
    });
}
