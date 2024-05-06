"""
RTC and NTP/WLAN related routines

base content copied from MicroPython-1.11/ports/esp32/modules/ntptime.py
and
https://forum.micropython.org/viewtopic.php?t=4034

"""

HOST = "pool.ntp.org"  # host where to get UTC time from
# POSIX/EMBEDDED port have different time Epoch, to calculate difference start python3 on PC and enter: import datetime
# then enter: (datetime.date(2000, 1, 1) - datetime.date(1900, 1, 1)).days * 24*60*60
NTP_DELTA = 3155673600  # time Epoch difference of POSIX/EMBEDDED ports in seconds
CET_DELTA = 3600  # Central European Time (CET) is UTC+1:00, difference to UTC in seconds
CEST_DELTA = 7200  # Central European Summer Time (CEST) is UTC+2:00, difference to UTC in seconds


def connect_wlan(connect):
    """
    Parameter
        connect
            0 --> disconnect from WLAN
            1 --> connect to WLAN
    """
    import network
    import utime
    import wlan_secret

    RetVal = 0
    wlan = network.WLAN(network.STA_IF)  # create network interface
    if connect:
        if not wlan.isconnected():  # check if device is connected to an AP
            wlan.active(True)  # activate network interface
            wlan.connect(wlan_secret.SSID, wlan_secret.KEY)  # connect to an AP
            for i in range(1, 10):  # for 10 seconds try to establish connection
                if not wlan.isconnected():
                    utime.sleep(1)
                else:
                    RetVal = 1
                    break
        else:
            RetVal = 2
    if not RetVal:
        wlan.disconnect()  # disconnect from network
        wlan.active(False)  # deactivate network interface
    return RetVal


def time_ntp():
    """
    return seconds since the (embedded) Epoch (2000-01-01 00:00:00 UTC) obtained via NTP query
    requires active connection to network
    """
    import usocket
    import ustruct

    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1b
    addr = usocket.getaddrinfo(HOST, 123)[0][-1]
    s = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
    s.settimeout(1)
    s.sendto(NTP_QUERY, addr)
    msg = s.recv(48)
    s.close()
    val = ustruct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA  # seconds since the (embedded) Epoch (2000-01-01 00:00:00 UTC)


def setrtc_cet():
    """
    set RTC to CET/CEST
    currently no timezone support in MicroPython, CET/CEST calculated offset calculated
    requires active connection to network

    RetVal
        0 --> RTC set to CET
        1 --> RTC set to CEST
    """
    from machine import RTC
    import utime

    SummerTime = 0
    TimeNow = time_ntp()  # seconds since the (embedded) Epoch (2000-01-01 00:00:00 UTC)
    Tm = utime.localtime(TimeNow)  # UTC, tupel --> 0 year, 1 month, 2 dayofmonth, 3 hour, 4 minute, 5 second, 6 dayofweek (0..6, mon=0), 7 dayofyear
    year = Tm[0]  # get current year
    Pmarch = utime.mktime((year, 3, (31-(int(5*year/4+4)) % 7), 1, 0, 0, 0, 0, 0))  # time when switching to Central European Summer Time (CEST), last sunday of march at 1:00 (UTC)
    Poctob = utime.mktime((year, 10, (31-(int(5*year/4+1)) % 7), 1, 0, 0, 0, 0, 0))  # time when switching to Central European Time (CET), last sunday of october at 1:00 (UTC)
    if TimeNow < Pmarch:  # we are before last sunday of march
        TimeNow = TimeNow + CET_DELTA  # CET:  UTC+1:00
    elif TimeNow < Poctob:  # we are before last sunday of october
        TimeNow = TimeNow + CEST_DELTA  # CEST: UTC+2:00
        SummerTime = 1
    else:  # we are after last sunday of october
        TimeNow = TimeNow + CET_DELTA  # CET:  UTC+1:00
    Tm = utime.localtime(TimeNow)  # CET tupel --> 0 year, 1 month, 2 dayofmonth, 3 hour, 4 minute, 5 second, 6 dayofweek (0..6, mon=0), 7 dayofyear
    Tm = Tm[0:3] + (0,) + Tm[3:6] + (0,)  # tupel slicing, generate RTC format, do not define dayofweek (will be calculated by RTC internally), do not define subsecond
    RTC().datetime(Tm)  # set RTC, tupel --> 0 year, 1 month, 2 dayofmonth, 3 dayofweek (0..6, mon=0), 4 hour, 5 minute, 6 second, 7 subsecond
    return SummerTime


def setrtc_ntp():
    """
    1.) try to establish network connection via WLAN
    2.) if successful set RTC to CET/CEST using NTP and WLAN
    3.) if not successful keep old RTC content
    4.) deactivate network interface

    RetVal
        0 --> could not set RTC using NTP and WLAN (RTC time and date unknown)
        1 --> RTC set to CET
        2 --> RTC set to CEST
    """
    from machine import RTC
    import utime
    
    RTCset = 0
    if connect_wlan(1):
        RTCset = setrtc_cet()  # set RTC to UTC time achieved via WLAN
        RTCset += 1
        connect_wlan(0)
    return RTCset


def setrtc(position):
    """
    set RTC manually, time only (date not valid, set to 2000-01-01)

    RetVal
        0 --> RTC set manually (RTC date not valid)
    """
    from machine import RTC

    Tm = 2000, 1, 1, 0, int(position / 60), position % 60, 0, 0
    RTC().datetime(Tm)  # set RTC, tupel --> 0 year, 1 month, 2 dayofmonth, 3 dayofweek (0..6, mon=0), 4 hour, 5 minute, 6 second, 7 subsecond
    return 0
