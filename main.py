from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog
from FileManager import File
import pandas as pd

import sys
import os

import MainWindow as MainWindow


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = MainWindow.Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.file1_button.clicked.connect(self.getFile1)
        self.ui.file2_button.clicked.connect(self.getFile2)
        self.ui.swap_button.clicked.connect(self.swapFile)
        self.ui.create_button.clicked.connect(self.create)

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_app = App()
    main_app.show()
    sys.exit(app.exec())
