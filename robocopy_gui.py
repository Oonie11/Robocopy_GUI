import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import os
import signal
from datetime import datetime

# Constants
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 500
BACKGROUND_COLOR = "#2C3E50"  # Dark blue-gray
TEXT_COLOR = "#ECF0F1"  # Light gray
ENTRY_BACKGROUND = "#34495E"  # Slightly lighter blue-gray
BUTTON_COLOR = "#3498DB"  # Bright blue
BUTTON_TEXT_COLOR = "#FFFFFF"  # White
ACCENT_COLOR = "#3498DB"  # Bright red
HOVER_COLOR = "#2980B9"  # Darker blue for hover

# Tooltip class
class ToolTip:
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.x = self.y = 0

    def showtip(self):
        "Display text in tooltip window"
        if self.tip_window or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
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
        master.configure(bg=BACKGROUND_COLOR)
        master.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.create_widgets()
        self.current_log_file = None
        self.last_command_details = None  # To store last executed command details
        self.current_process = None  # To store the current subprocess

    def create_widgets(self):
        main_frame = tk.Frame(self.master, bg=BACKGROUND_COLOR, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(main_frame, text="Advanced File Copy", font=("Helvetica", 18, "bold"), bg=BACKGROUND_COLOR, fg=TEXT_COLOR)
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky="w")

        # Source and Destination
        tk.Label(main_frame, text="Source:", bg=BACKGROUND_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, sticky="w")
        self.source_entry = tk.Entry(main_frame, bg=ENTRY_BACKGROUND, fg=TEXT_COLOR, width=40)
        self.source_entry.grid(row=1, column=1, pady=2, sticky="we")
        tk.Button(main_frame, text="Browse", command=self.browse_source, bg=BUTTON_COLOR, fg=BUTTON_TEXT_COLOR, width=8).grid(row=1, column=2, padx=10, pady=5, sticky="e")

        tk.Label(main_frame, text="Destination:", bg=BACKGROUND_COLOR, fg=TEXT_COLOR).grid(row=2, column=0, sticky="w")
        self.dest_entry = tk.Entry(main_frame, bg=ENTRY_BACKGROUND, fg=TEXT_COLOR, width=40)
        self.dest_entry.grid(row=2, column=1, pady=2, sticky="we")
        tk.Button(main_frame, text="Browse", command=self.browse_dest, bg=BUTTON_COLOR, fg=BUTTON_TEXT_COLOR, width=8).grid(row=2, column=2, padx=10, sticky="e")

        # File Filter and Threads
        filter_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
        filter_frame.grid(row=3, column=0, columnspan=3, pady=(10, 5), sticky="we")

        tk.Label(filter_frame, text="File Filter:", bg=BACKGROUND_COLOR, fg=TEXT_COLOR).pack(side=tk.LEFT)
        self.filter_entry = tk.Entry(filter_frame, bg=ENTRY_BACKGROUND, fg=TEXT_COLOR, width=15)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_entry.insert(0, "*.*")

        tk.Label(filter_frame, text="Threads:", bg=BACKGROUND_COLOR, fg=TEXT_COLOR).pack(side=tk.LEFT)
        self.threads_entry = tk.Entry(filter_frame, bg=ENTRY_BACKGROUND, fg=TEXT_COLOR, width=5)
        self.threads_entry.pack(side=tk.LEFT)
        self.threads_entry.insert(0, "8")

        # Options
        options_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
        options_frame.grid(row=4, column=0, columnspan=3, pady=(5, 10), sticky="nswe")
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(4, weight=1)

        tk.Label(options_frame, text="Options:", bg=BACKGROUND_COLOR, fg=TEXT_COLOR, font=("Helvetica", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")

        self.options = [
            "/S", "/E", "/Z", "/B", "/MIR", "/MOV", "/MOVE", "/PURGE", "/XO",
            "/XC", "/XN", "/XX", "/XL", "/IS", "/IT", "/MAX:n", "/MIN:n", "/MAXAGE:n",
            "/MINAGE:n", "/R:n", "/W:n"
        ]

        self.option_vars = {option: tk.BooleanVar() for option in self.options}

        # Create a grid for the checkbuttons
        option_descriptions = {
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

        for i, option in enumerate(self.options):
            cb = ttk.Checkbutton(options_frame, text=option, variable=self.option_vars[option], style="Custom.TCheckbutton", command=self.update_command)
            cb.grid(row=1 + i // 4, column=i % 4, sticky="w", padx=5, pady=2)
            create_tooltip(cb, option_descriptions.get(option, "No description available"))

        # Configure column weights for dynamic resizing
        for col in range(4):
            options_frame.grid_columnconfigure(col, weight=1)

        # Command Preview
        preview_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
        preview_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=(0, 10))

        tk.Label(preview_frame, text="Command Preview:", bg=BACKGROUND_COLOR, fg=TEXT_COLOR, font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.preview_text = tk.Text(preview_frame, height=3, bg=ENTRY_BACKGROUND, fg=TEXT_COLOR, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.X, expand=True)

        # Buttons
        button_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
        button_frame.grid(row=6, column=0, columnspan=3, sticky="we", pady=(10, 5))

        # Store a reference to the "Open Destination" button
        self.open_dest_button = tk.Button(button_frame, text="Open Dest", command=self.open_destination, bg=BUTTON_COLOR, fg=BUTTON_TEXT_COLOR, width=12, state=tk.DISABLED)
        
        buttons = [
            ("Run", self.execute_command),
            ("Reset", self.reset_fields),
            ("Log", self.show_log),
            ("Help", self.show_help),
            ("Previous", self.load_previous_command),  # New Previous button
        ]

        # Configure equal column weights for buttons
        for i, (text, command) in enumerate(buttons):
            button = tk.Button(button_frame, text=text, command=command, bg=BUTTON_COLOR, fg=BUTTON_TEXT_COLOR, width=12)
            button.grid(row=0, column=i, padx=5, sticky="we")
            button_frame.grid_columnconfigure(i, weight=1)

        # Add the "Open Destination" button
        self.open_dest_button.grid(row=0, column=len(buttons), padx=5, sticky="we")
        button_frame.grid_columnconfigure(len(buttons), weight=1)

        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=7, column=0, columnspan=3, sticky="we", pady=(5, 10))

        # Status Label
        self.status_label = tk.Label(main_frame, text="", bg=BACKGROUND_COLOR, fg=TEXT_COLOR)
        self.status_label.grid(row=8, column=0, columnspan=3, sticky="we")

        # Bind events
        self.source_entry.bind("<KeyRelease>", self.update_command)
        self.dest_entry.bind("<KeyRelease>", self.update_command)
        self.filter_entry.bind("<KeyRelease>", self.update_command)
        self.threads_entry.bind("<KeyRelease>", self.update_command)

        # Initial command update
        self.update_command()

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, folder)
            self.update_command()

    def browse_dest(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, folder)
            self.update_command()

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

        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Generate a unique log file name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = os.path.join(logs_dir, f"robocopy_log_{timestamp}.txt")

        def run_command():
            try:
                with open(self.current_log_file, "w") as log_file:
                    self.current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
                    while True:
                        output = self.current_process.stdout.readline()
                        if output == '' and self.current_process.poll() is not None:
                            break
                        if output:
                            log_file.write(output)
                            log_file.flush()
                            self.master.after(0, self.update_progress, output)
                rc = self.current_process.poll()
                self.master.after(0, self.copy_finished, rc)
            except Exception as e:
                self.master.after(0, self.copy_error, str(e))

        threading.Thread(target=run_command, daemon=True).start()

    def update_progress(self, output):
        # Parse robocopy output for progress
        try:
            if "%" in output:
                # Example parsing logic
                progress = float(output.split("%")[0].strip().split()[-1])
                self.progress_var.set(progress)
        except (ValueError, IndexError):
            pass

    def copy_finished(self, return_code):
        if return_code in [0, 1]:  # Treat both 0 and 1 as successful
            self.status_label.config(text="Copy completed successfully!")
            # Enable the "Open Destination" button
            self.open_dest_button.config(state=tk.NORMAL)
            # Store the last command details
            self.last_command_details = {
                "source": self.source_entry.get(),
                "dest": self.dest_entry.get(),
                "filter": self.filter_entry.get(),
                "threads": self.threads_entry.get(),
                "options": {option: var.get() for option, var in self.option_vars.items()}
            }
        elif return_code == 15:
            self.status_label.config(text="Copy operation was stopped by the user.")
        else:
            self.status_label.config(text=f"Copy finished with return code: {return_code}")

    def copy_error(self, error_message):
        self.status_label.config(text=f"Error: {error_message}")

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
        # Disable the "Open Destination" button
        self.open_dest_button.config(state=tk.DISABLED)

    def show_log(self):
        if self.current_log_file and os.path.exists(self.current_log_file):
            try:
                os.startfile(self.current_log_file)
            except AttributeError:
                # For non-Windows systems
                import subprocess
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
            except Exception as e:
                # For non-Windows systems or if any error occurs
                try:
                    subprocess.call(["xdg-open", dest])
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open destination folder: {e}")
        else:
            messagebox.showwarning("Warning", "Destination folder does not exist.")

    def load_previous_command(self):
        if self.last_command_details:
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
        else:
            messagebox.showinfo("Previous", "No previous command found.")

if __name__ == "__main__":
    root = tk.Tk()
    
    # Apply custom styles to ttk widgets
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TProgressbar", 
                    thickness=20, 
                    troughcolor=ENTRY_BACKGROUND, 
                    background=ACCENT_COLOR)
    style.configure("TCheckbutton", 
                    background=BACKGROUND_COLOR, 
                    foreground=TEXT_COLOR)
    style.map("Custom.TCheckbutton",
              background=[('active', HOVER_COLOR)])  # Set hover color

    app = AdvancedFileCopyGUI(root)
    root.mainloop()
