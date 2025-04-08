import pefile
import struct
from PIL import Image
import io
import argparse
import sys

def extract_icon_from_exe(exe_path, output_png_path):
    # Load the .exe file using pefile
    pe = pefile.PE(exe_path)
    
    # Locate the resources in the PE file
    for resource in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if resource.name and resource.name.__str__() == 'ICON':
            for entry in resource.directory.entries:
                data_rva = entry.directory.entries[0].data.struct.OffsetToData
                size = entry.directory.entries[0].data.struct.Size
                
                # Extract the icon data from the PE file
                icon_data = pe.get_memory_mapped_image()[data_rva:data_rva+size]
                
                # Create an ICO file in-memory
                ico = io.BytesIO(icon_data)
                
                # Open the ICO image and convert it to PNG
                try:
                    img = Image.open(ico)
                    img.save(output_png_path, format='PNG')
                    print(f"Icon saved as {output_png_path}")
                except Exception as e:
                    print(f"Failed to convert the icon: {e}")
                break

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Extract an icon from a Windows EXE file and save it as a PNG.')
    parser.add_argument('exe_path', type=str, help='Path to the .exe file')
    parser.add_argument('output_png_path', type=str, help='Path where the output .png file will be saved')

    args = parser.parse_args()

    # Call the icon extraction function
    extract_icon_from_exe(args.exe_path, args.output_png_path)

if __name__ == '__main__':
    main()

