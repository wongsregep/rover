import pyb
from pyb import Pin, Timer, UART

# setup standby PIN PA1 
MOTOR_EN = Pin('PA1', Pin.OUT, Pin.PULL_DOWN)
MOTOR_EN.off()

# setup output PIN
pb12 = Pin('PB12', Pin.OUT, Pin.PULL_DOWN)
pb13 = Pin('PB13', Pin.OUT, Pin.PULL_DOWN)

pb14 = Pin('PB14', Pin.OUT, Pin.PULL_DOWN)
pb15 = Pin('PB15', Pin.OUT, Pin.PULL_DOWN)

pb3 = Pin('PB3', Pin.OUT, Pin.PULL_DOWN)
pb4 = Pin('PB4', Pin.OUT, Pin.PULL_DOWN)

pb5 = Pin('PB5', Pin.OUT, Pin.PULL_DOWN)
pb6 = Pin('PB6', Pin.OUT, Pin.PULL_DOWN)

# setup UART2
uart2 = UART(2, 115200)


# setup speed PIN PA0 (motor speed)
pa0 = Pin('PA0', Pin.PULL_NONE)
TIM5 = Timer(5, freq=10000)
SPEED = TIM5.channel(1, Timer.PWM, pin=pa0)
SPEED_VAL = 50
SPEED.pulse_width_percent(SPEED_VAL)

# setup cam angle PIN PB9 (motor speed)
pb9 = Pin('PB9', Pin.PULL_NONE)
TIM4 = Timer(4, freq=50)
CAMTILT = TIM4.channel(4, Timer.PWM, pin=pb9)
CAM_ANGLE = 7.5
CAMTILT.pulse_width_percent(CAM_ANGLE)

# control wheel function
def ControlWheel(wheel, direction=0):
    '''
    wheel:
    0: rear-right
    1: front-right
    2: front-left
    3: rear-left
    
    direction:
    0: stop
    1: fwd
    2: rvs
    '''
    if wheel == 0:
        if direction == 0:
            pb14.off()
            pb15.off()
        elif direction == 1:
            pb14.on()
            pb15.off()
        elif direction == 2:
            pb14.off()
            pb15.on()
    elif wheel == 1:
        if direction == 0:
            pb5.off()
            pb6.off()
        elif direction == 1:
            pb5.on()
            pb6.off()
        elif direction == 2:
            pb5.off()
            pb6.on()
    elif wheel == 2:
        if direction == 0:
            pb3.off()
            pb4.off()
        elif direction == 1:
            pb3.off()
            pb4.on()
        elif direction == 2:
            pb3.on()
            pb4.off()
    elif wheel == 3:
        if direction == 0:
            pb12.off()
            pb13.off()
        elif direction == 1:
            pb12.off()
            pb13.on()
        elif direction == 2:
            pb12.on()
            pb13.off()

# control movement function
def Move(move=0):

    global CAM_ANGLE
    global SPEED_VAL
    
    '''
         movement:
         0:  stop
         1:  fwd
         2:  rvs
         3:  right
         4:  left
         5:  fwd-right
         6:  fwd-left
         7:  rvs-right
         8:  rvs-left
         9:  right-uturn
         10: left-uturn
     11: cam_up
     12: cam_down
     13: speed_up
     14: speed_down
    '''
    if move == 1:
        ControlWheel(0, 1) #rear-right-fwd
        ControlWheel(1, 1) #front-right-fwd
        ControlWheel(2, 1) #front-left-fwd
        ControlWheel(3, 1) #rear-left-fwd
    elif move == 2:
        ControlWheel(0, 2) #rear-right-rvs
        ControlWheel(1, 2) #front-right-rvs
        ControlWheel(2, 2) #front-left-rvs
        ControlWheel(3, 2) #rear-left-rvs
    elif move == 3:
        ControlWheel(0, 1) #rear-right-fwd
        ControlWheel(1, 2) #front-right-rvs
        ControlWheel(2, 1) #front-left-fwd
        ControlWheel(3, 2) #rear-left-rvs  
    elif move == 4:
        ControlWheel(0, 2) #rear-right-rvs
        ControlWheel(1, 1) #front-right-fwd
        ControlWheel(2, 2) #front-left-rvs
        ControlWheel(3, 1) #rear-left-fwd
    elif move == 5:
        ControlWheel(0, 1) #rear-right-fwd
        ControlWheel(1, 0) #front-right-stop
        ControlWheel(2, 1) #front-left-fwd
        ControlWheel(3, 0) #rear-left-stop
    elif move == 6:
        ControlWheel(0, 0) #rear-right-stop
        ControlWheel(1, 1) #front-right-fwd
        ControlWheel(2, 0) #front-left-stop
        ControlWheel(3, 1) #rear-left-fwd
    elif move == 7:
        ControlWheel(0, 0) #rear-right-stop
        ControlWheel(1, 2) #front-right-rvs
        ControlWheel(2, 0) #front-left-stop
        ControlWheel(3, 2) #rear-left-rvs
    elif move == 8:
        ControlWheel(0, 2) #rear-right-rvs
        ControlWheel(1, 0) #front-right-stop
        ControlWheel(2, 2) #front-left-rvs
        ControlWheel(3, 0) #rear-left-stop
    elif move == 9:
        ControlWheel(0, 2) #rear-right-rvs
        ControlWheel(1, 2) #front-right-rvs
        ControlWheel(2, 1) #front-left-fwd
        ControlWheel(3, 1) #rear-left-fwd
    elif move == 10:
        ControlWheel(0, 1) #rear-right-fwd
        ControlWheel(1, 1) #front-right-fwd
        ControlWheel(2, 2) #front-left-rvs
        ControlWheel(3, 2) #rear-left-rvs            
    else:
        ControlWheel(0, 0) #rear-right-stop
        ControlWheel(1, 0) #front-right-stop
        ControlWheel(2, 0) #front-left-stop
        ControlWheel(3, 0) #rear-left-stop

def read_cmd():
    while True:
        str_in = uart2.read()
        if str_in is not None:
            if str_in.startswith(b'CMD_'):
                str_in_val = str_in.split(b'_')
                cmd = str_in_val[1]
                try:
                    val = int(str_in_val[2])
                except:
                    val =0

                # set the movement command                    
                #print(cmd+':'+val)
                if cmd==b'MOVE':
                    if val in range(0, 11):
                        #print(val)
                        Move(val)

                # set the cam command
                #print(cmd+':'+val)
                if cmd==b'CAM':
                    if val in range(-90, 91):
                        #print(val)
                        CamAngle = ((90+val)/360 * 10)+5
                        #print(CamAngle)
                        CAMTILT.pulse_width_percent(CamAngle)
                
                # set the speed command
                #print(cmd+':'+str(val))
                if cmd==b'SPEED':
                    if val in range(0, 101):
                        SPEED.pulse_width_percent(val)
                        
            else:
                # debug
                print(str_in)
                
        
if __name__ == "__main__":
    pyb.delay(1000)
    MOTOR_EN.on()
    read_cmd()

