const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const LOCAL_PORT = 8310;
const LOCAL_URL = `http://127.0.0.1:${LOCAL_PORT}`;

let localServer = null;

function repoRoot() {
  return path.resolve(__dirname, "..");
}

function pythonExecutable() {
  return path.join(repoRoot(), ".venv", "Scripts", "python.exe");
}

async function waitForServer(timeoutMs = 30000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`${LOCAL_URL}/api/health`);
      if (response.ok) {
        return;
      }
    } catch {
      // ignore until timeout
    }
    await new Promise((resolve) => setTimeout(resolve, 600));
  }
  throw new Error("로컬 JayAI 서버 기동 시간 초과");
}

function startLocalServer() {
  const python = pythonExecutable();
  localServer = spawn(
    python,
    ["-m", "jayai.cli", "local-ui", "--host", "127.0.0.1", "--port", String(LOCAL_PORT)],
    {
      cwd: repoRoot(),
      windowsHide: true,
      stdio: "ignore",
    }
  );

  localServer.on("exit", (code) => {
    if (!app.isQuitting && code !== 0) {
      dialog.showErrorBox("JayAI", `로컬 서버가 비정상 종료됨 (${code ?? "unknown"})`);
    }
  });
}

function stopLocalServer() {
  if (!localServer) {
    return;
  }
  localServer.kill();
  localServer = null;
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1280,
    minHeight: 840,
    autoHideMenuBar: true,
    backgroundColor: "#f3ede3",
    title: "JayAI",
  });

  await win.loadURL(LOCAL_URL);
}

app.whenReady().then(async () => {
  try {
    startLocalServer();
    await waitForServer();
    await createWindow();
  } catch (error) {
    dialog.showErrorBox("JayAI 시작 실패", String(error));
    app.quit();
  }
});

app.on("window-all-closed", () => {
  app.isQuitting = true;
  stopLocalServer();
  app.quit();
});

app.on("before-quit", () => {
  app.isQuitting = true;
  stopLocalServer();
});
