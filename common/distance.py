from utime import ticks_ms, ticks_diff
from common import Device, DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN
from usonic import UltrasonicSensor, UltraSonicTimeout
from motor import MOTOR_CMD_FORWARD, MOTOR_CMD_LEFT, MOTOR_CMD_REVERSE, MOTOR_CMD_STOP

## Distance zones for the smart car
# Pings the ultrasonic sensor, maps each reading to a zone and queues the
# zone's motor command on a zone change. To limit the number of motor commands:
# - a ping is sent at most every DIST_INTERVAL_MS
# - a new zone must be seen DIST_ZONE_PEND_CNT readings in a row before the
#   car switches to it, so commands are at least
#   DIST_ZONE_PEND_CNT * DIST_INTERVAL_MS apart
# - while the zone stays the same nothing is sent, unless the zone has a
#   refresh time (repeat the command every REFRESH_MS)

DIST_ZONE_INVALID = const(-1)
DIST_ZONE_0 = const(0)
DIST_ZONE_1 = const(1)
DIST_ZONE_2 = const(2)
DIST_ZONE_3 = const(3)
DIST_ZONE_CNT = const(4)

# (zid, start, stop, CMD, ARG, REFRESH_MS)
ZONE_ZID_INDX     = const(0)
ZONE_START_INDX   = const(1)
ZONE_STOP_INDX    = const(2)
ZONE_CMD_INDX     = const(3)
ZONE_ARG_INDX     = const(4)
ZONE_REFRESH_INDX = const(5)

# readings in a row needed to change zones
DIST_ZONE_PEND_CNT = const(3)

DIST_TIMEOUT     = -1.0 # reading when no echo is received
DIST_MIN_INCHES  =   1 # inches, smallest change shown on the OLED
DIST_INTERVAL_MS =  80 # HC-SR04 needs >= 60ms between pings
DIST_MAX_IN      = (12 * 20) # Equivalent to infinity

# Zones must be in order and cover DIST_TIMEOUT up to DIST_MAX_IN,
# a reading >= DIST_MAX_IN is in the last zone
DIST_ZONES = (
    # (ZONE, start_in, stop_in, CMD, ARG, REFRESH_MS)
    (DIST_ZONE_0, -1,  0,          MOTOR_CMD_STOP,    0,   0),
    (DIST_ZONE_1,  0, 12,          MOTOR_CMD_REVERSE, 0,   0),
    (DIST_ZONE_2, 12, 30,          MOTOR_CMD_LEFT,    0, 750),
    (DIST_ZONE_3, 30, DIST_MAX_IN, MOTOR_CMD_FORWARD, 0,   0)
)

class DistException(Exception):
    pass

class CarDist(Device):
    def __init__(self, 
                 motors, oled, 
                 sonic=None, # FIXME: Should this be an arg now?
                 zones=DIST_ZONES, # FIXME: Should this be an arg now?
                 pend_cnt=DIST_ZONE_PEND_CNT, # FIXME: Should this be an arg now?
                 debug=0):
        self.DEBUG    = debug
        self.motors   = motors
        self.oled     = oled
        self.sonic    = sonic if sonic is not None else UltrasonicSensor()
        self.zones    = zones
        self.pend_cnt = pend_cnt
        self.init()

        if self.DEBUG >= DEBUG_INFO:
            print("CarDist: Distance env up")

    def __str__(self):
        return "CarDist: zone %d pending %d (%d)" % (self.zid, self.zone_pending, self.pending_cnt)

    # Device hooks, starting forgets the zone so its command is sent again
    def _init(self):
        self.reset()

    def _start(self):
        self.reset()

    def reset(self):
        # forget the current zone, the next reading sends its command
        self.zid          = DIST_ZONE_INVALID
        self.zone_pending = DIST_ZONE_INVALID
        self.pending_cnt  = 0

        self.ping_ms = 0 # time of the last ping
        self.cmd_ms  = 0 # time of the last motor command

        self.disp_dist = DIST_TIMEOUT # distance on the OLED

    def read(self):
        try:
            # throws Ultrasonic exception for timeouts or other errors
            return self.sonic.get_distance() # distance in inches
        except UltraSonicTimeout:
            if self.DEBUG >= DEBUG_INFO:
                print("CarDist.read: echo not received in timeout")
            return DIST_TIMEOUT

    def show(self, dist):
        if dist < 0:
            # only redraw on the first timeout in a row
            if self.disp_dist < 0:
                return
            self.oled.update_row2("Dist: --")
        elif self.disp_dist < 0 or abs(dist - self.disp_dist) >= DIST_MIN_INCHES:
            self.oled.update_row2("%d\' %.2f\"" % (dist // 12, dist % 12))
        else:
            return
        self.disp_dist = dist

    def find_zone(self, dist):
        for z in self.zones:
            if z[ZONE_START_INDX] <= dist < z[ZONE_STOP_INDX]:
                return z

        last = self.zones[-1]
        if dist >= last[ZONE_STOP_INDX]:
            return last

        raise DistException("CarDist.find_zone: Error, no zone for distance %.2f" % dist)

    def run(self):
        # consecutive reads must be spaced at least 60ms apart
        # --------------- check time interval ---------------
        now_ms = ticks_ms()
        if ticks_diff(now_ms, self.ping_ms) < DIST_INTERVAL_MS:
            return
        self.ping_ms = now_ms

        dist = self.read()
        self.show(dist)

        # --------------- determine dist zone ---------------
        zone = self.find_zone(dist)
        zid  = zone[ZONE_ZID_INDX]

        if self.DEBUG >= DEBUG_VERB:
            print("CarDist.run: zone %d for distance %.2f" % (zid, dist))

        # --------------- check for zone transition ---------------
        if zid == self.zid:
            # no change to distance zone, drop any pending zone
            self.zone_pending = DIST_ZONE_INVALID
            self.pending_cnt  = 0
            refresh = zone[ZONE_REFRESH_INDX]
            if refresh == 0 or ticks_diff(now_ms, self.cmd_ms) < refresh:
                return # do nothing

        elif self.zid != DIST_ZONE_INVALID and self.pend_cnt > 1:
            # new zone, wait until it has been seen pend_cnt times in a row
            if zid != self.zone_pending:
                self.zone_pending = zid
                self.pending_cnt  = 1
                return
            self.pending_cnt += 1
            if self.pending_cnt < self.pend_cnt:
                return

        # --------------- send the zone's command ---------------
        # check for special case
        if zid == DIST_ZONE_0:
            self.motors.clear_cmds()

        if not self.motors.add_cmd(zone[ZONE_CMD_INDX], zone[ZONE_ARG_INDX]):
            # queue is full, state is unchanged so the next reading tries again
            if self.DEBUG >= DEBUG_WARN:
                print("CarDist.run: motor queue full, zone %d cmd not sent" % zid)
            return

        if self.DEBUG >= DEBUG_INFO and zid != self.zid:
            print("CarDist.run: Transition to zone %d, dist = %.2f ... %d\' %.2f\"" % (zid, dist, dist // 12, dist % 12))

        self.zid          = zid
        self.zone_pending = DIST_ZONE_INVALID
        self.pending_cnt  = 0
        self.cmd_ms       = now_ms
