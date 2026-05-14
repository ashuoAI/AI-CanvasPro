import test from 'node:test';
import assert from 'node:assert/strict';
import {
  bindPreviewUploadEntry,
  handlePreviewUploadFile,
  handlePreviewUploadFiles,
  resolvePreviewUploadTarget
} from './previewUploadEntry.js';
import { _resetPreviewRuntimeForTests, setPreviewMode } from './previewMode.js';
import { IMAGE_TOOLBAR_HTML } from '../components/nodeToolbar/imageToolbarHtml.js';
import { VIDEO_TOOLBAR_HTML } from '../components/nodeToolbar/videoToolbarHtml.js';
import { AUDIO_TOOLBAR_HTML } from '../components/nodeToolbar/audioToolbar.js';
import { installPreviewDomStubs } from '../../tests/testPreviewDom.js';

const restoreDom = installPreviewDomStubs();

test.afterEach(() => { _resetPreviewRuntimeForTests(); });
test.after(() => { _resetPreviewRuntimeForTests(); restoreDom(); });

function createFile({ name = 'p.png', type = 'image/png' } = {}) {
  return { name, type };
}

function createButtonStub() {
  return { dataset: {}, disabled: false, textContent: '上传' };
}

function createEventTargetStub() {
  const listeners = new Map();
  return {
    accept: '',
    value: '',
    files: [],
    clicked: false,
    dataset: {},
    disabled: false,
    textContent: '',
    addEventListener(event, handler) { listeners.set(event, handler); },
    removeEventListener(event, handler) { if (listeners.get(event) === handler) listeners.delete(event); },
    click() { this.clicked = true; },
    setAttribute() {},
    async dispatch(event) { await listeners.get(event)?.(); }
  };
}

function createStoreState({ selectedNodeIds = [], nodes = {} } = {}) {
  return { getState: () => ({ selectedNodeIds, nodes }) };
}

test('previewUploadEntry: 会校验唯一选中的可上传节点', () => {
  assert.equal(resolvePreviewUploadTarget(createStoreState().getState()).ok, false);
  assert.equal(resolvePreviewUploadTarget(createStoreState({ selectedNodeIds: ['a', 'b'] }).getState()).ok, false);
  assert.equal(resolvePreviewUploadTarget(createStoreState({ selectedNodeIds: ['text-1'], nodes: { 'text-1': { id: 'text-1', type: 'ai-text' } } }).getState()).ok, false);
});

test('previewUploadEntry: 图片、视频、音频按选中节点类型分发', async () => {
  const log = [];
  const mockUpload = async (file, projectId) => {
    log.push(['upload', file.name, projectId]);
    return { url: '/data/uploads/' + file.name, localPath: 'data/uploads/' + file.name };
  };
  const applyResults = {
    image: r => log.push(['image', r.nodeId, r.fileName]),
    video: r => log.push(['video', r.nodeId, r.fileName]),
    audio: r => log.push(['audio', r.nodeId, r.fileName])
  };
  const toast = (msg, level) => log.push(['toast', msg, level]);

  const cases = [
    ['image', 'ai-image', createFile({ name: 'preview.png', type: 'image/png' })],
    ['image', 'source-image', createFile({ name: 'source-p.png', type: 'image/png' })],
    ['video', 'ai-video', createFile({ name: 'v.mp4', type: 'video/mp4' })],
    ['video', 'source-video', createFile({ name: 'source-v.mp4', type: 'video/mp4' })],
    ['audio', 'ai-audio', createFile({ name: 'a.mp3', type: 'audio/mpeg' })]
  ];

  for (const [kind, nodeType, file] of cases) {
    log.length = 0;
    const result = await handlePreviewUploadFile({
      file,
      storeApi: createStoreState({
        selectedNodeIds: ['node-' + kind],
        nodes: { ['node-' + kind]: { id: 'node-' + kind, type: nodeType } }
      }),
      uploadFileImpl: mockUpload,
      applyResults,
      showToast: toast,
      getProjectId: () => 'project-1'
    });
    assert.equal(result, true);
    assert.deepEqual(log, [
      ['upload', file.name, 'project-1'],
      [kind, 'node-' + kind, file.name],
      ['toast', '已将上传' + (kind === 'image' ? '图片' : kind === 'video' ? '视频' : '音频') + '写入当前节点', 'success']
    ]);
  }
});

test('previewUploadEntry: 文件类型错误与上传失败不会写入结果且按钮会恢复', async () => {
  const log = [];
  const button = createButtonStub();
  const store = createStoreState({
    selectedNodeIds: ['node-image'],
    nodes: { 'node-image': { id: 'node-image', type: 'ai-image' } }
  });
  const toast = (msg, level) => log.push([msg, level]);

  const result1 = await handlePreviewUploadFile({
    file: createFile({ name: 'bad.mp4', type: 'video/mp4' }),
    button,
    storeApi: store,
    uploadFileImpl: async () => { throw new Error('不应上传'); },
    applyResults: { image: () => log.push(['apply']) },
    showToast: toast
  });
  assert.equal(result1, false);
  assert.equal(button.disabled, false);
  assert.deepEqual(log, [['请上传图片文件', 'error']]);

  log.length = 0;
  const result2 = await handlePreviewUploadFile({
    file: createFile({ name: 'preview.png', type: 'image/png' }),
    button,
    storeApi: store,
    uploadFileImpl: async () => { throw new Error('上传失败'); },
    applyResults: { image: () => log.push(['apply']) },
    showToast: toast
  });
  assert.equal(result2, false);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, '上传');
  assert.deepEqual(log, [['上传失败', 'error']]);
});

test('previewUploadEntry: 绑定按钮点击后会创建带 multiple 的文件输入并打开选择', async () => {
  setPreviewMode(true);
  const createdInputs = [];
  const origCreate = globalThis.document.createElement;
  const origAppend = globalThis.document.body.appendChild;
  globalThis.document.createElement = (tag) => {
    const el = origCreate(tag);
    if (tag === 'input') {
      el.addEventListener = (event, handler) => { el['_' + event] = handler; };
      el.click = () => { el.clicked = true; };
      createdInputs.push(el);
    }
    return el;
  };
  globalThis.document.body.appendChild = (el) => { el.inDom = true; };

  const button = createEventTargetStub();
  button.dataset = {};
  button.textContent = '上传';
  const input = createEventTargetStub();
  bindPreviewUploadEntry({
    button,
    input,
    storeApi: createStoreState({
      selectedNodeIds: ['node-video'],
      nodes: { 'node-video': { id: 'node-video', type: 'ai-video' } }
    }),
    showToast: () => {}
  });
  await button.dispatch('click');

  assert.equal(createdInputs.length, 1);
  const fileInput = createdInputs[0];
  assert.equal(fileInput.type, 'file');
  assert.equal(fileInput.multiple, true);
  assert.equal(fileInput.accept, 'video/*');
  assert.equal(fileInput.clicked, true);

  globalThis.document.createElement = origCreate;
  globalThis.document.body.appendChild = origAppend;
});

test('previewUploadEntry: 节点工具栏不再包含预览上传按钮', () => {
  for (const html of [IMAGE_TOOLBAR_HTML, VIDEO_TOOLBAR_HTML, AUDIO_TOOLBAR_HTML]) {
    assert.doesNotMatch(html, /act-preview-upload/);
    assert.doesNotMatch(html, /preview-upload-btn/);
  }
});

test('previewUploadEntry: handlePreviewUploadFiles 批量上传多个文件', async () => {
  const log = [];
  const mockUpload = async (file, projectId) => {
    log.push(['upload', file.name, projectId]);
    return { url: '/data/uploads/' + file.name, localPath: 'data/uploads/' + file.name };
  };
  const applyResults = {
    image: r => log.push(['apply', r.nodeId, r.fileName])
  };
  const toast = (msg, level) => log.push(['toast', msg, level]);
  const button = createButtonStub();

  const files = [
    createFile({ name: 'a.png', type: 'image/png' }),
    createFile({ name: 'b.png', type: 'image/png' }),
    createFile({ name: 'c.png', type: 'image/png' })
  ];

  const result = await handlePreviewUploadFiles({
    files,
    button,
    storeApi: createStoreState({
      selectedNodeIds: ['node-image'],
      nodes: { 'node-image': { id: 'node-image', type: 'ai-image' } }
    }),
    uploadFileImpl: mockUpload,
    applyResults,
    showToast: toast,
    getProjectId: () => 'project-1'
  });

  assert.deepEqual(result, { succeeded: 3, failed: 0, total: 3 });
  assert.equal(button.disabled, false);
  assert.equal(log.filter(l => l[0] === 'upload').length, 3);
  assert.equal(log.filter(l => l[0] === 'apply').length, 3);
  assert.deepEqual(log.filter(l => l[0] === 'toast'), [['toast', '已将上传图片写入当前节点', 'success']]);
});

test('previewUploadEntry: handlePreviewUploadFiles 过滤不匹配类型的文件', async () => {
  const log = [];
  const mockUpload = async (file, projectId) => {
    log.push(['upload', file.name, projectId]);
    return { url: '/data/uploads/' + file.name, localPath: 'data/uploads/' + file.name };
  };
  const applyResults = {
    image: r => log.push(['apply', r.nodeId, r.fileName])
  };
  const toast = (msg, level) => log.push(['toast', msg, level]);

  const files = [
    createFile({ name: 'good.png', type: 'image/png' }),
    createFile({ name: 'bad.mp4', type: 'video/mp4' }),
    createFile({ name: 'also-good.jpg', type: 'image/jpeg' })
  ];

  const result = await handlePreviewUploadFiles({
    files,
    storeApi: createStoreState({
      selectedNodeIds: ['node-image'],
      nodes: { 'node-image': { id: 'node-image', type: 'ai-image' } }
    }),
    uploadFileImpl: mockUpload,
    applyResults,
    showToast: toast,
    getProjectId: () => 'project-1'
  });

  assert.deepEqual(result, { succeeded: 2, failed: 0, total: 3 });
  assert.equal(log.filter(l => l[0] === 'upload').length, 2);
  assert.equal(log.filter(l => l[0] === 'apply').length, 2);
});

test('previewUploadEntry: handlePreviewUploadFiles 部分上传失败仍继续处理', async () => {
  const log = [];
  let uploadCount = 0;
  const mockUpload = async (file, projectId) => {
    uploadCount++;
    if (uploadCount === 2) throw new Error('上传失败');
    log.push(['upload', file.name, projectId]);
    return { url: '/data/uploads/' + file.name, localPath: 'data/uploads/' + file.name };
  };
  const applyResults = {
    image: r => log.push(['apply', r.nodeId, r.fileName])
  };
  const toast = (msg, level) => log.push(['toast', msg, level]);
  const button = createButtonStub();

  const files = [
    createFile({ name: 'a.png', type: 'image/png' }),
    createFile({ name: 'b.png', type: 'image/png' }),
    createFile({ name: 'c.png', type: 'image/png' })
  ];

  const result = await handlePreviewUploadFiles({
    files,
    button,
    storeApi: createStoreState({
      selectedNodeIds: ['node-image'],
      nodes: { 'node-image': { id: 'node-image', type: 'ai-image' } }
    }),
    uploadFileImpl: mockUpload,
    applyResults,
    showToast: toast,
    getProjectId: () => 'project-1'
  });

  assert.deepEqual(result, { succeeded: 2, failed: 1, total: 3 });
  assert.equal(button.disabled, false);
  assert.equal(log.filter(l => l[0] === 'apply').length, 2);
  assert.ok(log.some(l => l[0] === 'toast' && l[2] === 'success'));
  assert.ok(log.some(l => l[0] === 'toast' && l[1] === '1个文件上传失败' && l[2] === 'error'));
});

test('previewUploadEntry: handlePreviewUploadFiles 无有效文件时提示类型错误', async () => {
  const log = [];
  const toast = (msg, level) => log.push(['toast', msg, level]);

  const files = [
    createFile({ name: 'bad.mp4', type: 'video/mp4' }),
    createFile({ name: 'bad2.mp4', type: 'video/mp4' })
  ];

  const result = await handlePreviewUploadFiles({
    files,
    storeApi: createStoreState({
      selectedNodeIds: ['node-image'],
      nodes: { 'node-image': { id: 'node-image', type: 'ai-image' } }
    }),
    showToast: toast,
    getProjectId: () => 'project-1'
  });

  assert.deepEqual(result, { succeeded: 0, failed: 2, total: 2 });
  assert.deepEqual(log, [['toast', '请上传图片文件', 'error']]);
});

test('previewUploadEntry: handlePreviewUploadFiles 无选中节点时返回失败', async () => {
  const result = await handlePreviewUploadFiles({
    files: [createFile()],
    storeApi: createStoreState(),
    showToast: () => {},
    getProjectId: () => 'project-1'
  });

  assert.deepEqual(result, { succeeded: 0, failed: 0, total: 0 });
});
