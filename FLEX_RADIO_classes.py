# FLEX Radio Classes for IP discovery and callsign retrieval
# Author: Jeff Tubbenhauer VK5IU
# Date: 22/10/2026
# This version provides classes for discovering the FLEX Radio IP and retrieving its callsign.
# Version 2.0 simplifies the discovery and retrieval process using classes.


import socket
import geocoder
import tkinter as tk

API_PORT = 4992  
RADIO_IP = None


def _get_slice_value(radio_ip, api_port, key, timeout):
    """Subscribe to slice updates and return the requested property value."""
    if not radio_ip:
        return None

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((radio_ip, api_port))
            sock.sendall(b"C1|sub slice all\n")

            buffer = ""
            while True:
                data = sock.recv(1024).decode("utf-8", errors="ignore")
                if not data:
                    break

                lines = (buffer + data).split("\n")
                buffer = lines.pop()
                for line in lines:
                    for part in line.replace("|", " ").split():
                        if part.startswith(f"{key}="):
                            return part.split("=", 1)[1]
    except socket.timeout:
        print(f"Timed out waiting for {key} data (no active slice?)")
    except OSError as error:
        print(f"Error connecting to radio: {error}")

    return None


class MyDialog(tk.Frame):
    """A custom dialog class for interacting with FlexRadio settings."""
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
        """Create the dialog box widgets."""
    #---Get the Radio IP and callsign from radio functions
    
        self.radio_ip = FindIpAddress().radio_ip
        self.r_callsign = GetMyCallSign(self.radio_ip).r_callsign

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
        """Handle the selection and close the dialog."""
        # Save values directly to the class instance attributes
        self.radio_ip = self.entry1.get()
        self.r_callsign = self.entry2.get()  
        self.my_option = self.v.get()
        self.current_scale_value = self.vertical_scale.get()

        # FIX: Use quit() instead of destroy() so main() can read data before it's deleted
        self.master.quit()

class FindIpAddress:
    """Class to find the IP address of a FlexRadio on the local network."""

    def __init__(self):
        """Initialize the FindIpAddress class."""
        self.api_port = 4992
        self.radio_ip = self._discover_radio_ip()

    def _discover_radio_ip(self):
        """Listen briefly for a FlexRadio broadcast and return its IP address."""
        # Create a standard UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            # Bind to the standard FlexRadio discovery broadcast port.
            sock.bind(('', self.api_port))
            sock.settimeout(2.0)
            data, addr = sock.recvfrom(2048)
            return str(addr[0])

        except socket.timeout:
            return None
        finally:
            sock.close()

class GetMyCallSign:
    """Class to get the callsign from the FlexRadio."""

    def __init__(self, radio_ip=None, api_port=API_PORT):
        """Connect to the radio and store its callsign."""
        if radio_ip is None:
            radio = FindIpAddress()
            radio_ip = radio.radio_ip
            api_port = radio.api_port

        self.radio_ip = radio_ip
        self.api_port = api_port
        self.r_callsign = self._get_callsign()

    def _get_callsign(self):
        if self.radio_ip is None:
            return "No Radio"

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3.0)
                sock.connect((self.radio_ip, self.api_port))
                sock.sendall(b"C1|sub radio all\n")

                while True:
                    data = sock.recv(1024).decode("utf-8", errors="ignore")
                    if not data:
                        break

                    for line in data.splitlines():
                        for part in line.replace("|", " ").split():
                            if part.startswith("callsign="):
                                return part.split("=", 1)[1]

        except (socket.timeout, socket.error) as error:
            print(f"Network issue or timeout: {error}")
        except Exception as error:
            print(f"Error connecting to radio: {error}")

        return "No Radio"


class GetFlexFrequency:
    """Class to get the active slice's operating frequency from the FlexRadio."""

    def __init__(self, radio_ip=None, api_port=API_PORT):
        self.radio_ip = radio_ip or FindIpAddress().radio_ip
        self.api_port = api_port
        self.frequency = self.get_frequency()

    def get_frequency(self, timeout=5):
        """This function gets the active slice's operating frequency (in MHz) from the radio"""

        value = _get_slice_value(self.radio_ip, self.api_port, "RF_frequency", timeout)
        if value is None:
            return None

        try:
            return f"{float(value):.3f} MHz"
        except ValueError:
            return None


class GetFlexMode:
    """Class to get the active slice's operating mode from the FlexRadio."""

    def __init__(self, radio_ip=None, api_port=API_PORT):
        self.radio_ip = radio_ip or FindIpAddress().radio_ip
        self.api_port = api_port
        self.mode = self.get_mode()

    def get_mode(self, timeout=5):
        """Return the active slice's operating mode."""
        ip = self.radio_ip or RADIO_IP
        if not ip:
            print("No FlexRadio found on the network.")
            return None

        mode = None

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((ip, self.api_port))
                sock.sendall(b"C1|sub slice all\n")

                while True:
                    data = sock.recv(1024).decode("utf-8", errors="ignore")
                    if not data:
                        break

                    for line in data.splitlines():
                        if "slice" in line and "mode=" in line:
                            for part in line.replace("|", " ").split():
                                if part.startswith("mode="):
                                    mode = part.split("=", 1)[1]
                                    return mode

        except socket.timeout:
            print("Timed out waiting for mode data (no active slice?)")
        except OSError as error:
            print(f"Error connecting to radio: {error}")

        return mode


def get_my_location():
    """Return the current public-IP location as latitude and longitude."""
    result = geocoder.ip("me")
    if not result.ok or not result.latlng:
        raise RuntimeError("Unable to determine location from the public IP address.")
    return result.latlng

def main():
    root = tk.Tk()
    root.title("FLEX RADIO")
    root.geometry("300x200")
    root.resizable(False, False)
    root.columnconfigure(2, weight=1)
    
    app = MyDialog(master=root)

    # The script blocks here until the user clicks Apply (triggering master.quit())
    root.mainloop()

    RADIO_IP = FindIpAddress().radio_ip
   
    if not RADIO_IP:
        print("No FlexRadio found on the network.")
        return
    call_sign = GetMyCallSign(RADIO_IP).r_callsign
    if not call_sign:
        print("No callsign found.")
        return
    frequency = GetFlexFrequency(RADIO_IP).frequency
    
    my_option = app.my_option
    current_scale_value = app.current_scale_value
    
    print(f"Found RADIO_IP: {RADIO_IP}")
    print(f"Callsign: {call_sign}")
    print(f"Frequency: {frequency or 'Unavailable'}")
    print(f"my_option: {my_option}")
    print(f"current_scale_value: {current_scale_value}")
    my_mode = GetFlexMode(RADIO_IP).mode
    print(f"Mode: {my_mode or 'Unavailable'}")
    # Clean up the GUI after retrieving the data
    root.destroy()

if __name__ == "__main__":
    main()