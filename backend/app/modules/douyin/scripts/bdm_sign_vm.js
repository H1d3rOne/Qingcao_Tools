const fs = require("fs");
const path = require("path");
const vm = require("vm");
const nodeCrypto = require("crypto");

const BDM_PATH = path.join(__dirname, getOption("bdm", "bdm.js"));
const API_PATH = path.join(__dirname, "api.txt");

function readProfile() {
  const raw = process.env.DOUYIN_BDM_PROFILE || getOption("profile", "");
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`invalid DOUYIN_BDM_PROFILE: ${err.message}`);
  }
}

function getInputUrl() {
  const argUrl = process.argv.slice(2).find((arg) => !arg.startsWith("--"));
  if (argUrl) return argUrl.trim();
  const line = Number(getOption("line", "1"));
  const text = fs.readFileSync(API_PATH, "utf8");
  const urls = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const selected = urls[line - 1];
  if (!selected) throw new Error(`api.txt does not contain URL line ${line}`);
  return selected;
}

function getOption(name, fallback) {
  const prefix = `--${name}=`;
  const hit = process.argv.find((arg) => arg.startsWith(prefix));
  if (hit) return hit.slice(prefix.length);
  return fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function stripOldSignature(rawUrl, options = {}) {
  const url = new URL(rawUrl);
  if (!options.keepABogus) url.searchParams.delete("a_bogus");
  if (options.dropSecSdk) {
    url.searchParams.delete("timestamp");
    url.searchParams.delete("x-secsdk-web-signature");
  }
  return url;
}

function toNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeLanguage(value) {
  return value || "zh-CN";
}

function makeBrowserEnv(rawUrl, body, userAgent, msToken, pageUrl, profile = {}) {
  const target = new URL(rawUrl);
  const page = new URL(pageUrl || `${target.origin}/`);
  let signedUrl = "";
  const navigationStart = Date.now() - 800;
  const browserLanguage = normalizeLanguage(profile.browser_language);
  const languages = Array.isArray(profile.languages) && profile.languages.length
    ? profile.languages
    : [browserLanguage, "zh"];
  const screenWidth = toNumber(profile.screen_width, 1707);
  const screenHeight = toNumber(profile.screen_height, 960);
  const availWidth = toNumber(profile.avail_width, screenWidth);
  const availHeight = toNumber(profile.avail_height, Math.max(screenHeight - 48, 0));
  const innerWidth = toNumber(profile.inner_width, screenWidth);
  const innerHeight = toNumber(profile.inner_height, Math.max(screenHeight - 151, 0));
  const outerWidth = toNumber(profile.outer_width, screenWidth);
  const outerHeight = toNumber(profile.outer_height, availHeight);
  const clientWidth = toNumber(profile.client_width, Math.max(innerWidth - 10, 0));
  const clientHeight = toNumber(profile.client_height, innerHeight);

  function FakeXHR() {}
  FakeXHR.prototype.open = function open(method, url, async) {
    this._method = method;
    this._url = url;
    this._async = async;
  };
  FakeXHR.prototype.setRequestHeader = function setRequestHeader() {};
  FakeXHR.prototype.getResponseHeader = function getResponseHeader(name) {
    return String(name).toLowerCase() === "x-ms-token" ? msToken || "" : null;
  };
  FakeXHR.prototype.addEventListener = function addEventListener(event, fn) {
    if (event === "load") this._load = fn;
  };
  FakeXHR.prototype.send = function send(payload) {
    if (this._load) this._load({});
  };

  const pluginArray = [
    { name: "PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
    { name: "Chrome PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
    { name: "Chromium PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
    { name: "Microsoft Edge PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
    { name: "WebKit built-in PDF", filename: "internal-pdf-viewer", description: "Portable Document Format" },
  ];
  pluginArray.item = (index) => pluginArray[index] || null;
  pluginArray.namedItem = (name) => pluginArray.find((item) => item.name === name) || null;

  const mimeTypeArray = [
    { type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" },
    { type: "text/pdf", suffixes: "pdf", description: "Portable Document Format" },
  ];
  mimeTypeArray.item = (index) => mimeTypeArray[index] || null;
  mimeTypeArray.namedItem = (type) => mimeTypeArray.find((item) => item.type === type) || null;

  function makeCanvasContext(type) {
    const isWebgl = String(type).toLowerCase().includes("webgl");
    if (isWebgl) {
      const debugInfo = {
        UNMASKED_VENDOR_WEBGL: 0x9245,
        UNMASKED_RENDERER_WEBGL: 0x9246,
      };
      return {
        VENDOR: 0x1f00,
        RENDERER: 0x1f01,
        VERSION: 0x1f02,
        SHADING_LANGUAGE_VERSION: 0x8b8c,
        MAX_TEXTURE_SIZE: 0x0d33,
        MAX_VIEWPORT_DIMS: 0x0d3a,
        canvas: null,
        getContextAttributes() {
          return { alpha: true, antialias: true, depth: true, premultipliedAlpha: true, preserveDrawingBuffer: false };
        },
        getExtension(name) {
          return name === "WEBGL_debug_renderer_info" ? debugInfo : null;
        },
        getParameter(parameter) {
          if (parameter === debugInfo.UNMASKED_VENDOR_WEBGL || parameter === this.VENDOR) return "Google Inc. (Intel)";
          if (parameter === debugInfo.UNMASKED_RENDERER_WEBGL || parameter === this.RENDERER) {
            return "ANGLE (Intel, Intel(R) UHD Graphics 730 (0x00004682) Direct3D11 vs_5_0 ps_5_0, D3D11)";
          }
          if (parameter === this.VERSION) return "WebGL 1.0 (OpenGL ES 2.0 Chromium)";
          if (parameter === this.SHADING_LANGUAGE_VERSION) return "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)";
          if (parameter === this.MAX_TEXTURE_SIZE) return 16384;
          if (parameter === this.MAX_VIEWPORT_DIMS) return new Int32Array([32767, 32767]);
          return 0;
        },
        getSupportedExtensions() {
          return ["ANGLE_instanced_arrays", "EXT_blend_minmax", "WEBGL_debug_renderer_info"];
        },
        createBuffer() {
          return {};
        },
        bindBuffer() {},
        bufferData() {},
        clearColor() {},
        clear() {},
      };
    }

    return {
      fillRect() {},
      fillText() {},
      beginPath() {},
      arc() {},
      closePath() {},
      fill() {},
      isPointInPath() {
        return false;
      },
      toDataURL() {
        return "data:image/png;base64,abc";
      },
      getImageData() {
        return { data: [1, 2, 3, 4] };
      },
      getContextAttributes() {
        return {};
      },
      getParameter() {
        return 0;
      },
      getExtension() {
        return null;
      },
      measureText() {
        return { width: 1 };
      },
      canvas: null,
    };
  }

  const win = {
    location: {
      pathname: page.pathname,
      href: page.href,
      protocol: page.protocol,
      host: page.host,
      hostname: page.hostname,
      origin: page.origin,
      search: page.search,
    },
    __ac_referer: "",
  };
  win.window = win;
  win.self = win;
  win.top = win;
  win.parent = win;
  win.globalThis = win;
  win.navigator = {
    userAgent,
    appCodeName: "Mozilla",
    appName: "Netscape",
    appVersion: userAgent.replace(/^Mozilla\//, ""),
    language: browserLanguage,
    languages,
    platform: profile.browser_platform || "Win32",
    product: "Gecko",
    vendor: "Google Inc.",
    webdriver: false,
    hardwareConcurrency: toNumber(profile.cpu_core_num, 8),
    deviceMemory: toNumber(profile.device_memory, 8),
    maxTouchPoints: 0,
    cookieEnabled: true,
    plugins: pluginArray,
    mimeTypes: mimeTypeArray,
    sendBeacon() {
      return true;
    },
  };
  win.screen = {
    width: screenWidth,
    height: screenHeight,
    availWidth,
    availHeight,
    colorDepth: toNumber(profile.color_depth, 24),
    pixelDepth: toNumber(profile.pixel_depth, 24),
  };
  win.document = {
    all: false,
    domain: page.hostname,
    cookie: profile.cookie || "",
    referrer: profile.referrer || getOption("referrer", ""),
    location: win.location,
    visibilityState: "visible",
    characterSet: "UTF-8",
    compatMode: "CSS1Compat",
    images: [],
    documentElement: { clientWidth, clientHeight },
    body: { clientWidth, clientHeight, appendChild() {}, removeChild() {} },
    createElement(tag) {
      const element = {
        tagName: String(tag).toUpperCase(),
        style: {},
        setAttribute() {},
        appendChild() {},
        removeChild() {},
        remove() {},
        canPlayType() {
          return "";
        },
        contentWindow: { document: { open() {}, write() {}, close() {} } },
      };
      element.getContext = (type) => {
        const context = makeCanvasContext(type);
        if (context && typeof context === "object") context.canvas = element;
        return context;
      };
      return element;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  win.XMLHttpRequest = FakeXHR;
  win.fetch = function fetch(url, init) {
    signedUrl = String(url && url.href ? url.href : url);
    return Promise.resolve({
      clone() {
        return this;
      },
      text() {
        return Promise.resolve("");
      },
      headers: {
        get() {
          return "text/plain";
        },
      },
    });
  };

  Object.assign(win, {
    addEventListener() {},
    removeEventListener() {},
    postMessage() {},
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    requestAnimationFrame: (fn) => setTimeout(fn, 16),
    cancelAnimationFrame: clearTimeout,
    innerWidth,
    innerHeight,
    outerWidth,
    outerHeight,
    devicePixelRatio: toNumber(profile.device_pixel_ratio, 1),
    pageXOffset: 0,
    pageYOffset: 0,
    screenX: 0,
    screenY: 0,
    performance: { now: () => Date.now() - navigationStart, timing: { navigationStart } },
    crypto: {
      getRandomValues(arr) {
        return nodeCrypto.webcrypto.getRandomValues(arr);
      },
      subtle: nodeCrypto.webcrypto.subtle,
    },
    localStorage: {
      getItem: (key) => (key === "xmst" ? msToken || null : null),
      setItem() {},
      removeItem() {},
    },
    sessionStorage: {
      getItem: () => null,
      setItem() {},
      removeItem() {},
    },
    URL,
    Request: function Request(input, init) {
      this.url = String(input);
      Object.assign(this, init || {});
    },
  });

  const ctx = {
    ...win,
    window: win,
    self: win,
    globalThis: win,
    console,
    Math,
    Date,
    Uint8Array,
    Uint16Array,
    Int32Array,
    TextDecoder,
    TextEncoder,
    Map,
    Set,
    Array,
    Object,
    String,
    Number,
    Boolean,
    RegExp,
    Error,
    TypeError,
    ReferenceError,
    SyntaxError,
    JSON,
    Promise,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    queueMicrotask,
    atob,
    btoa,
    encodeURIComponent,
    decodeURIComponent,
    URL,
    Request: win.Request,
  };

  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(BDM_PATH, "utf8"), ctx);

  return { win, getSignedUrl: () => signedUrl };
}

async function main() {
  const input = getInputUrl();
  const profile = readProfile();
  const body = getOption("body", "");
  const userAgent =
    getOption("ua", process.argv[4]) ||
    profile.user_agent ||
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36";
  const pageId = getOption("page-id", "douyin_pc");

  const unsigned = stripOldSignature(input, {
    keepABogus: hasFlag("keep-existing"),
    dropSecSdk: hasFlag("drop-secsdk"),
  });
  const msToken = unsigned.searchParams.get("msToken") || profile.msToken || "";

  const pageUrl = getOption("page-url", profile.page_url || profile.referer || `${unsigned.origin}/`);
  const { win, getSignedUrl } = makeBrowserEnv(unsigned.href, body, userAgent, msToken, pageUrl, {
    ...profile,
    referrer: profile.referrer || pageUrl,
  });
  win.bdms.init({
    aid: Number(unsigned.searchParams.get("aid") || 6383),
    pageId,
    paths: { include: [unsigned.pathname], exclude: [] },
    mode: "all",
    track: true,
    delay: 0,
  });

  await win.fetch(unsigned.href, { method: body ? "POST" : "GET", body: body || undefined });
  await new Promise((resolve) => setTimeout(resolve, 20));

  const signed = getSignedUrl();
  if (!signed) throw new Error("bdm.js did not sign the URL");

  const signedUrl = new URL(signed);
  console.log("a_bogus =", signedUrl.searchParams.get("a_bogus"));
  console.log("signed_url =", signed);
  process.exit(0);
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : err);
  process.exitCode = 1;
});
