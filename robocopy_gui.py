import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import signal
from datetime import datetime
import re
import logging
from queue import Queue, Empty
import json

# Configuration dictionary
CONFIG = {
    "WINDOW_WIDTH": 600,
    "WINDOW_HEIGHT": 525,
    "COLORS": {
        "BACKGROUND": "#2C3E50",
        "TEXT": "#ECF0F1",
        "ENTRY_BACKGROUND": "#34495E",
        "BUTTON": "#3498DB",
        "BUTTON_TEXT": "#FFFFFF",
        "ACCENT": "#3498DB",
        "HOVER": "#2980B9"
    },
    "FONTS": {
        "TITLE": ("Helvetica", 18, "bold"),
        "NORMAL": ("Helvetica", 10),
        "BOLD": ("Helvetica", 10, "bold")
    },
    "OPTION_DESCRIPTIONS": {
        "/S": "Copy subdirectories, but not empty ones",
        "/E": "Copy subdirectories, including empty ones",
        "/Z": "Copy files in restartable mode",
        "/B": "Copy files in backup mode",
        "/MIR": "Mirror a directory tree",
        "/MOV": "Move files (delete from source after copying)",
        "/MOVE": "Move files and directories",
        "/PURGE": "Delete destination files and directories that no longer exist in the source",
        "/XO": "Exclude older files",
        "/XC": "Exclude changed files",
        "/XN": "Exclude newer files",
        "/XX": "Exclude extra files and directories",
        "/XL": "Exclude lonely files and directories",
        "/IS": "Include same files",
        "/IT": "Include tweaked files",
        "/MAX:n": "Maximum file size - exclude files bigger than n bytes",
        "/MIN:n": "Minimum file size - exclude files smaller than n bytes",
        "/MAXAGE:n": "Maximum file age - exclude files older than n days",
        "/MINAGE:n": "Minimum file age - exclude files newer than n days",
        "/R:n": "Number of retries on failed copies",
        "/W:n": "Wait time between retries"
    }
}

def get_logs_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, 'all_logs')
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir

# Set up logging
logs_dir = get_logs_dir()
logging.basicConfig(filename=os.path.join(logs_dir, 'file_copy_gui.log'), level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class ToolTip:
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.tip_window = None

    def showtip(self):
        "Display text in tooltip window"
        if self.tip_window or not self.text:
            return
        x, y, _, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=CONFIG["FONTS"]["NORMAL"])
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

def create_tooltip(widget, text):
    tool_tip = ToolTip(widget, text)
    widget.bind('<Enter>', lambda event: tool_tip.showtip())
    widget.bind('<Leave>', lambda event: tool_tip.hidetip())

class AdvancedFileCopyGUI:
    def __init__(self, master):
        self.master = master
        master.title("Advanced File Copy")
        master.configure(bg=CONFIG["COLORS"]["BACKGROUND"])
        master.geometry(f"{CONFIG['WINDOW_WIDTH']}x{CONFIG['WINDOW_HEIGHT']}")

        self.create_widgets()
        self.current_log_file = None
        self.last_command_details = None
        self.current_process = None
        self.output_queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=1)

    def create_widgets(self):
        main_frame = tk.Frame(self.master, bg=CONFIG["COLORS"]["BACKGROUND"], padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.create_title(main_frame)
        self.create_source_dest_widgets(main_frame)
        self.create_filter_threads_widgets(main_frame)
        self.create_options_widgets(main_frame)
        self.create_preview_widget(main_frame)
        self.create_button_widgets(main_frame)
        self.create_progress_widgets(main_frame)

        self.bind_events()

    def create_title(self, parent):
        title_label = tk.Label(parent, text="Advanced File Copy", font=CONFIG["FONTS"]["TITLE"],
                               bg=CONFIG["COLORS"]["BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"])
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky="w")

    def create_source_dest_widgets(self, parent):
        tk.Label(parent, text="Source:", bg=CONFIG["COLORS"]["BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"]).grid(row=1, column=0, sticky="w")
        self.source_entry = tk.Entry(parent, bg=CONFIG["COLORS"]["ENTRY_BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"], width=40)
        self.source_entry.grid(row=1, column=1, pady=2, sticky="we")
        tk.Button(parent, text="Browse", command=self.browse_source, bg=CONFIG["COLORS"]["BUTTON"],
                  fg=CONFIG["COLORS"]["BUTTON_TEXT"], width=8).grid(row=1, column=2, padx=10, pady=5, sticky="e")

        tk.Label(parent, text="Destination:", bg=CONFIG["COLORS"]["BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"]).grid(row=2, column=0, sticky="w")
        self.dest_entry = tk.Entry(parent, bg=CONFIG["COLORS"]["ENTRY_BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"], width=40)
        self.dest_entry.grid(row=2, column=1, pady=2, sticky="we")
        tk.Button(parent, text="Browse", command=self.browse_dest, bg=CONFIG["COLORS"]["BUTTON"],
                  fg=CONFIG["COLORS"]["BUTTON_TEXT"], width=8).grid(row=2, column=2, padx=10, sticky="e")

    def create_filter_threads_widgets(self, parent):
        filter_frame = tk.Frame(parent, bg=CONFIG["COLORS"]["BACKGROUND"])
        filter_frame.grid(row=3, column=0, columnspan=3, pady=(10, 5), sticky="we")

        tk.Label(filter_frame, text="File Filter:", bg=CONFIG["COLORS"]["BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"]).pack(side=tk.LEFT)
        self.filter_entry = tk.Entry(filter_frame, bg=CONFIG["COLORS"]["ENTRY_BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"], width=15)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_entry.insert(0, "*.*")

        tk.Label(filter_frame, text="Threads:", bg=CONFIG["COLORS"]["BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"]).pack(side=tk.LEFT)
        self.threads_entry = tk.Entry(filter_frame, bg=CONFIG["COLORS"]["ENTRY_BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"], width=5)
        self.threads_entry.pack(side=tk.LEFT)
        self.threads_entry.insert(0, "8")

    def create_options_widgets(self, parent):
        options_frame = tk.Frame(parent, bg=CONFIG["COLORS"]["BACKGROUND"])
        options_frame.grid(row=4, column=0, columnspan=3, pady=(5, 10), sticky="nswe")
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(4, weight=1)

        tk.Label(options_frame, text="Options:", bg=CONFIG["COLORS"]["BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"],
                 font=CONFIG["FONTS"]["BOLD"]).grid(row=0, column=0, columnspan=4, sticky="w")

        self.options = list(CONFIG["OPTION_DESCRIPTIONS"].keys())
        self.option_vars = {option: tk.BooleanVar() for option in self.options}

        for i, option in enumerate(self.options):
            cb = ttk.Checkbutton(options_frame, text=option, variable=self.option_vars[option],
                                 style="Custom.TCheckbutton", command=self.update_command)
            cb.grid(row=1 + i // 4, column=i % 4, sticky="w", padx=5, pady=2)
            create_tooltip(cb, CONFIG["OPTION_DESCRIPTIONS"][option])

        for col in range(4):
            options_frame.grid_columnconfigure(col, weight=1)

    def create_preview_widget(self, parent):
        preview_frame = tk.Frame(parent, bg=CONFIG["COLORS"]["BACKGROUND"])
        preview_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=(0, 10))

        tk.Label(preview_frame, text="Command Preview:", bg=CONFIG["COLORS"]["BACKGROUND"],
                 fg=CONFIG["COLORS"]["TEXT"], font=CONFIG["FONTS"]["BOLD"]).pack(anchor="w")
        self.preview_text = tk.Text(preview_frame, height=3, bg=CONFIG["COLORS"]["ENTRY_BACKGROUND"],
                                    fg=CONFIG["COLORS"]["TEXT"], wrap=tk.WORD)
        self.preview_text.pack(fill=tk.X, expand=True)

    def create_button_widgets(self, parent):
        button_frame = tk.Frame(parent, bg=CONFIG["COLORS"]["BACKGROUND"])
        button_frame.grid(row=6, column=0, columnspan=3, sticky="we", pady=(10, 5))

        self.open_dest_button = tk.Button(button_frame, text="Open Dest", command=self.open_destination,
                                          bg=CONFIG["COLORS"]["BUTTON"], fg=CONFIG["COLORS"]["BUTTON_TEXT"],
                                          width=12, state=tk.DISABLED)

        buttons = [
            ("Run", self.execute_command),
            ("Reset", self.reset_fields),
            ("Log", self.show_log),
            ("Help", self.show_help),
            ("Previous", self.load_previous_command),
        ]

        for i, (text, command) in enumerate(buttons):
            button = tk.Button(button_frame, text=text, command=command, bg=CONFIG["COLORS"]["BUTTON"],
                               fg=CONFIG["COLORS"]["BUTTON_TEXT"], width=12)
            button.grid(row=0, column=i, padx=5, sticky="we")
            button_frame.grid_columnconfigure(i, weight=1)

        self.open_dest_button.grid(row=0, column=len(buttons), padx=5, sticky="we")
        button_frame.grid_columnconfigure(len(buttons), weight=1)

    def create_progress_widgets(self, parent):
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(parent, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=7, column=0, columnspan=3, sticky="we", pady=(5, 10))

        self.status_label = tk.Label(parent, text="", bg=CONFIG["COLORS"]["BACKGROUND"], fg=CONFIG["COLORS"]["TEXT"])
        self.status_label.grid(row=8, column=0, columnspan=3, sticky="we")

    def bind_events(self):
        self.source_entry.bind("<KeyRelease>", self.update_command)
        self.dest_entry.bind("<KeyRelease>", self.update_command)
        self.filter_entry.bind("<KeyRelease>", self.update_command)
        self.threads_entry.bind("<KeyRelease>", self.update_command)

    def browse_folder(self, entry_widget):
        folder = filedialog.askdirectory()
        if folder:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder)
            self.update_command()

    def browse_source(self):
        self.browse_folder(self.source_entry)

    def browse_dest(self):
        self.browse_folder(self.dest_entry)

    def update_command(self, event=None):
        source = self.source_entry.get()
        dest = self.dest_entry.get()
        file_filter = self.filter_entry.get()
        threads = self.threads_entry.get()

        command = f'robocopy "{source}" "{dest}" {file_filter} /MT:{threads}'

        for option, var in self.option_vars.items():
            if var.get():
                command += f" {option}"

        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, command)

    def execute_command(self):
        command = self.preview_text.get(1.0, tk.END).strip()
        if not command:
            messagebox.showerror("Error", "No command to execute. Please fill in the required fields.")
            return

        self.progress_var.set(0)
        self.status_label.config(text="Copying in progress...")

        logs_dir = get_logs_dir()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = os.path.join(logs_dir, f"robocopy_log_{timestamp}.txt")

        self.executor.submit(self.run_command, command)

    def run_command(self, command):
        try:
            with open(self.current_log_file, "w") as log_file:
                self.current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
                while True:
                    line = self.current_process.stdout.readline()
                    if not line:
                        break
                    log_file.write(line)
                    log_file.flush()
                    self.output_queue.put(line)
                    self.master.after(10, self.process_output)
                rc = self.current_process.wait()
                self.output_queue.put(("DONE", rc))
        except Exception as e:
            self.output_queue.put(("ERROR", str(e)))

        self.master.after(100, self.process_output)

    def process_output(self):
        try:
            while True:
                item = self.output_queue.get_nowait()
                if isinstance(item, tuple):
                    if item[0] == "DONE":
                        self.copy_finished(item[1])
                        return
                    elif item[0] == "ERROR":
                        self.copy_error(item[1])
                        return
                else:
                    self.update_progress(item)
        except Empty:
            self.master.after(100, self.process_output)

    def update_progress(self, output):
        progress_pattern = r'(\d+(?:\.\d+)?)%'
        match = re.search(progress_pattern, output)
        if match:
            try:
                progress = float(match.group(1))
                self.progress_var.set(progress)
            except ValueError:
                logging.warning(f"Failed to parse progress from: {output}")
        
        # Update status label with the latest output
        self.status_label.config(text=output.strip())

    def copy_finished(self, return_code):
        if return_code in [0, 1]:  # Treat both 0 and 1 as successful
            self.status_label.config(text="Copy completed successfully!")
            self.open_dest_button.config(state=tk.NORMAL)
            self.save_last_command()
        else:
            self.status_label.config(text=f"Copy finished with return code: {return_code}")
        logging.info(f"Copy operation finished with return code: {return_code}")

    def copy_error(self, error_message):
        self.status_label.config(text=f"Error: {error_message}")
        logging.error(f"Copy operation error: {error_message}")

    def save_last_command(self):
        self.last_command_details = {
            "source": self.source_entry.get(),
            "dest": self.dest_entry.get(),
            "filter": self.filter_entry.get(),
            "threads": self.threads_entry.get(),
            "options": {option: var.get() for option, var in self.option_vars.items()}
        }
        with open(os.path.join(get_logs_dir(), 'last_command.json'), 'w') as f:
            json.dump(self.last_command_details, f)

    def reset_fields(self):
        self.source_entry.delete(0, tk.END)
        self.dest_entry.delete(0, tk.END)
        self.filter_entry.delete(0, tk.END)
        self.filter_entry.insert(0, "*.*")
        self.threads_entry.delete(0, tk.END)
        self.threads_entry.insert(0, "8")
        for var in self.option_vars.values():
            var.set(False)
        self.update_command()
        self.progress_var.set(0)
        self.status_label.config(text="")
        self.open_dest_button.config(state=tk.DISABLED)

    def show_log(self):
        if self.current_log_file and os.path.exists(self.current_log_file):
            try:
                os.startfile(self.current_log_file)
            except AttributeError:
                # For non-Windows systems
                subprocess.call(["xdg-open", self.current_log_file])
        else:
            messagebox.showinfo("Log", "No log file available. Please run a copy operation first.")

    def show_help(self):
        help_text = """
        Advanced File Copy Help:
        
        1. Source: Select the folder you want to copy from.
        2. Destination: Select the folder you want to copy to.
        3. File Filter: Specify which files to copy (e.g., *.txt for all text files).
        4. Threads: Number of threads for multi-threaded copying.
        5. Options: Select additional Robocopy options as needed.
        6. Run: Executes the generated Robocopy command.
        7. Reset: Clears all fields and selections.
        8. Log: Opens the most recent log file.
        9. Help: Shows this help message.
        10. Open Destination: Opens the destination folder after a successful copy.
        11. Previous: Restores the last executed operation's settings.
        """
        messagebox.showinfo("Help", help_text)

    def open_destination(self):
        dest = self.dest_entry.get()
        if os.path.isdir(dest):
            try:
                os.startfile(dest)
            except AttributeError:
                # For non-Windows systems
                try:
                    subprocess.call(["xdg-open", dest])
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open destination folder: {e}")
                    logging.error(f"Failed to open destination folder: {e}")
        else:
            messagebox.showwarning("Warning", "Destination folder does not exist.")

    def load_previous_command(self):
        try:
            with open(os.path.join(get_logs_dir(), 'last_command.json'), 'r') as f:
                self.last_command_details = json.load(f)
            
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, self.last_command_details["source"])
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, self.last_command_details["dest"])
            self.filter_entry.delete(0, tk.END)
            self.filter_entry.insert(0, self.last_command_details["filter"])
            self.threads_entry.delete(0, tk.END)
            self.threads_entry.insert(0, self.last_command_details["threads"])
            for option, value in self.last_command_details["options"].items():
                self.option_vars[option].set(value)
            self.update_command()
        except FileNotFoundError:
            messagebox.showinfo("Previous", "No previous command found.")
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Failed to load previous command. File may be corrupted.")
            logging.error("Failed to load previous command due to JSON decode error.")

if __name__ == "__main__":
    root = tk.Tk()
    
    # Apply custom styles to ttk widgets
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TProgressbar", 
                    thickness=20, 
                    troughcolor=CONFIG["COLORS"]["ENTRY_BACKGROUND"], 
                    background=CONFIG["COLORS"]["ACCENT"])
    style.configure("TCheckbutton", 
                    background=CONFIG["COLORS"]["BACKGROUND"], 
                    foreground=CONFIG["COLORS"]["TEXT"])
    style.map("Custom.TCheckbutton",
              background=[('active', CONFIG["COLORS"]["HOVER"])])

    app = AdvancedFileCopyGUI(root)
    root.mainloop()
