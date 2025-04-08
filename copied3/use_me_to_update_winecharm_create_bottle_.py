############### PROGRESS 2 for initializing template:
    def show_processing_spinner(self, label_text):
        """
        Initialize progress tracking UI for any step-based process
        """
        # Clear the open button box
        while self.open_button_box.get_first_child():
            self.open_button_box.remove(self.open_button_box.get_first_child())
        
        # Create and add progress bar to the open button
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_text(label_text)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_size_request(300, 20)
        self.open_button_box.append(self.progress_bar)
        
        # Clear the flowbox for showing steps
        self.flowbox.remove_all()
        
        # Create a list to store steps
        self.step_boxes = []
        
        # Disable UI elements during processing
        self.search_button.set_sensitive(False)
        self.view_toggle_button.set_sensitive(False)

    def hide_processing_spinner(self):
        """
        Restore UI state after process completion
        """
        # Clear progress bar
        while self.open_button_box.get_first_child():
            self.open_button_box.remove(self.open_button_box.get_first_child())
        
        # Restore original button content
        open_icon = Gtk.Image.new_from_icon_name("folder-open-symbolic")
        open_label = Gtk.Label(label="Open")
        self.open_button_box.append(open_icon)
        self.open_button_box.append(open_label)
        
        # Re-enable UI elements
        self.search_button.set_sensitive(True)
        self.view_toggle_button.set_sensitive(True)
        
        # Clear step tracking
        if hasattr(self, 'step_boxes'):
            self.step_boxes = []

    def show_initializing_step(self, step_text):
        """
        Show a new processing step in the flowbox
        """
        

        if hasattr(self, 'progress_bar'):
            # Calculate total steps dynamically
            if hasattr(self, 'total_steps'):
                total_steps = self.total_steps
            else:
                # Default for bottle creation
                total_steps = 8
            
            current_step = len(self.step_boxes) + 1
            progress = current_step / total_steps
            
            # Update progress bar
            self.progress_bar.set_fraction(progress)
            self.progress_bar.set_text(f"Step {current_step}/{total_steps}")
            
            # Create step box
            step_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            step_box.set_margin_start(12)
            step_box.set_margin_end(12)
            step_box.set_margin_top(6)
            step_box.set_margin_bottom(6)
            
            # Add status icon and label
            step_icon = self.spinner = Gtk.Spinner()
            step_label = Gtk.Label(label=step_text)
            step_label.set_halign(Gtk.Align.START)
            step_label.set_hexpand(True)
            
            step_box.append(step_icon)
            step_box.append(step_label)
            self.spinner.start()

            
            # Add to flowbox
            flowbox_child = Gtk.FlowBoxChild()
            flowbox_child.set_child(step_box)
            self.flowbox.append(flowbox_child)
            
            # Store reference
            self.step_boxes.append((step_box, step_icon, step_label))

    def mark_step_as_done(self, step_text):
        """
        Mark a step as completed in the flowbox
        """
        if hasattr(self, 'step_boxes'):
            for step_box, step_icon, step_label in self.step_boxes:
                if step_label.get_text() == step_text:
                    step_box.remove(step_icon)
                    done_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                    step_box.prepend(done_icon)
                    break

    def initialize_template(self, template_dir, callback):
        """
        Modified template initialization to use the new progress system
        """
        self.create_required_directories()
        self.initializing_template = True
        
        # Disconnect open button handler
        if self.open_button_handler_id is not None:
            self.open_button.disconnect(self.open_button_handler_id)
        
        # Initialize the progress UI
        self.ensure_directory_exists(template_dir)
        
        steps = [
            ("Initializing wineprefix", f"WINEPREFIX='{template_dir}' WINEDEBUG=-all wineboot -i"),
            ("Replace symbolic links with directories", lambda: self.remove_symlinks_and_create_directories(template_dir)),
            ("Installing corefonts", f"WINEPREFIX='{template_dir}' winetricks -q corefonts"),
            ("Installing openal", f"WINEPREFIX='{template_dir}' winetricks -q openal"),
            ("Installing vkd3d", f"WINEPREFIX='{template_dir}' winetricks -q vkd3d"),
            ("Installing dxvk", f"WINEPREFIX='{template_dir}' winetricks -q dxvk"),
        ]
        
        # Set total steps for progress calculation
        self.total_steps = len(steps)
        self.show_processing_spinner("Initializing Template...")

        def initialize():
            for step_text, command in steps:
                GLib.idle_add(self.show_initializing_step, step_text)
                try:
                    if callable(command):
                        command()
                    else:
                        subprocess.run(command, shell=True, check=True)
                    GLib.idle_add(self.mark_step_as_done, step_text)
                except subprocess.CalledProcessError as e:
                    print(f"Error initializing template: {e}")
                    break
            GLib.idle_add(callback)

        threading.Thread(target=initialize).start()

################# 3rd
    def show_processing_spinner(self, label_text):
        """
        Initialize spinner in open button and progress UI in flowbox
        """
        # Clear the flowbox
        self.flowbox.remove_all()
        
        # Set up open button with spinner and text
        while self.open_button_box.get_first_child():
            self.open_button_box.remove(self.open_button_box.get_first_child())
        
        spinner = Gtk.Spinner()
        spinner.start()
        spinner_label = Gtk.Label(label=label_text)
        
        self.open_button_box.append(spinner)
        self.open_button_box.append(spinner_label)
        
        # Create progress bar in flowbox
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        progress_box.set_margin_start(12)
        progress_box.set_margin_end(12)
        progress_box.set_margin_top(6)
        progress_box.set_margin_bottom(6)
        
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(False)  # Hide text as requested
        self.progress_bar.set_size_request(-1, -1)
        self.progress_bar.set_fraction(0.0)
        
        progress_box.append(self.progress_bar)
        
        # Add progress bar to flowbox
        flowbox_child = Gtk.FlowBoxChild()
        flowbox_child.set_child(progress_box)
        self.flowbox.append(flowbox_child)
        
        # Create a list to store steps
        self.step_boxes = []
        
        # Disable UI elements during processing
        self.search_button.set_sensitive(False)
        self.view_toggle_button.set_sensitive(False)

    def hide_processing_spinner(self):
        """
        Restore UI state after process completion
        """
        # Restore open button
        while self.open_button_box.get_first_child():
            self.open_button_box.remove(self.open_button_box.get_first_child())
        
        open_icon = Gtk.Image.new_from_icon_name("folder-open-symbolic")
        open_label = Gtk.Label(label="Open")
        self.open_button_box.append(open_icon)
        self.open_button_box.append(open_label)
        
        # Re-enable UI elements
        self.search_button.set_sensitive(True)
        self.view_toggle_button.set_sensitive(True)
        
        # Clear step tracking
        if hasattr(self, 'step_boxes'):
            self.step_boxes = []

    def show_initializing_step(self, step_text):
        """
        Show a new processing step in the flowbox
        """
        if hasattr(self, 'progress_bar'):
            # Calculate total steps dynamically
            if hasattr(self, 'total_steps'):
                total_steps = self.total_steps
            else:
                total_steps = 8
            
            current_step = len(self.step_boxes) + 1
            progress = current_step / total_steps
            
            # Update progress bar
            self.progress_bar.set_fraction(progress)
            
            # Create step box
            step_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            step_box.set_margin_start(12)
            step_box.set_margin_end(12)
            step_box.set_margin_top(6)
            step_box.set_margin_bottom(6)
            
            # Add status icon and label
            step_icon = self.spinner = Gtk.Spinner()
            step_label = Gtk.Label(label=step_text)
            step_label.set_halign(Gtk.Align.START)
            step_label.set_hexpand(True)
            
            step_box.append(step_icon)
            step_box.append(step_label)
            self.spinner.start()
            
            # Add to flowbox
            flowbox_child = Gtk.FlowBoxChild()
            flowbox_child.set_child(step_box)
            self.flowbox.append(flowbox_child)
            
            # Store reference
            self.step_boxes.append((step_box, step_icon, step_label))

    def mark_step_as_done(self, step_text):
        """
        Mark a step as completed in the flowbox
        """
        if hasattr(self, 'step_boxes'):
            for step_box, step_icon, step_label in self.step_boxes:
                if step_label.get_text() == step_text:
                    step_box.remove(step_icon)
                    done_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
                    step_box.prepend(done_icon)
                    break

    def connect_open_button_with_bottling_cancel(self, script_key):
        """
        Connect cancel handler to the open button
        """
        if self.open_button_handler_id is not None:
            self.open_button.disconnect(self.open_button_handler_id)
            self.open_button_handler_id = self.open_button.connect("clicked", self.on_cancel_bottle_clicked, script_key)

#################
    def initialize_template(self, template_dir, callback):
        """
        Modified template initialization to use the new progress system with progress bar
        """
        self.create_required_directories()
        self.initializing_template = True
        
        # Disconnect open button handler
        if self.open_button_handler_id is not None:
            self.open_button.disconnect(self.open_button_handler_id)
        
        steps = [
            ("Initializing wineprefix", f"WINEPREFIX='{template_dir}' WINEDEBUG=-all wineboot -i"),
            ("Replace symbolic links with directories", lambda: self.remove_symlinks_and_create_directories(template_dir)),
            ("Installing corefonts", f"WINEPREFIX='{template_dir}' winetricks -q corefonts"),
            ("Installing openal", f"WINEPREFIX='{template_dir}' winetricks -q openal"),
            ("Installing vkd3d", f"WINEPREFIX='{template_dir}' winetricks -q vkd3d"),
            ("Installing dxvk", f"WINEPREFIX='{template_dir}' winetricks -q dxvk"),
        ]
        
        # Set total steps and initialize progress UI
        self.total_steps = len(steps)
        self.show_processing_spinner("Initializing Template...")

        def initialize():
            for index, (step_text, command) in enumerate(steps, 1):
                GLib.idle_add(self.show_initializing_step, step_text)
                try:
                    if callable(command):
                        command()
                    else:
                        subprocess.run(command, shell=True, check=True)
                    GLib.idle_add(self.mark_step_as_done, step_text)
                    # Update progress bar
                    GLib.idle_add(lambda: self.progress_bar.set_fraction(index / self.total_steps))
                except subprocess.CalledProcessError as e:
                    print(f"Error initializing template: {e}")
                    break
            GLib.idle_add(callback)
            GLib.idle_add(self.hide_processing_spinner)

        threading.Thread(target=initialize).start()

    def import_wine_directory(self, src, dst):
        """
        Import the Wine directory with progress tracking in flowbox
        """
        # Clear the flowbox and initialize the progress UI
        GLib.idle_add(self.flowbox.remove_all)
        
        steps = [
            ("Copying Wine directory", lambda: self.custom_copytree(src, dst)),
            ("Processing registry files", lambda: self.process_reg_files(dst)),
            ("Performing Replacements", lambda: self.perform_replacements(dst)),
            ("Creating scripts for .exe files", lambda: self.create_scripts_for_exe_files(dst)),
        ]
        
        # Set total steps and initialize progress UI
        self.total_steps = len(steps)
        self.show_processing_spinner("Importing Wine Directory...")

        def perform_import_steps():
            for index, (step_text, step_func) in enumerate(steps, 1):
                GLib.idle_add(self.show_initializing_step, step_text)
                try:
                    step_func()
                    GLib.idle_add(self.mark_step_as_done, step_text)
                    # Update progress bar
                    GLib.idle_add(lambda: self.progress_bar.set_fraction(index / self.total_steps))
                except Exception as e:
                    print(f"Error during step '{step_text}': {e}")
                    GLib.idle_add(self.show_info_dialog, "Error", f"An error occurred during '{step_text}': {e}")
                    break

            # Re-enable UI elements and restore the script list after the import process
            GLib.idle_add(self.on_import_wine_directory_completed)
            GLib.idle_add(self.hide_processing_spinner)

        threading.Thread(target=perform_import_steps).start()

    def perform_restore_steps(self, file_path):
        """
        Perform the restore process in steps, showing progress for each.
        """
        steps = [
            ("Checking Uncompressed Size", lambda: self.check_disk_space_and_show_step(file_path)),
            ("Extracting Backup File", lambda: self.extract_backup(file_path)),
            ("Processing Registry Files", lambda: self.process_reg_files(self.extract_prefix_dir(file_path))),
            ("Performing Replacements", lambda: self.perform_replacements(self.extract_prefix_dir(file_path))),
            ("Replacing Symbolic Links with Directories", lambda: self.remove_symlinks_and_create_directories(self.extract_prefix_dir(file_path))),
            ("Renaming and merging user directories", lambda: self.rename_and_merge_user_directories(self.extract_prefix_dir(file_path))),
            ("Add Shortcuts to Script List", lambda: self.add_charm_files_to_script_list(self.extract_prefix_dir(file_path))),

        ]
        #for wzt restore
#            ("Create Exe Shortcuts", lambda: self.create_scripts_for_exe_files(self.extract_prefix_dir(file_path)))
        def perform_steps():
            for step_text, step_func in steps:
                # Queue the UI update safely in the main thread
                GLib.idle_add(self.show_initializing_step, step_text)
                try:
                    # Perform the restore step and check the result
                    result = step_func()
                    if result is False:
                        # Stop further steps if a step fails
                        print(f"Step '{step_text}' failed, aborting restore process.")
                        break

                    # Mark the step as done in the main thread
                    GLib.idle_add(self.mark_step_as_done, step_text)
                except Exception as e:
                    print(f"Error during step '{step_text}': {e}")
                    GLib.idle_add(self.show_info_dialog, "Error", f"Failed during step '{step_text}': {str(e)}")
                    break

            # Once complete, update the UI in the main thread
            GLib.idle_add(self.on_restore_completed)

        # Start the restore process in a new thread
        threading.Thread(target=perform_steps).start()

    def create_bottle(self, script, script_key, backup_path):
        """
        Backs up the Wine prefix in a stepwise manner, indicating progress via spinner and label updates.
        """
        # Store current script info for cancellation handling
        self.current_script = script
        self.current_script_key = script_key
        self.stop_processing = False
        self.current_backup_path = backup_path
        wineprefix = Path(script).parent

        # Step 1: Disconnect the UI elements and initialize the spinner
        self.show_processing_spinner("Bottling...")
        self.connect_open_button_with_bottling_cancel(script_key)

        # Get the user's home directory to replace with `~`
        usershome = os.path.expanduser('~')

        # Get the current username from the environment
        user = os.getenv("USER") or os.getenv("USERNAME")
        if not user:
            raise Exception("Unable to determine the current username from the environment.")
        
        find_replace_pairs = {usershome: '~', f'\'{usershome}': '\'~\''}
        find_replace_media_username = {f'/media/{user}/': '/media/%USERNAME%/'}
        restore_media_username = {'/media/%USERNAME%/': f'/media/{user}/'}

        # Extract exe_file from script_data
        script_data = self.extract_yaml_info(script_key)
        if not script_data:
            raise Exception("Script data not found.")

        exe_file = self.expand_and_resolve_path(script_data['exe_file'])
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

        def perform_backup_steps():
            try:
                # Basic steps that are always needed
                basic_steps = [
                    (f"Replace \"{usershome}\" with '~' in script files", lambda: self.replace_strings_in_specific_files(wineprefix, find_replace_pairs)),
                    ("Reverting user-specific .reg changes", lambda: self.reverse_process_reg_files(wineprefix)),
                    (f"Replace \"/media/{user}\" with '/media/%USERNAME%'", lambda: self.replace_strings_in_specific_files(wineprefix, find_replace_media_username)),
                    ("Updating exe_file Path in Script", lambda: self.update_exe_file_path_in_script(script, self.replace_home_with_tilde_in_path(str(game_dir_exe)))),
                    ("Creating Bottle archive", lambda: self.create_bottle_archive(script_key, wineprefix, backup_path)),
                    ("Re-applying user-specific .reg changes", lambda: self.process_reg_files(wineprefix)),
                    (f"Revert %USERNAME% with \"{user}\" in script files", lambda: self.replace_strings_in_specific_files(wineprefix, restore_media_username)),
                    ("Reverting exe_file Path in Script", lambda: self.update_exe_file_path_in_script(script, self.replace_home_with_tilde_in_path(str(exe_file))))
                ]
                
                # Add runner-related steps only if runner exists and is not empty
                steps = basic_steps.copy()
                if runner and str(runner).strip():
                    is_runner_inside_prefix = runner.is_relative_to(self.runners_dir)
                    if is_runner_inside_prefix:
                        runner_update_index = next(i for i, (text, _) in enumerate(steps) if text == "Creating Bottle archive")
                        steps.insert(runner_update_index, 
                            ("Updating runner Path in Script", lambda: self.update_runner_path_in_script(script, self.replace_home_with_tilde_in_path(str(target_runner_exe))))
                        )
                        steps.append(
                            ("Reverting runner Path in Script", lambda: self.update_runner_path_in_script(script, self.replace_home_with_tilde_in_path(str(runner))))
                        )

                for step_text, step_func in steps:
                    if self.stop_processing:
                        GLib.idle_add(self.cleanup_cancelled_bottle, script, script_key)
                        return

                    GLib.idle_add(self.show_initializing_step, step_text)
                    try:
                        step_func()
                        if self.stop_processing:
                            GLib.idle_add(self.cleanup_cancelled_bottle, script, script_key)
                            return
                        GLib.idle_add(self.mark_step_as_done, step_text)
                    except Exception as e:
                        print(f"Error during step '{step_text}': {e}")
                        if not self.stop_processing:
                            GLib.idle_add(self.show_info_dialog, "Backup Failed", f"Error during '{step_text}': {str(e)}")
                        GLib.idle_add(self.cleanup_cancelled_bottle, script, script_key)
                        return

                if not self.stop_processing:
                    GLib.idle_add(self.on_create_bottle_completed, script_key, backup_path)
                
            except Exception as e:
                print(f"Backup process failed: {e}")
                GLib.idle_add(self.cleanup_cancelled_bottle, script, script_key)

        # Run the backup steps in a separate thread to keep the UI responsive
        self.processing_thread = threading.Thread(target=perform_backup_steps)
        self.processing_thread.start()