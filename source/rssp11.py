import ctypes
import os
import random
import wx
import sound_cacher # Assuming sound_cacher.py is in the same directory or accessible
import threading

class SoundPlayer(wx.Frame):
    def __init__(self, parent, title):
        # Increased width and height for more controls in attached rows
        super(SoundPlayer, self).__init__(parent, title=title, size=(750, 750)) # Adjusted size
        self.cacher = sound_cacher.SoundCacher()

        self.base_sounds_dir = "sounds"
        self.pack_names = []
        self.current_pack_name = None
        self.sound_folders = [] # Subfolders of the current_pack_name (for main selection)
        self.sound_files = []   # Sound files in the main selected subfolder

        self.MAX_ATTACHED = 5
        self.attached_pack_combos = []    # NEW: For selecting pack for each attached row
        self.attached_subfolder_combos = [] # RENAMED: Was attached_folder_combos
        self.attached_folder_delays = []
        self.attached_sizers = []

        self.initialize_ui()

    def initialize_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Random Pan Checkbox ---
        self.random_pan_checkbox = wx.CheckBox(panel, label="Random Pan")
        main_sizer.Add(self.random_pan_checkbox, 0, wx.ALL, 5)

        # --- Play Sound Button ---
        self.play_button = wx.Button(panel, label="Play Sound")
        self.play_button.Bind(wx.EVT_BUTTON, self.on_play_button)
        main_sizer.Add(self.play_button, 0, wx.ALL, 5)

        # --- Pack ComboBox (Main) ---
        pack_label = wx.StaticText(panel, label="Select Sound Pack:")
        self.pack_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        self.pack_combo.Bind(wx.EVT_COMBOBOX, self.on_pack_selected)
        main_sizer.Add(pack_label, 0, wx.LEFT | wx.TOP, 5)
        main_sizer.Add(self.pack_combo, 0, wx.ALL | wx.EXPAND, 5)

        # --- Main Subfolder Combo ---
        subfolder_label = wx.StaticText(panel, label="Choose Subfolder (from above pack):")
        self.step_folder_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        self.step_folder_combo.Bind(wx.EVT_COMBOBOX, self.on_subfolder_selected)
        main_sizer.Add(subfolder_label, 0, wx.LEFT | wx.TOP, 5)
        main_sizer.Add(self.step_folder_combo, 0, wx.ALL | wx.EXPAND, 5)

        # --- Attach Folders Controls ---
        self.attached_checkbox = wx.CheckBox(panel, label="Attach Sounds from Other Packs/Subfolders")
        self.attached_checkbox.Bind(wx.EVT_CHECKBOX, self.on_attach_checkbox_toggled)

        attach_count_label = wx.StaticText(panel, label="Number of Attached Sounds:")
        self.attach_count_spin = wx.SpinCtrl(panel, min=0, max=self.MAX_ATTACHED, initial=0)
        self.attach_count_spin.Bind(wx.EVT_SPINCTRL, self.on_attach_count_changed)
        self.attach_count_spin.Disable()

        attach_options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        attach_options_sizer.Add(self.attached_checkbox, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        attach_options_sizer.Add(attach_count_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        attach_options_sizer.Add(self.attach_count_spin, 0, wx.ALL, 5)
        main_sizer.Add(attach_options_sizer, 0, wx.EXPAND, 5)

        # --- Attached Sounds (Pack/Subfolder/Delay) ---
        for i in range(self.MAX_ATTACHED):
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)

            # NEW: Pack selection for this attached sound
            attached_pack_label = wx.StaticText(panel, label=f"Pack #{i+1}:")
            attached_pack_combo = wx.ComboBox(panel, style=wx.CB_READONLY, name=f"attached_pack_{i}")
            # Bind event to update its subfolder combo when pack changes
            attached_pack_combo.Bind(wx.EVT_COMBOBOX, lambda event, idx=i: self.on_attached_pack_selected(event, idx))

            # Subfolder selection for this attached sound
            attached_subfolder_label = wx.StaticText(panel, label=f"Subfolder #{i+1}:")
            attached_subfolder_combo = wx.ComboBox(panel, style=wx.CB_READONLY, name=f"attached_subfolder_{i}")

            delay_label = wx.StaticText(panel, label=f"Delay #{i+1} (ms):")
            delay_spin = wx.SpinCtrl(panel, min=0, max=5000, initial=500)

            # Hide them initially
            attached_pack_label.Hide()
            attached_pack_combo.Hide()
            attached_subfolder_label.Hide()
            attached_subfolder_combo.Hide()
            delay_label.Hide()
            delay_spin.Hide()

            self.attached_pack_combos.append(attached_pack_combo)
            self.attached_subfolder_combos.append(attached_subfolder_combo)
            self.attached_folder_delays.append(delay_spin)

            # Adjust proportions for more controls; using smaller padding (2)
            row_sizer.Add(attached_pack_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
            row_sizer.Add(attached_pack_combo, 1, wx.ALL | wx.EXPAND, 2) # Proportion 1
            row_sizer.Add(attached_subfolder_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
            row_sizer.Add(attached_subfolder_combo, 1, wx.ALL | wx.EXPAND, 2) # Proportion 1
            row_sizer.Add(delay_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
            row_sizer.Add(delay_spin, 0, wx.ALL, 2) # Proportion 0

            self.attached_sizers.append(row_sizer)
            main_sizer.Add(row_sizer, 0, wx.EXPAND)

        self.status_textbox = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 100))
        main_sizer.Add(self.status_textbox, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)
        self.Centre()
        self.Show()
        threading.Thread(target=self.load_initial_data, daemon=True).start()

    def load_initial_data(self):
        wx.CallAfter(self.update_status, "Scanning sound packs...")
        self._load_pack_names_from_disk()
        wx.CallAfter(self._populate_pack_ui)

    def _load_pack_names_from_disk(self):
        if not os.path.isdir(self.base_sounds_dir):
            self.pack_names = []
            wx.CallAfter(self.update_status, f"Error: Base sounds directory '{self.base_sounds_dir}' not found.")
            return
        try:
            self.pack_names = sorted([ # Sort pack names
                d for d in os.listdir(self.base_sounds_dir)
                if os.path.isdir(os.path.join(self.base_sounds_dir, d))
            ])
        except OSError as e:
            self.pack_names = []
            wx.CallAfter(self.update_status, f"Error scanning packs in '{self.base_sounds_dir}': {e}")
            return
        if not self.pack_names:
            wx.CallAfter(self.update_status, f"No sound packs found in '{self.base_sounds_dir}'.")

    def _populate_pack_ui(self):
        """Populates the main pack ComboBox and all attached pack ComboBoxes."""
        self.pack_combo.SetItems(self.pack_names)
        for combo in self.attached_pack_combos: # Populate all attached pack combos
            combo.SetItems(self.pack_names)

        if self.pack_names:
            self.pack_combo.SetSelection(0) # Triggers on_pack_selected for main pack

            # Set default selection for attached pack combos. This will trigger their
            # on_attached_pack_selected event, populating their subfolder combos.
            for i, attached_pk_combo in enumerate(self.attached_pack_combos):
                if attached_pk_combo.GetCount() > 0: # If it has pack names
                    current_val = attached_pk_combo.GetStringSelection()
                    # Set selection only if it's not already the first or if it's empty
                    if current_val != self.pack_names[0] or not current_val:
                         attached_pk_combo.SetSelection(0)
                    # If it was already set to the first item, event might not fire,
                    # so ensure subfolders are loaded if needed.
                    elif attached_pk_combo.GetStringSelection() == self.pack_names[0] and \
                         self.attached_subfolder_combos[i].GetCount() == 0:
                        self.on_attached_pack_selected(self.pack_names[0], i) # Manually trigger
        else:
            self.current_pack_name = None
            self._clear_and_update_subfolder_ui() # For main subfolder UI
            # Attached subfolder UIs will be empty because their pack combos are empty.
            self.update_status("Ready (no sound packs loaded).")

    def on_pack_selected(self, event):
        selected_pack = self.pack_combo.GetValue()
        if not selected_pack or selected_pack == self.current_pack_name:
            return
        self.current_pack_name = selected_pack
        self.sound_files = []
        self.step_folder_combo.SetValue("")
        # DO NOT clear attached folder selections here, as they are independent
        self._initiate_subfolder_load_for_current_pack()

    def _get_subfolders_for_pack(self, pack_name):
        """Synchronously gets subfolder names for a given pack_name."""
        if not pack_name:
            return []
        pack_path = os.path.join(self.base_sounds_dir, pack_name)
        if not os.path.isdir(pack_path):
            # self.update_status(f"Pack directory not found: {pack_path}") # Optional status
            return []
        try:
            return sorted([ # Sort subfolder names
                d for d in os.listdir(pack_path)
                if os.path.isdir(os.path.join(pack_path, d))
            ])
        except OSError as e:
            # self.update_status(f"Error reading subfolders for {pack_name}: {e}") # Optional
            return []

    def on_attached_pack_selected(self, event_or_pack_name, idx):
        """Handles pack selection in one of the ATTACHED pack ComboBoxes."""
        selected_pack_name = ""
        if isinstance(event_or_pack_name, wx.CommandEvent): # Called by event
            combo_box = event_or_pack_name.GetEventObject()
            selected_pack_name = combo_box.GetStringSelection()
        elif isinstance(event_or_pack_name, str): # Called manually (e.g. from _populate_pack_ui)
             selected_pack_name = event_or_pack_name
        else:
            return # Should not happen

        attached_subfolder_combo = self.attached_subfolder_combos[idx]
        attached_subfolder_combo.Clear()
        attached_subfolder_combo.SetValue("")

        if selected_pack_name:
            # Synchronously load subfolders for this specific pack
            subfolders = self._get_subfolders_for_pack(selected_pack_name)
            attached_subfolder_combo.SetItems(subfolders)
            if subfolders:
                attached_subfolder_combo.SetSelection(0)
        # If selected_pack_name is empty, subfolder combo remains empty

    def _initiate_subfolder_load_for_current_pack(self):
        if self.current_pack_name:
            self.update_status(f"Loading subfolders for main pack: {self.current_pack_name}...")
            threading.Thread(target=self._background_load_and_populate_main_subfolders, daemon=True).start()
        else:
            wx.CallAfter(self._clear_and_update_subfolder_ui)
            wx.CallAfter(self.update_status, "No main pack selected.")

    def _background_load_and_populate_main_subfolders(self):
        """Loads subfolders for the MAIN pack and populates its UI."""
        # This method now only affects the main step_folder_combo
        current_pack_subfolders = []
        if self.current_pack_name:
            current_pack_path = os.path.join(self.base_sounds_dir, self.current_pack_name)
            if os.path.isdir(current_pack_path):
                try:
                    current_pack_subfolders = sorted([ # Sort
                        d for d in os.listdir(current_pack_path)
                        if os.path.isdir(os.path.join(current_pack_path, d))
                    ])
                except OSError as e:
                    wx.CallAfter(self.update_status, f"Error scanning subfolders in '{current_pack_path}': {e}")
            else:
                 wx.CallAfter(self.update_status, f"Error: Main pack directory '{current_pack_path}' not found.")

        wx.CallAfter(self._populate_main_subfolder_ui, current_pack_subfolders)


    def _populate_main_subfolder_ui(self, subfolder_list):
        """Populates ONLY the MAIN subfolder ComboBox. Runs in the main UI thread."""
        self.sound_folders = subfolder_list # Store for the main pack
        self.step_folder_combo.Clear()
        self.step_folder_combo.SetItems(self.sound_folders)

        if self.sound_folders:
            self.step_folder_combo.SetSelection(0)
            evt = wx.CommandEvent(wx.wxEVT_COMBOBOX, self.step_folder_combo.GetId())
            evt.SetString(self.step_folder_combo.GetStringSelection())
            wx.PostEvent(self.step_folder_combo.GetEventHandler(), evt) # Trigger sound loading for this subfolder
        else:
            self.sound_files = []
            self.step_folder_combo.SetValue("")
            if self.current_pack_name: # Only if a pack is actually selected
                 wx.CallAfter(self.update_status, f"No subfolders found in main pack '{self.current_pack_name}'.")

        wx.CallAfter(self.update_status, "Ready.")


    def _clear_and_update_subfolder_ui(self):
        """Clears UI elements for the MAIN subfolder selection."""
        self.sound_folders = []
        self.step_folder_combo.Clear()
        self.step_folder_combo.SetItems([])
        self.step_folder_combo.SetValue("")
        self.sound_files = []

    def on_subfolder_selected(self, event):
        selected_subfolder = self.step_folder_combo.GetValue()
        if selected_subfolder and self.current_pack_name: # Ensure main pack is also selected
            self.sound_files = self.get_sound_files_from_subfolder(selected_subfolder, self.current_pack_name)
            if not self.sound_files:
                self.update_status(f"No sound files in '{selected_subfolder}' of pack '{self.current_pack_name}'.")
        else:
            self.sound_files = []

    def get_sound_files_from_subfolder(self, subfolder_name, pack_name):
        """Gets sound files from a specific subfolder OF A SPECIFIC PACK."""
        if not pack_name or not subfolder_name:
            return []
        folder_path = os.path.join(self.base_sounds_dir, pack_name, subfolder_name)
        if not os.path.isdir(folder_path):
            return []
        try:
            return [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f))
            ]
        except OSError as e:
            self.update_status(f"Error accessing files in '{folder_path}': {e}")
            return []

    def on_play_button(self, event):
        if self.sound_files: # Main sound is ready
            self.play_sound()
        else:
            # More detailed error messages
            if not self.pack_combo.GetValue():
                msg = "Please select a main sound pack."
            elif not self.step_folder_combo.GetValue():
                if not self.sound_folders:
                    msg = f"Main pack '{self.current_pack_name}' has no subfolders."
                else:
                    msg = "Please select a main subfolder."
            else:
                msg = f"No sound files in main selection: '{self.current_pack_name}/{self.step_folder_combo.GetValue()}'."
            wx.MessageBox(msg, "Cannot Play Sound", wx.OK | wx.ICON_INFORMATION)


    def play_sound(self):
        def get_pan():
            return random.uniform(-1.0, 1.0) if self.random_pan_checkbox.IsChecked() else 0.0

        main_sound = random.choice(self.sound_files)
        self.cacher.play(main_sound, pan=get_pan())

        if self.attached_checkbox.IsChecked():
            n = self.attach_count_spin.GetValue()
            chain = []
            for i in range(n):
                # Get pack and subfolder for THIS attached sound
                attached_pack_name = self.attached_pack_combos[i].GetValue().strip()
                attached_subfolder_name = self.attached_subfolder_combos[i].GetValue().strip()

                if attached_pack_name and attached_subfolder_name:
                    delay_seconds = self.attached_folder_delays[i].GetValue() / 1000.0
                    chain.append((attached_pack_name, attached_subfolder_name, delay_seconds))
                # else: # Silently skip if pack or subfolder not selected for an active attached row
                #    self.update_status(f"Skipping attached sound #{i+1}: Pack or Subfolder not selected.")

            cumulative_delay = 0
            for (pack_name, subfolder_name, delay_sec) in chain:
                # Get files from the specific pack and subfolder
                attached_files = self.get_sound_files_from_subfolder(subfolder_name, pack_name)
                if not attached_files:
                    self.update_status(f"Attached sound: '{subfolder_name}' in pack '{pack_name}' is empty/invalid. Skipping.")
                    continue

                attached_sound = random.choice(attached_files)
                cumulative_delay += delay_sec
                threading.Timer(
                    cumulative_delay,
                    self.cacher.play,
                    args=[attached_sound],
                    kwargs={'pan': get_pan()}
                ).start()

    def update_status(self, message):
        if not wx.IsMainThread():
            wx.CallAfter(self.status_textbox.AppendText, message + "\n")
        else:
            self.status_textbox.AppendText(message + "\n")

    def on_attach_checkbox_toggled(self, event):
        if self.attached_checkbox.IsChecked():
            self.attach_count_spin.Enable()
        else:
            self.attach_count_spin.Disable()
        self.update_attached_folder_visibility()

    def on_attach_count_changed(self, event):
        self.update_attached_folder_visibility()

    def update_attached_folder_visibility(self):
        """Shows/hides attached sound rows based on the checkbox and spin control value."""
        num_to_show = 0
        if self.attached_checkbox.IsChecked():
            num_to_show = self.attach_count_spin.GetValue()

        for i in range(self.MAX_ATTACHED):
            should_show_row = (i < num_to_show)
            for child_sizer_item in self.attached_sizers[i].GetChildren():
                widget = child_sizer_item.GetWindow()
                if widget:
                    if should_show_row:
                        widget.Show()
                    else:
                        widget.Hide()
        self.Layout() # Crucial to re-render the layout after show/hide


if __name__ == "__main__":
    app = wx.App(False)
    frame = SoundPlayer(None, "Sound Player - Advanced Attachments")
    app.MainLoop()