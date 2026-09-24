#!/usr/bin/env python3
"""
WSJT-X to Flex Radio Spots Bridge
Version: 1.3  (2026-03-11 – duplicate check ignores frequency)
  - Time-based deduplication: refresh active stations every SPOT_LIFETIME seconds
  - Duplicate check now only on callsign (ignores frequency)
  - Red (#FF0000) for spots calling YOU → "CALLING YOU:"
  - Green (#00FF00) for CQ POTA spots
"""

import socket
import struct
import time
import binascii
import re
import tkinter as tk
import FLEX_RADIO_functions_classes
from FLEX_RADIO_functions_classes import find_flex_radio_ip as ffri
from FLEX_RADIO_functions_classes import MyDialog

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────
FLEX_IP     = None

FLEX_PORT   = 4992
MCAST_GRP   = '224.0.0.1'
MCAST_PORT  = 2237

MIN_SNR     = -35
COMMENT_TS  = True

# Interactive
MY_CALLSIGN      = None
FILTER_MODE      = None
SPOT_LIFETIME    = 120     # seconds — user chosen, also duplicate/refresh window

# ────────────────────────────────────────────────
# GLOBALS / STATE
# ────────────────────────────────────────────────
dial_freq       = 0
current_mode    = 'FT8'
sent_spots      = {}       # key: callsign → last_sent_time (float) — freq ignored
cmd_seq         = 0
flex_socket     = None

# ────────────────────────────────────────────────
# QString parser (schema 2)
# ────────────────────────────────────────────────
def parse_qstring(data, offset, buf_len):
    if offset + 4 > buf_len:
        return "[short]", offset
    length = struct.unpack_from('>I', data, offset)[0]
    offset += 4
    if length == 0xFFFFFFFF:
        return '', offset
    if offset + length > buf_len:
        return f"[trunc len={length}]", buf_len
    str_bytes = data[offset:offset + length]
    offset += length
    try:
        return str_bytes.decode('utf-8').rstrip('\x00'), offset
    except UnicodeDecodeError:
        return f"[bad utf8 len={length}]", offset

# ────────────────────────────────────────────────
# Persistent Flex connection
# ────────────────────────────────────────────────
def get_flex_socket():
    global flex_socket, cmd_seq
    if flex_socket is not None:
        try:
            flex_socket.send(b'')
            return flex_socket
        except:
            flex_socket.close()
            flex_socket = None

    print(f"Connecting to Flex {FLEX_IP}:{FLEX_PORT} ...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((FLEX_IP, FLEX_PORT))
        welcome = s.recv(1024).decode('ascii', 'ignore').strip()
        print(f"  Connected: {welcome}")

        cmd_seq = 0
        bind_cmd = f'C{cmd_seq}|client program "WSJTX-Spotter"\n'
        s.sendall(bind_cmd.encode())
        s.recv(1024)
        flex_socket = s
        return s
    except Exception as e:
        print(f"  Connection failed: {e}")
        return None

# ────────────────────────────────────────────────
# Send spot (time-based dedup on callsign only)
# ────────────────────────────────────────────────
def send_flex_spot(callsign, freq_mhz, mode, comment, color=None):
    global cmd_seq
    now = time.time()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # Dedup key is just the callsign (frequency ignored)
    key = callsign.upper()  # case-insensitive

    # Time-based check
    if key in sent_spots:
        last_sent = sent_spots[key]
        if now - last_sent < SPOT_LIFETIME:
            print(f"{timestamp} → Duplicate: {callsign} @ {freq_mhz:.6f} (skipped - timer active)")
            return

    s = get_flex_socket()
    if s is None:
        return

    try:
        cmd_seq += 1
        cmd_parts = [
            f'C{cmd_seq}|spot add',
            f'rx_freq={freq_mhz:.6f}',
            f'callsign={callsign}',
            f'mode={mode}',
            f'source=WSJTX',
            f'comment={comment}',
            f'lifetime_seconds={SPOT_LIFETIME}'
        ]
        if color:
            cmd_parts.append(f'color={color}')

        spot_cmd = ' '.join(cmd_parts) + '\n'

        s.sendall(spot_cmd.encode())
        resp = s.recv(4096).decode('ascii', 'ignore').strip()

        if 'R' in resp and '|0|' in resp:
            col_str = f" ({color})" if color else ""
            label = "CALLING YOU" if color == '#FF0000' else "Accepted"
            print(f"{timestamp} → {label}: {callsign} @ {freq_mhz:.6f}{col_str}")
            sent_spots[key] = now
        elif 'R' in resp:
            sent_spots[key] = now

    except Exception as e:
        print(f"{timestamp} Send failed: {e}")
        global flex_socket
        if flex_socket:
            flex_socket.close()
            flex_socket = None

# ────────────────────────────────────────────────
# Parse WSJT-X message
# ────────────────────────────────────────────────
def parse_wsjtx_message(data):
    global dial_freq, current_mode
    buf_len = len(data)
    if buf_len < 20:
        return None

    offset = 0
    magic = struct.unpack_from('>I', data, offset)[0]; offset += 4
    if magic != 0xADBCCBDA:
        return None

    schema = struct.unpack_from('>I', data, offset)[0]; offset += 4
    msg_type = struct.unpack_from('>I', data, offset)[0]; offset += 4

    id_str, offset = parse_qstring(data, offset, buf_len)

    if msg_type == 1:  # Status
        dial_raw = struct.unpack_from('>Q', data, offset)[0]; offset += 8
        mode_str, offset = parse_qstring(data, offset, buf_len)
        dial_freq = dial_raw
        if mode_str and mode_str != '~':
            current_mode = mode_str.upper().strip()
        return {'type': 'status'}

    elif msg_type == 2:  # Decode
        is_new   = struct.unpack_from('>?', data, offset)[0]; offset += 1
        time_ms  = struct.unpack_from('>I',  data, offset)[0]; offset += 4
        snr      = struct.unpack_from('>i',  data, offset)[0]; offset += 4
        dt       = struct.unpack_from('>d',  data, offset)[0]; offset += 8
        df       = struct.unpack_from('>I',  data, offset)[0]; offset += 4

        mode_str, offset = parse_qstring(data, offset, buf_len)
        message,  offset = parse_qstring(data, offset, buf_len)

        mode_to_use = mode_str.upper().strip() if mode_str and mode_str != '~' else current_mode

        parts = re.split(r'\s+', message.strip())
        callsign = None
        modifier_list = ['POTA', 'SOTA', 'DX', 'NA']

        if len(parts) >= 3:
            if parts[0].upper() == 'CQ':
                if len(parts) >= 4 and parts[1].upper() in modifier_list:
                    callsign = parts[2]
                else:
                    callsign = parts[1]
            else:
                callsign = parts[1] if re.match(r'^[A-Z0-9/]{3,15}$', parts[1]) else None
        if not callsign and len(parts) >= 1:
            callsign = parts[0] if re.match(r'^[A-Z0-9/]{3,15}$', parts[0]) else None

        freq_mhz = (dial_freq + df) / 1e6 if dial_freq > 0 else 0.0

        # Priority 1: Calling YOU → force red, bypass filter
        is_calling_me = False
        if MY_CALLSIGN:
            my_upper = MY_CALLSIGN.upper()
            if len(parts) >= 2 and my_upper == parts[1].upper():
                is_calling_me = True
            elif my_upper in [p.upper() for p in parts]:
                is_calling_me = True

        if is_calling_me:
            ts = time.strftime('%H:%M') if COMMENT_TS else ''
            comment = f"{message} SNR {snr:+d} {ts}".strip()
            return {
                'type': 'decode',
                'callsign': callsign,
                'freq': freq_mhz,
                'mode': mode_to_use,
                'comment': comment,
                'color': '#FF0000'
            }

        # Normal path
        if snr < MIN_SNR:
            return None

        msg_upper = message.upper()
        if FILTER_MODE == 'cq' and not msg_upper.startswith('CQ '):
            return None
        elif FILTER_MODE == 'pota' and 'CQ POTA' not in msg_upper:
            return None

        if callsign and len(callsign) >= 4 and 1 < freq_mhz < 1000:
            ts = time.strftime('%H:%M') if COMMENT_TS else ''
            comment = f"{message} SNR {snr:+d} {ts}".strip()

            color = '#00FF00' if 'CQ POTA' in msg_upper else None

            return {
                'type': 'decode',
                'callsign': callsign,
                'freq': freq_mhz,
                'mode': mode_to_use,
                'comment': comment,
                'color': color
            }

    return None

# ────────────────────────────────────────────────
# Interactive prompts at startup
# ────────────────────────────────────────────────
root = tk.Tk()
root.title("FLEX RADIO")
root.geometry("300x200")
root.resizable(False, False)
root.columnconfigure(2, weight=1)

app = MyDialog(master=root)

# The script blocks here until the user clicks Apply (triggering master.quit())
root.mainloop()

# Read the values from the app instance safely while it still exists in memory.
# The dialog is the single source of truth because it may contain a manual edit.
fetched_radio_ip = app.radio_ip
fetch_r_callsign = app.r_callsign
my_option = app.my_option
current_scale_value = app.current_scale_value

# Clean up and completely close the underlying window system now
root.destroy()

# Get data from the dialog box.
FLEX_IP = fetched_radio_ip
MY_CALLSIGN = fetch_r_callsign
FILTER_MODE = {1: 'cq', 2: 'pota', 3: None}.get(my_option)
SPOT_LIFETIME = current_scale_value
# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────
if __name__ == "__main__":
    
    
    print(f"\nListening on {MCAST_GRP}:{MCAST_PORT}  →  Flex {FLEX_IP}:{FLEX_PORT}")
    print(f"  My call: {MY_CALLSIGN} (red if called)")
    print(f"  Filter: {FILTER_MODE}")
    print(f"  Lifetime / refresh window: {SPOT_LIFETIME} seconds")
    print(f"  CQ POTA spots: green\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MCAST_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    while True:
        try:
            data, addr = sock.recvfrom(1500)
            parsed = parse_wsjtx_message(data)
            if parsed and parsed['type'] == 'decode':
                send_flex_spot(
                    parsed['callsign'],
                    parsed['freq'],
                    parsed['mode'],
                    parsed['comment'],
                    color=parsed.get('color')
                )

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

    if flex_socket:
        flex_socket.close()
