import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

// Run the real notification store and SSE runtime with browser APIs isolated per test.
function setup({ permission = "granted", visible = false, focused = false, storageFails = false } = {}) {
  const window = new EventTarget();
  const document = { visibilityState: visible ? "visible" : "hidden", hasFocus: () => focused };
  const storage = new Map();
  const nativeNotices = [];
  const navigations = [];
  const channels = [];
  let focusCalls = 0;
  window.isSecureContext = true;
  window.setTimeout = setTimeout;
  window.clearTimeout = clearTimeout;
  window.focus = () => { focusCalls += 1; };
  window.location = { assign: (href) => navigations.push(href) };
  class FakeNotification {
    static permission = permission;
    constructor(title, options) {
      this.title = title;
      this.options = options;
      nativeNotices.push(this);
    }
    close() { this.closed = true; }
  }
  class FakeCustomEvent extends Event {
    constructor(name, init) { super(name, init); this.detail = init.detail; }
  }
  class FakeBroadcastChannel {
    constructor() { channels.push(this); }
    postMessage() {}
  }
  window.Notification = FakeNotification;
  const browserStorage = {
    getItem: (key) => { if (storageFails) throw new Error("storage denied"); return storage.get(key) ?? null; },
    setItem: (key, value) => { if (storageFails) throw new Error("storage denied"); storage.set(key, value); },
    removeItem: (key) => storage.delete(key),
  };
  const context = vm.createContext({
    window, document, Notification: FakeNotification, CustomEvent: FakeCustomEvent, Event,
    localStorage: browserStorage, sessionStorage: browserStorage,
    BroadcastChannel: FakeBroadcastChannel, Response, TextDecoder, AbortController, DOMException,
  });
  const modules = new Map();
  function load(name) {
    if (modules.has(name)) return modules.get(name).exports;
    const loadedModule = { exports: {} };
    modules.set(name, loadedModule);
    const source = fs.readFileSync(new URL(`../src/lib/${name}.ts`, import.meta.url), "utf8");
    const code = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    const requireModule = (id) => {
      if (id === "@/lib/api") return { describeDisconnectedError: (err) => err.message };
      return load(id.replace("@/lib/", ""));
    };
    vm.runInContext(`(function(require, module, exports) {${code}\n})`, context)(requireModule, loadedModule, loadedModule.exports);
    return loadedModule.exports;
  }
  const notifications = load("generation-notifications");
  notifications.setGenerationNotificationsEnabled(true);
  const notice = {
    id: "project:chat:1", projectId: "project", chatId: "chat",
    title: "Генерация завершена", body: "Ответ готов", outcome: "success",
  };
  return { notifications, nativeNotices, navigations, window, channels, notice, load, focusCalls: () => focusCalls };
}

function turnOptions(streamRequest, overrides = {}) {
  return {
    projectId: "project", chatId: "chat", chatTitle: "Мой сайт",
    userMessage: "Создай сайт", displayUserContent: "Создай сайт",
    attachments: [], seedMessages: [], createMessage: async () => {}, streamRequest, ...overrides,
  };
}

test("background completion creates a persistent browser alert and a cabinet notice", () => {
  const env = setup();
  let updates = 0;
  const unsubscribe = env.notifications.subscribeGenerationNotices(() => { updates += 1; });
  env.notifications.notifyGenerationFinished(env.notice);
  env.notifications.notifyGenerationFinished(env.notice);
  assert.equal(env.nativeNotices.length, 1, "duplicate completion is ignored");
  assert.equal(env.nativeNotices[0].options.requireInteraction, true);
  assert.equal(env.notifications.getGenerationNotices().length, 1);
  assert.equal(updates, 1);
  env.notifications.dismissGenerationNotice(env.notice.id);
  assert.equal(env.notifications.getGenerationNotices().length, 0);
  unsubscribe();
});

test("focused chat only gets a cabinet notice; another focused application gets a browser alert", () => {
  const focused = setup({ visible: true, focused: true });
  focused.notifications.notifyGenerationFinished(focused.notice);
  assert.equal(focused.nativeNotices.length, 0);
  assert.equal(focused.notifications.getGenerationNotices().length, 1);
  const otherApp = setup({ visible: true, focused: false });
  otherApp.notifications.notifyGenerationFinished(otherApp.notice);
  assert.equal(otherApp.nativeNotices.length, 1);
});

test("denied, unsupported, disabled and unavailable-storage browsers keep cabinet notices", () => {
  for (const permission of ["denied", "default"]) {
    const env = setup({ permission });
    env.notifications.notifyGenerationFinished(env.notice);
    assert.equal(env.nativeNotices.length, 0);
    assert.equal(env.notifications.getGenerationNotices().length, 1);
  }
  const disabled = setup();
  disabled.notifications.setGenerationNotificationsEnabled(false);
  disabled.notifications.notifyGenerationFinished(disabled.notice);
  assert.equal(disabled.nativeNotices.length, 0);
  const unsupported = setup();
  delete unsupported.window.Notification;
  unsupported.notifications.notifyGenerationFinished(unsupported.notice);
  assert.equal(unsupported.nativeNotices.length, 0);
  assert.equal(unsupported.notifications.getGenerationNotices().length, 1);
  const noStorage = setup({ storageFails: true });
  assert.equal(noStorage.notifications.generationNotificationsEnabled(), true);
});

test("notification click focuses and opens the exact chat, using SPA navigation when mounted", () => {
  for (const mounted of [true, false]) {
    const env = setup();
    const routed = [];
    if (mounted) env.window.addEventListener(env.notifications.OPEN_GENERATION_NOTICE_EVENT, (event) => {
      event.preventDefault(); routed.push(event.detail.href);
    });
    env.notifications.notifyGenerationFinished(env.notice);
    env.nativeNotices[0].onclick(new Event("click", { cancelable: true }));
    assert.equal(env.focusCalls(), 1);
    assert.equal(env.nativeNotices[0].closed, true);
    assert.equal(env.notifications.getGenerationNotices().length, 0);
    assert.equal((mounted ? routed : env.navigations)[0], "/app/projects/project/chat?chat=chat");
  }
});

test("successful SSE completion alerts once and includes the chat title", async () => {
  const env = setup();
  const runtime = env.load("chat-stream-runtime");
  await runtime.startChatTurn(turnOptions(async () => new Response('data: {"chunk":"Готово"}\n\ndata: [DONE]\n\n')));
  assert.equal(env.nativeNotices.length, 1);
  assert.equal(env.notifications.getGenerationNotices()[0].outcome, "success");
  assert.match(env.nativeNotices[0].options.body, /Мой сайт/);
  assert.equal(runtime.isChatStreamLoading("project", "chat"), false);
  // A follower tab mirrors completion; only the owner should alert.
  env.channels[0].onmessage({ data: {
    type: "state", projectId: "project", chatId: "chat",
    snapshot: runtime.getChatStreamSnapshot("project", "chat"),
  } });
  assert.equal(env.nativeNotices.length, 1);
});

test("HTTP failure, server failure and incomplete stream never announce success", async () => {
  const streams = [
    async () => new Response("Недостаточно кредитов", { status: 402 }),
    async () => new Response('data: {"status":{"phase":"error","state":"error","label":"Ошибка"}}\n\ndata: [DONE]\n\n'),
    async () => new Response('data: {"chunk":"Незавершённый ответ"}\n\n'),
  ];
  for (const streamRequest of streams) {
    const env = setup();
    await env.load("chat-stream-runtime").startChatTurn(turnOptions(streamRequest));
    assert.equal(env.notifications.getGenerationNotices()[0].outcome, "error");
    assert.equal(env.nativeNotices[0].title, "Генерация прервана");
  }
});

test("manual cancellation remains silent even if the fetch wrapper converts AbortError", async () => {
  const env = setup();
  const runtime = env.load("chat-stream-runtime");
  let started;
  const ready = new Promise((resolve) => { started = resolve; });
  const turn = runtime.startChatTurn(turnOptions((signal) => new Promise((resolve, reject) => {
    signal.addEventListener("abort", () => reject(new Error("Aborted")));
    started();
  })));
  await ready;
  runtime.abortChatStream("project", "chat");
  await turn;
  assert.equal(env.nativeNotices.length, 0);
  assert.equal(env.notifications.getGenerationNotices().length, 0);
  // Stop can race with a response that has already finished reading without throwing.
  await runtime.startChatTurn(turnOptions(async () => {
    runtime.abortChatStream("project", "chat");
    return new Response('data: [DONE]\n\n');
  }));
  assert.equal(env.nativeNotices.length, 0);
});

test("waiting for user input calls for action instead of announcing completion", async () => {
  const env = setup();
  await env.load("chat-stream-runtime").startChatTurn(turnOptions(async () => new Response(
    'data: {"status":{"phase":"waiting_for_user","state":"waiting","label":"Уточните задачу"}}\n\ndata: [DONE]\n\n'
  )));
  assert.equal(env.notifications.getGenerationNotices()[0].outcome, "attention");
  assert.equal(env.nativeNotices[0].title, "Нужно ваше действие");
});

test("repair completion also alerts after leaving the chat", async () => {
  const env = setup();
  await env.load("chat-stream-runtime").startRepairTurn({
    projectId: "project", chatId: "chat", userNote: "Исправь", seedMessages: [],
    streamRequest: async () => new Response('data: [DONE]\n\n'),
  });
  assert.equal(env.nativeNotices.length, 1);
  assert.equal(env.notifications.getGenerationNotices()[0].outcome, "success");
});
