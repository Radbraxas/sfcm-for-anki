# TCP connection lifecycle

TCP is a connection-oriented transport protocol: two hosts must establish a connection before exchanging data, and they tear it down explicitly afterwards.

## Opening: the three-way handshake

1. The client sends a segment with the SYN flag set and an initial sequence number (ISN) chosen at random.
2. The server answers with SYN and ACK set. It acknowledges the client's ISN plus one and sends its own ISN.
3. The client replies with ACK, acknowledging the server's ISN plus one.

Random initial sequence numbers make it harder for an attacker to inject forged segments into a connection, and reduce confusion with segments left over from an earlier connection between the same ports.

A server that receives many SYN segments but never the final ACK keeps half-open connections in its backlog. Flooding a server this way is called a SYN flood. SYN cookies defend against it by encoding the connection state in the server's ISN instead of storing it.

## Closing

Either side can close. Closing takes four segments because each direction is shut down independently: a FIN from one side, an ACK from the other, then a FIN and ACK in the opposite direction.

The side that closes first enters the TIME_WAIT state after the exchange and stays there for twice the maximum segment lifetime (2MSL). TIME_WAIT ensures the final ACK can be retransmitted if it is lost, and that delayed segments from the old connection expire before the same port pair is reused.

A connection can also be aborted with an RST segment, which ends it immediately without the orderly FIN exchange.
