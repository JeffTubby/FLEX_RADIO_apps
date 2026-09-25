# This module contains functions to get data from the FLEX radio using its IP and TCP/IP API port.

import socket
import geocoder
# FlexRadio IP and TCP/IP API port
RADIO_IP = "192.168.1.132"  # Replace with your radio's IP address
API_PORT = 4992            # Default TCP Command API port

def find_flex_radio_ip(RADIO_IP=None):
    """This function listens for FlexRadio broadcast packets on the network and returns the IP address of the first discovered FlexRadio."""
    
    # Bind to the UDP port that FlexRadios broadcast discovery packets to
    UDP_IP = "0.0.0.0"
    UDP_PORT = 4992

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))

    print("Listening for FlexRadio broadcast... (Make sure your radio is turned on)")

    try:
        while True:
            data, addr = sock.recvfrom(1024) # Buffer size
            # The data contains the radio's status string.
            # Convert to string and print the radio's IP & data
            msg = data.decode('utf-8', errors='ignore')
            
            if "FLEX" in msg or "Serial" in msg:
                #print(f"Found Radio IP: {addr[0]}")
                #print(f"Radio Info: {msg}")
                RADIO_IP = addr[0]
                print(f"Found FlexRadio IP Address: {RADIO_IP}")
                #print("You can now use this IP address in your application.")
               
                    
                # You can break here if you only need the first discovered radio
                break
                
    except KeyboardInterrupt:
        print("\nDiscovery stopped.")
    finally:
        sock.close()
    return RADIO_IP
if __name__ == "__main__":
    RADIO_IP = find_flex_radio_ip(RADIO_IP=None)
    print(RADIO_IP)

def get_flex_frequency(radio_ip=None, timeout=5):
    """This function gets the active slice's operating frequency (in MHz) from the radio"""

    ip = radio_ip or RADIO_IP
    frequency = None

    try:
        # Connect to the radio
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)  # avoid blocking forever if no slice is active
            s.connect((ip, API_PORT))

            # Subscribe to slice status updates, where frequency is reported
            s.sendall(b"C1|sub slice all\n")

            # Read radio responses in a loop looking for the frequency
            while True:
                data = s.recv(1024).decode('utf-8', errors='ignore')
                if not data:
                    break

                # Look for RF_frequency in the status stream
                for line in data.splitlines():
                    if "RF_frequency=" in line:
                        parts = line.split()
                        for part in parts:
                            if part.startswith("RF_frequency="):
                                frequency = float(part.split("=")[1])
                                return f"{frequency:.6f} MHz"

    except socket.timeout:
        print("Timed out waiting for frequency data (no active slice?)")
    except Exception as e:
        print(f"Error connecting to radio: {e}")

    return frequency

if __name__ == "__main__":
    frequency = get_flex_frequency()
    print(f"Discovered Frequency: {frequency}")

def get_flex_callsign(radio_ip=None, timeout=3.0):
    """Get the current FlexRadio callsign from the radio status stream."""
    ip = radio_ip or RADIO_IP
    callsign = None

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, API_PORT))
            s.sendall(b"C1|sub radio all\n")

            while True:
                data = s.recv(4096)
                if not data:
                    break

                for line in data.decode("utf-8", errors="ignore").splitlines():
                    if "callsign=" in line.lower():
                        for part in line.split():
                            if part.lower().startswith("callsign="):
                                callsign = part.split("=", 1)[1].strip().strip("\r\n\0")
                                return callsign

    except (socket.timeout, socket.error) as e:
        print(f"Timed out waiting for callsign data: {e}")
    except Exception as e:
        print(f"Error connecting to radio: {e}")

    return callsign or "No Radio"


if __name__ == "__main__":
    callsign = get_flex_callsign()
    print(f"Discovered Callsign: {callsign}")

def get_flex_mode(radio_ip=None, timeout=5):
    """This function gets the active slice's mode (e.g. USB, FM, CW) from the radio"""

    ip = radio_ip or RADIO_IP
    mode = None

    try:
        # Connect to the radio
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)  # avoid blocking forever if no slice is active
            s.connect((ip, API_PORT))

            # Subscribe to slice status updates, where mode is reported
            s.sendall(b"C1|sub slice all\n")

            # Read radio responses in a loop looking for the mode
            while True:
                data = s.recv(1024).decode('utf-8', errors='ignore')
                if not data:
                    break

                # Look for mode= in the status stream
                for line in data.splitlines():
                    if "slice" in line and "mode=" in line:
                        parts = line.split()
                        for part in parts:
                            if part.startswith("mode="):
                                mode = part.split("=")[1]
                                return mode

    except socket.timeout:
        print("Timed out waiting for mode data (no active slice?)")
    except Exception as e:
        print(f"Error connecting to radio: {e}")

    return mode

if __name__ == "__main__":
    mode = get_flex_mode()
    print(f"Discovered Mode: {mode}")

def get_my_location(): # gml: Get the current location based on IP address
    # Use the geocoder library to get the location based on the current IP address
    # Get the location object based on the current IP address
    # Get the latitude and longitude from the location object

    g = geocoder.ip('me')

    MY_LATITUDE = g.latlng[0]
    MY_LONGITUDE = g.latlng[1]
    return MY_LATITUDE, MY_LONGITUDE


def get_my_altitude():
    import geocoder
    import requests
    location = geocoder.ip('me')
    if not location.latlng:
        raise RuntimeError('Could not determine your location from your IP address')

    latitude, longitude = location.latlng
    elevation_response = requests.get(
        'https://api.open-meteo.com/v1/forecast',
        params={'latitude': latitude, 'longitude': longitude},
        timeout=10,
    )
    elevation_response.raise_for_status()
    elevation = elevation_response.json()['elevation']
    ALTITUDE = elevation
    return { 'elevation': ALTITUDE }

