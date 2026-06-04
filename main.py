from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox
from FileManager import File
import pandas as pd

import sys
import os
import tomllib

import updater

import MainWindow as MainWindow


def _project_root_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _load_app_version() -> str:
    try:
        from app_version import APP_VERSION as packaged_version

        packaged_version = str(packaged_version).strip()
        if packaged_version:
            return packaged_version
    except Exception:
        pass

    pyproject_path = os.path.join(_project_root_dir(), "pyproject.toml")
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        project = data.get("project", {})
        version = str(project.get("version", "")).strip()
        if version:
            return version
    except Exception:
        pass
    return "0.0.0"


APP_VERSION = _load_app_version()


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = MainWindow.Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.file1_button.clicked.connect(self.getFile1)
        self.ui.file2_button.clicked.connect(self.getFile2)
        self.ui.swap_button.clicked.connect(self.swapFile)
        self.ui.create_button.clicked.connect(self.create)
        self.ui.app_update_button.triggered.connect(self.update_app)

        self.considered_colums: list[str] = ["Codice", "Descrizione articolo", "Esistenza", "Prezzo", "Valore"]

    def getFile1(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File 1", "", "CSV Files (*.csv)")
        if file_path:
            file_path = os.path.abspath(file_path)
            self.file1_path = file_path
            try:
                self.ui.file1_lineEdit.setText(file_path)
            except Exception:
                pass

    def getFile2(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File 2", "", "CSV Files (*.csv)")
        if file_path:
            file_path = os.path.abspath(file_path)
            self.file2_path = file_path
            try:
                self.ui.file2_lineEdit.setText(file_path)
            except Exception:
                pass

    def swapFile(self):
        temp = self.ui.file1_lineEdit.text()
        self.ui.file1_lineEdit.setText(self.ui.file2_lineEdit.text())
        self.ui.file2_lineEdit.setText(temp)

    def create(self):
        file1_lines: list[str] = self.getFileLines(self.ui.file1_lineEdit.text())
        file2_lines: list[str] = self.getFileLines(self.ui.file2_lineEdit.text())

        file1_dict: dict[str, list] = self.getFileDict(file1_lines)
        file2_dict: dict[str, list] = self.getFileDict(file2_lines)

        df_1 = pd.DataFrame(file1_dict)
        df_2 = pd.DataFrame(file2_dict)

        df_merged = pd.merge(df_1, df_2, on=self.considered_colums[0], how="outer", indicator=True)
        df_merged.fillna("", inplace=True)
        df_dict = df_merged.to_dict(orient="list")

        out_path, _ = QFileDialog.getSaveFileName(self, "Salva il File", "", "CSV File (*.csv)")
        if not out_path:
            return

        out_file = File(out_path)

        out_file.write(";".join(str(x) for x in self.considered_colums[:5]*2) + "\n")

        merge_key = self.considered_colums[0]

        file1_key = [merge_key] + [f"{col}_x" for col in self.considered_colums[1:]]
        file2_key = [merge_key] + [f"{col}_y" for col in self.considered_colums[1:]]

        for i in range(self.getDictLen(df_dict)):
            merge_type = df_dict["_merge"][i]

            values_f1 = []
            if merge_type == "right_only":
                values_f1 = [""] * len(file1_key)
            else:
                for col in file1_key:
                    value = df_dict[col][i]
                    values_f1.append(str(value))

            values_f2 = []
            if merge_type == "left_only":
                values_f2 = [""] * len(file2_key)
            else:
                for col in file2_key:
                    value = df_dict[col][i]
                    values_f2.append(str(value))

            out_file.append(";".join(values_f1 + values_f2)+"\n")

    def getFileLines(self, filename: str) -> list[str]:
        file_lines: list[str] = File(filename) .read().split("\n")
        file_lines = file_lines[6:]
        file_lines.pop(1)
        file_lines = file_lines[:-5]
        return file_lines

    def getFileDict(self, file_lines: list[str]) -> dict:
        file_columns: dict = {}
        for column in self.considered_colums:
            values: list[str] = []
            try:
                column_index = file_lines[0].split(";").index(column)
                for line in file_lines:
                    values.append(line.split(";")[column_index])
                file_columns[column] = values
            except ValueError:
                pass
        return file_columns

    def getDictLen(self, dict: dict) -> int:
        size = 0
        for value in dict.values():
            if (len(value) > size):
                size = len(value)
        return size

    def update_app(self):
        # Check latest release synchronously, then hand off to a dedicated updater window.
        self.ui.app_update_button.setEnabled(False)
        owner = "LcBert"
        repo = "Gestione-Inventario"
        try:
            latest_version, download_url, asset_name = updater.get_latest_release_asset(owner, repo)
            has_update = updater.is_update_available(APP_VERSION, latest_version)
            if not has_update:
                QMessageBox.information(self, "Aggiornamento", "Ultima versione gia installata")
                return

            answer = QMessageBox.question(
                self,
                "Aggiornamento",
                f"Installare l'ultima versione ({latest_version})?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return

            QMessageBox.information(
                self,
                "Aggiornamento",
                "L'app si chiudera e si aprira una finestra di aggiornamento.",
            )
            updater.launch_update_mode(download_url, latest_version, asset_name, APP_VERSION)
            QApplication.quit()
        except Exception as exc:
            QMessageBox.warning(self, "Aggiornamento fallito", str(exc))
        finally:
            self.ui.app_update_button.setEnabled(True)


if __name__ == "__main__":
    if "--update-mode" in sys.argv:
        args = sys.argv[1:]

        def _value(flag: str, default: str = "") -> str:
            if flag in args:
                index = args.index(flag)
                if index + 1 < len(args):
                    return args[index + 1]
            return default

        download_url = _value("--download-url")
        latest_version = _value("--latest-version")
        asset_name = _value("--asset-name")
        current_version = _value("--current-version", APP_VERSION)
        if not download_url:
            sys.exit(1)

        sys.exit(updater.run_update_mode(download_url, latest_version, asset_name, current_version))

    app = QApplication(sys.argv)
    main_app = App()
    main_app.show()
    sys.exit(app.exec())
