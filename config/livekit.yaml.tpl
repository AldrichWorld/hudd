# Rendered by deploy.sh from .env into config/livekit.yaml. Edit .env, not livekit.yaml.
port: 7880
log_level: info
rtc:
  tcp_port: ${LIVEKIT_TCP_PORT}
  udp_port: ${LIVEKIT_UDP_PORT}
  use_external_ip: false
  node_ip: ${PUBLIC_HOST}
keys:
  ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
room:
  # Meetings only exist when Hudd creates them (an old link cannot bring an ended meeting back)
  auto_create: false
  empty_timeout: ${ROOM_EMPTY_TIMEOUT}
  departure_timeout: ${ROOM_DEPARTURE_TIMEOUT}
