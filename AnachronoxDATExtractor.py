import PyQt6
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow , QStyleFactory, QMessageBox, QTextEdit, QComboBox, QLineEdit, QComboBox, QScrollBar, QFileDialog
from PyQt6 import uic

import qdarktheme


import sys
import os
import io
import zlib
import shutil
from glob import glob

import struct
from dataclasses import dataclass, fields





@dataclass
class anox_dat_file_header:
    """
    This is just metadata because this class will not store the "lumps" of the file.
    It's not "strictly" a header either, since the file info is stored at the end of the file, but this will store all the relevant information.
    """

    # First 4 characters should be "ADAT"
    id: str

    # This is the offset which has information about the file (see below). This offset and 144 bytes thereafter contain that information.
    # A .dat file will typically have multiple files.  So, ever 144 bytes, this information is repeated for each file
    file_info_position: int
    file_info_length: int # The number of bytes that comprise the file info section at the ned of the file (divide by 144 to get the number of files)
    version: int # Always 9, possibly a version of some sort used by the Anachronox team, and we would never see 1-8 in the released product, for example.






def load_file_bytes(file_path):
    with open(file_path, "rb") as file:
        bytes = file.read()
    
    return bytes



def load_dat_header(self, file_bytes):
    header_bytes = struct.unpack("<cccciii", file_bytes[:16])
    # print(header_bytes[0].decode())

    # Separate the first 4 characters as 1 value (the "ADAT" string found in the header)
    header_id = ''.join(header_bytes[i].decode() for i in range(4))
    

    if header_id != "ADAT":
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Not Anachronox DAT")
        msg_box.setText("ERROR: File is not an Anachronox DAT")
        msg_box.show()
        return -1

    header_values_parsed = (header_id,) + header_bytes[4:16]
    header = anox_dat_file_header(*header_values_parsed)
    return header






class AnachronoxDATApp(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.getcwd(), 'AnachronoxDATExtractor.ui'), self)
        self.show()

        ### BUTTON EVENTS ###
        self.ui.btn_select_dat_file.clicked.connect(self.select_file)
        self.ui.btn_select_output_folder.clicked.connect(self.select_output_folder)



    def select_file(self):
        try:
            output_folder = self.ui.txt_output_folder.text()

            if not os.path.exists(output_folder):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Output Folder Error")
                msg_box.setText("ERROR: Selected Output folder does not exist")
                msg_box.show()
                return

            file_name = QFileDialog.getOpenFileName(caption = "Select .dat file", filter = "*.dat")[0]
            print(f"File Name: {file_name}")
            
            if file_name != '' and file_name is not None:
                dat_file_bytes = load_file_bytes(file_name)
                dat_file_header = load_dat_header(self, dat_file_bytes)
                
                if dat_file_header == -1:
                    print("Invalid DAT, aborting...")
                    return


                print("--------------- HEADER VALUES -------------------")
                for field in fields(dat_file_header):
                    print(f"{field.name} - ", getattr(dat_file_header, field.name))

                print("--------------------------------------------------")

            

                number_of_files = int(dat_file_header.file_info_length / 144)
                print (f"{number_of_files} files in DAT")


                # Get the actual files
                file_info_bytes = dat_file_bytes[dat_file_header.file_info_position : dat_file_header.file_info_position + dat_file_header.file_info_length]
                for i in range(number_of_files):
                    start_pos = i * 144
                    # print(file_info_bytes[start_pos + 128 : start_pos + 144])


                    file_name = file_info_bytes[start_pos : start_pos + 128].decode("ascii","ignore").strip()
                    metadata = struct.unpack("<iiii", file_info_bytes[start_pos + 128 : start_pos + 144])

                    # print(f"File {i}: Start pos: {start_pos}, metadata:\n{metadata}")

                    file_start_pos = metadata[0]
                    file_length = metadata[1]
                    compressed_file_size = metadata[2]
                    checksum_unknown = metadata[3]

                    
                    # print(f"File start pos: {file_start_pos}")
                    # print(f"File size: {file_length}")
                    # print(f"Compressed size: {compressed_file_size}")
                    # print(f"Checksum: {checksum_unknown}")


                    # If the file is compressed
                    if compressed_file_size > 0:
                        print(f"Decompressing/Writing: {file_name}, start position: {file_start_pos}, length: {file_length}, compressed size: {compressed_file_size}, checksum: {checksum_unknown}")
                        this_file_bytes = dat_file_bytes[file_start_pos : file_start_pos + compressed_file_size]
                        
                        decompressed_file = zlib.decompress(this_file_bytes)

                        output_path = os.path.join(output_folder, file_name)
                        output_path = ''.join(x for x in output_path if x.isprintable())
                        
                        output_directory = os.path.dirname(output_path)
                        if not os.path.exists(output_directory):
                            print("MAKING DIRECTORY!")
                            print(output_directory)
                            os.makedirs(output_directory)
                        
                        
                        output_file = open(output_path, 'wb')
                        output_file.write(decompressed_file)
                        output_file.close()

                    # If not compressed
                    else:
                        print(f"Writing (Uncompressed): {file_name}, start position: {file_start_pos}, length: {file_length}, compressed size: {compressed_file_size}, checksum: {checksum_unknown}")
                        
                        this_file_bytes = dat_file_bytes[file_start_pos : file_start_pos + file_length]

                        output_path = os.path.join(output_folder, file_name)
                        output_path = ''.join(x for x in output_path if x.isprintable())
                        
                        output_directory = os.path.dirname(output_path)
                        if not os.path.exists(output_directory):
                            print("MAKING DIRECTORY!")
                            print(output_directory)
                            os.makedirs(output_directory)


                        output_file = open(output_path, 'wb')
                        output_file.write(this_file_bytes)
                        output_file.close()

                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Complete")
                msg_box.setText("Extraction Complete!")
                msg_box.show()


        except Exception as argument:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("ERROR")
            msg_box.setText("Error extracting .DAT file:\n{argument}")
            msg_box.show()
            return


    def select_output_folder(self):
        try:
            # folder_name = QFileDialog.getOpenFileName(caption = "Select .dat file", filter = "*.dat")[0]
            folder = QFileDialog.getExistingDirectory(self, "Select Folder")
            self.ui.txt_output_folder.setText(folder)
        except Exception as argument:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Output Folder Error")
            msg_box.setText("Error selecting output folder:\n{argument}")
            msg_box.show()
            return



if __name__ == '__main__':
    # Prints out the themes available
    print(QStyleFactory.keys())

    user_login_name = os.getlogin()
    # print(user_login_name)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(qdarktheme.load_stylesheet())


    print(app.style().objectName())

    AnachronoxDATUI = AnachronoxDATApp()

    
    sys.exit(app.exec())
    