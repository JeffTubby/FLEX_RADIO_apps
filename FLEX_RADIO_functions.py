# This module contains functions to get data from the FLEX radio using its IP and TCP/IP API port.
# This module provides functions to discover a FlexRadio on the network and retrieve its frequency and callsign.
# This module requires the 'geocoder' library for network discovery.
# Finds mode
# Author: Jeff Tubbenhauer VK5IU
# Date: 05/09/2026

import socket
import time
import geocoder
import requests

from FLEX_RADIO_classes import (
    FindIpAddress,
    GetFlexFrequency,
    GetFlexMode,
    GetMyCallSign,
)



API_PORT = 4992  # Default API port for FlexRadio
RADIO_IP = None  # Will be set when discovering the radio on the network

def get_my_location(): # gml: Get the current location based on IP address
    location = geocoder.ip('me')
    if not location.ok or not location.latlng or len(location.latlng) != 2:
        raise RuntimeError('Could not determine your location from your IP address')

    latitude, longitude = location.latlng
    return latitude, longitude


def get_my_altitude():
    import requests
    location = geocoder.ip('me')
    if not location.ok or not location.latlng or len(location.latlng) != 2:
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

def main():
    radio_ip = FindIpAddress().radio_ip
    if not radio_ip:
        print("No FlexRadio found on the network.")
        return

    callsign = GetMyCallSign(radio_ip).r_callsign
    print(f"Discovered Callsign: {callsign}")

    mode = GetFlexMode(radio_ip).mode
    print(f"Discovered Mode: {mode}")

    latitude, longitude = get_my_location()
    print(f"Discovered Location: Latitude {latitude}, Longitude {longitude}")

    altitude = get_my_altitude()
    print(f"Discovered Altitude: {altitude['elevation']}")

    frequency = GetFlexFrequency(radio_ip).frequency
    print(f"Discovered Frequency: {frequency}")

if __name__ == "__main__":
    main()