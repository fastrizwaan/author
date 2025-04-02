    def create_yaml_file(self, exe_path, prefix_dir=None, use_exe_name=False):
        self.create_required_directories()
        exe_file = Path(exe_path).resolve()
        exe_name = exe_file.stem
        exe_no_space = exe_name.replace(" ", "_")

        # Calculate SHA256 hash
        sha256_hash = hashlib.sha256()
        with open(exe_file, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        sha256sum = sha256_hash.hexdigest()[:10]

        # Check if a script with the same sha256sum already exists
        script_key = sha256_hash.hexdigest()
        if script_key in self.script_list:
            # Remove the existing .charm file and its entry from the script list
            existing_script_path = Path(self.script_list[script_key]['script_path']).expanduser().resolve()
            if existing_script_path.exists():
                existing_script_path.unlink()  # Remove the existing file
                print(f"Removed existing charm file: {existing_script_path}")

            # Remove the entry from script_list
            #del self.script_list[script_key]
            #print(f"Removed old script_key {script_key} from script_list")

        # Handle prefix directory
        if prefix_dir is None:
            prefix_dir = self.prefixes_dir / f"{exe_no_space}-{sha256sum}"
            if not prefix_dir.exists():
                if self.default_template.exists():
                    self.copy_template(prefix_dir)
                else:
                    self.ensure_directory_exists(prefix_dir)

        wineprefix_name = prefix_dir.name

        # Extract product name using exiftool
        product_cmd = ['exiftool', shlex.quote(str(exe_file))]
        product_output = self.run_command(" ".join(product_cmd))
        if product_output is None:
            productname = exe_no_space
        else:
            productname_match = re.search(r'Product Name\s+:\s+(.+)', product_output)
            productname = productname_match.group(1).strip() if productname_match else exe_no_space

        # Determine program name based on use_exe_name flag
        if use_exe_name:
            progname = exe_name  # Use exe_name if flag is set
        else:
            progname = self.determine_progname(productname, exe_no_space, exe_name)
            
        # Create YAML file with proper naming
        yaml_file_path = prefix_dir / f"{exe_no_space if use_exe_name else progname.replace(' ', '_')}.charm"

        # Prepare YAML data
        yaml_data = {
            'exe_file': str(exe_file).replace(str(Path.home()), "~"),
            'script_path': str(yaml_file_path).replace(str(Path.home()), "~"), 
            'wineprefix': str(prefix_dir).replace(str(Path.home()), "~"),
            'progname': progname,
            'args': "",
            'sha256sum': sha256_hash.hexdigest(),
            'runner': "",
            'wine_debug': "WINEDEBUG=fixme-all DXVK_LOG_LEVEL=none",  # Set a default or allow it to be empty
            'env_vars': ""  # Initialize with an empty string or set a default if necessary
        }

        # Write the new YAML file
        with open(yaml_file_path, 'w') as yaml_file:
            yaml.dump(yaml_data, yaml_file, default_flow_style=False, width=1000)

        # Update yaml_data with resolved paths
        yaml_data['exe_file'] = str(exe_file.expanduser().resolve())
        yaml_data['script_path'] = str(yaml_file_path.expanduser().resolve())
        yaml_data['wineprefix'] = str(prefix_dir.expanduser().resolve())
        # Extract icon and create desktop entry
        icon_path = self.extract_icon(exe_file, prefix_dir, exe_no_space, progname)
        #self.create_desktop_entry(progname, yaml_file_path, icon_path, prefix_dir)

        # Add the new script data directly to self.script_list
        self.new_scripts.add(yaml_file_path.stem)

        # Add or update script row in UI
        self.script_list[script_key] = yaml_data
        # Update the UI row for the renamed script
        row = self.create_script_row(script_key, yaml_data)
        if row:
            self.flowbox.prepend(row)
        # 
        self.script_list = {script_key: yaml_data, **self.script_list}
        self.script_ui_data[script_key]['script_path'] = yaml_data['script_path']
        #script_data['script_path'] = yaml_data['script_path']
        
        print(f"Created new charm file: {yaml_file_path} with script_key {script_key}")


