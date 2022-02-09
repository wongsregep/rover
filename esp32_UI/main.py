import socket
import _thread
import ubinascii
import uhashlib
import ustruct as struct
import urandom as random
import camera

# Init Camera
camera.init(0, xclk_freq=camera.XCLK_20MHz, format=camera.JPEG)
camera.framesize(camera.FRAME_VGA)

#camera.speffect(camera.EFFECT_NONE)
#camera.whitebalance(camera.WB_NONE)
#camera.saturation(0)
camera.brightness(1)
#camera.contrast(0)
#camera.quality(10)

# Init Flash LED
flash_pin = Pin(4, Pin.OUT)
flash = Signal(flash_pin, invert=False)
flash.off()

# Init pin for movement
#dig0 = Pin(12, Pin.OUT)
#dig1 = Pin(13, Pin.OUT)
#dig2 = Pin(15, Pin.OUT)
#dig3 = Pin(14, Pin.OUT)

# Init PWM for servo
# lowest: 25
# highest: 119
#servo = PWM(Pin(12), freq=50, duty=72)


# define websocket listen port
webs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
webs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
webs_addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
webs.bind(webs_addr)
webs.listen(5)

CLIENTS = []

STREAM = True
CONN_EN = True
NCLIENT = 0



# define magic string websocket
MSTR = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

# define websocket constant
# =========================
# opcodes
OP_CONT = const(0x0)
OP_TEXT = const(0x1)
OP_BYTES = const(0x2)
OP_CLOSE = const(0x8)
OP_PING = const(0x9)
OP_PONG = const(0xa)


def parse_http_req(req):

    VALID = False
    METHOD = b''
    URL = b''
    HEADERS = b''
    DATA = b''
    PROTOCOL = ''

    Sec = req.split(b'\r\n\r\n')
    if len(Sec) > 1:
        HS = Sec[0].split(b'\r\n')
        if len(HS) > 1:
            HS1 = HS[0].split(b' ')
            if len(HS1) > 0:
                METHOD = HS1[0]
                URL = HS1[1]
                PROTOCOL = HS1[2]
            HEADERS=HS[1:]
            DATA = Sec[1]
            VALID = True
      
    return {'VALID': VALID, 'METHOD': METHOD, 'URL': URL, 'PROTOCOL': PROTOCOL, 'HEADERS': HEADERS, 'DATA': DATA}
    

def write_frame(clconn, CRAFT):
    # CRAFT struct:
    # CRAFT = {'FIN': FIN, 'OPCODE': OPCODE, 'MASKED': MASKED, 'DATA': DATA}
    
    # get data length
    data_len = len(CRAFT['DATA'])
    
    # Byte 1: FIN|1| RESV|1| RESV|1| RESV|1| OPCODE|4|
    if CRAFT['FIN']:
        byte1 = 0x80
        # 1000 0000
    else:
        byte1 = 0
        # 0000 0000
    
    byte1 |= CRAFT['OPCODE']
    
    # Byte 2: MASK|1| PAYLOADLEN|7|
    if CRAFT['MASKED']:
        byte2 = 0x80
    else:
        byte2 = 0
        
    # if data_len <= 0111 1110    
    if data_len < 126:
        # byte2 or data_len
        byte2 |= data_len
        try:
            clconn.write(struct.pack('!BB', byte1, byte2)) #big_endian u_char u_char
        except:
            print('socket write error')
            return
    
    # if data len < 16 bits ( 1 << 16) = 1111 1111 1111 1111 = 65536
    elif data_len < ( 1 << 16):
        # byte2 or 0111 1110
        byte2 |= 126
        try:
            clconn.write(struct.pack('!BBH', byte1, byte2, data_len)) #big_endian u_char u_char u_short
        except:
            print('socket write error')
            return        
    
    # if data len < 64 bits ( 1 << 64) = 18446744073709551616
    elif data_len < ( 1 << 64):
        # byte2 or 0111 1111
        byte2 |= 127
        try:
            # big_endian
            clconn.write(struct.pack('!BBH', byte1, byte2, data_len)) #big_endian u_char u_char u_long_long
        except:
            print('socket write error')
            return    
    
    else:
        print('date length value error')
        return
    
    # if server don't mask!
    if CRAFT['MASKED']:
        # generate random masking_key as u_int (32 bits / 4 bytes)
        masking_key = struct.pack('!I', random.getrandbits(32))
        try:
            clconn.write(masking_key)
        except:
            print('socket write error')
            return
            
        data = bytes(b ^ masking_key[i % 4] for i, b in enumerate(CRAFT['DATA']))
        try:
            clconn.write(data)
        except:
            print('socket write error')
            return
    else:
        try:
            clconn.write(CRAFT['DATA'])
        except:
            print('socket write error')
            return



def read_frame(clconn, addr_port):
    '''
    Spec:
    https://tools.ietf.org/html/rfc6455
    
    Follow below link for decode the frame:
    https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_servers
    
    '''
    
    VALID = False
    FIN = False
    OPCODE = OP_CONT
    DATA = b''
    
    DECODED = {'VALID': VALID, 'FIN': FIN, 'OPCODE': OPCODE, 'DATA': DATA}

    while not FIN:
        # get 2 bytes 
        try:
            fin_opcode = clconn.read(2)
        except:
            print('failed to read header')
            return DECODED
        try:
            byte1, byte2 = struct.unpack('!BB', fin_opcode) #big_endian u_char u_char
        except:
            print('failed to unpack header')
            return DECODED
        
        # Byte 1: FIN|1| RESV|1| RESV|1| RESV|1| OPCODE|4|
        FIN = bool(byte1 & 0x80) # byte1 & 1000 0000
        OPCODE = byte1 & 0x0f    # byte1 & 0000 1111
        #print('FIN: '+str(fin)+', OPCODE: '+str(opcode))
        
        # Byte 2: MASK|1| PAYLOADLEN|7| 
        masked = bool(byte2 & 0x80) # byte2 & 1000 0000 (bit 8)
        
        # if payloadlen <= 125, then payloadlen is real payload
        payloadlen = byte2 & 0x7f # byte2 & 0111 1111 (bits 9 - 15) - 7 bits
        
        # if payloadlen == 126, then get next 16 bits (2 bytes) as u_int
        if payloadlen == 126:
            # update payloadlen with ext len 16 bits
            # print('stage2')
            try:
                payloadlen, = struct.unpack('!H',clconn.read(2)) # big_endian u_short
            except:
                print('failed to read ext length 16 bits')
                return DECODED
                
        # if payloadlen == 127, then get next 64 bits ( 8 bytes) as u_int (with MSB 0)
        if payloadlen == 127:
            # update payloadlen with ext len 64 bits
            # print('stage3')
            try:
                payloadlen, = struct.unpack('!Q', clconn.read(8)) # big_endian u_long_long
            except:
                print('failed to read ext length 64 bits')
                return DECODED        
    
        #print('MASKED: '+str(masked)+', PAYLOADLEN: '+str(payloadlen))
        
        # if masked read next 32bits (4 bytes) for the masking key
        if masked:
            try:
                masking_key = clconn.read(4)
            except:
                print('error read masking_key')
                return DECODED
        
        # get payload
        try:
            PAYLOAD = clconn.read(payloadlen)
        except:
            print('faild to read payload')
            return DECODED
        
        if masked:
            PAYLOAD = bytes(b ^ masking_key[i % 4] for i, b in enumerate(PAYLOAD))
        
        DATA += PAYLOAD
    
    VALID = True
    
    return {'VALID': VALID, 'FIN': FIN, 'OPCODE': OPCODE, 'DATA': DATA}


def broadcast_msg(CLS, msg):
    
    for clconn in CLS:
        if clconn['WS']:
            write_frame(clconn['CLCONN'], {'FIN': True, 'OPCODE': OP_TEXT, 'MASKED': False, 'DATA': msg})

    

def drive_robotic(command):
    #print(command)
    cmd = command.split(b':')
    
    if cmd[0] == b'ctrl':
        val = cmd[1]
        #print(val)
        if val==b'fwd':
            print('CMD_MOVE_1')
        elif val==b'bwd':
            print('CMD_MOVE_2')
        elif val==b'right':
            print('CMD_MOVE_3')
        elif val==b'left':
            print('CMD_MOVE_4')
        elif val == b'fwdright':
            print('CMD_MOVE_5')
        elif val == b'fwdleft':
            print('CMD_MOVE_6')
        elif val == b'bwdright':
            print('CMD_MOVE_7')
        elif val == b'bwdleft':
            print('CMD_MOVE_8')
        elif val == b'CW':
            print('CMD_MOVE_9')
        elif val == b'CCW':
            print('CMD_MOVE_10')
        elif val == b'flash':
            flash.value(not flash.value())
            if flash.value():
                broadcast_msg(CLIENTS, b'flash:on')
            else:
                broadcast_msg(CLIENTS, b'flash:off')
        else:
            print('CMD_MOVE_0')
    elif cmd[0] == b'speed':
        val = cmd[1].decode("utf-8")
        print('CMD_SPEED_'+val)
    elif cmd[0] == b'cam':
        val = cmd[1].decode("utf-8")
        print('CMD_CAM_'+val)        
    else:
        print('CMD_MOVE_0')



def ws_handler(clconn, addr_port, parsed):
    #print('This is web socket request')

    # scan the Sec-WebSocket-Key
    for header in parsed['HEADERS']:
        HDR = header.split(b':')
        if b'Sec-WebSocket-Key' in HDR[0]:
            WSKEY = HDR[1].strip()
        if b'Sec-WebSocket-Version' in HDR[0]:
            WSVER = HDR[1].strip()

    #print(WSKEY)
    #print(WSVER)
    
    RESP=ubinascii.b2a_base64(uhashlib.sha1(WSKEY+MSTR).digest()).rstrip(b'\n')
    #print(RESP)

    try:
        clconn.send(b'HTTP/1.1 101 Switching Protocols\r\n')
        clconn.send(b'Upgrade: websocket\r\n')
        clconn.send(b'Connection: Upgrade\r\n')
        clconn.send(b'Sec-WebSocket-Accept: '+RESP+'\r\n')
        clconn.send(b'\r\n')

    except:
        print('socket error: sending failure')
        return
    
    while True:
        DF = read_frame(clconn, addr_port)
        if DF['OPCODE'] == OP_CLOSE:
            #write_frame(clconn, {'FIN': True, 'OPCODE': OP_CLOSE, 'MASKED': False, 'DATA': b''})
            break
            
        if DF['VALID']:
            #print(DF['DATA'])
            drive_robotic(DF['DATA'])
        else:
            break



def check_websocket(clconn, addr_port, parsed):
    # check for websocket
    # ===================
    # get http version
    try:
        HTTPVER=float(parsed['PROTOCOL'].split(b'/')[1])
    except:
        print('HTTP version not valid')
        return       
    #print(HTTPVER)
    
    UPGWEBSOCK = False
    CONNUPG = False
    
    # scan all the headers
    for header in parsed['HEADERS']:
        HDR = header.split(b':')
        if b'Upgrade' in HDR[0] and b'websocket' in HDR[1]:
            UPGWEBSOCK = True
        if b'Connection'in HDR[0] and b'Upgrade' in HDR[1]:
            CONNUPG = True
    
    # if got web socket request
    if HTTPVER>=1.1 and UPGWEBSOCK and CONNUPG:
        for i, j in enumerate(CLIENTS, start=0):           
            if j['CLPORT'][1] == addr_port[1]:
                CLIENTS[i]['WS'] = True
   
        return True

    return False


def url_root_handler(clconn, addr_port, parsed):    
    # normal http request
    # ===================
    parsed['URL'] = b'/rover.html'
    
    try:
        # Load file
        with open(parsed['URL'],'rb') as file:
            page = file.read()
            file.close()
    except:
        return False

    ownipaddr = wlan.ifconfig()[0]
    page = page.replace(b'ws://localhost', b'ws://'+ownipaddr)
    
    try:    
        clconn.send(b'HTTP/1.1 200 OK\r\n')
        clconn.send(b'Content-Type: text/html\r\n')
        clconn.send(b'Content-Length: '+str(len(page))+'\r\n')
        clconn.send(b'Connection: keep-alive\r\n')
        clconn.send(b'\r\n')
        
        clconn.send(page)
        clconn.send('\r\n\r\n')

    except:
        print('socket error: sending failure')
        return True
    # ===================    

def url_ctrl_handler(clconn, addr_port, parsed):
    # go to websocket handler if requested
    if check_websocket(clconn, addr_port, parsed):
        ws_handler(clconn, addr_port, parsed)
        return
    
    # normal http request
    # ===================
    PAGE = b'<!DOCTYPE html><html><body><h2>This URL is for websocket connection</h2></body></html>'

    try:
        clconn.send(b'HTTP/1.1 200 OK\r\n')
        clconn.send(b'Content-Type: text/html\r\n')
        clconn.send(b'Content-Length: '+str(len(PAGE))+'\r\n')
        clconn.send(b'Connection: keep-alive\r\n')
        clconn.send(b'\r\n')
        clconn.send(PAGE)
        clconn.send(b'\r\n\r\n')

    except:
        print('socket error: sending failure')
        return
    # ===================

def url_stream_handler(clconn, addr_port, parsed):

    boundary=b'123456789000000000000987654321'

    try:    
        clconn.send(b'HTTP/1.1 200 OK\r\n')
        clconn.send(b'Access-Control-Allow-Origin: *\r\n')
        clconn.send(b'Content-Type: multipart/x-mixed-replace; boundary='+boundary+b'\r\n')
        clconn.send(b'\r\n')
    except:
        print('socket error: sending failure') 

    while STREAM:
        
        # get the picture and store in frame buffer
        try:
            fb = camera.capture()
        except:
            print('camera capture failure')
        
        try:
            clconn.send(b'--'+boundary+'\r\n')
            clconn.send(b'Content-Type: image/jpeg\r\n')
            clconn.send(b'Content-Length: '+str(len(fb))+b'\r\n')
            clconn.send(b'\r\n')
            clconn.send(fb)
            clconn.send(b'\r\n')
        except:
            print('socket error: sending failure')
            return
    

def url_notfound(clconn, addr_port, parsed):
    PAGE = b'<!DOCTYPE html><html><body><h2>Page not found!</h2></body></html>'

    try:
        clconn.send(b'HTTP/1.1 404 Not Found\r\n')
        clconn.send(b'Content-Type: text/html\r\n')
        clconn.send(b'Content-Length: '+str(len(PAGE))+'\r\n')
        clconn.send(b'\r\n')
        clconn.send(PAGE)
        clconn.send(b'\r\n\r\n')
    except:
        print('socket error: sending failure')
        return


def load_file(clconn, addr, parsed): 
       
    # set mimetype
    if parsed['URL'].endswith(b'.html') or parsed['URL'].endswith(b'.htm'):
        mimetype = b'Content-Type: text/html\r\n'
    elif parsed['URL'].endswith(b'.css'):
        mimetype = b'Content-Type: text/css\r\n'        
    elif parsed['URL'].endswith(b'.txt'):
        mimetype = b'Content-Type: text/plain\r\n'        
    elif parsed['URL'].endswith(b'.js'):
        mimetype = b'Content-Type: application/javascript\r\n'
    elif parsed['URL'].endswith(b'.jpg') or parsed['URL'].endswith(b'.jpg'):
        mimetype = b'Content-Type: image/jpeg\r\n'
    elif parsed['URL'].endswith(b'.png'):
        mimetype = b'Content-Type: image/png\r\n'    
    elif parsed['URL'].endswith(b'.gif'):
        mimetype = b'Content-Type: image/gif\r\n'
    elif parsed['URL'].endswith(b'.ico'):
        mimetype = b'Content-Type: image/vnd.microsoft.icon\r\n'
    else:
        return False
        
    try:
        # Load file
        with open(parsed['URL'],'rb') as file:
            page = file.read()
            file.close()
    except:
        return False

    
    try:    
        clconn.send(b'HTTP/1.1 200 OK\r\n')
        clconn.send(mimetype)
        clconn.send(b'Content-Length: '+str(len(page))+'\r\n')
        clconn.send(b'Connection: keep-alive\r\n')
        clconn.send(b'\r\n')
        
        clconn.send(page)
        clconn.send('\r\n\r\n')

    except:
        print('socket error: sending failure')
        return True
    
    return True
    
def http_get_handler(clconn, addr_port, parsed):
    
    #print(parsed)
    
    # load registered URL:
    if parsed['URL'] == b'' or parsed['URL'] == b'/':
        url_root_handler(clconn, addr_port, parsed)
    elif parsed['URL'] == b'/ctrl' or parsed['URL'] == b'/ctrl/':
        url_ctrl_handler(clconn, addr_port, parsed)
    elif parsed['URL'] == b'/stream' or parsed['URL'] == b'/stream/':
        url_stream_handler(clconn, addr_port, parsed)        
    # else try to load / open file
    else:
        if not load_file(clconn, addr_port, parsed):
            url_notfound(clconn, addr_port, parsed)


def conn_handler(clconn, addr_port):

    global NCLIENT
    NCLIENT += 1
    
    CLIENT_NUM = NCLIENT
    
    print('connection instance: '+str(CLIENT_NUM)+', connected to: '+str(addr_port[0])+':'+str(addr_port[1])+' created')
    
    req = b''

    while True:
        rawstr = clconn.recv(8192)
        req = req + rawstr
        break
        #if b'\r\n\r\n' in req:
        #    break

    parsed = parse_http_req(req)

    if parsed['VALID']:
        if parsed['METHOD'] == b'GET':
            http_get_handler(clconn, addr_port, parsed)
               
    clconn.close()
    
    for i, j in enumerate(CLIENTS, start=0):       
        if j['CLPORT'][1]==addr_port[1]:
            CLIENTS.pop(i)
            break
    
    NCLIENT -= 1
    print('connection instance: '+str(CLIENT_NUM)+' ('+str(addr_port[0])+':'+str(addr_port[1]) +') exit')

    
def socket_worker(socket_ins):

    while CONN_EN:
        try:
            clconn, addr_port = socket_ins.accept()        
            CLIENTS.append({'CLCONN': clconn, 'CLPORT': addr_port, 'WS': False})
        except:
            print('error create listening socket')
            reset()
            break
        
        try:
            _thread.start_new_thread(conn_handler, (clconn, addr_port,))
        except:
            print('error on thread creation')
            reset()
            break


if __name__ == "__main__":
    # start the main thread
    rover = _thread.start_new_thread(socket_worker, (webs,))
