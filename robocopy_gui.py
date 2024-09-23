import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import os
import datetime
import logging
import sys

ROBOCOPY_OPTIONS = [
    ("/S", "Copy subdirectories, but not empty ones."),
    ("/E", "Copy subdirectories, including empty ones."),
    ("/Z", "Copy files in restartable mode."),
    ("/B", "Copy files in Backup mode."),
    ("/MIR", "Mirror a directory tree (equivalent to /E plus /PURGE)."),
    ("/MOV", "Move files (delete from source after copying)."),
    ("/MOVE", "Move files and dirs (delete from source after copying)."),
    ("/PURGE", "Delete dest files/dirs that no longer exist in source."),
    ("/XO", "Exclude older files."),
    ("/XC", "Exclude changed files."),
    ("/XN", "Exclude newer files."),
    ("/XX", "Exclude extra files and directories."),
    ("/XL", "Exclude 'lonely' files and directories."),
    ("/IS", "Include same files."),
    ("/IT", "Include tweaked files."),
    ("/MAX:n", "Maximum file size - exclude files bigger than n bytes."),
    ("/MIN:n", "Minimum file size - exclude files smaller than n bytes."),
    ("/MAXAGE:n", "Maximum file age - exclude files older than n days/date."),
    ("/MINAGE:n", "Minimum file age - exclude files newer than n days/date."),
    ("/R:n", "Number of retries on failed copies - default is 1 million."),
    ("/W:n", "Wait time between retries - default is 30 seconds."),
]

class AdvancedFileCopyGUI:
    def __init__(self, master):
        self.master = master
        master.title("Advanced File Copy GUI")
        master.geometry("650x350")
        master.resizable(False, False)

        self.setup_logging()
        self.create_widgets()

    def setup_logging(self):
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        log_dir = os.path.join(script_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"file_copy_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        logging.basicConfig(filename=log_file, level=logging.INFO, 
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def create_widgets(self):
        self.entries = {}
        for i, (label, command) in enumerate([("Source Folder:", self.browse_source), 
                                              ("Destination Folder:", self.browse_dest)]):
            self.entries[label] = self.create_entry(label, i, command)

        filter_frame = ttk.Frame(self.master)
        filter_frame.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        self.file_filter = tk.StringVar(value="*.*")
        self.thread_var = tk.StringVar(value="8")
        
        for label, var, width in [("File Type Filter:", self.file_filter, 10), 
                                  ("Threads:", self.thread_var, 5)]:
            tk.Label(filter_frame, text=label).pack(side=tk.LEFT, padx=(0, 5))
            entry = tk.Entry(filter_frame, textvariable=var, width=width)
            entry.pack(side=tk.LEFT, padx=(0, 10))
            entry.bind('<KeyRelease>', self.update_preview)

        options_frame = ttk.Frame(self.master)
        options_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        self.create_options(options_frame)

        tk.Label(self.master, text="Command Preview:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        preview_frame = ttk.Frame(self.master)
        preview_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        self.preview_text = tk.Text(preview_frame, height=3, width=70, wrap=tk.WORD, state='disabled', bg='#F0F0F0')
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(self.master)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        self.create_buttons(button_frame)

        self.progress = ttk.Progressbar(self.master, length=300, mode='indeterminate')
        self.progress.grid(row=7, column=0, columnspan=3, padx=5, pady=5)

        for i in range(3):
            self.master.grid_columnconfigure(i, weight=1)
        for i in (3, 5):
            self.master.grid_rowconfigure(i, weight=1)

    def create_entry(self, label_text, row, command):
        tk.Label(self.master, text=label_text).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        entry = tk.Entry(self.master, width=40)
        entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(self.master, text="Browse", command=command).grid(row=row, column=2, padx=5, pady=5)
        entry.bind('<KeyRelease>', self.update_preview)
        return entry

    def create_options(self, frame):
        self.option_vars = {option: tk.BooleanVar() for option, _ in ROBOCOPY_OPTIONS}
        for i, (option, description) in enumerate(ROBOCOPY_OPTIONS):
            cb = ttk.Checkbutton(frame, text=option, variable=self.option_vars[option], command=self.update_preview)
            cb.grid(row=i//10, column=i%10, sticky="w", padx=2, pady=1)
            self.create_tooltip(cb, description)

    def create_buttons(self, frame):
        for text, command in [("Run Copy", self.run_copy), ("Reset", self.reset_fields), 
                              ("Log", self.open_log_folder), ("Help", self.show_help)]:
            tk.Button(frame, text=text, command=command, width=15).pack(side=tk.LEFT, padx=30)

    def create_tooltip(self, widget, text):
        widget.bind("<Enter>", lambda event: self.show_tooltip(event, text))
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event, text):
        self.tooltip = tk.Toplevel(self.master)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
        tk.Label(self.tooltip, text=text, justify='left', background="#ffffff", 
                 relief='solid', borderwidth=1, wraplength=300).pack(ipadx=1)

    def hide_tooltip(self, event):
        if hasattr(self, 'tooltip'):
            self.tooltip.destroy()

    def browse_folder(self, entry):
        folder = filedialog.askdirectory()
        if folder:
            entry.delete(0, tk.END)
            entry.insert(0, folder)
        self.update_preview()

    def browse_source(self):
        self.browse_folder(self.entries["Source Folder:"])

    def browse_dest(self):
        self.browse_folder(self.entries["Destination Folder:"])

    def reset_fields(self):
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        for var in self.option_vars.values():
            var.set(False)
        self.thread_var.set("8")
        self.file_filter.set("*.*")
        self.update_preview()

    def run_copy(self):
        source = self.entries["Source Folder:"].get()
        dest = self.entries["Destination Folder:"].get()
        
        if not source or not dest:
            messagebox.showerror("Error", "Please select both source and destination folders.")
            return

        command = self.construct_command()
        
        logging.info(f"Starting copy operation with command: {' '.join(command)}")
        self.progress.start()
        threading.Thread(target=self.execute_command, args=(command,), daemon=True).start()

    def construct_command(self):
        command = ["robocopy", self.entries["Source Folder:"].get(), self.entries["Destination Folder:"].get(), self.file_filter.get()]
        command.extend(option for option, var in self.option_vars.items() if var.get())
        threads = self.thread_var.get()
        if threads and threads.isdigit():
            command.append(f"/MT:{threads}")
        return command

    def execute_command(self, command):
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            stdout, stderr = process.communicate()
            
            self.master.after(0, self.progress.stop)
            
            if process.returncode > 1:  # Robocopy uses return codes 0-8, 0-1 are successful
                self.log_and_show_message("Error", f"Error occurred:\n{stderr}", logging.error)
            else:
                self.log_and_show_message("Success", f"Operation completed successfully.\nOutput:\n{stdout}", logging.info)
        except Exception as e:
            self.master.after(0, self.progress.stop)
            self.log_and_show_message("Error", f"An error occurred: {str(e)}", logging.error)

    def log_and_show_message(self, title, message, log_func):
        log_func(f"{title}: {message}")
        self.master.after(0, lambda: messagebox.showinfo(title, message))

    def show_help(self):
        help_text = """
        Advanced File Copy GUI Help:

        - Source Folder: Select the folder you want to copy from.
        - Destination Folder: Select the folder you want to copy to.
        - File Type Filter: Specify file types to copy (e.g., *.txt, *.docx).
        - Threads: Set the number of threads for multithreaded copying.
        - Options: Select the desired Robocopy options. Hover over each option for a description.
        - Command Preview: Shows the Robocopy command that will be executed.
        - Run Copy: Executes the Robocopy command.
        - Reset: Clears all fields and resets options.
        - Log: Opens the folder containing log files.

        Note: This tool uses Robocopy, which is specific to Windows systems.
        Log files are saved in the 'logs' folder in the same directory as this script.
        """
        messagebox.showinfo("Help", help_text)

    def update_preview(self, *args):
        command = self.construct_command()
        preview_text = " ".join(command)
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.insert(tk.END, preview_text)
        self.preview_text.configure(state='disabled')

    def open_log_folder(self):
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        log_dir = os.path.join(script_dir, 'logs')
        os.startfile(log_dir)

def main():
    root = tk.Tk()
    app = AdvancedFileCopyGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
