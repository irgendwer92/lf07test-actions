"""
alarm clock based on ESP32, using internal RTC and external rotary encoder/switch
hardware implemented on base of ESP32-WROVER-KIT_V4.1 containing ILI9341 TFT display
using lv_micropython implementing LittlevGL GUI library for TFT display control

Author: sengp
Date: 2020-01-08

RTC date and time is initalized to CET/CEST using NTP/WLAN on power up if network connection exists
in case of RTC date and time is initalized CET/CEST time shift occcures automatically
if network connection exists RTC is adjusted periodically every 23h53'07" via NTP/WLAN
click and release switch to enable/set alarm-time
alarm is enabled for 60 seconds when time matches
RTC time can be set manually, press switch for > 5 seconds (RTC date will get lost)

"""


import lvgl as lv  # import LittlevGL
from ili9341 import ili9341  # import ILI9341 driver
from encoder import IncRotEc11
from machine import RTC
import utime
from machine import Pin
from rtc_ntp import setrtc_ntp
from rtc_ntp import setrtc
from machine import Timer
from machine import PWM
import time


# constants
# ili9341
MADCTL_MH = const(0x04)
MADCTL_ML = const(0x10)
MADCTL_MV = const(0x20)
MADCTL_MX = const(0x40)
MADCTL_MY = const(0x80)
PORTRAIT = MADCTL_MX
LANDSCAPE = MADCTL_MV
PERIOD_DSP = 300  # display update period in ms
PERIOD_BEEP = 500
BEEP_FREQ1 = 1175
BEEP_FREQ2 = 783
# rotary encoder/switch
PINA = 12
PINB = 13
PINSWITCH = 14
MAXPOS = (24*60)-1
INITPOS = 6*60
PERIOD_SWITCH = 70  # switch sample period in ms
# other
PERIOD_NTP = 85987000  # NTP fetch period 23h53'07" in ms
# TEXT = "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "        ", "Alarm"
TEXT = "Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So.", "        ", "Alarm"


def readrtc_cet_cest():
    """
    return RTC tupel
    if year and date valid accomplish automatic CET/CEST shift

    RetVal
        RTC tupel --> 0 year, 1 month, 2 dayofmonth, 3 dayofweek (0..6, mon=0), 4 hour, 5 minute, 6 second, 7 subsecond
        if ClockStatus == 0 (see down) year, month, dayofmonth and dayofweek not valid

    Globals
        ClockStatus
            0 --> could not set RTC using NTP and WLAN (RTC date not valid / unknown)
            1 --> RTC set to CET
            2 --> RTC set to CEST
        readrtc_cet_LastYear
            last "year" value read from RTC
        startCEST
            current CEST tupel
        startCET
            current CET tupel
    """
    #  globals needed cause variables must be static
    global ClockStatus
    global readrtc_cet_LastYear
    global startCEST
    global startCET
    
    Tnow = RTC().datetime()  # get RTC, tupel --> 0 year, 1 month, 2 dayofmonth, 3 dayofweek (0..6, mon=0), 4 hour, 5 minute, 6 second, 7 subsecond
    Tt = Tnow[0:3] + Tnow[4:7]  # Tnow, tupel --> 0 year, 1 month, 2 dayofmonth, 3 hour, 5 minute, 6 second
    year = Tt[0]
    if year != readrtc_cet_LastYear:  # calculate on program-start or start of year only
        startCEST = year, 3, (31-(int(5*year/4+4)) % 7), 1, 0, 0  # time when switching to Central European Summer Time (CEST), last sunday of march at 1:00 (UTC)
        startCET = year, 10, (31-(int(5*year/4+1)) % 7), 1, 0, 0  # time when switching to Central European Time (CET), last sunday of october at 1:00 (UTC)
        readrtc_cet_LastYear = year
    if Tt == startCEST and ClockStatus == 1:
        Tcet = Tnow[0], Tnow[1], Tnow[2], 0, Tnow[4] + 1, Tnow[5], Tnow[6], 0  # compose CEST RTC tupel, do not define dayofweek (will be calculated by RTC internally), do not define subsecond
        ClockStatus = 2  # CEST now
        RTC().datetime(Tcet)  # set RTC, tupel --> 0 year, 1 month, 2 dayofmonth, 3 dayofweek (0..6, mon=0), 4 hour, 5 minute, 6 second, 7 subsecond
        return RTC().datetime()
    if Tt == startCET and ClockStatus == 2:
        Tcet = Tnow[0], Tnow[1], Tnow[2], 0, Tnow[4] - 1, Tnow[5], Tnow[6], 0  # compose CET RTC tupel, do not define dayofweek (will be calculated by RTC internally), do not define subsecond
        ClockStatus = 1  # CET now
        RTC().datetime(Tcet)  # set RTC, tupel --> 0 year, 1 month, 2 dayofmonth, 3 dayofweek (0..6, mon=0), 4 hour, 5 minute, 6 second, 7 subsecond
        return RTC().datetime()
    return Tnow


def header(tx, active):
    if active:
#        tft.rect(0, 60, 320, miny, tft.RED, tft.RED)
#        tft.text(tft.CENTER, 63, tx, tft.YELLOW, transparent=True)
        label4.set_text(tx)
    else:
#        tft.rect(0, 60, 320, miny, tft.BLACK, tft.BLACK)
        label4.set_text("")


def update_alarm(tx, active):
    txt = TEXT[active+7]
    label3.set_text(txt)
    if not active:
        tx = ""
    label1.set_text(tx)


def update_date(tx):
    if ClockStatus:
        header(tx, 1)
    else:
        header(tx, 0)
    

def update_time(tx):
    label2.set_text(tx)
    
   


# Init TFT-display on ESP-WROVER-KIT V4.1 and LittlevGl
lv.init()
disp = ili9341(miso=25, mosi=23, clk=19, cs=22, dc=21, rst=18, power=-1, backlight=-1, rot=LANDSCAPE, width=320, height=240, hybrid=True)
# parameter "hybrid" is set to True to speed up frame processing for about 15ms.
# parameter "backlight" is disabled. Could be set to 5, but there should be a PWM signal generated at pin 5 of ili9341 to enable setting of brightness.
# meaning of parameter "power" is not clear, so it is disabled too.

# Create styles based on style_plain
mystyle1 = lv.style_t(lv.style_plain)
mystyle1.text.font = lv.font_seg7_70
mystyle1.body.main_color = lv.color_hex(0x000000) # background top color (main), 0xRRGGBB
mystyle1.body.grad_color = lv.color_hex(0x000000) # background bottom color (gradient), 0xRRGGBB
mystyle1.text.color = lv.color_hex(0xffffff) # alarm, time text-colour, 0xRRGGBB

mystyle2 = lv.style_t(mystyle1)
mystyle2.text.font = lv.font_seg7_140
mystyle2.text.color = lv.color_hex(0x00ff00) # time, text-colour, 0xRRGGBB

mystyle3 = lv.style_t(mystyle1)
mystyle3.text.font = lv.font_roboto_28
mystyle3.text.color = lv.color_hex(0xffffff) # alarm, indicator text-colour, 0xRRGGBB

mystyle4 = lv.style_t(mystyle3)
mystyle4.text.color = lv.color_hex(0x009aff) # date, text-colour, 0xRRGGBB


# Create screen and labels
scr = lv.obj()
scr.set_style(mystyle1)
label1 = lv.label(scr)
label2 = lv.label(scr)
label3 = lv.label(scr)
label4 = lv.label(scr)
lv.label.set_style(label2, 0, mystyle2)
lv.label.set_style(label3, 0, mystyle3)
lv.label.set_style(label4, 0, mystyle4)
label3.set_pos(60,0)  # alarm indicator
label1.set_pos(155,0)  # alarm time
label4.set_pos(70,70)  # date
label2.set_pos(10,110)  # time


# Create PWM for tone
pwmfreq = BEEP_FREQ1
pwmenable = 0



# LED's on E32-WROVER-KIT_V4.1 off
io0 = Pin(0, Pin.OUT, value=1)# DEBUG_ONLY create object, test output, GPIO0
io2 = Pin(2, Pin.OUT, value=0)# DEBUG_ONLY create object, test output, GPIO2
io4 = Pin(4, Pin.OUT, value=0)# DEBUG_ONLY create object, test output, GPIO4

# TFT backlight
pwm5 = PWM(Pin(5))  # create PWM object from a pin
pwm5.freq(200)  # set frequency

io26 = Pin(26, Pin.OUT, value=0)# DEBUG_ONLY create object, test output, GPIO26
io26Val = 0# DEBUG_ONLY
AlarmEnable = 0
readrtc_cet_LastYear = 0
ClockStatus = setrtc_ntp()  # set RTC to CET/CEST using NTP and WLAN
encoder = IncRotEc11(PINA, PINB, PINSWITCH, MAXPOS, INITPOS)  # create new instance of class "IncRotEc11"
EncoderPosLast = MAXPOS
TimeLastSwitch = utime.ticks_ms()
TimeLastNTP = TimeLastSwitch
TimeLastDispUpdate = TimeLastSwitch
TimeLastBeep = TimeLastSwitch
TimeLastBacklight = TimeLastSwitch
duty = 0
SwitchValueLast = 1
SwitchValue = SwitchValueLast
SwitchCount = 0
SwitchPressed = 0
AlarmState = 0
MinuteLast = 0
SecondLast = 0
DisplayUpdate = 0

print("\r\nPlease turn or push attached incremental rotary encoder!")
while True:
    TimeNow = utime.ticks_ms()
    if utime.ticks_diff(TimeNow, TimeLastNTP) > PERIOD_NTP:  # periodical RTC adjustment using NTP and WLAN
        TimeLastNTP = TimeNow
        ClockStatus = setrtc_ntp()  # set RTC to CET/CEST using NTP and WLAN
    if utime.ticks_diff(TimeNow, TimeLastDispUpdate) > PERIOD_DSP:  # periodical display update
        TimeLastDispUpdate = TimeNow
        DisplayUpdate = 1
        
    if utime.ticks_diff(TimeNow, TimeLastBacklight) > 3000:  # periodical display dim
        TimeLastBacklight = TimeNow
        pwm5.duty(duty)  # set TFT-backligh duty-cyle, 0 == max. brightness, 1000 == min. brightness (@f==200Hz), behaviour inverted on ESP32-WROVER-KIT_V4.1
        duty += 100
        if duty > 1000:
            duty = 0

    if utime.ticks_diff(TimeNow, TimeLastSwitch) > PERIOD_SWITCH:  # periodical scan of switch
        TimeLastSwitch = TimeNow
        SwitchValue = encoder.switch.value()
        if SwitchValue == 1 and SwitchValueLast == 0 and SwitchCount < 15:
            AlarmEnable = not AlarmEnable  # click detected
            DisplayUpdate = 1
            if SwitchPressed:
                ClockStatus = setrtc(encoder.position)  # state: SETTIME, set RTC to encoder position
                encoder.__init__(PINA, PINB, PINSWITCH, MAXPOS, INITPOS)  # set encoder to init-position
                SwitchPressed = 0  # not pressed
                AlarmEnable = 0
        if SwitchValue == 0:
            SwitchCount += 1
            if SwitchCount > 72:
                SwitchPressed = 1  # pressed for > 5s detected --> set time manually
                encoder.reset()
        else:
            SwitchCount = 0
        SwitchValueLast = SwitchValue
    Tm = readrtc_cet_cest()  # read RTC and return RTC tupel  
    encoder.update()  # read encoder, must be called in main loop or via timer interrupt
    #if (encoder.position != EncoderPosLast) or (MinuteLast != Tm[5]) or DisplayUpdate:
    if (MinuteLast != Tm[5]) or DisplayUpdate:        
    #if SecondLast != Tm[6] or (MinuteLast != Tm[5]) or DisplayUpdate:        
        DisplayUpdate = 0
        if SwitchPressed:
            # set time manually
            str_t = ("{:2d}:{:02d}".format(int(encoder.position / 60), encoder.position % 60))
            update_time(str_t)          
        elif AlarmEnable == 0:
            # alarm not active
            update_alarm(0, 0)
            str_t = ("{:3s} {:02d}.{:02d}.{:04d}".format(TEXT[Tm[3]], Tm[2], Tm[1], Tm[0]))
            update_date(str_t)
            str_t = ("{:2d}:{:02d}".format(Tm[4], Tm[5]))
            update_time(str_t)                
        else:
            # alarm active
            str_t = ("{:2d}:{:02d}".format(int(encoder.position / 60), encoder.position % 60))
            update_alarm(str_t, 1)
            str_t = ("{:3s} {:02d}.{:02d}.{:04d}".format(TEXT[Tm[3]], Tm[2], Tm[1], Tm[0]))
            update_date(str_t)
            str_t = ("{:2d}:{:02d}".format(Tm[4], Tm[5]))
            update_time(str_t)
        if (encoder.position == EncoderPosLast):
            lv.scr_load(scr)        
    EncoderPosLast = encoder.position
    MinuteLast = Tm[5]
    SecondLast = Tm[6]
    if ((Tm[4] * 60 + Tm[5]) - encoder.position == 0) and (AlarmEnable != 0):  # check if alarm active
        AlarmState = 1
        mystyle3.text.color = lv.color_hex(0xff0000) # alarm, indicator, text-colour, 0xRRGGBB
        if pwmenable == 0:
            pwm15 = PWM(Pin(15))  # create PWM object from a pin
            pwm15.duty(500)  # set current duty cycle to 50,0%
            pwmenable = 1
        if utime.ticks_diff(TimeNow, TimeLastBeep) > PERIOD_BEEP:  # periodical Beep
            TimeLastBeep = TimeNow
            if pwmfreq == BEEP_FREQ1:
                pwmfreq = BEEP_FREQ2
            else:
                pwmfreq = BEEP_FREQ1
            io0.value(1) # disable beeb amplifier    
            pwm15.freq(pwmfreq)  # set frequency
            io0.value(0) # enable beep amplifier
    else:
        AlarmState = 0
        if pwmenable == 1:
            io0.value(1) # disable beeb amplifier
            pwm15.deinit()  # turn off PWM on the pin
            pwmenable = 0
            pwmfreq = BEEP_FREQ1
            mystyle3.text.color = lv.color_hex(0xffffff) # alarm, indicator, text-colour, 0xRRGGBB
    io26Val = not io26Val  # toggle test output to enable measuring length of program cycle
    io26.value(io26Val)
