# Experimental wire-header accounting

These are sensitivity assumptions, not UB standard headers. Native single-target WRITE remains payload +78 bytes in every mode. ACK and Transaction Response bytes are not discounted.

## Full (accepted baseline)

For fanout F>1, actual packet size P+32+137F.

- Outer data-link header:4B.
- Envelope common fields: magic4,group4,sequence4,payload length4,member count4,destination bitmap8 =28B.
- Each target:rank4,prefix length4,native prefix78,FlowTag8,TransactionCorrelationTag42,ExplicitPayloadTag1 =137B.
- Payload:P actual received bytes, once on source link and once per switch output branch.

## Compact Oracle

Actual packet size P+32+16F. Common32B unchanged. Each target explicitly carries four32-bit quantities:rank,destination TP,PSN,SSN. This is a field-budget experiment with an ideal preinstalled native-header context, not a claim that those fields suffice to implement a real protocol. Native identity/address/opcode/correlation fields omitted from the wire are retained as immutable prefix/tag-only oracle context. Context creation/lookup and installation have no simulated control-plane cost. Payload itself may never be read from this context.

The exact common identity, destination member and per-target fields must validate before restoring an original child prefix. Context lifetime is limited to pending recipient branches and is reclaimed when all expected recipients consume it. Missing/duplicate/wrong member context fails rather than inventing success. All child TPs still generate and consume actual native ACK/Response and obey their own windows.

## Ideal Oracle lower bound

Actual packet size P+32 for F>1. Only common fields are charged; all per-target native header information uses oracle context. This is a fixed-common-header ideal bound for this implementation, not zero overhead and not a proof of achievability.

## What the experiment changes

The actual ns-3 Packet contains the selected header budget plus full Payload. GetNextPacketSize must match Packet::GetSize. Native source and switch queues, port serialization and CBFC cells therefore see that size. Every branch retains the charged envelope; the switch does not strip or decompress it. Receiver reconstructs the full native child packet only after physical network reception, using received payload bytes.

Each TA still has exactly the original native data/response/ACK sequencing. No fixed time discount or RTT adjustment is allowed. Oracle logical-decoding bytes and charged bytes are reported separately. The full mode is default and must reproduce previous bytes/events. Singleton uses the unchanged native path regardless of the selected experimental model.

For1024B payload: full/compact/ideal F2=1330/1088/1056B; F3=1467/1104/1056B; F4=1604/1120/1056B; F8=2152/1184/1056B. Corresponding160B CBFC cells: F2=9/7/7; F3=10/7/7; F4=11/7/7; F8=14/8/7. Singleton1102B=7cells. Credit control frames retain their native accounting.
