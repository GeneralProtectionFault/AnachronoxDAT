import PyQt6
from PyQt6.QtWidgets import QApplication, QWidget, QMessageBox, QTextEdit, QComboBox, QLineEdit, QScrollBar, QFileDialog, QListWidget
from PyQt6 import uic

import qdarktheme


import sys
import os
from pathlib import Path
import io
import zlib
import shutil
from glob import glob
import json

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
    file_info_length: int # The number of bytes that comprise the file info section at the end of the file (divide by 144 to get the number of files)
    version: int # Always 9, possibly a version of some sort used by the Anachronox team, and we would never see 1-8 in the released product, for example.


@dataclass
class anox_dat_file:
    file_name: str
    start_position: int
    length: int
    compressed_length: int
    checksum: int



dat_file_name = ""
dat_file_dictionary = dict()



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



def populate_file_list(ui_object, dat_file_bytes, dat_file_header, number_of_files):
    global dat_file_dictionary
    dat_file_dictionary.clear()
    ui_object.ui.lst_files.clear()

    file_info_bytes = dat_file_bytes[dat_file_header.file_info_position : dat_file_header.file_info_position + dat_file_header.file_info_length]
    for i in range(number_of_files):
        start_pos = i * 144
        # print(file_info_bytes[start_pos + 128 : start_pos + 144])


        file_name = file_info_bytes[start_pos : start_pos + 128].decode("ascii","ignore").rstrip('\x00')
        metadata = struct.unpack("<LLLL", file_info_bytes[start_pos + 128 : start_pos + 144])
        
        file_data = (file_name,) + metadata

        dat_file = anox_dat_file(*file_data)

        # Add to dictionary
        dat_file_dictionary[file_name] = dat_file.__dict__

        # Add to UI list
        ui_object.ui.lst_files.addItem(file_name)




def write_file(dat_file_bytes, dat_file, output_folder, file_name):
    print(f"Writing (Uncompressed): {file_name}, start position: {getattr(dat_file, 'start_position')}, length: {getattr(dat_file, 'length')}, compressed size: {getattr(dat_file, 'compressed_length')}, checksum: {getattr(dat_file, 'checksum')}")
                
    this_file_bytes = dat_file_bytes[getattr(dat_file, 'start_position') : getattr(dat_file, 'start_position') + getattr(dat_file, 'length')]

    global dat_file_name
    # This will add the name of the dat file itself as a subdirectory.
    # Judging from the models w/ a .atd file, and the paths they point to, I'm guessing this is convention, and it will allow parsing the .atd w/o extra work
    print(f"output folder: {output_folder}")
    output_path = os.path.join(output_folder, dat_file_name, file_name)
    output_path = ''.join(x for x in output_path if x.isprintable())
    
    output_directory = os.path.dirname(output_path)
    
    if not os.path.exists(output_directory):
        print(f"Making directory: {output_directory}")
        print(output_directory)
        os.makedirs(output_directory)

    output_file = open(output_path, 'wb')
    output_file.write(this_file_bytes)
    output_file.close()


def write_compressed_file(dat_file_bytes, dat_file, output_folder, file_name):
    print(f"Decompressing/Writing: {file_name}, start position: {getattr(dat_file, 'start_position')}, length: {getattr(dat_file, 'length')}, compressed size: {getattr(dat_file, 'compressed_length')}, checksum: {getattr(dat_file, 'checksum')}")
    this_file_bytes = dat_file_bytes[getattr(dat_file, 'start_position') : getattr(dat_file, 'start_position') + getattr(dat_file, 'compressed_length')]
    
    decompressed_file = zlib.decompress(this_file_bytes)

    global dat_file_name
    # This will add the name of the dat file itself as a subdirectory.
    # Judging from the models w/ a .atd file, and the paths they point to, I'm guessing this is convention, and it will allow parsing the .atd w/o extra work
    print(f"output folder: {output_folder}")
    output_path = os.path.join(output_folder, dat_file_name, file_name)
    output_path = ''.join(x for x in output_path if x.isprintable())
    
    output_directory = os.path.dirname(output_path)
    if not os.path.exists(output_directory):
        print(f"Making directory: {output_directory}")
        print(output_directory)
        os.makedirs(output_directory)
    
    output_file = open(output_path, 'wb')
    output_file.write(decompressed_file)
    output_file.close()


def extract_all_files(dat_file_bytes, dat_file_header, number_of_files, output_folder, ui_object):
    try:
        # Get the actual files
        file_info_bytes = dat_file_bytes[dat_file_header.file_info_position : dat_file_header.file_info_position + dat_file_header.file_info_length]
        for i in range(number_of_files):
            start_pos = i * 144
            # print(file_info_bytes[start_pos + 128 : start_pos + 144])


            file_name = file_info_bytes[start_pos : start_pos + 128].decode("ascii","ignore").rstrip('\x00')
            metadata = struct.unpack("<LLLL", file_info_bytes[start_pos + 128 : start_pos + 144])
            
            file_data = (file_name,) + metadata
            # print(f"File {i}: Start pos: {start_pos}, metadata:\n{metadata}")


            dat_file = anox_dat_file(*file_data)

            # If the file is compressed
            if getattr(dat_file, 'compressed_length') > 0:
                write_compressed_file(dat_file_bytes, dat_file, output_folder, file_name)

            # If not compressed
            else:
                write_file(dat_file_bytes, dat_file, output_folder, file_name)


        msg_box = QMessageBox(ui_object)
        msg_box.setWindowTitle("Complete")
        msg_box.setText("Extraction Complete!")
        msg_box.show()


    except Exception as argument:
        msg_box = QMessageBox(ui_object)
        msg_box.setWindowTitle("ERROR")
        msg_box.setText(f"Error extracting .DAT file:\n{argument}")
        msg_box.show()
        return




class AnachronoxDATApp(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.getcwd(), 'AnachronoxDATExtractor.ui'), self)
        self.show()

        ### BUTTON EVENTS ###
        self.ui.btn_select_dat_file.clicked.connect(self.select_file)
        self.ui.btn_select_output_folder.clicked.connect(self.select_output_folder)
        self.ui.btn_extract_all.clicked.connect(self.extract_all)
        self.ui.btn_extract_selected.clicked.connect(self.extract_selected)




    def select_file(self):
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

            global dat_file_name
            dat_file_name = Path(file_name).stem.lower()
            print(f"DAT FILENAME: {dat_file_name}")

            # Populate UI w/ file name
            self.ui.txt_dat_file.setText(file_name)

            number_of_files = int(dat_file_header.file_info_length / 144)
            print (f"{number_of_files} files in DAT")

            populate_file_list(self, dat_file_bytes, dat_file_header, number_of_files)

            print("--------------- HEADER VALUES -------------------")
            for field in fields(dat_file_header):
                print(f"{field.name} - ", getattr(dat_file_header, field.name))

            print("--------------------------------------------------")

        

            


                


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


    def extract_all(self):
        file = load_file_bytes(self.ui.txt_dat_file.text())
        header = load_dat_header(self, file)
        number_of_files = int(header.file_info_length / 144)
        output_folder = self.ui.txt_output_folder.text()

        if not os.path.exists(output_folder) or not os.path.isfile(self.ui.txt_dat_file.text()):
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Extract Error")
            msg_box.setText("ERROR: Folder or file no longer exist.")
            msg_box.show()
            return
        
        extract_all_files(file, header, number_of_files, output_folder, self)



    def extract_selected(self):
        if self.ui.lst_files.currentItem() is None:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Error")
            msg_box.setText("Please select a file first.")
            msg_box.show()
            return
        

        selected_file = self.ui.lst_files.currentItem().text()

        global dat_file_dictionary
        file_info = dat_file_dictionary[selected_file]

        # Convert dictionary back to class
        dat_file = anox_dat_file(None, None, None, None, None)
        for key in file_info:
            setattr(dat_file, key, file_info[key])

        #print(dat_file)

        dat_file_bytes = load_file_bytes(self.ui.txt_dat_file.text())
        if getattr(dat_file, "compressed_length") > 0:
            write_compressed_file(dat_file_bytes, dat_file, self.ui.txt_output_folder.text(), getattr(dat_file, "file_name"))
        else:
            write_file(dat_file_bytes, dat_file, self.ui.txt_output_folder.text(), getattr(dat_file, "file_name"))

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Complete")
        msg_box.setText("File Extracted!")
        msg_box.show()




if __name__ == '__main__':
    # Prints out the themes available
    # print(QStyleFactory.keys())

    user_login_name = os.getlogin()
    # print(user_login_name)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(qdarktheme.load_stylesheet())


    print(app.style().objectName())

    AnachronoxDATUI = AnachronoxDATApp()

    
    sys.exit(app.exec())
    