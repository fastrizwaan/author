    def connect_open_button_with_bottiling_cancel(self):
        """
        Disconnect the open button's handler and update its label to "Cancel".
        """
        if self.open_button_handler_id is not None:
            self.open_button.disconnect(self.open_button_handler_id)
            # Connect the cancel handler instead
            self.open_button_handler_id = self.open_button.connect("clicked", self.on_cancel_bottle_clicked)
        
        if not hasattr(self, 'spinner') or not self.spinner:
            self.spinner = Gtk.Spinner()
            self.spinner.start()
            self.open_button_box.append(self.spinner)

        self.set_open_button_label("Cancel")
        self.set_open_button_icon_visible(False)
        print("Open button switched to cancel mode")

    def on_cancel_bottle_clicked(self, button):
        """
        Handle the cancel button click during bottle creation.
        """
        dialog = Adw.MessageDialog.new(
            self.window,
            "Cancel Bottle Creation",
            "Do you want to cancel the bottle creation process?"
        )
        dialog.add_response("continue", "Continue")
        dialog.add_response("cancel", "Cancel Creation")
        dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_cancel_bottle_dialog_response)
        dialog.present()

    def on_cancel_bottle_dialog_response(self, dialog, response):
        """
        Handle the response from the cancel confirmation dialog.
        """
        if response == "cancel":
            self.stop_bottle_creation()
        dialog.close()

    def stop_bottle_creation(self):
        """
        Stop the bottle creation process and cleanup.
        """
        if hasattr(self, 'processing_thread') and self.processing_thread and self.processing_thread.is_alive():
            self.stop_processing = True
            self.processing_thread.join(timeout=0.5)

        # Revert exe_file and runner paths
        try:
            script = self.current_script
            script_key = self.current_script_key
            if script and script_key:
                script_data = self.extract_yaml_info(script_key)
                if script_data:
                    original_exe = script_data['exe_file']
                    original_runner = script_data.get('runner', '')
                    self.update_exe_file_path_in_script(script, original_exe)
                    if original_runner:
                        self.update_runner_path_in_script(script, original_runner)
        except Exception as e:
            print(f"Error reverting paths: {e}")

        # Reset UI
        self.reconnect_open_button()
        self.hide_processing_spinner()
        print("Bottle creation cancelled and cleaned up")

    def create_bottle(self, script, script_key, backup_path):
        """
        Modified create_bottle method with interruption support.
        """
        self.current_script = script  # Store for cancellation
        self.current_script_key = script_key
        self.stop_processing = False
        
        wineprefix = Path(script).parent

        self.show_processing_spinner("Bottling...")
        self.connect_open_button_with_bottiling_cancel()

        def perform_backup_steps():
            try:
                # Your existing backup steps code here
                # Add checks for self.stop_processing after each major step
                for step_text, step_func in steps:
                    if self.stop_processing:
                        GLib.idle_add(self.show_info_dialog, "Bottle Creation Cancelled", 
                                    "The bottle creation process was cancelled.")
                        return

                    GLib.idle_add(self.show_initializing_step, step_text)
                    try:
                        step_func()
                        if self.stop_processing:
                            return
                        GLib.idle_add(self.mark_step_as_done, step_text)
                    except Exception as e:
                        print(f"Error during step '{step_text}': {e}")
                        GLib.idle_add(self.show_info_dialog, "Backup Failed", 
                                    f"Error during '{step_text}': {str(e)}")
                        return

                if not self.stop_processing:
                    GLib.idle_add(self.on_create_bottle_completed, script_key, backup_path)
            finally:
                if self.stop_processing:
                    GLib.idle_add(self.stop_bottle_creation)

        self.processing_thread = threading.Thread(target=perform_backup_steps)
        self.processing_thread.start()

    def create_bottle_archive(self, script_key, wineprefix, backup_path):
        """
        Modified create_bottle_archive method with interruption support.
        """
        # Your existing create_bottle_archive code here
        # Add periodic checks for self.stop_processing
        if self.stop_processing:
            raise Exception("Bottle creation cancelled by user")
            
        # Rest of your existing code...
        tar_command = [
            'tar',
            '-I', 'zstd -T0',
            '--transform', f"s|{wineprefix.name}/drive_c/users/{current_username}|{wineprefix.name}/drive_c/users/%USERNAME%|g",
        ]
        
        # Execute tar command with subprocess.Popen instead of subprocess.run
        process = subprocess.Popen(tar_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        while process.poll() is None:
            if self.stop_processing:
                process.terminate()
                process.wait()
                # Clean up the partial backup file if it exists
                if Path(backup_path).exists():
                    Path(backup_path).unlink()
                raise Exception("Bottle creation cancelled by user")
            time.sleep(0.1)  # Small delay to prevent CPU overuse
            
        if process.returncode != 0:
            raise Exception(f"Backup failed: {process.stderr.read()}")