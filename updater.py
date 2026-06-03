import requests
import subprocess
import tempfile
import os
import re
import sys
import warnings

from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QProgressBar

try:
    from urllib3.exceptions import InsecureRequestWarning
except Exception:  # pragma: no cover
    InsecureRequestWarning = None

if InsecureRequestWarning is not None:
    warnings.filterwarnings("ignore", category=InsecureRequestWarning)


REQUESTS_VERIFY = False


def _main_application_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]

    script_path = os.path.abspath(sys.argv[0])
    return [sys.executable, script_path]


def _main_application_cwd() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _clean_launch_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env.keys()):
        if key.startswith("PYINSTALLER_") or key.startswith("_MEIPASS"):
            env.pop(key, None)

    env.pop("QT_PLUGIN_PATH", None)
    env.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
    env.pop("QTWEBENGINEPROCESS_PATH", None)
    return env


def _request(method: str, url: str, **kwargs):
    kwargs.setdefault("timeout", 60)
    kwargs.setdefault("verify", REQUESTS_VERIFY)
    return requests.request(method, url, **kwargs)


def _normalize_version(value: str) -> str:
    return value.strip().lower().lstrip("v")


def _version_key(version: str) -> tuple[int, ...]:
    normalized = _normalize_version(version)
    parts = re.findall(r"\d+", normalized)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def is_update_available(current_version: str, latest_version: str) -> bool:
    return _version_key(latest_version) > _version_key(current_version)


def _get_latest_release(owner: str, repo: str) -> dict:
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    resp = _request("GET", api_url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_latest_release_version(owner: str, repo: str) -> str:
    data = _get_latest_release(owner, repo)
    return str(data.get("tag_name") or data.get("name") or "0.0.0")


def get_latest_release_asset(owner: str, repo: str) -> tuple[str, str, str]:
    data = _get_latest_release(owner, repo)
    latest_version = str(data.get("tag_name") or data.get("name") or "0.0.0")
    assets = data.get("assets", [])
    if not assets:
        raise RuntimeError("No release assets found")

    asset = None
    for candidate in assets:
        name = candidate.get("name", "").lower()
        if name.endswith('.exe') or 'setup' in name:
            asset = candidate
            break
    if asset is None:
        asset = assets[0]

    download_url = asset.get("browser_download_url")
    asset_name = asset.get("name", "installer.exe")
    if not download_url:
        raise RuntimeError("No download URL for asset")

    return latest_version, download_url, asset_name


def _build_launcher_command(download_url: str, latest_version: str, asset_name: str, current_version: str) -> list[str]:
    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        command = [sys.executable, os.path.abspath(sys.argv[0])]

    return command + [
        "--update-mode",
        "--download-url", download_url,
        "--latest-version", latest_version,
        "--asset-name", asset_name,
        "--current-version", current_version,
    ]


def launch_update_mode(download_url: str, latest_version: str, asset_name: str, current_version: str) -> None:
    command = _build_launcher_command(download_url, latest_version, asset_name, current_version)
    subprocess.Popen(command, close_fds=True)


class DownloadWorker(QThread):
    status_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(int)
    finished_download = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, download_url: str, asset_name: str):
        super().__init__()
        self.download_url = download_url
        self.asset_name = asset_name

    def run(self):
        fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(self.asset_name)[1] or '.bin')
        os.close(fd)

        try:
            self.status_changed.emit("Download aggiornamento in corso...")
            with _request("GET", self.download_url, stream=True) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", "0") or 0)
                downloaded = 0
                with open(tmp_path, "wb") as output_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        output_file.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = int(downloaded * 100 / total)
                            self.progress_changed.emit(min(percent, 99))

            self.progress_changed.emit(100)
            self.finished_download.emit(tmp_path)
        except Exception as exc:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            self.failed.emit(str(exc))


class UpdateDialog(QDialog):
    def __init__(self, download_url: str, latest_version: str, asset_name: str, current_version: str):
        super().__init__()
        self.download_url = download_url
        self.latest_version = latest_version
        self.asset_name = asset_name
        self.current_version = current_version
        self.installer_process = None

        self.setWindowTitle("Aggiornamento Gestione Inventario")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)

        self.status_label = QLabel("Preparazione aggiornamento...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.detail_label = QLabel(f"Versione attuale: {self.current_version}  ->  Nuova versione: {self.latest_version}")

        layout = QVBoxLayout(self)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        self.worker = DownloadWorker(self.download_url, self.asset_name)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.finished_download.connect(self._on_download_finished)
        self.worker.failed.connect(self._on_failed)

        QTimer.singleShot(0, self.worker.start)

    def _on_failed(self, message: str):
        self.status_label.setText("Aggiornamento fallito")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.detail_label.setText(message)
        QTimer.singleShot(2500, self.reject)

    def _on_download_finished(self, installer_path: str):
        self.status_label.setText("Download completato. Avvio installatore...")
        self.progress_bar.setRange(0, 0)

        try:
            self.installer_process = subprocess.Popen(
                [installer_path, '/SILENT', '/NORESTART', '/SP-'],
                close_fds=True,
            )
            self.status_label.setText("Installazione in corso...")
            self._watch_installer()
        except Exception as exc:
            self._on_failed(str(exc))

    def _watch_installer(self):
        if self.installer_process is None:
            self.reject()
            return

        if self.installer_process.poll() is None:
            QTimer.singleShot(1000, self._watch_installer)
            return

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText("Aggiornamento completato")
        QTimer.singleShot(1500, self._restart_and_close)

    def _restart_and_close(self):
        try:
            subprocess.Popen(
                _main_application_command(),
                close_fds=True,
                cwd=_main_application_cwd(),
                env=_clean_launch_env(),
            )
        except Exception as exc:
            self._on_failed(str(exc))
            return

        self.accept()


def run_update_mode(download_url: str, latest_version: str, asset_name: str, current_version: str) -> int:
    app = QApplication(sys.argv)
    dialog = UpdateDialog(download_url, latest_version, asset_name, current_version)
    dialog.resize(480, 160)
    dialog.show()
    return app.exec()


def download_and_run_update(owner: str, repo: str) -> tuple[str, str]:
    latest_version, download_url, asset_name = get_latest_release_asset(owner, repo)
    fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(asset_name)[1] or '.bin')
    os.close(fd)

    with _request("GET", download_url, stream=True) as r:
        r.raise_for_status()
        with open(tmp_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    try:
        os.chmod(tmp_path, 0o755)
    except Exception:
        pass

    try:
        subprocess.Popen([tmp_path, '/SILENT', '/NORESTART', '/SP-'], close_fds=True)
    except Exception:
        subprocess.Popen([tmp_path], close_fds=True)

    return tmp_path, latest_version
