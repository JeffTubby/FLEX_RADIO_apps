# Configuration for FLEX Radio Beacon
#lat=-35.135731
#lon=139.249263
import requests
import aprslib
from aprslib.packets.position import PositionReport
import time

import FLEX_RADIO_get_my_data_funcs
from FLEX_RADIO_get_my_data_funcs import get_flex_callsign as gcs
from FLEX_RADIO_get_my_data_funcs import get_flex_frequency as gff
from FLEX_RADIO_get_my_data_funcs import get_flex_mode as gfm
from FLEX_RADIO_get_my_data_funcs import get_my_location as gml
from FLEX_RADIO_get_my_data_funcs import get_my_altitude as gma


# Time interval for resending APRS packets in minutes
RESEND_TIME = 15

radio_callsign = gcs()


def refresh_radio_state():
	global radio_callsign
	raw_frequency = gff() or "0"
	try:
		radio_frequency = float(str(raw_frequency).split()[0])
	except (TypeError, ValueError):
		radio_frequency = 0.0
	formatted_frequency = f"{radio_frequency:.3f}"

	radio_mode = gfm() or "USB"
	if radio_mode == "DIGU":
		radio_mode = "FT8"

	radio_callsign = gcs()
	return formatted_frequency, radio_mode

# APRS Beacon Configuration must be updated with your own callsign, passcode, server, and location information
CALL = "VK5IU-8"
PASSCODE = 17888
SERVER = "aunz.aprs2.net"
PORT = 14580
ICON = "-w"
ALTITUDE = gma()['elevation']
LATITUDE = -35.135731
LONGITUDE = 139.249263
#LATITUDE = None #-35.135731
#LONGITUDE = None #139.249263
# This section allows for automatic location detection if LATITUDE and LONGITUDE are not predefined
	#LATITUDE = None #-35.135731 LONGITUDE = None #139.249263
if LATITUDE is None or LONGITUDE is None:
		LATITUDE, LONGITUDE = gml()
		print("Location obtained from IP: ", LATITUDE, LONGITUDE)
else:
		print("Using predefined location: ", LATITUDE, LONGITUDE)

RESEND_INTERVAL_SECONDS = RESEND_TIME * 60
POSITION_PACKET = PositionReport(
    {
        "from": CALL,
        "to": "APRS",
        "path": ["TCPIP*", "qAC", "T2TAS"],
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "altitude": ALTITUDE,
        "symbol": ICON,
        "comment": "Beacon",
    }
)


def build_status_packet():
	current_frequency, current_mode = refresh_radio_state()
	message = f"{radio_callsign},{current_frequency},{current_mode} on air"
	return f"{CALL}>APRS,TCPIP*,qAC,T2TAS:>{message}"


def validate_packet(packet):
	packet_text = str(packet)
	if ":" not in packet_text:
		raise ValueError(f"Packet missing APRS header/body separator: {packet_text!r}")
	if ">" not in packet_text.split(":", 1)[0]:
		raise ValueError(f"Packet missing sender/destination header: {packet_text!r}")
	return packet_text


def send_packets():
	status_packet = build_status_packet()
	packets_to_send = [POSITION_PACKET, status_packet]
	for packet in packets_to_send:
		try:
			packet_text = validate_packet(packet)
		except ValueError as exc:
			print(f"Invalid APRS packet: {exc}")
			return
		print(f"Prepared: {packet_text}")

	ais = aprslib.IS(CALL, passwd=str(PASSCODE), host=SERVER, port=PORT)
	try:
		ais.connect()
		for packet in packets_to_send:
			packet_text = validate_packet(packet)
			ais.sendall(packet_text)
			print(f"Sent: {packet_text}")
	finally:
		ais.close()


def main():
	try:
		while True:
			send_packets()
			print(f"Waiting {RESEND_TIME} minutes before resending.")
			time.sleep(RESEND_INTERVAL_SECONDS)
	except KeyboardInterrupt:
		print("Stopping APRS beacon.")


if __name__ == "__main__":
	main()