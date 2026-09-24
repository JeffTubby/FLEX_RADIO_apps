import sys
import socket
import tkinter as tk

class MyDialog(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        
        #---Initialize attributes to hold your final data safely
        self.radio_ip = "No Radio"
        self.r_callsign = "No Radio"
        self.my_option = None
        self.current_scale_value = None

        #---Dialog Box    
        self.create_widgets()
    
    #---Dialog Box
    def create_widgets(self):
    #---Get the Radio IP and callsign from radio functions
    
        self.radio_ip = find_flex_radio_ip()
        self.r_callsign = get_flex_callsign()

        #---Assign local helper variables for your entry boxes and color check
        RADIO_IP = self.radio_ip
        r_callsign = self.r_callsign

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=0)
        
        #---Make label
        tk.Label(self, text="RADIO IP").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        tk.Label(self, text="Callsign").grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.entry1 = tk.Entry(self)
        self.entry2 = tk.Entry(self)  
        self.entry1.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.entry2.grid(row=1, column=1, sticky="w", padx=5, pady=5)  

        # Check for None values before inserting into text entries
        self.entry1.insert(0, RADIO_IP if RADIO_IP is not None else "No Radio")
        self.entry2.insert(0, r_callsign if r_callsign is not None else "No Radio")  

        rb_frame = tk.Frame(self)
        rb_frame.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=10)

        self.v = tk.IntVar(value=3)

        tk.Radiobutton(rb_frame, text="Only CQ Calls", variable=self.v, value=1).pack(anchor="w")
        tk.Radiobutton(rb_frame, text="Only CQ POTA Calls", variable=self.v, value=2).pack(anchor="w")
        tk.Radiobutton(rb_frame, text="No Filters (all valid decodes)", variable=self.v, value=3).pack(anchor="w")

        right_frame = tk.Frame(self)
        right_frame.grid(row=0, column=2, rowspan=5, sticky="ne", padx=5, pady=5)

        scale_value_var = tk.StringVar(value="300")

        def update_scale_value(value):
            value = int(float(value))
            scale_value_var.set(str(value))

        self.vertical_scale = tk.Scale(right_frame, from_=600, to=60, orient="vertical", command=update_scale_value)
        self.vertical_scale.set(300)
        self.vertical_scale.pack(side="top")

        tk.Label(right_frame, textvariable=scale_value_var, font=("Arial", 10, "bold")).pack(side="top", pady=(5, 2))
        tk.Label(right_frame, text="Lifetime").pack(side="top")

        button = tk.Button(self, text="Apply", width=12, command=self.select_and_close)
        button.grid(row=3, column=0, columnspan=3, sticky="", padx=3, pady=5)
        
        # Safe comparison to see if an IP string actually exists
        if RADIO_IP is not None and RADIO_IP != "No Radio":
            button.config(bg="light green")
        else:
            button.config(text="No radio", bg="light coral")

    def select_and_close(self):
        # Save values directly to the class instance attributes
        self.radio_ip = self.entry1.get()
        self.r_callsign = self.entry2.get()  
        self.my_option = self.v.get()
        self.current_scale_value = self.vertical_scale.get()

        # FIX: Use quit() instead of destroy() so main() can read data before it's deleted
        self.master.quit()

def find_flex_radio_ip():
    """ 
    Listens to the local network for a FlexRadio broadcast packet 
    and returns its active IP address string.
    """
    # Create a standard UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # Bind to the standard FlexRadio discovery broadcast port
        sock.bind(('', 4992))
        sock.settimeout(2.0)  # Stop waiting after 2 seconds if no radio is found
        
        # Capture the incoming network packet
        data, addr = sock.recvfrom(2048)
        
        # The sender's IP address is stored inside the 'addr' tuple at index 0
        discovered_ip = addr[0] 
        return str(discovered_ip)
        
    except socket.timeout:
        # If no radio responds within 2 seconds, safely return None
        return None
        
    finally:
        sock.close()  # Always free up the network port
    return RADIO_IP

def get_flex_callsign(callsign=None):
    """This function gets callsign from radio"""
     
    API_PORT = 4992 
    fallback_return = "No Radio"

#---Get ip address
    RADIO_IP = find_flex_radio_ip()
    API_PORT = 4992

    try:
        # Connect to the radio
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # FIX 1: Set a timeout so s.recv() doesn't block indefinitely
            s.settimeout(3.0)
            s.connect((RADIO_IP, API_PORT))
            
            # Send the sub all command to subscribe to all radio status updates
            s.sendall(b"C1|sub radio all\n")
            
            # Read radio responses in a loop looking for callsign
            while True:
                data = s.recv(1024).decode('utf-8', errors='ignore')
                if not data:
                    break
                
                # Look for properties in the status stream
                for line in data.splitlines():
                    if "callsign=" in line:
                        # Extract the callsign value
                        parts = line.split()
                        for part in parts:
                            if part.startswith("callsign="):
                                return part.split("=")[1]

    # FIX 2: Catch timeouts and network errors gracefully
    except (socket.timeout, socket.error) as e:
        print(f"Network issue or timeout: {e}")
    except Exception as e:
        print(f"Error connecting to radio: {e}")

    return "No Radio"

def main():
    root = tk.Tk()
    root.title("FLEX RADIO")
    root.geometry("300x200")
    root.resizable(False, False)
    root.columnconfigure(2, weight=1)
    
    app = MyDialog(master=root)

    # The script blocks here until the user clicks Apply (triggering master.quit())
    root.mainloop()
    
    # Read the values from the app instance safely while it still exists in memory
    fetched_radio_ip = app.radio_ip
    fetch_r_callsign = app.r_callsign
    my_option = app.my_option
    current_scale_value = app.current_scale_value

    # Clean up and completely close the underlying window system now
    root.destroy()

    # Use your variables now in main()
    print("\n--- Data received inside main() ---")
    print(f"RADIO_IP: {fetched_radio_ip}")
    print(f"Callsign: {fetch_r_callsign}")
    print(f"my_option: {my_option}")
    print(f"current_scale_value: {current_scale_value}")
    print(find_flex_radio_ip())

if __name__ == "__main__":
    main()

