    def create_yaml_file(self, exe_path, prefix_dir=None, use_exe_name=False):
        # Existing runner setup and directory creation
        if self.runner_to_use:
            runner_to_use = self.replace_home_with_tilde_in_path(str(self.runner_to_use))
        else:
            runner_to_use = ""
        
        self.create_required_directories()
        exe_file = Path(exe_path).resolve()
        exe_name = exe_file.stem
        exe_no_space = exe_name.replace(" ", "_")

        # SHA256 calculation (keep original functionality)
        sha256_hash = hashlib.sha256()
        with open(exe_file, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        sha256sum = sha256_hash.hexdigest()
        short_hash = sha256sum[:10]

        # Count existing entries with same SHA256 (NEW)
        existing_count = sum(1 for data in self.script_list.values() 
                           if data.get('sha256sum') == sha256sum)
        suffix = f" ({existing_count + 1})" if existing_count > 0 else ""

        # Keep original prefix directory logic intact
        if prefix_dir is None:
            if self.single_prefix:
                if self.arch == 'win32':
                    prefix_dir = self.single_prefix_dir_win32
                    template_to_use = self.default_template_win32
                else:
                    prefix_dir = self.single_prefix_dir_win64
                    template_to_use = self.default_template_win64
                
                if not prefix_dir.exists():
                    self.copy_template(prefix_dir, template_to_use)
            else:
                # Modified directory naming to allow duplicates
                dir_suffix = f"-{existing_count + 1}" if existing_count > 0 else ""
                prefix_dir = self.prefixes_dir / f"{exe_no_space}-{short_hash}{dir_suffix}"
                if not prefix_dir.exists():
                    template_to_use = self.default_template_win32 if self.arch == 'win32' else self.default_template_win64
                    if template_to_use.exists():
                        self.copy_template(prefix_dir, template_to_use)
                    else:
                        self.ensure_directory_exists(prefix_dir)

        # Product name detection (original logic)
        product_cmd = ['exiftool', shlex.quote(str(exe_file))]
        product_output = self.run_command(" ".join(product_cmd))
        productname = exe_no_space
        if product_output:
            productname_match = re.search(r'Product Name\s+:\s+(.+)', product_output)
            if productname_match:
                productname = productname_match.group(1).strip()

        # Modified progname handling with counter
        base_progname = exe_name if use_exe_name else self.determine_progname(productname, exe_no_space, exe_name)
        progname = f"{base_progname}{suffix}" if suffix else base_progname

        # File path generation (original pattern)
        yaml_file_path = prefix_dir / f"{exe_no_space if use_exe_name else base_progname.replace(' ', '_')}.charm"

        # YAML data preparation (original structure)
        yaml_data = {
            'exe_file': self.replace_home_with_tilde_in_path(str(exe_file)),
            'script_path': self.replace_home_with_tilde_in_path(str(yaml_file_path)),
            'wineprefix': self.replace_home_with_tilde_in_path(str(prefix_dir)),
            'progname': progname,
            'args': "",
            'sha256sum': sha256sum,
            'runner': runner_to_use,
            'wine_debug': "WINEDEBUG=fixme-all DXVK_LOG_LEVEL=none",
            'env_vars': ""
        }

        # Write file (original logic)
        with open(yaml_file_path, 'w') as yaml_file:
            yaml.dump(yaml_data, yaml_file, default_flow_style=False, width=1000)

        # Update data with resolved paths (original)
        yaml_data.update({
            'exe_file': str(exe_file.expanduser().resolve()),
            'script_path': str(yaml_file_path.expanduser().resolve()),
            'wineprefix': str(prefix_dir.expanduser().resolve())
        })

        # Icon and desktop entry (original)
        icon_path = self.extract_icon(exe_file, prefix_dir, exe_no_space, progname)
        # self.create_desktop_entry(progname, yaml_file_path, icon_path, prefix_dir)

        # Modified script list management
        script_key = str(yaml_file_path.resolve())  # Unique key
        self.script_list[script_key] = yaml_data
        self.new_scripts.add(yaml_file_path.stem)

        # UI updates (original)
        row = self.create_script_row(script_key, yaml_data)
        if row:
            self.flowbox.prepend(row)
        
        print(f"Created new configuration: {progname} in {yaml_file_path}")
        GLib.idle_add(self.create_script_list)
