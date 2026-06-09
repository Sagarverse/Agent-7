import sys
import os
import tkinter as tk
import subprocess

class OverlayController:
    """Controls an overlay by spawning a separate python process for Tkinter."""
    def __init__(self):
        self.process = None

    def start(self):
        """Start the overlay subprocess."""
        # Use the same python executable to avoid env issues
        self.process = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )

    def show(self, text: str):
        """Send text to the overlay subprocess."""
        if self.process and self.process.poll() is None:
            # Send the text followed by a newline, replacing actual newlines to keep it one line
            safe_text = text.replace('\n', ' || ')
            try:
                self.process.stdin.write(f"SHOW:{safe_text}\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def hide(self):
        """Hide the overlay."""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write("HIDE\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def stop(self):
        """Kill the subprocess."""
        if self.process:
            self.process.terminate()

# The standalone Tkinter application
if __name__ == "__main__":
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.8)
    root.configure(bg='black')

    label = tk.Label(
        root, 
        text="Waiting for MCQ...", 
        font=("Helvetica", 20, "bold"), 
        fg="white", 
        bg="black",
        padx=20,
        pady=10
    )
    label.pack()

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    x = 50
    y = screen_height - 100
    root.geometry(f"+{x}+{y}")
    
    root.withdraw() # Start hidden
    is_visible = False

    def check_stdin():
        global is_visible
        import select
        # Read available lines from stdin without blocking
        while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline()
            if not line: # EOF
                root.quit()
                return
            
            line = line.strip()
            if line.startswith("SHOW:"):
                text = line[5:].replace(' || ', '\n')
                label.config(text=text)
                if not is_visible:
                    root.deiconify()
                    is_visible = True
            elif line == "HIDE":
                if is_visible:
                    root.withdraw()
                    is_visible = False
                    
        # Check again in 100ms
        root.after(100, check_stdin)

    root.after(100, check_stdin)
    root.mainloop()
