
############################################ CREATE_BOTTLE 2

    def create_bottle(self, script, script_key, backup_path):
        """
        Backs up the Wine prefix in a stepwise manner, indicating progress via spinner and label updates.
        """
        wineprefix = Path(script).parent

        # Step 1: Disconnect the UI elements and initialize the spinner
        self.show_processing_spinner("Bottling...")

        # Get the user's home directory to replace with `~`
        usershome = os.path.expanduser('~')
        user = os.getenv('USER')
        find_replace_pairs = {usershome: '~', f'/media/{user}/': '/media/%USERNAME%/'}
        restore_media_username = {'/media/%USERNAME%/': f'/media/{user}/'}

        # Extract exe_file from script_data
        script_data = self.extract_yaml_info(script_key)
        if not script_data:
            raise Exception("Script data not found.")

        exe_file = Path(script_data['exe_file']).expanduser().resolve()
        exe_file = Path(str(exe_file).replace("%USERNAME%", user))
        exe_path = exe_file.parent
        exe_name = exe_file.name
        game_dir = wineprefix / "drive_c" / "GAMEDIR"

        # Check if the game directory is in DO_NOT_BUNDLE_FROM directories
        if str(exe_path) in self.get_do_not_bundle_directories():
            msg1 = "Cannot copy the selected game directory"
            msg2 = "Please move the files to a different directory to create a bundle."
            self.show_info_dialog(msg1, msg2)
            return

        # Check disk space in the source and destination directories
        if not self.has_enough_disk_space(exe_path, wineprefix):
            self.show_info_dialog("Insufficient Disk Space", "There is not enough space to import the game directory.")
            return

        # Check the size of the game directory
        game_dir_size = self.get_directory_size(exe_path)
        if game_dir_size > 3 * 1024**3:  # 3GB
            dialog = Adw.MessageDialog.new(self.window, "Large Game Directory",
                                           "The game directory is larger than 3GB. Do you want to continue?")
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("continue", "Continue")
            dialog.set_response_appearance("continue", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", self.on_large_game_dir_response, script, script_key, backup_path)
            dialog.present()
            return

        # Step 2: Define the steps for the backup process
        def perform_backup_steps():
            steps = [
                (f"Replace \"{usershome}\" with '~' in script files", lambda: self.replace_strings_in_specific_files(wineprefix, find_replace_pairs)),
                ("Reverting user-specific .reg changes", lambda: self.reverse_process_reg_files(wineprefix)),
                ("Updating Script Path", lambda: self.update_script_path(script, game_dir / exe_name)),
                ("Creating Bottle archive", lambda: self.create_bottle_archive_with_progress(script_key, wineprefix, backup_path)),
                ("Re-applying user-specific .reg changes", lambda: self.process_reg_files(wineprefix)),
                (f"Revert %USERNAME% with \"{user}\" in script files", lambda: self.replace_strings_in_specific_files(wineprefix, restore_media_username)),
                ("Reverting Script Path", lambda: self.update_script_path(script, exe_file)),
            ]

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

            # Step 3: Once all steps are completed, reset the UI
            GLib.idle_add(self.on_create_bottle_completed, script_key, backup_path)

        # Step 4: Run the backup steps in a separate thread to keep the UI responsive
        threading.Thread(target=perform_backup_steps).start()

    def on_large_game_dir_response(self, dialog, response, script, script_key, backup_path):
        if response == "continue":
            threading.Thread(target=self.create_bottle, args=(script, script_key, backup_path)).start()
        dialog.close()

    def create_bottle_archive_with_progress(self, script_key, wineprefix, backup_path):
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

        tar_game_dir_name = exe_path.name
        tar_game_dir_path = exe_path.parent

        # Prepare the tar command with --transform option
        tar_command = [
            'tar',
            '-I', 'zstd -T0',  # Use zstd compression with all available CPU cores
            '--transform', f"s|{wineprefix.name}/drive_c/users/{current_username}|{wineprefix.name}/drive_c/users/%USERNAME%|g",  # Rename the directory and its contents
            '--transform', f"s|^\./{tar_game_dir_name}|{wineprefix.name}/drive_c/GAMEDIR/{tar_game_dir_name}|g",
            '-cf', backup_path,
            '-C', str(wineprefix.parent),
            wineprefix.name,
            '-C', str(tar_game_dir_path),
            rf"./{tar_game_dir_name}",
        ]

        print(f"Running backup command: {' '.join(tar_command)}")

        # Execute the tar command and show progress
        process = subprocess.Popen(tar_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        def update_progress():
            total_size = self.get_directory_size(wineprefix) + self.get_directory_size(exe_path)
            processed_size = 0
            while True:
                output = process.stdout.readline()
                if process.poll() is not None:
                    break
                if output:
                    processed_size += len(output)
                    progress = (processed_size / total_size) * 100
                    GLib.idle_add(self.update_progress_bar, progress)

            process.stdout.close()
            process.wait()

            if process.returncode != 0:
                raise Exception(f"Backup failed: {process.stderr.read()}")

            print(f"Backup archive created at {backup_path}")

        threading.Thread(target=update_progress).start()

    def update_progress_bar(self, progress):
        # Update the progress bar in the UI
        self.progress_bar.set_fraction(progress / 100)

    def get_directory_size(self, directory):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size
########################### /CREATE_BOTTLE2