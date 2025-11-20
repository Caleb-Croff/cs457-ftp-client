# ftp_gui.py
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import os
from ftp_client import FTPClient

class FTPGui:
    def __init__(self, root):
        self.root = root
        self.root.title("FTP Client - GUI")

        self.client = FTPClient()

        # ======================
        # Top: Host entry + connect button
        # ======================
        host_frame = ttk.Frame(root)
        host_frame.pack(padx=10, pady=10, fill="x")

        ttk.Label(host_frame, text="Host:").pack(side="left")
        self.host_entry = ttk.Entry(host_frame, width=30)
        self.host_entry.pack(side="left", padx=5)

        ttk.Button(host_frame, text="Connect", command=self.connect).pack(side="left", padx=5)
        ttk.Button(host_frame, text="Disconnect", command=self.disconnect).pack(side="left", padx=5)
        ttk.Button(host_frame, text="Quit", command=root.quit).pack(side="right")

        # ======================
        # Response console (scrollable)
        # ======================
        console_frame = ttk.LabelFrame(root, text="Server Responses")
        console_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.console = tk.Text(console_frame, height=12)
        self.console.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(console_frame, command=self.console.yview)
        scrollbar.pack(side="right", fill="y")
        self.console.configure(yscrollcommand=scrollbar.set)

        # ======================
        # File lists (local + remote)
        # ======================
        lists_frame = ttk.Frame(root)
        lists_frame.pack(padx=10, pady=5, fill="both", expand=True)

        # Local files
        local_frame = ttk.LabelFrame(lists_frame, text="Local Files")
        local_frame.pack(side="left", fill="both", expand=True, padx=5)

        self.local_list = tk.Listbox(local_frame)
        self.local_list.pack(fill="both", expand=True)
        self.local_list.bind("<Double-Button-1>", self.upload_file)

        # Remote files
        remote_frame = ttk.LabelFrame(lists_frame, text="Remote Files")
        remote_frame.pack(side="right", fill="both", expand=True, padx=5)

        self.remote_list = tk.Listbox(remote_frame)
        self.remote_list.pack(fill="both", expand=True)
        self.remote_list.bind("<Double-Button-1>", self.remote_file_action)

        self.refresh_local_files()

    # ======================
    # Backend interactions
    # ======================
    def log(self, text):
        self.console.insert("end", text + "\n")
        self.console.see("end")

    def connect(self):
        host = self.host_entry.get().strip()
        if not host:
            messagebox.showerror("Error", "Host field is empty.")
            return

        try:
            resp = self.client.connect(host)
            self.log(str(resp))

            # Modal login dialog
            user = simpledialog.askstring("Login", "Username:")
            pwd = simpledialog.askstring("Login", "Password:", show="*")
            if user:
                self.log(f"SENT: USER {user}")
                self.log(str(self.client.send_command(f"USER {user}")))
            if pwd:
                self.log(f"SENT: PASS ******")
                self.log(str(self.client.send_command(f"PASS {pwd}")))

            self.list_remote()

        except Exception as e:
            self.log(f"Error: {e}")

    def disconnect(self):
        try:
            self.client.quit()
            self.log("Disconnected.")
            self.remote_list.delete(0, "end")
        except Exception as e:
            self.log(f"Error: {e}")

    def list_remote(self):
        # TODO: integrate handle_list output parsing
        pass

    def refresh_local_files(self):
        self.local_list.delete(0, "end")
        for f in os.listdir("."):
            self.local_list.insert("end", f)

    def upload_file(self, event):
        pass

    def remote_file_action(self, event):
        pass


if __name__ == "__main__":
    root = tk.Tk()
    app = FTPGui(root)
    root.mainloop()
