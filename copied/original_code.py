def restore_from_backup(self, action=None, param=None):
        # Step 1: Create required directories (if needed)
        self.create_required_directories()

        # Step 2: Create a new Gtk.FileDialog instance
        file_dialog = Gtk.FileDialog.new()

        # Step 3: Create file filters for .tar.zst and .wzt files
        file_filter_combined = Gtk.FileFilter()
        file_filter_combined.set_name("Backup Files (*.prefix, *.bottle, *.wzt)")
        file_filter_combined.add_pattern("*.prefix")
        file_filter_combined.add_pattern("*.bottle")
        file_filter_combined.add_pattern("*.wzt")

        file_filter_botle_tar = Gtk.FileFilter()
        file_filter_botle_tar.set_name("WineCharm Bottle Files (*.bottle)")
        file_filter_botle_tar.add_pattern("*.bottle")

        file_filter_tar = Gtk.FileFilter()
        file_filter_tar.set_name("WineCharm Prefix Backup (*.prefix)")
        file_filter_tar.add_pattern("*.prefix")

        file_filter_wzt = Gtk.FileFilter()
        file_filter_wzt.set_name("Winezgui Backup Files (*.wzt)")
        file_filter_wzt.add_pattern("*.wzt")

        # Step 4: Set the filters on the dialog
        filter_model = Gio.ListStore.new(Gtk.FileFilter)
        
        # Add the combined filter as the default option
        filter_model.append(file_filter_combined)

        # Add individual filters for .tar.zst and .wzt files
        filter_model.append(file_filter_tar)
        filter_model.append(file_filter_botle_tar)
        filter_model.append(file_filter_wzt)
        
        # Apply the filters to the file dialog
        file_dialog.set_filters(filter_model)

        # Step 5: Open the dialog and handle the response
        file_dialog.open(self.window, None, self.on_restore_file_dialog_response)

    def get_total_uncompressed_size(self, archive_path):
        """
        Calculate the total uncompressed size of a tar archive without extracting it.

        Args:
            archive_path (str): The path to the tar archive.

        Returns:
            int: Total uncompressed size of the archive in bytes.
        """
        # Run the tar command and capture the output
        command = ['tar', '-tvf', archive_path]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if there was an error
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return 0

        total_size = 0

        # Process each line of the tar output
        for line in result.stdout.splitlines():
            # Split the line by spaces and extract the third field (file size)
            parts = line.split()
            if len(parts) > 2:
                try:
                    size = int(parts[2])  # The size is in the third field
                    total_size += size
                except ValueError:
                    pass  # Skip lines where we can't parse the size

        print(f"Total uncompressed size: {total_size} bytes")
        return total_size


    def check_disk_space_and_uncompressed_size(self, prefixes_dir, file_path):
        """
        Check the available disk space and uncompressed size of the backup file.

        Args:
            prefixes_dir (Path): The directory where the wine prefixes are stored.
            file_path (str): Path to the backup .tar.zst file.

        Returns:
            (bool, int, int): Tuple containing:
                - True if there's enough space, False otherwise.
                - Available disk space in bytes.
                - Uncompressed size of the archive in bytes.
        """
        try:
            # Step 1: Get available disk space in the prefixes directory
            df_output = subprocess.check_output(['df', '--output=avail', str(prefixes_dir)]).decode().splitlines()[1]
            available_space_kb = int(df_output.strip()) * 1024  # Convert KB to bytes

            # Step 2: Get the total uncompressed size of the tar.zst file
            uncompressed_size_bytes = self.get_total_uncompressed_size(file_path)

            print(f"Available space: {available_space_kb / (1024 * 1024)} MB")
            print(f"Uncompressed size: {uncompressed_size_bytes / (1024 * 1024)} MB")

            # Step 3: Compare available space with uncompressed size
            return available_space_kb >= uncompressed_size_bytes, available_space_kb, uncompressed_size_bytes

        except subprocess.CalledProcessError as e:
            print(f"Error checking disk space or uncompressed size: {e}")
            return False, 0, 0


    def on_restore_file_dialog_response(self, dialog, result):
        try:
            # Retrieve the selected file using open_finish() for Gtk.FileDialog in GTK 4
            file = dialog.open_finish(result)
            if file:
                # Get the file path
                file_path = file.get_path()
                print(f"Selected file: {file_path}")

                # the restore
                self.restore_prefix_bottle_wzt_tar_zst(file_path)

        except GLib.Error as e:
            # Handle errors, such as dialog cancellation
            if e.domain != 'gtk-dialog-error-quark' or e.code != 2:
                print(f"An error occurred: {e}")


    def restore_prefix_bottle_wzt_tar_zst(self, file_path):
        """
        Restore from a .prefix or .bottle which is a .tar.zst compressed file.
        """
        self.stop_processing = False
        
        try:
            # Extract prefix name before starting
            extracted_prefix = self.extract_prefix_dir(file_path)
            if not extracted_prefix:
                raise Exception("Failed to determine prefix directory name")
            
            # Handle existing directory
            backup_dir = None
            if extracted_prefix.exists():
                timestamp = int(time.time())
                backup_dir = extracted_prefix.parent / f"{extracted_prefix.name}_backup_{timestamp}"
                shutil.move(str(extracted_prefix), str(backup_dir))
                print(f"Backed up existing directory to: {backup_dir}")

            # Clear the flowbox and show progress spinner
            GLib.idle_add(self.flowbox.remove_all)
            self.show_processing_spinner(f"Restoring")
            #self.disconnect_open_button()
            #self.connect_open_button_with_import_wine_directory_cancel()
            self.connect_open_button_with_restore_backup_cancel()
            def restore_process():
                try:
                    # Determine the file extension and get the appropriate restore steps
                    if file_path.endswith(".wzt"):
                        restore_steps = self.get_wzt_restore_steps(file_path)
                    else:
                        restore_steps = self.get_restore_steps(file_path)

                    # Perform restore steps
                    for step_text, step_func in restore_steps:
                        if self.stop_processing:
                            # Handle cancellation
                            if backup_dir and backup_dir.exists():
                                if extracted_prefix.exists():
                                    shutil.rmtree(extracted_prefix)
                                shutil.move(str(backup_dir), str(extracted_prefix))
                                print(f"Restored original directory from: {backup_dir}")
                            GLib.idle_add(self.on_restore_completed)
                            #GLib.idle_add(self.show_info_dialog, "Cancelled", "Restore process was cancelled")
                            return

                        GLib.idle_add(self.show_initializing_step, step_text)
                        try:
                            step_func()
                            GLib.idle_add(self.mark_step_as_done, step_text)
                        except Exception as e:
                            print(f"Error during step '{step_text}': {e}")
                            # Handle failure
                            if backup_dir and backup_dir.exists():
                                if extracted_prefix.exists():
                                    shutil.rmtree(extracted_prefix)
                                shutil.move(str(backup_dir), str(extracted_prefix))
                            GLib.idle_add(self.show_info_dialog, "Error", f"Failed during step '{step_text}': {str(e)}")
                            return

                    # If successful, remove backup directory
                    if backup_dir and backup_dir.exists():
                        shutil.rmtree(backup_dir)
                        print(f"Removed backup directory: {backup_dir}")

                    GLib.idle_add(self.on_restore_completed)

                except Exception as e:
                    print(f"Error during restore process: {e}")
                    # Handle failure
                    if backup_dir and backup_dir.exists():
                        if extracted_prefix.exists():
                            shutil.rmtree(extracted_prefix)
                        shutil.move(str(backup_dir), str(extracted_prefix))
                    GLib.idle_add(self.show_info_dialog, "Error", f"Restore failed: {str(e)}")

            # Start the restore process in a new thread
            threading.Thread(target=restore_process).start()

        except Exception as e:
            print(f"Error initiating restore process: {e}")
            GLib.idle_add(self.show_info_dialog, "Error", f"Failed to start restore: {str(e)}")



    def get_restore_steps(self, file_path):
        """
        Return the list of steps for restoring a prefix/bottle backup.
        """
        return [
            ("Checking Uncompressed Size", lambda: self.check_disk_space_and_show_step(file_path)),
            ("Extracting Backup File", lambda: self.extract_backup(file_path)),
            ("Processing Registry Files", lambda: self.process_reg_files(self.extract_prefix_dir(file_path))),
            ("Performing Replacements", lambda: self.perform_replacements(self.extract_prefix_dir(file_path))),
            ("Replacing Symbolic Links with Directories", lambda: self.remove_symlinks_and_create_directories(self.extract_prefix_dir(file_path))),
            ("Renaming and merging user directories", lambda: self.rename_and_merge_user_directories(self.extract_prefix_dir(file_path))),
            ("Add Shortcuts to Script List", lambda: self.add_charm_files_to_script_list(self.extract_prefix_dir(file_path))),
        ]

    def get_wzt_restore_steps(self, file_path):
        """
        Return the list of steps for restoring a WZT backup.
        """
        return [
            ("Checking Disk Space", lambda: self.check_disk_space_and_show_step(file_path)),
            ("Extracting WZT Backup File", lambda: self.extract_backup(file_path)),
            ("Performing User Related Replacements", lambda: self.perform_replacements(self.extract_prefix_dir(file_path))),
            ("Processing WineZGUI Script Files", lambda: self.process_sh_files(self.extract_prefix_dir(file_path))),
            ("Search LNK Files and Append to Found List", lambda: self.find_and_save_lnk_files(self.extract_prefix_dir(file_path))),
            ("Replacing Symbolic Links with Directories", lambda: self.remove_symlinks_and_create_directories(self.extract_prefix_dir(file_path))),
            ("Renaming and Merging User Directories", lambda: self.rename_and_merge_user_directories(self.extract_prefix_dir(file_path))),
        ]

    def perform_replacements(self, directory):
        user = os.getenv('USER')
        usershome = os.path.expanduser('~')
        datadir = os.getenv('DATADIR', '/usr/share')

        # Simplified replacements using plain strings
        find_replace_pairs = {
            "XOCONFIGXO": "\\\\?\\H:\\.config",
            "XOFLATPAKNAMEXO": "io.github.fastrizwaan.WineCharm",
            "XOINSTALLTYPEXO": "flatpak",
            "XOPREFIXXO": ".var/app/io.github.fastrizwaan.WineCharm/data/winecharm/Prefixes",
            "XOWINEZGUIDIRXO": ".var/app/io.github.fastrizwaan.WineCharm/data/winecharm",
            "XODATADIRXO": datadir,
            "XODESKTOPDIRXO": ".local/share/applications/winecharm",
            "XOAPPLICATIONSXO": ".local/share/applications",
            "XOAPPLICATIONSDIRXO": ".local/share/applications",
            "XOREGUSERSUSERXO": f"\\\\users\\\\{user}",
            "XOREGHOMEUSERXO": f"\\\\home\\\\{user}",
            "XOREGUSERNAMEUSERXO": f'"USERNAME"="{user}"',
            "XOREGINSTALLEDBYUSERXO": f'"InstalledBy"="{user}"',
            "XOREGREGOWNERUSERXO": f'"RegOwner"="{user}"',
            "XOUSERHOMEXO": usershome,
            "XOUSERSUSERXO": f"/users/{user}",
            "XOMEDIASUSERXO": f"/media/{user}",
            "XOFLATPAKIDXO": "io.github.fastrizwaan.WineCharm",
            "XOWINEEXEXO": "",
            "XOWINEVERXO": "wine-9.0",
            "/media/%USERNAME%/": f'/media/{user}/',
        }

        self.replace_strings_in_files(directory, find_replace_pairs)
        

    def replace_strings_in_files(self, directory, find_replace_pairs):
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)

                # Skip binary files
                if self.is_binary_file(file_path):
                    #print(f"Skipping binary file: {file_path}")
                    continue

                # Skip files where permission is denied
                if not os.access(file_path, os.R_OK | os.W_OK):
                    #print(f"Skipping file: {file_path} (Permission denied)")
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    for find, replace in find_replace_pairs.items():
                        content = content.replace(find, replace)

                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                    print(f"Replacements applied to file: {file_path}")
                except (UnicodeDecodeError, FileNotFoundError, PermissionError) as e:
                    print(f"Skipping file: {file_path} ({e})")

    def is_binary_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\0' in chunk:
                    return True
        except Exception as e:
            print(f"Could not check file {file_path} ({e})")
        return False    def on_startup(self, app):
        self.create_main_window()
        self.script_list = {}
        self.load_script_list()

        self.single_prefix = False
        self.load_settings()
        print(f"Single Prefix: {self.single_prefix}")

        def initialize_template_if_needed(template_path, arch, single_prefix_dir=None):
            if not template_path.exists():
                self.set_open_button_label("Initializing")
                print(f"Initializing {arch} template...")
                self.initialize_template(template_path, self.on_template_initialized, arch=arch)
                return True
            elif self.single_prefix and single_prefix_dir and not single_prefix_dir.exists():
                print(f"Copying {arch} template to single prefix...")
                self.copy_template(single_prefix_dir)
            return False

        # Corrected conditions: Only check current arch when single_prefix is False
        arch_templates = []
        if self.single_prefix:
            # Check both templates if single_prefix is enabled
            arch_templates = [
                (True, self.default_template_win32, 'win32', self.single_prefix_dir_win32),
                (True, self.default_template_win64, 'win64', self.single_prefix_dir_win64)
            ]
        else:
            # Check only the current arch's template
            if self.arch == 'win32':
                arch_templates = [
                    (True, self.default_template_win32, 'win32', self.single_prefix_dir_win32)
                ]
            else:
                arch_templates = [
                    (True, self.default_template_win64, 'win64', self.single_prefix_dir_win64)
                ]

        needs_initialization = False
        for check, template, arch, single_dir in arch_templates:
            if check:
                needs_initialization |= initialize_template_if_needed(template, arch, single_dir)

        if not needs_initialization:
            self.create_script_list()
            self.set_dynamic_variables()
            if self.command_line_file:
                print("Processing command-line file after UI initialization")
                self.process_cli_file_later(self.command_line_file)

        missing_programs = self.check_required_programs()
        if missing_programs:
            self.show_missing_programs_dialog(missing_programs)
        
        self.check_running_processes_on_startup()
        threading.Thread(target=self.maybe_fetch_runner_urls).start()

    def start_socket_server(self):
        def server_thread():
            socket_dir = self.SOCKET_FILE.parent

            # Ensure the directory for the socket file exists
            self.create_required_directories()

            # Remove existing socket file if it exists
            if self.SOCKET_FILE.exists():
                self.SOCKET_FILE.unlink()

            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(self.SOCKET_FILE))
                server.listen()

                while True:
                    conn, _ = server.accept()
                    with conn:
                        message = conn.recv(1024).decode()
                        if message:
                            command_parts = message.split("||")
                            command = command_parts[0]

                            if command == "show_dialog":
                                title = command_parts[1]
                                body = command_parts[2]
                                # Call show_info_dialog in the main thread using GLib.idle_add
                                GLib.timeout_add_seconds(0.5, self.show_info_dialog, title, body)
                            elif command == "process_file":
                                file_path = command_parts[1]
                                GLib.idle_add(self.process_cli_file, file_path)

        # Run the server in a separate thread
        threading.Thread(target=server_thread, daemon=True).start()


    def initialize_app(self):
        if not hasattr(self, 'window') or not self.window:
            # Call the startup code
            self.create_main_window()
            self.create_script_list()
            #self.check_running_processes_and_update_buttons()
            
            missing_programs = self.check_required_programs()
            if missing_programs:
                self.show_missing_programs_dialog(missing_programs)
            else:
                if not self.default_template.exists() and not self.single_prefix:
                    self.initialize_template(self.default_template, self.on_template_initialized)
                if not self.default_template.exists() and self.single_prefix:
                    self.initialize_template(self.default_template, self.on_template_initialized)
                    self.copy_template(self.single_prefixes_dir)
                elif self.default_template.exists() and not self.single_prefixes_dir.exists() and self.single_prefix:
                    self.copy_template(self.single_prefixes_dir)
                else:
                    self.set_dynamic_variables()

    def process_cli_file_later(self, file_path):
        # Use GLib.idle_add to ensure this runs after the main loop starts
        GLib.idle_add(self.show_processing_spinner, "hello world")
        GLib.idle_add(self.process_cli_file, file_path)

    def process_cli_file_in_thread(self, file_path):
        """Process CLI file in a background thread with step-based progress"""
        self.stop_processing = False
        
        GLib.idle_add(lambda: self.show_processing_spinner("Processing..."))
        steps = [
            ("Creating configuration", lambda: self.create_yaml_file(str(file_path), None)),
        ]
        try:
            # Show progress bar and initialize UI
            self.total_steps = len(steps)
            
            # Process each step
            for index, (step_text, step_func) in enumerate(steps, 1):
                if self.stop_processing:
                    return
                    
                # Update progress bar
                GLib.idle_add(lambda i=index: self.progress_bar.set_fraction((i-1)/self.total_steps))
                #GLib.idle_add(lambda t=step_text: self.set_open_button_label(t))
                
                try:
                    # Execute the step
                    step_func()
                    # Update progress after step completion
                    GLib.idle_add(lambda i=index: self.progress_bar.set_fraction(i/self.total_steps))
                except Exception as e:
                    print(f"Error during step '{step_text}': {e}")
                    GLib.idle_add(lambda: self.show_info_dialog("Error", f"An error occurred during '{step_text}': {e}"))
                    return

        except Exception as e:
            print(f"Error during file processing: {e}")
            GLib.idle_add(lambda: self.show_info_dialog("Error", f"Processing failed: {e}"))
        finally:
            # Clean up and update UI
            def cleanup():
                if not self.initializing_template:
                    self.hide_processing_spinner()
                self.create_script_list()
                return False
            
            GLib.timeout_add(500, cleanup)

    def on_template_initialized(self, arch=None):
        print(f"Template initialization complete for {arch if arch else 'default'} architecture.")
        self.initializing_template = False
        
        # Update architecture setting if we were initializing a specific arch
        if arch:
            self.arch = arch
            # Set template path based on architecture
            self.template = self.default_template_win32 if arch == 'win32' \
                else self.default_template_win64
            self.save_settings()
        
        # Ensure the spinner is stopped after initialization
        self.hide_processing_spinner()
        
        self.set_open_button_label("Open")
        self.set_open_button_icon_visible(True)
        self.search_button.set_sensitive(True)
        self.view_toggle_button.set_sensitive(True)
        
        # Disabled Cancel/Interruption
        #if self.open_button_handler_id is not None:
        #    self.open_button_handler_id = self.open_button.connect("clicked", self.on_open_button_clicked)

        print("Template initialization completed and UI updated.")
        self.show_initializing_step("Initialization Complete!")
        self.mark_step_as_done("Initialization Complete!")
        
        # If not called from settings create script list else go to settings
        if not self.called_from_settings:
            GLib.timeout_add_seconds(0.5, self.create_script_list)
        
        if self.called_from_settings:
            self.on_template_restore_completed()
            
        # Check if there's a command-line file to process after initialization
        if self.command_line_file:
            print("Processing command-line file after template initialization")
            self.process_cli_file_later(self.command_line_file)
            self.command_line_file = None  # Reset after processing

        self.set_dynamic_variables()
        self.reconnect_open_button()
        self.called_from_settings = False

    def on_open_file_dialog_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
                file_path = file.get_path()
                print("- - - - - - - - - - - - - -self.show_processing_spinner")
                self.monitoring_active = False
                
                # If there's already a processing thread, stop it
                if hasattr(self, 'processing_thread') and self.processing_thread and self.processing_thread.is_alive():
                    self.stop_processing = True
                    self.processing_thread.join(timeout=0.5)  # Wait briefly for thread to stop
                    self.hide_processing_spinner()
                    self.set_open_button_label("Open")
                    self.set_open_button_icon_visible(True)
                    return

                # Show processing spinner
                self.show_processing_spinner("Processing...")
                
                # Start a new background thread to process the file
                self.stop_processing = False
                self.processing_thread = threading.Thread(target=self.process_cli_file_in_thread, args=(file_path,))
                self.processing_thread.start()

        except GLib.Error as e:
            if e.domain != 'gtk-dialog-error-quark' or e.code != 2:
                print(f"An error occurred: {e}")
        finally:
            self.window.set_visible(True)
            self.monitoring_active = True

    def process_cli_file_in_thread(self, file_path):
        """
        Process CLI file in a background thread with proper Path handling
        """
        try:
            print(f"Processing CLI file in thread: {file_path}")
            file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
            abs_file_path = file_path.resolve()
            print(f"Resolved absolute CLI file path: {abs_file_path}")

            if not abs_file_path.exists():
                print(f"File does not exist: {abs_file_path}")
                return

            # Perform the heavy processing here
            self.create_yaml_file(str(abs_file_path), None)

        except Exception as e:
            print(f"Error processing file in background: {e}")
        finally:
            if self.initializing_template:
                pass  # Keep showing spinner
            else:
                GLib.idle_add(self.hide_processing_spinner)
            
            GLib.timeout_add_seconds(0.5, self.create_script_list)


    def on_open(self, app, files, *args):
        # Ensure the application is fully initialized
        print("1. on_open method called")
        
        # Initialize the application if it hasn't been already
        self.initialize_app()
        print("2. self.initialize_app initiated")
        
        # Present the window as soon as possible
        GLib.idle_add(self.window.present)
        print("3. self.window.present() Complete")
        
        # Check if the command_line_file exists and is either .exe or .msi
        if self.command_line_file:
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            print(self.command_line_file)
            
            file_extension = Path(self.command_line_file).suffix.lower()
            if file_extension in ['.exe', '.msi']:
                print(f"Processing file: {self.command_line_file} (Valid extension: {file_extension})")
                print("Trying to process file inside on template initialized")

                GLib.idle_add(self.show_processing_spinner)
                self.process_cli_file(self.command_line_file)
            else:
                print(f"Invalid file type: {file_extension}. Only .exe or .msi files are allowed.")
                GLib.timeout_add_seconds(0.5, self.show_info_dialog, "Invalid File Type", "Only .exe and .msi files are supported.")
                self.command_line_file = None
                return False
        self.check_running_processes_on_startup()


def parse_args():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(description="WineCharm GUI application or headless mode for .charm files")
    parser.add_argument('file', nargs='?', help="Path to the .exe, .msi, .charm, .bottle, .prefix, or .wzt file")
    return parser.parse_args()
    
def main():
    args = parse_args()

    # Create an instance of WineCharmApp
    app = WineCharmApp()

    # If a file is provided, handle it appropriately
    if args.file:
        file_path = Path(args.file).expanduser().resolve()
        file_extension = file_path.suffix.lower()

        # If it's a .charm file, launch it without GUI
        if file_extension == '.charm':
            try:
                # Load the .charm file data
                with open(file_path, 'r', encoding='utf-8') as file:
                    script_data = yaml.safe_load(file)

                exe_file = script_data.get("exe_file")
                if not exe_file:
                    print("Error: No executable file defined in the .charm script.")
                    sys.exit(1)

                # Prepare to launch the executable
                exe_path = Path(exe_file).expanduser().resolve()
                if not exe_path.exists():
                    print(f"Error: Executable '{exe_path}' not found.")
                    sys.exit(1)

                # Extract additional environment and arguments
                
                # if .charm file has script_path use it
                wineprefix_path_candidate = script_data.get('script_path')

                if not wineprefix_path_candidate:  # script_path not found
                    # if .charm file has wineprefix in it, then use it
                    wineprefix_path_candidate = script_data.get('wineprefix')
                    if not wineprefix_path_candidate:  # if wineprefix not found
                        wineprefix_path_candidate = file_path  # use the current .charm file's path

                # Resolve the final wineprefix path
                wineprefix = Path(wineprefix_path_candidate).parent.expanduser().resolve()
                
                env_vars = script_data.get("env_vars", "").strip()
                script_args = script_data.get("args", "").strip()
                runner = script_data.get("runner", "wine")

                # Resolve runner path
                if runner:
                    runner = Path(runner).expanduser().resolve()
                    runner_dir = str(runner.parent.expanduser().resolve())
                    path_env = f'export PATH="{runner_dir}:$PATH"'
                else:
                    runner = "wine"
                    runner_dir = ""  # Or set a specific default if required
                    path_env = ""

                # Prepare the command safely using shlex for quoting
                exe_parent = shlex.quote(str(exe_path.parent.resolve()))
                wineprefix = shlex.quote(str(wineprefix))
                runner = shlex.quote(str(runner))

                # Construct the command parts
                command_parts = []

                # Add path to runner if it exists
                if path_env:
                    command_parts.append(f"{path_env}")

                # Change to the executable's directory
                command_parts.append(f"cd {exe_parent}")

                # Add environment variables if present
                if env_vars:
                    command_parts.append(f"{env_vars}")

                # Add wineprefix and runner
                command_parts.append(f"WINEPREFIX={wineprefix} {runner} {shlex.quote(str(exe_path))}")

                # Add script arguments if present
                if script_args:
                    command_parts.append(f"{script_args}")

                # Join all the command parts
                command = " && ".join(command_parts)

                print(f"Executing: {command}")
                subprocess.run(command, shell=True)

                # Exit after headless execution to ensure no GUI elements are opened
                sys.exit(0)

            except Exception as e:
                print(f"Error: Unable to launch the .charm script: {e}")
                sys.exit(1)

        # For .exe, .msi, .bottle, .prefix, or .wzt files, handle via GUI mode
        elif file_extension in ['.exe', '.msi']:
            if app.SOCKET_FILE.exists():
                try:
                    # Send the file to an existing running instance
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.connect(str(app.SOCKET_FILE))
                        message = f"process_file||{args.file}"
                        client.sendall(message.encode())
                        print(f"Sent file path to existing instance: {args.file}")
                    return
                except ConnectionRefusedError:
                    print("No existing instance found, starting a new one.")

            # If no existing instance is running, proceed with normal startup and processing
            app.command_line_file = args.file

        else:
            # Check if it's a supported backup file type
            if file_extension in ['.bottle', '.prefix', '.wzt']:
                app.command_line_file = args.file
            # If no instance is running, start WineCharmApp and show the error dialog directly
            if not app.SOCKET_FILE.exists():
                app.start_socket_server()
                GLib.timeout_add_seconds(1.5, app.show_info_dialog, "Invalid File Type", f"Only .exe, .msi, or .charm files are allowed. You provided: {file_extension}")
                app.run(sys.argv)

                # Clean up the socket file
                if app.SOCKET_FILE.exists():
                    app.SOCKET_FILE.unlink()
            else:
                print(f"Invalid file type: {file_extension}. Only .exe, .msi, .charm, .bottle, .prefix, or .wzt files are allowed.")
                if app.SOCKET_FILE.exists():
                    app.SOCKET_FILE.unlink()
            else:
                # If an instance is running, send the error message to the running instance
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.connect(str(app.SOCKET_FILE))
                        message = f"show_dialog||Invalid file type: {file_extension}||Only .exe, .msi, or .charm files are allowed."
                        client.sendall(message.encode())
                        return
                except ConnectionRefusedError:
                    print("No existing instance found, starting a new one.")
            
            # Return early to skip further processing
            return

    # Start the socket server and run the application (GUI mode)
    if args.file and file_extension in ['.bottle', '.prefix', '.wzt']:
        app.command_line_file = args.file
    app.start_socket_server()
    app.run(sys.argv)

    # Clean up the socket file
    if app.SOCKET_FILE.exists():
        app.SOCKET_FILE.unlink()

if __name__ == "__main__":
    main()


