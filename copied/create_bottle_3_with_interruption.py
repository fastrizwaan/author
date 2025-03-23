    def on_open_button_clicked(self, button):
        self.open_file_dialog()

    def open_file_dialog(self):
        file_dialog = Gtk.FileDialog.new()
        filter_model = Gio.ListStore.new(Gtk.FileFilter)
        filter_model.append(self.create_file_filter())
        file_dialog.set_filters(filter_model)
        file_dialog.open(self.window, None, self.on_open_file_dialog_response)

    def create_file_filter(self):
        file_filter = Gtk.FileFilter()
        file_filter.set_name("EXE and MSI files")
        file_filter.add_mime_type("application/x-ms-dos-executable")
        file_filter.add_pattern("*.exe")
        file_filter.add_pattern("*.msi")
        return file_filter

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

    def disconnect_open_button(self):
        """
        Disconnect the open button's handler and update its label to "Importing...".
        """
        if self.open_button_handler_id is not None:
            self.open_button.disconnect(self.open_button_handler_id)
        
        if not hasattr(self, 'spinner') or not self.spinner:  # Ensure spinner is not created multiple times
            self.spinner = Gtk.Spinner()
            self.spinner.start()
            self.open_button_box.append(self.spinner)

        #self.set_open_button_label("Importing...")
        self.set_open_button_icon_visible(False)  # Hide the open-folder icon
        print("Open button disconnected and spinner shown.")

    def reconnect_open_button(self):
        """
        Reconnect the open button's handler and reset its label.
        """
        if self.open_button_handler_id is not None:
            self.open_button_handler_id = self.open_button.connect("clicked", self.on_open_button_clicked)
        
        if self.spinner:
            self.spinner.stop()
            self.open_button_box.remove(self.spinner)
            self.spinner = None  # Ensure the spinner reference is cleared

        self.set_open_button_label("Open")
        self.set_open_button_icon_visible(True)
        print("Open button reconnected and UI reset.")

######################### CREATE BOTTLE
    # Get directory size method
    def get_directory_size(self, path):
        if not path.exists():
            print(f"The provided path '{path}' does not exist.")
            return 0

        try:
            total_size = sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())
            return total_size
        except Exception as e:
            print(f"Error calculating directory size: {e}")
            return 0

    def create_bottle(self, script, script_key, backup_path):
        """
        Backs up the Wine prefix in a stepwise manner, indicating progress via spinner and label updates.
        """
        wineprefix = Path(script).parent

        # Step 1: Disconnect the UI elements and initialize the spinner
        
        self.show_processing_spinner("Bottling...")
        #self.set_open_button_icon_visible(False)
        self.disconnect_open_button()

        # Get the user's home directory to replace with `~`
        usershome = os.path.expanduser('~')

        # Get the current username from the environment
        user = os.getenv("USER") or os.getenv("USERNAME")
        if not user:
            raise Exception("Unable to determine the current username from the environment.")
        
        find_replace_pairs = {usershome: '~', f'\'{usershome}': '`\~'}
        find_replace_media_username = {f'/media/{user}/': '/media/%USERNAME%/'}
        restore_media_username = {'/media/%USERNAME%/': f'/media/{user}/'}

        # Extract exe_file from script_data
        script_data = self.extract_yaml_info(script_key)
        if not script_data:
            raise Exception("Script data not found.")

        exe_file = self.expand_and_resolve_path(script_data['exe_file'])
        #exe_file = Path(str(exe_file).replace("%USERNAME%", user))
        exe_file = Path(str(exe_file).replace("%USERNAME%", user))
        exe_path = exe_file.parent
        exe_name = exe_file.name

        runner = self.expand_and_resolve_path(script_data['runner'])

        # If runner is inside the script
        if runner:
            print(f"RUNNER FOUND = {runner}")
            # Check if the runner is inside runners_dir
            is_runner_inside_prefix = runner.is_relative_to(self.runners_dir)
            print("===========================================================")
            if is_runner_inside_prefix:
                print("RUNNER INSIDE PREFIX")
                runner_dir = runner.parent.parent
                runner_dir_exe = runner_dir / "bin/wine"

                target_runner_dir = wineprefix / "Runner" 
                target_runner_exe = target_runner_dir / runner_dir.name / "bin/wine"
            else:
                target_runner_exe = runner
                runner_dir_exe = runner
                print("RUNNER IS NOT INSIDE PREFIX")

        # Check if game directory is inside the prefix
        is_exe_inside_prefix = exe_path.is_relative_to(wineprefix)

        print("==========================================================")
        # exe_file path replacement should use existing exe_file if it's already inside prefix
        if is_exe_inside_prefix:
            game_dir = exe_path
            game_dir_exe = exe_file
            print(f"""
            exe_file is inside wineprefix:
            game_dir = {game_dir}
            game_dir_exe = {game_dir_exe}
            """)
        else:
            game_dir = wineprefix / "drive_c" / "GAMEDIR"
            game_dir_exe = game_dir / exe_path.name / exe_name
            print(f"""
            exe_file is OUTSIDE wineprefix:
            game_dir = {game_dir}
            game_dir_exe = {game_dir_exe}
            """)
        # Step 2: Define the steps for the backup process

        def perform_backup_steps():
            # Basic steps that are always needed
            basic_steps = [
                (f"Replace \"{usershome}\" with '~' in script files", lambda: self.replace_strings_in_specific_files(wineprefix, find_replace_pairs)),
                ("Reverting user-specific .reg changes", lambda: self.reverse_process_reg_files(wineprefix)),
                (f"Replace \"/media/{user}\" with '/media/%USERNAME%' in script files", lambda: self.replace_strings_in_specific_files(wineprefix, find_replace_media_username)),
                ("Updating exe_file Path in Script", lambda: self.update_exe_file_path_in_script(script, self.replace_home_with_tilde_in_path(str(game_dir_exe)))),
                ("Creating Bottle archive", lambda: self.create_bottle_archive(script_key, wineprefix, backup_path)),
                ("Re-applying user-specific .reg changes", lambda: self.process_reg_files(wineprefix)),
                (f"Revert %USERNAME% with \"{user}\" in script files", lambda: self.replace_strings_in_specific_files(wineprefix, restore_media_username)),
                ("Reverting exe_file Path in Script", lambda: self.update_exe_file_path_in_script(script, self.replace_home_with_tilde_in_path(str(exe_file))))
            ]
            
            # Add runner-related steps only if runner exists and is not empty
            steps = basic_steps.copy()
            if runner and str(runner).strip():  # Check if runner exists and is not empty
                # Check if the runner is inside runners_dir
                is_runner_inside_prefix = runner.is_relative_to(self.runners_dir)
                if is_runner_inside_prefix:
                    # Insert runner update steps after exe_file update and before archive creation
                    runner_update_index = next(i for i, (text, _) in enumerate(steps) if text == "Creating Bottle archive")
                    steps.insert(runner_update_index, 
                        ("Updating runner Path in Script", lambda: self.update_runner_path_in_script(script, self.replace_home_with_tilde_in_path(str(target_runner_exe))))
                    )
                    # Add runner revert step at the end
                    steps.append(
                        ("Reverting runner Path in Script", lambda: self.update_runner_path_in_script(script, self.replace_home_with_tilde_in_path(str(runner))))
                    )

            for step_text, step_func in steps:
                GLib.idle_add(self.show_initializing_step, step_text)
                try:
                    # Execute the step
                    step_func()
                    GLib.idle_add(self.mark_step_as_done, step_text)
                except Exception as e:
                    print(f"Error during step '{step_text}': {e}")
                    GLib.idle_add(self.show_info_dialog, "Backup Failed", f"Error during '{step_text}': {str(e)}")
                    break

            # Once all steps are completed, reset the UI
            GLib.idle_add(self.on_create_bottle_completed, script_key, backup_path)
        # Step 4: Run the backup steps in a separate thread to keep the UI responsive
        threading.Thread(target=perform_backup_steps).start()

    def on_create_bottle_completed(self, script_key, backup_path):
        """
        Called when the backup process is complete. Updates the UI accordingly.
        """
        # Reset the button label and remove the spinner
        self.set_open_button_label("Open")
        self.set_open_button_icon_visible(True)
        self.reconnect_open_button()
        self.hide_processing_spinner()

        # Notify the user that the backup is complete
        self.show_info_dialog("Bottle Created", f"{backup_path}")
        print("Bottle creating process completed successfully.")

        # Iterate over all script buttons and update the UI based on `is_clicked_row`
        for key, data in self.script_ui_data.items():
            row_button = data['row']
            row_play_button = data['play_button']
            row_options_button = data['options_button']
        self.show_options_for_script(self.script_ui_data[script_key], row_button, script_key)

    def on_backup_confirmation_response(self, dialog, response_id, script, script_key):
        if response_id == "continue":
            dialog.close()
            self.show_create_bottle_dialog(script, script_key)
        else:
            return

    def create_bottle_selected(self, script, script_key, button):

        # Step 1: Check if the executable file exists
        # Extract exe_file from script_data
        script_data = self.extract_yaml_info(script_key)
        if not script_data:
            raise Exception("Script data not found.")

        wineprefix = Path(script).parent
        exe_file = self.expand_and_resolve_path(script_data['exe_file'])
        #exe_file = Path(str(exe_file).replace("%USERNAME%", user))
        exe_path = exe_file.parent
        exe_name = exe_file.name
        game_dir = wineprefix / "drive_c" / "GAMEDIR"
        game_dir_exe = game_dir / exe_path.name / exe_name

        # Check if the game directory is in DO_NOT_BUNDLE_FROM directories
        if str(exe_path) in self.get_do_not_bundle_directories():
            msg1 = "Cannot copy the selected game directory"
            msg2 = "Please move the files to a different directory to create a bundle."
            self.show_info_dialog(msg1, msg2)
            return

        # If exe_not found i.e., game_dir is not accessble due to unmounted directory
        if not exe_file.exists():
            GLib.timeout_add_seconds(0.5, self.show_info_dialog, "Exe Not Found", f"Not Mounted or Deleted?\n{exe_file}")
            return

        # Step 2: Check for size if > 3GB ask the user:
        # Calculate the directory size in bytes
        directory_size = self.get_directory_size(exe_path)

        # Convert directory size to GB for comparison
        directory_size_gb = directory_size / (1024 ** 3)  # 1 GB is 1024^3 bytes
        directory_size_gb = round(directory_size_gb, 2)  # round to two decimal places

        print("----------------------------------------------------------")
        print(directory_size)
        print(directory_size_gb)

        if directory_size_gb > 3:
            print("Size Greater than 3GB")
            # Show confirmation dialog
            dialog = Adw.MessageDialog.new(
            self.window,
            "Large Game Directory",
            f"The game directory size is {directory_size_gb}GB. Do you want to continue?"
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("continue", "Continue")
            dialog.set_response_appearance("continue", Adw.ResponseAppearance.SUGGESTED)
        #dialog.connect("response", perform_backup_steps, script, script_key, backup_path)
            dialog.connect("response", self.on_backup_confirmation_response, script, script_key)
            dialog.present()
            print("----------------------------------------------------------")
        else:
            self.show_create_bottle_dialog(script, script_key)

    def show_create_bottle_dialog(self, script, script_key):
            # Step 3: Suggest the backup file name
            default_backup_name = f"{script.stem}-bottle.tar.zst"

            # Create a Gtk.FileDialog instance for saving the file
            file_dialog = Gtk.FileDialog.new()

            # Set the initial file name using set_initial_name() method
            file_dialog.set_initial_name(default_backup_name)

            # Open the dialog asynchronously to select the save location
            file_dialog.save(self.window, None, self.on_create_bottle_dialog_response, script, script_key)

            print("FileDialog presented for saving the backup.")

    def on_create_bottle_dialog_response(self, dialog, result, script, script_key):
        try:
            # Retrieve the selected file (save location) using save_finish()
            backup_file = dialog.save_finish(result)
            if backup_file:
                self.on_back_button_clicked(None)
                self.flowbox.remove_all()
                backup_path = backup_file.get_path()  # Get the backup file path
                print(f"Backup will be saved to: {backup_path}")

                # Start the backup process in a separate thread
                threading.Thread(target=self.create_bottle, args=(script, script_key, backup_path)).start()

        except GLib.Error as e:
            # Handle any errors, such as cancellation
            print(f"An error occurred: {e}")

    def create_bottle_archive(self, script_key, wineprefix, backup_path):
        # Get the current username from the environment
        current_username = os.getenv("USER") or os.getenv("USERNAME")
        if not current_username:
            raise Exception("Unable to determine the current username from the environment.")

        # Extract exe_file from script_data
        script_data = self.extract_yaml_info(script_key)
        if not script_data:
            raise Exception("Script data not found.")

        exe_file = Path(script_data['exe_file']).expanduser().resolve()
        exe_file = Path(str(exe_file).replace("%USERNAME%", current_username))
        exe_path = exe_file.parent

        # Check if game directory is inside the prefix
        is_exe_inside_prefix = exe_path.is_relative_to(wineprefix)

        tar_game_dir_name = exe_path.name
        tar_game_dir_path = exe_path.parent

        runner = self.expand_and_resolve_path(script_data['runner'])

        # Start building the tar command with common options
        tar_command = [
            'tar',
            '-I', 'zstd -T0',  # Use zstd compression with all available CPU cores
            '--transform', f"s|{wineprefix.name}/drive_c/users/{current_username}|{wineprefix.name}/drive_c/users/%USERNAME%|g",
        ]

        # If game is not in prefix, add game directory transform
        if not is_exe_inside_prefix:
            tar_command.extend([
                '--transform', f"s|^\./{tar_game_dir_name}|{wineprefix.name}/drive_c/GAMEDIR/{tar_game_dir_name}|g"
            ])

        # Initialize the list of source directories and their base paths
        sources = []
        
        # Always add the wineprefix
        sources.append(('-C', str(wineprefix.parent), wineprefix.name))

        # If runner exists and is inside runners_dir
        if runner and runner.is_relative_to(self.runners_dir):
            runner_dir = runner.parent.parent
            runner_dir_name = runner_dir.name
            runner_dir_path = runner_dir.parent
            tar_command.extend([
                '--transform', f"s|^\./{runner_dir_name}|{wineprefix.name}/Runner/{runner_dir_name}|g"
            ])
            sources.append(('-C', str(runner_dir_path), rf"./{runner_dir_name}"))


        # If game is not in prefix, add it as a source
        if not is_exe_inside_prefix:
            sources.append(('-C', str(tar_game_dir_path), rf"./{tar_game_dir_name}"))

        # Add the output file path
        tar_command.extend(['-cf', backup_path])

        # Add all sources to the command
        for source in sources:
            tar_command.extend(source)

        print(f"Running create bottle command: {' '.join(tar_command)}")

        # Execute the tar command
        result = subprocess.run(tar_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            raise Exception(f"Backup failed: {result.stderr}")

        print(f"Backup archive created at {backup_path}")
#########################/CREATE BOTTLE

