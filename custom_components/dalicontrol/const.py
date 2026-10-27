"""Constants for the DALIcontrol integration."""

DOMAIN = "dalicontrol"

CONF_CONTROLLER_ID = "controller_id"
CONF_PROTOCOL = "protocol"
CONF_LIGHTS = "lights"

CONF_KIND = "kind"
CONF_LINE = "line"
CONF_ADDRESS = "address"

PROTOCOL_UDP = "udp"
PROTOCOL_TCP = "tcp"

DEFAULT_PORT = {PROTOCOL_UDP: 1235, PROTOCOL_TCP: 1001}

KIND_GROUP = "group"
KIND_BALLAST = "ballast"
KIND_BROADCAST = "broadcast"

LINE_BOTH = "both"
LINE_A = "a"
LINE_B = "b"
