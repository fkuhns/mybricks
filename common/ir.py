from machine import Pin, enable_irq, disable_irq
from common import Device, DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN, IR_PIN
from ir_sensor import NEC_8, IR_RX
from motor import MOTOR_CMD_FORWARD, MOTOR_CMD_LEFT, MOTOR_CMD_REVERSE, MOTOR_CMD_RIGHT, \
                  MOTOR_CMD_STOP, MOTOR_CMD_NOOP

## IR remote for the smart car
# The NEC decoder runs in interrupt context: its callbacks only save the last
# command and error code. run() is called from the main loop, picks them up
# with interrupts disabled, maps the command to a motor command and queues it.
# Only the most recent command is kept, a newer one overwrites an unread one.

IR_ERRS = {IR_RX.BADSTART: "BADSTART",
           IR_RX.BADBLOCK: "BADBLOCK",
           IR_RX.BADREP:   "BADREP",
           IR_RX.OVERRUN:  "OVERRUN",
           IR_RX.BADDATA:  "BADDATA",
           IR_RX.BADADDR:  "BADADDR"}

# IR command -> motor command, no mapping for MOTOR_CMD_STOP_FORCE
IR_CMD_MAP = {
    IR_RX.number_up:    MOTOR_CMD_FORWARD,
    IR_RX.number_down:  MOTOR_CMD_REVERSE,
    IR_RX.number_left:  MOTOR_CMD_LEFT,
    IR_RX.number_right: MOTOR_CMD_RIGHT,
    IR_RX.number_ok:    MOTOR_CMD_STOP,
    IR_RX.REPEAT:       MOTOR_CMD_NOOP,
}

class IRMgr(Device):
    def __init__(self, motors, oled, debug=0):
        # FIXME: removed from init args: pin=IR_PIN, cmd_map=IR_CMD_MAP,
        # Add later if needed, but for now just use defaults
        self.DEBUG   = debug
        self.motors  = motors
        self.oled    = oled
        self.cmd_map = IR_CMD_MAP
        self.err_code = 0
        self.cmd      = 0x00
        self.rx       = False

        # receiver is created once, its pin irq is only on while started
        self.ctrl = NEC_8(Pin(IR_PIN, Pin.IN), self.callback) # type: ignore
        self.ctrl.error_function(self.err)
        self.init()

        if self.DEBUG >= DEBUG_INFO:
            print("IRMgr: IR up: ", self.ctrl)

    # Device hooks
    def _init(self):
        self.ctrl.init()
        self._clear()

    def _start(self):
        self._clear()
        self.ctrl.start()

    def _stop(self):
        self.ctrl.stop()
        self._clear()

    def _clear(self):
        # drop any unread command or error
        s = disable_irq()
        try:
            self.err_code = 0
            self.cmd      = 0x00
            self.rx       = False
        finally:
            enable_irq(s)

    def __str__(self):
        return "IRMgr: rx %s cmd 0x%02x err %d" % (self.rx, self.cmd, self.err_code)


    # ---------------- interrupt context ----------------
    def callback(self, cmd, addr, _):
        # An IR message has been received, ignore address.
        # FIXME: Add command queue
        self.cmd = cmd
        self.rx  = True
        if self.DEBUG >= DEBUG_VERB:
            print('# IR Callback -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

    def err(self, code):
        self.err_code = code

    # ---------------- main loop ----------------
    def ck_err_code(self):
        s = disable_irq()
        try:
            code = self.err_code
            self.err_code = 0
        finally:
            enable_irq(s)

        # Errors are < -1 (repeat cmd), a 0 means no errors
        if  code < IR_RX.REPEAT:
            try:
                if self.DEBUG >= DEBUG_ERROR:
                    print("IR Error: ", IR_ERRS[code])
                self.oled.update_row3(IR_ERRS[code])
            except KeyError:
                self.oled.update_row3("bad code")

    def process(self, cmd):
        motor_cmd = self.cmd_map.get(cmd)
        if motor_cmd is None:
            if self.DEBUG >= DEBUG_ERROR:
                print("IRMgr.process: Invalid command ", cmd)
            self.oled.update_row3("Unknown IR cmd")
            return
        self.motors.add_cmd(motor_cmd)

    def run(self):
        # first see if there is a pending error code
        self.ck_err_code()

        # Now see if there is a pending command
        if not self.rx:
            return

        s = disable_irq()
        try:
            # critical section
            self.rx  = False
            code     = self.cmd
            self.cmd = 0
        finally:
            enable_irq(s)

        try:
            # I2CExceptions & OSError are handled below process
            self.process(code)
        except Exception as e:
            if self.DEBUG >= DEBUG_WARN:
                print("** IRMgr.run: General exception, ignoring: ", e)
