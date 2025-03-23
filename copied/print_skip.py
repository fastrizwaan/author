def process_sh_files(directory, skip_ui_update=False):
    print(f"Directory: {directory}")
    print(f"skip_ui_update: {skip_ui_update}")

# Call the function with different values for skip_ui_update
process_sh_files('1 /some/directory', skip_ui_update=True)
process_sh_files('2 /some/directory', skip_ui_update=False)
process_sh_files('3 /some/directory')  # Default value for skip_ui_update is False
process_sh_files('4 /some/directory', skip_ui_update)  # Default value for skip_ui_update is False
