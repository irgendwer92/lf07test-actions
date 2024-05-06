"""
code for handling encoders

"""

from machine import Pin
import utime

PERIOD_AQR = 70  # "fast gear" acquire period in ms
TRESH = 4  # "fast gear" speed treshhold
FASTINC = 60  # "fast gear" step-with


class IncRotEc11:  # create class "IncRotEc11"
    """
    class for handling incremental rotary encoders like e.g. ALPS EC11 series
    when turning slow position inc- decrements by 1
    when turning fast position inc- decrements by FASTINC

    __init__ arguments
        IncRotEc11(PinA, PinB, PinSwitch, MaxPos, InitPos)
            PinA
                pin number channelA
            PinB
                pin number channelA
            PinSwitch
                pin number switch
            MaxPos
                position maximum value
            InitPos
                position init value

    methods
        .update()
            must be called in main loop or via timer interrupt

    variables
        .position
            0 ... MaxPos
            init value = InitPos
        .switch.value()
            0 = pressed
            1 = not pressed
    """
  

    def __init__(self, PinA, PinB, PinSwitch, MaxPos, InitPos):  # method is automatically called when new instance of class is created
        self.MaxPos = MaxPos
        self.ChA = Pin(PinA, Pin.IN, Pin.PULL_UP)  # encoder channel A, PinA, enable internal pull-up resistor
        self.ChB = Pin(PinB, Pin.IN, Pin.PULL_UP)  # encoder channel A, PinB, enable internal pull-up resistor
        self.state = self.ChA.value() + (self.ChB.value() << 1)
        self.state_last = self.state
        self.switch = Pin(PinSwitch, Pin.IN, Pin.PULL_UP)  # encoder pushbutton, PinSwitch, enable internal pull-up resistor
        self.pos = (InitPos * 2) + 1
        self.position = InitPos
        self.position_lastsample = self.position
        self.time_lastsample = utime.ticks_ms()
        self.table = [[0, 1, -1, 0], [-1, 0, 0, 1], [1, 0, 0, -1], [0, -1, 1, 0]]  # incremental rotary encoder states
        self.io27Val = 0# DEBUG_ONLY
        self.io27 = Pin(27, Pin.OUT, value=0)# DEBUG_ONLY create object, test output, GPIO27

    def update(self):
        self.state = self.ChA.value() + (self.ChB.value() << 1)
        i = (self.table[self.state_last][self.state])
        self.state_last = self.state
        self.pos += i
        self.position = self.pos // 2  # filter out odd and unstable position values that may exist
        self.timenow = utime.ticks_ms()
        if utime.ticks_diff(self.timenow, self.time_lastsample) > PERIOD_AQR:  # fastgear?
            self.posdiff = self.position - self.position_lastsample
            if abs(self.posdiff) > TRESH:
                self.fastgear()
            self.position_lastsample = self.position
            self.time_lastsample = self.timenow
        if self.position > self.MaxPos:  # overflow?
            self.reset()
        elif self.position < 0:  # underflow?
            self.set()
        self.io27Val = not self.io27Val# DEBUG_ONLY toggle test output to enable measuring length of program cycle
        self.io27.value(self.io27Val)# DEBUG_ONLY


    def reset(self):
        self.pos = 0
        self.position = 0
        self.position_lastsample = self.position

    def set(self):
        self.pos = (self.MaxPos * 2) + 1
        self.position = self.MaxPos
        self.position_lastsample = self.position

    def fastgear(self):
        if self.posdiff > 0:
            self.position = self.position + FASTINC
        else:
            self.position = self.position - FASTINC
        self.pos = (self.position * 2) + 1
        self.position_lastsample = self.position
